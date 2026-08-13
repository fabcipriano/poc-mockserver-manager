## MODIFIED Requirements

### Requirement: Emulated topology mirrors production request path
The system SHALL provide Kubernetes manifests that stand up three independent emulated topologies, mirroring production's three gateways (public, private, product), each wired in the same relative order as production so a single external request entering that topology's entrypoint reaches its backend only by passing through MockServer and, for the product topology, a Gateway stand-in:
- **product**: `ALB stand-in -> MockServer -> Gateway stand-in -> Backend stand-in`, where the Backend stand-in runs the real restful-booker application, unchanged from before this change.
- **public** and **private**: `ALB stand-in -> MockServer -> Backend stand-in`, each Backend stand-in being a small, purpose-built NodeJS service with no separate Gateway layer - a deliberate POC simplification of the two lower-traffic gateways, kept minimal since their purpose is to demonstrate the multi-target MockServer/UI behavior rather than to model a second real backend.

#### Scenario: Request traverses the full emulated path
- **WHEN** a client sends an HTTP request to the product topology's entrypoint for a route the restful-booker Backend stand-in serves
- **THEN** the request is received by MockServer, then the Gateway stand-in, then the Backend stand-in, and the Backend stand-in's response is returned to the client unchanged (or the mocked response is returned instead, if a matching expectation exists)

#### Scenario: Request traverses the emulated path for the public or private topology
- **WHEN** a client sends an HTTP request to the public or private topology's entrypoint for a route its Backend stand-in serves
- **THEN** the request is received by MockServer and then directly by that topology's Backend stand-in, and the Backend stand-in's response is returned to the client unchanged (or the mocked response is returned instead, if a matching expectation exists)

### Requirement: Backend stand-in runs the real restful-booker application
The product topology's Backend stand-in SHALL run the real, unmodified [restful-booker](https://github.com/mwinteringham/restful-booker) application, built from its own upstream source and deployed in-cluster, exposing its native REST API (JSON, multiple resource routes, auth) so response shape, status codes, and headers are representative of a real-world backend rather than a synthetic single-endpoint stand-in. This requirement applies only to the product topology; the public and private topologies' Backend stand-ins are covered by the "simplified NodeJS backends" requirement instead.

#### Scenario: Backend stand-in answers a real restful-booker route
- **WHEN** the Gateway stand-in forwards a request for a restful-booker route (for example, `GET /booking/{id}`) to the product topology's Backend stand-in
- **THEN** the Backend stand-in returns the same response shape, status code, and headers the real restful-booker application would return for that route

#### Scenario: Backend stand-in runs without an internet dependency
- **WHEN** the emulated environment is running with no outbound internet access from the cluster
- **THEN** the product topology's Backend stand-in continues to serve requests, because it is deployed in-cluster from a container image rather than proxying to an externally hosted instance

### Requirement: Environment installs and tears down with minimal steps
The system SHALL allow a developer to bring up all three emulated topologies (public, private, product) in a local Kubernetes cluster with a single documented command sequence, and tear them down completely with another.

#### Scenario: Fresh install on a local cluster
- **WHEN** a developer runs the documented install command(s) against an empty local Kubernetes cluster
- **THEN** every component of all three topologies reports Ready, and each topology's entrypoint successfully proxies a sample request end-to-end

#### Scenario: Full teardown
- **WHEN** a developer runs the documented uninstall command(s)
- **THEN** all resources created for all three emulated topologies are removed from the cluster

## ADDED Requirements

### Requirement: Public and private topologies use simplified NodeJS backends returning a hardcoded API
The public and private topologies' Backend stand-ins SHALL each be a small NodeJS service, distinct from each other and from the product topology's restful-booker backend, that answers at least one route with a fixed, hardcoded JSON response rather than proxying to or embedding a real upstream application.

#### Scenario: Public topology's backend answers with a hardcoded response
- **WHEN** a client sends a request for a route the public topology's Backend stand-in serves and no MockServer expectation matches it
- **THEN** the response is the backend's fixed, hardcoded JSON payload for that route

#### Scenario: Private topology's backend answers with a hardcoded response
- **WHEN** a client sends a request for a route the private topology's Backend stand-in serves and no MockServer expectation matches it
- **THEN** the response is the backend's fixed, hardcoded JSON payload for that route

#### Scenario: Public and private backends are independent services
- **WHEN** a developer inspects the public and private topologies' Backend stand-ins
- **THEN** they are two separately deployed NodeJS services, each answering only its own topology's requests, with no shared runtime state between them

### Requirement: All three topologies are reachable through the single POC entrypoint
The system SHALL expose all three topologies (public, private, product) through the same ALB stand-in Ingress used for mock-ui, each at its own documented path prefix, so a developer can exercise any of the three topologies without provisioning separate DNS names or Ingress resources per topology - a POC simplification of production, where the three gateways sit behind genuinely separate entrypoints.

#### Scenario: Developer reaches each topology through the shared entrypoint
- **WHEN** a developer sends a request to the public topology's documented path prefix, the private topology's documented path prefix, or the product topology's default path
- **THEN** the request is routed to that topology's MockServer instance and handled per the "Emulated topology mirrors production request path" requirement, without the developer needing a separate entrypoint per topology
