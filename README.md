# MockServer POC

A proof of concept showing how to drop [MockServer](https://www.mock-server.com/) transparently in front of
a Gateway so a developer can mock any API route in minutes, with everything else passing through to the
real backend untouched.

## Architecture

```
without MockServer:   ALB -> Gateway -> Backend
with MockServer:       ALB -> MockServer -> Gateway -> Backend
```

This repo emulates a production topology - `ALB -> NodeJS Gateway -> restful-booker Backend` - in a local
Kubernetes cluster, then shows how MockServer is inserted as a new hop directly in front of the Gateway:

| Component        | Stands in for                | What it does |
|-------------------|------------------------------|---------------|
| Ingress + ingress-nginx | AWS ALB                | The single external HTTP entrypoint. "Installing" MockServer means repointing this Ingress's backend from the Gateway Service to the MockServer Service - a one-resource change, nothing else. |
| `gateway/`        | NodeJS Gateway                | A minimal Express app that proxies every request to the Backend. **Never modified** to enable/disable mocking. |
| `backend/`         | Real backend                  | The real, unmodified [restful-booker](https://github.com/mwinteringham/restful-booker) application (auth, CRUD on a `booking` resource), built from its own upstream source pinned to a specific commit and run in-cluster - no external network dependency at request time. |
| MockServer         | New                            | By default forwards every request unchanged to the Gateway. When a dev adds an expectation for a route, MockServer answers that route directly and keeps forwarding everything else. |
| `mock-ui/`         | New                            | A small Python/Flask web interface for creating, editing, and deleting MockServer expectations in real time, reachable at `/mock-ui` through the same ALB stand-in - no port-forward needed. |

See `openspec/changes/mockserver-poc/design.md` for the full rationale behind these choices, including
alternatives considered and known risks.

## Prerequisites

- Docker
- [kind](https://kind.sigs.k8s.io/) (or adapt the scripts for minikube)
- `kubectl`
- `jq` (used by the mock-authoring helper scripts)

## Quick start

```bash
# 1. Create a local cluster with ingress-nginx installed
scripts/create-cluster.sh

# 2. Build the backend/gateway stand-in images and load them into the cluster
scripts/build-and-load-images.sh

# 3. Deploy the baseline environment: ALB stand-in -> Gateway -> Backend
kubectl apply -k k8s/base

# 4. Confirm the baseline works (the Ingress is exposed on localhost:8080 via kind's port mapping)
curl http://localhost:8080/ping
curl http://localhost:8080/booking/1
```

## Installing MockServer

```bash
scripts/install-mockserver.sh
```

This deploys MockServer and repoints the Ingress's backend at it - the Gateway's Deployment/Service/code
are never touched. Traffic keeps flowing exactly as before:

```bash
curl http://localhost:8080/booking/1
# still returns the real backend's response - MockServer forwards anything unmocked
```

## Adding your first mock

MockServer's own REST API listens on the same port as the proxy (`1080` inside the cluster). Port-forward
to it, then use the helper script:

```bash
kubectl port-forward svc/mockserver -n mockserver-poc 1080:80 &

scripts/add-mock.sh GET /booking/1 200 mocks/booking-get.example.json
```

The script prints the new expectation's `id` - save it. Now the mocked route answers directly:

```bash
curl http://localhost:8080/booking/1
# {"firstname": "Ada", "lastname": "Lovelace", ..., "additionalneeds": "mocked-response, not the real backend"}

curl http://localhost:8080/booking/2
# still passes through to the real Gateway/Backend
```

Other example expectations are in `mocks/` - `booking-list.example.json` (`GET /booking`) and
`booking-create.example.json` (`POST /booking`) - showing a list route and a write route in addition to
this read example.

Remove the mock (pass the `id` printed by `add-mock.sh`, **not** method/path - see Gotchas below):

```bash
scripts/delete-mock.sh <expectation-id>
```

List everything currently active:

```bash
scripts/list-mocks.sh
```

### Priority convention

MockServer picks the highest-priority matching expectation. This POC seeds a catch-all forwarding
expectation at **priority 0**. `scripts/add-mock.sh` always creates new expectations at **priority 10**, so
a dev-added mock always wins over the catch-all without anyone having to think about ordering.

### Shareable mocks

For a mock worth committing to the repo (instead of a one-off REST API call), drop a JSON expectation file
into `mocks/`. Files there are meant to be wired into the same ConfigMap-backed initializer MockServer uses
for its catch-all rule, so they reload automatically whenever the MockServer pod restarts.

## Managing mocks with the Web UI

Once MockServer is installed, a small web interface for creating, editing, and deleting mocks in real time
is available through the same entrypoint - no port-forward needed:

```
http://localhost:8080/mock-ui/
```

It lists every currently active, developer-created mock (the seeded catch-all is never shown or editable
here), and lets you create a new one, edit an existing one in place, or delete one. Every action calls
MockServer directly, so the change takes effect immediately - the UI keeps no cache or copy of its own. It's
a thin Python/Flask app (`mock-ui/`) that talks to the same MockServer REST API `scripts/add-mock.sh` and
friends use, so both ways of managing mocks work side by side against the same live state.

## Mock persistence

Mock expectations - the seeded catch-all and anything a developer adds via `scripts/add-mock.sh` or
`mock-ui` - survive a restart or rescheduling of the `mockserver` pod. MockServer's built-in JSON
persistence (`MOCKSERVER_PERSIST_EXPECTATIONS` - the property name for the `5.15.0` image this repo pins;
newer MockServer releases rename it to `MOCKSERVER_PERSIST_EXPECTATIONS_AS_JSON`) writes the full current expectation set to a file
on a `PersistentVolumeClaim` (`mockserver-data`) every time it changes, and MockServer reloads that same
file (`MOCKSERVER_INITIALIZATION_JSON_PATH`) on every boot. On a brand-new volume (first install), a small
init container seeds that file from the `mockserver-init` ConfigMap's catch-all rule so it's still present
before any mock has been added.

**`scripts/uninstall-mockserver.sh` does not delete this PVC** - persisted mocks survive an
uninstall/reinstall cycle, the same way you wouldn't expect a real environment's persistent storage to be
wiped just because an application was temporarily taken down. To fully reset (wipe all persisted mocks back
to just the catch-all), delete the PVC explicitly:

```bash
kubectl delete pvc mockserver-data -n mockserver-poc
```

## Uninstalling MockServer

```bash
scripts/uninstall-mockserver.sh
```

This reverts the Ingress backend to the Gateway Service and removes MockServer's Deployment/Service/ConfigMap.
Traffic returns to the direct `ALB -> Gateway -> Backend` path exactly as it was before MockServer existed.
The `mockserver-data` PVC (and everything persisted on it) is left in place - see "Mock persistence" above.

## Gotchas

- **Delete expectations by id, not by method/path.** MockServer's `clear` API matches by request-matcher
  *overlap*, not exact identity. The seeded catch-all's path (`/.*`) overlaps every request, so clearing "by
  method + path" also deletes the catch-all and silently breaks pass-through for every other route until
  MockServer restarts. `scripts/delete-mock.sh` takes an expectation id specifically to avoid this.
- **Priority matters, not insertion order.** If a mock isn't taking effect, check its priority is higher than
  the catch-all's (`0`). `scripts/add-mock.sh` handles this for you at `10`.

## Known gaps (don't over-generalize these results)

- The Ingress + ingress-nginx ALB stand-in does not reproduce real AWS ALB behavior (target groups, listener
  rules, WAF, TLS termination). It only proves the "repoint the entrypoint" mechanic.
- restful-booker keeps its data in an in-memory store that resets on every pod restart/reschedule - don't
  expect bookings created (or mocks-turned-real writes) to survive a Backend pod recreation.
- `backend/Dockerfile` builds restful-booker from a commit pinned in that file - it isn't tracking
  upstream's `main` branch, so bumping to a newer restful-booker version is a deliberate one-line edit.
- No auth/mTLS is modeled between hops; header/timeout behavior under a real gateway's auth layer is
  undocumented here.
- The mock management web UI (`/mock-ui`) has no authentication either - anyone who can reach the ALB
  stand-in can create, edit, or delete mocks, matching this POC's no-auth stance everywhere else.
- Rolling MockServer into the *real* environment (where the ALB may not even be Kubernetes-managed) is a
  follow-up decision this POC does not make - see `openspec/changes/mockserver-poc/design.md` - Open Questions.

## Repository layout

```
backend/            restful-booker backend stand-in (built from pinned upstream source)
gateway/             NodeJS gateway stand-in (Express proxy)
mock-ui/             Web UI for managing MockServer expectations in real time (Python/Flask)
k8s/base/            ALB stand-in (Ingress) + Gateway + Backend manifests
k8s/overlays/with-mockserver/   MockServer + mock-ui manifests + Ingress patch
mocks/               Example committed mock expectation file(s)
scripts/             Cluster lifecycle + mock authoring helper scripts
```
