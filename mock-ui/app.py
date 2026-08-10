import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

from flask import Flask, Response, jsonify, request, send_from_directory

MOCKSERVER_URL = os.environ.get("MOCKSERVER_URL", "http://mockserver")

# Convention shared with scripts/add-mock.sh: the seeded catch-all forwarding
# expectation always sits at priority 0, every dev-created mock at priority 10.
CATCH_ALL_PRIORITY = 0
MOCK_PRIORITY = 10

app = Flask(__name__, static_folder="static", static_url_path="/mock-ui")


class MockServerError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _mockserver_put(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{MOCKSERVER_URL}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
    except urllib.error.URLError as exc:
        raise MockServerError(502, f"could not reach MockServer: {exc}") from exc
    if not raw:
        return None
    return json.loads(raw)


DEFAULT_BODY_MATCH_TYPE = "ONLY_MATCHING_FIELDS"


def _pairs_to_multimap(pairs):
    """[{name, value}, ...] -> {name: [value, ...]}, grouping repeated names."""
    multimap = {}
    for pair in pairs or []:
        name = pair.get("name")
        value = pair.get("value", "")
        if not name:
            continue
        multimap.setdefault(name, []).append(value)
    return multimap


def _multimap_to_pairs(multimap):
    """{name: [value, ...]} -> [{name, value}, ...], one row per value."""
    pairs = []
    for name, values in (multimap or {}).items():
        for value in values:
            pairs.append({"name": name, "value": value})
    return pairs


def _pairs_to_cookie_map(pairs):
    """[{name, value}, ...] -> {name: value} - cookies are single-valued, unlike headers/query params."""
    return {pair["name"]: pair.get("value", "") for pair in (pairs or []) if pair.get("name")}


def _cookie_map_to_pairs(cookie_map):
    return [{"name": name, "value": value} for name, value in (cookie_map or {}).items()]


def _request_body_from_httpRequest(http_request):
    """Normalizes MockServer's two JSON-body-matcher shapes into (requestBody, matchType).

    With the default matchType (ONLY_MATCHING_FIELDS), MockServer collapses the stored
    matcher back down to a bare JSON object; the full {type, json, matchType} shape is
    only returned for a non-default matchType (e.g. STRICT).
    """
    body = http_request.get("body")
    if body is None:
        return None, None
    if isinstance(body, dict) and body.get("type") == "JSON":
        return body.get("json"), body.get("matchType", DEFAULT_BODY_MATCH_TYPE)
    return body, DEFAULT_BODY_MATCH_TYPE


def to_friendly(expectation):
    http_request = expectation.get("httpRequest") or {}
    http_response = expectation.get("httpResponse") or {}

    path_parameters = _multimap_to_pairs(http_request.get("pathParameters"))
    query_string_parameters = _multimap_to_pairs(http_request.get("queryStringParameters"))
    headers = _multimap_to_pairs(http_request.get("headers"))
    cookies = _cookie_map_to_pairs(http_request.get("cookies"))
    request_body, request_body_match_type = _request_body_from_httpRequest(http_request)

    matcher_count = sum(
        1
        for matcher in (path_parameters, query_string_parameters, headers, cookies, [request_body] if request_body is not None else [])
        if matcher
    )

    return {
        "id": expectation.get("id"),
        "method": http_request.get("method"),
        "path": http_request.get("path"),
        "statusCode": http_response.get("statusCode"),
        "responseBody": http_response.get("body"),
        "pathParameters": path_parameters,
        "queryStringParameters": query_string_parameters,
        "headers": headers,
        "cookies": cookies,
        "requestBody": request_body,
        "requestBodyMatchType": request_body_match_type,
        "matcherCount": matcher_count,
    }


def to_expectation(payload, expectation_id=None):
    for field in ("method", "path", "statusCode"):
        if field not in payload:
            raise MockServerError(400, f"missing required field: {field}")

    http_request = {
        "method": payload["method"],
        "path": payload["path"],
    }

    path_parameters = _pairs_to_multimap(payload.get("pathParameters"))
    if path_parameters:
        http_request["pathParameters"] = path_parameters

    query_string_parameters = _pairs_to_multimap(payload.get("queryStringParameters"))
    if query_string_parameters:
        http_request["queryStringParameters"] = query_string_parameters

    headers = _pairs_to_multimap(payload.get("headers"))
    if headers:
        http_request["headers"] = headers

    cookies = _pairs_to_cookie_map(payload.get("cookies"))
    if cookies:
        http_request["cookies"] = cookies

    request_body = payload.get("requestBody")
    if request_body is not None:
        http_request["body"] = {
            "type": "JSON",
            "json": request_body,
            "matchType": payload.get("requestBodyMatchType") or DEFAULT_BODY_MATCH_TYPE,
        }

    expectation = {
        "httpRequest": http_request,
        "httpResponse": {
            "statusCode": payload["statusCode"],
            "headers": {"Content-Type": ["application/json"]},
            "body": payload.get("responseBody", {}),
        },
        "priority": MOCK_PRIORITY,
    }
    if expectation_id:
        expectation["id"] = expectation_id
    return expectation


@app.errorhandler(MockServerError)
def handle_mockserver_error(err):
    return jsonify({"error": err.message}), err.status_code


@app.get("/mock-ui/healthz")
def healthz():
    return "ok", 200


@app.get("/mock-ui/api/mocks")
def list_mocks():
    expectations = _mockserver_put("/mockserver/retrieve?type=ACTIVE_EXPECTATIONS", {}) or []
    mocks = [
        to_friendly(expectation)
        for expectation in expectations
        if expectation.get("priority", MOCK_PRIORITY) != CATCH_ALL_PRIORITY
    ]
    return jsonify(mocks)


@app.post("/mock-ui/api/mocks")
def create_mock():
    payload = request.get_json(force=True, silent=True) or {}
    expectation = to_expectation(payload)
    created = _mockserver_put("/mockserver/expectation", expectation)
    if not created:
        raise MockServerError(502, "MockServer did not return the created expectation")
    return jsonify(to_friendly(created[0])), 201


@app.put("/mock-ui/api/mocks/<mock_id>")
def update_mock(mock_id):
    payload = request.get_json(force=True, silent=True) or {}
    expectation = to_expectation(payload, expectation_id=mock_id)
    updated = _mockserver_put("/mockserver/expectation", expectation)
    if not updated:
        raise MockServerError(502, "MockServer did not return the updated expectation")
    return jsonify(to_friendly(updated[0]))


@app.delete("/mock-ui/api/mocks/<mock_id>")
def delete_mock(mock_id):
    _mockserver_put("/mockserver/clear", {"id": mock_id})
    return "", 204


REQUEST_HISTORY_LIMIT = 40
REQUEST_STREAM_POLL_SECONDS = 1


def _observed_body(body):
    """Normalizes an observed (not matcher) request/response body into a plain value.

    Unlike expectation matchers, MockServer logs actual traffic bodies in a few
    different shapes depending on content type (raw string, `{"json": ...}`,
    `{"string": ...}`); this collapses them all down to whatever's most useful
    to display as-is.
    """
    if body is None:
        return None
    if isinstance(body, dict):
        if "json" in body:
            return body["json"]
        if "string" in body:
            return body["string"]
    return body


def _is_forwarded_response(http_response):
    """True if an observed response was proxied to a real backend rather than answered by a canned mock.

    MockServer can only report a real HTTP reason phrase or round-trip timing when it actually made an
    outbound call (an `httpForward` expectation); a canned `httpResponse` expectation is synthesized
    locally and this tool's own `to_expectation` never sets either field, so their presence reliably
    marks a response as forwarded rather than mocked. See design.md in the
    add-recent-requests-mocked-filter change for the empirical basis and known limits of this heuristic.
    """
    if http_response.get("reasonPhrase"):
        return True
    headers = http_response.get("headers") or {}
    return any(name.lower() == "x-mockserver-response-time-ms" for name in headers)


def _parse_mocked_filter(mocked_query):
    """Turns the `mocked` query param ("true"/"false"/absent) into True/False/None (no filter)."""
    if mocked_query is None:
        return None
    return mocked_query.lower() == "true"


ENTRY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def _parse_entry_datetime(timestamp):
    """Parses one of MockServer's own logged timestamps. Returns None if missing/malformed."""
    if not timestamp:
        return None
    try:
        return datetime.strptime(timestamp, ENTRY_TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _parse_query_datetime(value):
    """Parses a developer-supplied from/to filter value (e.g. from an HTML datetime-local
    input, "YYYY-MM-DDTHH:MM[:SS]") into a naive datetime. Returns None if empty/unparsable -
    an invalid value is treated as "no bound" rather than a hard error, since this only narrows
    a read-only view."""
    if not value:
        return None
    normalized = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _matches_filters(entry, path_query, mocked_filter, from_dt, to_dt):
    if path_query and path_query not in (entry["path"] or ""):
        return False
    if mocked_filter is not None and entry["mocked"] != mocked_filter:
        return False
    if from_dt is not None or to_dt is not None:
        entry_dt = _parse_entry_datetime(entry["timestamp"])
        if entry_dt is None:
            return False
        if from_dt is not None and entry_dt < from_dt:
            return False
        if to_dt is not None and entry_dt > to_dt:
            return False
    return True


def _build_history_entry(raw_entry):
    """Normalizes one raw MockServer REQUEST_RESPONSES log entry into what this page displays."""
    http_request = raw_entry.get("httpRequest") or {}
    http_response = raw_entry.get("httpResponse") or {}
    return {
        "timestamp": raw_entry.get("timestamp"),
        "method": http_request.get("method"),
        "path": http_request.get("path"),
        "statusCode": http_response.get("statusCode"),
        "mocked": not _is_forwarded_response(http_response),
        "requestHeaders": _multimap_to_pairs(http_request.get("headers")),
        "requestBody": _observed_body(http_request.get("body")),
        "responseHeaders": _multimap_to_pairs(http_response.get("headers")),
        "responseBody": _observed_body(http_response.get("body")),
    }


# --- shared history poller ---
#
# A single background thread fetches MockServer's full (unfiltered, unpaginated) request log
# on REQUEST_STREAM_POLL_SECONDS cadence, regardless of how many browser tabs are open, and
# every request/connection reads from this shared, continuously-rebuilt snapshot instead of
# hitting MockServer itself. Previously each SSE connection polled MockServer independently -
# with N open tabs that meant N re-fetches and N re-parses of the entire (potentially
# multi-MB) log every second, which is what collapsed the page under concurrent viewers. See
# docs/studies/2026-08-09-recent-requests-resilience.md for the full reproduction.
#
# The snapshot holds nothing MockServer doesn't already have and nothing survives past the next
# tick, so this isn't the kind of independent cache the mocks CRUD flows are required to avoid -
# see design.md in the improve-recent-requests-resilience change for why.
_history_lock = threading.Lock()
_history_snapshot = []


def _poll_history_once():
    try:
        raw_entries = _mockserver_put("/mockserver/retrieve?type=REQUEST_RESPONSES", {}) or []
    except MockServerError:
        # Keep serving the previous snapshot rather than blanking it out on a transient failure.
        return
    built = [_build_history_entry(entry) for entry in raw_entries]
    global _history_snapshot
    with _history_lock:
        _history_snapshot = built


def _history_poller_loop():
    while True:
        _poll_history_once()
        time.sleep(REQUEST_STREAM_POLL_SECONDS)


def _get_history_snapshot():
    with _history_lock:
        return list(_history_snapshot)


@app.get("/mock-ui/api/requests")
def list_requests():
    path_query = request.args.get("path")
    mocked_filter = _parse_mocked_filter(request.args.get("mocked"))
    from_dt = _parse_query_datetime(request.args.get("from"))
    to_dt = _parse_query_datetime(request.args.get("to"))
    before_cursor = request.args.get("before")

    snapshot = _get_history_snapshot()
    oldest_available_timestamp = snapshot[0]["timestamp"] if snapshot else None

    filtered = [entry for entry in snapshot if _matches_filters(entry, path_query, mocked_filter, from_dt, to_dt)]
    if before_cursor:
        # Tie-break for entries sharing the exact same millisecond timestamp as the cursor:
        # strict "<" means a same-timestamp sibling positioned before the cursor entry in
        # MockServer's own return order could be skipped rather than shown on the next page.
        # Documented, accepted known limitation (see design.md) rather than solved with a
        # stable per-entry id - collisions at millisecond precision are rare at this scale.
        filtered = [entry for entry in filtered if entry["timestamp"] < before_cursor]

    has_more = len(filtered) > REQUEST_HISTORY_LIMIT
    page = filtered[-REQUEST_HISTORY_LIMIT:]
    newest_first = list(reversed(page))

    oldest_available_dt = _parse_entry_datetime(oldest_available_timestamp)
    range_truncated = bool(from_dt and oldest_available_dt and from_dt < oldest_available_dt)

    return jsonify(
        {
            "entries": newest_first,
            "hasMore": has_more,
            "oldestAvailableTimestamp": oldest_available_timestamp,
            "rangeTruncated": range_truncated,
        }
    )


@app.get("/mock-ui/api/requests/stream")
def stream_requests():
    path_query = request.args.get("path")
    mocked_filter = _parse_mocked_filter(request.args.get("mocked"))
    # Deliberately no from/to here - a live-tailed entry is always "now," so a historical time
    # range doesn't have a sensible reading against it. See design.md's "time range filter does
    # not scope the live tail" decision.

    def event_stream():
        # Start tailing from "now" - the page loads existing history separately via
        # /mock-ui/api/requests, so the stream should only push genuinely new arrivals. Reads
        # the shared snapshot rather than polling MockServer itself - see the poller comment
        # above.
        snapshot = _get_history_snapshot()
        last_timestamp = snapshot[-1]["timestamp"] if snapshot else ""
        while True:
            time.sleep(REQUEST_STREAM_POLL_SECONDS)
            snapshot = _get_history_snapshot()
            new_entries = [
                entry
                for entry in snapshot
                if entry["timestamp"] > last_timestamp and _matches_filters(entry, path_query, mocked_filter, None, None)
            ]
            for entry in new_entries:
                yield f"data: {json.dumps(entry)}\n\n"
            if new_entries:
                last_timestamp = new_entries[-1]["timestamp"]

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/mock-ui/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    # Started here rather than at module import time so importing app.py (e.g. from
    # test_app.py) doesn't spin up a thread that tries to reach MOCKSERVER_URL.
    threading.Thread(target=_history_poller_loop, daemon=True).start()

    # Flask's dev server is fine for this POC's scale; threaded=True keeps
    # concurrent requests from serializing behind each other. A real
    # deployment would front this with a WSGI server (gunicorn/waitress)
    # instead of running this block.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threaded=True)
