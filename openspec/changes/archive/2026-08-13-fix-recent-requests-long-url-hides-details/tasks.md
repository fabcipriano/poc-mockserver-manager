## 1. Requests table layout

- [x] 1.1 In `mock-ui/static/style.css`, set `table-layout: fixed` on `#requests-table` and give the Time, Method, Status, Source, and Details (blank-header) columns fixed/`ch`-based widths sized to their content, so they never shrink or get clipped.
- [x] 1.2 Give the Path column the remaining width (e.g. `width: auto` with the other columns fixed) and make its `<code>` cell wrap long unbroken text (`overflow-wrap: anywhere` and/or `word-break: break-word`) instead of forcing the column wider.
- [x] 1.3 Confirm `.table-card` no longer needs to clip content for this row (its `overflow: hidden` can stay, since wrapping - not scrolling - is the fix), and remove/adjust it only if verification in section 2 shows it still clips a wrapped row.

## 2. Verification

- [x] 2.1 Manually seed a request with a very long path (long query string) against mock-ui, open the Recent Requests page, and confirm the path wraps and the "Details" button is visible and clickable on that row.
- [x] 2.2 Confirm normal short-path rows are unaffected (column widths and existing detail-expand behavior look the same as before).
- [x] 2.3 Check narrow viewport widths (e.g. resize to ~600px) to confirm the Details button still stays visible and the table doesn't overflow the page horizontally.
