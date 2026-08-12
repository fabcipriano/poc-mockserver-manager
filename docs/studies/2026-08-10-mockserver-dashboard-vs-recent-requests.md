# Study: MockServer's built-in Dashboard UI vs. our custom Recent Requests page

**Status:** Study only - no code changed. Written to answer "does it make sense to use
MockServer's Dashboard instead of `mock-ui`'s Recent Requests page," and to seed an
`/opsx:propose` if a menu link is wanted.
**Trigger:** Direct ask to study `https://www.mock-server.com`'s Dashboard UI and compare it
against our Recent Requests page.

## 1. What I actually checked, not just read

MockServer's own docs describe two different things depending on which page you land on, and
they don't agree with each other in scope - the newer `mockserver-monorepo` docs describe an
elaborate 19-view product (Traffic, Trace, gRPC, Chaos, SLO, Drift, MCP Health, LLM
Optimise, Breakpoints, a full expectation composer, React 19/MUI/Zustand, etc.), while the
versioned product docs describe a simpler 4-panel dashboard. Rather than trust either
description at face value, I hit our own running MockServer instance directly:

```
kubectl -n mockserver-poc port-forward svc/mockserver 11080:80
curl http://localhost:11080/mockserver/dashboard        # -> 200, loads a small React app shell
curl http://localhost:11080/mockserver/dashboard/static/js/main.defc53a6.chunk.js
```

Our POC pins `mockserver/mockserver:5.15.0`
(`k8s/overlays/with-mockserver/mockserver-deployment.yaml:48`). Grepping the actual served
bundle confirms which of the two descriptions applies to what we run:

| String searched | Found in our 5.15.0 bundle? |
|---|---|
| `Received Requests`, `Active Expectations`, `Log Messages`, `Proxied Requests` | Yes (1 each) |
| `WebSocket`, `/_mockserver_ui_websocket` | Yes |
| `filter`, `method`, `path`, `header`, `cookie` | Yes |
| `theme` | Yes (2) |
| `Traffic`, `Trace`, `gRPC`, `Chaos`, `SLO`, `Breakpoint`, `Verify`, `pause`, `clear`, `reset`, `copy` | **No** |

**Conclusion: what we run is the classic 4-panel dashboard, not the 19-view product described
in the monorepo docs.** That elaborate feature set (LLM conversation inspection, gRPC/AsyncAPI,
chaos engineering, SLOs, an expectation composer, etc.) does not exist in 5.15.0 and shouldn't
factor into this decision unless we're also proposing a MockServer upgrade, which is out of
scope here. The rest of this study is grounded in what 5.15.0 actually serves.

**Also confirmed: it's already reachable through our existing entrypoint, no new routing
needed.** The ALB stand-in Ingress (`k8s/overlays/with-mockserver/ingress-patch.yaml`) routes
`/mock-ui` to `mock-ui` and `/` (everything else) to the `mockserver` service. That means
`/mockserver/dashboard` is already live at the same entrypoint `mock-ui` uses:

```
curl -o /dev/null -w "%{http_code}\n" http://localhost:8080/mockserver/dashboard   # -> 200
```

## 2. What MockServer 5.15.0's Dashboard actually shows

Four panels, each capped to the 100 most recent matching items, populated by push over
`/_mockserver_ui_websocket` (updates throttle to ~1/sec under load) rather than polling:

- **Active Expectations** - every currently registered expectation, from `RequestMatchers`.
- **Log Messages** - every event MockServer's own `EventLog` recorded (request received,
  matched, forwarded, error, expectation created/deleted, etc.), newest first, **grouped by
  `correlationId`** so all the log lines belonging to one request's lifecycle sit together.
  For a request that didn't match anything, the `EXPECTATION_NOT_MATCHED` entry has an
  expandable "because" section explaining *which specific matcher property* did or didn't
  match (method matched, but this header didn't, etc.).
- **Received Requests** - `RECEIVED_REQUEST` entries paired with their outcome
  (`EXPECTATION_RESPONSE` or `NO_MATCH_RESPONSE`) by `correlationId`.
- **Proxied Requests** - `FORWARDED_REQUEST` entries with request + response.

Each row is a one-line collapsed summary that expands to full JSON on click. A search box
filters by method/path/header/cookie content across panels; there's a dark/light theme toggle.
It's a read-only monitoring surface - there's no create/edit/delete UI for expectations in
this version; that's still API/CLI-only, which is exactly the gap our `mock-ui` was built to
fill.

## 3. What our Recent Requests page already has

Per the current spec (`openspec/specs/mock-management-ui/spec.md`), our page:

- Shows timestamp, method, path, status, and **mocked-vs-forwarded**, most recent first,
  sourced live (no independent cache of the entries themselves).
- Converts timestamps to the **viewer's local time zone** (MockServer logs raw UTC).
- Lets a developer **independently filter** by path substring, mocked/forwarded, and a
  local-time "from"/"to" range, all combinable, with an explicit message when the "from" time
  predates what MockServer's ring buffer still retains.
- **Paginates** history in pages of up to 100, with an explicit "no older requests" signal at
  the end - not just "the newest 100," which is all the vendor dashboard's panels do.
- **Live-tails** new matching requests over SSE, with **pause/resume** that doesn't lose
  requests received while paused.
- Expands to show **request and response headers and body** per entry, including for entries
  that arrived via the live tail, with explicit "absent" states for missing headers/body.
- Was specifically hardened (`docs/studies/2026-08-09-recent-requests-resilience.md`,
  archived as `2026-08-09-improve-recent-requests-resilience`) so many simultaneous viewers
  don't degrade or hang the rest of the web UI - a shared poller now serves all SSE
  connections instead of one independent poll loop per tab.

## 4. Side-by-side

| Capability | Our Recent Requests page | MockServer 5.15.0 Dashboard |
|---|---|---|
| Mocked vs. forwarded label + filter | Yes | No (two separate panels, not one filterable list) |
| Path substring filter | Yes | Yes (search box, but spans all panels, not scoped) |
| Time-range ("from"/"to") search | Yes | No |
| Pagination beyond the newest 100 | Yes (explicit "load more" / end-of-history) | No (hard cap at 100, no way to see older) |
| Local time zone display | Yes | Unconfirmed - not grepped for; likely browser-rendered but unverified |
| Live tail | Yes (SSE), with pause/resume | Yes (WebSocket), no confirmed pause control |
| Request/response header + body detail | Yes, per entry, explicit "absent" states | Yes, via expand-to-JSON |
| **Why a request didn't match a mock** | **No** - only shows the outcome, not the reasoning | **Yes** - `EXPECTATION_NOT_MATCHED` "because" breakdown per matcher property |
| Correlated request lifecycle (all log lines for one request) | No | Yes, grouped by `correlationId` |
| Create/edit/delete a mock | Yes (that's the tool's core purpose) | No (read-only) |
| Concurrency hardening for many simultaneous viewers | Yes (fixed 2026-08-09) | Unverified - vendor's own code, not something we control or have load-tested |
| Already reachable at our single entrypoint | Yes (`/mock-ui`) | Yes, already, at `/mockserver/dashboard` - no new Ingress rule needed |

## 5. Verdict

**No, the Dashboard shouldn't replace Recent Requests.** Every filtering/pagination/UX
investment already made in Recent Requests (mocked/forwarded split, time-range search with
retention-boundary messaging, real pagination, local time zone, pause/resume, resilience
under concurrent viewers) is either missing from or weaker in the vendor dashboard as shipped
in 5.15.0, and none of that work carries over to it - it's not our code.

**But it's worth exposing as a secondary, complementary link**, because it has exactly one
thing our page doesn't and can't cheaply replicate: **the matching-diagnostics view** - why a
specific request didn't match any expectation, broken down property-by-property, with the
full log lifecycle for that request grouped together. That's a real, recurring debugging need
("I created a mock and it's not matching - why?") that today has no answer in `mock-ui` short
of reasoning about the matcher rules by hand.

The cost to offer it is close to zero: it's already served by MockServer and already routed
through the same Ingress. This is a link, not a build.

## 6. Proposal sketch (if the user wants to proceed)

- Add a fifth sidebar destination, e.g. **"Advanced Log"** or **"Diagnostics"**, alongside
  Create Mock / List Mocks / Recent Requests / Help.
- Behavior: opens `/mockserver/dashboard` **in a new tab**, not embedded. Reasons this beats
  an iframe or a proxied/rewritten embed:
  - It's a separate SPA with its own client-side routing and its own WebSocket
    (`/_mockserver_ui_websocket`) - embedding it would mean either an iframe (fragile: its
    internal links/assets are already rooted at `/mockserver/dashboard`, and X-Frame-Options
    /CSP behavior isn't something we control since it's vendor code) or reverse-proxying and
    rewriting its asset paths (real engineering work for a page we're explicitly not trying to
    own or restyle).
  - "Open in new tab" also matches how the Help page should probably frame it: a vendor tool
    for diagnostics, not a page that's part of our left-nav/content-area pattern.
- No backend work needed in `mock-ui`/`app.py` - `/mockserver/dashboard` is already reachable
  through the existing Ingress `/` rule. The only change is a link and, on the Help page, a
  sentence explaining what it's for and when to reach for it instead of Recent Requests.
- Spec impact: an ADDED requirement on `mock-management-ui` along the lines of "the sidebar
  SHALL offer a link to MockServer's own Dashboard, opened separately, described as the place
  to see why a request didn't match any mock" - explicitly scoped as a link-out, not a new
  page the web UI owns or is responsible for keeping working (it's the vendor's, not ours).

## 7. Non-goals / open questions for whoever proposes this

- Not proposing a MockServer version upgrade to reach the newer 19-view dashboard described in
  the monorepo docs - that's a materially different, unverified feature set on a version we
  don't run, and upgrading is its own decision independent of this one.
- Not proposing any redesign of Recent Requests based on dashboard features - the comparison in
  Section 4 shows our page is already ahead on every axis it was purpose-built for.
- Open question for the proposal: should the link be visible to every developer, or should the
  Help page note that MockServer's dashboard has no auth in this POC (same as everything else
  here) so nothing changes about who can reach it - just flagging it's worth one sentence
  rather than assuming it's obvious.
- Open question: exact label/wording for the sidebar entry and Help copy - not settled here.

## Sources

- Live-verified against this repo's own running `mockserver-656d9b8776-zvnb7` pod (image
  `mockserver/mockserver:5.15.0`) via `kubectl port-forward` and `curl`, including grepping
  the actually-served `main.*.chunk.js` bundle - see Section 1.
- `k8s/overlays/with-mockserver/mockserver-deployment.yaml`,
  `k8s/overlays/with-mockserver/ingress-patch.yaml`,
  `k8s/overlays/with-mockserver/mockserver-service.yaml` - version pin and existing routing.
- [MockServer UI](https://www.mock-server.com/mock_server/mockserver_ui.html) - general
  dashboard description (product docs, version-agnostic framing).
- [mockserver-monorepo dashboard-ui.md](https://github.com/mock-server/mockserver-monorepo/blob/master/docs/code/dashboard-ui.md) -
  describes a materially newer/larger dashboard than what 5.15.0 serves; used only to confirm
  what *not* to assume is present in our version (Section 1).
- [mock-server/mockserver-ui](https://github.com/mock-server/mockserver-ui) - now archived,
  merged into the monorepo; confirms the dashboard is bundled at `/mockserver/dashboard`.
- `openspec/specs/mock-management-ui/spec.md` - current Recent Requests requirements (Section
  3).
- `docs/studies/2026-08-09-recent-requests-resilience.md` and the archived
  `2026-08-09-improve-recent-requests-resilience` change - concurrency hardening already done
  on our page.
