# Study: Making the Recent Requests page resilient to high request volume

**Status:** Study only - no code changed. Written to seed an `/opsx:propose` for whichever
direction gets picked.
**Trigger:** `scripts/load-test-recent-requests.sh` (20,000 requests) made the Recent Requests
page fail.

## 1. Problem statement

After running the load test, the Recent Requests page becomes unusable. The ask was to
investigate why, and to evaluate two specific mitigations - pagination (max 100 items/page)
and search by time/date - as a way to browse a large request history without the page falling
over.

## 2. Reproduction and root cause

Reproduced directly against a real MockServer instance (not the k8s POC, to isolate the
variable): seeded 20,000 logged requests, then pointed a `mock-ui` instance at it.

**A single history fetch is already expensive.** `GET /mock-ui/api/requests` took ~0.28s and
the underlying MockServer call (`PUT /mockserver/retrieve?type=REQUEST_RESPONSES`) returned a
9.8MB JSON payload for the full 20,000-entry log - even though the page only ever displays 100
rows.

**The real failure is concurrency, and it's total, not gradual.** With 30 concurrent SSE
connections open to `/mock-ui/api/requests/stream` (i.e. 30 open browser tabs - not an unusual
number for a shared QA/dev environment), the `mock-ui` container's memory grew from ~350MB to
~1.8GB in 15 seconds and CPU pegged at 100%+. Worse: a plain `GET /mock-ui/healthz` - a
handler that does nothing but return `"ok"` - **timed out after 15 seconds**, and none of the
30 streams delivered a single byte in a 20-second window. This isn't degraded performance,
it's a full hang of the process.

**Why:** `mock-ui/app.py`'s `_fetch_request_history()` is the single function behind both
`/api/requests` and the SSE stream. The stream's `event_stream()` generator calls it once per
second, per connection, forever:

```python
while True:
    time.sleep(REQUEST_STREAM_POLL_SECONDS)
    history = _fetch_request_history(path_query, mocked_filter)   # refetches + reparses EVERYTHING
    new_entries = [entry for entry in history if entry["timestamp"] > last_timestamp]
    ...
```

Every tick, every open tab, the full matching log is re-fetched from MockServer and
re-parsed/re-built into Python dicts - work that scales with **total log size**, not with
"how many new requests actually arrived" (usually zero or a handful). `REQUEST_HISTORY_LIMIT =
100` only trims the *final* list right before it's returned to a client; it does nothing to
reduce the fetch/parse cost, which happens well before that slice.

With N open tabs, that's N independent ~10MB JSON parses every second. Flask's dev server
(`threaded=True`) runs each connection in its own OS thread, but CPython's GIL means only one
thread executes Python bytecode at a time - so N threads doing CPU-bound JSON parsing don't
run in parallel, they queue up and starve everything else on the process, including accepting
new connections. That's the mechanism behind the total hang observed above.

**This is the actual bug to fix**, independent of whatever pagination/search design gets
chosen: the page's cost today is `O(open tabs × total log size)` *per second*, unbounded in
both dimensions.

## 3. What MockServer's API can and can't do for us

Researched via MockServer's docs and this session's own testing (see
[Sources](#sources)) since this shapes what's actually implementable:

- **`/mockserver/retrieve` has no pagination, `limit`/`maxResults`, or time-range parameter.**
  Its only filter is a request matcher (method/path/headers/etc., the same shape used for
  expectations) - there's no way to ask MockServer for "the last 100" or "entries after
  timestamp X." Any offset/limit/time-window logic has to happen in `mock-ui` itself, after
  fetching whatever the matcher-filtered set is.
- **MockServer already caps its own log** via `maxLogEntries` (default: `min(free heap KB / 8,
  100000)`), stored as a circular buffer - oldest entries are silently overwritten once the cap
  is hit. So MockServer itself won't grow unbounded forever or OOM from log retention alone,
  but 100,000 retained entries is still enormous to fetch/parse per poll tick, and once an
  entry is evicted from that ring buffer it is **gone** - there is no way to page or search
  back to it. Any "search old requests by date" feature can only ever see as far back as
  MockServer's current ring buffer window, not true unbounded history.

## 4. The architectural tension this creates

The current spec (`openspec/specs/mock-management-ui/spec.md`) has a standing requirement:

> **Web UI reflects MockServer's live state with no independent cache** - every list, create,
> update, and delete action SHALL act directly and synchronously against MockServer's live
> expectation store.

Real pagination and real time-range search both want *some* place to hold a working copy of
"the current window of entries" - even a small one - so a page request costs `O(page size)`
instead of `O(matching log size)`. That's in tension with "no independent cache," which was
written for the mocks CRUD flows (where staleness is a real correctness risk - you don't want
to edit a mock against a stale copy) but was extended to the Recent Requests page's read-only
history view too. History entries are immutable once logged (MockServer never "edits" a past
request), so caching them doesn't carry the same staleness risk that motivated the original
requirement for mocks - but it's still a deliberate departure worth calling out explicitly
rather than quietly reinterpreting, since it's a documented capability, not just an
implementation habit.

Two ways to resolve this, both compatible with fixing the concurrency bug in Section 2:

**Option A - shared poller, still zero persistence.** Replace "N connections each poll
MockServer independently" with a single background poller (one thread/task, regardless of how
many tabs are open) that fetches from MockServer on the same 1-second cadence and fans new
entries out to all connected SSE clients from an in-memory buffer that's continuously
rebuilt/discarded, not persisted. This fixes the `O(tabs × log size)` blowup (turns it into
`O(log size)` regardless of tab count) without keeping any state MockServer doesn't already
have. Pagination and time-range filtering are then applied to that one shared fetch per tick -
still `O(matching log size)` per tick, but paid once, not once per tab. This is the minimal
change that directly fixes what actually broke in the load test, and it doesn't touch the "no
independent cache" requirement's spirit since nothing survives past the next poll tick.

**Option B - a small, bounded, explicit cache.** Keep an actual in-memory index of the
current log window (e.g. a ring buffer mirroring MockServer's own retention, updated
incrementally as new entries are observed), so a page request or a time-range query costs
`O(page size)` / `O(log n)` instead of `O(matching log size)`, and doesn't require re-fetching
the full set from MockServer on every request. This is more scalable if the log gets very
large, but it requires either loosening the "no independent cache" requirement for this one
read-only, immutable-history view, or narrowing that requirement's scope explicitly to say it
governs mock CRUD state, not request history. That's a spec decision, not an implementation
detail, and should be made explicitly in the OpenSpec proposal rather than assumed.

**Recommendation:** start with Option A. It's the direct fix for the reproduced failure, it's a
smaller change, and it avoids relitigating the cache requirement. Option B is worth keeping on
the table if Option A's `O(matching log size)`-per-tick cost turns out to still be too high in
practice (e.g. if the log routinely holds tens of thousands of entries) - but that's worth
measuring after Option A ships, not assumed up front.

## 5. Pagination (max 100 items/page)

Today, `/api/requests` always returns "the newest 100 matching entries" - there's no way to see
entries 101-200. Adding real pagination means:

- A cursor or offset parameter (cursor on `timestamp` is a natural fit, since entries are
  already timestamp-ordered and unique-enough for this purpose - two entries would need the
  same millisecond timestamp to collide, which needs a documented tie-break, e.g. also cap via
  a stable id if MockServer provides one, or accept last-write-wins ordering for same-millisecond
  entries as a known limitation).
- Page size capped at 100 per the ask - should this be fixed at 100 or configurable up to a max
  of 100? (Open question for the proposal.)
- Applies on top of the existing path filter and mocked/forwarded filter, same as today.
- Needs UI: some form of "next page" / "load older" control on the Recent Requests page (a
  "load more" button appended to the table is probably the simplest fit for this page's
  existing style, rather than numbered pages, since the developer is browsing a time-ordered
  log, not a static list - but that's a UX call for the proposal, not settled here).
- Bounded by MockServer's own ring buffer: pagination can only ever page back as far as
  MockServer has retained (see Section 3) - the last page will simply run out, and the UI needs
  to say so rather than implying more history exists.

## 6. Search by time/date

Since MockServer's retrieve API has no time-range filter (Section 3), this has to be a
client-visible parameter that `mock-ui` applies itself after fetching the (path/status-filtered)
matching set from MockServer, before pagination is applied. Concretely: a "from" / "to"
timestamp filter alongside the existing path and mocked/forwarded filters, applied server-side
in `mock-ui` so the response is still capped at page size.

Two things worth deciding explicitly in the proposal rather than assuming:

- **What "old" means here is bounded by MockServer's retention**, not by how long ago the
  request actually happened - if the ring buffer has evicted it, no date filter will find it.
  The page should probably say so (e.g. "showing history back to `<oldest entry's timestamp>`")
  rather than let a developer wonder why a known-old request doesn't show up.
- **Whether this reuses the live-tail's already-fetched data (Option A's shared poll buffer) or
  issues a separate one-off fetch.** A separate fetch is simpler to reason about but doesn't
  benefit from Option A's cost amortization; reusing the shared buffer is cheaper but only works
  if the requested time range still fits within what that buffer currently holds.

## 7. Non-goals (for the eventual proposal to state explicitly)

- True long-term/persistent history (surviving a MockServer restart, or querying further back
  than MockServer's own ring buffer retains) - would require introducing actual storage, which
  is a materially bigger change than what this study covers.
- Changing MockServer's own configuration (e.g. lowering `maxLogEntries`) is a possible
  complementary mitigation but doesn't fix the concurrency bug in Section 2 by itself (the
  process still hangs re-parsing whatever size log remains, just somewhat less severely), so it
  shouldn't be presented as a substitute for the fix.
- Moving off Flask's dev server (gunicorn/waitress, multiple worker processes) is a separate,
  legitimate hardening step - already called out as a known gap in `app.py`'s existing
  `if __name__ == "__main__"` comment - but it doesn't address the GIL/re-fetch problem either
  (more worker *processes* would raise the number of tabs before things fall over, but each
  process would still hang under enough concurrent tabs of its own).

## 8. Feeding this into `/opsx:propose`

Suggested shape for the proposal this study is meant to seed:

- **Capability:** modifies `mock-management-ui` (no new capability) - the Recent Requests
  page's requirements for showing history, filtering, and live-tailing all need MODIFIED
  requirements to reflect pagination and time-range filtering; a new requirement for "the page
  remains responsive under many simultaneous viewers" would give the concurrency fix a spec
  anchor to test against (today nothing in the spec says anything about concurrent viewers).
- **Design decisions the proposal needs to make explicitly** (flagged as open questions above,
  repeated here for visibility):
  1. Option A (shared poller, no persistence) vs. Option B (small bounded cache) - recommend
     starting with A (Section 4).
  2. Cursor shape for pagination - timestamp-based, with a documented tie-break.
  3. Page size: fixed at 100, or configurable up to 100.
  4. Pagination UX: "load more" vs. numbered pages vs. something else.
  5. How the date-range filter and the live tail interact (Section 6).
  6. Whether/how the "no independent cache" requirement's scope gets clarified for read-only
     history (Section 4) - this one especially should be resolved with the user before or
     during spec-writing, not assumed by whoever writes the proposal.

## Sources

- [MockServer configuration properties](https://www.mock-server.com/mock_server/configuration_properties.html) - `maxLogEntries` default and ring-buffer eviction behavior.
- [mock-server/mockserver-client-node data retrieval reference (DeepWiki)](https://deepwiki.com/mock-server/mockserver-client-node/2.5-data-retrieval) - confirms `/mockserver/retrieve`'s only filter is a request matcher; no pagination/time-range parameters documented.
- Empirical reproduction in this session: MockServer + `mock-ui` run locally in Docker, seeded with 20,000 requests via `scripts/load-test-recent-requests.sh`'s approach, then stressed with 30 concurrent SSE connections against `/mock-ui/api/requests/stream`.
