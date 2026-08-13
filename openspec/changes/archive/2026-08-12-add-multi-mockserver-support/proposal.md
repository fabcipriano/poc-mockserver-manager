## Why

In production this tool will sit in front of three independent MockServer instances - one per gateway (public, private, product) - but mock-ui and the POC environment today are hard-wired to a single MockServer reachable at one fixed URL. A developer who needs to inspect or mock traffic for a different gateway currently has no way to do that from mock-ui at all, and standing up the tool against a new/different MockServer requires rebuilding the Docker image because the target URL is baked in. This change makes mock-ui multi-server aware and configurable purely through environment variables, and extends the POC to actually emulate three gateways so the multi-server behavior can be exercised end-to-end before it meets production.

## What Changes

- mock-ui gains a concept of a "MockServer target" - id, display label, base URL - and can be configured with any number of them via an environment variable, with no code change or image rebuild required to add, remove, or repoint a target.
- The web UI adds a MockServer selector (a labeled dropdown, always visible regardless of which page is open) so a developer picks which MockServer's data they're viewing. Selecting a target re-scopes the Create Mock, List Mocks, and Recent Requests pages to that target, and the selection persists across page navigation and reload.
- All mock-ui API endpoints (mocks CRUD, request history, live-tail stream) become target-scoped, accepting which MockServer they operate against instead of assuming a single fixed one.
- The shared history-poller architecture in `app.py` is extended from one global background thread to one background thread per configured target, each polling only its own MockServer, so Recent Requests keeps working per-target with the same shared-snapshot design (no per-viewer polling cost) it has today.
- **BREAKING**: the `MOCKSERVER_URL` environment variable is replaced by a new `MOCKSERVER_TARGETS` variable that describes one or more named targets; a deployment that only sets the old variable falls back to a single default target so existing single-server deployments keep working unchanged.
- The POC environment is extended from one emulated gateway to three, mirroring the production public/private/product split: the existing MockServer + Gateway + restful-booker backend becomes the "product" target, and two new, deliberately simple targets ("public", "private") are added, each a MockServer instance forwarding directly to its own small NodeJS backend that returns a hardcoded JSON API (no proxy layer, no real upstream application) - keeping the two new stacks minimal while still letting the multi-target UI and polling be demoed against three genuinely independent MockServer instances.

## Capabilities

### New Capabilities
(none - this change extends existing capabilities rather than introducing new ones)

### Modified Capabilities
- `mockserver-integration`: MockServer is no longer assumed to be a single instance; the system supports multiple independently configured MockServer instances, each installed the same way, addressable by an id/label a client (mock-ui) uses to pick one.
- `poc-environment`: the emulated topology grows from one ALB -> Gateway -> Backend path to three independent MockServer-fronted paths (public, private, product), with the two new paths using simplified NodeJS backends returning hardcoded responses instead of a real upstream application.
- `mock-management-ui`: the web UI adds a MockServer target selector and every existing mocks/requests feature becomes scoped to the currently selected target instead of assuming one MockServer.

## Impact

- `mock-ui/app.py`: replace the single `MOCKSERVER_URL` constant and single global history-poller thread/snapshot/lock with a target registry parsed from `MOCKSERVER_TARGETS`, one poller thread per target, and a `server` parameter threaded through every mocks/requests route.
- `mock-ui/static/`: new target-selector control in `index.html`, target-aware state and API calls in `app.js`, corresponding styling in `style.css`.
- `mock-ui/test_app.py`: existing tests that assume one global snapshot/poller need updating to the per-target model; new tests for target parsing and selection.
- New `backend-public/` and `backend-private/` NodeJS services (hardcoded JSON routes) plus their Dockerfiles, mirroring the existing `backend/` and `gateway/` pattern at a smaller scope.
- `k8s/overlays/with-mockserver/`: new Deployments/Services/PVCs/ConfigMaps for `mockserver-public`, `mockserver-private`, `backend-public`, `backend-private`; `mock-ui-deployment.yaml` updated to set `MOCKSERVER_TARGETS` instead of `MOCKSERVER_URL`; ingress patch extended with path prefixes so all three MockServer-fronted paths are reachable through the single POC entrypoint.
- `README.md`: updated to describe the three-target topology and the new environment variable.
