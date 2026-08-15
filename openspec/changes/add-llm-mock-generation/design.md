## Context

mock-ui (`mock-ui/app.py`, Flask) already has two pieces this change builds directly on top of, per-configured-`Target`:

- **Captured traffic**: a background poller per target keeps a shared in-memory snapshot of MockServer's `REQUEST_RESPONSES` log, served via `/mock-ui/api/requests` and normalized by `_build_history_entry` into `{timestamp, method, path, statusCode, mocked, requestHeaders, requestBody, responseHeaders, responseBody}`.
- **Mock creation**: `/mock-ui/api/mocks` (POST/PUT) accepts a "friendly" JSON shape (`method`, `path`, `statusCode`, `responseBody`, `pathParameters`, `queryStringParameters`, `headers`, `cookies`, `requestBody`, `requestBodyMatchType`), converted by `to_expectation()` into a MockServer expectation and PUT to `/mockserver/expectation`, with `MOCK_PRIORITY` fixed.

Per the proposal, the LLM provider is AWS Bedrock (via its model-agnostic Converse API), and generation is on-demand + human-reviewed: the developer triggers a synchronous LLM call from the running mock-ui app, then explicitly approves before anything reaches MockServer. See proposal.md - Why / What Changes for the motivation and scope.

## Goals / Non-Goals

**Goals:**
- Reuse `to_expectation`/`to_friendly` and the existing mock creation path as the *only* way generated expectations reach MockServer, so this feature can't introduce a second, divergent way of writing expectations.
- Keep the LLM call fully synchronous and developer-initiated, with the review/approve step as a hard gate — no code path loads an unapproved candidate.
- Keep the feature optional at the infrastructure level: a deployment with no `BEDROCK_MODEL_ID` set runs mock-ui exactly as it does today, minus this one page.
- Let the model used for generation be a configuration choice, not a code change: calling Bedrock's provider-agnostic Converse API (rather than a provider-specific SDK/prompt format) means swapping `BEDROCK_MODEL_ID` to a different Bedrock-hosted model needs no mock-ui code change.

**Non-Goals:**
- No automatic/background generation (e.g., generating expectations whenever a new route is observed) — out of scope per the proposal's "on-demand" decision.
- No persistence of "this expectation was AI-generated" provenance in MockServer — approved expectations are ordinary mocks (per spec's last requirement), so no new data model is introduced there.
- No support for LLM providers outside AWS Bedrock's own catalog (e.g., calling OpenAI or Anthropic's API directly) — Bedrock's Converse API is itself the provider-agnostic layer this change relies on, not a second abstraction built on top of it.
- No streaming of partial LLM output to the UI — the Converse call blocks and returns the full draft in one response, given typical seed-corpus sizes (see Risks).

## Decisions

### New backend endpoints, not a new service
Add two routes to the existing `mock-ui/app.py` rather than a separate microservice:
- `POST /mock-ui/api/mock-generation/draft` — body: `{sourceEntries: [...captured entries...], mode: "edge-cases" | "from-recordings"}`. Calls Anthropic, returns `{candidates: [...friendly-shape mocks...], rejected: [{raw, reason}, ...]}`.
- `POST /mock-ui/api/mock-generation/load` — body: `{mocks: [...friendly-shape mocks, developer-edited...]}`. Runs each through the *existing* `to_expectation` + `_mockserver_put(target, "/mockserver/expectation", ...)` path (the same one `create_mock` uses) and returns the created expectations.

Rationale: this is a POC-scale tool already structured as one Flask app per the multi-target design; a second service would add a network hop and a second deployment/config surface for no isolation benefit. Alternative considered — extending `create_mock` itself to accept a `source: "ai"` batch — rejected because draft/review/load are three distinct steps with different failure modes (LLM call, validation, MockServer write), and collapsing them would make partial failure (some candidates invalid) awkward to report back to the UI.

### Candidate schema mirrors the existing "friendly" mock shape exactly
The Anthropic prompt instructs the model to emit JSON matching the same fields `to_expectation` already accepts (`method`, `path`, `statusCode`, `responseBody`, `requestBody`, `requestBodyMatchType`, `pathParameters`, `queryStringParameters`, `headers`, `cookies`) — not raw MockServer `httpRequest`/`httpResponse` JSON.

Rationale: `to_expectation`'s existing required-field check (`method`, `path`, `statusCode`) becomes the validation step for free, and the load endpoint needs no new parsing/conversion logic. Alternative considered — have the LLM emit MockServer-native expectation JSON (or drive MockServer's own OpenAPI-to-expectation feature) — rejected for this change because it would require a second, parallel validation path outside `to_expectation`, and the friendly shape is already expressive enough for the edge cases this feature targets (status/body/header/matcher variation), which is what the spec's scenarios exercise.

### Seed corpus sent as the same normalized shape Recent Requests already uses
The `draft` endpoint takes the exact entries the frontend already has from `/mock-ui/api/requests` (`method`, `path`, `statusCode`, request/response headers and bodies) rather than re-fetching or re-normalizing anything server-side. The backend embeds these directly into the Claude prompt as the seed corpus.

Rationale: avoids a second code path for reading MockServer's log; the frontend already fetched and rendered these entries for selection, so passing the same objects through is the smallest surface.

### Validation happens before showing candidates, not before loading
`draft` runs every LLM-returned candidate through `to_expectation`'s required-field check immediately (catching missing `method`/`path`/`statusCode` and malformed body-matcher shapes) and splits the response into `candidates` (loadable) vs `rejected` (shown with reason, never loadable) before returning to the frontend. This directly implements the spec's "Malformed or invalid candidates are surfaced, not silently loaded" requirement, and means the `load` endpoint only ever receives already-valid shapes (plus whatever a developer's manual edit might break — `load` re-validates for that reason, cheaply, since it's the same check).

### Configuration: fail open, not fail fast, when the model isn't configured
Unlike `MOCKSERVER_TARGETS`/`REQUEST_HISTORY_LIMIT` (which crash startup on a bad value), a missing `BEDROCK_MODEL_ID` does **not** stop mock-ui from starting — it disables this feature, the same fail-open behavior as before. `GET /mock-ui/api/mock-generation/status` (returning `{available: bool}`) now reports availability based on whether `BEDROCK_MODEL_ID` is set, so the frontend can hide/disable the AI Mock Generator page instead of showing a broken one. mock-ui does not itself validate AWS credentials at startup - boto3 resolves them lazily from its standard credential chain (environment variables, a shared config file, an instance profile, or IRSA), so a missing, invalid, or under-permissioned credential surfaces as a runtime error at draft-time, the same treatment an invalid Anthropic key got in the original design.

Rationale: this feature is additive and optional per the proposal's Impact section ("mock-ui SHALL continue to run... if `BEDROCK_MODEL_ID` is unset"); the existing fail-fast convention exists for settings that make the *whole app* behave wrong if misconfigured (targets, timing), which doesn't apply to one optional page.

### AWS Bedrock via boto3's Converse API, not a provider-specific SDK
Add `boto3` to `requirements.txt` (replacing the `anthropic` package) and call `bedrock-runtime`'s `converse` API with a single user-turn message embedding the seed corpus and generation mode, requesting the same JSON-array-of-friendly-mocks output as before. The model is selected purely by the `BEDROCK_MODEL_ID` env var (a Bedrock model ID or inference-profile ARN/ID) - swapping which model answers (Anthropic Claude, Amazon Nova, Meta Llama, or anything else Bedrock hosts that supports Converse) requires no code change, only a config change.

Rationale: Converse presents the same request/response shape across every model family Bedrock hosts, which is what actually delivers "ease of use for any model" - a provider-specific SDK (the original `anthropic` package, or Bedrock's older model-specific `invoke_model` body formats, which differ per model family) would tie the prompt/response parsing to one vendor's message format again. Alternative considered - keep calling Anthropic directly and add Bedrock as a second optional path - rejected as unnecessary complexity: Bedrock already hosts Anthropic's models, so nothing is lost by routing everything through Bedrock alone.

### AWS credential handling in deployment
Prefer letting the mock-ui pod assume an IAM role (IRSA on EKS, or an instance profile on plain EC2 nodes) scoped to `bedrock:InvokeModel`/`bedrock:InvokeModelWithResponseStream` on the configured model, rather than static keys - this is boto3's default credential-chain behavior and needs zero extra mock-ui code. For this POC's local cluster (no IRSA available), fall back to the same pattern the Anthropic key used: an out-of-band `mock-ui-aws-credentials` Secret (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`), referenced via `secretKeyRef` with `optional: true`, never committed to the repo. `BEDROCK_MODEL_ID` and `AWS_REGION` remain plain (non-secret) env vars.

## Risks / Trade-offs

- **[Risk]** A large seed-corpus selection (many/large captured bodies) could exceed reasonable prompt size or produce a slow/expensive Claude call → **Mitigation**: the frontend caps how many Recent Requests entries can be selected per generation run (small fixed limit, e.g. tens not hundreds); `draft` treats an oversized request as a 400.
- **[Risk]** The LLM invents a response shape that's syntactically valid (passes `to_expectation`) but semantically wrong for the real API (e.g., a made-up error envelope) → **Mitigation**: this is exactly why review/approval is a hard gate (spec requirement) rather than auto-load; the design doesn't try to fully solve LLM correctness, only ensures a human sees every candidate first.
- **[Risk]** Synchronous Bedrock call blocks a Flask request thread for the duration of generation → **Mitigation**: acceptable at this POC's scale (Flask already runs `threaded=True`); revisit if generation latency becomes disruptive.
- **[Risk]** AWS credentials present in pod env (in the static-key fallback case) are a credential that must not leak into logs or error responses → **Mitigation**: error handling around the Bedrock call must not echo request/credential details back to the client or logger (same care already taken with MockServer errors via `MockServerError`, which only ever carries a message, not headers).
- **[Risk]** `BEDROCK_MODEL_ID` points at a model/region combination the AWS account hasn't been granted access to (Bedrock model access is opt-in per account and region) or the pod's credentials lack `bedrock:InvokeModel` → **Mitigation**: surfaced as the same clean draft-time error as any other Bedrock API failure; document the required IAM permission and the need to enable model access in the Bedrock console in the deployment docs.
- **[Risk]** Some Bedrock-hosted models (notably newer Claude models, in certain regions) require an inference-profile ID rather than a bare model ID → **Mitigation**: `BEDROCK_MODEL_ID` accepts either form as an opaque config value; mock-ui's code doesn't need to distinguish them.

## Migration Plan

Purely additive to mock-ui as a whole, but replaces this change's own not-yet-archived direct-Anthropic implementation outright (see tasks.md) - there is no dual-support period between the two providers. No existing endpoint, data shape, or MockServer behavior changes. Rollback is deploying the previous mock-ui image/config; no data migration exists since approved expectations are stored only as ordinary MockServer expectations.
