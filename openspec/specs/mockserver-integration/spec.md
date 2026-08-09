## Purpose

Let a developer transparently mock any API route in the emulated (and later real) environment by inserting MockServer in front of the Gateway, without modifying Gateway or Backend code or configuration.

## Requirements

### Requirement: MockServer is installed transparently in front of the Gateway
The system SHALL deploy MockServer into the Kubernetes environment such that it becomes the sole entry point the ALB stand-in routes to, sitting between the ALB stand-in and the Gateway stand-in (`ALB -> MockServer -> Gateway -> Backend`), with no changes required to the Gateway stand-in's own code or configuration.

#### Scenario: MockServer installed without touching the Gateway
- **WHEN** a developer installs MockServer into an already-running emulated environment using the documented install command(s)
- **THEN** the ALB stand-in's traffic now reaches MockServer first, the Gateway stand-in's deployment and configuration are unchanged, and no manual edits to the Gateway are required

### Requirement: Unmocked requests are forwarded to the Gateway by default
For any route with no matching expectation configured, MockServer SHALL forward the request unchanged (method, path, headers, body) to the Gateway stand-in and relay the Gateway's response back to the caller.

#### Scenario: Request for an unmocked route passes through end-to-end
- **WHEN** a client sends a request for a route that has no MockServer expectation defined
- **THEN** the request reaches the Backend stand-in via the Gateway stand-in, and the caller receives the same response they would have received if MockServer were not installed

### Requirement: Developer can add a mock expectation without redeploying Gateway or Backend
The system SHALL let a developer define a mock response for a specific route (method + path) by submitting an expectation to MockServer (via a JSON expectation file and/or MockServer's REST expectation API), without rebuilding, redeploying, or reconfiguring the Gateway or Backend.

#### Scenario: Developer adds a mock expectation
- **WHEN** a developer submits an expectation for a given method and path, specifying a response status, headers, and body
- **THEN** MockServer accepts the expectation and it becomes active without any Gateway or Backend deployment change

#### Scenario: Mocked route returns the configured response
- **WHEN** a client sends a request matching an active expectation's method and path
- **THEN** MockServer returns the expectation's configured status, headers, and body directly, and the request is not forwarded to the Gateway or Backend

### Requirement: Mock expectations are removable and inspectable
The system SHALL let a developer list currently active expectations and remove (or reset) one or all of them, immediately restoring pass-through forwarding for the affected route(s).

#### Scenario: Developer removes a mock expectation
- **WHEN** a developer deletes a previously added expectation for a route
- **THEN** subsequent requests for that route are forwarded to the Gateway stand-in instead of receiving the mocked response

### Requirement: MockServer can be uninstalled to restore the direct path
The system SHALL allow a developer to remove MockServer from the environment with a single documented command sequence, after which the ALB stand-in routes directly to the Gateway stand-in as it did before MockServer was installed.

#### Scenario: MockServer uninstalled
- **WHEN** a developer runs the documented MockServer uninstall command(s)
- **THEN** MockServer's resources are removed from the cluster and the ALB stand-in's entrypoint routes directly to the Gateway stand-in again

### Requirement: Example mock expectations are provided for the restful-booker backend
The repository SHALL ship committed example MockServer expectation files in `mocks/` covering representative restful-booker routes - at minimum a read, a list, and a create - so a developer can see realistic mocking in action and use them as a starting point, without first having to author an expectation from scratch.

#### Scenario: Developer applies a committed example mock
- **WHEN** a developer runs `scripts/add-mock.sh` with one of the committed example files in `mocks/`
- **THEN** MockServer accepts the expectation and the corresponding restful-booker route (for example, `GET /booking/{id}`) returns the example's configured response instead of being forwarded to the Backend stand-in

#### Scenario: Example mocks cover more than one HTTP method
- **WHEN** a developer inspects the example files committed under `mocks/`
- **THEN** they find examples for at least a read (`GET`) route and a write (`POST` or similar) route against the restful-booker backend

### Requirement: Mock expectations persist across MockServer restarts
Mock expectations - both the seeded catch-all forwarding rule and any mock a developer has added - SHALL survive a restart or rescheduling of the MockServer pod, without requiring a developer to re-add anything.

#### Scenario: Dev-added mock survives a MockServer pod restart
- **WHEN** a developer has added a mock expectation and the MockServer pod is then restarted or rescheduled
- **THEN** after the pod becomes ready again, the same mock expectation is active without the developer re-adding it

#### Scenario: Catch-all is present after a restart on a brand-new volume
- **WHEN** MockServer is installed for the first time, before any developer has added a mock
- **THEN** the seeded catch-all forwarding rule is active, exactly as it is today

#### Scenario: Persisted mocks outlive an uninstall/reinstall cycle
- **WHEN** a developer runs the documented MockServer uninstall command(s) and then reinstalls MockServer
- **THEN** mock expectations that were active before the uninstall are active again after the reinstall, without being re-added
