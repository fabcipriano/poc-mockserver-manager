## Why

The Spring Boot 1.5 backend stand-in exists only to have *something* behind the Gateway - it has one
hand-written endpoint and no real business behavior, so it can't demonstrate much about mocking beyond
"a single JSON route can be intercepted." Swapping it for [restful-booker](https://restful-booker.herokuapp.com/),
a real, widely-used demo REST API (auth, CRUD on a resource, XML/JSON content negotiation, mixed status
codes), gives the POC realistic, varied routes to mock and makes it a much more convincing demo of what
MockServer can do - without maintaining a bespoke Java app just to have traffic to point at.

## What Changes

- **BREAKING**: Remove the Spring Boot 1.5 backend stand-in entirely (`backend/src`, `backend/pom.xml`,
  the Maven-based `backend/Dockerfile`).
- Replace it with a container that runs the real, unmodified [restful-booker](https://github.com/mwinteringham/restful-booker)
  application (built from its own upstream source, pinned to a specific commit), deployed in-cluster as
  the new `backend` Deployment/Service - so the POC's "self-contained, no internet dependency" property is
  preserved (this was an explicit choice over pointing at the public `restful-booker.herokuapp.com`
  instance, which would require cluster egress and share mutable state with every other user of that
  instance).
- Update the Gateway's `BACKEND_URL` (default and k8s env var) and the `backend` Service/Deployment
  port/readiness probe to match restful-booker's port (`3001`) and health route (`GET /ping`). No change
  to the Gateway's own code - it keeps proxying everything unmodified, per the existing "Gateway is never
  modified to enable/disable mocking" invariant.
- Remove `mocks/hello-mock.example.json` (mocks a route, `/api/hello`, that no longer exists) and add new
  committed example MockServer expectations for representative restful-booker routes (a read, a list, and
  a create) so `scripts/add-mock.sh` has real, varied examples to demo.
- Update `scripts/build-and-load-images.sh` and `README.md` (architecture table, quickstart curl commands,
  "Known gaps") to describe restful-booker instead of the Spring Boot stand-in.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `poc-environment`: the Backend stand-in requirement changes from "a Spring Boot 1.5.x app" to "the real
  restful-booker application"; the topology requirement's description of the Backend stand-in is updated
  to match.
- `mockserver-integration`: adds a requirement that the repo ships example mock expectations covering
  representative restful-booker routes.

## Impact

- Code: `backend/` (full replacement of Dockerfile/source), `gateway/server.js` (default URL fallback
  only), `k8s/base/backend-deployment.yaml`, `k8s/base/backend-service.yaml`,
  `k8s/base/gateway-deployment.yaml` (env var), `scripts/build-and-load-images.sh`, `mocks/`, `README.md`.
- Dependencies: drops Maven/JDK 8 as a build-time dependency for `backend/`; adds a build-time dependency
  on cloning a pinned commit of `github.com/mwinteringham/restful-booker` (Node.js app, no external DB -
  it uses an embedded, in-memory store that resets on pod restart).
- No change to `gateway/`'s proxying logic, `k8s/overlays/with-mockserver/` (MockServer still forwards
  the catch-all to the `gateway` Service unchanged), or the install/uninstall scripts.
