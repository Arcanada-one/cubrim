import json
import math
import sys
import unittest
from pathlib import Path


BENCH_DIR = Path(__file__).resolve().parents[1]
VECTORS = Path(__file__).resolve().parent / "fixtures" / "canonical-fingerprint-vectors.json"
sys.path.insert(0, str(BENCH_DIR))

import model


class CanonicalFingerprintTests(unittest.TestCase):
    def test_python_matches_language_neutral_cross_runtime_vectors(self):
        fixture = json.loads(VECTORS.read_text(encoding="utf-8"))
        self.assertEqual(fixture["contract"], "cubrim-canonical-json-v1")
        for vector in fixture["vectors"]:
            with self.subTest(vector=vector["name"]):
                self.assertEqual(
                    model.stable_fingerprint(vector["input"]),
                    vector["sha256"],
                )
                self.assertTrue(hasattr(model, "canonical_json_bytes"))
                self.assertEqual(
                    model.canonical_json_bytes(vector["input"]).decode("utf-8"),
                    vector["canonical_json"],
                )

    def test_canonicalizer_rejects_ambiguous_or_nonportable_values(self):
        hostile_values = (
            math.nan,
            math.inf,
            2**53,
            {"$float64": "forged"},
            {1: "non-string-key"},
        )
        for value in hostile_values:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    model.stable_fingerprint(value)


if __name__ == "__main__":
    unittest.main()
