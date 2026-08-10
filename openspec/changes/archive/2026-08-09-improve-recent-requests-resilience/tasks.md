## 1. Backend: shared poller (the concurrency fix)

- [x] 1.1 Add a single background poller (started once at app startup, not per-connection) that fetches `/mockserver/retrieve?type=REQUEST_RESPONSES` on the existing 1-second cadence and holds the parsed result in an in-memory structure shared by all requests
- [x] 1.2 Rework `stream_requests()`'s `event_stream()` generator to read from the shared poller's latest snapshot instead of calling `_fetch_request_history()` itself every tick, computing each connection's own new-entries-since-`last_timestamp` diff and applying that connection's own active filters (path, mocked/forwarded, time range) against the shared snapshot
- [x] 1.3 Ensure `/mock-ui/api/requests` (the non-streaming history endpoint) also reads from the shared snapshot rather than issuing its own independent MockServer fetch, so a page load doesn't add a second concurrent fetch on top of the poller's
- [x] 1.4 Handle the shared poller's fetch failing or MockServer being unreachable without crashing the poller loop or silently freezing all connected clients' data

## 2. Backend: pagination

- [x] 2.1 Add a cursor parameter (oldest currently-shown `timestamp`) to `/mock-ui/api/requests`, returning up to 100 entries strictly older than the cursor, matching active filters
- [x] 2.2 Apply a documented, stable tie-break for entries sharing the same millisecond timestamp so pagination doesn't skip or repeat entries at a page boundary
- [x] 2.3 Signal "no older entries available" distinctly from "filters matched nothing on this page" in the API response, so the frontend can show the right message

## 3. Backend: time-range filter

- [x] 3.1 Accept `from`/`to` query parameters on `/mock-ui/api/requests` and `/mock-ui/api/requests/stream`, applied in `mock-ui` against the shared poller's snapshot (or the matcher-filtered fetch), alongside the existing path and mocked/forwarded filters
- [x] 3.2 When a requested `from` predates the oldest entry MockServer currently retains, indicate that in the response rather than silently returning a partial range with no explanation
- [x] 3.3 Confirm the SSE stream ignores `from`/`to` for newly arriving entries (per design.md) while still respecting `path` and `mocked`

## 4. Frontend: pagination and time-range UI

- [x] 4.1 Add a "Load more" control at the bottom of the Recent Requests table that requests the next page using the oldest currently-shown entry's timestamp as the cursor
- [x] 4.2 Show a distinct "no older requests available" state when the API signals the oldest retained entry has been reached, replacing the "Load more" control
- [x] 4.3 Add "from"/"to" time-range inputs alongside the existing path and mocked/forwarded filter controls, wired into both history loading and pagination requests
- [x] 4.4 Show messaging when the requested time range predates what MockServer currently retains (per backend signal in 3.2)

## 5. Verification

- [x] 5.1 Reproduce the original failure scenario (a large logged volume, ~30 concurrent SSE connections) and confirm the page and other endpoints (e.g. `/mock-ui/healthz`) remain responsive
- [x] 5.2 Confirm live-tail delivery latency to existing viewers does not measurably degrade as additional viewers open the page
- [x] 5.3 Confirm "Load more" pages through history correctly under each active filter combination (path, mocked/forwarded, time range, and combinations)
- [x] 5.4 Confirm reaching the oldest retained entry is communicated rather than silently offering another ineffective "Load more"
- [x] 5.5 Confirm the live tail keeps delivering new entries when a "to" time in the past is set, per the scenario in the spec delta
