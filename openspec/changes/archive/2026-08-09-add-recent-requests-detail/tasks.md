## 1. Backend: enrich the request history feed

- [x] 1.1 Add an `_observed_body` helper in `mock-ui/app.py` that normalizes an observed request/response body (string, `{"json": ...}`, or `{"string": ...}`) into a plain value
- [x] 1.2 Extend `_fetch_request_history` to include `requestHeaders`, `requestBody`, `responseHeaders`, `responseBody` on each entry, using `_multimap_to_pairs` for headers and `_observed_body` for bodies
- [x] 1.3 Confirm `/mock-ui/api/requests` and `/mock-ui/api/requests/stream` both carry the new fields with no other endpoint changes needed

## 2. Frontend: expandable detail panel

- [x] 2.1 Add an `escapeHtml` helper in `mock-ui/static/app.js` and use it for all interpolated request-derived text, including the existing summary-row fields
- [x] 2.2 Add a body formatter that pretty-prints JSON bodies and passes through non-JSON bodies as-is, with an explicit placeholder for an absent body
- [x] 2.3 Render each request as a summary row plus a paired, initially-hidden detail row with a "Details" toggle; toggling shows/hides that row's headers tables and body blocks for both request and response
- [x] 2.4 Wire the detail row into both history loading (`loadRequestHistory`) and the live tail (`prependRequestRow`), so live-tailed entries get the same detail view as history entries
- [x] 2.5 Add the "Details" column header and detail-panel styling (two-column request/response layout, scrollable body blocks) to `mock-ui/static/index.html` and `mock-ui/static/style.css`

## 3. Verification

- [x] 3.1 Confirm multiple rows can be expanded at once, independently
- [x] 3.2 Confirm an entry with no request/response body or no headers renders an explicit "(empty)" / "(none)" placeholder instead of a blank cell
- [x] 3.3 Exercise the page against real traffic (headers, cookies, JSON body) and check the browser console for errors
