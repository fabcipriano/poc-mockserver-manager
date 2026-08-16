import json
import os
import shutil
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock, patch

import app as app_module
from app import MockServerError, Target, _is_forwarded_response

_TEST_HISTORY_DATA_DIR = None


def setUpModule():
    # Each target's SQLite history file lives under here for the whole test run, isolated from
    # both a real deployment's REQUEST_HISTORY_DATA_DIR and any other test run - see design.md's
    # "no PVC, local/ephemeral storage" decision.
    global _TEST_HISTORY_DATA_DIR
    _TEST_HISTORY_DATA_DIR = tempfile.mkdtemp(prefix="mock-ui-test-history-")
    app_module.REQUEST_HISTORY_DATA_DIR = _TEST_HISTORY_DATA_DIR


def tearDownModule():
    shutil.rmtree(_TEST_HISTORY_DATA_DIR, ignore_errors=True)


def _clear_target_env():
    os.environ.pop("MOCKSERVER_TARGETS", None)
    os.environ.pop("MOCKSERVER_URL", None)


def _fresh_target(label="test"):
    """A Target with a unique id, so its SQLite file never collides with another test's."""
    return Target(f"{label}-{uuid.uuid4().hex[:8]}", "Test", "http://mockserver-test")


class IsForwardedResponseTests(unittest.TestCase):
    def test_canned_mock_response_is_not_forwarded(self):
        # Shape produced by this tool's own to_expectation(): no reasonPhrase, no timing header.
        http_response = {
            "statusCode": 200,
            "headers": {"Content-Type": ["application/json"]},
            "body": {"firstname": "Mocked"},
        }
        self.assertFalse(_is_forwarded_response(http_response))

    def test_forwarded_response_with_reason_phrase_is_forwarded(self):
        http_response = {
            "statusCode": 200,
            "reasonPhrase": "OK",
            "body": "real-backend-response",
        }
        self.assertTrue(_is_forwarded_response(http_response))

    def test_forwarded_response_with_timing_header_is_forwarded(self):
        http_response = {
            "statusCode": 200,
            "headers": {"x-mockserver-response-time-ms": ["25"]},
            "body": "real-backend-response",
        }
        self.assertTrue(_is_forwarded_response(http_response))

    def test_timing_header_match_is_case_insensitive(self):
        http_response = {
            "statusCode": 200,
            "headers": {"X-MockServer-Response-Time-Ms": ["25"]},
        }
        self.assertTrue(_is_forwarded_response(http_response))

    def test_response_with_no_headers_or_reason_phrase_is_not_forwarded(self):
        self.assertFalse(_is_forwarded_response({"statusCode": 404}))


class HistoryPollerLoggingTests(unittest.TestCase):
    def test_successful_poll_is_logged(self):
        target = Target("test", "Test", "http://mockserver-test")
        with patch.object(app_module, "_mockserver_put", return_value=[]):
            with self.assertLogs("mock-ui", level="INFO") as captured:
                app_module._poll_history_once(target)
        self.assertTrue(any("history poll succeeded" in message for message in captured.output))

    def test_failed_poll_is_logged(self):
        target = Target("test", "Test", "http://mockserver-test")
        with patch.object(app_module, "_mockserver_put", side_effect=MockServerError(502, "could not reach MockServer")):
            with self.assertLogs("mock-ui", level="WARNING") as captured:
                app_module._poll_history_once(target)
        self.assertTrue(any("history poll failed" in message for message in captured.output))


def _built_entry(timestamp):
    return {
        "timestamp": timestamp,
        "method": "GET",
        "path": "/x",
        "statusCode": 200,
        "mocked": True,
        "requestHeaders": [],
        "requestBody": None,
        "responseHeaders": [],
        "responseBody": None,
    }


def _raw_entry(timestamp):
    return {
        "timestamp": timestamp,
        "httpRequest": {"method": "GET", "path": "/x"},
        "httpResponse": {"statusCode": 200},
    }


class HistoryResetDetectionTests(unittest.TestCase):
    def _run_poll(self, previous_entries, raw_response):
        target = _fresh_target()
        target.last_polled_entries = list(previous_entries)
        with patch.object(app_module, "_mockserver_put", return_value=raw_response):
            app_module._poll_history_once(target)
            return target.history_reset_generation

    def test_empty_poll_after_non_empty_snapshot_is_a_reset(self):
        previous = [_built_entry("2026-08-11 10:00:00.000000")]
        generation = self._run_poll(previous, [])
        self.assertEqual(generation, 1)

    def test_previous_newest_missing_from_non_empty_new_snapshot_is_a_reset(self):
        previous = [_built_entry("2026-08-11 10:00:00.000000")]
        raw = [_raw_entry("2026-08-11 10:05:00.000000")]
        generation = self._run_poll(previous, raw)
        self.assertEqual(generation, 1)

    def test_normal_growth_is_not_a_reset(self):
        previous = [_built_entry("2026-08-11 10:00:00.000000")]
        raw = [
            _raw_entry("2026-08-11 10:00:00.000000"),
            _raw_entry("2026-08-11 10:00:01.000000"),
        ]
        generation = self._run_poll(previous, raw)
        self.assertEqual(generation, 0)

    def test_first_ever_poll_is_not_a_reset(self):
        generation = self._run_poll([], [_raw_entry("2026-08-11 10:00:00.000000")])
        self.assertEqual(generation, 0)


class StreamHeartbeatTests(unittest.TestCase):
    def test_heartbeat_is_sent_on_an_idle_stream(self):
        # Zeroing both intervals means the very first tick has nothing new to send and the
        # heartbeat threshold is already crossed, without the test sleeping for real.
        with patch.object(app_module, "REQUEST_STREAM_POLL_SECONDS", 0), patch.object(
            app_module, "HEARTBEAT_INTERVAL_SECONDS", 0
        ):
            client = app_module.app.test_client()
            response = client.get("/mock-ui/api/requests/stream")
            chunk = next(response.response)
            response.response.close()
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        self.assertEqual(chunk, ": ping\n\n")


class MockserverPutErrorHandlingTests(unittest.TestCase):
    def test_mid_request_connection_reset_is_raised_as_mockservererror(self):
        # The failure mode that crashed the poller thread before this fix: a connection reset
        # mid-request is an OSError, but not a urllib.error.URLError - see design.md's addendum.
        target = Target("test", "Test", "http://mockserver-test")
        with patch.object(
            app_module.urllib.request, "urlopen", side_effect=ConnectionResetError(104, "Connection reset by peer")
        ):
            with self.assertRaises(MockServerError):
                app_module._mockserver_put(target, "/mockserver/retrieve?type=REQUEST_RESPONSES", {})


class PollerLoopResilienceTests(unittest.TestCase):
    def test_loop_continues_after_an_unexpected_exception(self):
        call_count = {"n": 0}

        def flaky_poll(_target):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("boom")

        class StopLoop(Exception):
            pass

        sleep_calls = {"n": 0}

        def fake_sleep(_seconds):
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 2:
                raise StopLoop

        target = Target("test", "Test", "http://mockserver-test")
        with patch.object(app_module, "_poll_history_once", side_effect=flaky_poll), patch.object(
            app_module.time, "sleep", side_effect=fake_sleep
        ):
            with self.assertRaises(StopLoop):
                app_module._history_poller_loop(target)

        # Called again after the first call raised - proves one bad tick doesn't kill the loop.
        self.assertGreaterEqual(call_count["n"], 2)


class StreamHistoryResetEventTests(unittest.TestCase):
    def test_generation_bump_emits_history_reset_event(self):
        target = app_module.DEFAULT_TARGET
        with patch.object(app_module, "REQUEST_STREAM_POLL_SECONDS", 0), patch.object(
            app_module, "HEARTBEAT_INTERVAL_SECONDS", 0
        ), patch.object(target, "history_reset_generation", 0):
            client = app_module.app.test_client()
            response = client.get("/mock-ui/api/requests/stream")
            # First tick: no reset yet, nothing new - falls through to the heartbeat, which
            # also establishes this connection's last_seen_generation at 0.
            next(response.response)
            target.history_reset_generation = 1
            second_chunk = next(response.response)
            response.response.close()
        if isinstance(second_chunk, bytes):
            second_chunk = second_chunk.decode("utf-8")
        self.assertEqual(second_chunk, "event: history-reset\ndata: {}\n\n")


def _seed(target, raw_entries):
    with patch.object(app_module, "_mockserver_put", return_value=raw_entries):
        app_module._poll_history_once(target)


def _rows(target):
    conn = app_module._open_history_db(target)
    try:
        return conn.execute("SELECT timestamp FROM requests ORDER BY id ASC").fetchall()
    finally:
        conn.close()


class HistoryPersistenceTests(unittest.TestCase):
    """Covers the SQLite-backed accumulation the history poller now does: upsert-not-replace,
    dedup on repeated ticks, retention pruning, and per-target isolation - see design.md."""

    def test_dedup_on_repeated_poll_ticks(self):
        # The same MockServer log entry showing up again on a later tick (because MockServer
        # hasn't evicted it yet) must not create a second row.
        target = _fresh_target()
        raw = [_raw_entry("2026-08-15 10:00:00.000000")]
        _seed(target, raw)
        _seed(target, raw)
        self.assertEqual(len(_rows(target)), 1)

    def test_entry_survives_mockserver_evicting_it_from_a_later_poll(self):
        # Reproduces the bug this change fixes: once mock-ui has seen an entry, a later tick
        # where MockServer's own retrieve response no longer includes it (simulating
        # maxLogEntries eviction) must not remove it from mock-ui's own store.
        target = _fresh_target()
        early = _raw_entry("2026-08-15 10:00:00.000000")
        _seed(target, [early])
        later_only = [_raw_entry("2026-08-15 10:05:00.000000")]
        _seed(target, later_only)
        timestamps = [row[0] for row in _rows(target)]
        self.assertIn("2026-08-15 10:00:00.000000", timestamps)
        self.assertIn("2026-08-15 10:05:00.000000", timestamps)

    def test_retention_prunes_oldest_rows_past_the_cap(self):
        target = _fresh_target()
        raw = [_raw_entry(f"2026-08-15 10:00:0{i}.000000") for i in range(3)]
        with patch.object(app_module, "REQUEST_HISTORY_RETENTION_ROWS", 2):
            _seed(target, raw)
        timestamps = [row[0] for row in _rows(target)]
        self.assertEqual(timestamps, ["2026-08-15 10:00:01.000000", "2026-08-15 10:00:02.000000"])

    def test_per_target_history_is_isolated(self):
        target_a = _fresh_target("a")
        target_b = _fresh_target("b")
        _seed(target_a, [_raw_entry("2026-08-15 10:00:00.000000")])
        _seed(target_b, [_raw_entry("2026-08-15 11:00:00.000000")])
        self.assertEqual([row[0] for row in _rows(target_a)], ["2026-08-15 10:00:00.000000"])
        self.assertEqual([row[0] for row in _rows(target_b)], ["2026-08-15 11:00:00.000000"])

    def test_default_retention_cap_covers_the_reproduced_load_test_scenario(self):
        # scripts/load-test-recent-requests.sh sends TOTAL_REQUESTS (default 100,000) distinct
        # requests. The retention cap must stay at or above that, or mock-ui's own pruning would
        # silently re-introduce the same class of loss this change was built to fix (confirmed by
        # directly running the upsert/prune path at that scale - see design.md's retention
        # decision and tasks.md's note on the discrepancy this caught during implementation).
        self.assertGreaterEqual(app_module.REQUEST_HISTORY_RETENTION_ROWS, 100000)


class HistoryReadPathTests(unittest.TestCase):
    """Covers list_requests/stream_requests reading from SQLite: rowid-based pagination cursor
    and the path filter's LIKE-escaping - see design.md's pagination-cursor decision."""

    def test_pagination_cursor_pages_through_history_newest_first(self):
        target = _fresh_target()
        raw = [_raw_entry(f"2026-08-15 10:00:0{i}.000000") for i in range(5)]
        _seed(target, raw)
        client = app_module.app.test_client()
        with patch.object(app_module, "REQUEST_HISTORY_LIMIT", 2), patch.dict(
            app_module.TARGETS_BY_ID, {target.id: target}
        ):
            first = client.get(f"/mock-ui/api/requests?server={target.id}").get_json()
            self.assertEqual(
                [e["timestamp"] for e in first["entries"]],
                ["2026-08-15 10:00:04.000000", "2026-08-15 10:00:03.000000"],
            )
            self.assertTrue(first["hasMore"])

            second = client.get(
                f"/mock-ui/api/requests?server={target.id}&before={first['entries'][-1]['cursor']}"
            ).get_json()
            self.assertEqual(
                [e["timestamp"] for e in second["entries"]],
                ["2026-08-15 10:00:02.000000", "2026-08-15 10:00:01.000000"],
            )
            self.assertTrue(second["hasMore"])

            third = client.get(
                f"/mock-ui/api/requests?server={target.id}&before={second['entries'][-1]['cursor']}"
            ).get_json()
            self.assertEqual([e["timestamp"] for e in third["entries"]], ["2026-08-15 10:00:00.000000"])
            self.assertFalse(third["hasMore"])

    def test_path_filter_treats_percent_and_underscore_as_literal_characters(self):
        # LIKE treats % and _ as wildcards unless escaped - without _like_escape, a path
        # containing them would match unrelated paths instead of just its own literal text.
        target = _fresh_target()
        raw = [
            {
                "timestamp": "2026-08-15 10:00:00.000000",
                "httpRequest": {"method": "GET", "path": "/100%_off"},
                "httpResponse": {"statusCode": 200},
            },
            {
                "timestamp": "2026-08-15 10:00:01.000000",
                "httpRequest": {"method": "GET", "path": "/100Xoff"},
                "httpResponse": {"statusCode": 200},
            },
        ]
        _seed(target, raw)
        client = app_module.app.test_client()
        with patch.dict(app_module.TARGETS_BY_ID, {target.id: target}):
            response = client.get(
                "/mock-ui/api/requests", query_string={"server": target.id, "path": "100%_off"}
            )
        entries = response.get_json()["entries"]
        self.assertEqual([e["path"] for e in entries], ["/100%_off"])


class TargetParsingTests(unittest.TestCase):
    def test_multiple_targets_parsed_from_json(self):
        targets_json = (
            '[{"id":"public","label":"Gateway Public","url":"http://mockserver-public"},'
            '{"id":"private","label":"Gateway Private","url":"http://mockserver-private"}]'
        )
        with patch.dict(os.environ, {"MOCKSERVER_TARGETS": targets_json}):
            targets = app_module._parse_targets()
        self.assertEqual([t.id for t in targets], ["public", "private"])
        self.assertEqual(targets[0].label, "Gateway Public")
        self.assertEqual(targets[0].url, "http://mockserver-public")

    def test_falls_back_to_mockserver_url_when_targets_unset(self):
        with patch.dict(os.environ, {}):
            _clear_target_env()
            os.environ["MOCKSERVER_URL"] = "http://legacy-mockserver"
            targets = app_module._parse_targets()
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].id, "default")
        self.assertEqual(targets[0].label, "Default")
        self.assertEqual(targets[0].url, "http://legacy-mockserver")

    def test_falls_back_to_default_url_when_nothing_set(self):
        with patch.dict(os.environ, {}):
            _clear_target_env()
            targets = app_module._parse_targets()
        self.assertEqual(targets[0].url, "http://mockserver")

    def test_invalid_json_raises(self):
        with patch.dict(os.environ, {"MOCKSERVER_TARGETS": "not json"}):
            with self.assertRaises(ValueError):
                app_module._parse_targets()

    def test_missing_field_raises(self):
        with patch.dict(os.environ, {"MOCKSERVER_TARGETS": '[{"id":"public","label":"Public"}]'}):
            with self.assertRaises(ValueError):
                app_module._parse_targets()

    def test_duplicate_id_raises(self):
        targets_json = '[{"id":"public","label":"A","url":"http://a"},{"id":"public","label":"B","url":"http://b"}]'
        with patch.dict(os.environ, {"MOCKSERVER_TARGETS": targets_json}):
            with self.assertRaises(ValueError):
                app_module._parse_targets()

    def test_empty_array_raises(self):
        with patch.dict(os.environ, {"MOCKSERVER_TARGETS": "[]"}):
            with self.assertRaises(ValueError):
                app_module._parse_targets()


class ServersEndpointTests(unittest.TestCase):
    def test_list_servers_returns_id_and_label_only(self):
        client = app_module.app.test_client()
        response = client.get("/mock-ui/api/servers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [{"id": t.id, "label": t.label} for t in app_module.TARGETS])


class ServerResolutionTests(unittest.TestCase):
    def test_unknown_server_returns_404(self):
        client = app_module.app.test_client()
        response = client.get("/mock-ui/api/mocks?server=nonexistent")
        self.assertEqual(response.status_code, 404)
        self.assertIn("unknown server", response.get_json()["error"])

    def test_omitted_server_resolves_to_default_target(self):
        with patch.object(app_module, "_mockserver_put", return_value=[]) as mock_put:
            client = app_module.app.test_client()
            response = client.get("/mock-ui/api/mocks")
        self.assertEqual(response.status_code, 200)
        called_target = mock_put.call_args[0][0]
        self.assertIs(called_target, app_module.DEFAULT_TARGET)


class RuntimeConfigParsingTests(unittest.TestCase):
    def test_returns_default_when_unset(self):
        with patch.dict(os.environ, {}):
            os.environ.pop("REQUEST_HISTORY_LIMIT", None)
            value = app_module._parse_positive_int_env("REQUEST_HISTORY_LIMIT", 40)
        self.assertEqual(value, 40)

    def test_override_takes_effect(self):
        with patch.dict(os.environ, {"REQUEST_HISTORY_LIMIT": "100"}):
            value = app_module._parse_positive_int_env("REQUEST_HISTORY_LIMIT", 40)
        self.assertEqual(value, 100)

    def test_non_integer_raises(self):
        with patch.dict(os.environ, {"HEARTBEAT_INTERVAL_SECONDS": "soon"}):
            with self.assertRaises(ValueError):
                app_module._parse_positive_int_env("HEARTBEAT_INTERVAL_SECONDS", 15)

    def test_zero_raises(self):
        with patch.dict(os.environ, {"REQUEST_STREAM_POLL_SECONDS": "0"}):
            with self.assertRaises(ValueError):
                app_module._parse_positive_int_env("REQUEST_STREAM_POLL_SECONDS", 1)

    def test_negative_raises(self):
        with patch.dict(os.environ, {"REQUEST_STREAM_POLL_SECONDS": "-1"}):
            with self.assertRaises(ValueError):
                app_module._parse_positive_int_env("REQUEST_STREAM_POLL_SECONDS", 1)


def _fake_bedrock_client(response_text):
    client = MagicMock()
    client.converse.return_value = {"output": {"message": {"content": [{"text": response_text}]}}}
    return client


SAMPLE_SOURCE_ENTRY = {
    "timestamp": "2026-08-14 10:00:00.000000",
    "method": "GET",
    "path": "/booking/1",
    "statusCode": 200,
    "mocked": False,
    "requestHeaders": [],
    "requestBody": None,
    "responseHeaders": [],
    "responseBody": {"firstname": "Ada"},
}


class MockGenerationDraftEndpointTests(unittest.TestCase):
    def test_rejects_empty_source_entries(self):
        client = app_module.app.test_client()
        response = client.post("/mock-ui/api/mock-generation/draft", json={"sourceEntries": [], "mode": "edge-cases"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("sourceEntries", response.get_json()["error"])

    def test_rejects_oversized_source_entries(self):
        oversized = [SAMPLE_SOURCE_ENTRY] * (app_module.MOCK_GENERATION_MAX_SOURCE_ENTRIES + 1)
        client = app_module.app.test_client()
        response = client.post("/mock-ui/api/mock-generation/draft", json={"sourceEntries": oversized, "mode": "edge-cases"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("at most", response.get_json()["error"])

    def test_rejects_invalid_mode(self):
        client = app_module.app.test_client()
        response = client.post(
            "/mock-ui/api/mock-generation/draft",
            json={"sourceEntries": [SAMPLE_SOURCE_ENTRY], "mode": "not-a-real-mode"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("mode must be one of", response.get_json()["error"])

    def test_returns_error_when_unavailable(self):
        with patch.object(app_module, "_bedrock_client", None):
            client = app_module.app.test_client()
            response = client.post(
                "/mock-ui/api/mock-generation/draft",
                json={"sourceEntries": [SAMPLE_SOURCE_ENTRY], "mode": "edge-cases"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.get_json()["error"])

    def test_malformed_llm_json_is_a_failed_generation_attempt(self):
        with patch.object(app_module, "_bedrock_client", _fake_bedrock_client("not valid json")):
            client = app_module.app.test_client()
            response = client.post(
                "/mock-ui/api/mock-generation/draft",
                json={"sourceEntries": [SAMPLE_SOURCE_ENTRY], "mode": "edge-cases"},
            )
        self.assertEqual(response.status_code, 502)
        self.assertIn("could not be parsed", response.get_json()["error"])

    def test_splits_valid_and_invalid_candidates(self):
        raw_items = [
            {"method": "GET", "path": "/booking/1", "statusCode": 404, "responseBody": {"error": "not found"}},
            {"method": "GET", "responseBody": {}},  # missing required "path" and "statusCode"
        ]
        with patch.object(app_module, "_bedrock_client", _fake_bedrock_client(json.dumps(raw_items))):
            client = app_module.app.test_client()
            response = client.post(
                "/mock-ui/api/mock-generation/draft",
                json={"sourceEntries": [SAMPLE_SOURCE_ENTRY], "mode": "edge-cases"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body["candidates"]), 1)
        self.assertEqual(body["candidates"][0]["path"], "/booking/1")
        self.assertEqual(len(body["rejected"]), 1)
        self.assertIn("missing required field", body["rejected"][0]["reason"])


class MockGenerationLoadEndpointTests(unittest.TestCase):
    def test_rejects_empty_mocks_list(self):
        client = app_module.app.test_client()
        response = client.post("/mock-ui/api/mock-generation/load", json={"mocks": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("mocks", response.get_json()["error"])

    def test_valid_mocks_load_through_existing_mockserver_put_path(self):
        created_expectation = {
            "id": "abc123",
            "httpRequest": {"method": "GET", "path": "/booking/1"},
            "httpResponse": {"statusCode": 200, "body": {"firstname": "Ada"}},
        }
        with patch.object(app_module, "_mockserver_put", return_value=[created_expectation]) as mock_put:
            client = app_module.app.test_client()
            response = client.post(
                "/mock-ui/api/mock-generation/load",
                json={"mocks": [{"method": "GET", "path": "/booking/1", "statusCode": 200, "responseBody": {"firstname": "Ada"}}]},
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body["loaded"]), 1)
        self.assertEqual(body["loaded"][0]["id"], "abc123")
        self.assertEqual(len(body["rejected"]), 0)
        put_args = mock_put.call_args[0]
        self.assertIs(put_args[0], app_module.DEFAULT_TARGET)
        self.assertEqual(put_args[1], "/mockserver/expectation")

    def test_invalid_mock_is_rejected_without_failing_whole_batch(self):
        created_expectation = {
            "id": "abc123",
            "httpRequest": {"method": "GET", "path": "/booking/1"},
            "httpResponse": {"statusCode": 200, "body": {}},
        }
        with patch.object(app_module, "_mockserver_put", return_value=[created_expectation]):
            client = app_module.app.test_client()
            response = client.post(
                "/mock-ui/api/mock-generation/load",
                json={
                    "mocks": [
                        {"method": "GET", "path": "/booking/1", "statusCode": 200, "responseBody": {}},
                        {"method": "GET", "responseBody": {}},  # missing required fields
                    ]
                },
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body["loaded"]), 1)
        self.assertEqual(len(body["rejected"]), 1)
        self.assertIn("missing required field", body["rejected"][0]["reason"])


class MockGenerationAvailabilityTests(unittest.TestCase):
    def test_status_reports_unavailable_without_model_id(self):
        with patch.object(app_module, "_bedrock_client", None):
            client = app_module.app.test_client()
            response = client.get("/mock-ui/api/mock-generation/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"available": False})

    def test_draft_endpoint_fails_cleanly_without_model_id(self):
        with patch.object(app_module, "_bedrock_client", None):
            client = app_module.app.test_client()
            response = client.post(
                "/mock-ui/api/mock-generation/draft",
                json={"sourceEntries": [SAMPLE_SOURCE_ENTRY], "mode": "edge-cases"},
            )
        self.assertEqual(response.status_code, 503)

    def test_app_still_serves_existing_routes_without_model_id(self):
        with patch.object(app_module, "_bedrock_client", None):
            client = app_module.app.test_client()
            response = client.get("/mock-ui/healthz")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
