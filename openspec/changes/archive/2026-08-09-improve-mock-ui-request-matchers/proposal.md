## Why

`mock-ui` today can only match a request by method and literal path - there's no way to constrain a mock to
a specific query string, header, cookie, or request body, and the form doesn't even distinguish "what to
match" from "what to respond with" (the single `body` field is actually only the response body). For this
POC to demonstrate what a real mocking workflow looks like, a developer needs to be able to author the
request matchers they'd actually reach for day to day - path parameters, query string parameters, headers,
cookies, and a JSON request body - through a form that stays easy to use for the common method+path case
and doesn't overwhelm it with rarely-needed fields.

## What Changes

- Add support for authoring these MockServer request matchers, all optional: path parameters (for
  templated paths like `/booking/{id}`), query string parameters, headers, cookies, and a JSON request
  body (exact or partial/`ONLY_MATCHING_FIELDS` match).
- Split the existing single "body" field into two distinct, clearly-labeled concepts: **request body
  matcher** (optional, constrains which requests this mock applies to) and **response body** (what to send
  back) - today's field is actually only the latter.
- Redesign the create/edit form for usability: method, path, status code, and response body stay front and
  center exactly as they are today (the common case is unchanged); path parameters, query string
  parameters, headers, cookies, and request body matching live in a clearly-labeled, collapsed-by-default
  "Request matchers" section so the simple case never feels more complex than it does today.
- The active-mocks table gains a compact indicator (not full detail) when a mock has additional matchers
  beyond method+path, so a developer can tell at a glance which mocks are narrowly scoped.
- `mock-ui`'s `/api/mocks` JSON shape gains new optional fields (`pathParameters`, `queryStringParameters`,
  `headers`, `cookies`, `requestBody`) and renames the existing response field from `body` to
  `responseBody` - **BREAKING** for any script or tooling that calls `mock-ui`'s API directly with the old
  field name (the web UI itself is updated to match; `scripts/add-mock.sh` and friends, which talk to
  MockServer directly rather than through `mock-ui`, are unaffected).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `mock-management-ui`: creating/editing a mock gains optional request-matcher fields (path parameters,
  query string parameters, headers, cookies, JSON request body); the form's usability requirements are
  extended so these additions don't complicate the common method+path+status+response-body case.

## Impact

- Code (modified): `mock-ui/app.py` (`to_expectation`/`to_friendly` translation logic, new optional
  fields), `mock-ui/static/index.html` (new form sections), `mock-ui/static/app.js` (collapsible section
  behavior, building/parsing the richer payload, table indicator).
- No change to `mock-ui/Dockerfile`, the `mock-ui` k8s manifests, or how the web UI is deployed/reached -
  this is purely an in-app capability change.
- No change to `scripts/add-mock.sh`/`list-mocks.sh`/`delete-mock.sh` or MockServer itself - they continue
  to work exactly as before, independently of `mock-ui`.
- **BREAKING** (see above): `mock-ui`'s own `/api/mocks` JSON shape changes (`body` -> `responseBody`, new
  optional fields). Nothing else in this repo calls that API besides the web UI itself, which is updated in
  the same change.
