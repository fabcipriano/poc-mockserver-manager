## Why

`mock-ui` hardcodes three runtime settings - request-history page size, live-tail poll interval, and SSE heartbeat interval - as Python constants in `app.py`, and its `MOCKSERVER_URL` single-target fallback (already environment-driven) is undocumented as a deployment knob and absent from the POC's own Kubernetes manifest. Migrating this POC to a real environment means someone else will need to tune these - a larger deployment may want a longer history window or a different poll cadence, and a single-MockServer environment needs to know `MOCKSERVER_URL` is how to configure that without `MOCKSERVER_TARGETS`. Today that requires editing `app.py` and rebuilding the image. This change makes all four settings configurable purely through environment variables, wires them into the POC's Kubernetes manifest the same way `MOCKSERVER_TARGETS` already is, and documents them in the README so a migrator has one place to look.

## What Changes

- `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, and `HEARTBEAT_INTERVAL_SECONDS` become environment-variable-configurable in `mock-ui/app.py`, read once at startup with the current hardcoded values (`40`, `1`, `15`) as defaults, so an unconfigured deployment behaves exactly as it does today.
- A malformed value (non-integer, or an out-of-range value such as zero/negative) for any of these three fails startup fast with a specific error, matching the existing `MOCKSERVER_TARGETS` fail-fast convention.
- `k8s/overlays/with-mockserver/mock-ui-deployment.yaml` gains explicit `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, and `HEARTBEAT_INTERVAL_SECONDS` entries (set to the current defaults) alongside the existing `MOCKSERVER_TARGETS`, so the POC's own manifest doubles as a working example of every tunable a migrator needs to carry over.
- README gains a consolidated "Configuring mock-ui" reference documenting all four variables (`MOCKSERVER_URL`, `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, `HEARTBEAT_INTERVAL_SECONDS`, alongside the already-documented `MOCKSERVER_TARGETS`) - what each controls, its default, and (for `MOCKSERVER_URL`) that it only takes effect when `MOCKSERVER_TARGETS` is unset.
- `MOCKSERVER_URL` itself is not added to the POC's manifest: `MOCKSERVER_TARGETS` is set there and takes precedence, so an inert `MOCKSERVER_URL` entry would be dead configuration. It stays documented as the fallback path for a single-target deployment that doesn't set `MOCKSERVER_TARGETS` at all.

## Capabilities

### New Capabilities
(none - this change extends an existing capability rather than introducing a new one)

### Modified Capabilities
- `mock-management-ui`: mock-ui's runtime configuration surface extends beyond MockServer targets to also cover request-history page size, live-tail poll interval, and heartbeat interval, all settable via environment variables with documented defaults.

## Impact

- `mock-ui/app.py`: `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, `HEARTBEAT_INTERVAL_SECONDS` move from bare constants to `os.environ.get`-sourced values with validation, following the existing `_parse_targets`/fail-fast pattern.
- `mock-ui/test_app.py`: new tests for parsing/validating the three new environment variables (valid override, invalid value, unset/default).
- `k8s/overlays/with-mockserver/mock-ui-deployment.yaml`: three new `env` entries.
- `README.md`: new consolidated environment-variable reference section covering all five `mock-ui` variables (`MOCKSERVER_TARGETS`, `MOCKSERVER_URL`, `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, `HEARTBEAT_INTERVAL_SECONDS`).
