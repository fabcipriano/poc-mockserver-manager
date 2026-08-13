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

### Requirement: Web UI reflects the selected MockServer target's live state with no independent cache
The web interface SHALL NOT maintain its own copy or cache of mock definitions; every list, create, update, and delete action SHALL act directly and synchronously against the currently selected MockServer target's live expectation store.

#### Scenario: UI reflects a change made outside the UI
- **WHEN** a mock is added, changed, or removed by some means other than the web interface (for example, `scripts/add-mock.sh` or a direct MockServer API call) on the currently selected target
- **THEN** the web interface's next list view reflects that change, because it queries that MockServer target directly rather than a local cache

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
The web interface SHALL present a persistent left-hand navigation sidebar with five destinations - Create Mock, List Mocks, Recent Requests, Help, and MockServer Dashboard - such that selecting Create Mock, List Mocks, Recent Requests, or Help shows only that destination's content in the main content area, and selecting MockServer Dashboard opens MockServer's own Dashboard UI in a new browser tab without changing what is shown in the main content area.

#### Scenario: Developer switches between pages
- **WHEN** a developer selects a different one of Create Mock, List Mocks, Recent Requests, or Help in the sidebar
- **THEN** the main content area shows only that destination's page, and the content of the previously shown page is no longer visible

#### Scenario: A page is reachable by a direct link
- **WHEN** a developer loads or reloads the web interface with a specific destination referenced in the URL
- **THEN** that destination's page is shown, without requiring the developer to navigate there manually

#### Scenario: Developer opens the MockServer Dashboard
- **WHEN** a developer selects MockServer Dashboard in the sidebar
- **THEN** MockServer's own Dashboard UI opens in a new browser tab, and the web interface's main content area continues showing whatever page was already displayed there

### Requirement: Web UI lets a developer select which MockServer target to view
The web interface SHALL present a MockServer target selector - a labeled dropdown (or equivalent list control) - that is visible regardless of which page (Create Mock, List Mocks, Recent Requests, Help) is currently shown, listing every MockServer target the system is configured with by its display label. Selecting a different target SHALL immediately re-scope the Create Mock, List Mocks, and Recent Requests pages to that target's live MockServer state.

#### Scenario: Developer switches MockServer target
- **WHEN** a developer selects a different target from the MockServer target selector
- **THEN** the List Mocks page's contents, the Recent Requests page's history and live tail, and any in-progress Create Mock form target the newly selected MockServer instance instead of the previous one

#### Scenario: Selector lists only configured targets
- **WHEN** a developer opens the MockServer target selector
- **THEN** it shows exactly the targets the system is currently configured with, by their display labels, and no others

#### Scenario: Selector remains visible across pages
- **WHEN** a developer navigates between Create Mock, List Mocks, Recent Requests, and Help
- **THEN** the MockServer target selector remains visible and shows the currently selected target throughout

### Requirement: Selected MockServer target persists across navigation and reload
The web interface SHALL remember which MockServer target a developer has selected, both when navigating between pages within the same session and when the page is reloaded, rather than resetting to a default target each time.

#### Scenario: Selection survives page navigation
- **WHEN** a developer selects a MockServer target, then navigates to a different page within the web interface
- **THEN** the same target remains selected on the new page

#### Scenario: Selection survives a page reload
- **WHEN** a developer selects a MockServer target and then reloads the web interface
- **THEN** the previously selected target is still selected, rather than the interface resetting to its default target

### Requirement: mock-ui is configurable to reach multiple MockServer targets without rebuilding
The mock-ui server SHALL determine the set of MockServer targets it can reach (each target's identifier, display label, and base URL) from environment variables read at process startup, such that adding, removing, or repointing a target requires only a configuration change and a restart, not a rebuild of the mock-ui container image.

#### Scenario: Adding a target requires no rebuild
- **WHEN** an operator adds a new MockServer target to the environment-variable configuration and restarts the mock-ui process, without changing any application code or rebuilding its container image
- **THEN** the new target appears in the MockServer target selector and can be selected and used like any other configured target

#### Scenario: A deployment with no multi-target configuration keeps working
- **WHEN** mock-ui is started with none of the multi-target configuration set
- **THEN** it falls back to a single default MockServer target, preserving the behavior of a deployment that has not adopted multi-target configuration

### Requirement: mock-ui's request-history and live-tail timing are configurable without rebuilding
The mock-ui server SHALL determine its recent-requests page size, live-tail poll interval, and SSE heartbeat interval from environment variables read at process startup, each falling back to its current fixed value (page size 40, poll interval 1 second, heartbeat interval 15 seconds) when unset, such that tuning any of them requires only a configuration change and a restart, not a rebuild of the mock-ui container image.

#### Scenario: Operator overrides a timing/size setting
- **WHEN** an operator sets the request-history page size, live-tail poll interval, or heartbeat interval via its environment variable and restarts the mock-ui process, without changing any application code or rebuilding its container image
- **THEN** mock-ui uses the configured value for that setting

#### Scenario: A deployment with none of these variables set keeps working
- **WHEN** mock-ui is started with none of the request-history/live-tail timing variables set
- **THEN** it uses the same page size, poll interval, and heartbeat interval it used before these variables existed

#### Scenario: An invalid value fails startup loudly
- **WHEN** mock-ui is started with a non-integer or out-of-range (zero or negative) value for one of these variables
- **THEN** the process exits at startup with a specific error identifying which variable and value was invalid, rather than starting with an unusable or silently-clamped setting

### Requirement: Web UI shows recent requests received by MockServer
The web interface's Recent Requests page SHALL display MockServer's actual received-request history - timestamp, method, path, response status code, and whether MockServer answered the request from a developer-created mock or forwarded it to the Gateway/backend - sourced live from MockServer rather than a copy the web interface keeps itself, showing the most recent requests first. Each displayed timestamp SHALL be shown in the viewer's local time zone rather than the raw UTC value MockServer logs. For any entry, the developer SHALL be able to reveal that request's and its response's headers and body, also sourced live from MockServer rather than a copy the web interface keeps itself.

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
- **THEN** that request's headers and body, and its response's headers and body, are shown, reflecting what MockServer actually recorded rather than a summary

#### Scenario: A request or response with no headers or no body is shown as such
- **WHEN** a developer reveals detail for a request whose response has no body, or whose request or response has no headers
- **THEN** the missing headers or body are indicated as absent rather than left blank or omitted without explanation

#### Scenario: Multiple entries can be expanded at once
- **WHEN** a developer reveals detail for more than one listed request
- **THEN** each revealed request's detail remains visible independently of the others

### Requirement: Live-tailed requests support the same detail view as history
The web interface's Recent Requests page SHALL let a developer reveal headers and body detail for a request added to the page by the live tail, the same as for a request loaded from history.

#### Scenario: Developer reveals detail for a request that arrived via the live tail
- **WHEN** a developer reveals detail for a request that appeared in the list after the page was already open
- **THEN** that request's headers and body, and its response's headers and body, are shown

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
The web interface SHALL keep the Recent Requests page responsive - including pages and endpoints unrelated to Recent Requests - when multiple developers have the page open at the same time, whether viewing the same target or different targets, regardless of how many requests any configured MockServer target has logged.

#### Scenario: Other pages stay responsive while Recent Requests is busy
- **WHEN** multiple developers have the Recent Requests page open simultaneously while a MockServer target holds a large volume of logged requests
- **THEN** the web interface's other endpoints (for example, health checks and the mocks list) continue to respond promptly rather than being blocked by Recent Requests activity

#### Scenario: Live tail cost does not scale with viewer count
- **WHEN** additional developers open the Recent Requests page for the same target while others already have it open
- **THEN** the live tail continues delivering new requests to all open viewers of that target without a proportional increase in the work performed against that MockServer target for each additional viewer

#### Scenario: Live tail cost does not scale with the number of configured targets beyond one poller each
- **WHEN** the system is configured with multiple MockServer targets, regardless of how many developers are viewing each one
- **THEN** each target is polled by exactly one background poller, and the number of viewers of a given target does not change how many times that target is polled

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
The web interface's Help page SHALL explain, for a developer unfamiliar with the tool, what each supported request matcher (path parameters, query string parameters, headers, cookies, request body) does and how to use it, SHALL state that the seeded catch-all forwarding expectation can never be edited or deleted through the web interface, and SHALL explain what the sidebar's MockServer Dashboard link is for and that it leads to a separate, unauthenticated vendor tool rather than a page the web interface owns.

#### Scenario: Developer learns how a matcher works from the Help page
- **WHEN** a developer navigates to the Help page
- **THEN** they find an explanation of what path parameters, query string parameters, headers, cookies, and the request body matcher each do

#### Scenario: Developer learns what the MockServer Dashboard link is for
- **WHEN** a developer navigates to the Help page
- **THEN** they find an explanation that the MockServer Dashboard link opens MockServer's own Dashboard UI in a new tab, that it shows why a request didn't match any mock (which Recent Requests doesn't show), and that it is a separate vendor tool with no authentication in this POC, not a page the web interface owns or keeps working

### Requirement: Web UI logs the live-tail connection lifecycle and upstream polling outcomes
The mock-ui server SHALL emit structured log records - at minimum a timestamp, an event type, and enough identifying detail (for example, applied filters, error type, or elapsed time) to distinguish causes - for: each SSE client connecting to and disconnecting from the Recent Requests live tail, each attempt by the shared history poller to fetch request history from MockServer (success with latency, or failure with the error), and each time the poller falls back to serving a stale snapshot because a fetch failed.

#### Scenario: A developer can find why the live tail went quiet from server logs
- **WHEN** the shared history poller fails to reach MockServer, or an SSE client's connection is opened or dropped
- **THEN** the mock-ui server's logs contain a record of that event with enough detail to tell a poller failure (can't reach MockServer) apart from a dropped client connection (network/proxy issue) without reproducing the problem live

#### Scenario: Successful polling is also logged, not just failures
- **WHEN** the shared history poller successfully fetches request history from MockServer
- **THEN** the mock-ui server's logs contain a record of that successful poll, so a gap in successful-poll log entries itself indicates when the poller stopped working

### Requirement: Web UI automatically reconnects a lost live tail connection
The web interface's Recent Requests page SHALL automatically attempt to reestablish the live tail connection after it is lost, using increasing delays between attempts up to a capped maximum, rather than requiring the developer to manually reload the page.

#### Scenario: Live tail reconnects after a transient drop
- **WHEN** the live tail connection is lost while a developer has the Recent Requests page open
- **THEN** the web interface automatically attempts to reestablish the connection without the developer reloading the page, and resumes delivering newly arriving requests once reconnected

#### Scenario: Reconnection attempts back off rather than retrying in a tight loop
- **WHEN** the live tail connection repeatedly fails to reestablish
- **THEN** the delay between successive reconnection attempts increases up to a capped maximum, rather than retrying immediately and continuously

### Requirement: Web UI indicates the live tail's connection status
The web interface's Recent Requests page SHALL display an always-visible indicator of the live tail's current connection status - at least Live, Reconnecting, and Disconnected - that updates as the connection's state changes, so a developer can tell at a glance whether newly arriving requests are currently being delivered.

#### Scenario: Indicator reflects a healthy connection
- **WHEN** the live tail connection is open and receiving data
- **THEN** the connection-status indicator shows a Live (connected) state

#### Scenario: Indicator reflects a lost connection that is retrying
- **WHEN** the live tail connection has been lost and the web interface is attempting to reconnect
- **THEN** the connection-status indicator shows a Reconnecting state until the connection is reestablished or reconnection attempts are exhausted

### Requirement: Live tail connection survives idle periods without being dropped by intermediate proxies
The live tail connection SHALL periodically send data to the client even when no new request has arrived, at an interval short enough to keep the connection from being closed as idle by a typical intermediate proxy or load balancer.

#### Scenario: Live tail stays open through a quiet period with no new requests
- **WHEN** a developer has the Recent Requests page open and MockServer receives no new requests for longer than a typical proxy idle-connection timeout
- **THEN** the live tail connection remains open throughout the quiet period and immediately delivers the next request once one arrives, without the developer seeing a dropped-connection state
