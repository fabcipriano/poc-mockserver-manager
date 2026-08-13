## ADDED Requirements

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
