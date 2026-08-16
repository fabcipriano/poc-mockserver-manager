## 1. Configuration

- [x] 1.1 Replace the existing `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` env var handling in `mock-ui/app.py` with `BEDROCK_MODEL_ID` (required for the feature to be available) and `AWS_REGION` (optional), keeping the fail-open convention from design.md (missing model id disables the feature, does not crash startup).
- [x] 1.2 Replace the `anthropic` SDK entry in `mock-ui/requirements.txt` with `boto3`.
- [x] 1.3 Update `GET /mock-ui/api/mock-generation/status` to report `{available: bool}` based on whether `BEDROCK_MODEL_ID` is configured, instead of the Anthropic key.

## 2. Backend: draft endpoint

- [x] 2.1 Add `POST /mock-ui/api/mock-generation/draft` accepting `{sourceEntries, mode}` and validating a non-empty, size-capped `sourceEntries` list (400 on empty or over the cap). (Provider-agnostic; unaffected by the Bedrock switch.)
- [x] 2.2 Replace the Anthropic-formatted prompt with a Bedrock Converse API request (system/user messages) built from `sourceEntries` and `mode` (`"edge-cases"` vs `"from-recordings"`), still requesting output in the existing friendly mock shape (method/path/statusCode/responseBody/matchers).
- [x] 2.3 Replace the Anthropic Messages API call with a boto3 `bedrock-runtime` `converse` call, made synchronously; handle missing/invalid AWS credentials, missing Bedrock model access, and any other Bedrock API error as a clean error response that never echoes credentials back to the client or logs.
- [x] 2.4 Parse the Bedrock Converse response's output message text as JSON; treat a totally unparseable response as a failed generation attempt with no candidates.
- [x] 2.5 Run each parsed item through `to_expectation`'s required-field validation, splitting output into `candidates` (valid) and `rejected` (with a reason), without writing anything to MockServer yet. (Operates on already-parsed items; provider-agnostic.)

## 3. Backend: load endpoint

- [x] 3.1 Add `POST /mock-ui/api/mock-generation/load` accepting `{mocks}` (developer-approved, possibly developer-edited friendly-shape mocks).
- [x] 3.2 Re-validate each via `to_expectation` (covers edits made during review) and reject invalid ones individually rather than failing the whole batch.
- [x] 3.3 For each valid mock, reuse the existing `to_expectation` + `_mockserver_put(target, "/mockserver/expectation", ...)` path used by `create_mock`, against the currently selected target.
- [x] 3.4 Return the created expectations (friendly shape, via `to_friendly`) plus any per-item rejections, mirroring `create_mock`'s response shape.

## 4. Frontend: AI Mock Generator page

- [x] 4.1 Add a new nav entry/page ("AI Mock Generator") in `mock-ui/static/index.html` / `app.js`, hidden or disabled when `/mock-ui/api/mock-generation/status` reports unavailable.
- [x] 4.2 Add selection UI on the Recent Requests page (or within the new page) to pick a capped number of captured entries as the seed corpus, with a mode toggle (edge-cases vs from-recordings). (Implemented as its own list within the AI Mock Generator page - fetched via the existing `/mock-ui/api/requests`, independent from the Recent Requests page's table/DOM, to avoid coupling to that page's in-progress column layout changes.)
- [x] 4.3 Wire the "Generate mocks with AI" action to call the draft endpoint and render the returned candidates (loadable) and rejected items (with reasons) as a review list.
- [x] 4.4 Let a developer edit or remove individual candidates in the review list before approving, reusing existing mock-editing form fields/components where practical.
- [x] 4.5 Wire an "Approve & Load" action that calls the load endpoint with the reviewed/edited candidate set and shows the result (loaded vs rejected), then refreshes the Active Mocks view.
- [x] 4.6 Add an empty-selection guard that blocks starting generation with no entries selected, per spec.

## 5. Deployment

- [x] 5.1 Replace the `ANTHROPIC_API_KEY` `secretKeyRef` in `k8s/overlays/with-mockserver/mock-ui-deployment.yaml` with plain `BEDROCK_MODEL_ID`/`AWS_REGION` env vars, plus `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` sourced the same out-of-band-Secret way (a `mock-ui-aws-credentials` Secret, `optional: true`) as this POC cluster's fallback for when no IRSA/instance-profile role is available.
- [x] 5.2 Update the README's runtime-config table and "Configuring AI mock generation" section to describe `BEDROCK_MODEL_ID`/`AWS_REGION`/AWS credentials instead of `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL`, including the required `bedrock:InvokeModel` IAM permission and enabling model access in the Bedrock console.

## 6. Tests

- [x] 6.1 Update `test_app.py` draft-endpoint coverage to mock the boto3 `bedrock-runtime` client instead of the Anthropic client (empty selection rejected, oversized selection rejected, malformed Bedrock response handled as failed generation, valid/invalid candidates correctly split).
- [x] 6.2 Add `test_app.py` coverage for the load endpoint: valid mocks loaded through the existing MockServer PUT path, invalid mocks rejected individually without failing the whole batch. (Provider-agnostic; unaffected by the Bedrock switch.)
- [x] 6.3 Update the missing-configuration test coverage for the `BEDROCK_MODEL_ID`-unset case: status endpoint reports unavailable, draft endpoint returns a clean error, app still starts and serves existing routes normally.
