## Context

The Recent Requests page already polls MockServer's `retrieve?type=REQUEST_RESPONSES` for history and
tails it live over SSE (`/mock-ui/api/requests` and `/mock-ui/api/requests/stream` in `mock-ui/app.py`).
Both endpoints funnel through one function, `_fetch_request_history`, that currently narrows each
MockServer log entry down to `timestamp`, `method`, `path`, `statusCode`. See proposal.md for why that's
no longer enough on its own.

## Goals / Non-Goals

**Goals:**
- Surface headers and body for both the request and its response, for any entry the page already shows.
- Keep the page's existing "no independent cache" property: detail comes from the same MockServer log
  entry already fetched for the row, not a second request-on-demand call.

**Non-Goals:**
- Persisting or exporting request/response detail anywhere outside the page.
- Editing, replaying, or otherwise acting on a past request from the detail view.
- Truncating or paginating large bodies - out of scope for this change; today's `REQUEST_HISTORY_LIMIT`
  (100 entries) already bounds how much a single page load can hold.

## Decisions

- **Extend the existing entry shape instead of adding a second endpoint.** `_fetch_request_history`
  already retrieves the full `httpRequest`/`httpResponse` objects from MockServer per entry; it just
  discards most of the fields. Adding `requestHeaders`, `requestBody`, `responseHeaders`,
  `responseBody` to the same returned dict means the SSE stream carries full detail automatically, with
  no separate "fetch detail for entry X" round trip and no risk of the detail no longer matching the
  summary row (MockServer's log is immutable per entry, but a second fetch would still be an
  unnecessary extra call).
- **Normalize header multimaps with the existing `_multimap_to_pairs` helper.** Already used for mock
  matcher headers; MockServer represents observed request/response headers the same
  `{name: [value, ...]}` shape, so no new normalization logic is needed there.
- **Normalize body shape with a new small helper (`_observed_body`).** Unlike a mock's *matcher* body
  (which has its own typed shape handled by `_request_body_from_httpRequest`), an *observed* body in
  MockServer's log can come back as a bare string, `{"json": ...}`, or `{"string": ...}`, depending on
  content type. The helper collapses these to a plain value (dict/list for JSON, string otherwise) so
  the frontend can render it uniformly - JSON pretty-printed, everything else as-is.
  - Alternative considered: keep the raw MockServer shape and let the frontend branch on it. Rejected -
    pushes MockServer-specific parsing into the UI layer for no benefit.
- **Render detail as an expandable row, built and destroyed with the summary row, not a modal or a
  separate view.** Consistent with the page's live-tail model: a live-tailed entry's detail row is
  created at the same time as its summary row (both come from the same SSE payload), so there's no
  extra state to keep in sync when new requests arrive while a detail panel is open elsewhere in the
  list.
- **Escape all interpolated request/response text before inserting it into the DOM.** Header values,
  paths, and bodies come from arbitrary traffic MockServer received - not just from data the developer
  entered - so they're attacker-influenceable. The existing summary-row rendering already built HTML via
  template literals; this change adds an `escapeHtml` helper and applies it there too while touching
  that code, rather than introducing a second, unescaped path for the new detail content next to it.

## Risks / Trade-offs

- [Large bodies could make a detail panel unwieldy] → Body display is scrollable with a max height; no
  further truncation for this change, per Non-Goals.
- [SSE payloads grow larger now that every entry carries full headers/body] → Acceptable at this POC's
  scale (single developer, `REQUEST_HISTORY_LIMIT` = 100); revisit if the page is ever used against
  high-volume traffic.
