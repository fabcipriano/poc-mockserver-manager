## 1. mock-ui backend: target registry and configuration

- [x] 1.1 Add a `Target` structure (id, label, url) and a `parse_targets()` function that reads `MOCKSERVER_TARGETS` (JSON array) at startup, falling back to a single `id=default, label=Default` target built from `MOCKSERVER_URL` (default `http://mockserver`) when `MOCKSERVER_TARGETS` is unset.
- [x] 1.2 Validate parsed targets (non-empty, each has `id`/`label`/`url`, ids unique) and exit the process with a clear log message on failure, per design.md's fail-fast decision.
- [x] 1.3 Build the `TARGETS: dict[str, Target]` registry once at startup and make it available to route handlers.

## 2. mock-ui backend: per-target history poller

- [x] 2.1 Move `_history_lock`, `_history_snapshot`, `_history_reset_generation` from module globals onto the `Target` object (or a small per-target state holder keyed by target id).
- [x] 2.2 Parametrize `_poll_history_once`, `_detect_history_reset`, `_get_history_snapshot`, `_get_history_reset_generation`, and `_history_poller_loop` to operate on a single `Target`'s state instead of module globals.
- [x] 2.3 Parametrize `_mockserver_put` to take a target's base URL instead of the module-level `MOCKSERVER_URL` constant.
- [x] 2.4 In `if __name__ == "__main__"`, start one daemon `_history_poller_loop` thread per configured target instead of one thread total.

## 3. mock-ui backend: target-scoped routes

- [x] 3.1 Add `GET /mock-ui/api/servers` returning each target's `id` and `label` (not `url`), in configured order.
- [x] 3.2 Add a `server` query-param resolver shared by the mocks and requests routes: resolves against `TARGETS`, defaults to the first configured target when omitted, and returns 404 with the list of known ids for an unknown `server` value.
- [x] 3.3 Update `list_mocks`, `create_mock`, `update_mock`, `delete_mock` to resolve `server` and call `_mockserver_put` against that target's URL.
- [x] 3.4 Update `list_requests` and `stream_requests` to resolve `server` and read/poll that target's snapshot/reset-generation state instead of the old globals.

## 4. mock-ui backend: tests

- [x] 4.1 Update `test_app.py`'s existing poller/reset-detection tests to construct/patch a `Target` (or equivalent per-target state) instead of patching module-level globals.
- [x] 4.2 Add tests for `parse_targets()`: JSON config with multiple targets, `MOCKSERVER_URL`-only fallback, and each validation failure (invalid JSON, missing field, duplicate id).
- [x] 4.3 Add a test for the unknown-`server` 404 path and for the default-target fallback when `server` is omitted.

## 5. mock-ui frontend: target selector

- [x] 5.1 Add a MockServer `<select>` to the sidebar in `index.html`, visible on every page, populated from `GET /mock-ui/api/servers`.
- [x] 5.2 In `app.js`, add a `currentServer` state variable initialized from the `?server=` URL query param (falling back to the first entry from `/api/servers` if absent or unrecognized), and keep the query param in sync when the selection changes.
- [x] 5.3 Thread `server=<currentServer>` onto every API call: `loadMocks`, create/update/delete mock, `loadRequestHistory`, `loadMoreRequests`, and the SSE stream URL built in `connectRequestsStream`.
- [x] 5.4 On target change: reload the mocks list, reset and reconnect the Recent Requests stream (reusing the existing reconnect/resync path), and reset the create-mock form if it was mid-edit.
- [x] 5.5 Style the selector consistently with the existing sidebar (`style.css`).

## 6. POC: new NodeJS backends for public and private targets

- [x] 6.1 Create `backend-public/` - a minimal Express app (mirroring `gateway/`'s structure) with one or two hardcoded JSON routes (e.g. `GET /health`, `GET /items`) and its own `package.json`/`Dockerfile`.
- [x] 6.2 Create `backend-private/` with the same shape as `backend-public/`, distinct hardcoded routes/responses, its own `package.json`/`Dockerfile`.

## 7. POC: Kubernetes manifests for two new MockServer-fronted topologies

- [x] 7.1 Add `backend-public-deployment.yaml`/`backend-public-service.yaml` and `backend-private-deployment.yaml`/`backend-private-service.yaml` under `k8s/overlays/with-mockserver/`.
- [x] 7.2 Add `mockserver-public-*` and `mockserver-private-*` Deployment/Service/PVC/ConfigMap manifests, copied from the existing `mockserver-*` pattern, each ConfigMap's catch-all forward pointed at `backend-public`/`backend-private` instead of `gateway`.
- [x] 7.3 Add all new resources to `kustomization.yaml`.
- [x] 7.4 Extend `ingress-patch.yaml` with `/public` and `/private` path prefixes routed to `mockserver-public`/`mockserver-private`, alongside the existing `/` (product) and `/mock-ui` paths.
- [x] 7.5 Update `mock-ui-deployment.yaml`'s env to set `MOCKSERVER_TARGETS` (public/private/product, per design.md's example) instead of `MOCKSERVER_URL`.

## 8. Documentation

- [x] 8.1 Update `README.md` to describe the three-target topology, the `MOCKSERVER_TARGETS` environment variable (and its `MOCKSERVER_URL` fallback), and the new `/public`/`/private` Ingress paths. Also updated `scripts/build-and-load-images.sh`, `scripts/install-mockserver.sh`, and `scripts/uninstall-mockserver.sh` (not separately tracked above) so the documented install/uninstall/build flow actually covers all three topologies, plus a Gotchas note about the `/public`/`/private` path prefix not being stripped before MockServer/backends see it.

## 9. Verification

- [x] 9.1 Run `mock-ui`'s test suite (`python3 -m pytest` or equivalent) and confirm it passes. 25/25 passed via `python3 -m unittest test_app`.
- [x] 9.2 Bring up the full POC on a local cluster; confirm all three topologies report Ready and each serves a sample request through its Ingress path. Verified on the existing local `kind` cluster: all pods Ready, `curl localhost:8080/booking/1`, `/public/items`, `/public/health`, `/private/accounts`, `/private/health` all returned the expected hardcoded/mocked responses.
- [ ] 9.3 In the browser, confirm the MockServer selector lists all three targets, switching targets re-scopes List Mocks and Recent Requests, and the selection survives a page reload via the URL. **Not verified in an actual browser** (none available in this environment) - verified instead that the served `index.html`/`app.js` contain the selector markup and target-switching logic, and that `GET /mock-ui/api/servers` (what the selector fetches) returns all three targets. Manual browser verification is still recommended before shipping.
- [x] 9.4 Confirm a mock created against one target is not visible when a different target is selected. Verified via the API directly: created a mock on `public`, confirmed it appeared in `?server=public` and was absent from `?server=private` and `?server=product`.
- [x] 9.5 Confirm restarting mock-ui with only `MOCKSERVER_URL` set (no `MOCKSERVER_TARGETS`) still starts and serves a single "Default" target. Verified by importing `app.py` with only `MOCKSERVER_URL` set: `TARGETS` resolves to a single `default`/`Default` target and `/mock-ui/api/servers` reflects it.
