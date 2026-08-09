## 1. Page structure and navigation shell

- [x] 1.1 In `mock-ui/static/index.html`, restructure the body into a persistent left sidebar (nav with three items: Create Mock, List Mocks, Help) and a main content area containing three page `<section>`s (`#page-create`, `#page-list`, `#page-help`), moving the existing create/edit form into the Create Mock section and the existing mocks table into the List Mocks section
- [x] 1.2 Add a new Help page section with content explaining what each request matcher (path parameters, query string parameters, headers, cookies, request body) does and how to use it, and stating the seeded catch-all is never editable here
- [x] 1.3 In `mock-ui/static/app.js`, implement hash-based navigation: a `showPage(pageName)` function that hides all page sections except the one matching `pageName`, highlights the corresponding sidebar nav item, and is called on initial load and on every `hashchange` (defaulting to Create Mock when there's no/unrecognized hash)
- [x] 1.4 Wire the sidebar nav items to set `location.hash` (`#create`, `#list`, `#help`) on click

## 2. Action feedback and confirmation

- [x] 2.1 In `mock-ui/static/app.js`, after a successful create or update, navigate to `#list` and show a dismissible success banner ("Mock created" / "Mock updated") instead of resetting the form in place
- [x] 2.2 Add a `window.confirm()` guard before `deleteMock()` proceeds; if not confirmed, take no action and leave the mock unchanged

## 3. Visual redesign

- [x] 3.1 In `mock-ui/static/index.html`'s `<head>`, add the Google Fonts `<link>`s for `Inter` (weights 400/500/600/700)
- [x] 3.2 Rewrite `mock-ui/static/style.css` with new CSS custom properties for the color palette (`--color-ink`, `--color-accent`, `--color-accent-dark`, `--color-surface`, `--color-surface-alt`, `--color-border`, `--color-danger`) per design.md Decision 1, and apply `Inter` as the base font
- [x] 3.3 Style the sidebar (fixed-width, `--color-ink` background, `--color-surface-alt` text, active-item highlight using `--color-accent`) and the main content area (`--color-surface` background)
- [x] 3.4 Apply the asymmetric corner-radius treatment (per design.md Decision 3) to buttons, the mocks table's card wrapper, and the matcher badge
- [x] 3.5 Restyle the success banner (task 2.1) and existing error message styling to use the new palette (`--color-accent`/`--color-danger`) instead of the old ad hoc colors

## 4. Container image

- [x] 4.1 Rebuild `mock-ui`'s Docker image (`docker build -t mockserver-poc/mock-ui:local mock-ui/`) - no `Dockerfile`/`requirements.txt`/`app.py` changes expected, this is a static-asset-only change

## 5. Verification

- [x] 5.1 Load the new image into the kind cluster and redeploy `mock-ui`
- [x] 5.2 Confirm the sidebar shows all three destinations, and clicking each one shows only that page's content in the main area with the clicked item visually highlighted
- [x] 5.3 Confirm loading the web interface with `#list` (or `#help`) directly in the URL lands on that page without manual navigation, and that browser back/forward moves between previously visited pages
- [x] 5.4 Create a mock through the Create Mock page; confirm it navigates to List Mocks afterward with a visible success confirmation, and the new mock appears in the list
- [x] 5.5 Edit an existing mock; confirm it still pre-fills correctly (regression check against the previous change's matcher pre-fill behavior) and navigates back to List Mocks with a success confirmation on save
- [x] 5.6 Click delete on a mock and dismiss/cancel the confirmation; confirm the mock is still active. Click delete again and confirm; confirm the mock is removed and its route passes through again
- [x] 5.7 Open the Help page and confirm it explains each of the five request matcher types
- [x] 5.8 Re-run the per-matcher-type checks from the previous change (path parameter, query string parameter, header, cookie, JSON request body in both match modes) to confirm the visual/structural restructuring didn't regress the underlying matching behavior
- [x] 5.9 Drive the above end-to-end through the actual browser UI (not just the `/api/mocks` HTTP API), confirming zero console/page errors
