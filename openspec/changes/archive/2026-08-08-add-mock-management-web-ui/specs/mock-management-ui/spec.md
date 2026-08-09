## Purpose

Let a developer create, view, update, and delete MockServer mock expectations through a real-time web
interface instead of CLI scripts, demonstrating the kind of self-service mocking workflow a real
environment would offer, while always acting directly on MockServer's live state.

## ADDED Requirements

### Requirement: Web UI lists currently active developer-created mocks
The web interface SHALL display every currently active MockServer expectation created through it or through the existing CLI scripts, showing at least method, path, and status code for each, and SHALL exclude the seeded catch-all forwarding expectation from this list.

#### Scenario: Developer views current mocks
- **WHEN** a developer opens the web interface
- **THEN** they see a list of every currently active, developer-created mock expectation (method, path, status code), with the seeded catch-all forwarding rule excluded from the list

### Requirement: Web UI creates a mock in real time
The web interface SHALL let a developer submit a new mock (method, path, status code, and a JSON response body) and SHALL make it active in MockServer immediately, with no separate deploy, sync, or refresh step.

#### Scenario: Developer creates a mock through the UI
- **WHEN** a developer submits a new mock (method, path, status code, response body) through the web interface
- **THEN** the expectation becomes active in MockServer immediately, and the corresponding route in the cluster returns the configured response on the very next request

### Requirement: Web UI updates an existing mock in place
The web interface SHALL let a developer edit one of their existing mocks and save the change, and SHALL update the same MockServer expectation in place rather than creating a duplicate.

#### Scenario: Developer edits a mock
- **WHEN** a developer edits one of their existing mocks through the web interface and saves it
- **THEN** the same expectation in MockServer is updated in place, the corresponding route immediately reflects the new response, and no duplicate expectation is created for that mock

### Requirement: Web UI deletes a mock and restores pass-through
The web interface SHALL let a developer delete one of their existing mocks, removing only that expectation from MockServer (by id) and immediately restoring pass-through forwarding for its route.

#### Scenario: Developer deletes a mock
- **WHEN** a developer deletes a mock through the web interface
- **THEN** the corresponding expectation is removed from MockServer, and the route immediately resumes passing through to the Gateway instead of returning the deleted mock's response

### Requirement: Web UI reflects MockServer's live state with no independent cache
The web interface SHALL NOT maintain its own copy or cache of mock definitions; every list, create, update, and delete action SHALL act directly and synchronously against MockServer's live expectation store.

#### Scenario: UI reflects a change made outside the UI
- **WHEN** a mock is added, changed, or removed by some means other than the web interface (for example, `scripts/add-mock.sh` or a direct MockServer API call)
- **THEN** the web interface's next list view reflects that change, because it queries MockServer directly rather than a local cache

### Requirement: Web UI never modifies the seeded catch-all expectation
The web interface SHALL NOT allow the seeded priority-0 catch-all forwarding expectation to be edited or deleted through any of its create, update, or delete actions.

#### Scenario: Catch-all is protected from UI actions
- **WHEN** a developer uses any create, update, or delete action in the web interface
- **THEN** the seeded catch-all forwarding expectation is unaffected and continues forwarding unmocked routes to the Gateway stand-in

### Requirement: Web UI is reachable through the single external entrypoint
The system SHALL expose the web interface through the same ALB stand-in Ingress used for all other traffic in this POC, at a documented path, rather than requiring a separate port-forward.

#### Scenario: Developer reaches the UI without port-forwarding
- **WHEN** a developer navigates to the web interface's documented path on the ALB stand-in's entrypoint
- **THEN** the web interface loads and can list, create, update, and delete mocks without the developer running `kubectl port-forward`
