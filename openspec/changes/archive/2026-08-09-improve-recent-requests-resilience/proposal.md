## Why

`scripts/load-test-recent-requests.sh` (20,000 requests) exposed that the Recent Requests page
fails under real-world load: with 20,000 requests logged in MockServer and just 30 concurrent
browser tabs open, the `mock-ui` process fully hangs - memory grows ~5x in 15 seconds, CPU pegs
at 100%+, and even the trivial `/mock-ui/healthz` endpoint times out. See
`docs/studies/2026-08-09-recent-requests-resilience.md` for the full reproduction and root
cause analysis. The root cause: the live tail's polling loop re-fetches and re-parses
MockServer's entire matching request log every second, per open tab - cost that scales with
`open tabs × total log size`, unbounded in both dimensions. This needs fixing regardless of any
other feature work, and while fixing it, the page should also gain real pagination and
time-range search so a developer can browse history beyond "the most recent 100 entries"
without reintroducing the same unbounded-fetch problem.

## What Changes

- **Concurrency fix**: replace the current "every SSE connection independently polls MockServer
  every second" model with a single shared background poller (one poll per tick, regardless of
  how many tabs are open) that fans new entries out to all connected clients from an in-memory
  buffer that is continuously rebuilt and never persisted between ticks. This turns the page's
  cost from `O(open tabs × total log size)` per second into `O(total log size)` per tick,
  independent of tab count.
- Recent Requests history gains **pagination**: a "Load more" control appends the next page
  (fixed at 100 entries) to the bottom of the table, using a timestamp-based cursor. Pagination
  is bounded by MockServer's own log retention (a ring buffer, oldest entries evicted first) -
  the page communicates when it has reached the oldest entry MockServer still has, rather than
  implying more history exists.
- Recent Requests gains a **time/date-range filter** ("from" / "to"), applied alongside the
  existing path and mocked/forwarded filters, computed server-side in `mock-ui` (MockServer's
  own retrieve API has no time-range parameter, so this can't be pushed down to MockServer).
- **New requirement**: the Recent Requests page SHALL remain responsive with multiple
  simultaneous viewers - gives the concurrency fix a spec anchor to test against, since nothing
  today constrains behavior under concurrent viewers.
- Not a **BREAKING** change to any existing behavior - the existing path filter, mocked/forwarded
  filter, live tail, pause/resume, and detail view all keep working as specified; this only adds
  pagination, time-range filtering, and the concurrency fix underneath them.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mock-management-ui`: the Recent Requests page's requirements for showing history, filtering,
  and live-tailing are extended to cover pagination and time-range filtering, and a new
  requirement is added for remaining responsive under multiple simultaneous viewers.

## Impact

- `mock-ui/app.py`: introduces a shared background poller replacing the current per-connection
  polling loop in `stream_requests()`; `_fetch_request_history()` gains pagination (cursor/limit)
  and time-range parameters; `/mock-ui/api/requests` and `/mock-ui/api/requests/stream` both gain
  new query parameters (`before`/cursor, `from`/`to`).
- `mock-ui/static/app.js`, `index.html`, `style.css`: a "Load more" control and a from/to
  date-range filter on the Recent Requests page, plus messaging for "reached the oldest
  retained entry."
- No new external dependencies. No change to MockServer itself or its configuration.
- Depends on no other in-flight change (both prior Recent Requests changes -
  `add-recent-requests-detail` and `add-recent-requests-mocked-filter` - are already archived).
