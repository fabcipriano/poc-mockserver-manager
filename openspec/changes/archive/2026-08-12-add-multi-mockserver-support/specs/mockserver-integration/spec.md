## MODIFIED Requirements

### Requirement: MockServer is installed transparently in front of its configured upstream
The system SHALL deploy one or more MockServer instances into the Kubernetes environment such that each instance becomes the sole entry point the ALB stand-in routes to for its portion of traffic, sitting between the ALB stand-in and that instance's configured upstream (either a Gateway stand-in, as in `ALB -> MockServer -> Gateway -> Backend`, or a Backend stand-in directly, as in `ALB -> MockServer -> Backend`), with no changes required to that upstream's own code or configuration.

#### Scenario: MockServer installed without touching its upstream
- **WHEN** a developer installs a MockServer instance into an already-running emulated environment using the documented install command(s)
- **THEN** the ALB stand-in's traffic for that instance's path now reaches MockServer first, that instance's configured upstream's deployment and configuration are unchanged, and no manual edits to the upstream are required

#### Scenario: Different instances have different upstream shapes
- **WHEN** a developer inspects two different MockServer instances, one configured with a Gateway stand-in as its upstream and one configured with a Backend stand-in directly as its upstream
- **THEN** each instance forwards unmocked requests to its own configured upstream, and neither instance's configuration depends on what kind of upstream another instance has

### Requirement: Unmocked requests are forwarded to the configured upstream by default
For any route with no matching expectation configured, a MockServer instance SHALL forward the request unchanged (method, path, headers, body) to its configured upstream and relay that upstream's response back to the caller.

#### Scenario: Request for an unmocked route passes through end-to-end
- **WHEN** a client sends a request for a route that has no MockServer expectation defined on the instance handling that route
- **THEN** the request reaches that instance's configured upstream, and the caller receives the same response they would have received if MockServer were not installed

## ADDED Requirements

### Requirement: System supports multiple independently configured MockServer instances
The system SHALL support running more than one MockServer instance at a time, each installed, forwarding, and persisting its own expectations independently of the others, and each addressable by a stable identifier that a client (such as mock-ui) can use to select which instance it is talking to.

#### Scenario: Instances operate independently
- **WHEN** a developer adds, updates, or removes a mock expectation on one MockServer instance
- **THEN** the other configured MockServer instances' expectations are unaffected

#### Scenario: An instance is addressable by a stable identifier
- **WHEN** a client needs to direct a request at a specific MockServer instance
- **THEN** it can do so using that instance's identifier, without needing to know implementation details like its internal network address
