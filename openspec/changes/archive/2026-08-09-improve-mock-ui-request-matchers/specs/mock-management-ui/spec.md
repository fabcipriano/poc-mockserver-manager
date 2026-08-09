## MODIFIED Requirements

### Requirement: Web UI creates a mock in real time
The web interface SHALL let a developer submit a new mock - method, path, status code, and a response body are required; path parameters, query string parameters, headers, cookies, and a JSON request body matcher are optional - and SHALL make it active in MockServer immediately, with no separate deploy, sync, or refresh step.

#### Scenario: Developer creates a mock through the UI
- **WHEN** a developer submits a new mock (method, path, status code, response body) through the web interface
- **THEN** the expectation becomes active in MockServer immediately, and the corresponding route in the cluster returns the configured response on the very next request

#### Scenario: Developer creates a mock with additional request matchers
- **WHEN** a developer submits a new mock that also specifies any combination of path parameters, query string parameters, headers, cookies, or a JSON request body matcher
- **THEN** the resulting MockServer expectation only matches requests satisfying all of the specified matchers, and a request that doesn't satisfy them is not matched by this mock

### Requirement: Web UI updates an existing mock in place
The web interface SHALL let a developer edit one of their existing mocks - including any request matchers it has - and save the change, and SHALL update the same MockServer expectation in place rather than creating a duplicate.

#### Scenario: Developer edits a mock
- **WHEN** a developer edits one of their existing mocks through the web interface and saves it
- **THEN** the same expectation in MockServer is updated in place, the corresponding route immediately reflects the new response, and no duplicate expectation is created for that mock

#### Scenario: Developer edits a mock's request matchers
- **WHEN** a developer opens an existing mock that has path parameters, query string parameters, headers, cookies, or a request body matcher configured
- **THEN** the edit form is pre-filled with those matchers, and saving without changing them keeps the same matching behavior

## ADDED Requirements

### Requirement: Web UI distinguishes the request body matcher from the response body
The web interface SHALL present the request body matcher and the response body as two separate, clearly-labeled fields, so a developer cannot mistake one for the other.

#### Scenario: Request body matcher and response body are edited independently
- **WHEN** a developer sets a request body matcher and a response body on the same mock
- **THEN** the request body matcher constrains which incoming requests match the mock, and the response body is what's returned when a request matches, independently of each other

### Requirement: Web UI matches requests by path parameters
The web interface SHALL let a developer constrain a mock to specific path parameter values when the path contains named segments (for example, `/booking/{id}`).

#### Scenario: Developer matches a specific path parameter value
- **WHEN** a developer creates a mock with path `/booking/{id}` and a path parameter constraint `id=123`
- **THEN** a request to `/booking/123` matches the mock, and a request to `/booking/456` does not

### Requirement: Web UI matches requests by query string parameters
The web interface SHALL let a developer constrain a mock to one or more query string parameter name/value pairs.

#### Scenario: Developer matches a query string parameter
- **WHEN** a developer creates a mock with a query string parameter constraint `active=true`
- **THEN** a request including `?active=true` matches the mock, and a request without that query parameter (or with a different value) does not

### Requirement: Web UI matches requests by headers
The web interface SHALL let a developer constrain a mock to one or more request header name/value pairs.

#### Scenario: Developer matches a request header
- **WHEN** a developer creates a mock with a header constraint `X-Test: yes`
- **THEN** a request including that header matches the mock, and a request without it does not

### Requirement: Web UI matches requests by cookies
The web interface SHALL let a developer constrain a mock to one or more cookie name/value pairs.

#### Scenario: Developer matches a request cookie
- **WHEN** a developer creates a mock with a cookie constraint `session=abc`
- **THEN** a request including that cookie matches the mock, and a request without it does not

### Requirement: Web UI matches requests by a JSON request body
The web interface SHALL let a developer constrain a mock to requests whose JSON body matches a specified JSON value, either requiring an exact match or allowing the actual request body to contain additional fields beyond the ones specified.

#### Scenario: Developer matches requests containing at least the specified JSON fields
- **WHEN** a developer creates a mock with a JSON request body matcher `{"firstname": "Ada"}` using the partial-match mode
- **THEN** a request whose JSON body includes `"firstname": "Ada"` plus other fields matches the mock

#### Scenario: Developer requires an exact JSON body match
- **WHEN** a developer creates a mock with a JSON request body matcher `{"firstname": "Ada"}` using the exact-match mode
- **THEN** a request whose JSON body is exactly `{"firstname": "Ada"}` matches the mock, and a request with additional fields does not

### Requirement: Request matchers stay optional and out of the way for the common case
The web interface SHALL keep path parameters, query string parameters, headers, cookies, and the request body matcher visually secondary to method, path, status code, and response body, so creating a mock that only needs method and path is no more complex than before these matchers existed.

#### Scenario: Creating a simple mock doesn't require touching matcher fields
- **WHEN** a developer creates a mock specifying only method, path, status code, and response body
- **THEN** they are not required to open, fill in, or dismiss any path parameter, query string parameter, header, cookie, or request body matcher field to do so

#### Scenario: Matchers are visible when editing a mock that has them
- **WHEN** a developer opens an existing mock that has one or more request matchers configured
- **THEN** the section containing those matchers is already expanded, so the developer sees the mock's full matching behavior without an extra click

### Requirement: Active mocks list indicates additional request matchers
The web interface's list of active mocks SHALL indicate when a mock has request matchers beyond method and path, without displaying full matcher detail inline for every mock.

#### Scenario: A mock with extra matchers is visually distinguished from one without
- **WHEN** a developer views the active mocks list and it contains both a mock matching only on method and path, and a mock additionally matching on a header
- **THEN** the mock with the additional header matcher is visibly indicated as having extra matchers, and the mock matching only on method and path is not
