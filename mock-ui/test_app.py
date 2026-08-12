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


if __name__ == "__main__":
    unittest.main()
