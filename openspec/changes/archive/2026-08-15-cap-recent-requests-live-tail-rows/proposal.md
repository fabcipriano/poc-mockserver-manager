## Why

The Recent Requests page's live tail (`mock-ui/static/app.js`'s `prependRequestRow()`) appends two DOM nodes per incoming request and never removes any, so a tab left open during sustained high request volume (for example, 100 req/s) accumulates DOM nodes without bound and eventually makes the browser tab unresponsive. This is a real gap: `REQUEST_HISTORY_LIMIT` caps the initial page load and each page-load-more fetch, but nothing bounds what the live tail keeps adding to the page while it's open. See `docs/studies/2026-08-09-recent-requests-resilience.md` for the related backend concurrency study and `openspec/changes/archive/2026-08-09-improve-recent-requests-resilience` for the shared-poller fix that already solved the backend side of "many viewers, high volume." This change addresses the remaining client-side gap the study didn't cover.

## What Changes

- The Recent Requests page's live tail keeps at most a fixed number of rows in the browser DOM. When a new request arrives via the live tail and the table is already at that cap, the oldest row (and its paired detail row) is removed before the new one is added - the same ring-buffer eviction MockServer already applies to its own request log, applied client-side.
- This applies regardless of how the row arrived at the cap boundary: a live tail push while the tail is running, or the queued backlog replayed when a paused tail is resumed.
- No change to backward pagination (`loadRequestHistory`/`loadMoreRequests`, `REQUEST_HISTORY_LIMIT`, the "load more" control) - that path already bounds its own cost per page and is out of scope here.
- No backend change: `app.py`'s shared per-target poller, its in-memory `history_snapshot`, and the SSE fan-out are unaffected: this is a client-side rendering cap, not a change to what MockServer or mock-ui's backend retains or serves.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `mock-management-ui`: adds a requirement that the Recent Requests page's live tail bounds how many rows it keeps in the browser DOM, evicting the oldest row once a fixed cap is reached, so an open tab's memory/DOM footprint stays flat regardless of how long the tail runs or how fast requests arrive.

## Impact

- **Code:** `mock-ui/static/app.js` only - a max-live-rows constant and an eviction check inside `prependRequestRow()` (and, by extension, wherever it's invoked from the paused-tail replay path). No changes expected to `mock-ui/app.py`, `mock-ui/static/index.html`, or `mock-ui/static/style.css`.
- **Behavior:** once the live tail has added enough rows to reach the cap, the oldest visible row silently drops off the bottom of the list as each new one arrives at the top - matching how MockServer's own log eviction already works, and consistent with backward pagination remaining the way to look further back.
- **No API/spec changes to MockServer or mock-ui's backend endpoints.**
- **No persistence introduced** - consistent with the existing "no independent cache" principle for this capability; this only bounds what the already-ephemeral live view holds on screen at once.
