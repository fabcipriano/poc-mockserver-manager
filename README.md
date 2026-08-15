# MockServer POC

A proof of concept showing how to drop [MockServer](https://www.mock-server.com/) transparently in front of
a Gateway so a developer can mock any API route in minutes, with everything else passing through to the
real backend untouched.

Production runs **three** independent MockServer instances - one per gateway (public, private, product) -
so this POC emulates all three, and `mock-ui` can connect to any one of them from a single web interface.

## Architecture

```
without MockServer:   ALB -> Gateway -> Backend
with MockServer:       ALB -> MockServer -> Gateway -> Backend
```

This repo emulates production's three gateways as three independent topologies, each with its own
MockServer instance:

| Topology  | Path                                              | Backend |
|-----------|----------------------------------------------------|---------|
| product   | `ALB -> MockServer -> Gateway -> Backend`           | The real, unmodified [restful-booker](https://github.com/mwinteringham/restful-booker) application - the original, most feature-complete stand-in. |
| public    | `ALB -> MockServer -> Backend`                      | `backend-public/` - a minimal Express app returning a hardcoded JSON API (no separate Gateway hop, no real upstream app - deliberately kept simple). |
| private   | `ALB -> MockServer -> Backend`                      | `backend-private/` - same shape as `backend-public/`, a separate service with its own hardcoded routes. |

| Component        | Stands in for                | What it does |
|-------------------|------------------------------|---------------|
| Ingress + ingress-nginx | AWS ALB                | The single external HTTP entrypoint. "Installing" MockServer means repointing this Ingress's backend from the Gateway Service to the MockServer Service(s) - each topology gets its own path prefix (`/`, `/public`, `/private`) since production's three gateways sit behind genuinely separate entrypoints and this POC keeps them all under one Ingress for simplicity. |
| `gateway/`        | NodeJS Gateway (product only)  | A minimal Express app that proxies every request to `backend/`. **Never modified** to enable/disable mocking. Only the product topology has a separate Gateway hop. |
| `backend/`         | Real backend (product)         | The real, unmodified restful-booker application (auth, CRUD on a `booking` resource), built from its own upstream source pinned to a specific commit and run in-cluster - no external network dependency at request time. |
| `backend-public/`, `backend-private/` | Backends (public/private) | Small Express apps that answer with a fixed, hardcoded JSON response - no proxying, no real upstream application. |
| MockServer (x3)     | New                            | One instance per topology. By default forwards every request unchanged to its configured upstream. When a dev adds an expectation for a route on a given instance, that instance answers the route directly and keeps forwarding everything else. |
| `mock-ui/`         | New                            | A small Python/Flask web interface for creating, editing, and deleting mock expectations, and for browsing recent requests, against any one of the three MockServer instances - switchable from a target selector in the sidebar. Reachable at `/mock-ui` through the same ALB stand-in - no port-forward needed. |

See `openspec/changes/mockserver-poc/design.md` and `openspec/changes/add-multi-mockserver-support/design.md`
for the full rationale behind these choices, including alternatives considered and known risks.

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

This deploys all three MockServer instances (product, public, private) and repoints the Ingress so each
topology is reachable at its own path - `/` (product), `/public`, `/private`. The product topology's
Gateway Deployment/Service/code are never touched. Traffic on `/` keeps flowing exactly as before:

```bash
curl http://localhost:8080/booking/1
# still returns the real backend's response - MockServer forwards anything unmocked

curl http://localhost:8080/public/items
# returns backend-public's hardcoded response - forwarded through the public topology's MockServer

curl http://localhost:8080/private/accounts
# returns backend-private's hardcoded response - forwarded through the private topology's MockServer
```

## Adding your first mock

MockServer's own REST API listens on the same port as the proxy (`1080` inside the cluster) on every
instance. Port-forward to the instance you want (`mockserver` for product, `mockserver-public`,
`mockserver-private`), then use the helper script:

```bash
kubectl port-forward svc/mockserver -n mockserver-poc 1080:80 &

scripts/add-mock.sh GET /booking/1 200 mocks/booking-get.example.json
```

The same script works against the public/private instances too - just port-forward the corresponding
Service instead (e.g. `kubectl port-forward svc/mockserver-public -n mockserver-poc 1080:80`) and point
`MOCKSERVER_URL` at it if you're not using the default `localhost:1080`.

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

A **MockServer** selector in the sidebar lets you pick which of the three instances (Gateway Public, Gateway
Private, Gateway Product) you're viewing; switching it re-scopes Create Mock, List Mocks, and Recent
Requests to that instance, and the selection is kept in the page's URL so it survives navigation and reload
(and is shareable - send a teammate a link straight to a specific target's Recent Requests page).

For whichever instance is selected, the UI lists every currently active, developer-created mock (the seeded
catch-all is never shown or editable here), and lets you create a new one, edit an existing one in place, or
delete one. Every action calls that instance's MockServer directly, so the change takes effect immediately -
the UI keeps no cache or copy of its own. It's a thin Python/Flask app (`mock-ui/`) that talks to the same
MockServer REST API `scripts/add-mock.sh` and friends use, so both ways of managing mocks work side by side
against the same live state.

### Configuring mock-ui

`mock-ui` is configured entirely through environment variables read once at process startup, so migrating
it to a different environment - a different cluster, a different set of MockServer instances, different
traffic volume - is a configuration change, not a code change or image rebuild. All five variables are set
in `k8s/overlays/with-mockserver/mock-ui-deployment.yaml`; that file doubles as a working example.

| Variable | Default | Controls |
| --- | --- | --- |
| `MOCKSERVER_TARGETS` | *(unset)* | JSON array of `{"id", "label", "url"}` objects - the MockServer instances the selector lists. See below. |
| `MOCKSERVER_URL` | `http://mockserver` | Single-target fallback URL, used only when `MOCKSERVER_TARGETS` is unset. See below. |
| `REQUEST_HISTORY_LIMIT` | `40` | Recent Requests page size - how many requests one page/load-more fetch returns. |
| `REQUEST_STREAM_POLL_SECONDS` | `1` | How often (in seconds) the background poller re-checks each target's MockServer for new requests. |
| `HEARTBEAT_INTERVAL_SECONDS` | `15` | How often (in seconds) an idle live-tail connection sends a keep-alive event, to stay under typical proxy/ALB idle-connection timeouts. |
| `BEDROCK_MODEL_ID` | *(unset)* | Enables the AI Mock Generator page - the AWS Bedrock model or inference-profile ID it calls. Unset means that page is simply unavailable - see below. |
| `AWS_REGION` | *(boto3's own resolution)* | AWS region for the Bedrock call. Only read when `BEDROCK_MODEL_ID` is set; if unset, falls back to whatever boto3's standard chain resolves (`AWS_DEFAULT_REGION`, shared config file, instance metadata). |

`REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, and `HEARTBEAT_INTERVAL_SECONDS` each accept a
positive integer; an unset variable keeps its default, and an invalid value (non-integer, zero, or
negative) fails `mock-ui` startup immediately with a specific error, rather than starting with an unusable
setting.

Unlike those, `BEDROCK_MODEL_ID` fails *open*, not fast: `mock-ui` starts up and runs normally without it,
just with the AI Mock Generator page unavailable - see "Configuring AI mock generation" below.

#### Configuring which MockServer instances mock-ui can reach

`mock-ui` reads its list of MockServer targets from the `MOCKSERVER_TARGETS` environment variable at
startup - a JSON array of `{"id", "label", "url"}` objects, one per instance:

```json
[
  {"id": "public", "label": "Gateway Public", "url": "http://mockserver-public"},
  {"id": "private", "label": "Gateway Private", "url": "http://mockserver-private"},
  {"id": "product", "label": "Gateway Product", "url": "http://mockserver"}
]
```

Adding, removing, or repointing a target only requires changing this value (see
`k8s/overlays/with-mockserver/mock-ui-deployment.yaml`) and restarting the pod - no code change or image
rebuild. If `MOCKSERVER_TARGETS` is unset, `mock-ui` falls back to a single target built from the older
`MOCKSERVER_URL` variable (default `http://mockserver`), so an existing single-server deployment keeps
working unchanged. Because this POC's manifest always sets `MOCKSERVER_TARGETS`, `MOCKSERVER_URL` has no
effect there today - it only matters for a deployment that intentionally omits `MOCKSERVER_TARGETS` in
favor of a single fixed MockServer.

#### Configuring AI mock generation

The **AI Mock Generator** page lets a developer select captured Recent Requests entries and have an LLM
draft candidate mock expectations from them, reviewed and approved before anything loads into MockServer
(see `openspec/changes/add-llm-mock-generation`). It calls the model through **AWS Bedrock** rather than a
single model vendor's API directly, so which model actually answers - Anthropic Claude, Amazon Nova, Meta
Llama, or anything else Bedrock hosts that supports the Converse API - is a configuration choice
(`BEDROCK_MODEL_ID`), not a code change.

Two things are needed:

1. **Model access.** In the AWS Bedrock console, request access to whichever model `BEDROCK_MODEL_ID` names
   (Bedrock model access is opt-in per AWS account and region). Some models (notably newer Claude models,
   in certain regions) require an inference-profile ID rather than a bare model ID - `BEDROCK_MODEL_ID`
   accepts either form as an opaque value.
2. **AWS credentials with `bedrock:InvokeModel` permission for that model.** Prefer letting the `mock-ui`
   pod assume an IAM role (IRSA on EKS, or an instance profile on plain EC2 nodes) - boto3 picks that up
   automatically with no extra configuration. For a cluster without such a role (e.g. this POC's local
   cluster), fall back to a static key pair, which is deliberately **not** committed anywhere in this repo -
   `mock-ui-deployment.yaml` reads it from a `mock-ui-aws-credentials` Secret that you create yourself:

   ```sh
   kubectl create secret generic mock-ui-aws-credentials \
     --namespace mockserver-poc \
     --from-literal=access-key-id=<your AWS access key ID> \
     --from-literal=secret-access-key=<your AWS secret access key>
   ```

Until `BEDROCK_MODEL_ID` is set (and, in the static-key case, until that Secret exists), the AI Mock
Generator page is simply unavailable - `mock-ui` starts and runs normally either way (see
`BEDROCK_MODEL_ID`'s fail-open behavior above). Restart the `mock-ui` pod after creating or updating the
Secret so it picks up the new environment variables.

## Mock persistence

Each of the three MockServer instances persists independently. Mock expectations - the seeded catch-all and
anything a developer adds via `scripts/add-mock.sh` or `mock-ui` - survive a restart or rescheduling of that
instance's pod. MockServer's built-in JSON persistence (`MOCKSERVER_PERSIST_EXPECTATIONS` - the property
name for the `5.15.0` image this repo pins; newer MockServer releases rename it to
`MOCKSERVER_PERSIST_EXPECTATIONS_AS_JSON`) writes the full current expectation set to a file on that
instance's own `PersistentVolumeClaim` (`mockserver-data`, `mockserver-public-data`,
`mockserver-private-data`) every time it changes, and MockServer reloads that same file
(`MOCKSERVER_INITIALIZATION_JSON_PATH`) on every boot. On a brand-new volume (first install), a small init
container seeds that file from that instance's own ConfigMap's catch-all rule so it's still present before
any mock has been added.

**`scripts/uninstall-mockserver.sh` does not delete these PVCs** - persisted mocks survive an
uninstall/reinstall cycle, the same way you wouldn't expect a real environment's persistent storage to be
wiped just because an application was temporarily taken down. To fully reset a given instance (wipe its
persisted mocks back to just the catch-all), delete its PVC explicitly:

```bash
kubectl delete pvc mockserver-data -n mockserver-poc              # product
kubectl delete pvc mockserver-public-data -n mockserver-poc       # public
kubectl delete pvc mockserver-private-data -n mockserver-poc      # private
```

## Uninstalling MockServer

```bash
scripts/uninstall-mockserver.sh
```

This reverts the Ingress backend to the Gateway Service, and removes all three MockServer
Deployments/Services/ConfigMaps along with the public and private topologies' backend Deployments/Services.
Traffic on `/` returns to the direct `ALB -> Gateway -> Backend` path exactly as it was before MockServer
existed. All three `*-data` PVCs (and everything persisted on them) are left in place - see "Mock
persistence" above.

## Gotchas

- **Delete expectations by id, not by method/path.** MockServer's `clear` API matches by request-matcher
  *overlap*, not exact identity. The seeded catch-all's path (`/.*`) overlaps every request, so clearing "by
  method + path" also deletes the catch-all and silently breaks pass-through for every other route until
  MockServer restarts. `scripts/delete-mock.sh` takes an expectation id specifically to avoid this.
- **Priority matters, not insertion order.** If a mock isn't taking effect, check its priority is higher than
  the catch-all's (`0`). `scripts/add-mock.sh` handles this for you at `10`.
- **Mocks for the public/private topologies need the `/public`/`/private` prefix in their path.** The shared
  Ingress does not strip these prefixes, so MockServer (and `backend-public`/`backend-private`) see the full
  `/public/...` or `/private/...` path exactly as the client sent it. A mock created with path `/items`
  never matches traffic arriving at `/public/items` - create it with path `/public/items` instead. This
  doesn't apply to the product topology, whose Ingress path is the unprefixed `/`.

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
- This POC exposes all three topologies through one Ingress with a path prefix per topology (`/`,
  `/public`, `/private`); production has genuinely separate entrypoints per gateway, not path prefixes on a
  shared one - see `openspec/changes/add-multi-mockserver-support/design.md`.
- `backend-public/` and `backend-private/` are deliberately trivial (one or two hardcoded JSON routes each) -
  they exist to prove the multi-target MockServer/`mock-ui` behavior, not to model a second real backend.

## Repository layout

```
backend/            restful-booker backend stand-in for the product topology (built from pinned upstream source)
backend-public/      Minimal NodeJS backend stand-in for the public topology (hardcoded JSON API)
backend-private/     Minimal NodeJS backend stand-in for the private topology (hardcoded JSON API)
gateway/             NodeJS gateway stand-in for the product topology (Express proxy)
mock-ui/             Web UI for managing MockServer expectations in real time (Python/Flask), multi-target aware
k8s/base/            ALB stand-in (Ingress) + Gateway + Backend manifests (product topology baseline)
k8s/overlays/with-mockserver/   All three MockServer instances + their backends + mock-ui manifests + Ingress patch
mocks/               Example committed mock expectation file(s)
scripts/             Cluster lifecycle + mock authoring helper scripts
```
