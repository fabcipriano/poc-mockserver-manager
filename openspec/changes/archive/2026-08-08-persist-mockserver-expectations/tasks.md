## 1. Persistent volume

- [x] 1.1 Create `k8s/overlays/with-mockserver/mockserver-pvc.yaml`: a `PersistentVolumeClaim` named `mockserver-data`, `ReadWriteOnce`, `100Mi` request, no `storageClassName` (use the cluster default)
- [x] 1.2 Add `mockserver-pvc.yaml` to `k8s/overlays/with-mockserver/kustomization.yaml`'s `resources`

## 2. Seed-on-first-boot init container

- [x] 2.1 In `k8s/overlays/with-mockserver/mockserver-deployment.yaml`, add an `initContainer` (minimal `busybox` image) that mounts both the existing `init-config` ConfigMap volume (read-only, at `/config`) and the new PVC (at `/data`), and runs a shell command that copies `/config/initializerJson.json` to `/data/persistedExpectations.json` only if the destination doesn't already exist
- [x] 2.2 Add a `volumeMounts` entry for the new PVC at `/data` on the main `mockserver` container
- [x] 2.3 Add a `volumes` entry referencing the new `mockserver-data` PVC (alongside the existing `init-config` ConfigMap volume, which the init container still needs)
- [x] 2.4 *(added during verification)* Add `chmod 666 /data/persistedExpectations.json` to the init container script (unconditionally, after the create-if-missing check), and a pod-level `securityContext.fsGroup: 65532` - see note below

**Correction found during verification (tasks 5.2/5.3):** the `mockserver` image runs as
`gcr.io/distroless/java17:nonroot` (uid/gid 65532). `fsGroup: 65532` alone did not make the PVC file
writable by that user - confirmed by inspection (via a temporary debug sidecar sharing the same PVC mount)
that the file stayed owned `root:root`, mode `644`, even after a pod restart with `fsGroup` set. This is a
known Kubernetes limitation: fsGroup ownership management is not applied to hostPath-backed volumes, and
kind's default StorageClass (`rancher.io/local-path`) provisions exactly that under the hood. The actual
fix is the init container's explicit `chmod 666` on the file, which is provisioner-agnostic. Kept `fsGroup`
in the manifest anyway (harmless, and would help on a real CSI-backed cluster where it *is* honored), but
the `chmod` is what makes this work here - confirmed MockServer's persistence write succeeds with no
`SEVERE ... Permission denied` in its logs after this fix, and that a mock added before a pod restart is
still active after it (see 5.3).

## 3. MockServer persistence configuration

- [x] 3.1 Change `MOCKSERVER_INITIALIZATION_JSON_PATH` on the main `mockserver` container from `/config/initializerJson.json` to `/data/persistedExpectations.json`
- [x] 3.2 Add env var `MOCKSERVER_PERSIST_EXPECTATIONS=true` (corrected from `MOCKSERVER_PERSIST_EXPECTATIONS_AS_JSON` after verification - see note below)
- [x] 3.3 Add env var `MOCKSERVER_PERSISTED_EXPECTATIONS_PATH=/data/persistedExpectations.json` (corrected from `MOCKSERVER_PERSISTED_EXPECTATIONS_FILE_PATH`)

**Correction found during verification (task 5.3):** the property names in the original design
(`MOCKSERVER_PERSIST_EXPECTATIONS_AS_JSON` / `MOCKSERVER_PERSISTED_EXPECTATIONS_FILE_PATH`) came from
MockServer's current docs site, but this repo pins `mockserver/mockserver:5.15.0`, an older release. Checked
the actual source at the `mockserver-5.15.0` tag: at that version the properties are named
`MOCKSERVER_PERSIST_EXPECTATIONS` and `MOCKSERVER_PERSISTED_EXPECTATIONS_PATH` (renamed in a later
MockServer release to add `_AS_JSON`/`_FILE`). MockServer silently ignores unrecognized `MOCKSERVER_*` env
vars rather than erroring, so the wrong names produced no error - persistence just silently never activated.
Confirmed the corrected names work end-to-end (see 5.3).

## 4. Documentation

- [x] 4.1 Update `README.md` to document that mock expectations now survive a MockServer pod restart, backed by a PVC
- [x] 4.2 Document that `scripts/uninstall-mockserver.sh` does **not** delete the PVC - persisted mocks survive an uninstall/reinstall cycle - and give the manual command to fully reset (`kubectl delete pvc mockserver-data -n mockserver-poc`)

## 5. Verification

- [x] 5.1 Fresh install (`scripts/install-mockserver.sh` against a cluster where the PVC doesn't exist yet): confirmed the catch-all forwarding rule is active (`curl /ping` through the Ingress returns the catch-all's forwarded response) and the init container's log shows it seeded `/data/persistedExpectations.json` from the ConfigMap. (The `mockserver` image has no shell/`cat` - distroless `nonroot` - so verification used MockServer's own `retrieve` API and the init container's logs instead of `kubectl exec ... cat`, which is more authoritative anyway.)
- [x] 5.2 Added a mock via MockServer's REST API directly (equivalent to what `add-mock.sh`/`mock-ui` send); confirmed no `SEVERE ... Permission denied` in the `mockserver` container's logs after the chmod fix (task 2.4) - i.e., the persistence write to `/data/persistedExpectations.json` actually succeeded
- [x] 5.3 Deleted the `mockserver` pod (`kubectl delete pod -l app=mockserver -n mockserver-poc`) to force a restart without touching the PVC; confirmed on the new pod that the previously added mock (`GET /booking/1`) is still active - `curl http://localhost:8080/booking/1` returns the mocked body - and the catch-all still forwards `/ping`
- [x] 5.4 Ran `scripts/uninstall-mockserver.sh` then `scripts/install-mockserver.sh` again; confirmed the PVC was untouched (`kubectl apply` reported `persistentvolumeclaim/mockserver-data unchanged`) and the mock added earlier is active again (`curl /booking/1` returns the mocked body) without being re-added
- [x] 5.5 Manually deleted the PVC (`kubectl delete pvc mockserver-data -n mockserver-poc`) and reinstalled; confirmed a genuine full reset - `kubectl apply` reported `persistentvolumeclaim/mockserver-data created` (fresh), `/booking/1` returned real backend data (mock gone), and the catch-all reseeded and still forwards `/ping`
