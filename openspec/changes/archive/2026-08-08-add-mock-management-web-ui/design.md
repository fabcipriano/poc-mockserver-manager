## Context

Mock management today is CLI-only: `scripts/add-mock.sh` / `list-mocks.sh` / `delete-mock.sh` wrap raw
`curl`/`jq` calls against MockServer's REST control-plane API, reached via
`kubectl port-forward svc/mockserver -n mockserver-poc 1080:80`. Verified live against the running cluster
while researching this change:

- `PUT /mockserver/retrieve?type=ACTIVE_EXPECTATIONS` returns **every** active expectation, including the
  seeded priority-0 catch-all (`path: "/.*"`) - the `{"path": ".*"}` filter body `list-mocks.sh` sends does
  **not** exclude it, despite that script's comment claiming it does. Any UI listing must filter it out
  itself (by priority, not by asking MockServer to).
- `PUT /mockserver/expectation` **creates a new expectation on every call that omits `id`** - calling
  `add-mock.sh` twice for the same method+path produces two separate expectations, not one updated
  expectation. Including the existing `id` field in the PUT body is what makes MockServer replace it in
  place instead.
- Deletion must go through `PUT /mockserver/clear {"id": "..."}` (matcher-based clear on method+path also
  matches - and deletes - the catch-all, per the existing README Gotchas section).

See proposal.md - Why/What Changes for motivation and scope.

## Goals / Non-Goals

**Goals:**
- Every list/create/update/delete action acts directly and synchronously on MockServer's live expectation
  store - no cache, no separate database, no reconciliation delay.
- No NodeJS anywhere in this component.
- Reachable through the existing ALB stand-in Ingress, no new port-forward.
- The seeded catch-all is never editable or deletable through the UI.
- Follow the repo's existing pattern: one small component, its own directory, its own Dockerfile, its own
  k8s manifests - same shape as `gateway/` and `backend/`.

**Non-Goals:**
- Authentication/authorization - matches this POC's existing no-auth stance everywhere else (already a
  documented "Known gap"); out of scope here too.
- Editing MockServer's advanced expectation fields (custom headers, delay, callbacks, `times`/TTL) - the UI
  only exposes method, path, status code, and a JSON response body, matching the level of control
  `scripts/add-mock.sh` already offers.
- A persistence layer or history of past mocks - MockServer is the only source of truth, by design.
- Changing or wrapping the existing CLI scripts - they keep working exactly as before, independently of
  this UI.

## Decisions

1. **Backend: Python 3 with flask framework.**
   - Alternative considered: Go. Also a reasonable "not Node" choice, but this repo has no existing Go
     tooling, and a compiled-binary build step is more machinery than this small amount of logic needs.
   - Alternative considered: zero backend - static HTML/JS calling MockServer's API directly from the
     browser (Nginx only reverse-proxying for same-origin). Rejected: it would push the
     priority-10-convention and catch-all-protection logic into browser JS, and expose MockServer's raw
     expectation JSON shape to the frontend. A small backend is the one place that can enforce "never
     touch the catch-all" and translate to/from a friendlier shape - closer to how a real environment's
     admin service would be structured, which is what this change is explicitly meant to demonstrate.
   - `ThreadingHTTPServer` (still stdlib, zero dependencies) rather than the single-threaded default, so
     concurrent requests don't serialize behind each other.

2. **Friendly REST surface at `/mock-ui/api/mocks`** (`GET` list, `POST` create, `PUT /{id}` update,
   `DELETE /{id}` delete), translating `{method, path, statusCode, body}` to/from MockServer's
   `httpRequest`/`httpResponse` envelope, rather than exposing MockServer's expectation JSON to the
   frontend directly.
   - List filters out any expectation with `priority: 0` (the catch-all convention this repo already uses)
     before returning results - working around `retrieve`'s lack of real server-side filtering, confirmed
     above.
   - Create always POSTs without an `id` and sets `priority: 10`, matching `scripts/add-mock.sh`'s
     convention, so a UI-created mock always outranks the catch-all.
   - Update always includes the target's existing `id` (and `priority: 10`) in the PUT body, which
     confirmed replaces the expectation in place rather than stacking a duplicate.
   - Delete always calls `PUT /mockserver/clear {"id": "<id>"}` - never a method/path matcher - for the
     same reason `scripts/delete-mock.sh` does: matcher-based clears also sweep up the catch-all.

3. **New `mock-ui` Deployment/Service live under `k8s/overlays/with-mockserver/`, not `k8s/base/`** - the
   UI has nothing to manage when MockServer isn't installed. It's created and removed by the existing
   `scripts/install-mockserver.sh` / `scripts/uninstall-mockserver.sh` alongside MockServer itself; no new
   lifecycle scripts are needed. `uninstall-mockserver.sh` needs one addition: it deletes MockServer's
   resources by explicit name (not by reapplying the base overlay), so it must also explicitly delete the
   `mock-ui` Deployment/Service.

4. **Exposed through the existing ALB stand-in Ingress at a new `/mock-ui` path**, added to
   `k8s/overlays/with-mockserver/ingress-patch.yaml` alongside the existing `/` -> `mockserver` rule,
   rather than a separate port-forward or NodePort. ingress-nginx matches the most specific path
   regardless of declaration order, so `/mock-ui` and the catch-all `/` rule don't conflict; requests under
   `/mock-ui` go straight to the `mock-ui` Service and never pass through MockServer. The mock-ui app is
   itself prefix-aware (it serves its static assets and API under `/mock-ui/...`) so no `rewrite-target`
   annotation is needed, keeping the Ingress patch as simple as the existing one.

5. **Backend reaches MockServer via the in-cluster Service DNS name** (`http://mockserver` in the
   `mockserver-poc` namespace, configurable via a `MOCKSERVER_URL` env var defaulting to that) - the same
   internal-Service pattern the Gateway already uses for the Backend (`BACKEND_URL`).

## Risks / Trade-offs

- [The backend has no auth, so anything that can reach the ALB stand-in can create/delete mocks.] ->
  Mitigation: matches this POC's existing no-auth stance everywhere else; call it out again in the
  README's "Known gaps," same as the other hops.
- [Editing a mock through the UI rebuilds its full expectation from the simplified form, so a mock that
  has fields the form doesn't expose (e.g. custom headers, created by some other means) would lose them if
  edited here.] -> Mitigation: acceptable - every mock the UI itself creates only ever has the fields the
  form exposes, so this only affects mocks created outside the UI; documented as a known limitation rather
  than silently special-cased.
- [`retrieve` returning the catch-all means a bug in the priority filter would expose it as editable.] ->
  Mitigation: the backend is the single choke point that applies this filter (not something duplicated in
  the frontend), and the same choke point is what always forces `priority: 10` on writes, so even a
  missed-filter listing bug can't result in the catch-all being overwritten by a create/update call (it
  would just fail to match the intended route, not corrupt the catch-all).

## Migration Plan

Net-new component; nothing to migrate. Rollout is the existing `scripts/build-and-load-images.sh` (now
also building `mock-ui`) followed by `scripts/install-mockserver.sh`. Rollback is
`scripts/uninstall-mockserver.sh`, which will also remove the `mock-ui` resources once this change updates
it.
