import json
import math
import sys
import unittest
from copy import deepcopy
from pathlib import Path


BENCH_DIR = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "valid-trials.json"
sys.path.insert(0, str(BENCH_DIR))

from summarize import summarize_bundle, verify_bundle


class SummarizeTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_seeded_summary_uses_all_trials_without_best_run_selection(self):
        first = summarize_bundle(self.bundle, seed=74074, bootstrap_iterations=500)
        second = summarize_bundle(self.bundle, seed=74074, bootstrap_iterations=500)
        self.assertEqual(first, second)
        compressed = next(
            row for row in first["summaries"] if row["metric_name"] == "compressed_bytes"
        )
        self.assertEqual(compressed["sample_count"], 5)
        self.assertEqual(compressed["median"], 30)
        self.assertEqual(compressed["p95"], 50)
        self.assertEqual(compressed["unit"], "bytes")
        self.assertNotEqual(compressed["median"], 10)
        self.assertLessEqual(compressed["bootstrap_95"]["low"], compressed["median"])
        self.assertGreaterEqual(compressed["bootstrap_95"]["high"], compressed["median"])

    def test_verify_rejects_duplicate_trials(self):
        invalid = deepcopy(self.bundle)
        invalid["resource_results"].append(deepcopy(invalid["resource_results"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate trial"):
            verify_bundle(invalid)

    def test_verify_rejects_nonfinite_metrics_and_inexact_roundtrip(self):
        invalid_metric = deepcopy(self.bundle)
        invalid_metric["resource_results"][0]["metrics"]["compression_duration"] = math.inf
        with self.assertRaisesRegex(ValueError, "finite"):
            verify_bundle(invalid_metric)

        invalid_roundtrip = deepcopy(self.bundle)
        invalid_roundtrip["resource_results"][0]["decoded_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "round trip"):
            verify_bundle(invalid_roundtrip)

    def test_verify_requires_code_sha_on_environment_and_each_trial(self):
        missing_environment = deepcopy(self.bundle)
        del missing_environment["environment"]["code_sha"]
        with self.assertRaisesRegex(ValueError, "environment code_sha"):
            verify_bundle(missing_environment)

        missing_trial = deepcopy(self.bundle)
        del missing_trial["resource_results"][0]["runner_code_sha"]
        with self.assertRaisesRegex(ValueError, "trial code SHA"):
            verify_bundle(missing_trial)

    def test_verify_rejects_void_records_inside_a_bundle(self):
        invalid = deepcopy(self.bundle)
        invalid["voids"] = [{"reason": "timeout"}]
        with self.assertRaisesRegex(ValueError, "void"):
            verify_bundle(invalid)


if __name__ == "__main__":
    unittest.main()
