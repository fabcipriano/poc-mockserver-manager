## Why

The Recent Requests page currently shows only timestamp, method, path, and status code for each
request. When a mock isn't matching as expected, or a developer is debugging pass-through traffic,
that summary isn't enough to diagnose the problem - they need to see the actual headers and body
MockServer received and returned, without switching to another tool.

## What Changes

- Each row in the Recent Requests table gets a "Details" toggle that expands an inline panel showing:
  - The request's headers and body
  - The response's headers and body
- Detail data is sourced live from MockServer's request log (the same `REQUEST_RESPONSES` retrieval
  already backing the page), consistent with the page's existing no-local-cache principle - no new
  cache or storage is introduced.
- Multiple rows can be expanded independently at the same time.
- The detail panel appears for both history rows (loaded on page open) and rows added later by the
  live tail.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mock-management-ui`: the Recent Requests page's requirement for what a request entry displays
  (currently timestamp, method, path, status code) is extended to include, on demand, the request's
  and response's headers and body.

## Impact

- `mock-ui/app.py`: `_fetch_request_history` (used by both `/mock-ui/api/requests` and
  `/mock-ui/api/requests/stream`) includes header and body data in each returned entry.
- `mock-ui/static/app.js`: Recent Requests page rendering gains an expandable detail row per request.
- `mock-ui/static/index.html`, `mock-ui/static/style.css`: markup and styling for the detail panel.
- No new external dependencies or API endpoints; no change to MockServer itself.
