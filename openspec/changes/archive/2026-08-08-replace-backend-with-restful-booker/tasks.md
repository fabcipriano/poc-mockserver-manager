## 1. Backend container

- [x] 1.1 Delete `backend/src`, `backend/pom.xml`, `backend/target`, and the existing Maven-based `backend/Dockerfile`
- [x] 1.2 Write a new `backend/Dockerfile` (`FROM node:22`) that clones `https://github.com/mwinteringham/restful-booker.git` at the pinned commit `00461155995c8636866bf51dc444f63033da44fb`, runs `npm install`, `EXPOSE 3001`, and `CMD npm start`; add a comment noting the pin date and how to bump it
- [x] 1.3 Build the image locally (`docker build -t mockserver-poc/backend:local backend/`) and confirm `GET /ping` returns `201` and `GET /booking/1` returns a JSON booking on a local container run

## 2. Kubernetes manifests

- [x] 2.1 Update `k8s/base/backend-deployment.yaml`: `containerPort` 8080 -> 3001, readiness probe path `/api/hello` -> `/ping` on port 3001
- [x] 2.2 Update `k8s/base/backend-service.yaml`: `port`/`targetPort` 8080 -> 3001
- [x] 2.3 Update `k8s/base/gateway-deployment.yaml`: `BACKEND_URL` env var `http://backend:8080` -> `http://backend:3001`
- [x] 2.4 Update `gateway/server.js`'s `BACKEND_URL` fallback default to `http://backend:3001`

## 3. Build script

- [x] 3.1 Confirm `scripts/build-and-load-images.sh` still works unmodified (it builds `backend/` by directory, no path/tag changes needed) - update its comments if they mention Spring Boot/Java

## 4. Example mocks

- [x] 4.1 Remove `mocks/hello-mock.example.json`
- [x] 4.2 Add `mocks/booking-get.example.json` - example response body for `GET /booking/{id}`
- [x] 4.3 Add `mocks/booking-list.example.json` - example response body for `GET /booking`
- [x] 4.4 Add `mocks/booking-create.example.json` - example response body for `POST /booking`

## 5. Documentation

- [x] 5.1 Update `README.md`'s architecture table: describe the Backend row as "restful-booker application (built from upstream source)" instead of "Spring Boot 1.5.x Backend"
- [x] 5.2 Update `README.md`'s quickstart and mock-adding curl examples to use restful-booker routes (e.g. `GET /ping`, `GET /booking/1`) instead of `/api/hello`
- [x] 5.3 Update `README.md`'s "Known gaps" section: replace the Spring Boot stand-in bullet with a note about restful-booker's in-memory store resetting on pod restart, and about the pinned-commit build

## 6. Verification

- [x] 6.1 Run `scripts/create-cluster.sh`, `scripts/build-and-load-images.sh`, `kubectl apply -k k8s/base`; confirm `curl http://localhost:8080/ping` and `curl http://localhost:8080/booking/1` succeed end-to-end through ALB stand-in -> Gateway -> Backend
- [x] 6.2 Run `scripts/install-mockserver.sh`; confirm unmocked restful-booker routes still pass through
- [x] 6.3 Use `scripts/add-mock.sh` with each new example file in `mocks/`; confirm each mocked route returns the example response and other routes keep passing through
- [x] 6.4 Run `scripts/uninstall-mockserver.sh`; confirm direct ALB -> Gateway -> Backend path is restored
