## Why

`scripts/load-test-recent-requests.sh` (100,000 sequential `/booking/N` requests) proved the Recent Requests page loses history: `GET /booking/20123` never appears, even though it was received. Today `mock-ui`'s history poller (`_poll_history_once` in `mock-ui/app.py`) wholesale-replaces its per-target in-memory snapshot from MockServer's `/mockserver/retrieve` response on every tick - it mirrors MockServer's current log rather than accumulating what it has observed. Combined with MockServer's own `maxLogEntries` ring buffer (which silently evicts its oldest entries once full, with no explicit cap configured in `k8s/overlays/with-mockserver/mockserver-deployment.yaml`), any entry MockServer has already evicted is gone from `mock-ui` too, and there is no way to get it back. The same in-memory design also means a `mock-ui` process restart or crash discards all history immediately, not just entries MockServer would have evicted anyway.

This was called out as an explicit non-goal in `docs/studies/2026-08-09-recent-requests-resilience.md` ("true long-term/persistent history... would require introducing actual storage, which is a materially bigger change") and deliberately not addressed in the follow-up `2026-08-09-improve-recent-requests-resilience` change, which kept the poller's snapshot as a "transient computation cache" specifically so it wouldn't need to touch the "no independent cache" requirement. This proposal is that follow-up: make `mock-ui` accumulate request history it has observed into a local SQLite store instead of replacing an in-memory snapshot each tick, so the Recent Requests page stops losing entries it already saw. Surviving a `mock-ui` restart is explicitly not a goal - only reliability of the log while `mock-ui` is running, i.e. no longer silently losing entries MockServer has already evicted from its own ring buffer.

## What Changes

- Replace each `Target`'s in-memory `history_snapshot` list with a per-target SQLite database that the history poller upserts into every poll tick (insert-or-ignore on a documented dedup key, since MockServer assigns no stable per-request id), instead of replacing wholesale.
- `GET /mock-ui/api/requests` (path/mocked/time-range filters, pagination) reads from SQLite via indexed queries instead of slicing an in-memory list.
- `GET /mock-ui/api/requests/stream` (SSE live tail) is re-based on SQLite-backed reads for newly inserted rows each tick, in place of reading the old in-memory snapshot directly.
- Add a bounded retention/pruning policy for the SQLite store (row cap or TTL) so accumulation trades yesterday's "OOM from re-fetch/re-parse blowup" (already fixed) for a new, explicitly bounded "disk usage" risk instead of an unbounded one.
- SQLite files live on `mock-ui`'s local/ephemeral filesystem (no PVC, no new k8s volume) - the goal is a reliable, non-lossy log while `mock-ui` is running, not history that survives a pod restart/reschedule. A restart starts each target's store empty again, same as today's in-memory behavior.
- **MODIFIED**: "Web UI shows recent requests received by MockServer" currently states history is "sourced live from MockServer rather than a copy the web interface keeps itself" - this is no longer accurate once `mock-ui` accumulates history into its own local SQLite store instead of mirroring MockServer's current log, and the requirement text and its "oldest retained" scenarios need to say so explicitly, including that "oldest available" is now bounded by `mock-ui`'s own retention policy, not only by MockServer's ring buffer.
- Not changed: MockServer's own `/mockserver/retrieve` behavior, `maxLogEntries` configuration, or the per-tick cost of fetching MockServer's full current log (no cursor/time-range fetch API exists there - see the 2026-08-09 study). This proposal does not reduce that per-tick fetch/parse cost; it only changes what `mock-ui` does with the result once fetched.

## Capabilities

### New Capabilities
(none - this modifies the existing Recent Requests behavior within `mock-management-ui`)

### Modified Capabilities
- `mock-management-ui`: Recent Requests history becomes a locally accumulating record instead of a live mirror of MockServer's current log - affects "Web UI shows recent requests received by MockServer" (history source and "no copy the web interface keeps" language), the time-range/pagination "oldest retained" scenarios (now bounded by `mock-ui`'s own retention, not only MockServer's), and adds a new requirement that Recent Requests history stays reliable (no silent loss of previously-observed entries) for as long as `mock-ui` keeps running, independent of MockServer's own log eviction. Restart survival is explicitly out of scope.

## Impact

- **Code**: `mock-ui/app.py` - `Target` class (replace `history_snapshot`/`history_lock` with a SQLite connection/handle per target), `_poll_history_once`, `_get_history_snapshot`, `list_requests`, `stream_requests`, `_detect_history_reset` (reset-detection logic needs to work against the SQLite store, not an in-memory list).
- **Dependencies**: Python's stdlib `sqlite3` (no new external dependency).
- **Storage**: one SQLite file per configured `Target` (multi-target support from `MOCKSERVER_TARGETS` already exists), written to a local/ephemeral data directory - no PVC or other durable volume, since surviving a restart is not a goal.
- **Deployment**: no new k8s volume needed. `k8s/overlays/with-mockserver/mock-ui-deployment.yaml` is unchanged apart from optionally pointing the data-directory env var at a writable path in the existing container filesystem (or an `emptyDir`, if the container's default filesystem isn't writable); local/docker-compose usage similarly needs no new mount.
- **Spec**: `openspec/specs/mock-management-ui/spec.md` requirements listed above under Modified Capabilities.
- **Out of scope**: MockServer's own log retention/configuration, reducing per-tick fetch cost from MockServer, moving off Flask's dev server, persisting history across a `mock-ui` restart/reschedule.
