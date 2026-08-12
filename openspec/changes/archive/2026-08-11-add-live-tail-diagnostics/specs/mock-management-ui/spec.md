## ADDED Requirements

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
