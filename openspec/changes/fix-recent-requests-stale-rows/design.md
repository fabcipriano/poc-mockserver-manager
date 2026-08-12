## Context

See `proposal.md` - Why for the two scenarios this closes. Relevant current state:

- The shared history poller (`_poll_history_once`, `mock-ui/app.py`) already re-fetches
  MockServer's full request/response log every `REQUEST_STREAM_POLL_SECONDS` (1s) into a single
  shared, lock-protected `_history_snapshot`, read by every open SSE connection and by
  `/mock-ui/api/requests`. It returns entries oldest-first (`snapshot[0]` is oldest,
  `snapshot[-1]` is newest - already relied on elsewhere, e.g. `list_requests`'s
  `oldest_available_timestamp = snapshot[0]["timestamp"]`).
- Each SSE connection's `event_stream()` generator tracks its own `last_timestamp` (the newest
  entry it has already sent) and, per `add-live-tail-diagnostics`, also tracks time since its
  last byte sent for the heartbeat. Both are per-connection state inside the generator closure.
- The client's `connectRequestsStream()` (`mock-ui/static/app.js`) is the single function used
  both for the very first connection (from `openRequestsStream`) and for every automatic
  reconnect attempt (from `scheduleRequestsReconnect`'s `setTimeout`). `loadRequestHistory()`
  fully replaces `#requests-body`'s contents from `/mock-ui/api/requests`; nothing currently
  calls it except the initial page-navigation path in `syncRequestsPageStream`.
- Existing accepted convention: entry identity is keyed by timestamp (millisecond precision),
  already used for pagination's `before` cursor with a documented, accepted collision
  limitation (`mock-ui/app.py`, `list_requests`'s tie-break comment). This design reuses that
  same convention rather than introducing a new identity scheme.

## Goals / Non-Goals

**Goals:**
- Detect a MockServer-side history reset from the already-running shared poller, with no extra
  calls to MockServer beyond what it already makes.
- Notify every currently-open Recent Requests tab of a detected reset within about one poll
  cycle, whether or not that tab's own connection to mock-ui ever dropped.
- Resync the displayed table (not just resume the tail) both when a reset is detected and when
  a genuinely dropped connection reconnects.

**Non-Goals:**
- Preserving row-level continuity or avoiding any visual "flash" across a resync - a full
  table replace (already what `loadRequestHistory()` does) is acceptable; this is a diagnostic
  POC tool, not a change-tracked data grid.
- Guaranteeing zero possibility of a race between a resync's fetch and a concurrently-arriving
  live-tailed entry (see Risks) - the existing codebase doesn't guard concurrent
  `loadRequestHistory()`/live-tail interleaving today either, and this change doesn't raise the
  bar there.
- Detecting or explaining *why* a reset happened (MockServer OOM vs. rolling deploy vs. manual
  restart) - that's a MockServer/infrastructure-level question, covered by the diagnostics
  already shipped in `add-live-tail-diagnostics` and the checklist in
  `docs/studies/2026-08-11-live-tail-eks-diagnostics.md`, not by this change.

## Decisions

**Reset detection: a shared generation counter, incremented by the poller, compared per-connection - not a per-connection diff.** Add a module-level `_history_reset_generation` integer alongside `_history_snapshot`, updated under the same lock. On each poll, `_poll_history_once` compares the new snapshot against the previous one using two cheap checks, in order: (a) the previous snapshot was non-empty and the new one is empty - the common case, where the restart happens to be observed as a real gap; (b) the new snapshot is non-empty but its newest entry's timestamp *was already seen* as absent (i.e., the previous newest entry's timestamp is no longer present anywhere in the new snapshot) - covers the case where new traffic arrives fast enough after a restart that we never observe a literally-empty poll in between. Either condition increments the generation counter. Each SSE connection's generator initializes its own `last_seen_generation` to the *current* generation at connect time (so a freshly-opened tab never gets a spurious "reset" notice for one that already happened before it connected), and on each loop tick compares against the shared value - a cheap integer read under the lock, not a diff. This mirrors the existing "one shared background computation, many cheap per-connection reads" pattern already documented in `app.py`'s "shared history poller" comment, so it adds no new per-tab cost to MockServer or to the poll itself.

*Alternative considered:* have MockServer expose a boot/start time or instance id to check directly. Rejected - not something mock-ui controls or has confirmed MockServer 5.15.0 exposes in a stable, documented way, whereas the generation-counter approach only depends on behavior already relied on elsewhere in this codebase (append-only-from-the-newest-end, oldest-end eviction).

**Signal mechanism: a distinct named SSE event, not the heartbeat comment or a regular `data:` message.** The existing heartbeat (`: ping\n\n`) is an SSE *comment* - invisible to `EventSource`, by design, so it can't carry this signal. A regular `data: ...\n\n` message is what the client's default `onmessage` already interprets as one live request entry - reusing it would require the client to distinguish payload shapes, adding ambiguity for no benefit. Instead, `event_stream` yields `event: history-reset\ndata: {}\n\n` when it observes the generation counter has advanced since its own last-seen value. The client adds `requestsEventSource.addEventListener("history-reset", handler)` - SSE named events are a standard, already-spec-compliant mechanism, requiring no protocol change beyond what `EventSource` natively supports.

**Client: one shared resync helper, called from both trigger paths.** Both "reconnect succeeded" and "history-reset event received" should do the same thing - refresh the table and show the same kind of notice - so both call a single new `resyncRequestsHistory(reasonText)` helper that runs `loadRequestHistory()` and shows a transient notice with the given reason, rather than duplicating that logic. `connectRequestsStream` gains a parameter distinguishing "this is a reconnect" from "this is the very first connect" (the first connect already gets its history load from `syncRequestsPageStream`, so calling the resync helper there too would be a redundant, if harmless, double fetch - avoided by the parameter rather than accepted as waste).

**Notice UX: reuse the existing transient-note styling pattern, not a new banner system.** A small note element styled like the existing `#requests-range-truncated` note (`mock-ui/static/style.css`), shown for a few seconds and then hidden, rather than introducing a new banner/toast component for a single use case.

## Risks / Trade-offs

[A live-tailed entry arrives in the narrow window between a reset being detected and the resync's `loadRequestHistory()` fetch completing] → `loadRequestHistory()` fetches current state from `/mock-ui/api/requests`, which reads the same shared snapshot the live tail reads - in practice the resync's own fetch will already include anything that arrived up to that point, and anything arriving in the small remaining window is picked up by the next live-tail message once the resync completes. Accepted, not guarded with locking - consistent with the existing codebase's unguarded concurrent-fetch pattern (e.g. `loadMoreRequests` racing a filter change today).

[Detection heuristic (b) - "previous newest entry's timestamp no longer present" - could theoretically false-positive if MockServer's own retention ever evicted from the newest end instead of the oldest] → Not expected behavior for MockServer's request log (retention has always been oldest-first in what this codebase has observed and is architected around, e.g. `oldestAvailableTimestamp` semantics), and a false-positive here only costs one extra, harmless resync - not a correctness problem, just a wasted refresh.

[Generation counter is in-memory only, per mock-ui process] → If mock-ui itself restarts, the counter resets to 0 along with everything else; this is fine, since a mock-ui restart is already covered by the separate reconnect-triggers-resync path, not by generation-counter detection.

## Addendum: poller thread resilience (found during manual verification)

Manual verification of task 6.1 surfaced a pre-existing bug, unrelated to the reset-detection
feature's own logic but directly blocking its ability to ever run: `_mockserver_put` only
caught `urllib.error.URLError`, not the broader `OSError` family. A MockServer restart that
happens to interrupt an in-flight poll request raises `ConnectionResetError` - an `OSError`
subclass, but not a `URLError` subclass - which went uncaught, propagated out of
`_poll_history_once` and `_history_poller_loop`, and permanently killed the poller's daemon
thread with nothing to restart it. Once that happens, `/mock-ui/api/requests`, the live tail,
and this change's own reset detection all freeze at whatever `_history_snapshot` last held,
for the rest of that mock-ui process's life - a strictly worse outcome than the stale-rows
problem this change set out to fix, and plausibly the actual root cause behind the original
AWS EKS report.

**Fix, folded into this change rather than split out:** this change's own verification is what
surfaces the bug, and the reset-detection feature is meaningless if the thread that would
detect a reset can die permanently, so hardening it here rather than in a separate change keeps
the fix and the thing it protects together.

- `_mockserver_put`'s except clause is broadened from `urllib.error.URLError` to `OSError`
  (`URLError` is itself an `OSError` subclass, confirmed via `issubclass`, so this is a
  strict widening, not a behavior change for the cases already handled) - converts a mid-request
  reset into the same `MockServerError` path every caller already handles, rather than an
  uncaught exception.
- `_history_poller_loop` additionally wraps its `_poll_history_once()` call in a catch-all
  `except Exception`, logged via `logger.exception` and then continuing the loop - a backstop
  so no future, not-yet-considered exception type can silently kill this thread either. The
  `OSError` widening above is expected to handle the actual observed case; this is defense in
  depth for a long-lived background thread, not a substitute for it.

## Migration Plan

No data migration - `_history_reset_generation` is in-memory state, starting at 0 on every
mock-ui process start, same lifecycle as `_history_snapshot`. Rollout is a normal image
rebuild/redeploy of `mock-ui`. Rollback is redeploying the previous image; no schema or
persisted state is introduced.
