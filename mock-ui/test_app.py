import unittest
from unittest.mock import patch

import app as app_module
from app import MockServerError, _is_forwarded_response


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
        with patch.object(app_module, "_mockserver_put", return_value=[]):
            with self.assertLogs("mock-ui", level="INFO") as captured:
                app_module._poll_history_once()
        self.assertTrue(any("history poll succeeded" in message for message in captured.output))

    def test_failed_poll_is_logged(self):
        with patch.object(app_module, "_mockserver_put", side_effect=MockServerError(502, "could not reach MockServer")):
            with self.assertLogs("mock-ui", level="WARNING") as captured:
                app_module._poll_history_once()
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
        with patch.object(app_module, "_history_snapshot", list(previous_snapshot)), patch.object(
            app_module, "_history_reset_generation", 0
        ), patch.object(app_module, "_mockserver_put", return_value=raw_response):
            app_module._poll_history_once()
            return app_module._history_reset_generation

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
        with patch.object(
            app_module.urllib.request, "urlopen", side_effect=ConnectionResetError(104, "Connection reset by peer")
        ):
            with self.assertRaises(MockServerError):
                app_module._mockserver_put("/mockserver/retrieve?type=REQUEST_RESPONSES", {})


class PollerLoopResilienceTests(unittest.TestCase):
    def test_loop_continues_after_an_unexpected_exception(self):
        call_count = {"n": 0}

        def flaky_poll():
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

        with patch.object(app_module, "_poll_history_once", side_effect=flaky_poll), patch.object(
            app_module.time, "sleep", side_effect=fake_sleep
        ):
            with self.assertRaises(StopLoop):
                app_module._history_poller_loop()

        # Called again after the first call raised - proves one bad tick doesn't kill the loop.
        self.assertGreaterEqual(call_count["n"], 2)


class StreamHistoryResetEventTests(unittest.TestCase):
    def test_generation_bump_emits_history_reset_event(self):
        with patch.object(app_module, "REQUEST_STREAM_POLL_SECONDS", 0), patch.object(
            app_module, "HEARTBEAT_INTERVAL_SECONDS", 0
        ), patch.object(app_module, "_history_reset_generation", 0), patch.object(app_module, "_history_snapshot", []):
            client = app_module.app.test_client()
            response = client.get("/mock-ui/api/requests/stream")
            # First tick: no reset yet, nothing new - falls through to the heartbeat, which
            # also establishes this connection's last_seen_generation at 0.
            next(response.response)
            app_module._history_reset_generation = 1
            second_chunk = next(response.response)
            response.response.close()
        if isinstance(second_chunk, bytes):
            second_chunk = second_chunk.decode("utf-8")
        self.assertEqual(second_chunk, "event: history-reset\ndata: {}\n\n")


if __name__ == "__main__":
    unittest.main()
