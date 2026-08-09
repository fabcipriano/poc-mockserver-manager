## Context

`mock-ui/app.py` today only talks to MockServer's `/mockserver/expectation`, `/mockserver/retrieve?type=
ACTIVE_EXPECTATIONS`, and `/mockserver/clear` endpoints - nothing touches MockServer's request history.
`mock-ui/static/index.html`/`app.js` have a working four-page-minus-one shell (Create Mock, List Mocks,
Help) with hash-based routing (`VALID_PAGES`, `showPage()`) from the previous change. See proposal.md - Why
for motivation.

Verified live against the actual running MockServer (`5.15.0`, this repo's pinned version) while
researching this change:

- `PUT /mockserver/retrieve?type=REQUEST_RESPONSES` returns every request MockServer has received - mocked
  or forwarded alike - each as `{httpRequest, httpResponse, timestamp}`. `timestamp` is a sortable string
  like `"2026-08-09 03:51:40.823"`. Confirmed the array comes back in chronological order (oldest first);
  fired three sequenced requests and the retrieve response returned them in the same order they were sent.
- **The `path` field in the retrieve matcher is a full-match regex, not a substring/contains search** -
  confirmed live: filtering with the plain string `/booking` matched only requests whose path was
  *exactly* `/booking`, while `.*booking.*` matched every path containing "booking"
  (`/booking`, `/booking/1`, `/booking/2`, ...). A developer typing a plain path fragment into a search box
  expects "contains," so `mock-ui`'s backend must wrap the query in `.*<escaped>.*` before sending it as
  the matcher - the developer never sees or writes regex themselves.
- `REQUEST_RESPONSES` entries carry **no field indicating whether the request was mocked or forwarded** -
  just the request and whatever response was actually sent. There's no reliable way to derive "was this
  mocked" from this API alone without fragile guesswork (cross-referencing against currently-active
  expectations, which can itself change between the request and the query). This page shows real traffic
  and real responses; it doesn't claim to label provenance it doesn't have.
- Retention is bounded (`MOCKSERVER_MAX_LOG_ENTRIES`, in-memory ring buffer, not part of the
  `MOCKSERVER_PERSIST_EXPECTATIONS` persistence added previously) and does **not** survive a `mockserver`
  pod restart - already known from prior research in this project, re-confirmed here since it's directly
  relevant to what this page can show.

## Goals / Non-Goals

**Goals:**
- A fourth page, Recent Requests, showing MockServer's actual request history (timestamp, method, path,
  status), newest first.
- Filter by path, as a plain substring search (no regex knowledge required).
- A genuinely live (push-based) tail of new matching requests while the page is open.
- A pause/resume control so a developer can stop the list moving while reading, without losing the stream.
- The filter scopes both the initial history shown and what the live tail continues to add.

**Non-Goals:**
- Labeling whether a request was "mocked" vs "forwarded" - not reliably derivable from MockServer's API,
  per Context above; out of scope rather than shipped as a guess.
- Filtering by anything other than path (method, status code, headers, etc.) - path was what was asked for;
  additional filter dimensions are a reasonable future follow-up.
- Persisting or exporting request history - this page is a live window onto MockServer's own (bounded,
  restart-losing) log, not a new store `mock-ui` keeps itself.
- Pagination/infinite scroll through MockServer's full retained history - the page shows a bounded recent
  window (see Decisions); older entries beyond that aren't a concern this change addresses.

## Decisions

1. **Server-Sent Events (SSE) for the live tail, not client-side polling.** `mock-ui/app.py` gains a
   streaming endpoint (`GET /mock-ui/api/requests/stream`) that polls MockServer's `REQUEST_RESPONSES`
   server-side on a short interval (~1s), tracks the timestamp of the last entry it has already sent, and
   `yield`s only the new ones as `text/event-stream` events. The browser consumes this with the native
   `EventSource` API - no new client dependency.
   - Alternative considered: `setInterval` + `fetch` polling from the browser directly. Rejected - the
     ask was explicitly for something that follows requests "in real time," and polling reads as laggy
     /mechanical next to a push-based stream; SSE isn't meaningfully more code (Flask supports streaming
     responses natively, no new dependency) for a noticeably better result.
   - Alternative considered: WebSockets. Rejected - overkill for a one-directional (server-to-browser)
     feed; SSE is the simpler primitive for exactly this shape and needs no extra library on either side.
2. **New-entry detection is timestamp-cursor-based, not index-based.** The stream generator remembers the
   timestamp string of the last entry it emitted and, each poll, emits every entry after that point in the
   (confirmed chronological) response. An index/count-based cursor would break if the ring buffer evicts
   old entries between polls, shifting every index; a timestamp cursor doesn't care how many older entries
   fell off the front.
3. **The path filter re-establishes the SSE connection with the new filter as a query parameter**, rather
   than streaming everything and filtering client-side. Keeps the same substring-search semantics (Decision
   in Context: wrap in `.*...*`) applied server-side to both the initial history fetch and the live stream,
   so a developer never sees an unfiltered flood while a filter is active, and the backend - not the
   browser - is the one place that knows how to turn a plain string into MockServer's matcher syntax.
4. **A bounded initial history window (most recent 100 entries) rather than MockServer's entire retained
   log.** `GET /mock-ui/api/requests?path=<optional>` returns at most the 100 most recent matching entries
   on page load / filter change; the live tail then adds to that from the point the page opened. Keeps the
   initial render and the DOM bounded regardless of how much history MockServer happens to be holding.
5. **Pause/Resume stops rendering new entries without closing the `EventSource` connection.** The stream
   keeps running in the background (so no entries are silently dropped and lost - they're just queued
   client-side); Resume flushes the queue into the list. Alternative considered: closing the connection on
   Pause and reopening on Resume. Rejected - would need to re-fetch history to fill the gap and lose exactly
   the entries a developer paused to go read about; keeping the connection open and buffering client-side is
   simpler and doesn't lose data.
6. **Recent Requests joins the existing hash-routing shell as a fourth entry** (`#requests`), reusing
   `showPage()`/`VALID_PAGES` from the prior change - no new navigation mechanism.

## Risks / Trade-offs

- [Flask's threaded dev server holding open a long-lived SSE connection per browser tab.] -> Mitigation:
  acceptable at this POC's scale (one developer, one browser tab at a time); already documented as a known
  limitation of using Flask's dev server in production (see the previous `mock-ui` change's design.md).
- [1-second server-side polling of MockServer's retrieve API adds continuous background load while the
  Recent Requests page is open.] -> Mitigation: negligible at this POC's traffic volume; the polling only
  runs while a browser has the stream open, not continuously in the background otherwise.
- [No provenance (mocked vs. forwarded) shown, which a developer might expect from a "requests" view.] ->
  Mitigation: explicitly a Non-Goal with the reason documented (not reliably derivable) rather than an
  oversight; status code and response body are still visible and usually make it obvious.
- [History is lost on a `mockserver` pod restart, same as MockServer's own retrieve API.] -> Mitigation:
  not a regression this change introduces - inherent to what MockServer itself retains; worth a line on the
  page itself so it isn't mistaken for a `mock-ui` bug.

## Migration Plan

No data migration - net-new, read-only page over MockServer's existing API. Rollout is rebuilding and
redeploying the `mock-ui` image; rollback is reverting to the prior image, with nothing persisted by this
feature to reconcile either way.
