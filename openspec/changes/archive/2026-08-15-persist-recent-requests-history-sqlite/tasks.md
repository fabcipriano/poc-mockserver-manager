## 1. SQLite-backed history store

- [x] 1.1 Add a per-target SQLite schema: a `requests` table with an `INTEGER PRIMARY KEY` (autoincrement) rowid, the existing history-entry fields (timestamp, method, path, status code, mocked flag, request/response headers and body), and a `UNIQUE` constraint on `(timestamp, method, path, response_status_code)` for dedup.
- [x] 1.2 Add a data-directory/file-path resolution helper: one SQLite file per `Target.id`, under a configurable base directory (env var, following the existing `_parse_positive_int_env`-style config pattern), created on first use if missing. Defaults to a local/ephemeral path (e.g. within the container's writable filesystem) - no PVC or other durable volume is required, since history is not expected to survive a restart.
- [x] 1.3 Replace `Target.history_snapshot`/`history_lock` with a SQLite connection/handle appropriate for the per-target poller thread (e.g. one connection per poller thread, WAL mode for concurrent reads from request handlers while the poller writes).

## 2. Poller: upsert instead of replace

- [x] 2.1 Change `_poll_history_once` to upsert each fetched entry into the target's SQLite table (`INSERT OR IGNORE`) instead of replacing `target.history_snapshot` wholesale.
- [x] 2.2 Add retention pruning at the end of each poll tick: delete oldest rows by `rowid` past the configured row cap (default 120,000; env-configurable per design.md), in the same transaction as that tick's upserts.
- [x] 2.3 Update `_detect_history_reset` to compare the newly-fetched MockServer batch against what was last fetched *from MockServer* (not against the full accumulated persisted history), so a genuine MockServer-side log reset is still detected and still triggers the SSE `history-reset` event.

## 3. Read paths: SQLite-backed queries

- [x] 3.1 Rewrite `list_requests` (`GET /mock-ui/api/requests`) to query SQLite directly: path/mocked/time-range filters as `WHERE` clauses, `before` pagination cursor as a `rowid`-based comparison instead of `timestamp` string comparison, ordered by `rowid` descending, limited to `REQUEST_HISTORY_LIMIT` (+1 for `hasMore` detection).
- [x] 3.2 Update `oldestAvailableTimestamp`/`rangeTruncated` computation to reflect `mock-ui`'s own persisted retention boundary (oldest row still in SQLite) rather than MockServer's currently-retained oldest entry.
- [x] 3.3 Rewrite `stream_requests`' (`GET /mock-ui/api/requests/stream`) new-entries-since-last-tick query to select rows with `rowid` greater than the last-seen `rowid` from SQLite, applying the stream's path/mocked filters, in place of scanning the in-memory snapshot.
- [x] 3.4 Update the reset-detection generation check in `event_stream()` to keep working against the (now SQLite-backed) reset signal from step 2.3.

## 4. Retention configuration

- [x] 4.1 Add `REQUEST_HISTORY_RETENTION_ROWS` (or equivalent) env var, parsed with the existing `_parse_positive_int_env` helper, default 120,000, documented alongside the other `mock-ui` timing/config env vars.
- [x] 4.2 Confirm the default retention cap is comfortably above `REQUEST_HISTORY_LIMIT`'s default and large enough that the reproduced load-test scenario (100,000 requests, `/booking/20123` lookup) no longer loses the target entry at default settings. Confirmed by running the real `_poll_history_once`/upsert/prune path in-process against a 100,000-distinct-request simulation of the load test: at the original 50,000 default, `/booking/20123` was pruned by `mock-ui`'s own cap (see note below); at the corrected 120,000 default, all 100,000 rows fit under the cap and `/booking/20123` remains queryable.

## 5. Deployment (k8s)

- [x] 5.1 Confirm `mock-ui`'s data-directory path (task 1.2) resolves to a writable location on the pod's existing ephemeral filesystem by default; add an `emptyDir` volume in `k8s/overlays/with-mockserver/mock-ui-deployment.yaml` only if the container's default filesystem turns out not to be writable. No PVC is added - history is not expected to survive a pod restart/reschedule. Confirmed: `mock-ui`'s image (`mock-ui/Dockerfile`) runs as root with no `readOnlyRootFilesystem`, and the default `REQUEST_HISTORY_DATA_DIR` (`/tmp/mock-ui-request-history`) is writable without any extra volume - no `emptyDir` needed. Also documented the two new env vars in `mock-ui-deployment.yaml` and README.
- [x] 5.2 Verify `mock-ui` starts cleanly with an empty data directory (first boot / after a restart) and correctly recreates each target's SQLite file. Verified locally: ran `app.py` twice against the same initially-empty `REQUEST_HISTORY_DATA_DIR` (process killed between runs to simulate a restart) - `/mock-ui/healthz` and `/mock-ui/api/requests` both return 200 on a fresh directory, and the target's `.db` file is created lazily on first use, not required to pre-exist.

## 6. Tests

- [x] 6.1 Update/extend `mock-ui/test_app.py` for the new SQLite-backed `list_requests`/`stream_requests` behavior (pagination cursor, filters, retention pruning, dedup on repeated poll ticks).
- [x] 6.2 Add a test for the specific reproduced bug: seed more entries than MockServer's simulated retention would keep, poll multiple times, and confirm an early entry remains queryable from `mock-ui` after MockServer "forgets" it (simulate via a fake/mocked MockServer response sequence).
- [x] 6.3 Add a test confirming per-target isolation: two targets' SQLite stores don't leak entries into each other.
- [x] 6.4 Re-run `scripts/load-test-recent-requests.sh` manually against a local `mock-ui` + MockServer (kind cluster) and confirm `/booking/20123` (or an equivalent mid-range entry) is found after the full run. Rebuilt and reloaded the `mock-ui` image into the existing `mockserver-poc` kind cluster, applied the updated deployment (new env vars), rolled the pod, then ran the full 100,000-request load test against `http://localhost:8080`. `GET /mock-ui/api/requests?server=product&path=/booking/20123` found the entry afterward (`mocked: false`, 404 from the real backend, as expected for an ID not seeded) - the exact bug `scripts/load-test-recent-requests.sh` was written to reproduce is fixed end-to-end, not just in the in-process simulation.

## 7. Spec sync

- [x] 7.1 Confirm the delta in `specs/mock-management-ui/spec.md` under this change accurately reflects the implemented behavior before archiving (run `openspec validate` for this change). `openspec validate persist-recent-requests-history-sqlite --strict` passes; the spec delta's "locally accumulated, not durably persisted across restarts" framing matches the implementation.

## Note: retention-default discrepancy found during implementation, now resolved

A direct in-process simulation of the reproduced load-test scenario (100,000 poll-tick upserts,
one per `/booking/N`, all genuinely distinct dedup keys) against the real `_poll_history_once`
upsert/prune path showed `/booking/20123` does **not** survive at the original 50,000-row default:
since mock-ui's own row cap (50,000) was smaller than the load test's 100,000 distinct requests,
retention pruning kept only the newest 50,000 rows (`/booking/50001`..`/booking/100000`) by the end
of the run - `/booking/20123` was pruned by mock-ui's *own* cap, independent of anything MockServer
does. This contradicted design.md's stated rationale for the 50,000 default. Raised to the user,
who chose to raise the default instead of lowering the bar on the load-test scenario - the default
is now 120,000 (see design.md and app.py), confirmed via the same in-process simulation to keep all
100,000 rows under the cap, and subsequently confirmed for real: `scripts/load-test-recent-requests.sh`
was run against a live `kind` cluster (rebuilt `mock-ui` image, updated deployment, full 100,000-request
run), and `/booking/20123` was found afterward via the real `/mock-ui/api/requests` endpoint (see 6.4).
