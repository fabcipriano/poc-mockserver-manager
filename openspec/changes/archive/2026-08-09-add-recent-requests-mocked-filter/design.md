## Context

The Recent Requests page's history and live tail both funnel through one function,
`_fetch_request_history` in `mock-ui/app.py`, which calls MockServer's
`retrieve?type=REQUEST_RESPONSES` and narrows each returned log entry down to the fields the page
displays. See proposal.md for why a mocked/forwarded signal is needed on top of that.

This design was validated empirically in this session (not yet covered by an automated test) against a
real `mockserver/mockserver` container, configured the same way this POC configures it: a catch-all
`httpForward` expectation at priority 0, plus one specific `httpResponse` expectation at priority 10
(mirroring `mock-ui`'s own `CATCH_ALL_PRIORITY`/`MOCK_PRIORITY` convention). One request matched the
mock; one fell through to the forward. Inspecting the resulting `REQUEST_RESPONSES` log entries showed:

- The forwarded request's logged `httpResponse` included `"reasonPhrase": "OK"` and a header
  `"x-mockserver-response-time-ms"` reporting the real round-trip time to the backend.
- The mocked request's logged `httpResponse` had neither field - just the plain status code and body
  this tool's own `to_expectation` configured.

Two alternative signals were also investigated and are documented in the proposal's originating
discussion, but not chosen here:
- `retrieve?type=RECORDED_EXPECTATIONS` contains only forwarded traffic, but has no shared identifier
  with `REQUEST_RESPONSES` entries, making it unreliable to correlate to a specific row.
- `retrieve?type=LOGS` states explicitly whether a request was forwarded, but is a human-readable log
  (not a stable typed API) and is also awkward to correlate under concurrent traffic.

## Goals / Non-Goals

**Goals:**
- Label every entry on the Recent Requests page as mocked or forwarded, for both history and the live
  tail, using only data already fetched for that entry - no additional MockServer calls.
- Let a developer filter the page to mocked-only or forwarded-only, combinable with the existing path
  filter.

**Non-Goals:**
- Identifying *which* expectation (by id or name) answered a mocked request - out of scope; mocked vs.
  forwarded is the question this change answers.
- Guaranteeing correctness against a hand-crafted mock response that happens to set a `reasonPhrase` or a
  header literally named `x-mockserver-response-time-ms` - see Risks.
- Any change to how MockServer itself is configured or deployed.

## Decisions

- **Classify using the same `REQUEST_RESPONSES` entry already fetched, not a second API call.** The
  distinguishing fields (`reasonPhrase`, the `x-mockserver-response-time-ms` header) are already present
  in the payload `_fetch_request_history` retrieves; classification is a pure function over data already
  in hand, so it costs nothing extra per request and applies identically to history and the SSE-driven
  live tail.
- **The heuristic: a response is "forwarded" if it has a `reasonPhrase` or a
  `x-mockserver-response-time-ms` header; otherwise "mocked".** This is a genuine behavioral fact, not
  arbitrary: MockServer can only populate a real reason phrase and round-trip timing when it actually
  made an outbound HTTP call on the request's behalf (a `httpForward` action); a canned `httpResponse`
  action is synthesized locally with no such transport-level information to report, and this tool's own
  `to_expectation` (in `mock-ui/app.py`) never sets either field on a mock's response.
- **Compute a single derived field (e.g. `mocked: true|false`) once, in the backend.** Keeps the
  heuristic in one place rather than duplicating the field-checking logic in the frontend; the frontend
  only renders and filters on the resulting boolean.
- **Filter semantics mirror the existing path filter**: a status filter (mocked / forwarded / both)
  narrows the initial history fetch and re-scopes the live tail the same way changing the path filter
  already does, and the two filters combine (AND, not OR).

## Risks / Trade-offs

- [This is an inferred heuristic, not a documented MockServer API contract] → It was verified empirically
  against a real MockServer instance in this session, and it follows directly from what MockServer can
  and cannot know at synthesis time vs. forward time - but MockServer does not publish "mocked vs.
  forwarded" as a stable field, so a future MockServer version could in principle change what metadata it
  attaches to a forwarded response. Mitigation: keep the field-checking logic isolated to one small
  function so it's a one-place fix if MockServer's behavior changes, and add the automated test called
  out below before relying on this in anything beyond a POC.
- [A developer could manually configure a mock's response with a `reasonPhrase` field or a header named
  exactly `x-mockserver-response-time-ms`, misclassifying it as forwarded] → Accepted for this POC: this
  tool's own Create/Edit Mock UI never sets either field, so a mock created through the UI is always
  classified correctly; only a mock created by hand through MockServer's raw API, using that exact
  header name, could trigger a misclassification, which is an edge case rather than a common path.
- [No automated test exists yet for this behavior] → This change's task list should include adding one
  (e.g. spinning up a real or stubbed MockServer response fixture for each shape and asserting the
  computed flag), rather than relying solely on the manual verification already done.
