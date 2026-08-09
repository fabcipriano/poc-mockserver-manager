## Context

`mock-ui/app.py`'s `to_expectation()` builds `httpRequest` with only `method` and `path`; `to_friendly()`
reads back only the same two fields plus the response's `statusCode`/`body`. The form
(`mock-ui/static/index.html` + `app.js`) has exactly one body field, labeled "Response body (JSON)," which
maps to `httpResponse.body` - there is currently no way to constrain a mock by anything in the request
beyond method+path, and no request body matcher exists at all. See proposal.md - Why for motivation.

Verified live against the actual running MockServer (`mockserver/mockserver:5.15.0`, the version this repo
pins - not assumed from generic docs, given the property-name version mismatch found in a prior change):

- `httpRequest.pathParameters` matches named segments in a **templated** `path` (e.g. `path: "/booking/{id}"`,
  `pathParameters: {"id": ["123"]}`) - confirmed a request to `/booking/123` matches and `/booking/999`
  doesn't, with no extra configuration needed beyond writing `{id}` directly in the path string.
- `httpRequest.queryStringParameters` and `httpRequest.headers` both use the same shape: a map of name to
  a **list** of allowed values (`{"active": ["true"]}`).
- `httpRequest.cookies` uses a **different** shape - a map of name to a single **string** (not a list):
  `{"session": "abc"}`. Sending a list here is rejected by MockServer's schema validation with a clear
  error naming the correct shape. This inconsistency is real and the UI needs to build the right shape for
  each field, not treat all four matcher types uniformly.
- `httpRequest.body` for JSON matching takes `{"type": "JSON", "json": <object-or-string>, "matchType":
  "ONLY_MATCHING_FIELDS" | "STRICT"}`. `ONLY_MATCHING_FIELDS` (MockServer's own default) matches if the
  actual request body is a superset of the specified fields - confirmed a request with extra fields still
  matched, and a request missing a specified field didn't. `STRICT` requires an exact match - confirmed
  extra fields broke the match. When `matchType` is the default (`ONLY_MATCHING_FIELDS`), MockServer's API
  responses **collapse** the stored matcher back down to a bare JSON object (no `type`/`matchType`
  wrapper); the full `{type, json, matchType, rawBytes}` shape is only returned when `matchType` is
  non-default (`STRICT`). `mock-ui`'s read path (`to_friendly`) has to handle both shapes when displaying
  or pre-filling the edit form for a mock created by some other means (e.g. `scripts/add-mock.sh` writing a
  raw expectation) with an explicit `STRICT` matcher.
- Omitting a matcher field entirely (not present in the JSON at all) means "no constraint from this
  field" - MockServer does not treat an empty object/list the same way for all matcher types, so `mock-ui`
  must omit fields the developer left blank rather than sending `{}`/`[]` for them.

## Goals / Non-Goals

**Goals:**
- Support authoring, in the web UI, the request matchers a developer would reach for most often: path
  parameters, query string parameters, headers, cookies, and a JSON request body.
- Keep the common case (method + path + status + response body) exactly as simple as it is today - no new
  required fields, no new required clicks for a mock that doesn't need extra matching.
- Make the request-body-matcher vs. response-body distinction unambiguous in the UI, since today's single
  "body" field is misleadingly named for what it actually does.
- Give a developer a way to tell, from the mocks list, which mocks have matchers beyond method+path,
  without cluttering the table with full matcher detail for every row.

**Non-Goals:**
- Non-JSON request body matching (plain string, XML, regex, JSON Schema, binary) - "principally JSON" per
  the request that started this change; a real need for other body types is a reasonable future follow-up,
  not addressed here.
- Matching on anything outside `httpRequest` (e.g. `secure`, `keepAlive`, client certificates) - out of
  scope, not part of what was asked for.
- Changing how `scripts/add-mock.sh`/`list-mocks.sh`/`delete-mock.sh` work, or unifying them with
  `mock-ui`'s richer matcher support - they remain the simple method+path+status+body tools they are today,
  independent of this change.
- Validating matcher values beyond basic JSON syntax (e.g. no regex-pattern validation, no warning for a
  path parameter name that doesn't appear in the path string) - left as straightforward user error for now.

## Decisions

1. **Split `body` into `requestBody` (matcher, optional) and `responseBody` (what to send back, required)
   in `mock-ui`'s friendly API and form** - rather than keeping one field and adding a checkbox/toggle for
   "is this a matcher or a response." Two clearly-labeled fields are more legible than one field whose
   meaning depends on a mode toggle, and it mirrors MockServer's own model (`httpRequest.body` vs.
   `httpResponse.body` are unrelated fields). This is the one deliberately breaking change in this
   proposal - see proposal.md - Impact.

2. **Request matchers (path parameters, query string parameters, headers, cookies, request body) live in a
   single collapsed-by-default "Request matchers (optional)" section**, expanded by a plain disclosure
   toggle - not separate modal dialogs, not a multi-step wizard, and not always-expanded fields.
   - Alternative considered: always show all fields (no collapsing). Rejected - directly contradicts the
     "keep the common case simple" goal; five mostly-unused sections would dominate the form visually for
     the majority of mocks that only need method+path.
   - Alternative considered: a multi-step wizard (method/path/status first, then a "matchers" step, then
     "response" step). Rejected - more clicks for the common case than today for no real benefit; a single
     scrollable form with a collapsed section is simpler to build and use.
   - Path parameters, query string parameters, and headers are each authored as a dynamic list of
     name/value rows (add row / remove row) - the standard, well-understood pattern for editing a
     name-keyed collection in a form, and it matches the "list of values per name" shape MockServer
     actually expects for query params and headers (a UI could support multiple values per name, but see
     Non-Goals-adjacent scope note below).
   - Cookies are authored the same way (name/value rows) for UI consistency, even though MockServer's
     cookie shape is a single string per name rather than a list - the form always builds exactly one value
     per cookie row, matching what MockServer expects.
   - Request body matcher is a JSON textarea (mirroring the existing response body textarea) plus a
     match-type choice (`ONLY_MATCHING_FIELDS` - MockServer's own default, selected by default here too -
     or `STRICT`).

3. **Multiple values per query-parameter/header name are out of scope for this change** - the form takes
   one value per name/value row; a developer who adds the same name twice gets two separate matcher
   entries sent as a two-element list for that name (this falls out naturally from how the friendly API
   maps name/value pairs to MockServer's list-shaped fields, not from special-case code), which is
   sufficient for the common case without needing a more complex "add another value" sub-control per row.

4. **Table indicator, not full detail**: the active-mocks table gets one small badge/label (e.g. "+3
   matchers") when a mock has any matcher beyond method+path, rather than expanding table columns for every
   matcher type. Full detail is one click away (Edit already opens the complete form pre-filled). Keeps the
   table scannable as originally designed while still surfacing that "this mock is narrowly scoped" at a
   glance.

5. **`to_friendly()` normalizes both JSON-body-matcher shapes** (the collapsed bare-object form and the
   full `{type, json, matchType}` form) into one consistent `{requestBody: {...}, requestBodyMatchType:
   "ONLY_MATCHING_FIELDS"|"STRICT"}` shape for the frontend, so the edit form doesn't need to know about
   MockServer's shape-collapsing behavior - confirmed necessary in Context above.

## Risks / Trade-offs

- [A developer edits a mock that was created by some other means (e.g. a hand-written expectation via
  `scripts/add-mock.sh`) with matcher fields this form doesn't expose (e.g. a regex path matcher, XML
  body).] -> Mitigation: same accepted limitation as the existing response-body editing behavior (documented
  in the prior change's design) - editing through the form rebuilds the expectation from what the form
  exposes; a mock relying on unexposed fields simply shouldn't be edited here if those fields must be kept.
- [Cookies' different wire shape (string, not list) could be a source of bugs if implemented by analogy
  with headers/query params.] -> Mitigation: explicitly covered in Context and Decision 2 above, and
  covered by a dedicated task/verification step so it isn't implemented incorrectly by pattern-matching the
  other three.
- [Collapsed-by-default section could hide the feature entirely from a developer who doesn't notice it.]
  -> Mitigation: label it plainly ("Request matchers (optional)") rather than an unlabeled chevron, and
  auto-expand it when editing a mock that already has matchers set, so it's never silently hiding active
  configuration.

## Migration Plan

No data migration - this only changes `mock-ui`'s own request/response shape and form, not anything stored
in MockServer (existing mocks created before this change keep working and remain listable/deletable; they
just won't have request-matcher fields populated when opened for editing, which is correct since they don't
have any). Rollout is rebuilding and redeploying the `mock-ui` image; rollback is reverting to the prior
image, with no persisted state to reconcile either way.
