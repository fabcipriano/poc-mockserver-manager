## MODIFIED Requirements

### Requirement: Web UI is organized around a left-hand navigation sidebar
The web interface SHALL present a persistent left-hand navigation sidebar with four destinations - Create Mock, List Mocks, Recent Requests, and Help - such that selecting a destination shows only that destination's content in the main content area.

#### Scenario: Developer switches between pages
- **WHEN** a developer selects a different destination in the sidebar
- **THEN** the main content area shows only that destination's page, and the content of the previously shown page is no longer visible

#### Scenario: A page is reachable by a direct link
- **WHEN** a developer loads or reloads the web interface with a specific destination referenced in the URL
- **THEN** that destination's page is shown, without requiring the developer to navigate there manually

## ADDED Requirements

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
