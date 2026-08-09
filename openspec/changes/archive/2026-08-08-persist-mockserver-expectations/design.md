## Context

Today `mockserver-deployment.yaml` sets `MOCKSERVER_INITIALIZATION_JSON_PATH=/config/initializerJson.json`,
pointing at the `mockserver-init` ConfigMap, which contains only the seeded catch-all forwarding rule
(`path: "/.*"`, `priority: 0`, forwards to the `gateway` Service). MockServer keeps all expectations in
memory; nothing a developer adds via `scripts/add-mock.sh` or `mock-ui` is written anywhere durable. On
every pod restart, MockServer re-reads the ConfigMap (unchanged, static) and comes back with only the
catch-all - every dev-added mock is gone. See proposal.md - Why for motivation.

Verified against MockServer's current documentation (not from memory) while researching this change:

- `MOCKSERVER_PERSIST_EXPECTATIONS=true` + `MOCKSERVER_PERSISTED_EXPECTATIONS_PATH=<path>` makes MockServer
  rewrite the **entire** current expectation set to that file "whenever the expectation state is updated
  (i.e. add, clear, expires, etc)" - a full snapshot on every change, not an append-only log and not a
  database. **Correction found during implementation**: MockServer's current docs site names these
  properties `persistExpectationsAsJson`/`persistedExpectationsFilePath` (`MOCKSERVER_..._AS_JSON`/
  `MOCKSERVER_..._FILE_PATH`), but that reflects a newer release than the `mockserver/mockserver:5.15.0`
  image this repo pins. Checked the actual source at the `mockserver-5.15.0` tag: at that version the
  properties are `mockserver.persistExpectations`/`mockserver.persistedExpectationsPath`
  (`MOCKSERVER_PERSIST_EXPECTATIONS`/`MOCKSERVER_PERSISTED_EXPECTATIONS_PATH`, no `_AS_JSON`/`_FILE`
  segment). MockServer logs but does not error on unrecognized `MOCKSERVER_*` env vars, so the wrong names
  produced no error - persistence just silently never activated. This design and the manifest below use the
  version-correct names.
- `MOCKSERVER_INITIALIZATION_JSON_PATH` does support glob patterns for loading multiple files at startup.
  This looked like it might let us skip an init container (load the ConfigMap's catch-all file and the PVC's
  persisted file side by side), but doing so risks loading the catch-all rule twice after the first
  persisted save (since a full-state snapshot written to the PVC file would also already contain the
  catch-all) - whether MockServer's *init loader* treats two expectations with the same declared `id` as
  an upsert (like its REST API does) rather than two entries isn't documented. Rejected in favor of the
  simpler, verifiable approach below (see Decisions).
- A missing/unreadable `initializationJsonPath` file only logs a WARN by default
  (`MOCKSERVER_FAIL_ON_INITIALIZATION_ERROR` defaults to `false`) - not fatal - but this change's design
  doesn't rely on that fallback anyway (see Decisions).
- Kind's cluster already has a default StorageClass available: `standard` (`rancher.io/local-path`,
  `WaitForFirstConsumer` binding), confirmed via `kubectl get storageclass` against the running dev
  cluster.

## Goals / Non-Goals

**Goals:**
- Mock expectations a developer adds (via `scripts/add-mock.sh` or `mock-ui`) survive a `mockserver` pod
  restart or reschedule.
- The seeded catch-all forwarding rule is still guaranteed present after a restart, including on a
  brand-new/empty volume (first install).
- No change to how a developer adds/edits/deletes mocks - `scripts/add-mock.sh`, `mock-ui`, and the raw
  MockServer REST API all keep working exactly as before.
- No change to `mock-ui/`, the Ingress, or the Gateway/Backend.

**Non-Goals:**
- Multi-instance / high-availability MockServer (this POC runs a single replica; the persistence approach
  here - a single `ReadWriteOnce` PVC - does not need to support concurrent writers from multiple pods).
- Cloud blob storage (S3/GCS/Azure) persistence - a local PVC is the right fit for this local kind-based
  POC; blob storage is a reasonable next step for a real cloud deployment but out of scope here.
- Automatic backup/restore or migration tooling for the persisted file - just durability across pod
  restarts within the same cluster.
- Deleting persisted data on `scripts/uninstall-mockserver.sh` - see Decisions.

## Decisions

1. **One persisted file, reused for both `persistedExpectationsPath` and `initializationJsonPath`,
   seeded on first boot only by a dedicated init container** - not the glob-multiple-init-files approach.
   - The init container (a minimal `busybox` image, sharing the PVC and the existing ConfigMap volume with
     the main container) runs a single idempotent check: if the PVC's expectations file doesn't exist yet,
     copy the ConfigMap's catch-all-only JSON into it as the seed; if it already exists (a restart, not a
     first boot), do nothing and leave it alone.
   - The main `mockserver` container then has exactly one `initializationJsonPath`, always pointing at the
     PVC file, which is guaranteed to exist (empty-cluster case handled by the init container) and to
     already contain everything from the previous session (restart case).
   - Alternative considered: point `initializationJsonPath` at a glob covering both the ConfigMap file and
     the PVC file, skipping the init container. Rejected - as noted in Context, this risks double-loading
     the catch-all rule after the first save, based on undocumented init-time id-collision behavior. The
     init-container approach only relies on documented behaviors (full-state persistence, ordinary file
     copy) and is trivial to verify directly.
   - Alternative considered: have the init container run `mockserver`'s own persistence logic in reverse
     (seed via the REST API instead of a raw file copy). Rejected - unnecessary; the ConfigMap's JSON is
     already in the exact file format MockServer's `initializationJsonPath` expects, so a plain file copy
     is sufficient and needs no running MockServer instance to do it.

2. **PVC is not deleted by `scripts/uninstall-mockserver.sh`.**
   - `uninstall-mockserver.sh` already deletes MockServer's Deployment/Service/ConfigMap (and mock-ui's) by
     explicit name, not by tearing down the whole overlay. The PVC is simply left off that list.
   - Alternative considered: delete the PVC too, for a fully clean teardown. Rejected - the entire point of
     this change is that mocks survive disruption; deleting the PVC on every uninstall would make
     "uninstall MockServer, then reinstall it" indistinguishable from today's total-memory-loss behavior,
     defeating the change. A developer who genuinely wants a clean slate can delete the PVC explicitly
     (`kubectl delete pvc mockserver-data -n mockserver-poc`) - documented in the README rather than wired
     into a script, since it's a deliberately rarer, more destructive action than a normal uninstall.

3. **PVC size: a small fixed value (e.g. `100Mi`).** Expectation JSON for dozens (even hundreds) of mocks is
   at most a few hundred KB; `100Mi` leaves generous headroom without over-provisioning kind's local-path
   storage.

4. **No `storageClassName` set on the PVC** - lets it use the cluster's default StorageClass (`standard` on
   kind). Keeps the manifest portable to any cluster with a default StorageClass rather than hardcoding
   `standard`, which is kind-specific.

5. **Init container explicitly `chmod 666`s the persisted-expectations file**, in addition to (not instead
   of) a pod-level `securityContext.fsGroup: 65532`. Found during implementation: the `mockserver` image
   runs as `gcr.io/distroless/java17:nonroot` (uid/gid 65532), and `fsGroup` alone left the file
   `root:root` mode `644` - unwritable by that user - confirmed by inspecting the file through a temporary
   debug sidecar sharing the same PVC mount. This is a known Kubernetes limitation: fsGroup ownership
   management is not applied to hostPath-backed volumes, and kind's default StorageClass
   (`rancher.io/local-path`) provisions exactly that under the hood. `chmod 666` from the (root-running)
   init container sidesteps the issue regardless of storage provisioner; `fsGroup` is kept too since it's
   free and would help on a real CSI-backed cluster where it *is* honored.

## Risks / Trade-offs

- [Undocumented interaction if a future MockServer upgrade changes init-time upsert-by-id semantics for
  multiple init files.] -> Mitigation: not applicable to the chosen design - only one init path is ever
  configured, so this class of ambiguity doesn't arise.
- [`WaitForFirstConsumer` binding mode means the PVC isn't actually bound until the first pod that mounts
  it is scheduled.] -> Mitigation: expected and fine - the `mockserver` Deployment's pod is exactly that
  first consumer; no separate provisioning step is needed.
- [A developer expects `scripts/uninstall-mockserver.sh` to fully reset state, per how it behaves today.]
  -> Mitigation: documented explicitly in the README (this change updates the "Known gaps"/relevant section
  to say persisted mocks outlive uninstall, and how to delete the PVC manually if a clean slate is wanted).
- [Full-file-rewrite-per-change persistence could add latency under very high mock churn.] -> Already
  covered by prior research in this project's history: irrelevant at this POC's scale (dozens of mocks);
  not re-litigated here.

## Migration Plan

Net-new PVC and init container; no existing data to migrate (today there is no persisted state at all).
Rollout is `kubectl apply -k k8s/overlays/with-mockserver` (via `scripts/install-mockserver.sh`), which
creates the PVC alongside the updated Deployment. Rollback is reverting this change's manifests and
re-applying; the orphaned PVC can be deleted manually if desired
(`kubectl delete pvc mockserver-data -n mockserver-poc`).
