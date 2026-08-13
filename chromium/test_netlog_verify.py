import unittest

from chromium.netlog_verify import verify_payload


class NetlogVerifyTests(unittest.TestCase):
    def setUp(self):
        self.types = {
            "FAILED": 1,
            "HTTP_TRANSACTION_READ_RESPONSE_HEADERS": 243,
            "HTTP_TRANSACTION_SEND_REQUEST_HEADERS": 238,
            "URL_REQUEST_START_JOB": 134,
        }

    def _payload(self, *events):
        return {
            "constants": {
                "logEventTypes": self.types,
                "netError": {"ERR_CONTENT_DECODING_FAILED": -330},
            },
            "events": list(events),
        }

    @staticmethod
    def _event(event_type, params=None, phase=0):
        return {
            "type": event_type,
            "phase": phase,
            "source": {"id": 7, "type": 1, "start_time": "1"},
            "params": params or {},
        }

    def test_constants_table_does_not_count_as_request_failure(self):
        payload = self._payload(
            self._event(
                self.types["URL_REQUEST_START_JOB"],
                {"url": "http://127.0.0.1:8078/page.html"},
                phase=1,
            ),
            self._event(
                self.types["HTTP_TRANSACTION_SEND_REQUEST_HEADERS"],
                {"headers": ["Accept-Encoding: gzip, br, cbm"]},
            ),
            self._event(
                self.types["HTTP_TRANSACTION_READ_RESPONSE_HEADERS"],
                {
                    "headers": [
                        "HTTP/1.1 200 OK",
                        "Vary: Accept-Encoding",
                        "Content-Encoding: cbm",
                    ]
                },
            ),
        )

        evidence = verify_payload(payload, "page.html")

        self.assertTrue(evidence.verdict)
        self.assertFalse(evidence.request_failed)

    def test_failed_request_is_not_a_pass(self):
        payload = self._payload(
            self._event(
                self.types["URL_REQUEST_START_JOB"],
                {"url": "http://127.0.0.1:8078/page.html"},
                phase=1,
            ),
            self._event(
                self.types["HTTP_TRANSACTION_SEND_REQUEST_HEADERS"],
                {"headers": ["Accept-Encoding: cbm"]},
            ),
            self._event(
                self.types["HTTP_TRANSACTION_READ_RESPONSE_HEADERS"],
                {
                    "headers": [
                        "Content-Encoding: cbm",
                        "Vary: Accept-Encoding",
                    ]
                },
            ),
            self._event(self.types["FAILED"], {"net_error": -330}),
        )

        evidence = verify_payload(payload, "page.html")

        self.assertFalse(evidence.verdict)
        self.assertTrue(evidence.request_failed)


if __name__ == "__main__":
    unittest.main()
