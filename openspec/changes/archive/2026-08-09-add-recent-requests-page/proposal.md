## Why

MockServer already records every request it receives - mocked or passed through - but the only way to see
that traffic today is `kubectl logs` or hand-rolled `curl` calls against its `/mockserver/retrieve` API.
`mock-ui` has no visibility into live traffic at all. A "Recent Requests" page - findable by path, updating
in real time - turns MockServer's existing request log into something a developer can actually use while
testing: confirm a request arrived, see what path/method/status it actually was, without leaving the
browser or knowing MockServer's control-plane API.

## What Changes

- Add a fourth sidebar destination, **Recent Requests**, alongside Create Mock / List Mocks / Help.
- The page shows MockServer's actual received-request history (timestamp, method, path, response status),
  newest first - sourced live from MockServer's `REQUEST_RESPONSES` log, not a copy `mock-ui` keeps itself.
- A **path filter** narrows the list to requests whose path contains the typed text (a plain substring
  search - the text is turned into a MockServer path-matcher regex under the hood, not exposed to the
  developer as regex syntax).
- A **live tail**: while the page is open, newly received requests matching the current filter appear at
  the top automatically, with no manual refresh - implemented via Server-Sent Events (SSE) so it's genuinely
  push-based rather than a polling illusion. A **Pause/Resume** control lets a developer freeze the tail to
  read something without new entries pushing it out of view, then pick back up - the standard companion
  control to any live/streaming log view.
- Changing the path filter re-scopes both the currently displayed history and the live tail to match.
- The existing "Web UI is organized around a left-hand navigation sidebar" requirement is updated from
  three destinations to four.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `mock-management-ui`: adds the Recent Requests page (findable-by-path, live-tailing request history) and
  updates the navigation structure requirement to include it as a fourth destination.

## Impact

- Code (new): a new SSE streaming endpoint and a request-history endpoint in `mock-ui/app.py`; a new page
  section, filter input, and live-tail list markup in `mock-ui/static/index.html`; the
  `EventSource`-based live-tail logic, filter wiring, and pause/resume control in `mock-ui/static/app.js`;
  corresponding styling in `mock-ui/static/style.css`.
- Code (modified): the sidebar nav list (one more entry), the existing hash-routing `VALID_PAGES` list.
- No change to `mock-ui/Dockerfile`, `requirements.txt`, the `mock-ui` k8s manifests, or how mocks
  themselves are created/edited/deleted/listed - this only adds a new, read-only view onto MockServer's
  existing request log.
- No change to `scripts/add-mock.sh`/`list-mocks.sh`/`delete-mock.sh` or MockServer itself.
