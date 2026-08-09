## MODIFIED Requirements

### Requirement: Web UI shows recent requests received by MockServer
The web interface's Recent Requests page SHALL display MockServer's actual received-request history - timestamp, method, path, and response status code for each - sourced live from MockServer rather than a copy the web interface keeps itself, showing the most recent requests first. For any entry, the developer SHALL be able to reveal that request's and its response's headers and body, also sourced live from MockServer rather than a copy the web interface keeps itself.

#### Scenario: Developer views recent traffic
- **WHEN** a developer navigates to the Recent Requests page
- **THEN** they see the most recently received requests, each showing at least a timestamp, method, path, and response status code, most recent first

#### Scenario: Requests are shown regardless of whether they were mocked
- **WHEN** MockServer has received both a request that matched a developer-created mock and a request that was forwarded to the Gateway unmocked
- **THEN** both requests appear in the Recent Requests page

#### Scenario: Developer reveals a request's full detail
- **WHEN** a developer asks to see more detail for one of the listed requests
- **THEN** that request's headers and body, and its response's headers and body, are shown, reflecting what MockServer actually recorded rather than a summary

#### Scenario: A request or response with no headers or no body is shown as such
- **WHEN** a developer reveals detail for a request whose response has no body, or whose request or response has no headers
- **THEN** the missing headers or body are indicated as absent rather than left blank or omitted without explanation

#### Scenario: Multiple entries can be expanded at once
- **WHEN** a developer reveals detail for more than one listed request
- **THEN** each revealed request's detail remains visible independently of the others

## ADDED Requirements

### Requirement: Live-tailed requests support the same detail view as history
The web interface's Recent Requests page SHALL let a developer reveal headers and body detail for a request added to the page by the live tail, the same as for a request loaded from history.

#### Scenario: Developer reveals detail for a request that arrived via the live tail
- **WHEN** a developer reveals detail for a request that appeared in the list after the page was already open
- **THEN** that request's headers and body, and its response's headers and body, are shown
