## Why

Today MockServer's expectations live only in JVM memory. Every mock added through `scripts/add-mock.sh` or
the `mock-ui` web interface is gone the moment the `mockserver` pod restarts or gets rescheduled - only the
seeded catch-all forwarding rule comes back, because that alone is baked into a ConfigMap MockServer
re-reads on every boot. For this POC to demonstrate something closer to a real environment, mocks a
developer adds should survive a pod restart, not just live for the lifetime of one container.

## What Changes

- Enable MockServer's built-in JSON persistence (`MOCKSERVER_PERSIST_EXPECTATIONS`,
  `MOCKSERVER_PERSISTED_EXPECTATIONS_PATH` - the property names for the `5.15.0` image this repo pins;
  newer MockServer releases rename these to `..._AS_JSON`/`..._FILE_PATH`), writing to a file on a new
  `PersistentVolumeClaim`
  (`kind`'s default `standard` local-path StorageClass) mounted into the `mockserver` pod, so the current
  set of expectations survives pod restarts and rescheduling.
- Point `MOCKSERVER_INITIALIZATION_JSON_PATH` at that same PVC-backed file, so MockServer reloads whatever
  was persisted (catch-all plus any dev-added mocks) on every boot.
- Add a small init container to the `mockserver` Deployment that seeds the PVC file from the existing
  ConfigMap-defined catch-all rule **only the first time** (i.e., only if the PVC file doesn't exist yet),
  so the catch-all is still guaranteed present on a brand-new volume, without ever overwriting
  already-persisted state on subsequent restarts.
- The existing ConfigMap (`mockserver-init`) keeps its current content and role as the one-time seed
  source; it's no longer read directly by MockServer's own `initializationJsonPath`.
- `scripts/uninstall-mockserver.sh` continues to remove MockServer's Deployment/Service/ConfigMap (and
  `mock-ui`'s) exactly as today, but **does not** delete the new PVC - persisted mocks survive an
  uninstall/reinstall cycle, the same way a real environment's persistent storage wouldn't be wiped just
  because an application was temporarily scaled down. This is called out explicitly in the README so it
  isn't mistaken for a bug.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `mockserver-integration`: adds a requirement that dev-added mock expectations, and the seeded catch-all,
  survive a MockServer pod restart.

## Impact

- Code (new): `k8s/overlays/with-mockserver/mockserver-pvc.yaml`.
- Code (modified): `k8s/overlays/with-mockserver/mockserver-deployment.yaml` (init container, PVC volume
  mount, new/changed env vars), `k8s/overlays/with-mockserver/kustomization.yaml` (add the PVC manifest),
  `README.md` (document persistence behavior and that the PVC outlives uninstall).
- No change to `mock-ui/`, `scripts/add-mock.sh`/`list-mocks.sh`/`delete-mock.sh`, the Ingress, or the
  Gateway/Backend - this only changes what happens to MockServer's own state across restarts.
- No new external dependency - uses MockServer's existing built-in persistence feature and Kubernetes'
  standard PVC mechanism; the init container uses a minimal existing base image (e.g. `busybox`), nothing
  bespoke to build.
