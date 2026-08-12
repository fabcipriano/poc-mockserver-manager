## Context

`mock-ui/app.py` is a single-file Flask app with no logging configured anywhere today. A background thread (`_history_poller_loop`) polls MockServer's full request log on a 1-second cadence (`REQUEST_STREAM_POLL_SECONDS`) into a shared in-memory snapshot (`_history_snapshot`); `/mock-ui/api/requests/stream` is a per-connection generator that diffs against that snapshot every tick and yields an SSE `data:` line only when new entries exist - see proposal.md for why. `mock-ui/static/app.js`'s `openRequestsStream()` opens a plain `EventSource` and its `onerror` handler only shows a static banner; it never closes or reopens the connection, so if the browser's built-in (fixed ~3s, unconfigurable) auto-retry succeeds the banner never clears, and if the browser gives up there is no recovery at all. There is no JS test harness in this repo (only `mock-ui/test_app.py`, Python `unittest` against the Flask app); manual verification via the `run` skill is how JS behavior gets checked today.

## Goals / Non-Goals

**Goals:**
- Make the live tail's failure modes (poller can't reach MockServer, SSE connection dropped by an intermediate proxy, client-side error) each individually visible in server logs and browser console.
- Keep the live tail connection alive across quiet periods so it isn't mistaken for - or actually killed by - an idle-connection timeout in front of it (relevant on EKS, where a real AWS ALB or another ingress proxy sits in front of mock-ui instead of the local nginx stand-in).
- Recover from a dropped connection automatically and visibly, without a manual page reload.

**Non-Goals:**
- Shipping logs off-cluster (to CloudWatch, ELK, etc.) - this change emits to stdout/console only; forwarding is an existing platform concern (e.g. Fluent Bit sidecar/daemonset on EKS), not something mock-ui configures.
- Diagnosing or fixing any specific EKS networking issue (ALB idle timeout value, NetworkPolicy rules, node placement) - this change makes such issues *diagnosable and more resilient to*, not eliminated.
- Multi-replica coordination for the history poller - `mock-ui` still runs as a single replica (see `k8s/overlays/with-mockserver/mock-ui-deployment.yaml`); that's unchanged by this proposal.

## Decisions

**Server logging: stdlib `logging`, plain text, stdout, level via env var.** Use Python's `logging` module (`logging.getLogger("mock-ui")`) rather than a structured/JSON logging library - this is a single small Flask file with no existing logging dependency, and EKS container logs are typically scraped as text lines regardless. Configure via `logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))` writing to stdout, so log verbosity can be raised (e.g. to `DEBUG`) in the EKS deployment by setting an env var, without a code change or rebuild. Log the poller's per-attempt outcome (success + latency, or failure + exception) and each SSE connection's open/close, including the applied `path`/`mocked` filters, at INFO; keep per-tick "no new entries" ticks out of the log entirely (they're expected and constant) to avoid drowning the useful signal at 1-second cadence.

**Heartbeat: SSE comment lines on a separate interval from the poll cadence.** SSE comment lines (`: ping\n\n`, per the SSE spec, lines starting with `:` are ignored by `EventSource.onmessage`) sent periodically keep bytes flowing on an otherwise-idle connection without the client mistaking a heartbeat for a real entry. Reuse the existing 1-second generator loop rather than a second timer/thread: track elapsed time since the last byte was sent on that connection, and emit a heartbeat comment once a `HEARTBEAT_INTERVAL_SECONDS` (default 15s - comfortably under typical proxy/ALB idle timeouts, which commonly default around 60s) threshold is crossed with no real entries sent. This avoids a second concurrent timer per connection.

**Reconnection: client takes explicit control instead of relying on native `EventSource` auto-retry.** The `EventSource` spec already auto-reconnects on `error` with a fixed ~3s delay, but that retry is invisible (no event fires to hook into for logging or UI state) and not backed off, so a persistent problem produces a silent tight retry loop with no server-side signal of how bad it is. Instead, `onerror` explicitly closes the `EventSource`, logs the failure to the console, and schedules the next connection attempt itself with capped exponential backoff (starting at 1s, doubling, capped at 30s), resetting the delay back to 1s on a successful reconnect. This makes every attempt observable and keeps retry pressure on MockServer/the proxy bounded.

**Connection-status indicator: three states driven by the same reconnect loop, not a fourth network check.** Live = `EventSource` open and has received at least one heartbeat or entry since connecting; Reconnecting = a reconnect attempt is scheduled or in flight; Disconnected = shown once consecutive failed attempts exceed a small threshold (5), while reconnection attempts continue silently in the background rather than stopping - since the underlying cause (proxy hiccup, pod restart) may resolve on its own, the UI should keep trying rather than requiring the developer to notice and reload.

## Risks / Trade-offs

[Heartbeat interval too long for some proxy's shorter idle timeout] → Default of 15s is conservative against common 60s-class defaults; the interval is a single named constant, easy to lower further if a specific environment needs it.

[More frequent small writes on the SSE connection increase log/network chatter] → Heartbeats are single-line SSE comments (a few bytes), and only sent when nothing else was already sent in the interval, so the added chatter is bounded and only appears when it's otherwise needed to keep the connection alive.

[Client-side reconnect loop retries forever, masking a truly dead MockServer/proxy] → The visible Disconnected state after repeated failures, plus the corresponding server-side poller failure logs (from the existing shared poller, unaffected by any one client's reconnect loop), together give a developer the same signal a hard failure would; capping backoff at 30s keeps retry cost low enough that "retry forever" is an acceptable default for this POC.

[No JS test harness exists to assert the reconnect/backoff/indicator logic automatically] → Cover this in the manual verification tasks (using the `run` skill against the emulated k8s environment) rather than adding a JS test framework, which is out of scope for this change; server-side logging and heartbeat behavior are covered by `test_app.py`.

## Migration Plan

No data migration. Rollout is a normal image rebuild/redeploy of `mock-ui`; the new `LOG_LEVEL` env var defaults to `INFO` if unset, so existing manifests keep working without modification (setting it explicitly in the EKS overlay is a follow-up operational step, not required by this change). Rollback is redeploying the previous image; no schema or state is introduced.
