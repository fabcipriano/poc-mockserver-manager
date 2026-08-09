## 1. Local cluster tooling

- [x] 1.1 Document prerequisites (kind or minikube, kubectl, Docker) and create a script to (re)create a local cluster with `ingress-nginx` enabled
- [x] 1.2 Create the `mockserver-poc` namespace manifest

## 2. Backend stand-in (Spring Boot 1.5.x)

- [x] 2.1 Scaffold a minimal Spring Boot 1.5.x app with one sample JSON REST endpoint (e.g. `GET /api/hello`)
- [x] 2.2 Add a Dockerfile pinned to a JDK 8-compatible base image and build the image
- [x] 2.3 Write the Backend Deployment + Service manifests (`kustomize base`)

## 3. Gateway stand-in (NodeJS)

- [x] 3.1 Scaffold a minimal Express (or similar) app that proxies requests to the Backend Service's in-cluster DNS name, preserving method/path/body
- [x] 3.2 Add a Dockerfile and build the image
- [x] 3.3 Write the Gateway Deployment + Service manifests (`kustomize base`)

## 4. ALB stand-in and base overlay

- [x] 4.1 Write the Ingress manifest routing the external entrypoint to the Gateway Service
- [x] 4.2 Assemble the `overlays/base` Kustomize overlay (namespace, backend, gateway, ingress) with no MockServer present
- [x] 4.3 Verify: apply `overlays/base` to a fresh cluster, confirm a sample request flows ALB stand-in -> Gateway -> Backend end-to-end

## 5. MockServer deployment

- [x] 5.1 Write the MockServer Deployment + Service manifest using the official `mockserver/mockserver` image
- [x] 5.2 Write the ConfigMap holding the JSON initializer file with the seeded catch-all forwarding expectation (priority 0, forwards to the Gateway Service DNS name) and mount it via `initializationJsonPath`
- [x] 5.3 Write the Ingress patch that repoints the backend from the Gateway Service to the MockServer Service
- [x] 5.4 Assemble the `overlays/with-mockserver` Kustomize overlay (base + MockServer resources + Ingress patch)
- [x] 5.5 Verify: apply `overlays/with-mockserver`, confirm the same sample request still flows end-to-end unchanged (pass-through proven) and the Gateway manifests/app code were not modified

## 6. Mock expectation authoring workflow

- [x] 6.1 Write a helper script (e.g. `scripts/add-mock.sh`) that wraps MockServer's `PUT /mockserver/expectation` REST API, taking method/path/status/body and applying the documented default priority (10)
- [x] 6.2 Add a `mocks/` directory with one example committed JSON expectation file, and document how committed files get picked up by the initializer on pod restart
- [x] 6.3 Write a helper/README snippet for listing and deleting active expectations (`PUT /mockserver/retrieve`, `PUT /mockserver/clear`)
- [x] 6.4 Verify: use the helper script to mock the sample route, confirm MockServer answers directly instead of forwarding; delete the expectation and confirm pass-through resumes

## 7. Rollback / uninstall

- [x] 7.1 Document and script the uninstall path: revert the Ingress backend to the Gateway Service and remove MockServer's resources
- [x] 7.2 Verify: after uninstall, the ALB stand-in routes directly to the Gateway again with no MockServer resources left in the cluster

## 8. Documentation

- [x] 8.1 Write a top-level README covering: architecture diagram (`ALB -> MockServer -> Gateway -> Backend`), install/uninstall commands, and the expectation-priority convention from design.md
- [x] 8.2 Write a short "add your first mock" walkthrough a dev can follow end-to-end in under 10 minutes
- [x] 8.3 Document the POC's known gaps (no real ALB/AWS semantics, no auth/mTLS between hops, Spring Boot 1.5 stand-in is minimal) so results aren't over-generalized to production
