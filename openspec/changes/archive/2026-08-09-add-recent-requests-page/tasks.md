## 1. Backend: request history and live stream

- [x] 1.1 In `mock-ui/app.py`, add a helper that turns a plain-text path filter into a MockServer path matcher by escaping it and wrapping it as `.*<escaped>.*` (returning no filter/`None` when the input is empty), per design.md's verified substring-search behavior
- [x] 1.2 Add a helper that calls `PUT /mockserver/retrieve?type=REQUEST_RESPONSES` (optionally with the path matcher from 1.1) and maps each entry to a friendly shape: `{timestamp, method, path, statusCode}`
- [x] 1.3 Add `GET /mock-ui/api/requests?path=<optional>`: returns the most recent 100 matching entries (per design.md Decision 4), newest first
- [x] 1.4 Add `GET /mock-ui/api/requests/stream?path=<optional>`: a `text/event-stream` SSE endpoint that polls the helper from 1.2 roughly every second, tracks the timestamp of the last entry already sent, and yields only newer entries as SSE `data:` events (JSON per entry)

## 2. Frontend: page structure

- [x] 2.1 In `mock-ui/static/index.html`, add "Recent Requests" as a fourth sidebar nav item (between List Mocks and Help) and a new `#page-requests` section containing: a path filter input, a Pause/Resume button, and a list/table area for entries (timestamp, method, path, status code)
- [x] 2.2 In `mock-ui/static/app.js`, add `"requests"` to `VALID_PAGES` so the existing hash-routing (`showPage`, active-nav-highlight) picks it up with no other routing changes needed

## 3. Frontend: history load, live tail, filter, pause/resume

- [x] 3.1 On navigating to the Recent Requests page (or on filter change), fetch `GET /mock-ui/api/requests?path=<filter>` and render the returned entries newest-first
- [x] 3.2 Open an `EventSource` against `/mock-ui/api/requests/stream?path=<filter>` when the Recent Requests page becomes active; close it when navigating away from the page
- [x] 3.3 On each SSE message, prepend the new entry to the top of the list if not paused; if paused, push it onto a client-side pending queue instead
- [x] 3.4 Wire the Pause/Resume button: Pause stops new entries from being rendered (queues them per 3.3) without closing the `EventSource`; Resume flushes the queued entries into the list and resumes live rendering
- [x] 3.5 Wire the filter input: on change (debounced), re-fetch history (3.1) and close/reopen the `EventSource` (3.2) with the new filter value, clearing the currently displayed list first

## 4. Styling

- [x] 4.1 In `mock-ui/static/style.css`, style the Recent Requests page: the filter input, the Pause/Resume button (with a visual state difference between paused/live), and the request list/table (reusing the existing table-card/table conventions from List Mocks where sensible)

## 5. Container image

- [x] 5.1 Rebuild `mock-ui`'s Docker image - no `Dockerfile`/`requirements.txt` changes expected (Flask's `Response` streaming is stdlib-adjacent, already available)

## 6. Verification

- [x] 6.1 Load the new image into the kind cluster and redeploy `mock-ui`
- [x] 6.2 Generate a few requests against different paths through the running stack; open the Recent Requests page and confirm they appear, newest first, with correct timestamp/method/path/status
- [x] 6.3 Type a path fragment into the filter; confirm only matching requests remain shown (test a fragment that appears in the middle of a path, not just a prefix, to confirm substring behavior)
- [x] 6.4 With the Recent Requests page open and a filter active, send a new request matching the filter and confirm it appears at the top without a page refresh; send one that doesn't match and confirm it does not appear
- [x] 6.5 Change the filter while the page is open; confirm both the displayed history and subsequently arriving requests reflect the new filter
- [x] 6.6 Click Pause, send a new matching request, confirm the list doesn't change; click Resume and confirm the request(s) received while paused now appear
- [x] 6.7 Navigate away from Recent Requests and back; confirm no duplicate `EventSource` connections accumulate (check via browser dev tools network panel or a request counter) and the page still works correctly
- [x] 6.8 Drive the above end-to-end through the actual browser UI with zero console/page errors, and spot-check that Create Mock / List Mocks / Help still work unmodified (regression check on the existing pages)
