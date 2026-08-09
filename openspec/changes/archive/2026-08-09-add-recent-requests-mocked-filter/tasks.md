## 1. Backend: classify each request as mocked or forwarded

- [x] 1.1 Add a small helper in `mock-ui/app.py` (e.g. `_is_forwarded_response(http_response)`) that returns `True` when the observed `httpResponse` has a `reasonPhrase` or an `x-mockserver-response-time-ms` header, per the heuristic in design.md
- [x] 1.2 Extend `_fetch_request_history` to include a `mocked` boolean (or equivalent) per entry, derived from that helper
- [x] 1.3 Confirm `/mock-ui/api/requests` and `/mock-ui/api/requests/stream` both carry the new field with no other endpoint changes needed
- [x] 1.4 Add an automated test exercising the helper against fixture response shapes for both a canned mock response and a forwarded response (see design.md's noted risk of no existing coverage)

## 2. Backend: support filtering by mocked/forwarded status

- [x] 2.1 Accept a status filter parameter (e.g. `mocked=true|false`) on `/mock-ui/api/requests` and `/mock-ui/api/requests/stream`, alongside the existing `path` filter
- [x] 2.2 Apply the status filter in `_fetch_request_history` (or immediately after) so both endpoints return only matching entries, combined with the existing path filter (AND semantics)

## 3. Frontend: show and filter by mocked/forwarded status

- [x] 3.1 Render a mocked/forwarded indicator (e.g. a badge) on each Recent Requests row, using the new field
- [x] 3.2 Add a status filter control (mocked / forwarded / both) alongside the existing path filter input
- [x] 3.3 Wire the status filter into the request URL used by both history loading and the live tail's `EventSource` connection, mirroring how the existing path filter is wired
- [x] 3.4 Ensure changing the status filter re-scopes the live tail the same way changing the path filter already does (reload history, reopen the stream)

## 4. Verification

- [x] 4.1 Confirm a request answered by a developer-created mock is labeled mocked, and a request forwarded to the Gateway/backend is labeled forwarded, against real traffic
- [x] 4.2 Confirm the mocked-only and forwarded-only filters each hide the other kind of request, for both history and newly arriving live-tailed requests
- [x] 4.3 Confirm the status filter and the path filter combine correctly (both must match)
- [x] 4.4 Check the browser console for errors while exercising the new filter and live tail together
