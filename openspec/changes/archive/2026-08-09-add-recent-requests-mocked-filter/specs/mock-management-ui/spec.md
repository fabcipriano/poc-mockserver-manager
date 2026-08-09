## MODIFIED Requirements

### Requirement: Web UI shows recent requests received by MockServer
The web interface's Recent Requests page SHALL display MockServer's actual received-request history - timestamp, method, path, response status code, and whether MockServer answered the request from a developer-created mock or forwarded it to the Gateway/backend - sourced live from MockServer rather than a copy the web interface keeps itself, showing the most recent requests first.

#### Scenario: Developer views recent traffic
- **WHEN** a developer navigates to the Recent Requests page
- **THEN** they see the most recently received requests, each showing at least a timestamp, method, path, response status code, and whether it was mocked or forwarded, most recent first

#### Scenario: Requests are shown regardless of whether they were mocked
- **WHEN** MockServer has received both a request that matched a developer-created mock and a request that was forwarded to the Gateway unmocked
- **THEN** both requests appear in the Recent Requests page, each labeled with its own mocked-or-forwarded status

### Requirement: Web UI lets a developer filter recent requests by path
The web interface SHALL let a developer narrow the Recent Requests page to only requests whose path contains a given piece of text, without requiring the developer to write a regular expression, and independently narrow it to only mocked requests or only forwarded requests.

#### Scenario: Developer filters by a path fragment
- **WHEN** a developer types a piece of text into the Recent Requests page's path filter
- **THEN** only requests whose path contains that text are shown, whether the text appears at the start, middle, or end of the path

#### Scenario: Clearing the filter shows all recent requests again
- **WHEN** a developer clears the path filter
- **THEN** the Recent Requests page shows recent requests for any path again

#### Scenario: Developer filters to only mocked requests
- **WHEN** a developer sets the Recent Requests page's status filter to mocked only
- **THEN** only requests MockServer answered from a developer-created mock are shown, and forwarded requests are hidden

#### Scenario: Developer filters to only forwarded requests
- **WHEN** a developer sets the Recent Requests page's status filter to forwarded only
- **THEN** only requests MockServer forwarded to the Gateway/backend are shown, and mocked requests are hidden

#### Scenario: The path filter and the mocked/forwarded filter combine
- **WHEN** a developer has both a path filter and a mocked-or-forwarded filter active
- **THEN** only requests satisfying both filters are shown

### Requirement: Web UI live-tails new requests in real time
The web interface's Recent Requests page SHALL show newly received requests matching the current path filter and mocked/forwarded filter as they arrive, without the developer needing to manually refresh the page.

#### Scenario: A new matching request appears without a refresh
- **WHEN** a developer has the Recent Requests page open and a new request matching the current filters is received by MockServer
- **THEN** that request appears at the top of the list without the developer reloading or refreshing the page

#### Scenario: A new non-matching request does not appear
- **WHEN** a developer has a path filter or a mocked/forwarded filter active on the Recent Requests page and a new request not matching that filter is received by MockServer
- **THEN** that request does not appear in the list while the filter remains active

#### Scenario: Changing the filter re-scopes the live tail
- **WHEN** a developer changes the path filter or the mocked/forwarded filter while the Recent Requests page is open
- **THEN** both the displayed history and subsequently arriving requests reflect the new filters
