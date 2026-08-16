## Why

When the legacy system a real API depends on is unavailable, QA needs a mock that behaves like the real thing — not just the exact requests someone happened to capture, but plausible edge cases (validation errors, auth failures, boundary values) shaped the same way the real API shapes them. mock-ui already captures real traffic (Recent Requests) and already manages MockServer expectations (mocks CRUD), but a developer today has to hand-write every edge-case expectation themselves. This change closes that gap by letting a developer turn a selection of captured traffic into an LLM-drafted set of expectations, reviewed and loaded on demand from inside mock-ui.

(This proposal originally called for a direct Anthropic API integration; that's superseded here by AWS Bedrock, chosen so generation isn't locked to a single model provider - see design.md.)

## What Changes

- Add an "AI Mock Generator" page to mock-ui where a developer selects a set of previously captured Recent Requests entries (for the currently selected MockServer target) as the seed corpus.
- On demand, mock-ui's backend sends that seed corpus to AWS Bedrock's Converse API with a prompt instructing the configured model to draft additional MockServer expectations in mock-ui's existing "friendly" mock shape (method/path/status/body/matchers) — covering validation errors, auth failures, boundary values, and other edge cases shaped like the real captured responses — plus a mode to draft the same shape from the captured happy-path entries directly. Bedrock's Converse API presents a uniform request/response shape across every model family it hosts, so the model actually used (Anthropic Claude, Amazon Nova, Meta Llama, or any other Bedrock-hosted model) is a configuration choice, not a code change.
- Show the LLM's proposed expectations as a reviewable diff/preview list (each item editable or removable) before anything is loaded into MockServer — nothing is loaded automatically.
- On explicit developer approval, bulk-load the approved expectations into the selected MockServer target through the existing mock creation path (`to_expectation` / `/mockserver/expectation`), so they show up in the existing Active Mocks list like any hand-created mock.
- Validate the LLM's output against the same required-field rules `to_expectation` already enforces, and surface (without loading) any proposed expectation that fails validation or that the LLM returned as malformed JSON.
- Add `BEDROCK_MODEL_ID` (required to use this feature - a Bedrock model or inference-profile ID) and an optional `AWS_REGION` override as new runtime environment variables. AWS credentials are picked up through boto3's standard credential chain (an IAM role, an instance profile, or explicit `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`), not a bespoke mock-ui setting. mock-ui SHALL continue to run with this feature simply unavailable if `BEDROCK_MODEL_ID` is unset, rather than failing to start.

## Capabilities

### New Capabilities
- `llm-mock-generation`: Turns a developer-selected set of captured requests into LLM-drafted MockServer expectations, previewed and approved by the developer before being loaded into the selected MockServer target.

### Modified Capabilities
(none — the existing `mock-management-ui` mock CRUD requirements and `mockserver-integration` requirements are reused as-is, not changed)

## Impact

- **mock-ui backend (`mock-ui/app.py`)**: new endpoints to (a) submit a selection of Recent Requests entries + generation mode for LLM drafting, and (b) bulk-approve/load the resulting expectations by reusing `to_expectation`/`_mockserver_put`. New outbound dependency: AWS Bedrock (`bedrock-runtime`, via network egress from the mock-ui pod, or a VPC endpoint where required).
- **mock-ui frontend (`mock-ui/static/app.js`, `index.html`, `style.css`)**: new nav page for selecting captured requests, triggering generation, and reviewing/approving proposed expectations.
- **Configuration**: new `BEDROCK_MODEL_ID` / `AWS_REGION` env vars and `requirements.txt` (`boto3`, replacing the `anthropic` SDK); `k8s/` deployment manifests need AWS credentials available to the pod (an IAM role/instance profile preferred, a Secret-backed static key pair as this POC's fallback).
- **No changes** to MockServer itself, the existing mocks CRUD API/behavior, or the Recent Requests capture pipeline — this change only adds a new consumer of already-captured data and a new producer of expectations through the existing creation path.
