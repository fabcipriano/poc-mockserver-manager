## Context

Today `mock-ui/app.py` hardcodes a single MockServer target: one `MOCKSERVER_URL` constant, one global history-poller thread, one global `_history_snapshot`/`_history_lock`/`_history_reset_generation`, and every route (`/mock-ui/api/mocks*`, `/mock-ui/api/requests*`) talks to that one target. The POC (`k8s/overlays/with-mockserver/`) matches: one `mockserver` Deployment/Service/PVC/ConfigMap, one `gateway`, one `backend` (restful-booker), and one Ingress path (`/`) that routes to `mockserver`.

Production will run three independent MockServer instances (gateway public, private, product). See proposal.md - Why/What Changes for the motivation; this document covers how mock-ui and the POC get there.

## Goals / Non-Goals

**Goals:**
- Turn the single hardcoded MockServer target into a configurable list of targets, read from environment variables at process startup.
- Preserve the existing shared-poller design (one background thread does the polling regardless of viewer count) - just make it "one thread per target" instead of "one thread total".
- Give the existing single-target deployment (`MOCKSERVER_URL` only) a zero-config migration path.
- Extend the POC to three genuinely independent MockServer instances so the above can be demoed and tested end-to-end.

**Non-Goals:**
- Authentication/authorization for the target selector or for mock-ui generally - this POC has none today and this change doesn't add any.
- Cross-target operations (e.g., copying a mock from one target to another, or a combined view across targets) - the selector switches the whole UI to one target at a time.
- Modeling three separate ALBs/Ingresses in the POC - production has genuinely separate entrypoints per gateway, but the POC keeps a single Ingress with per-topology path prefixes to avoid requiring three sets of local DNS/ingress setup.
- Changing how an individual MockServer instance works internally (persistence, catch-all seeding, expectation matching) - that machinery is unchanged, just instantiated three times.

## Decisions

### Configuration shape: `MOCKSERVER_TARGETS` as JSON, with a fallback to the old `MOCKSERVER_URL`

`MOCKSERVER_TARGETS` is a JSON array of `{"id": "...", "label": "...", "url": "..."}` objects, e.g.:

```
MOCKSERVER_TARGETS=[{"id":"public","label":"Gateway Public","url":"http://mockserver-public"},{"id":"private","label":"Gateway Private","url":"http://mockserver-private"},{"id":"product","label":"Gateway Product","url":"http://mockserver"}]
```

`id` is the stable identifier used in API query params and persisted client-side; `label` is what the selector displays; `url` is the base URL `app.py` already knows how to talk to (same shape `MOCKSERVER_URL` is today).

If `MOCKSERVER_TARGETS` is unset, `app.py` falls back to a single target built from `MOCKSERVER_URL` (default `http://mockserver`, unchanged from today) with `id="default"`, `label="Default"`. This is the **BREAKING** change's mitigation from proposal.md: an existing deployment that only sets `MOCKSERVER_URL` keeps working unchanged, including the API surface for callers that never pass `server=`.

If `MOCKSERVER_TARGETS` is set but fails to parse (invalid JSON, missing `id`/`label`/`url`, or duplicate `id`s), `app.py` logs the specific error and exits at startup rather than starting with a partially-broken target list - a misconfigured deployment should fail loudly in its logs/readiness probe, not silently serve zero or wrong targets.

**Alternatives considered:**
- A delimited string format (e.g. `id:label:url,id:label:url`) - rejected because labels are free text ("Gateway Public") that would need its own escaping rule, and JSON is already a first-class value type in every place this needs to be set (Kubernetes env var, `.env`, shell export) without extra parsing code beyond `json.loads`.
- One `MOCKSERVER_URL_<ID>` env var per target - rejected because it can't express the display label, and enumerating "which env vars are targets" requires prefix-scanning `os.environ`, which is fragile compared to one variable holding the whole list.

### Per-target poller: parametrize today's shared-poller module state into a `Target` registry

Replace the module-level `_history_lock` / `_history_snapshot` / `_history_reset_generation` globals with a small `Target` object (id, label, url, plus its own lock/snapshot/reset-generation) held in a `TARGETS: dict[str, Target]` built once at startup from the parsed config. `_history_poller_loop` becomes a function of one `Target`, and `main` starts one daemon thread per target instead of one thread total - directly matching the user's "one thread polling per MockServer" request, and keeping the existing property that N browser tabs viewing the same target still cost one poll per target per tick, not one per tab. `_mockserver_put` gains a `target` parameter (the base URL it hits today) instead of closing over the module-level constant.

Every route that currently assumes the single global target (`list_mocks`, `create_mock`, `update_mock`, `delete_mock`, `list_requests`, `stream_requests`) gains a `server` query parameter, resolved against `TARGETS`; a request for an unknown `server` id gets a 404 with the known ids. Omitting `server` uses the first configured target (stable order = the order targets appear in `MOCKSERVER_TARGETS`, or the single fallback target) so existing direct API callers (scripts, curl, tests) that don't know about multi-target keep working against "whichever target is configured first."

Adds a `GET /mock-ui/api/servers` endpoint returning each target's `id` and `label` (not `url` - the frontend has no need to know internal Service DNS names, and there's no reason to expose more of the cluster's internal topology than the selector needs).

**Alternatives considered:**
- Keep one global poller and have it round-robin across targets - rejected: it would make each target's effective poll interval scale with the number of targets, unlike today's fixed 1s cadence per target, and it re-adds a single point of contention the current design deliberately avoids.
- A poller process/thread pool sized independently of target count - rejected as unnecessary complexity; three (or a handful more) daemon threads is exactly the concurrency primitive Python's `threading` module is for, and it mirrors the existing single-thread pattern almost exactly (see fix-recent-requests-stale-rows/design.md for why this codebase already leans on a single always-retrying daemon thread rather than a supervised pool).

### Frontend: a persistent target selector, state kept in the URL query string

`index.html` gains a `<select>` (labeled "MockServer") in the sidebar, populated from `GET /mock-ui/api/servers`, visible on every page (not inside any one page's `<section>`). `app.js` keeps the selected target id in a `currentServer` variable, threads it as `?server=<id>` onto every API call (mocks CRUD, requests list, requests stream), and re-triggers `loadMocks()` / `loadRequestHistory()` / reconnects the SSE stream whenever the selection changes - the same re-fetch/reconnect path `syncRequestsPageStream` already uses for hash-based page navigation, just keyed on target instead of page.

Selection persists via the URL query string (`?server=public#requests`) rather than `localStorage`: it's visible, shareable (a developer can send a teammate a link to "the private target's Recent Requests page"), and consistent with how page routing already works via `location.hash` in this app - no new persistence mechanism to introduce. On load, `app.js` reads `?server=` if present and valid (falls back to the first entry from `/api/servers` otherwise, including on an unrecognized id).

**Alternatives considered:**
- `localStorage` - rejected: not shareable via link, and would silently keep showing a developer's last-used target on a machine even after an incognito/clean load, which is more surprising than a URL that says explicitly what it's pointing at.
- A separate route/page per target (`/mock-ui/public/...`) - rejected: it would fragment page state (the create-mock form, filters, etc.) per target-times-page combination and complicate the SSE/polling wiring for no real benefit over a single selector.

### POC topology: keep `mockserver`/`gateway`/`backend` as-is for "product", add two minimal siblings for "public"/"private"

The existing `mockserver` Deployment/Service/PVC/ConfigMap, `gateway`, and `backend` (restful-booker) are left with their current resource names and are treated as the **product** target (`MOCKSERVER_TARGETS` entry `id=product`, `url=http://mockserver`) - avoids renaming anything the README, scripts (`MOCKSERVER_URL` default in `scripts/add-mock.sh`), or existing Ingress path already reference.

Two new, minimal siblings are added for **public** and **private**:
- `backend-public/` and `backend-private/`: two small Express apps (same pattern as `gateway/server.js` but not proxying anything), each hardcoding one or two JSON routes (e.g. `GET /health`, `GET /items`) with a fixed response body - deliberately not a real upstream application, per proposal.md's simplification.
- `mockserver-public` / `mockserver-private`: new Deployment/Service/PVC/ConfigMap pairs, identical in shape to the existing `mockserver-*` resources, each with its own catch-all-forward ConfigMap pointed at `backend-public`/`backend-private` instead of `gateway`.

`mock-ui-deployment.yaml`'s env changes from `MOCKSERVER_URL=http://mockserver` to `MOCKSERVER_TARGETS=[...]` listing all three (`id`s `public`/`private`/`product`, `url`s the in-cluster Service DNS names above).

The Ingress patch adds `/public` and `/private` path prefixes routed to `mockserver-public`/`mockserver-private` respectively, alongside the existing `/` (unprefixed, product) and `/mock-ui` paths - covering the "all three topologies reachable through the single POC entrypoint" spec requirement without standing up separate Ingress objects.

**Alternatives considered:**
- Renaming the existing `mockserver`/`gateway`/`backend` resources to a `*-product` suffix for symmetry with the two new ones - rejected: it's a larger, purely-cosmetic diff across the README, scripts, and existing manifests for no behavior change, and this POC's naming asymmetry (one unprefixed "default-looking" target plus two explicitly-named new ones) is an accepted, documented trade-off rather than an oversight.
- Making all three topologies use the simplified hardcoded-backend pattern (dropping restful-booker) - rejected: the existing product topology's realism (real REST API, auth, multiple resource routes) is valuable and already built; the ask was to add two *more*, simpler targets, not to simplify the existing one.

## Risks / Trade-offs

- **[Risk]** A misconfigured `MOCKSERVER_TARGETS` (e.g. hand-edited YAML with a JSON typo) takes mock-ui down entirely, including for targets that were configured correctly. → **Mitigation**: fail fast at startup with a specific parse error in the logs (see Decisions above) so the cause is immediately visible via `kubectl logs`/readiness-probe failure, rather than serving a confusing partial state.
- **[Risk]** Three MockServer instances instead of one roughly triples the PVCs, ConfigMaps, and pods the POC's local cluster needs. → **Mitigation**: the two new backends and their MockServer instances are intentionally tiny (no real app, minimal image), so the added resource footprint is small relative to the existing restful-booker-backed instance; `scripts/create-cluster.sh`/install docs get a note if `kind`'s default resource limits need adjusting.
- **[Risk]** Existing `mock-ui/test_app.py` tests patch module-level globals (`app_module._history_snapshot`, etc.) directly - see `HistoryResetDetectionTests._run_poll`. Moving to a per-target object breaks those patches. → **Mitigation**: update the tests to construct/patch a `Target` instance instead of module globals as part of this change (tracked in tasks.md); this is an internal test-only migration, not a spec change.
- **[Trade-off]** Selecting a target via URL query string means an old bookmark/link to `/mock-ui/#requests` (no `server=`) silently falls back to "whichever target is first" rather than erroring - accepted, since it matches today's zero-config single-target behavior and a hard error on a missing param would regress the common case.

## Migration Plan

1. Ship `app.py`'s target-registry/multi-poller support with the `MOCKSERVER_URL`-fallback behavior first - existing deployments that set only `MOCKSERVER_URL` see no behavior change.
2. Ship the frontend selector - with a single fallback target configured, the selector still renders (one option, "Default"), so this is safe to deploy without also switching to multi-target config.
3. Roll out the POC's two new targets and the `MOCKSERVER_TARGETS` env var change to `mock-ui-deployment.yaml` together, since the new env var is only useful once the new targets exist.
4. Rollback at any point is a straight revert of `mock-ui-deployment.yaml`'s env (back to `MOCKSERVER_URL`) plus removing the new K8s resources - `app.py`'s fallback path means the older env shape keeps working throughout.
