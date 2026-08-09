# mock-management-ui Specification

## Purpose

Let a developer create, view, update, and delete MockServer mock expectations through a real-time web
interface instead of CLI scripts, demonstrating the kind of self-service mocking workflow a real
environment would offer, while always acting directly on MockServer's live state.

## Requirements

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

### Requirement: Web UI is organized around a left-hand navigation sidebar
The web interface SHALL present a persistent left-hand navigation sidebar with four destinations - Create Mock, List Mocks, Recent Requests, and Help - such that selecting a destination shows only that destination's content in the main content area.

#### Scenario: Developer switches between pages
- **WHEN** a developer selects a different destination in the sidebar
- **THEN** the main content area shows only that destination's page, and the content of the previously shown page is no longer visible

#### Scenario: A page is reachable by a direct link
- **WHEN** a developer loads or reloads the web interface with a specific destination referenced in the URL
- **THEN** that destination's page is shown, without requiring the developer to navigate there manually

### Requirement: Web UI shows recent requests received by MockServer
The web interface's Recent Requests page SHALL display MockServer's actual received-request history - timestamp, method, path, and response status code for each - sourced live from MockServer rather than a copy the web interface keeps itself, showing the most recent requests first.

#### Scenario: Developer views recent traffic
- **WHEN** a developer navigates to the Recent Requests page
- **THEN** they see the most recently received requests, each showing at least a timestamp, method, path, and response status code, most recent first

#### Scenario: Requests are shown regardless of whether they were mocked
- **WHEN** MockServer has received both a request that matched a developer-created mock and a request that was forwarded to the Gateway unmocked
- **THEN** both requests appear in the Recent Requests page

### Requirement: Web UI lets a developer filter recent requests by path
The web interface SHALL let a developer narrow the Recent Requests page to only requests whose path contains a given piece of text, without requiring the developer to write a regular expression.

#### Scenario: Developer filters by a path fragment
- **WHEN** a developer types a piece of text into the Recent Requests page's path filter
- **THEN** only requests whose path contains that text are shown, whether the text appears at the start, middle, or end of the path

#### Scenario: Clearing the filter shows all recent requests again
- **WHEN** a developer clears the path filter
- **THEN** the Recent Requests page shows recent requests for any path again

### Requirement: Web UI live-tails new requests in real time
The web interface's Recent Requests page SHALL show newly received requests matching the current path filter as they arrive, without the developer needing to manually refresh the page.

#### Scenario: A new matching request appears without a refresh
- **WHEN** a developer has the Recent Requests page open and a new request matching the current path filter is received by MockServer
- **THEN** that request appears at the top of the list without the developer reloading or refreshing the page

#### Scenario: A new non-matching request does not appear
- **WHEN** a developer has a path filter active on the Recent Requests page and a new request not matching that filter is received by MockServer
- **THEN** that request does not appear in the list while the filter remains active

#### Scenario: Changing the filter re-scopes the live tail
- **WHEN** a developer changes the path filter while the Recent Requests page is open
- **THEN** both the displayed history and subsequently arriving requests reflect the new filter

### Requirement: Web UI lets a developer pause and resume the live request tail
The web interface's Recent Requests page SHALL let a developer pause the live tail so newly arriving requests stop being added to the visible list, and resume it so they are added again without requests received during the pause being lost.

#### Scenario: Developer pauses the tail to read an entry
- **WHEN** a developer pauses the live tail and a new matching request is received by MockServer while paused
- **THEN** the visible list does not change while paused

#### Scenario: Resuming shows what arrived while paused
- **WHEN** a developer resumes a previously paused live tail
- **THEN** any matching requests received while paused are now shown

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
