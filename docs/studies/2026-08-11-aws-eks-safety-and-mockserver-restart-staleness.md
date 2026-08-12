# Study: does `mock-ui/aws_eks.yaml`'s environment work safely with the current code, and is the "stale Recent Requests after MockServer restart" problem fixed?

**Status:** Study only - no code changed, nothing implemented. Written to answer two direct
questions: (1) does the current mock-ui implementation, including the live-tail hardening just
shipped in `add-live-tail-diagnostics`, run safely against the real AWS EKS environment
described in `mock-ui/aws_eks.yaml`; and (2) is the previously-observed "Recent Requests page
isn't cleared when MockServer restarts" behavior already fixed by that change, or does it need
more work.
**Trigger:** Direct ask to analyze `mock-ui/aws_eks.yaml` against the current implementation.

## 1. What `mock-ui/aws_eks.yaml` actually is - and isn't

Its shape (`replicaCount`, `affinity`, `app.config`, `app.persistence`, `ingress`, `resources`,
`tolerations`, no `apiVersion`/`kind`) is a **Helm values file**, not a raw manifest - almost
certainly for the chart that deploys the **MockServer container itself**
(`app.config.properties` sets `mockserver.initializationJsonPath`, the pod-anti-affinity
`matchLabels` target `app: mockserver-public`, the ingress host is
`mockserver-public.flexdev.aws.clarobrasil.mobi`).

**It contains no mock-ui configuration at all** - no image, no `MOCKSERVER_URL`, no `LOG_LEVEL`,
no resource limits, no replica count, no ingress path for `/mock-ui`. Everything below about
mock-ui's own behavior in this environment is therefore inferred from the code, not confirmed
by this file - flagged explicitly wherever that's the case.

**File-integrity finding, unrelated to but worth fixing before trusting this file further:**
line 1 is not actually `replicaCount: 1` - it's `​​replicaCount: 1`, two zero-width
space characters (U+200B) prefixed onto the key:

```
$ python3 -c "import yaml; print(list(yaml.safe_load(open('aws_eks.yaml')).keys())[0])" | cat -A
M-bM-^@M-^L M-bM-^@M-^L replicaCount$
```

A YAML/Helm loader parses that as a key literally named `"​​replicaCount"`, which
matches nothing in the chart's schema - **Helm would silently fall back to the chart's own
default replica count instead of the `1` this file appears to specify.** The rest of the file
(146 lines, 80 of them blank - one blank line between almost every content line) is consistent
with having been copied out of a rendered document (Confluence, Google Docs, a PDF) rather than
edited as plain text, which is the most common way this specific artifact gets introduced. No
other line in the file carries the same character, so it looks like a one-off paste artifact on
line 1, not a systemic encoding problem - but it means **this file cannot be trusted as proof
of the live replica count**; that needs independent confirmation (`kubectl get deploy
mockserver-public -o jsonpath='{.spec.replicas}'` or equivalent) before relying on the
single-instance assumption the rest of this study makes.

That assumption matters more than it looks: if MockServer is actually running with more than
one replica (because the real deployment fell back to a chart default other than 1), its
request/response log is **not shared** across pods - it's per-process, in-memory. mock-ui's
poller (`_poll_history_once` in `mock-ui/app.py:355`) hits `/mockserver/retrieve` through the
Kubernetes Service, which load-balances across whichever replicas exist; each poll could land
on a different pod with a different in-memory log, and entries would appear to flicker in and
out between polls with no restart involved at all. This is a more direct, higher-probability
explanation for "Recent Requests doesn't work" than anything below - and it's exactly the kind
of thing the corrupted `replicaCount` key prevents this file from ruling out.

## 2. Does the ALB path put the just-shipped live-tail fix at risk?

`add-live-tail-diagnostics` (archived 2026-08-11) added a 15-second SSE heartbeat specifically
so the live tail survives an idle-connection timeout in front of mock-ui - motivated by exactly
this kind of real AWS ALB deployment. What this file's `ingress` block shows:

- `className: "alb"`, `alb.ingress.kubernetes.io/target-type: ip` - a real AWS Load Balancer
  Controller-managed ALB routing directly to pod IPs, not the local nginx stand-in this repo's
  own `poc-environment` uses. This is the class of proxy the heartbeat was built for.
- No `alb.ingress.kubernetes.io/target-group-attributes` (or similar) setting an explicit idle
  timeout. Left unset, an ALB's idle timeout defaults to **60 seconds**. The 15s heartbeat gives
  4x headroom under that default - safe *if* the default is actually what's in effect.
- **Unverifiable from this file**: whether some other layer in front of or shared with this ALB
  (a listener rule shared across `alb.ingress.kubernetes.io/group.name: flex-eks-internal-mock`,
  a WAF, an internal proxy) applies a shorter timeout than the ALB's own default. Recommend
  confirming the live target group's `idle_timeout.timeout_seconds` directly (AWS console or
  `aws elbv2 describe-load-balancer-attributes`) rather than assuming the default applies, per
  the checklist already written in
  `docs/studies/2026-08-11-live-tail-eks-diagnostics.md`.
- **This ingress has no `/mock-ui` path rule** - only `/` to the `mockserver` service. If
  mock-ui is meant to sit behind this same ALB (the pattern this repo's own
  `poc-environment` spec documents - "reachable through the single external entrypoint"), that
  routing isn't visible here, meaning either mock-ui is fronted by a separate
  Ingress/ALB not shown in this file, or it isn't reachable through this host at all in this
  environment. Either way, this file alone can't confirm mock-ui's exposure is safe or even
  present - a second values file (for mock-ui, if one exists) would be needed to complete this
  half of the analysis.

**Conclusion for this section:** nothing in what's visible here contradicts the heartbeat fix
working correctly - but "works safely" can only be confirmed for the ALB-idle-timeout failure
mode specifically, and only once the actual live idle-timeout value and mock-ui's own ingress
path are confirmed independently of this file.

## 3. Is "Recent Requests isn't cleared when MockServer restarts" fixed by `add-live-tail-diagnostics`?

**No - this is a different failure mode than the one that change addressed, and it is not
fixed.** Walking through why, from the current code:

**Why the data disappears on a MockServer restart at all (expected, already documented):**
MockServer's `MOCKSERVER_PERSIST_EXPECTATIONS`/`initializationJsonPath` persistence (visible in
both this repo's own `k8s/overlays/with-mockserver/mockserver-deployment.yaml` and in
`aws_eks.yaml`'s `app.config.properties`) persists **expectations** (the mocks) to disk -
that's what survives a restart. It does not, and by MockServer's own design cannot, persist the
**observed request/response log** that `/mockserver/retrieve?type=REQUEST_RESPONSES` returns -
that log is in-memory only and is empty immediately after any MockServer restart, for any
reason (rolling deploy, node drain, OOM, crash). mock-ui's own UI already says as much:
`mock-ui/static/index.html:134` - *"History is lost if the MockServer pod restarts."* This part
is intentional and already correctly communicated.

**What actually happens in mock-ui when that reset occurs, while a browser tab is already open:**

1. The shared poller (`_poll_history_once`, `mock-ui/app.py:355`) keeps running every
   `REQUEST_STREAM_POLL_SECONDS` (1s). After MockServer restarts, its next poll gets a
   **successful** response (`200`, not a `MockServerError`) containing an empty list. This is
   not treated as a failure - it correctly overwrites `_history_snapshot` with `[]`. The
   just-shipped logging now makes this visible: a run of `history poll succeeded ... (247
   entries)` lines abruptly dropping to `(0 entries)` is a clear, searchable signal in the logs
   that this happened - genuinely useful, and new as of this change.
2. **But nothing tells an already-open browser tab that the reset happened.** The rows already
   rendered in `#requests-body` were put there by `loadRequestHistory()`
   (`mock-ui/static/app.js:507`), which is only called on initial page load and on an explicit
   filter change (`reloadRequestsForFilterChange`, `app.js:590`) - never on a timer, and never
   in response to the live tail or the reconnect logic. The live tail
   (`connectRequestsStream`'s `onmessage`, `app.js`) only ever **prepends** new rows via
   `prependRequestRow` - there is no code path that removes or invalidates existing rows.
3. If **only MockServer** restarts, mock-ui itself is a separate process/pod that never goes
   down, so the already-open `EventSource` never breaks either. The connection-status indicator
   correctly, but misleadingly, keeps showing **Live** the entire time - the reconnect/backoff
   logic added in `add-live-tail-diagnostics` never even engages, because nothing about *that*
   connection broke. The only symptom is that no new rows arrive (`entry["timestamp"] >
   last_timestamp` in `event_stream` never finds anything from the now-empty snapshot), while
   every pre-restart row stays on screen, unlabeled, indefinitely.

**Confirmed (2026-08-11, live testing) that the same symptom also happens when mock-ui itself
restarts - via the reconnect path, not just the "connection never broke" path above** - which
is the more likely real-world case, since a rolling deploy or node drain typically restarts
mock-ui and MockServer together. The mechanism is subtly different but converges on the same
result: `connectRequestsStream()` (`mock-ui/static/app.js:593`) is the function used both for
the *first* connection and for *every* automatic reconnect attempt scheduled by
`scheduleRequestsReconnect()` (`app.js:579-591`). When mock-ui's pod actually dies, the open
`EventSource` genuinely errors, the reconnect loop correctly retries with backoff, and once the
new pod is ready a reconnect attempt genuinely succeeds - the indicator correctly returns to
**Live**. But `connectRequestsStream()` only opens the SSE tail; it never calls
`loadRequestHistory()`. So even a *real*, successfully-recovered reconnection never clears or
refreshes `#requests-body` - it just resumes prepending new rows above the stale ones. Worse,
`syncRequestsPageStream()`'s `if (!requestsEventSource)` guard (`app.js:626-636`) means that
once the reconnect succeeds, even clicking the Recent Requests nav link again while already on
that page does nothing, because the (new) `requestsEventSource` is non-null - the only way to
force `loadRequestHistory()` to run again is to navigate to a different page and back, or a
full browser reload.

A fresh page load or reload is fine either way: `loadRequestHistory()` does
`requestsBody.innerHTML = ""` before repopulating, so a new visit correctly shows the (now
empty, or newly-accumulating) history. **The gap is specific to a tab left open across a
restart - and, as confirmed above, it fires through the reconnect path just as easily as
through the "connection never broke" path, so it is not limited to MockServer-only restarts.**

## 4. A plausible reason MockServer itself keeps restarting

Neither question above explains *why* MockServer would be restarting in the first place, but
the pieces here are suggestive enough to flag, not just the symptom:

- `aws_eks.yaml`'s `resources.limits.memory: 1Gi` caps MockServer's heap in this environment.
- No `mockserver.maxLogEntries` (or equivalent request-log retention/eviction setting) appears
  anywhere in the `app.config.properties` block - only `mockserver.initializationJsonPath` is
  set. Left at MockServer's own default, the in-memory request/response log can grow
  unboundedly with real traffic.
- mock-ui's shared poller fetches that **entire, unfiltered, unpaginated** log every single
  second (`/mockserver/retrieve?type=REQUEST_RESPONSES`, `mock-ui/app.py:346`) regardless of how
  large it's grown - a design already known to be expensive at scale (see
  `docs/studies/2026-08-09-recent-requests-resilience.md`), previously fixed for the "N browser
  tabs means N pollers" case, but not for the "one very large log" case.
- The new per-poll latency logging (`history poll succeeded in %.3fs (%d entries)`) will now
  make a growing log directly visible over time in the logs - if latency and entry count climb
  steadily rather than staying flat, that's the log growing unbounded, and a MockServer OOMKill
  under the 1Gi limit becomes a very plausible explanation for repeated restarts - which would
  in turn repeatedly trigger the staleness gap in Section 3, in an environment with production
  traffic volumes this local repo's own synthetic test traffic never approaches.

This is inference, not confirmed by anything measured against the real environment - flagged as
the most actionable next thing to check, not a conclusion.

## 5. Verdict

**Confirmed safe (as far as this file shows):** the ALB idle-timeout failure mode the live-tail
change targeted has 4x headroom against the ALB's default idle timeout, assuming that default
is actually what's configured for this target group.

**Unverified, not confirmable from this file alone:** the real live idle-timeout value; whether
mock-ui is even fronted by this same ALB (no `/mock-ui` path is present here); mock-ui's own
resource limits, replica count, and `LOG_LEVEL` in this environment; and the real live
MockServer replica count, given the corrupted `replicaCount` key in this file can't be trusted.

**Confirmed not fixed, needs more work if it should be:** an already-open Recent Requests tab
does not detect or reflect a restart of MockServer, mock-ui, or both. When only MockServer
restarts, the connection-status indicator stays Live throughout (correctly, for the
browser<->mock-ui connection - but misleadingly for the underlying data). When mock-ui itself
restarts, the reconnect logic correctly detects the drop and correctly recovers the
connection back to Live - but even that successful reconnect never re-fetches or clears the
already-rendered rows, because the function used for every reconnect attempt
(`connectRequestsStream`) only resumes the live tail and never calls `loadRequestHistory()`.
Either way, rows from before the restart are never cleared or marked stale, and once the tab
is in this state, only navigating away and back (or a full reload) fixes it - clicking Recent
Requests again while already on it is a no-op, blocked by `syncRequestsPageStream()`'s
`if (!requestsEventSource)` guard. This is a distinct failure mode from the one
`add-live-tail-diagnostics` fixed - that change hardened the browser<->mock-ui *transport*
(detecting and recovering a dropped connection); this gap is about mock-ui<->MockServer *data
continuity* after a connection - dropped or not - comes back, which nothing in that change
touches.

**Worth investigating, not yet confirmed:** whether unbounded MockServer request-log growth
under this environment's 1Gi memory limit, combined with mock-ui's once-a-second full-log poll,
is what's causing MockServer to restart in the first place - which would make Section 3's gap
the *visible symptom* of a *root cause* neither this study nor `add-live-tail-diagnostics`
resolved.

## If this gets picked up as a change (not proposed here, just what the shape would likely be)

- Detecting a MockServer restart from the poller's perspective looks straightforward: the
  snapshot's entry count or newest timestamp going *backwards or to empty* between two
  consecutive successful polls is a clean signal `_poll_history_once` already has everything it
  needs to observe.
- Getting that signal to an already-open tab needs a new mechanism - most naturally, a special
  SSE message (a named event, not the current heartbeat comment which browsers can't see) that
  the client uses to clear `#requests-body` and re-fetch history, similar to how
  `loadRequestHistory()` already fully replaces `requestsBody.innerHTML`.
- The unbounded-log-growth question needs measurement in the real environment (or at least
  MockServer's documented `maxLogEntries`-equivalent property confirmed and set) before
  concluding it's the actual cause of the restarts, not just a plausible one.

## Sources

- `mock-ui/aws_eks.yaml` - the file under analysis, including the byte-level inspection of line
  1 (`xxd`, `python3 -c "import yaml; ..."`).
- `mock-ui/app.py` - `_poll_history_once` (:355), `_history_poller_loop` (:371), `event_stream`
  (:427), logging setup (:12).
- `mock-ui/static/app.js` - `loadRequestHistory` (:507), `openRequestsStream`/
  `connectRequestsStream`/`scheduleRequestsReconnect` (the reconnect logic added in
  `add-live-tail-diagnostics`).
- `mock-ui/static/index.html:134` - existing UI copy already documenting history loss on
  restart.
- `k8s/overlays/with-mockserver/mockserver-deployment.yaml`,
  `k8s/overlays/with-mockserver/mockserver-configmap.yaml` - this repo's own local equivalent of
  MockServer's persistence setup, for comparison (no resource limits set locally, unlike
  `aws_eks.yaml`'s 1Gi cap).
- `openspec/changes/archive/2026-08-11-add-live-tail-diagnostics/` - the just-archived change
  and its `design.md`, for what was and wasn't in scope.
- `docs/studies/2026-08-11-live-tail-eks-diagnostics.md` - the diagnostic checklist that change
  produced, referenced in Section 2's idle-timeout-verification recommendation.
- `docs/studies/2026-08-09-recent-requests-resilience.md` - prior study on the shared poller's
  cost characteristics, referenced in Section 4.
