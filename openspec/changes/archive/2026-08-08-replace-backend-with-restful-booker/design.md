## Context

`backend/` is currently a Spring Boot 1.5 app built via a two-stage Dockerfile
(`maven:3.6-jdk-8` -> `eclipse-temurin:8-jre-alpine`), exposing one endpoint (`GET /api/hello`) on port
`8080`. The Gateway proxies everything unmodified to `BACKEND_URL` (default `http://backend:8080`, same
value set via the k8s Deployment's env var). The `backend` k8s Deployment/Service is named `backend`, port
`8080`, with a readiness probe against `GET /api/hello`.

The user chose (over pointing at the public `restful-booker.herokuapp.com`) to run
[restful-booker](https://github.com/mwinteringham/restful-booker) in-cluster, to preserve the POC's
self-contained, no-internet-dependency property at request time. Confirmed from its own source
(`Dockerfile`, `package.json`, `docker-compose.yml` on the upstream repo): it's a Node/Express app on port
`3001`, no external database - it uses an embedded, file-less `lokijs` store, seeded at startup via
`SEED=true` (already the default in its `npm start` script). No official prebuilt image exists on Docker
Hub; it must be built from its own source.

## Goals / Non-Goals

**Goals:**
- Keep the Backend component a single Deployment/Service named `backend`, reachable at
  `http://backend:<port>` from the Gateway - same "swap the image, not the topology" shape as today.
- Keep the cluster fully self-contained/offline-capable at request time - no dependency on
  `restful-booker.herokuapp.com` or any other host once the images are built.
- Build restful-booker from its own upstream source, pinned to a specific commit, for reproducibility,
  without vendoring/forking application code this repo doesn't own.

**Non-Goals:**
- Persistence/volumes for restful-booker's data - its in-memory store resetting on pod restart is
  acceptable for a POC (the old Spring Boot stand-in was equally stateless).
- Changes to the Gateway's proxy logic - only its target URL/port config changes.
- Changes to MockServer's catch-all forwarding target (`gateway`) or the install/uninstall scripts - the
  `ALB -> MockServer -> Gateway` hop is unaffected by what's behind the Gateway.
- A general "point at any external backend" toggle - out of scope here.

## Decisions

1. **Build restful-booker from a pinned upstream commit inside `backend/Dockerfile`**, rather than
   vendoring its source into this repo or building from a remote git URL directly in the build script.
   `backend/Dockerfile` becomes: `FROM node:22`, clone
   `https://github.com/mwinteringham/restful-booker.git` at a pinned commit SHA (`0046115...`, the current
   tip of upstream `main` as of this proposal), `npm install`, `EXPOSE 3001`, `CMD npm start`.
   - Alternative: `docker build <git-url>#<ref>` directly in `scripts/build-and-load-images.sh` with no
     local Dockerfile. Rejected - hides the pin in a shell script instead of a version-controlled
     Dockerfile, and diverges from the existing multi-stage-Dockerfile-per-component pattern this repo
     already uses for `backend/` and `gateway/`.
   - Alternative: vendor (submodule or copy) restful-booker's source into `backend/`. Rejected - turns
     this repo into an accidental fork to keep in sync; a pinned clone-at-build-time gets the same
     reproducibility without that burden.

2. **Keep the component named `backend` everywhere** (directory, Dockerfile, image tag
   `mockserver-poc/backend:local`, k8s Deployment/Service name, `BACKEND_URL` env var) rather than renaming
   to `restful-booker`. It plays the same topological role; renaming would ripple into the Gateway's env
   var, the k8s Service DNS name, the install/uninstall scripts' assumptions, and the README's component
   table for no behavioral benefit.

3. **Point the readiness probe at restful-booker's real health route, `GET /ping`** (returns `201`),
   instead of a route under `/booking` - it needs no seed data or auth, matching how a real health check
   would be wired.

4. **Change the `backend` Service/Deployment port from `8080` to `3001`** (restful-booker's actual listen
   port) and update `BACKEND_URL`'s default in both `gateway/server.js`'s fallback and the k8s Deployment
   env var to `http://backend:3001` - the Gateway's own proxy code is untouched, only the config it reads
   changes.

5. **New example mocks in `mocks/` cover three restful-booker routes**: `GET /booking/{id}` (read),
   `GET /booking` (list), `POST /booking` (create) - chosen to be varied and useful as copy-paste starting
   points. All three are usable via `scripts/add-mock.sh` unmodified, since it only matches on method+path
   (not request body), the same way `hello-mock.example.json` worked today.

## Risks / Trade-offs

- Pinned commit becomes unavailable if upstream history is rewritten -> Mitigation: pin by full commit
  SHA (not a branch), documented with the date it was pinned in a Dockerfile comment, so bumping it later
  is a one-line change.
- `node:22` base image drifts over time -> Mitigation: we don't build restful-booker's own Dockerfile
  as-is, we write our own minimal one against the pinned source, so upstream Dockerfile changes can't
  silently affect us - only an intentional commit bump can.
- restful-booker's in-memory store resets on every pod restart/reschedule -> Mitigation: same volatility
  class as today's stateless Spring Boot stand-in; call this out in the README's "Known gaps" so it isn't
  mistaken for a bug.
- `npm install` at image-build time needs internet access -> Mitigation: build-time-only dependency (same
  class as Maven pulling dependencies today, or `npm install` in `gateway/Dockerfile`), not a runtime one -
  the running cluster stays offline-capable.

## Migration Plan

This is a POC with no production deployment or persisted state to migrate. "Deploying" this change means
rebuilding images (`scripts/build-and-load-images.sh`) and re-applying manifests (`kubectl apply -k
k8s/base`). Rollback is reverting this change's commit(s) and re-running the same two commands to restore
the Spring Boot stand-in.
