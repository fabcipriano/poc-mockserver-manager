## MODIFIED Requirements

### Requirement: Web UI lets a developer filter recent requests by path
The web interface SHALL let a developer narrow the Recent Requests page to only requests whose path contains a given piece of text, without requiring the developer to write a regular expression; independently narrow it to only mocked requests or only forwarded requests; and independently narrow it to requests received within a given time range. All active filters SHALL combine.

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

#### Scenario: Developer filters by a time range
- **WHEN** a developer sets a "from" and/or "to" time on the Recent Requests page
- **THEN** only requests received within that time range are shown, combined with any other active filters

#### Scenario: A time range predating MockServer's retained history is communicated, not silently incomplete
- **WHEN** a developer sets a "from" time earlier than the oldest request MockServer currently retains
- **THEN** the page shows requests from the oldest retained entry onward and indicates that earlier requests are no longer available, rather than implying the range was fully searched

#### Scenario: The time range filter does not scope the live tail
- **WHEN** a developer has a "to" time in the past set on the Recent Requests page
- **THEN** newly arriving requests still appear via the live tail as they are received, since the live tail reflects requests happening now rather than the historical range being browsed

### Requirement: Web UI live-tails new requests in real time
The web interface's Recent Requests page SHALL show newly received requests matching the current path filter and mocked/forwarded filter as they arrive, without the developer needing to manually refresh the page, and SHALL do so without a per-viewer cost that scales with the number of developers viewing the page at once.

#### Scenario: A new matching request appears without a refresh
- **WHEN** a developer has the Recent Requests page open and a new request matching the current filters is received by MockServer
- **THEN** that request appears at the top of the list without the developer reloading or refreshing the page

#### Scenario: A new non-matching request does not appear
- **WHEN** a developer has a path filter or a mocked/forwarded filter active on the Recent Requests page and a new request not matching that filter is received by MockServer
- **THEN** that request does not appear in the list while the filter remains active

#### Scenario: Changing the filter re-scopes the live tail
- **WHEN** a developer changes the path filter or the mocked/forwarded filter while the Recent Requests page is open
- **THEN** both the displayed history and subsequently arriving requests reflect the new filters

## ADDED Requirements

### Requirement: Web UI paginates recent request history
The web interface's Recent Requests page SHALL let a developer load additional, older requests beyond the initially displayed set, in fixed pages of at most 100 requests, respecting any active filters, and SHALL indicate when no further, older requests are available.

#### Scenario: Developer loads the next page of history
- **WHEN** a developer asks the Recent Requests page to load older requests
- **THEN** up to 100 additional, older requests matching the active filters are appended to the list

#### Scenario: Loading more respects active filters
- **WHEN** a developer has a path filter, a mocked/forwarded filter, or a time range filter active and loads older requests
- **THEN** the additional requests loaded also satisfy all of those active filters

#### Scenario: Reaching the oldest available request
- **WHEN** a developer loads older requests until reaching the oldest request MockServer currently retains
- **THEN** the page indicates that no older requests are available, rather than allowing another load attempt that returns nothing with no explanation

### Requirement: Web UI remains responsive with multiple simultaneous viewers
The web interface SHALL keep the Recent Requests page responsive - including pages and endpoints unrelated to Recent Requests - when multiple developers have the page open at the same time, regardless of how many requests MockServer has logged.

#### Scenario: Other pages stay responsive while Recent Requests is busy
- **WHEN** multiple developers have the Recent Requests page open simultaneously while MockServer holds a large volume of logged requests
- **THEN** the web interface's other endpoints (for example, health checks and the mocks list) continue to respond promptly rather than being blocked by Recent Requests activity

#### Scenario: Live tail cost does not scale with viewer count
- **WHEN** additional developers open the Recent Requests page while others already have it open
- **THEN** the live tail continues delivering new requests to all open viewers without a proportional increase in the work performed against MockServer for each additional viewer
