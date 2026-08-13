import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

from flask import Flask, Response, jsonify, request, send_from_directory

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mock-ui")


class Target:
    """One configured MockServer instance: its identity plus its own history-poller state.

    The history-poller fields (lock/snapshot/reset generation) used to be module-level
    globals shared by a single implicit target; each Target now owns its own, so N
    configured targets get N independent shared snapshots polled by N independent
    threads - see design.md's "per-target poller" decision.
    """

    def __init__(self, target_id, label, url):
        self.id = target_id
        self.label = label
        self.url = url
        self.history_lock = threading.Lock()
        self.history_snapshot = []
        self.history_reset_generation = 0


def _parse_targets():
    """Builds the configured Target list from MOCKSERVER_TARGETS, or a single
    MOCKSERVER_URL-based fallback target when it's unset - see design.md's
    "Configuration shape" decision for the migration rationale."""
    raw = os.environ.get("MOCKSERVER_TARGETS")
    if not raw:
        url = os.environ.get("MOCKSERVER_URL", "http://mockserver")
        return [Target("default", "Default", url)]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"MOCKSERVER_TARGETS is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("MOCKSERVER_TARGETS must be a non-empty JSON array")

    targets = []
    seen_ids = set()
    for index, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            raise ValueError(f"MOCKSERVER_TARGETS[{index}] must be a JSON object")
        missing = [field for field in ("id", "label", "url") if not entry.get(field)]
        if missing:
            raise ValueError(f"MOCKSERVER_TARGETS[{index}] missing required field(s): {', '.join(missing)}")
        target_id = entry["id"]
        if target_id in seen_ids:
            raise ValueError(f"MOCKSERVER_TARGETS has a duplicate id: {target_id!r}")
        seen_ids.add(target_id)
        targets.append(Target(target_id, entry["label"], entry["url"]))
    return targets


try:
    TARGETS = _parse_targets()
except ValueError as exc:
    # Fail fast and loud at startup rather than serve a partially-broken target list -
    # see design.md's "Risks / Trade-offs".
    logger.error("invalid MOCKSERVER_TARGETS configuration: %s", exc)
    raise SystemExit(1) from exc

TARGETS_BY_ID = {target.id: target for target in TARGETS}
# Used whenever a caller omits ?server= - the first configured target, so existing
# direct API callers that don't know about multi-target keep working. See design.md.
DEFAULT_TARGET = TARGETS[0]

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


def _resolve_target():
    """Resolves the ?server= query param against TARGETS_BY_ID, defaulting to
    DEFAULT_TARGET when omitted; raises a 404 MockServerError for an unknown id."""
    server_id = request.args.get("server")
    if server_id is None:
        return DEFAULT_TARGET
    target = TARGETS_BY_ID.get(server_id)
    if target is None:
        known = ", ".join(TARGETS_BY_ID)
        raise MockServerError(404, f"unknown server {server_id!r}; known servers: {known}")
    return target


def _mockserver_put(target, path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{target.url}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
    except OSError as exc:
        # Catches both urllib.error.URLError (a URLError subclass) for connect-time failures
        # and raw connection errors like ConnectionResetError that can surface mid-request if
        # MockServer's pod is killed while a request is in flight - both are OSError subclasses.
        # Previously only URLError was caught, so a mid-request reset (e.g. from a MockServer
        # restart racing the shared history poller) crashed whatever caller was in flight; for
        # the poller specifically, that permanently killed its background thread with no
        # supervisor to restart it. See fix-recent-requests-stale-rows/design.md.
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


@app.get("/mock-ui/api/servers")
def list_servers():
    return jsonify([{"id": target.id, "label": target.label} for target in TARGETS])


@app.get("/mock-ui/api/mocks")
def list_mocks():
    target = _resolve_target()
    expectations = _mockserver_put(target, "/mockserver/retrieve?type=ACTIVE_EXPECTATIONS", {}) or []
    mocks = [
        to_friendly(expectation)
        for expectation in expectations
        if expectation.get("priority", MOCK_PRIORITY) != CATCH_ALL_PRIORITY
    ]
    return jsonify(mocks)


@app.post("/mock-ui/api/mocks")
def create_mock():
    target = _resolve_target()
    payload = request.get_json(force=True, silent=True) or {}
    expectation = to_expectation(payload)
    created = _mockserver_put(target, "/mockserver/expectation", expectation)
    if not created:
        raise MockServerError(502, "MockServer did not return the created expectation")
    return jsonify(to_friendly(created[0])), 201


@app.put("/mock-ui/api/mocks/<mock_id>")
def update_mock(mock_id):
    target = _resolve_target()
    payload = request.get_json(force=True, silent=True) or {}
    expectation = to_expectation(payload, expectation_id=mock_id)
    updated = _mockserver_put(target, "/mockserver/expectation", expectation)
    if not updated:
        raise MockServerError(502, "MockServer did not return the updated expectation")
    return jsonify(to_friendly(updated[0]))


@app.delete("/mock-ui/api/mocks/<mock_id>")
def delete_mock(mock_id):
    target = _resolve_target()
    _mockserver_put(target, "/mockserver/clear", {"id": mock_id})
    return "", 204


REQUEST_HISTORY_LIMIT = 40
REQUEST_STREAM_POLL_SECONDS = 1
# Comfortably under typical proxy/ALB idle-connection timeouts (commonly ~60s by default),
# so a live tail with no new requests never goes long enough without a byte on the wire to
# look idle to an intermediate proxy. See design.md's heartbeat decision.
HEARTBEAT_INTERVAL_SECONDS = 15


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
# One background thread per configured Target fetches that target's full (unfiltered,
# unpaginated) request log on REQUEST_STREAM_POLL_SECONDS cadence, regardless of how many
# browser tabs are open, and every request/connection reads from that target's shared,
# continuously-rebuilt snapshot instead of hitting MockServer itself. Previously each SSE
# connection polled MockServer independently - with N open tabs that meant N re-fetches and N
# re-parses of the entire (potentially multi-MB) log every second, which is what collapsed the
# page under concurrent viewers. See docs/studies/2026-08-09-recent-requests-resilience.md for
# the full reproduction, and design.md's "per-target poller" decision for why this is now one
# thread per target rather than one thread total.
#
# The snapshot holds nothing MockServer doesn't already have and nothing survives past the next
# tick, so this isn't the kind of independent cache the mocks CRUD flows are required to avoid -
# see design.md in the improve-recent-requests-resilience change for why.


def _detect_history_reset(previous_snapshot, new_snapshot):
    """True if new_snapshot looks like MockServer's log was reset rather than just polled again.

    MockServer's request log is append-only from the newest end and only evicts from the
    oldest end, so a legitimate poll's newest entry should either match what we already saw or
    be a genuinely later one still preceded by it. A reset instead makes the previously-newest
    entry vanish entirely - either because the new snapshot is empty, or because it's non-empty
    but doesn't contain that entry's timestamp anywhere.
    """
    if not previous_snapshot:
        return False
    if not new_snapshot:
        return True
    previous_newest_timestamp = previous_snapshot[-1]["timestamp"]
    return not any(entry["timestamp"] == previous_newest_timestamp for entry in new_snapshot)


def _poll_history_once(target):
    start = time.monotonic()
    try:
        raw_entries = _mockserver_put(target, "/mockserver/retrieve?type=REQUEST_RESPONSES", {}) or []
    except MockServerError as exc:
        # Keep serving the previous snapshot rather than blanking it out on a transient failure.
        logger.warning("history poll failed for target %s after %.3fs: %s", target.id, time.monotonic() - start, exc)
        return
    latency = time.monotonic() - start
    built = [_build_history_entry(entry) for entry in raw_entries]
    with target.history_lock:
        reset_detected = _detect_history_reset(target.history_snapshot, built)
        previous_count = len(target.history_snapshot)
        if reset_detected:
            target.history_reset_generation += 1
        generation = target.history_reset_generation
        target.history_snapshot = built
    if reset_detected:
        logger.warning(
            "history reset detected for target %s (generation now %d): previous snapshot had %d entries, new snapshot has %d entries",
            target.id,
            generation,
            previous_count,
            len(built),
        )
    logger.info("history poll succeeded for target %s in %.3fs (%d entries)", target.id, latency, len(built))


def _history_poller_loop(target):
    while True:
        try:
            _poll_history_once(target)
        except Exception:
            # _poll_history_once already handles the expected MockServerError case (logs and
            # keeps serving the stale snapshot) - this is a last-resort backstop so *any* other
            # unexpected exception can't silently kill this daemon thread and permanently freeze
            # Recent Requests for the rest of this mock-ui process's life, with nothing left to
            # ever retry MockServer again. See fix-recent-requests-stale-rows/design.md.
            logger.exception("history poller tick failed unexpectedly for target %s - continuing", target.id)
        time.sleep(REQUEST_STREAM_POLL_SECONDS)


def _get_history_snapshot(target):
    with target.history_lock:
        return list(target.history_snapshot)


def _get_history_reset_generation(target):
    with target.history_lock:
        return target.history_reset_generation


@app.get("/mock-ui/api/requests")
def list_requests():
    target = _resolve_target()
    path_query = request.args.get("path")
    mocked_filter = _parse_mocked_filter(request.args.get("mocked"))
    from_dt = _parse_query_datetime(request.args.get("from"))
    to_dt = _parse_query_datetime(request.args.get("to"))
    before_cursor = request.args.get("before")

    snapshot = _get_history_snapshot(target)
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
    target = _resolve_target()
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
        logger.info("SSE client connected (target=%s, path=%r, mocked=%r)", target.id, path_query, mocked_filter)
        snapshot = _get_history_snapshot(target)
        last_timestamp = snapshot[-1]["timestamp"] if snapshot else ""
        last_sent = time.monotonic()
        # Initialized to the *current* generation so a freshly-opened connection never gets a
        # reset notice for one that already happened before it connected.
        last_seen_generation = _get_history_reset_generation(target)
        try:
            while True:
                time.sleep(REQUEST_STREAM_POLL_SECONDS)
                current_generation = _get_history_reset_generation(target)
                if current_generation != last_seen_generation:
                    # Named SSE event, not the heartbeat comment (invisible to EventSource) or
                    # a regular data: message (which the client reads as one request entry) -
                    # see design.md's signal-mechanism decision.
                    yield "event: history-reset\ndata: {}\n\n"
                    last_seen_generation = current_generation
                    last_sent = time.monotonic()
                    # The post-reset snapshot's entries are unrelated to what we've already
                    # sent - resync last_timestamp to "now" so the live tail only resumes with
                    # genuinely new entries going forward, instead of replaying the whole
                    # post-reset log through the tail on top of the client's own resync fetch.
                    snapshot = _get_history_snapshot(target)
                    last_timestamp = snapshot[-1]["timestamp"] if snapshot else ""
                    continue
                snapshot = _get_history_snapshot(target)
                new_entries = [
                    entry
                    for entry in snapshot
                    if entry["timestamp"] > last_timestamp and _matches_filters(entry, path_query, mocked_filter, None, None)
                ]
                for entry in new_entries:
                    yield f"data: {json.dumps(entry)}\n\n"
                    last_sent = time.monotonic()
                if new_entries:
                    last_timestamp = new_entries[-1]["timestamp"]
                elif time.monotonic() - last_sent >= HEARTBEAT_INTERVAL_SECONDS:
                    # SSE comment line: ignored by EventSource.onmessage, but keeps bytes
                    # flowing so an idle-connection timeout in front of us never trips.
                    yield ": ping\n\n"
                    last_sent = time.monotonic()
        finally:
            logger.info("SSE client disconnected (target=%s, path=%r, mocked=%r)", target.id, path_query, mocked_filter)

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
    # test_app.py) doesn't spin up threads that try to reach any configured target. One daemon
    # thread per configured target - see design.md's "per-target poller" decision.
    for mockserver_target in TARGETS:
        threading.Thread(target=_history_poller_loop, args=(mockserver_target,), daemon=True).start()

    # Flask's dev server is fine for this POC's scale; threaded=True keeps
    # concurrent requests from serializing behind each other. A real
    # deployment would front this with a WSGI server (gunicorn/waitress)
    # instead of running this block.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threaded=True)
