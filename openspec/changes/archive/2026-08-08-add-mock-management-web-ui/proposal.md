## Why

Today the only way to manage MockServer expectations is `kubectl port-forward` plus three shell scripts
(`add-mock.sh`, `list-mocks.sh`, `delete-mock.sh`) that wrap raw `curl`/`jq` calls. That's fine for this
POC's own development, but it doesn't demonstrate what a self-service mocking workflow would look like for
a team in a real environment - a developer there would expect a web page, not a terminal. Adding a small,
real-time web UI for creating, editing, deleting, and viewing mocks shows that shape without adding
much complexity, and does so entirely against MockServer's live state (no separate datastore to keep in
sync).

## What Changes

- Add a new in-cluster component, `mock-ui/`, that serves a small web interface for managing MockServer
  expectations: list (excluding the seeded catch-all), create, edit (update in place, not duplicate), and
  delete - each action taking effect in MockServer immediately, with no caching layer.
- Backend: a small Python 3 + Flask app (no NodeJS anywhere) that serves the static frontend and exposes a
  small `/api/mocks` JSON API translating to/from MockServer's own expectation API
  (`PUT /mockserver/expectation`, `PUT /mockserver/retrieve`, `PUT /mockserver/clear`).
- Frontend: static HTML/CSS/vanilla JavaScript (no build step, no framework) that calls `/api/mocks` and
  re-lists MockServer's actual current state after every action.
- New Kubernetes manifests (`mock-ui` Deployment/Service) added to `k8s/overlays/with-mockserver/` only -
  the UI only makes sense once MockServer is installed - deployed/torn down by the existing
  `scripts/install-mockserver.sh` / `scripts/uninstall-mockserver.sh`, no new scripts needed.
- The UI is reachable through the same ALB stand-in Ingress as everything else, at a new `/mock-ui` path,
  rather than requiring its own port-forward - consistent with this POC's "single external entrypoint"
  principle and closer to how a real deployment would expose it.
- The seeded priority-0 catch-all forwarding expectation is never shown as editable or deletable in the UI.

## Capabilities

### New Capabilities
- `mock-management-ui`: a real-time web interface for creating, viewing, updating, and deleting MockServer
  mock expectations from inside the cluster.

### Modified Capabilities
(none - existing `poc-environment` and `mockserver-integration` behavior is unchanged; the CLI scripts keep
working exactly as before, side by side with the new UI)

## Impact

- Code (new): `mock-ui/` (Python/Flask backend + static frontend + Dockerfile),
  `k8s/overlays/with-mockserver/mock-ui-deployment.yaml`,
  `k8s/overlays/with-mockserver/mock-ui-service.yaml`.
- Code (modified): `k8s/overlays/with-mockserver/kustomization.yaml` (add the two new manifests),
  `k8s/overlays/with-mockserver/ingress-patch.yaml` (add the `/mock-ui` path rule),
  `scripts/build-and-load-images.sh` (build/load the new image),
  `scripts/uninstall-mockserver.sh` (also remove the `mock-ui` Deployment/Service), `README.md`.
- Dependencies: adds Flask (a pip package, pinned in `mock-ui/requirements.txt`) for the new backend; no
  NodeJS anywhere.
- No change to `gateway/`, `backend/`, `k8s/base/`, or the existing CLI scripts' own behavior.
