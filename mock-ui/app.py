import json
import os
import urllib.error
import urllib.request

from flask import Flask, jsonify, request, send_from_directory

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


@app.get("/mock-ui/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    # Flask's dev server is fine for this POC's scale; threaded=True keeps
    # concurrent requests from serializing behind each other. A real
    # deployment would front this with a WSGI server (gunicorn/waitress)
    # instead of running this block.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threaded=True)
