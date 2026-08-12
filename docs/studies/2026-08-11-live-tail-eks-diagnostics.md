# Note: diagnosing a dropped Recent Requests live tail on AWS EKS

**Status:** Reference checklist, written alongside the `add-live-tail-diagnostics` change.
**Trigger:** The Recent Requests live tail stopped delivering new entries in an AWS EKS
deployment with no way to tell why - `mock-ui` emitted no logs at all, and the browser only
ever showed a static "Lost connection" message with no automatic recovery. This change added
server-side logging, a client-side reconnect loop with a visible connection-status indicator,
and a periodic SSE heartbeat; this note is the checklist for using them.

## Why this didn't show up locally

The local emulated environment (`poc-environment`, `k8s/base/ingress.yaml`) fronts everything
with an `ingress-nginx` Ingress as a stand-in for the real ALB. A real AWS EKS deployment
typically fronts `mock-ui` with the AWS Load Balancer Controller's ALB Ingress instead, which
has different defaults - most notably an **idle connection timeout** (defaults to 60 seconds)
that the local nginx stand-in either doesn't apply the same way or isn't configured with. The
Recent Requests live tail (`/mock-ui/api/requests/stream`, an SSE connection) previously only
sent a byte to the client when a new request actually arrived - during any quiet period longer
than the proxy's idle timeout, the connection could be silently closed without the client
finding out until (if ever) the next real entry tried to send.

## What to check, in order, when the live tail shows Reconnecting or Disconnected

1. **`mock-ui`'s server logs.** As of this change, every SSE client connect/disconnect and
   every attempt by the shared history poller to reach MockServer is logged (`kubectl logs
   deploy/mock-ui`, or set `LOG_LEVEL=DEBUG` on the deployment for more detail without a code
   change). A steady stream of `history poll succeeded` entries with no matching `SSE client
   disconnected` entries around the time the developer noticed the problem means MockServer
   itself is fine and the drop happened between the browser and `mock-ui` - go to step 2.
   Frequent `history poll failed` entries instead point at `mock-ui` not being able to reach
   MockServer (wrong `MOCKSERVER_URL`, MockServer pod down, NetworkPolicy blocking the
   connection) rather than a live-tail-specific problem.
2. **The browser console**, on the affected developer's machine. As of this change, the
   client logs every `EventSource` open/error and every scheduled reconnect attempt with its
   delay. A tight repeating cycle of connection errors indicates the connection keeps being
   cut shortly after opening - consistent with an idle timeout shorter than the 15-second
   heartbeat interval (`HEARTBEAT_INTERVAL_SECONDS` in `mock-ui/app.py`), or some other proxy
   between the browser and the ALB/`mock-ui` actively terminating the connection.
3. **The ALB's idle timeout setting**, if step 2 suggests connections are being cut on a
   regular cadence. Check the target group / load balancer attributes (via the AWS console,
   `aws elbv2 describe-load-balancer-attributes`, or the `alb.ingress.kubernetes.io/*`
   annotations on the Ingress if the AWS Load Balancer Controller manages it) for
   `idle_timeout.timeout_seconds`. If it's shorter than 15s, either raise it or lower
   `HEARTBEAT_INTERVAL_SECONDS` to comfortably undercut it.
4. **Pod restarts.** `kubectl get pods -n <namespace> -w` / `kubectl describe pod
   <mock-ui-pod>` around the time of the drop. A restart (OOM, node drain, rollout) closes
   every open SSE connection on that pod at once; the client-side reconnect loop added by this
   change should recover automatically once the new pod is Ready, without a manual page
   reload - if it doesn't, that's a bug in the reconnect logic itself, not the underlying
   infrastructure.
5. **Buffering proxies.** Anything else sitting between the ALB and `mock-ui` that buffers
   response bodies (rather than streaming them) can hold heartbeats and real entries alike
   without forwarding them promptly, which looks like a stalled tail even though `mock-ui`
   itself is sending data. `stream_requests` already sets `X-Accel-Buffering: no` for
   nginx-family proxies; an unfamiliar proxy in the path may need an equivalent setting.

## What "Disconnected" does and doesn't mean

The connection-status indicator shows Disconnected after 5 consecutive failed reconnect
attempts, but the page keeps retrying with capped exponential backoff in the background - it
never gives up on its own. Disconnected is a signal to go investigate (starting with step 1
above), not something that requires the developer to manually intervene for the tail to
eventually recover if the underlying cause clears up by itself (e.g. a pod finishing its
restart).
