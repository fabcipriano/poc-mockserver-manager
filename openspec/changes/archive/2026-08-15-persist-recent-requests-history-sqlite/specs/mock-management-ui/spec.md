## MODIFIED Requirements

### Requirement: Web UI shows recent requests received by MockServer
The web interface's Recent Requests page SHALL display request history - timestamp, method, path, response status code, and whether MockServer answered the request from a developer-created mock or forwarded it to the Gateway/backend - for every request `mock-ui` has observed from the selected MockServer target since `mock-ui` last started, accumulated by `mock-ui` in its own local store independent of MockServer's own log retention, showing the most recent requests first. Each displayed timestamp SHALL be shown in the viewer's local time zone rather than the raw UTC value MockServer logs. For any entry, the developer SHALL be able to reveal that request's and its response's headers and body, sourced from `mock-ui`'s locally stored record of what MockServer returned when the request was first observed.

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

### Requirement: Web UI lets a developer filter recent requests by path
The web interface SHALL let a developer narrow the Recent Requests page to only requests whose path contains a given piece of text, without requiring the developer to write a regular expression; independently narrow it to only mocked requests or only forwarded requests; and independently narrow it to requests received within a given time range. All active filters SHALL combine. The "from" and "to" time-range values SHALL be interpreted in the viewer's local time zone, consistent with how timestamps are displayed.

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

#### Scenario: Time range values are interpreted as local time
- **WHEN** a developer sets a "from" or "to" time on the Recent Requests page
- **THEN** the value is treated as the viewer's local time and converted to match MockServer's UTC-logged timestamps before filtering, so it lines up with the locally-displayed timestamps on the page

#### Scenario: A time range predating MockServer's retained history is communicated, not silently incomplete
- **WHEN** a developer sets a "from" time earlier than the oldest request `mock-ui` currently retains in its locally accumulated history (which may predate what MockServer itself still retains, or vice versa if `mock-ui`'s own retention policy has pruned further back than MockServer's ring buffer, and which in either case only covers what `mock-ui` has observed since it last started)
- **THEN** the page shows requests from the oldest retained entry onward and indicates that earlier requests are no longer available, rather than implying the range was fully searched

#### Scenario: The time range filter does not scope the live tail
- **WHEN** a developer has a "to" time in the past set on the Recent Requests page
- **THEN** newly arriving requests still appear via the live tail as they are received, since the live tail reflects requests happening now rather than the historical range being browsed

### Requirement: Web UI paginates recent request history
The web interface's Recent Requests page SHALL let a developer load additional, older requests beyond the initially displayed set, in fixed pages of at most 100 requests, respecting any active filters, and SHALL indicate when no further, older requests are available.

#### Scenario: Developer loads the next page of history
- **WHEN** a developer asks the Recent Requests page to load older requests
- **THEN** up to 100 additional, older requests matching the active filters are appended to the list

#### Scenario: Loading more respects active filters
- **WHEN** a developer has a path filter, a mocked/forwarded filter, or a time range filter active and loads older requests
- **THEN** the additional requests loaded also satisfy all of those active filters

#### Scenario: Reaching the oldest available request
- **WHEN** a developer loads older requests until reaching the oldest request `mock-ui` currently retains in its locally accumulated history
- **THEN** the page indicates that no older requests are available, rather than allowing another load attempt that returns nothing with no explanation

## ADDED Requirements

### Requirement: Recent Requests history stays reliable independent of MockServer's own log retention
While `mock-ui` is running, the web interface SHALL retain every request it has observed for each configured MockServer target in its own local store, such that the Recent Requests page continues to show a previously observed request after MockServer itself has evicted that request from its own log. Locally accumulated history SHALL be bounded by an explicit retention policy rather than retained without limit. This history is not required to survive a `mock-ui` process restart or pod reschedule - it covers only what `mock-ui` has observed since it last started.

#### Scenario: A previously observed request is not silently lost while mock-ui keeps running
- **WHEN** `mock-ui` has observed and locally stored a request, and MockServer subsequently evicts that request from its own log during normal, continued operation
- **THEN** the request still appears on the Recent Requests page, without requiring `mock-ui` to have been restarted

#### Scenario: Locally accumulated history is bounded, not unbounded
- **WHEN** the volume of requests `mock-ui` has observed for a target exceeds its configured retention policy
- **THEN** `mock-ui` prunes the oldest locally stored entries for that target so its stored history stays within the configured bound, rather than growing without limit

#### Scenario: Each configured target's locally accumulated history is independent
- **WHEN** `mock-ui` is configured with multiple MockServer targets
- **THEN** each target's locally stored request history and retention are tracked independently, and pruning or restarting the history for one target does not affect another target's history

#### Scenario: A mock-ui restart starts each target's history empty
- **WHEN** `mock-ui` is restarted
- **THEN** each configured target's Recent Requests history begins empty again and reaccumulates from subsequent polls, rather than being expected to reflect requests observed before the restart
