## Why

MockServer's built-in Dashboard (bundled with the `mockserver/mockserver:5.15.0` image this
POC already runs, served at `/mockserver/dashboard`) shows exactly one thing `mock-ui`'s
Recent Requests page can't: why a specific request didn't match any expectation, broken down
matcher-property by matcher-property, with the full log lifecycle for that request grouped
together. That's a real, recurring debugging need ("I created a mock and it's not matching -
why?") that today has no answer in `mock-ui` short of reasoning about the matcher rules by
hand. A study (`docs/studies/2026-08-10-mockserver-dashboard-vs-recent-requests.md`) confirmed
this by hitting our own running MockServer pod directly: the Dashboard is already reachable at
`/mockserver/dashboard` through the existing ALB stand-in Ingress with no new routing, so
surfacing it costs a link, not a build.

## What Changes

- Add a fifth sidebar destination, **MockServer Dashboard**, alongside Create Mock, List
  Mocks, Recent Requests, and Help.
- Selecting it opens MockServer's own Dashboard (`/mockserver/dashboard`) in a new browser
  tab - not embedded or iframed - since it's a separate vendor SPA with its own client-side
  routing and its own WebSocket endpoint (`/_mockserver_ui_websocket`) that `mock-ui` doesn't
  own or control.
- Add a short explanation to the Help page: what the MockServer Dashboard link is for (seeing
  why a request didn't match any mock) and that it's a separate, unauthenticated vendor tool
  in this POC (consistent with everything else here having no auth), not a page `mock-ui` is
  responsible for keeping working.
- Explicitly **not** a replacement for Recent Requests: no change to Recent Requests'
  filtering, pagination, live tail, or any other existing behavior.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mock-management-ui`: the sidebar navigation requirement gains a fifth destination
  (MockServer Dashboard, opened in a new tab rather than shown in the main content area) and
  the Help page requirement gains an explanation of what that link is for.

## Impact

- `mock-ui/static/index.html`, `mock-ui/static/app.js`, `mock-ui/static/style.css`: add the
  sidebar link/icon and its new-tab behavior; no new client-side page/route needed since it
  navigates away rather than rendering in the content area.
- `mock-ui/app.py`: no changes - `/mockserver/dashboard` is already reachable through the
  existing Ingress `/` rule; `mock-ui` doesn't proxy or serve it.
- Help page content: one short addition.
- No Kubernetes/Ingress changes - `k8s/overlays/with-mockserver/ingress-patch.yaml` already
  routes non-`/mock-ui` traffic to the `mockserver` service, which is how
  `/mockserver/dashboard` already returns 200 today.
