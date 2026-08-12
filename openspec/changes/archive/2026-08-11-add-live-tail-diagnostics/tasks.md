## 1. Server-side logging

- [x] 1.1 Configure `logging` in `mock-ui/app.py` (module logger, stdout, level from `LOG_LEVEL` env var, default `INFO`)
- [x] 1.2 Log each history poller attempt in `_poll_history_once`: success with latency and entry count at INFO, failure with the exception at WARNING (still falling back to the stale snapshot as today)
- [x] 1.3 Log each SSE client connect/disconnect in `stream_requests`/`event_stream`, including the applied `path`/`mocked` filters, at INFO
- [x] 1.4 Confirm per-tick "no new entries" checks stay unlogged so log volume doesn't scale with the 1-second poll/tail cadence

## 2. Live-tail heartbeat

- [x] 2.1 Add a `HEARTBEAT_INTERVAL_SECONDS` constant (default 15) near `REQUEST_STREAM_POLL_SECONDS`
- [x] 2.2 In `event_stream`, track elapsed time since the last byte sent on the connection and yield an SSE comment line (e.g. `: ping\n\n`) once the heartbeat interval elapses with no real entry sent
- [x] 2.3 Verify a real entry sent to the client resets the heartbeat timer (no redundant heartbeat immediately after)

## 3. Client-side reconnect and status indicator

- [x] 3.1 Add a connection-status indicator element to the Recent Requests page (`mock-ui/static/index.html`) and its styling (`mock-ui/static/style.css`) with Live/Reconnecting/Disconnected states
- [x] 3.2 In `mock-ui/static/app.js`, log `EventSource` open/error/close events to the console with enough detail to distinguish a clean close (navigating away) from an unexpected drop
- [x] 3.3 Replace the current static "Lost connection" banner: on `onerror`, explicitly close the `EventSource`, update the indicator to Reconnecting, and schedule a reconnect attempt
- [x] 3.4 Implement capped exponential backoff for reconnect attempts (start 1s, double, cap 30s), resetting to 1s on a successful reconnect
- [x] 3.5 Update the indicator to Disconnected after 5 consecutive failed reconnect attempts, while continuing to retry in the background; update it back to Live once a reconnect succeeds and the first heartbeat or entry is received

## 4. Tests

- [x] 4.1 Add/extend `mock-ui/test_app.py` coverage for the heartbeat comment appearing on an idle stream after the configured interval
- [x] 4.2 Add/extend `mock-ui/test_app.py` coverage asserting log records are emitted for a successful poll and for a poll failure (e.g. via `assertLogs`)

## 5. Documentation

- [x] 5.1 Update the Help page's MockServer Dashboard/Recent Requests explanation (or add a short note) covering what the connection-status indicator means and what to check (server logs, then MockServer Dashboard) if the live tail shows Disconnected
- [x] 5.2 Add a short study or note documenting the known EKS-specific causes this change defends against (ALB idle timeout, pod restart, buffering proxies) as a starting checklist for a future occurrence

## 6. Manual verification

- [x] 6.1 Using the `run` skill, bring up the emulated environment and confirm server logs show poller success entries and SSE connect/disconnect entries
- [x] 6.2 Manually simulate a dropped connection (e.g. restart the `mock-ui` pod while the Recent Requests page is open) and confirm the indicator moves Live -> Reconnecting -> Live and the live tail resumes without a manual reload
- [x] 6.3 Confirm the connection stays Live (no false Reconnecting/Disconnected flicker) through a quiet period longer than the heartbeat interval with no new requests
