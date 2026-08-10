## 1. Local-time display

- [x] 1.1 Add a `formatLocalTimestamp(rawUtcTimestamp)` helper in `mock-ui/static/app.js` that parses MockServer's naive `YYYY-MM-DD HH:MM:SS.ffffff` string as UTC and returns it rendered in the browser's local time zone, falling back to the raw string if parsing fails
- [x] 1.2 Use `formatLocalTimestamp` for each row's timestamp cell (`mock-ui/static/app.js:417`)
- [x] 1.3 Use `formatLocalTimestamp` for the `oldestAvailableTimestamp` interpolated into the "range truncated" notice (`mock-ui/static/app.js:445`)

## 2. Local-time filter input

- [x] 2.1 Add a helper that converts a `datetime-local` input's value (local wall-clock, no zone) into the naive-UTC `YYYY-MM-DD HH:MM:SS` string the backend expects
- [x] 2.2 Apply the conversion to `requestsFromFilter.value` and `requestsToFilter.value` before they're set as the `from`/`to` query params in `requestsApiUrl` (`mock-ui/static/app.js:335-340`)

## 3. Verification

- [x] 3.1 Run the mock-ui app locally, generate a request, and confirm the Recent Requests table shows a timestamp matching the local system clock rather than UTC
- [x] 3.2 Set a "from"/"to" range using times as shown in the local system clock and confirm the expected requests are included/excluded
- [x] 3.3 Confirm the "range truncated" notice (trigger by setting a "from" earlier than the oldest retained request) shows a local-time timestamp consistent with the table
- [x] 3.4 Run `mock-ui`'s existing test suite (`mock-ui/test_app.py`) and confirm it still passes unchanged, since backend behavior is untouched
