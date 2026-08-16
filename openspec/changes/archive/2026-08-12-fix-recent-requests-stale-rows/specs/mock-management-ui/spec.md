## MODIFIED Requirements

### Requirement: Web UI automatically reconnects a lost live tail connection
The web interface's Recent Requests page SHALL automatically attempt to reestablish the live tail connection after it is lost, using increasing delays between attempts up to a capped maximum, rather than requiring the developer to manually reload the page. Upon successfully reestablishing a previously lost connection, the web interface SHALL resync its displayed request history with MockServer's current state rather than only resuming delivery of newly arriving requests.

#### Scenario: Live tail reconnects after a transient drop
- **WHEN** the live tail connection is lost while a developer has the Recent Requests page open
- **THEN** the web interface automatically attempts to reestablish the connection without the developer reloading the page, and resumes delivering newly arriving requests once reconnected

#### Scenario: Reconnection attempts back off rather than retrying in a tight loop
- **WHEN** the live tail connection repeatedly fails to reestablish
- **THEN** the delay between successive reconnection attempts increases up to a capped maximum, rather than retrying immediately and continuously

#### Scenario: A successful reconnect resyncs history, not just the tail
- **WHEN** the live tail connection is lost and then successfully reestablished
- **THEN** the displayed request history is refreshed to match MockServer's current state, so requests shown before the drop that are no longer part of MockServer's history (for example, because MockServer itself restarted while mock-ui's connection to it was interrupted) are no longer shown as current

## ADDED Requirements

### Requirement: Web UI detects and resyncs a MockServer-side history reset without requiring a connection drop
The mock-ui server SHALL detect when MockServer's request/response history has been reset (for example, because MockServer itself restarted) even while its own connection to MockServer and to open Recent Requests browser tabs remains uninterrupted, and SHALL cause every open Recent Requests page to resync its displayed history to MockServer's current state shortly after detecting the reset, with a visible indication to the developer that a resync occurred.

#### Scenario: A MockServer-only restart is detected and resynced without a live-tail reconnect
- **WHEN** MockServer restarts and its request/response history is reset while a developer has the Recent Requests page open and its live tail connection to mock-ui never drops
- **THEN** the displayed request history is refreshed to match MockServer's current (reset) state within a short, bounded time of the reset being detected, without requiring the developer to reload the page or the live tail connection to have dropped and reconnected

#### Scenario: Developer is told a resync happened
- **WHEN** the Recent Requests page's displayed history is refreshed because a MockServer-side reset was detected
- **THEN** the developer sees a visible, transient notice explaining that the history was refreshed because of a detected reset, rather than the displayed rows silently changing with no explanation

### Requirement: Web UI's shared history poller recovers from a MockServer connectivity interruption without requiring a mock-ui restart
The mock-ui server's shared history poller SHALL continue polling MockServer on its normal cadence after any individual poll attempt fails for any reason, including a connection interrupted mid-request (for example, by MockServer restarting while a poll is in flight), without requiring mock-ui itself to be restarted for polling to resume.

#### Scenario: A connection reset mid-poll does not permanently stop polling
- **WHEN** a poll attempt's connection to MockServer is reset or otherwise interrupted partway through the request
- **THEN** that attempt is treated as a failed poll, and the next scheduled poll attempt still occurs on the normal cadence, rather than polling stopping permanently for the rest of the mock-ui process's life
