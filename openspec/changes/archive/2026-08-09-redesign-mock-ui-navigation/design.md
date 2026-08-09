## Context

`mock-ui/static/index.html` today is one `<body>` with two `<section>`s stacked vertically: the create/edit
form, then the mocks table - no navigation, no page concept, default `system-ui` font, a handful of ad hoc
colors (`#666`, `#ddd`, `#c0392b`, `#eef`/`#335` for the matcher badge). `app.js` has a single `resetForm()`
that re-shows the same page in place after a successful create/update; `deleteMock()` acts immediately on
click with no confirmation. See proposal.md - Why for motivation.

Researched zup.com.br's actual visual design directly (fetched the live page's HTML/CSS rather than
guessing) to ground the "style of this site" request in real tokens instead of a generic impression:

- **Color**: the dominant hex values on the page (by frequency in inline styles) are a very dark
  maroon/near-black (`#260A12`, including the page's own `theme-color` meta tag), a warm off-white
  (`#F5F2F2`), a dusty pink-gray neutral (`#DED4D4`), and a family of warm terracotta/rust/wine accents
  (`#CC7958`, `#9B4527`, `#CB5E5E`, `#A12F43`, `#852838`). This is a warm, earthy, editorial palette - not
  the generic navy/cyan "corporate tech" look an impression-only read would suggest.
- **Typography**: the page loads Google Fonts `"Funnel Display"` (weight 600/700, headings) and `"Inter"`
  (weight 400/500/600/700, body) - a bold display face paired with a highly legible, ubiquitous UI sans.
- **Shape**: several elements use an asymmetric `border-radius` (e.g. `8px 8px 8px 32px` - three small
  corners, one noticeably larger), giving cards and buttons a distinctive soft, organic silhouette rather
  than uniform rounded rectangles or sharp corners.

This is the concrete "style of this site" - reused here as a **new, distinct palette in the same visual
family** (see Decisions), not the literal hex values or their brand assets, since this is an unrelated
internal tool with no affiliation to zup.com.br.

## Goals / Non-Goals

**Goals:**
- A persistent left sidebar with three destinations - Create Mock, List Mocks, Help - where selecting one
  shows only that page's content in the main area, with the active destination visually distinguished.
- Deep-linkable, back/forward-friendly navigation (a reload or a shared link lands on the intended page).
- A cohesive, intentional visual design (color, type, spacing, shape) applied consistently across all three
  pages, inspired by - not copied from - zup.com.br's public site.
- A Help page that documents what each request matcher does, giving the capability added in the previous
  change a permanent, discoverable explanation beyond the form's inline hints.
- Confirmation before a destructive action (delete) and visible feedback after a successful one
  (create/update), matching conventions a real admin tool would have.

**Non-Goals:**
- No new build tooling - stays plain HTML/CSS/JS with no framework and no bundler, consistent with every
  prior `mock-ui` change; fonts are loaded the same way any static asset would be (see Decisions).
- No client-side router library - three pages and hash-based show/hide is simple enough to hand-roll.
- No changes to `mock-ui/app.py`, the `/api/mocks` shape, or how mocks are matched - this change is
  presentation-only.
- No responsive/mobile-specific layout work - this is an internal developer tool accessed from a desktop
  browser during local development, matching every other page in this repo (none are mobile-optimized).
- No dark-mode-specific palette - out of scope; the existing `color-scheme: light dark` stays as a baseline
  browser hint but the new palette is authored for light backgrounds only, same level of effort as today.

## Decisions

1. **A fresh, distinct palette "in the family of" zup.com.br's, not their literal hex values or assets.**
   Chosen tokens:
   - `--color-ink: #2b0f16` (near-black maroon, primary text/dark surfaces - a shade lighter than zup's
     `#260A12` so it isn't a pixel-identical lift)
   - `--color-accent: #c96a4a` (terracotta, primary buttons/links/active nav state)
   - `--color-accent-dark: #8a3a22` (accent hover/pressed state)
   - `--color-surface: #faf7f6` (warm off-white page background)
   - `--color-surface-alt: #ffffff` (card/form background, sits on top of the page background)
   - `--color-border: #e2d6d3` (dusty neutral border/divider)
   - `--color-danger: #a12f43` (delete/error - reuses the same warm-wine family instead of a jarring
     unrelated red)
   This keeps the "warm terracotta/wine, not corporate blue" identity of the source site without reusing
   its exact values, name, or logo.
2. **Typography: `Inter` for everything, at different weights**, rather than pairing it with `Funnel
   Display` for headings. Alternative considered: load both fonts, matching zup.com.br's actual pairing
   more closely. Rejected - a second webfont is extra weight and a second Google Fonts request for a
   POC-scale internal tool, for a visual difference (a display face on 3 page titles) that's marginal next
   to the color/shape signature; `Inter` at 700 for headings reads bold and confident on its own.
3. **Asymmetric corner radius as the shape signature** - buttons, cards, and the badge get one larger
   corner (e.g. `4px 4px 4px 16px`) instead of the uniform `4px`/`999px` used today, echoing the source
   site's distinctive silhouette cheaply (it's just a CSS value, no new markup).
4. **Hash-based navigation (`location.hash` + a `hashchange` listener), not a router library or
   `history.pushState`.** Three known, fixed destinations (`#create`, `#list`, `#help`) map directly to
   three page `<section>`s toggled by a simple "hide all, show the one matching the hash" function called
   on load and on every `hashchange`. This is the simplest option that still gets deep-linking and
   back/forward for free, and needs no dependency.
5. **Edit reuses the Create Mock page** (relabeled "Edit Mock" while an id is set, exactly as today) rather
   than a separate "Edit" page or an inline modal on List Mocks. Keeps one form to maintain, and matches
   the already-shipped `startEdit()`/`resetForm()` model from the previous change - this change adds
   navigation and confirmation around that flow, not a new editing surface.
6. **Post-save behavior: navigate to List Mocks and show a dismissible success banner**, instead of
   resetting the form in place on the same page. Alternative considered: stay on Create Mock with an inline
   success message (better for rapid-fire creation of several mocks in a row). Rejected as the default -
   navigating to the list to see the result you just created/edited is the more common pattern in admin
   tools and gives immediate visual confirmation the action took effect; a developer who wants to add
   another mock right after is one click away on the sidebar regardless.
7. **Delete confirmation is a native `window.confirm()`**, not a custom modal component. A custom modal is
   more visual polish than this destructive-action-guard needs; `confirm()` is synchronous, accessible by
   default, and needs no new markup/CSS/focus-trap work.

## Risks / Trade-offs

- [Hand-rolled hash routing could drift from the "three known pages" assumption if a fourth page is ever
  added.] -> Mitigation: the show/hide function is a single small loop over a page-name-to-element map;
  adding a fourth entry is a one-line change, not a redesign.
- [A visual redesign this broad touches every existing selector in `style.css`.] -> Mitigation: no HTML
  element `id`s/classes used by `app.js` logic are renamed, only their styling changes - so this is a
  CSS-and-markup-structure change, not a JS behavior change, and the request-matcher functionality verified
  in the previous change isn't at risk of regressing from this one.
- [`window.confirm()` blocks the JS event loop and looks distinctly "browser-native," clashing with an
  otherwise custom-styled page.] -> Mitigation: acceptable trade-off for this POC's scope (see Decision 7);
  a custom confirm dialog is a reasonable future follow-up, not blocking here.

## Migration Plan

No data migration - presentation-only change to an already-stateless static frontend. Rollout is rebuilding
and redeploying the `mock-ui` image; rollback is reverting to the prior image, with no persisted state to
reconcile either way (mirrors the previous `mock-ui` change's migration plan).
