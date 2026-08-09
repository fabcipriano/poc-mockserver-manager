import json
import os
import re
import time
import urllib.error
import urllib.request

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


REQUEST_HISTORY_LIMIT = 100
REQUEST_STREAM_POLL_SECONDS = 1


def _path_filter_matcher(path_query):
    """Turns a plain-text path filter into MockServer's path matcher.

    MockServer's retrieve `path` matcher is a full-match regex, not a substring
    search (confirmed live: a plain `/booking` only matches the literal path
    `/booking`, not `/booking/1`) - so a developer's plain text needs wrapping
    in `.*...*` to behave like the "contains" search they expect.
    """
    if not path_query:
        return None
    return ".*" + re.escape(path_query) + ".*"


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


def _fetch_request_history(path_query=None):
    """Returns MockServer's received-request log (oldest first), optionally filtered by path."""
    body = {}
    matcher = _path_filter_matcher(path_query)
    if matcher:
        body["path"] = matcher
    entries = _mockserver_put("/mockserver/retrieve?type=REQUEST_RESPONSES", body) or []
    history = []
    for entry in entries:
        http_request = entry.get("httpRequest") or {}
        http_response = entry.get("httpResponse") or {}
        history.append(
            {
                "timestamp": entry.get("timestamp"),
                "method": http_request.get("method"),
                "path": http_request.get("path"),
                "statusCode": http_response.get("statusCode"),
                "requestHeaders": _multimap_to_pairs(http_request.get("headers")),
                "requestBody": _observed_body(http_request.get("body")),
                "responseHeaders": _multimap_to_pairs(http_response.get("headers")),
                "responseBody": _observed_body(http_response.get("body")),
            }
        )
    return history


@app.get("/mock-ui/api/requests")
def list_requests():
    history = _fetch_request_history(request.args.get("path"))
    newest_first = list(reversed(history))
    return jsonify(newest_first[:REQUEST_HISTORY_LIMIT])


@app.get("/mock-ui/api/requests/stream")
def stream_requests():
    path_query = request.args.get("path")

    def event_stream():
        # Start tailing from "now" - the page loads existing history separately
        # via /mock-ui/api/requests, so the stream should only push genuinely
        # new arrivals, not replay what was already fetched.
        history = _fetch_request_history(path_query)
        last_timestamp = history[-1]["timestamp"] if history else ""
        while True:
            time.sleep(REQUEST_STREAM_POLL_SECONDS)
            history = _fetch_request_history(path_query)
            new_entries = [entry for entry in history if entry["timestamp"] > last_timestamp]
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
    # Flask's dev server is fine for this POC's scale; threaded=True keeps
    # concurrent requests from serializing behind each other. A real
    # deployment would front this with a WSGI server (gunicorn/waitress)
    # instead of running this block.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threaded=True)
