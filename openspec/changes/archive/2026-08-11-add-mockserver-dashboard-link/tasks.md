## 1. Sidebar link

- [x] 1.1 In `mock-ui/static/index.html`, add a fifth `<li>` to `.nav-list` for "MockServer Dashboard": `<a href="/mockserver/dashboard" target="_blank" rel="noopener" class="nav-link" data-page="mockserver-dashboard">MockServer Dashboard</a>`.
- [x] 1.2 In `mock-ui/static/app.js`, confirm (or adjust) the existing sidebar click/active-highlight handler so it does not treat this link as an internal `data-page` destination - it must not try to show/hide a `#page-mockserver-dashboard` section or mark itself "active" the way Create Mock/List Mocks/Recent Requests/Help do, since no such section exists and none should be created.
- [x] 1.3 Style the new link consistently with the existing `nav-link` items in `mock-ui/static/style.css`; optionally add a small external-link indicator (e.g. an icon or `↗`) so it's visually distinct from the four in-app destinations before the developer clicks it.

## 2. Help page content

- [x] 2.1 In `mock-ui/static/index.html`, add a new `help-article` under `#page-help` explaining: what the MockServer Dashboard link is for (seeing why a request didn't match any mock, via its matching-diagnostics log view), that it opens in a new tab, and that it's a separate vendor tool with no authentication in this POC - not a page `mock-ui` owns or keeps working.

## 3. Verification

- [x] 3.1 Run the mock-ui test suite (`mock-ui/test_app.py`) and confirm it still passes unchanged (no backend behavior changed).
- [x] 3.2 Manually load `mock-ui` through the POC's single entrypoint, click the new sidebar link, and confirm MockServer's Dashboard opens in a new tab at `/mockserver/dashboard` while the original `mock-ui` tab is unaffected.
- [x] 3.3 Confirm the Help page's new explanation is visible and that the four existing sidebar destinations (Create Mock, List Mocks, Recent Requests, Help) still switch content in the main content area and highlight as active exactly as before.
