## Context

MockServer logs `timestamp` as a naive string (`%Y-%m-%d %H:%M:%S.%f`, e.g. `2026-08-09 17:42:03.123456`) with no timezone marker, but in practice it is UTC (the container's clock). `mock-ui/app.py` parses and compares these naively (`_parse_entry_datetime`, `_parse_query_datetime` in `mock-ui/app.py:265-291`) and never converts timezones - it just treats every naive datetime, log entries and filter input alike, as living in the same (UTC) frame. `mock-ui/static/app.js:417` renders `entry.timestamp` verbatim into the table. The from/to filter inputs are native `<input type="datetime-local">` (`mock-ui/static/index.html:150,154`); browsers already give these a local wall-clock value with no zone info (e.g. `2026-08-09T14:30:00`), which today gets sent to the backend and compared directly against UTC-labeled entries - so a developer typing what they intend as their own local time is actually filtering against that clock time in UTC, off by whatever the local UTC offset is.

Per the proposal, conversion happens entirely browser-side; `app.py` keeps storing and comparing everything in UTC, unchanged.

## Goals / Non-Goals

**Goals:**
- Display each request's timestamp in the viewer's local time zone (read from the browser/OS, not hardcoded), including the timestamp embedded in the "range truncated" notice.
- Make the from/to filter inputs round-trip correctly: a developer types what they see as local time, and the backend keeps filtering as if given UTC, transparently converted in between.
- Keep `app.py` and the `/mock-ui/api/requests*` JSON schema unchanged.

**Non-Goals:**
- Changing what MockServer logs or how the backend stores/parses timestamps.
- Letting a developer pick an explicit timezone independent of their browser's; the browser's reported local zone is authoritative.
- Fixing the pagination cursor's wire format (`before=<timestamp>`) - it stays UTC/opaque, since it's never shown to or typed by a developer.

## Decisions

**Parse MockServer's naive timestamp as UTC, then let `Intl`/`Date` render it locally.**
`new Date(entry.timestamp.replace(" ", "T") + "Z")` turns the naive string into a UTC instant; `.toLocaleString()` (no explicit `timeZone` option, so it defaults to the browser's own zone) then renders it in the viewer's local time. This needed a small helper (`formatLocalTimestamp`) since the raw string has no `T`/`Z` and `Date` won't accept it as-is. Considered hardcoding `timeZone: "America/Sao_Paulo"` (matches the literal request), but the user picked the browser-local option during proposal review: it's correct for any viewer, not just one city, and needs no backend or config changes if the mock-ui is ever used from elsewhere.

**Convert `datetime-local` filter values to UTC before adding them to the query string, not on the server.**
`datetime-local` inputs already parse as local wall-clock time when passed to `new Date(...)` (no `Z` suffix). Building a `Date` from the input's components and reformatting it back to `YYYY-MM-DD HH:MM:SS` in UTC (via the `getUTC*` accessors) keeps `_parse_query_datetime` on the backend completely unchanged - it still just receives a naive-UTC string in a format it already accepts. Doing the conversion in the browser (vs. sending the raw local string and converting server-side) means the backend never needs to know the viewer's timezone, consistent with the display decision above.

**Also localize the "range truncated" notice's embedded timestamp.**
`requests-range-truncated`'s text (`mock-ui/static/app.js:445`) interpolates `oldestAvailableTimestamp` raw. It's user-facing prose showing a specific point in time, so it goes through the same `formatLocalTimestamp` helper used for table rows, for consistency with what's displayed in the table.

**Leave the pagination cursor (`before`) untouched.**
`requestsOldestLoadedTimestamp` (`mock-ui/static/app.js:306,477,497`) is only ever round-tripped back to the backend as an opaque `before` query value, never shown to a developer - it keeps using the raw UTC string from the API response.

## Risks / Trade-offs

- **Viewer's OS clock/timezone is wrong or unset** → displayed and filtered times would be off by whatever the misconfiguration is. Acceptable for this internal dev-tool POC; no server-side override is offered since that reintroduces the original UTC-vs-local mismatch for anyone whose browser *is* configured correctly.
- **DST transition ambiguity** for a `datetime-local` value that falls in a repeated or skipped local hour → resolution follows whatever the browser's `Date` engine picks; not worth special-casing for a request-history filter.
- **Malformed/unparsable `entry.timestamp`** (already handled defensively elsewhere, e.g. `_parse_entry_datetime` returning `None`) → `formatLocalTimestamp` falls back to displaying the raw string rather than throwing, matching the existing "don't hard-fail on a display quirk" posture of this page.

## Migration Plan

Frontend-only change (`mock-ui/static/app.js`, `mock-ui/static/index.html` if any label text needs updating); ships with the next `mock-ui` image build. No data migration, no backend deploy ordering concerns, no rollback beyond reverting the static assets.
