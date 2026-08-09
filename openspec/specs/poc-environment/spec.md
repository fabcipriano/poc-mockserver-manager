## Purpose

Provide a self-contained Kubernetes environment that emulates the production request path (ALB -> NodeJS Gateway -> Spring Boot Backend) so the MockServer integration can be proven and demoed without touching real infrastructure.

## Requirements

### Requirement: Emulated topology mirrors production request path
The system SHALL provide Kubernetes manifests that stand up three components wired in the same order as production: an ALB stand-in, a NodeJS Gateway stand-in, and a Backend stand-in running the real restful-booker application, such that a single external request entering the ALB stand-in reaches the Backend stand-in only by passing through the Gateway stand-in.

#### Scenario: Request traverses the full emulated path
- **WHEN** a client sends an HTTP request to the ALB stand-in's external entrypoint for a route the Backend stand-in serves
- **THEN** the request is received by the Gateway stand-in and then by the Backend stand-in, and the Backend stand-in's response is returned to the client unchanged

### Requirement: Backend stand-in runs the real restful-booker application
The Backend stand-in SHALL run the real, unmodified [restful-booker](https://github.com/mwinteringham/restful-booker) application, built from its own upstream source and deployed in-cluster, exposing its native REST API (JSON, multiple resource routes, auth) so response shape, status codes, and headers are representative of a real-world backend rather than a synthetic single-endpoint stand-in.

#### Scenario: Backend stand-in answers a real restful-booker route
- **WHEN** the Gateway stand-in forwards a request for a restful-booker route (for example, `GET /booking/{id}`) to the Backend stand-in
- **THEN** the Backend stand-in returns the same response shape, status code, and headers the real restful-booker application would return for that route

#### Scenario: Backend stand-in runs without an internet dependency
- **WHEN** the emulated environment is running with no outbound internet access from the cluster
- **THEN** the Backend stand-in continues to serve requests, because it is deployed in-cluster from a container image rather than proxying to an externally hosted instance

### Requirement: Gateway stand-in forwards requests without altering them
The Gateway stand-in SHALL forward incoming requests to the Backend stand-in's Kubernetes Service address, preserving method, path, and body, without requiring route-specific configuration for the sample endpoints.

#### Scenario: Gateway stand-in passes a request through unchanged
- **WHEN** the Gateway stand-in receives a request for a route it is configured to proxy
- **THEN** it forwards the same method, path, and body to the Backend stand-in and relays the Backend stand-in's response back to the caller

### Requirement: Environment installs and tears down with minimal steps
The system SHALL allow a developer to bring up the full emulated environment (ALB stand-in, Gateway stand-in, Backend stand-in) in a local Kubernetes cluster with a single documented command sequence, and tear it down completely with another.

#### Scenario: Fresh install on a local cluster
- **WHEN** a developer runs the documented install command(s) against an empty local Kubernetes cluster
- **THEN** all three components report Ready and the ALB stand-in's entrypoint successfully proxies a sample request end-to-end

#### Scenario: Full teardown
- **WHEN** a developer runs the documented uninstall command(s)
- **THEN** all resources created for the emulated environment are removed from the cluster
