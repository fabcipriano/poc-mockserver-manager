## 1. Server-side reset detection

- [x] 1.1 Add a `_history_reset_generation` counter alongside `_history_snapshot` in `mock-ui/app.py`, protected by the same lock
- [x] 1.2 In `_poll_history_once`, detect a reset: previous snapshot non-empty and new snapshot empty, OR new snapshot non-empty but the previous newest entry's timestamp is no longer present anywhere in it; increment the generation counter when detected
- [x] 1.3 Log a reset detection at INFO/WARNING (reusing the existing logger) so it shows up alongside the poll success/failure logging from `add-live-tail-diagnostics`

## 2. Server-side signal delivery

- [x] 2.1 In `event_stream`, initialize each connection's `last_seen_generation` to the current generation at connect time
- [x] 2.2 On each loop tick, compare the shared generation to the connection's last-seen value; if advanced, yield `event: history-reset\ndata: {}\n\n` and update the connection's last-seen value
- [x] 2.3 Confirm the heartbeat and the reset event don't interfere - a tick that sends a reset event should not also send a heartbeat comment in the same tick unless needed

## 3. Client-side resync on reconnect

- [x] 3.1 Add a `resyncRequestsHistory(reasonText)` helper in `mock-ui/static/app.js` that calls `loadRequestHistory()` and shows a transient notice with the given reason
- [x] 3.2 Give `connectRequestsStream` a parameter distinguishing a reconnect from the initial connect; on a reconnect's `onopen`, call `resyncRequestsHistory` with a reconnect-specific reason
- [x] 3.3 Confirm the very first connect (via `openRequestsStream`/`syncRequestsPageStream`) does not also trigger `resyncRequestsHistory` (avoiding a redundant double fetch on initial page load)

## 4. Client-side resync on detected reset

- [x] 4.1 Add a `history-reset` listener via `requestsEventSource.addEventListener` in `connectRequestsStream`, calling `resyncRequestsHistory` with a reset-specific reason
- [x] 4.2 Add the transient notice element to `mock-ui/static/index.html` and style it in `mock-ui/static/style.css`, reusing the existing transient-note visual pattern (e.g. `#requests-range-truncated`)
- [x] 4.3 Auto-hide the notice a few seconds after it's shown

## 5. Tests

- [x] 5.1 Add `mock-ui/test_app.py` coverage for reset detection: previous non-empty snapshot followed by an empty poll increments the generation counter
- [x] 5.2 Add `mock-ui/test_app.py` coverage for reset detection: previous snapshot's newest entry absent from a new non-empty snapshot increments the generation counter
- [x] 5.3 Add `mock-ui/test_app.py` coverage confirming a poll with no reset (new snapshot is a superset ending in the same or a later entry) does not increment the generation counter
- [x] 5.4 Add `mock-ui/test_app.py` coverage that an SSE connection receives the `history-reset` event after a reset is detected

## 6. Poller thread resilience (found during manual verification)

- [x] 6.1 Broaden `_mockserver_put`'s except clause from `urllib.error.URLError` to `OSError` so a mid-request connection reset (e.g. MockServer restarting while a poll is in flight) is handled like any other unreachable-MockServer case instead of propagating uncaught
- [x] 6.2 Wrap `_history_poller_loop`'s call to `_poll_history_once()` in a catch-all `except Exception`, logged via `logger.exception`, so no exception can permanently kill the background poller thread
- [x] 6.3 Add `mock-ui/test_app.py` coverage that a `ConnectionResetError` (or other non-`URLError` `OSError`) from `_mockserver_put` is raised as `MockServerError`, not propagated raw
- [x] 6.4 Add `mock-ui/test_app.py` coverage that `_history_poller_loop` continues (calls `_poll_history_once` again) after a tick raises an unexpected exception

## 7. Manual verification

- [x] 7.1 Using the `run` skill, bring up the emulated environment, open Recent Requests, restart the `mockserver` pod only (leave `mock-ui` running), and confirm the page resyncs (with the transient notice) even though the connection-status indicator never leaves Live
- [x] 7.2 Restart the `mock-ui` pod while Recent Requests is open and confirm that once the live tail reconnects, the table resyncs (with the transient notice) rather than only resuming the tail on top of stale rows
- [x] 7.3 Confirm a normal reconnect/resync cycle does not duplicate or drop rows for requests made shortly before and after the restart
