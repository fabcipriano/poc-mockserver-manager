## Why

The Recent Requests page's live tail has, in at least one AWS EKS deployment, silently stopped delivering new entries with no way to tell why: the mock-ui server emits no logs at all today (no logging is configured anywhere in `mock-ui/app.py`), and the browser side only ever shows a static "Lost connection" message with no detail and no automatic recovery. EKS introduces failure modes the local POC environment doesn't exercise - a real AWS ALB (idle connection timeouts, target deregistration on rollout) instead of the local nginx stand-in, pod restarts, and node-level network policies - any of which can drop the SSE stream. Without logs on either side, diagnosing which of these actually happened requires guesswork or reproducing the problem live in the cluster.

## What Changes

- Add structured server-side logging (Python `logging` module) around the shared history poller's MockServer polls (success, failure, latency) and around each SSE stream connection's lifecycle (open, client disconnect, filters applied).
- Add client-side console logging around the `EventSource` lifecycle (open, error, close, reconnect attempt) on the Recent Requests page, including enough detail (readyState, timestamp) to distinguish a clean navigation-away close from an unexpected drop.
- Add a server-sent heartbeat comment on the `/mock-ui/api/requests/stream` SSE endpoint, emitted on a fixed interval regardless of new entries, so the connection is never idle long enough to hit a proxy's idle-connection timeout (a likely cause of the EKS symptom, since the current stream only sends bytes when a new request arrives).
- Replace the current single static "Lost connection" banner with automatic client-side reconnection using capped exponential backoff, and a small always-visible connection-status indicator on the Recent Requests page (Live / Reconnecting / Disconnected) so a developer can tell the tail is degraded at a glance instead of only after reading a banner.
- Document, in the Help page and/or a study doc, the known EKS-specific causes this change defends against (ALB idle timeout, pod restart, buffering proxies) so a developer investigating a future occurrence has a starting checklist.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mock-management-ui`: the "Web UI shows recent requests received by MockServer" and "Web UI live-tails new requests in real time" requirements gain observability (logging) and resilience (heartbeat, reconnection, visible connection status) behavior for the live tail.

## Impact

- `mock-ui/app.py`: add logging configuration, log statements in `_poll_history_once`, `_history_poller_loop`, and `stream_requests`/`event_stream`; add a periodic heartbeat comment to the SSE generator.
- `mock-ui/static/app.js`: add console logging around `openRequestsStream`/`EventSource` events; replace the current one-shot error banner with a reconnect-with-backoff loop and a connection-status indicator.
- `mock-ui/static/index.html` / `style.css`: add the connection-status indicator element and its styling.
- `mock-ui/test_app.py`: extend or add tests for the heartbeat behavior and any new logging hooks that are practical to assert on.
- No change to the MockServer integration or the emulated k8s topology (`poc-environment`) - this addresses observability and resilience of the existing live tail, not the network path itself.
