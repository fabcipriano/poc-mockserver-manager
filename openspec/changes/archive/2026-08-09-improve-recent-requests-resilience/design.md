## Context

Full investigation, empirical reproduction, and options analysis already live in
`docs/studies/2026-08-09-recent-requests-resilience.md` - this document doesn't repeat that
work, only records the decisions made from it and the resulting technical approach. See that
study for: the reproduction methodology and numbers (30 concurrent tabs hanging the process
entirely), the root-cause trace through `_fetch_request_history()` and `event_stream()`, the
research into MockServer's `/mockserver/retrieve` API (no pagination/limit/time-range
parameter - any such logic has to live in `mock-ui`) and its own log retention (`maxLogEntries`
ring buffer, oldest evicted first), and the two architectural options considered.

## Goals / Non-Goals

**Goals:**
- Fix the reproduced hang: the page's cost must stop scaling with the number of open tabs.
- Add pagination (fixed 100/page, "Load more") and a time-range filter for browsing history
  beyond the current 100-entry window, within what MockServer still retains.
- Do this without weakening or reinterpreting the "no independent cache" requirement that
  governs mock CRUD state.

**Non-Goals** (carried from the study):
- Persistent/long-term history beyond MockServer's own retention window.
- Changing MockServer's own configuration (e.g. `maxLogEntries`) as a substitute fix.
- Moving off Flask's dev server - a legitimate but separate hardening step that doesn't address
  the root cause on its own (see study, Section 7).

## Decisions

- **Shared background poller, not per-connection polling (study's Option A).** One
  background thread, started once at app startup (not per-connection), polls
  `/mockserver/retrieve?type=REQUEST_RESPONSES` on the existing 1-second cadence regardless of
  how many SSE clients are connected, and holds the result in an in-memory structure that each
  SSE connection reads from to compute its own new-entries-since-last-tick diff (each
  connection still needs its own `last_timestamp` cursor and its own active filters, since
  filters are per-viewer). This turns the poll cost from `O(open tabs)` polls per tick into 1
  poll per tick, fixing the reproduced hang directly.
  - This in-memory structure is rebuilt from MockServer on every tick and never written to
    outside of that tick - it holds no state MockServer doesn't already have, and nothing
    survives a restart. It is a transient computation cache, not an independent copy of
    MockServer's state in the sense the existing "no independent cache" requirement means
    (which governs mock CRUD correctness - see study Section 4) - no spec conflict, and no
    change to that requirement is needed.
  - Alternative considered (study's Option B - a small bounded index/ring buffer serving
    O(page size) queries): rejected for this change because it would require either loosening
    or explicitly re-scoping the "no independent cache" requirement, which the study flagged as
    a decision to make deliberately rather than assume. Worth revisiting if Option A's
    per-tick fetch cost (still `O(matching log size)`, just paid once instead of N times) turns
    out to be insufficient in practice.
- **Pagination cursor: the `timestamp` field, descending.** History is already timestamp-ordered
  from MockServer. "Load more" sends the oldest timestamp currently shown and asks for up to 100
  entries strictly older than it, matching the active filters. Two entries sharing the exact
  same millisecond timestamp are a known, documented edge case (see study Section 5) - the
  server-side implementation should apply a stable secondary tie-break (e.g. preserving
  MockServer's own return order for same-timestamp entries) so pagination doesn't skip or repeat
  entries at a boundary, without needing a full request-id scheme.
- **Time-range filtering happens in `mock-ui`, after MockServer's matcher-filtered fetch,
  before pagination is applied.** MockServer has no time-range parameter (study Section 3), so
  there's no way to push this down. The `from`/`to` filter is applied to the same fetch that
  backs the path/mocked filters, in the same request-handling pass, so it doesn't add a second
  round-trip to MockServer.
- **The time-range filter scopes the initial/paginated history fetch only, not the live
  tail.** A live-tailed entry is, by definition, arriving "now" - applying a historical "to" in
  the past to a stream of new arrivals doesn't have a sensible reading (does a new request
  "violate" a past "to" bound and get hidden, even though it just happened?). Decision: the live
  tail continues to respect the path and mocked/forwarded filters exactly as today, and ignores
  `from`/`to`. This is made explicit as a scenario in the spec delta rather than left implicit,
  since a developer skimming the code could reasonably guess either behavior.
- **"Reached the oldest retained entry" is a first-class UI state, not a silent empty page.**
  Since MockServer's ring buffer silently evicts oldest entries once its cap is hit (study
  Section 3), a "Load more" that returns nothing is ambiguous - out of results because of the
  filters, or out of results because that's genuinely the oldest MockServer has? The page
  distinguishes these: a page with an empty result you could not have anticipated (fewer than
  100 returned, or zero returned after previously returning some) is treated as "no older
  entries," not silently offering another "Load more" click that will always return nothing.

## Risks / Trade-offs

- [The shared poller's per-tick fetch is still `O(matching log size)` - if the log routinely
  holds tens of thousands of entries, that per-tick cost could itself become significant, even
  paid only once] → Accepted for this change per the study's recommendation to start with
  Option A and measure before reaching for Option B's bounded cache. Worth a follow-up
  measurement once this ships.
- [A "Load more" cursor based on `timestamp` alone has a same-millisecond tie-break edge case]
  → Documented as a known limitation (see Decisions above); acceptable at this POC's traffic
  patterns, where true same-millisecond duplicate requests are rare.
- [MockServer's ring buffer means "search old requests by date" can silently come up short if
  the requested range predates what's retained] → Addressed directly by a spec scenario and UI
  messaging (see Decisions above and the "predating MockServer's retained history" scenario in
  the spec delta) rather than left as a surprise.
