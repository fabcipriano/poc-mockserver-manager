## 1. Backend (mock-ui)

- [x] 1.1 Create `mock-ui/requirements.txt` pinning `Flask`, and `mock-ui/app.py`: a Flask app with a `MOCKSERVER_URL` env var (default `http://mockserver`)
- [x] 1.2 Implement `GET /mock-ui/api/mocks`: call `PUT {MOCKSERVER_URL}/mockserver/retrieve?type=ACTIVE_EXPECTATIONS`, filter out any expectation with `priority: 0`, map the rest to `{id, method, path, statusCode, body}` and return as JSON
- [x] 1.3 Implement `POST /mock-ui/api/mocks`: accept `{method, path, statusCode, body}`, build a MockServer expectation with `priority: 10` and no `id`, `PUT {MOCKSERVER_URL}/mockserver/expectation`, return the created record (including MockServer's generated id)
- [x] 1.4 Implement `PUT /mock-ui/api/mocks/{id}`: same as create but includes the existing `id` and `priority: 10` in the expectation body, so MockServer updates in place instead of creating a duplicate
- [x] 1.5 Implement `DELETE /mock-ui/api/mocks/{id}`: `PUT {MOCKSERVER_URL}/mockserver/clear` with body `{"id": "<id>"}` only (never a method/path matcher)
- [x] 1.6 Implement `GET /mock-ui/healthz` returning 200, for the k8s readiness probe
- [x] 1.7 Serve the static frontend assets (task group 2) as a Flask static folder under `/mock-ui/`
- [x] 1.8 Run the app with a production-suitable Flask server setup (e.g. `flask run --host=0.0.0.0` is fine for this POC's scale; note in a comment that a WSGI server would be the next step for real traffic) so concurrent requests don't serialize behind each other

## 2. Frontend (static, vanilla JS)

- [x] 2.1 Create `mock-ui/static/index.html`: a page with a table of current mocks and a create/edit form (method, path, status code, response body)
- [x] 2.2 Create `mock-ui/static/app.js`: fetch-based calls to `/mock-ui/api/mocks` for list/create/update/delete; re-fetch and re-render the list after every mutation; clicking a row's "Edit" loads it into the form for update instead of create
- [x] 2.3 Create `mock-ui/static/style.css`: minimal styling for the table and form (no framework/CDN dependency - inline or vendored only)

## 3. Container image

- [x] 3.1 Write `mock-ui/Dockerfile` (`python:3-slim` base), `pip install -r requirements.txt`, copying `app.py` and `static/`, `EXPOSE`ing the server's port, `CMD` running the Flask app

## 4. Kubernetes manifests

- [x] 4.1 Add `k8s/overlays/with-mockserver/mock-ui-deployment.yaml`: image `mockserver-poc/mock-ui:local`, env `MOCKSERVER_URL=http://mockserver`, readiness probe on `/mock-ui/healthz`
- [x] 4.2 Add `k8s/overlays/with-mockserver/mock-ui-service.yaml`
- [x] 4.3 Update `k8s/overlays/with-mockserver/kustomization.yaml` to include both new manifest files
- [x] 4.4 Update `k8s/overlays/with-mockserver/ingress-patch.yaml` to add a `/mock-ui` path rule routing to the `mock-ui` Service, alongside the existing `/` -> `mockserver` rule

## 5. Scripts

- [x] 5.1 Update `scripts/build-and-load-images.sh` to also `docker build` and `kind load` `mockserver-poc/mock-ui:local`
- [x] 5.2 Update `scripts/uninstall-mockserver.sh` to also `kubectl delete deployment/service mock-ui -n mockserver-poc --ignore-not-found`
- [x] 5.3 Update `scripts/install-mockserver.sh`'s final echo to mention the web UI's URL path (`/mock-ui`)

## 6. Documentation

- [x] 6.1 Add a "Managing mocks with the Web UI" section to `README.md`: URL path, and a short walkthrough of list/create/edit/delete
- [x] 6.2 Add a `mock-ui` row to `README.md`'s architecture table and repository layout section
- [x] 6.3 Add a bullet to `README.md`'s "Known gaps" noting the web UI has no authentication, same as the rest of this POC

## 7. Verification

- [x] 7.1 Build and load images, run `scripts/install-mockserver.sh`; confirm `curl http://localhost:8080/mock-ui/healthz` returns 200 and `GET http://localhost:8080/mock-ui/api/mocks` returns `[]` (or existing mocks) without the catch-all
- [x] 7.2 Create a mock via `POST /mock-ui/api/mocks`; confirm the target route immediately returns the mocked response
- [x] 7.3 Update that mock via `PUT /mock-ui/api/mocks/{id}`; confirm the route reflects the new response and `GET /mock-ui/api/mocks` still shows exactly one entry for it (no duplicate)
- [x] 7.4 Delete the mock via `DELETE /mock-ui/api/mocks/{id}`; confirm the route passes through again and the seeded catch-all is still active (unmocked routes still forward to the Gateway)
- [x] 7.5 Open `http://localhost:8080/mock-ui/` in a browser (or via `curl`) and repeat create/edit/delete through the actual UI form, not just the API, to confirm the frontend works end-to-end
- [x] 7.6 Run `scripts/uninstall-mockserver.sh`; confirm the `mock-ui` Deployment/Service are removed along with MockServer's
