## 1. Backend: friendly API shape

- [x] 1.1 In `mock-ui/app.py`, rename the response field in `to_friendly()`/`to_expectation()` from `body` to `responseBody` (matching `httpResponse.body`)
- [x] 1.2 Add `requestBody` (JSON value) and `requestBodyMatchType` (`"ONLY_MATCHING_FIELDS"` default, or `"STRICT"`) to `to_expectation()`, building `httpRequest.body` as `{"type": "JSON", "json": <value>, "matchType": <matchType>}` only when `requestBody` is provided; omit `httpRequest.body` entirely otherwise
- [x] 1.3 Add `pathParameters` and `queryStringParameters` (each a list of `{name, value}` pairs from the form) to `to_expectation()`, building `httpRequest.pathParameters`/`queryStringParameters` as `{name: [value, ...]}` maps (grouping repeated names into a multi-value list), omitted entirely when empty
- [x] 1.4 Add `headers` (list of `{name, value}` pairs) to `to_expectation()`, building `httpRequest.headers` the same way as query string parameters (list-shaped values), omitted when empty
- [x] 1.5 Add `cookies` (list of `{name, value}` pairs) to `to_expectation()`, building `httpRequest.cookies` as `{name: value}` (single string per name, **not** a list - MockServer's cookie shape differs from headers/query params), omitted when empty
- [x] 1.6 Update `to_friendly()` to read back `pathParameters`, `queryStringParameters`, `headers` (flattening each `{name: [values]}` map to a list of `{name, value}` pairs, one row per value), `cookies` (flattening `{name: value}` to a list of `{name, value}` pairs), and `requestBody`/`requestBodyMatchType` - handling both the collapsed bare-JSON-object shape (implies default `ONLY_MATCHING_FIELDS`) and the full `{type, json, matchType}` shape MockServer returns for a non-default `matchType`
- [x] 1.7 Add a computed field in `to_friendly()`'s output (e.g. `matcherCount`) counting how many of path parameters/query string parameters/headers/cookies/request body are set, for the list view's indicator

## 2. Frontend: form restructuring

- [x] 2.1 In `mock-ui/static/index.html`, rename the existing "Response body (JSON)" field's label/id to make clear it's the response (e.g. `mock-response-body`), keeping it visually in the same primary position as today
- [x] 2.2 Add a collapsed-by-default `<details>`/toggle section labeled "Request matchers (optional)" containing: dynamic name/value row lists for path parameters, query string parameters, and headers; a dynamic name/value row list for cookies; a "Request body (JSON)" textarea; and a match-type choice (`ONLY_MATCHING_FIELDS` selected by default, `STRICT` as the other option)
- [x] 2.3 In `mock-ui/static/app.js`, implement a small reusable helper for rendering/adding/removing name/value rows, used by path parameters, query string parameters, headers, and cookies
- [x] 2.4 Update the form submit handler to build the richer payload (`responseBody`, `pathParameters`, `queryStringParameters`, `headers`, `cookies`, `requestBody`, `requestBodyMatchType`), omitting any matcher the developer left empty rather than sending an empty list/object
- [x] 2.5 Update `startEdit()` to pre-fill all matcher rows from a mock's data, and auto-expand the "Request matchers" section when the mock being edited has any matcher set
- [x] 2.6 Update `resetForm()` to also clear all dynamic matcher rows and re-collapse the "Request matchers" section
- [x] 2.7 Update `mock-ui/static/style.css` for the collapsible section and the name/value row layout (add/remove row buttons)

## 3. Frontend: list view indicator

- [x] 3.1 In `renderMocks()` (`mock-ui/static/app.js`), add a small badge/label next to a mock's row (e.g. "+3 matchers") when its `matcherCount` is greater than zero, and nothing extra when it's zero

## 4. Container image

- [x] 4.1 Rebuild `mock-ui`'s Docker image (`docker build -t mockserver-poc/mock-ui:local mock-ui/`) - no `Dockerfile`/`requirements.txt` changes expected, this is an application-code-only change

## 5. Verification

- [x] 5.1 Load the new image into the kind cluster and redeploy `mock-ui` (`scripts/build-and-load-images.sh`, then reapply the `with-mockserver` overlay or restart the `mock-ui` Deployment)
- [x] 5.2 Create a mock with only method/path/status/response body through the UI (no matchers section touched); confirm it behaves exactly as before this change
- [x] 5.3 Create a mock with a templated path and a path parameter constraint; confirm a request matching the constraint hits the mock and one with a different path-parameter value doesn't
- [x] 5.4 Create a mock with a query string parameter constraint; confirm matching/non-matching requests behave as expected
- [x] 5.5 Create a mock with a header constraint; confirm matching/non-matching requests behave as expected
- [x] 5.6 Create a mock with a cookie constraint; confirm matching/non-matching requests behave as expected (this is the one whose wire shape differs from the others - explicitly re-verify it round-trips correctly through an edit, not just a create)
- [x] 5.7 Create a mock with a JSON request body matcher in `ONLY_MATCHING_FIELDS` mode; confirm a request with extra body fields still matches and one missing a required field doesn't
- [x] 5.8 Create a mock with a JSON request body matcher in `STRICT` mode; confirm a request with extra body fields no longer matches
- [x] 5.9 Edit an existing mock that has matchers set; confirm the "Request matchers" section is pre-expanded and every field is correctly pre-filled, and that saving without changes preserves the same matching behavior (no duplicate expectation, per the existing update-in-place requirement)
- [x] 5.10 Confirm the active-mocks list shows the "+N matchers" indicator only for mocks that have matchers beyond method+path
- [x] 5.11 Drive the above end-to-end through the actual browser UI (not just the `/api/mocks` HTTP API) for at least the create-with-matchers and edit-pre-fill flows, to confirm the frontend JS/HTML actually works, not just the backend translation logic
