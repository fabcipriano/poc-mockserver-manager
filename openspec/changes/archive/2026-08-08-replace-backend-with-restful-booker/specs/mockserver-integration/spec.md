## ADDED Requirements

### Requirement: Example mock expectations are provided for the restful-booker backend
The repository SHALL ship committed example MockServer expectation files in `mocks/` covering representative restful-booker routes - at minimum a read, a list, and a create - so a developer can see realistic mocking in action and use them as a starting point, without first having to author an expectation from scratch.

#### Scenario: Developer applies a committed example mock
- **WHEN** a developer runs `scripts/add-mock.sh` with one of the committed example files in `mocks/`
- **THEN** MockServer accepts the expectation and the corresponding restful-booker route (for example, `GET /booking/{id}`) returns the example's configured response instead of being forwarded to the Backend stand-in

#### Scenario: Example mocks cover more than one HTTP method
- **WHEN** a developer inspects the example files committed under `mocks/`
- **THEN** they find examples for at least a read (`GET`) route and a write (`POST` or similar) route against the restful-booker backend
