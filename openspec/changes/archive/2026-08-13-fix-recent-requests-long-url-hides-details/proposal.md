## Why

On the Recent Requests page, a request whose path is long (a long URL, a large query string, etc.)
forces the requests table wider than its container. The table's container clips overflow instead
of scrolling, so the trailing columns - including the "Details" button - are pushed past the
visible edge and disappear. A developer who most needs to inspect a request with an unusual or
oversized path (often exactly the kind of request worth debugging) has no way to reveal its
detail.

## What Changes

- The Recent Requests table adopts fixed column sizing so the Time, Method, Status, Source, and
  Details columns always keep enough width to stay visible, and the Path column absorbs the
  remaining space instead of the browser auto-sizing the table to its widest cell.
- A long, unbroken path value wraps within its cell (rather than forcing the column wider) so the
  full row - and its "Details" button - always stays visible without horizontal scrolling.
- No change to what "Details" reveals or how it behaves once clicked - only to the guarantee that
  the button stays reachable regardless of path length.

## Capabilities

### Modified Capabilities

- `mock-management-ui`: the "Web UI shows recent requests received by MockServer" requirement
  gains a guarantee that a long request path does not hide the detail control for that row.

## Impact

- `mock-ui/static/style.css`: requests table layout (`#requests-table`, `.table-card`) gains fixed
  column widths / `table-layout: fixed` and the path cell gains wrapping instead of unconstrained
  growth.
- `mock-ui/static/app.js`: `renderRequestRow` - no logic change expected, but verify no assumption
  about column widths.
- No backend or API changes.
