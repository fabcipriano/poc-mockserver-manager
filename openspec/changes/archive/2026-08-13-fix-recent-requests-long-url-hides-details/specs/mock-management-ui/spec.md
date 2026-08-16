## MODIFIED Requirements

### Requirement: Web UI shows recent requests received by MockServer
The web interface's Recent Requests page SHALL display request history - timestamp, method, path, response status code, and whether MockServer answered the request from a developer-created mock or forwarded it to the Gateway/backend - for every request `mock-ui` has observed from the selected MockServer target since `mock-ui` last started, accumulated by `mock-ui` in its own local store independent of MockServer's own log retention, showing the most recent requests first. Each displayed timestamp SHALL be shown in the viewer's local time zone rather than the raw UTC value MockServer logs. For any entry, the developer SHALL be able to reveal that request's and its response's headers and body, sourced from `mock-ui`'s locally stored record of what MockServer returned when the request was first observed. The control that reveals detail for an entry SHALL remain visible regardless of how long that entry's path is.

#### Scenario: Developer views recent traffic
- **WHEN** a developer navigates to the Recent Requests page
- **THEN** they see the most recently received requests, each showing at least a timestamp, method, path, response status code, and whether it was mocked or forwarded, most recent first

#### Scenario: Timestamp is shown in the viewer's local time
- **WHEN** a developer views a request on the Recent Requests page
- **THEN** the displayed timestamp reflects the viewer's local time zone, not the raw UTC value MockServer logged

#### Scenario: Requests are shown regardless of whether they were mocked
- **WHEN** MockServer has received both a request that matched a developer-created mock and a request that was forwarded to the Gateway unmocked
- **THEN** both requests appear in the Recent Requests page, each labeled with its own mocked-or-forwarded status

#### Scenario: Developer reveals a request's full detail
- **WHEN** a developer asks to see more detail for one of the listed requests
- **THEN** that request's headers and body, and its response's headers and body, are shown, reflecting what MockServer actually recorded when `mock-ui` first observed the request, rather than a summary

#### Scenario: A request or response with no headers or no body is shown as such
- **WHEN** a developer reveals detail for a request whose response has no body, or whose request or response has no headers
- **THEN** the missing headers or body are indicated as absent rather than left blank or omitted without explanation

#### Scenario: Multiple entries can be expanded at once
- **WHEN** a developer reveals detail for more than one listed request
- **THEN** each revealed request's detail remains visible independently of the others

#### Scenario: A request remains visible after MockServer evicts it from its own log
- **WHEN** MockServer's own request log has evicted a request (for example, due to its `maxLogEntries` cap) that `mock-ui` had already observed during an earlier poll
- **THEN** that request continues to appear on the Recent Requests page, sourced from `mock-ui`'s own locally accumulated history rather than from MockServer's current log

#### Scenario: A long request path does not hide the detail control
- **WHEN** a request's path is long enough that its full text would otherwise force the row wider than the page
- **THEN** the path text wraps within its own column instead of pushing other columns out of view, and that row's detail-revealing control remains visible and clickable without horizontal scrolling
