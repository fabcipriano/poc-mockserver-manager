## Why

`mock-ui` today is a single scrolling page: a create/edit form stacked directly above the mocks table, styled
with browser-default form controls and no visual identity. It works, but it doesn't read as a real internal
tool - there's no wayfinding, no dedicated place to explain the request-matcher options added in the
previous change, and nothing about it looks intentional. A proper left-hand navigation shell (Create Mock /
List Mocks / Help) with a considered visual design turns this from "a form on a page" into something that
reads like an actual admin tool, and gives the newly-added matcher options a natural home for documentation.

## What Changes

- Restructure `mock-ui` around a persistent left-hand navigation sidebar with three destinations: **Create
  Mock**, **List Mocks**, and **Help**. Selecting a destination shows only that page's content in the main
  area - the classic sidebar-nav-plus-content-pane shell used across most admin/dashboard tools - with the
  active destination visually highlighted. Navigation is hash-based (`#create`, `#list`, `#help`) so the
  browser's back/forward buttons and a page reload land on the expected page.
- Apply a distinct visual design system across the whole app - color palette, typography, spacing, card and
  button treatment - visually inspired by zup.com.br's public site (researched directly: a warm
  terracotta/wine palette rather than a generic corporate blue, "Inter" for body text with a bolder display
  weight for headings, generous whitespace, and a distinctive asymmetric corner-radius treatment on cards
  and buttons). This is a fresh, from-scratch palette in the same visual family, not a copy of zup.com.br's
  logo, copy, or exact assets - see design.md for the concrete tokens and why.
- Add a **Help** page explaining, in plain language, what each request matcher (path parameters, query
  string parameters, headers, cookies, request body) does and how to use it, and reiterating that the
  seeded catch-all is never editable here - giving the matcher options added previously a documented home
  instead of only the inline hints already on the form.
- Round out the create/edit and delete flows with the usability conventions a real admin tool would have:
  submitting the create/edit form navigates to List Mocks with a visible success confirmation (instead of
  silently resetting in place), and deleting a mock asks for confirmation first instead of acting
  immediately on a single click.
- The mocks table's Edit action still opens the same form (now living on the Create Mock page, relabeled
  "Edit Mock" while editing) - no change to the underlying create/edit/delete/list behavior or the
  `/api/mocks` API from the previous change, only to how it's organized, styled, and confirmed.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `mock-management-ui`: the web interface gains a left-hand navigation structure (Create Mock / List Mocks
  / Help pages), a Help page with defined content responsibilities, and confirmation/feedback conventions
  for create, update, and delete actions.

## Impact

- Code (modified): `mock-ui/static/index.html` (sidebar shell, three page sections, Help page content),
  `mock-ui/static/app.js` (hash-based navigation, active-nav-item highlighting, post-save navigation to
  List Mocks with a success message, delete confirmation), `mock-ui/static/style.css` (full visual redesign
  - new color/typography/spacing tokens, sidebar layout, card and button treatment).
- No change to `mock-ui/app.py`, the `/api/mocks` JSON shape, `mock-ui/Dockerfile`, or the `mock-ui` k8s
  manifests - this change is entirely about the existing page's structure, navigation, and visual design,
  not the backend or how the app is deployed/reached.
- No change to `scripts/add-mock.sh`/`list-mocks.sh`/`delete-mock.sh` or MockServer itself.
