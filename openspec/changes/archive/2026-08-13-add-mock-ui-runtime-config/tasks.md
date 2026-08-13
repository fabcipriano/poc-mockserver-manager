## 1. mock-ui configuration

- [x] 1.1 In `mock-ui/app.py`, replace the `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, `HEARTBEAT_INTERVAL_SECONDS` constants with values read from environment variables of the same name, defaulting to their current values (`40`, `1`, `15`) when unset.
- [x] 1.2 Validate each parsed value is a positive integer; on failure, log a specific error naming the variable and the invalid value, then exit at startup (mirroring `_parse_targets`'s fail-fast behavior).

## 2. Tests

- [x] 2.1 Add tests to `mock-ui/test_app.py` covering: a valid override of each new variable takes effect, an unset variable keeps the current default, and an invalid value (non-integer, zero, negative) exits at startup with a clear error.

## 3. Kubernetes manifest

- [x] 3.1 Add `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, and `HEARTBEAT_INTERVAL_SECONDS` env entries (set to the current defaults) to `k8s/overlays/with-mockserver/mock-ui-deployment.yaml`, alongside the existing `MOCKSERVER_TARGETS` entry.

## 4. Documentation

- [x] 4.1 Add a consolidated "Configuring mock-ui" environment-variable reference to `README.md` covering `MOCKSERVER_TARGETS`, `MOCKSERVER_URL`, `REQUEST_HISTORY_LIMIT`, `REQUEST_STREAM_POLL_SECONDS`, and `HEARTBEAT_INTERVAL_SECONDS` - what each controls, its default, and that `MOCKSERVER_URL` only takes effect when `MOCKSERVER_TARGETS` is unset.
