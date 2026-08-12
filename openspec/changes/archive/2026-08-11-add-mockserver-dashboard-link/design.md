## Context

See `proposal.md` - Why, and the underlying study at
`docs/studies/2026-08-10-mockserver-dashboard-vs-recent-requests.md` for the full comparison
and evidence. The two facts that shape this design, both verified against the running POC
rather than assumed:

- MockServer's Dashboard is already served at `/mockserver/dashboard` by the
  `mockserver/mockserver:5.15.0` image this POC pins, and is already reachable at that path
  through the existing ALB stand-in Ingress (`k8s/overlays/with-mockserver/ingress-patch.yaml`
  routes everything not under `/mock-ui` to the `mockserver` service).
- It's a separate, self-contained SPA (its own webpack bundle, its own client-side routing,
  its own WebSocket at `/_mockserver_ui_websocket`) that `mock-ui` has never proxied, embedded,
  or otherwise depended on.

## Goals / Non-Goals

**Goals:**
- Make the MockServer Dashboard discoverable from `mock-ui` for developers who need to
  understand why a request didn't match a mock.
- Keep the change purely additive to `mock-ui`'s static frontend - no new backend route, no
  new Ingress rule, no dependency on MockServer's internal implementation.

**Non-Goals:**
- Embedding, iframing, or reverse-proxying the Dashboard's UI into `mock-ui`'s own layout.
- Replicating any Dashboard functionality (matching diagnostics, log correlation) inside
  `mock-ui` itself - out of scope per the study's verdict.
- Making the link's target configurable per-environment beyond what's needed for this POC's
  single-entrypoint architecture (see Decisions).

## Decisions

**Link out via a plain `<a>` tag to an absolute path, opened in a new tab.**
The sidebar entry is `<a href="/mockserver/dashboard" target="_blank" rel="noopener">`, added
alongside the existing `nav-link` items in `mock-ui/static/index.html`. Using an absolute path
(not one relative to `/mock-ui/...`) relies on the existing "Web UI is reachable through the
single external entrypoint" requirement already in the spec: since both `mock-ui` and
MockServer are served from the same Ingress origin, `/mockserver/dashboard` resolves correctly
from any page in the web interface without needing configuration or an environment variable.
`target="_blank"` plus `rel="noopener"` opens it in a new tab without giving the new tab a
handle back to `mock-ui`'s `window` (standard practice for cross-origin-in-spirit links, even
though these are same-origin here).

*Alternatives considered:*
- **Iframe embed** - rejected. The Dashboard is a full-page SPA with its own routing and
  WebSocket; embedding it would fight its own navigation and layout assumptions, and
  MockServer's frame-embedding behavior (headers, CSP) isn't something this project controls
  or should take a dependency on.
- **Reverse-proxy + rewrite into `mock-ui`'s content area** - rejected. Would require rewriting
  the Dashboard's asset paths and WebSocket URL inside `mock-ui`'s Flask app, real ongoing
  maintenance for a page we explicitly don't want to own the behavior of (per the study's
  verdict, `mock-ui` isn't trying to replace or reimplement it).
- **Configurable target URL via an environment variable** (mirroring `MOCKSERVER_URL` used
  server-side) - rejected for now. `MOCKSERVER_URL` is the in-cluster service DNS name
  (`http://mockserver`), used by `app.py` for server-to-server calls; the sidebar link needs
  the *browser-reachable* path, which is already stable as `/mockserver/dashboard` under the
  single entrypoint this project always assumes. Revisit only if a future environment serves
  `mock-ui` and MockServer from different origins.

**Sidebar label: "MockServer Dashboard".**
Chosen over "Advanced Log" or "Diagnostics" (both floated as open questions in the study)
because it names the actual vendor product rather than inventing our own label for someone
else's page - a developer who's used MockServer elsewhere will recognize it immediately, and
it avoids implying it's a `mock-ui` feature.

**Visual treatment: not highlighted as an "active" destination.**
The existing "active destination" requirement highlights whichever of the four in-app pages is
currently shown. MockServer Dashboard never becomes the shown content (it opens a new tab), so
it's excluded from that highlighting behavior - it behaves like a normal outbound link, not a
navigation state. No requirement change was needed for this since the existing "active
destination" requirement already only applies to pages shown in the main content area.

**Help page addition is a short paragraph, not a new section.**
Consistent with the Help page's existing single-purpose framing (explaining matchers plus one
sentence about the protected catch-all), the MockServer Dashboard explanation is one short
paragraph: what it's for, that it opens in a new tab, and that it has no authentication in this
POC (same as every other endpoint here, so this is a one-sentence note rather than a new
concern).

## Risks / Trade-offs

- **[Risk]** If a future environment serves `mock-ui` behind a different Ingress path scheme
  (e.g. `/mock-ui` moves, or MockServer stops being served at the root) the absolute
  `/mockserver/dashboard` link would 404. → **Mitigation**: this project's spec already
  requires a single external entrypoint serving both; if that assumption changes, it changes
  for the whole app, not just this link, and would be caught immediately (a 404 is loud, not
  silent).
- **[Risk]** The Dashboard has no authentication of its own; adding a visible link makes it
  marginally more discoverable to anyone with network access to the entrypoint. → **Mitigation**:
  not a new exposure - `/mockserver/dashboard` already returns 200 today with no link needed to
  find it, and this POC has no auth anywhere else either. The Help page addition calls this out
  explicitly rather than leaving it implicit.
- **[Trade-off]** No `mock-ui`-owned fallback if MockServer's Dashboard changes shape or moves
  in a future MockServer version upgrade. → Accepted: the whole point of linking out instead of
  embedding is that `mock-ui` doesn't take on maintenance of vendor UI; if a version upgrade
  changes `/mockserver/dashboard`'s behavior, that's evaluated as part of that upgrade
  decision, not this change.
