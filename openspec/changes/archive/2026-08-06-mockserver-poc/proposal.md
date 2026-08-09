## Why

Developers currently have no way to mock a backend API response in this environment without coordinating a code change in the NodeJS Gateway or standing up a full backend change. This slows down frontend/integration testing and incident reproduction. We need a POC that proves a MockServer can be dropped into the existing `ALB -> NodeJS Gateway -> Spring Boot 1.5 Backend` request path, let a dev define a mock response for a specific route in minutes, and transparently pass every other request through to the real backend untouched.

## What Changes

- Stand up a self-contained Kubernetes environment that emulates the target production topology: an Ingress/LoadBalancer Service standing in for the ALB, a minimal NodeJS Gateway service, and a minimal Spring Boot 1.5.x Backend service, wired together the same way as production (`ALB -> Gateway -> Backend`).
- Introduce **MockServer** (mock-server.org, official Docker image) as a new hop inserted in front of the Gateway: `ALB -> MockServer -> Gateway -> Backend`. By default MockServer forwards every request unchanged to the Gateway; when a dev adds an expectation for a route, MockServer answers that route directly and still forwards everything else.
- Provide a low-friction way for a dev to author a mock expectation (JSON expectation file and/or MockServer's REST expectation API) without redeploying the Gateway or Backend, and without needing to understand MockServer internals beyond "path + method + response body/status."
- Package the MockServer deployment as Kubernetes manifests (Deployment/Service/ConfigMap, optionally a Helm chart) that can be installed into the emulated environment - and, following the same pattern, into the real environment - with a single install command, and removed just as easily to restore the direct `ALB -> Gateway` path.
- Document the transparent-proxy behavior/limits (headers, timeouts, TLS termination assumptions) discovered while building the POC.

## Capabilities

### New Capabilities
- `poc-environment`: The Kubernetes-based emulation of the production topology (ALB stand-in, NodeJS Gateway stand-in, Spring Boot 1.5 Backend stand-in) used as the baseline to prove the MockServer integration against.
- `mockserver-integration`: Deploying MockServer transparently in front of the Gateway, the default forward-to-backend behavior, and the workflow a developer uses to add/remove a mock expectation for a route.

### Modified Capabilities
(none - this is a new, standalone POC with no pre-existing specs)

## Impact

- **New code/config**: Kubernetes manifests (namespace, Deployments, Services, Ingress, ConfigMaps) for the emulated ALB, Gateway, Backend, and MockServer; a minimal NodeJS Gateway app; a minimal Spring Boot 1.5.x Backend app; sample MockServer expectation files; install/uninstall scripts (and/or a Helm chart) for the MockServer piece.
- **No production systems are touched** - this change only creates a local/POC Kubernetes environment (e.g., for kind/minikube) plus reusable manifests. Rolling MockServer into the real environment is a follow-up decision, informed by this POC.
- **Dependencies**: Docker images for MockServer (`mockserver/mockserver`), Node.js (Gateway), and a Spring Boot 1.5.x-compatible JDK/base image (Backend); a local Kubernetes cluster (kind/minikube) for running the POC; optionally Helm.
