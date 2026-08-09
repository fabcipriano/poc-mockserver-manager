## Why

The Recent Requests page shows every request MockServer received, but not whether MockServer answered
it from a developer-created mock or passed it through to the real Gateway/backend. A developer testing a
new mock has to infer this from the response body alone, which breaks down for anything that doesn't
obviously look "mocked" (e.g. a mock whose response happens to resemble the real backend's shape, or a
request the developer expected to be mocked but wasn't, because their matcher was wrong). Showing this
directly, and letting a developer filter down to just mocked or just forwarded traffic, turns the page
into a real verification tool for "is my mock actually taking effect."

## What Changes

- Each entry on the Recent Requests page is labeled as either mocked (answered by a developer-created
  expectation) or forwarded (passed through to the Gateway/backend).
- A filter control lets a developer narrow the page to only mocked or only forwarded requests, on top of
  the existing path filter, for both the loaded history and the live tail.
- No new call to MockServer is introduced: the mocked/forwarded status is derived from response metadata
  already present in the `REQUEST_RESPONSES` log entries the page already fetches - specifically, that a
  forwarded/proxied response carries MockServer-injected transport facts (a `reasonPhrase` and an
  `x-mockserver-response-time-ms` header) that a canned mock response, created through this tool's own
  Create/Edit Mock flow, never sets. See design.md for the reasoning and its limits.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mock-management-ui`: the Recent Requests page's requirements for what a request entry shows, and for
  how a developer filters the page, are extended to cover mocked-vs-forwarded status alongside the
  existing path text filter.

## Impact

- `mock-ui/app.py`: `_fetch_request_history` (backing both `/mock-ui/api/requests` and
  `/mock-ui/api/requests/stream`) computes and includes a mocked/forwarded flag per entry.
- `mock-ui/static/app.js`, `index.html`, `style.css`: a visible mocked/forwarded indicator per row, and a
  filter control alongside the existing path filter.
- No new external dependencies, no new MockServer API calls, no change to MockServer itself.
- Depends on no other in-flight change, but touches the same requirements as the not-yet-archived
  `add-recent-requests-detail` change (which adds the expandable header/body detail view). Both changes
  edit the Recent Requests page; whichever is archived first should sync cleanly, and the other should be
  re-diffed against the then-current main spec before archiving to avoid one silently overwriting the
  other's requirement text.
