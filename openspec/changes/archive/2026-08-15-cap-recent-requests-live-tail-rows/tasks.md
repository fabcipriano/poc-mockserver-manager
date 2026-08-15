## 1. Live-tail row cap

- [x] 1.1 Add a `LIVE_TAIL_MAX_ROWS` constant to `mock-ui/static/app.js`, alongside the page's other Recent Requests constants (e.g. near `REQUESTS_RECONNECT_BASE_DELAY_MS`), set to 500.
- [x] 1.2 In `prependRequestRow()`, after inserting the new summary/detail pair, evict pairs from the end of `requestsBody` (`requestsBody.lastElementChild`, removed twice per pair) until `requestsBody.children.length` is back at or below `LIVE_TAIL_MAX_ROWS * 2`.
- [x] 1.3 Confirm `appendRequestRow()` (used by `loadRequestHistory()` and `loadMoreRequests()`) is left untouched, so pagination's own loads are never truncated by the cap.

## 2. Verification

- [x] 2.1 Manually verify: open Recent Requests, drive sustained traffic past `LIVE_TAIL_MAX_ROWS` requests (e.g. via `scripts/load-test-recent-requests.sh` or repeated calls against a mocked route), and confirm the visible row count plateaus at 500 instead of growing further, with the browser tab staying responsive. (Confirmed by user.)
- [x] 2.2 Manually verify: expand a detail row, let enough live-tail traffic arrive to evict it, and confirm it disappears cleanly with no leftover/orphaned detail row. (Confirmed by user.)
- [x] 2.3 Manually verify: pause the tail, let more than `LIVE_TAIL_MAX_ROWS` requests arrive, resume, and confirm the list settles at exactly `LIVE_TAIL_MAX_ROWS` rows showing the most recent ones. (Confirmed by user.)
- [x] 2.4 Manually verify: with the list at the row cap, click "load more" and confirm the full requested page of older rows is added (temporarily exceeding the cap), then confirm the cap resumes evicting on the next live-tail arrival. (Confirmed by user.)
- [x] 2.5 Run `mock-ui`'s existing test suite (`mock-ui/test_app.py`) to confirm no backend regressions, since this change is frontend-only. (42 passed, 0 failed - `python3 -m pytest mock-ui/test_app.py -q`)

## 3. Housekeeping

- [x] 3.1 Run `openspec validate cap-recent-requests-live-tail-rows --strict` and fix any reported issues. (Valid, no issues.)
