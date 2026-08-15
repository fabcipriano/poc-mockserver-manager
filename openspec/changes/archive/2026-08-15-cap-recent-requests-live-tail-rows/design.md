## Context

`mock-ui/static/app.js` renders each Recent Requests entry as a pair of adjacent DOM rows appended to `requestsBody`: a summary row and its (initially hidden) detail row. Two call sites build that pair:

- `appendRequestRow()` - adds the pair at the **end** of `requestsBody`. Used by the initial `loadRequestHistory()` fetch and by `loadMoreRequests()` (pagination's "load more").
- `prependRequestRow()` - adds the pair at the **start** of `requestsBody`. Used by the live tail's `onmessage` handler and by the paused-tail backlog replay on resume.

Because prepend always inserts at the top and append always inserts at the bottom, the table stays newest-first regardless of which path added a given row, and the **oldest pair is always the last two children of `requestsBody`**.

See proposal.md - Why/What Changes for the motivation and scope; this document covers only how the cap is implemented.

## Goals / Non-Goals

**Goals:**
- Keep the live tail's contribution to DOM size bounded and flat over time, independent of arrival rate or how long the tab has been open.
- Reuse the existing row-pair structure with no change to how a row is built or how detail expansion works.

**Non-Goals:**
- Bounding rows added by `loadRequestHistory()`/`loadMoreRequests()` - pagination already bounds its own cost per call (`REQUEST_HISTORY_LIMIT`), and per the spec delta, a developer's explicit "load more" click is never truncated by this cap.
- Bounding `requestsPendingQueue` (the plain-object backlog held while the tail is paused) - it holds parsed JSON entries, not DOM nodes, so its per-item memory cost is much lower, and this change caps DOM growth specifically. Noted as a risk below, not fixed here.
- Making the cap value externally configurable (e.g. via an env var, mirroring `REQUEST_HISTORY_LIMIT`) - a fixed client-side constant is sufficient for this fix; revisit only if a real need for tuning it shows up.

## Decisions

**Cap value: a fixed constant, `LIVE_TAIL_MAX_ROWS = 500`, defined alongside the page's other Recent Requests constants in `app.js`.** 500 keeps worst-case DOM size trivial for a browser (500 pairs = 1,000 nodes, versus effectively unbounded today) while comfortably exceeding what a developer would scroll through during a live-debugging session. Chosen as a plain constant rather than deriving it from `REQUEST_HISTORY_LIMIT` (40) because the two serve different purposes: `REQUEST_HISTORY_LIMIT` bounds one page's *fetch* cost from `mock-ui`'s backend, while this bounds the browser's cumulative *render* cost across an unbounded number of live-tail pushes - there's no reason the two should share a value.

**Eviction lives only in `prependRequestRow()`, gated on `requestsBody.children.length` after insertion.** After adding the new pair, if the child count exceeds `LIVE_TAIL_MAX_ROWS * 2`, remove pairs from the end (`requestsBody.lastElementChild`, twice per pair) until back at the cap. Putting the check here - not in `appendRequestRow()` - is what keeps pagination's own loads untouched per the spec delta: a developer's "load more" click always renders the full page it asked for, and the cap only resumes trimming on the next live-tail arrival.

**No special handling for an expanded detail row being evicted.** Removing a summary/detail pair via `removeChild` drops both nodes (and their listeners) regardless of whether the detail row was currently toggled open; there's no visible artifact left behind, so no extra state cleanup is needed beyond the removal itself.

**Resuming a paused tail replays the backlog through the same `prependRequestRow()` path, one entry at a time.** The eviction check runs on every call, so if the backlog is larger than the cap, the row count still converges to `LIVE_TAIL_MAX_ROWS` by the time the replay finishes - no separate backlog-specific trimming logic needed.

## Risks / Trade-offs

- **A developer who pauses the tail during a very high-volume period still accumulates an unbounded `requestsPendingQueue`** (plain objects, not DOM nodes) until they resume. Lower severity than the DOM issue this change fixes, and out of scope per Non-Goals - worth a follow-up if it turns out to matter in practice.
- **A developer who loads many pages of history and then leaves the tail running can see rows they explicitly paginated in get evicted** once cumulative live-tail arrivals push the total past the cap. This is the documented, intended trade-off (see spec delta's pagination scenario) of using one shared cap rather than tracking two separate windows in the same table; it keeps the implementation to a single check instead of two.
- **A fixed 500-row cap is a guess, not a measured number.** If it turns out to be noticeably too small (developers routinely wanting to scroll back further in a live burst) or unnecessarily large, it's a one-line constant to adjust - no structural change needed.
