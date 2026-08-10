## Why

The Recent Requests page displays MockServer's logged timestamps verbatim, and MockServer logs in UTC. A developer working in Brazil has to mentally subtract 3 hours from every timestamp to know when a request actually happened, which is error-prone and slows down debugging live traffic.

## What Changes

- The Recent Requests page displays each request's timestamp converted to the viewer's local time zone (browser-side conversion via the `Intl`/`Date` APIs), instead of the raw UTC string MockServer logs.
- The page's "from" and "to" time-range filter inputs are now interpreted as local time and converted to UTC before being sent to the backend, so a value a developer types (e.g. matching what they now see displayed) lines up with the displayed, localized timestamps.
- The backend's `/mock-ui/api/requests` endpoint continues to store and compare timestamps in UTC internally; only the browser-side display and the browser-side interpretation of filter input change. No API request/response schema changes.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `mock-management-ui`: "Web UI shows recent requests received by MockServer" now requires the displayed timestamp to be shown in the viewer's local time rather than raw UTC. "Web UI lets a developer filter recent requests by path" now requires the time-range filter's "from"/"to" values to be interpreted as local time.

## Impact

- `mock-ui/static/app.js`: the Recent Requests row renderer (`entry.timestamp` display, around line 417) and the time-range filter inputs' request/response handling.
- `mock-ui/app.py`: unaffected in behavior (still logs/compares in UTC); the "oldest retained" and "range truncated" notices that surface raw timestamps to the page also need their display localized for consistency.
- No changes to MockServer, the persisted log format, or the `/mock-ui/api/requests` JSON schema.
