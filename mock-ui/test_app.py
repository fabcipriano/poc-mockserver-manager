import os
import unittest
from unittest.mock import patch

import app as app_module
from app import MockServerError, Target, _is_forwarded_response


def _clear_target_env():
    os.environ.pop("MOCKSERVER_TARGETS", None)
    os.environ.pop("MOCKSERVER_URL", None)


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
    def _run_poll(self, previous_snapshot, raw_response):
        target = Target("test", "Test", "http://mockserver-test")
        target.history_snapshot = list(previous_snapshot)
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
        ), patch.object(target, "history_reset_generation", 0), patch.object(target, "history_snapshot", []):
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


if __name__ == "__main__":
    unittest.main()
