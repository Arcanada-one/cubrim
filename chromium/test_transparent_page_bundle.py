import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from chromium.transparent_page_bundle import build_bundle


class TransparentPageBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.origin = self.root / "page.html"
        self.origin.write_bytes(b"page fixture")
        self.metadata = {
            "schema_version": 1,
            "source_sha": "a" * 40,
            "browser_sha256": "b" * 64,
            "browser_version": "Chromium 151.0.7922.108",
            "chromium_source_sha": "c" * 40,
            "document": "page.html",
        }
        (self.root / "metadata.json").write_text(json.dumps(self.metadata))
        (self.root / "schedule.tsv").write_text(
            "".join(
                f"{kind}\t{arm}\t{number:02d}\n"
                for kind in ("warmup", "trial")
                for arm in ("cbm", "identity")
                for number in range(1, (1 if kind == "warmup" else 2) + 1)
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _netlog(encoding):
        types = {
            "FAILED": 1,
            "HTTP_TRANSACTION_READ_RESPONSE_HEADERS": 243,
            "HTTP_TRANSACTION_SEND_REQUEST_HEADERS": 238,
            "URL_REQUEST_START_JOB": 134,
        }
        headers = ["HTTP/1.1 200 OK", "Vary: Accept-Encoding"]
        request = "Accept-Encoding: gzip, br"
        if encoding == "cbm":
            request = "Accept-Encoding: gzip, br, cbm"
            headers.append("Content-Encoding: cbm")
        return {
            "constants": {"logEventTypes": types},
            "events": [
                {
                    "type": types["URL_REQUEST_START_JOB"],
                    "phase": 1,
                    "source": {"id": 7},
                    "params": {"url": "http://127.0.0.1:8078/page.html"},
                },
                {
                    "type": types["HTTP_TRANSACTION_SEND_REQUEST_HEADERS"],
                    "source": {"id": 7},
                    "params": {"headers": [request]},
                },
                {
                    "type": types["HTTP_TRANSACTION_READ_RESPONSE_HEADERS"],
                    "source": {"id": 7},
                    "params": {"headers": headers},
                },
            ],
        }

    def _write_arm(self, arm, count):
        arm_root = self.root / arm
        for kind, total in (("warmups", 1), ("trials", count)):
            for number in range(1, total + 1):
                name = f"{kind[:-1]}-{number:02d}"
                row = {
                    "schema_version": 1,
                    "body": {
                        "status": 200,
                        "byte_length": len(self.origin.read_bytes()),
                        "sha256": hashlib.sha256(self.origin.read_bytes()).hexdigest(),
                        "origin_byte_length": len(self.origin.read_bytes()),
                        "origin_sha256": hashlib.sha256(self.origin.read_bytes()).hexdigest(),
                        "roundtrip_exact": True,
                    },
                    "screenshot": {"byte_length": 3, "sha256": hashlib.sha256(b"png").hexdigest()},
                    "metrics": {
                        "time_to_first_byte": 10 + number,
                        "first_contentful_paint": 20 + number,
                        "largest_contentful_paint": 30 + number,
                        "total_blocking_time": number,
                        "page_load_duration": 40 + number,
                    },
                }
                row_path = arm_root / kind / f"{name}.json"
                netlog_path = arm_root / "netlogs" / f"{name}.json"
                screenshot_path = arm_root / "screenshots" / f"{name}.png"
                row_path.parent.mkdir(parents=True, exist_ok=True)
                netlog_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                row_path.write_text(json.dumps(row))
                netlog_path.write_text(json.dumps(self._netlog(arm)))
                screenshot_path.write_bytes(b"png")

    def test_build_bundle_requires_both_transports_and_exact_trials(self):
        self._write_arm("cbm", 2)
        self._write_arm("identity", 2)

        bundle = build_bundle(self.root, self.origin, trials=2, warmups=1)

        self.assertEqual(bundle["scenario"], "transparent_http_page")
        self.assertEqual(len(bundle["page_results"]), 4)
        self.assertEqual(
            {row["delivery"] for row in bundle["page_results"]}, {"cbm", "identity"}
        )
        self.assertEqual(len(bundle["page_summaries"]), 10)

    def test_build_bundle_rejects_a_missing_trial(self):
        self._write_arm("cbm", 2)
        self._write_arm("identity", 2)
        (self.root / "cbm" / "trials" / "trial-02.json").unlink()

        with self.assertRaisesRegex(ValueError, "exactly 2 trial rows"):
            build_bundle(self.root, self.origin, trials=2, warmups=1)


if __name__ == "__main__":
    unittest.main()
