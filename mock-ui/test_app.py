import unittest

from app import _is_forwarded_response


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


if __name__ == "__main__":
    unittest.main()
