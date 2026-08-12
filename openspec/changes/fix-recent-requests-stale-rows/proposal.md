## Why

The Recent Requests live tail's reconnect and heartbeat hardening (`add-live-tail-diagnostics`,
archived 2026-08-11) fixed the browser<->mock-ui *transport* - a dropped connection now recovers
automatically and visibly. But `docs/studies/2026-08-11-aws-eks-safety-and-mockserver-restart-staleness.md`
and live testing on this branch confirmed a separate, still-open gap in *data continuity*:
rows already rendered on the Recent Requests page are never cleared or resynced after a
restart, in two distinct ways. First, when mock-ui itself restarts and the live tail genuinely
reconnects, the reconnect path only resumes tailing new entries - it never re-fetches history,
so pre-restart rows sit there indefinitely even though the connection is healthy again. Second,
when only MockServer restarts, mock-ui's own connection to the browser never breaks at all, so
the reconnect logic never engages and the connection-status indicator stays "Live" while the
underlying history was silently wiped. Either way, a developer watching the page has no way to
tell that what they're looking at is stale.

## What Changes

- On every successful live-tail *reconnect* (not the very first connect, which already loads
  history separately), the client re-fetches and replaces the Recent Requests table instead of
  only resuming the tail - closing the mock-ui-restart-while-tab-open gap.
- The shared history poller detects when MockServer's request/response log has been reset
  (the previously-newest entry is no longer present, since the log is normally append-only from
  the newest end and only evicts from the oldest end) and pushes an explicit signal down every
  open live-tail connection so open tabs resync within about a second - closing the
  MockServer-only-restart gap, where the connection to mock-ui never drops at all.
- A brief, visible notice appears when a resync happens because of a detected reset, so a
  developer isn't left wondering why rows just changed out from under them.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mock-management-ui`: the "Web UI automatically reconnects a lost live tail connection"
  requirement gains a resync-on-reconnect behavior; a new requirement is added covering
  detection and client-side resync of a MockServer-side history reset that doesn't involve a
  connection drop.

## Impact

- `mock-ui/app.py`: the shared history poller (`_poll_history_once`) gains reset detection;
  `event_stream` gains a distinct SSE event (not the existing heartbeat comment, not a regular
  `data:` entry message) to signal a detected reset to every open connection.
- `mock-ui/static/app.js`: `connectRequestsStream`/`scheduleRequestsReconnect` distinguish a
  reconnect from the initial connect and re-run `loadRequestHistory()` on reconnect; a new
  listener for the reset event triggers the same resync and a transient notice.
- `mock-ui/static/index.html` / `style.css`: the transient resync notice element and its
  styling.
- `mock-ui/test_app.py`: coverage for reset detection in the poller and the new SSE event.
- No change to the connection-status indicator, heartbeat interval, or reconnect backoff
  schedule shipped in `add-live-tail-diagnostics` - this change only affects what happens to the
  already-rendered table once a connection is healthy (whether newly reconnected or never
  dropped).
