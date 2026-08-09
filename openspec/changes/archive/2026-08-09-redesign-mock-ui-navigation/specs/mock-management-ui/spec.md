## MODIFIED Requirements

### Requirement: Web UI lists currently active developer-created mocks
The web interface's List Mocks page SHALL display every currently active MockServer expectation created through it or through the existing CLI scripts, showing at least method, path, and status code for each, and SHALL exclude the seeded catch-all forwarding expectation from this list.

#### Scenario: Developer views current mocks
- **WHEN** a developer navigates to the List Mocks page
- **THEN** they see a list of every currently active, developer-created mock expectation (method, path, status code), with the seeded catch-all forwarding rule excluded from the list

### Requirement: Web UI creates a mock in real time
The web interface's Create Mock page SHALL let a developer submit a new mock - method, path, status code, and a response body are required; path parameters, query string parameters, headers, cookies, and a JSON request body matcher are optional - and SHALL make it active in MockServer immediately, with no separate deploy, sync, or refresh step.

#### Scenario: Developer creates a mock through the UI
- **WHEN** a developer submits a new mock (method, path, status code, response body) through the Create Mock page
- **THEN** the expectation becomes active in MockServer immediately, and the corresponding route in the cluster returns the configured response on the very next request

#### Scenario: Developer creates a mock with additional request matchers
- **WHEN** a developer submits a new mock that also specifies any combination of path parameters, query string parameters, headers, cookies, or a JSON request body matcher
- **THEN** the resulting MockServer expectation only matches requests satisfying all of the specified matchers, and a request that doesn't satisfy them is not matched by this mock

#### Scenario: Developer sees confirmation after creating a mock
- **WHEN** a developer successfully creates a mock
- **THEN** the web interface navigates to the List Mocks page and shows a visible confirmation that the mock was created

### Requirement: Web UI updates an existing mock in place
The web interface SHALL let a developer edit one of their existing mocks - including any request matchers it has - from the Create Mock page (relabeled for editing) and save the change, and SHALL update the same MockServer expectation in place rather than creating a duplicate.

#### Scenario: Developer edits a mock
- **WHEN** a developer edits one of their existing mocks and saves it
- **THEN** the same expectation in MockServer is updated in place, the corresponding route immediately reflects the new response, and no duplicate expectation is created for that mock

#### Scenario: Developer edits a mock's request matchers
- **WHEN** a developer opens an existing mock that has path parameters, query string parameters, headers, cookies, or a request body matcher configured
- **THEN** the edit form is pre-filled with those matchers, and saving without changing them keeps the same matching behavior

#### Scenario: Developer sees confirmation after saving an edit
- **WHEN** a developer successfully saves changes to an existing mock
- **THEN** the web interface navigates to the List Mocks page and shows a visible confirmation that the mock was updated

### Requirement: Web UI deletes a mock and restores pass-through
The web interface SHALL let a developer delete one of their existing mocks after confirming the action, removing only that expectation from MockServer (by id) and immediately restoring pass-through forwarding for its route.

#### Scenario: Developer deletes a mock
- **WHEN** a developer confirms deleting a mock through the web interface
- **THEN** the corresponding expectation is removed from MockServer, and the route immediately resumes passing through to the Gateway instead of returning the deleted mock's response

#### Scenario: Developer is asked to confirm before a mock is deleted
- **WHEN** a developer clicks delete on a mock but does not confirm the action
- **THEN** the mock's expectation remains active and unchanged in MockServer

## ADDED Requirements

### Requirement: Web UI is organized around a left-hand navigation sidebar
The web interface SHALL present a persistent left-hand navigation sidebar with three destinations - Create Mock, List Mocks, and Help - such that selecting a destination shows only that destination's content in the main content area.

#### Scenario: Developer switches between pages
- **WHEN** a developer selects a different destination in the sidebar
- **THEN** the main content area shows only that destination's page, and the content of the previously shown page is no longer visible

#### Scenario: A page is reachable by a direct link
- **WHEN** a developer loads or reloads the web interface with a specific destination referenced in the URL
- **THEN** that destination's page is shown, without requiring the developer to navigate there manually

### Requirement: Web UI highlights the currently active navigation destination
The web interface SHALL visually distinguish the sidebar destination corresponding to the currently displayed page from the other destinations.

#### Scenario: Active destination is visually distinct
- **WHEN** a developer is viewing one of the three pages
- **THEN** that page's entry in the sidebar is visually distinguished from the other two entries

### Requirement: Web UI provides a Help page documenting request matchers
The web interface's Help page SHALL explain, for a developer unfamiliar with the tool, what each supported request matcher (path parameters, query string parameters, headers, cookies, request body) does and how to use it, and SHALL state that the seeded catch-all forwarding expectation can never be edited or deleted through the web interface.

#### Scenario: Developer learns how a matcher works from the Help page
- **WHEN** a developer navigates to the Help page
- **THEN** they find an explanation of what path parameters, query string parameters, headers, cookies, and the request body matcher each do
