from __future__ import annotations

import importlib.util
import sys
import unittest
from unittest import mock
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "allocator_telemetry_runner.py"
SPEC = importlib.util.spec_from_file_location("allocator_telemetry_runner", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def fixture_bundle(*, samples: int = 13, trials: int = 30, largest: int = 4096, auxiliary_ratio: float = 0.25) -> dict:
    results = []
    for sample_index in range(samples):
        profiles = {}
        for profile in ("static", "dynamic"):
            profiles[profile] = {
                "frame_bytes": 1024 + sample_index,
                "frame_sha256": ("a" if profile == "static" else "b") * 64,
                "mode": "web",
                "trials": [
                    {
                        "trial_no": trial_no,
                        "roundtrip_exact": True,
                        "decoded_sha256": "c" * 64,
                        "allocation_count": 4,
                        "allocated_bytes": 4096,
                        "deallocated_bytes": 4096,
                        "peak_live_bytes": 4096,
                        "largest_single_allocation_bytes": largest,
                        "live_bytes_after": 0,
                        "caller_input_bytes": 1024 + sample_index,
                        "declared_output_bytes": 2048,
                        "decoder_retained_peak_bytes": 4096,
                        "decoder_retained_after_drop_bytes": 0,
                        "output_capacity_bytes": 2048,
                        "auxiliary_peak_bytes": int((1024 + sample_index) * auxiliary_ratio),
                        "auxiliary_ratio_numerator_bytes": int((1024 + sample_index) * auxiliary_ratio),
                        "auxiliary_ratio_denominator_bytes": 1024 + sample_index,
                        "auxiliary_memory_bound_ratio": int((1024 + sample_index) * auxiliary_ratio)
                        / (1024 + sample_index),
                    }
                    for trial_no in range(1, trials + 1)
                ],
            }
        results.append(
            {
                "sample_id": f"sample-{sample_index}",
                "path": f"payload-{sample_index}.bin",
                "input_bytes": 2048,
                "input_sha256": "d" * 64,
                "static_profile": profiles["static"],
                "dynamic_profile": profiles["dynamic"],
            }
        )
    bundle = {
        "schema_version": 1,
        "task_id": "CUBR-0075",
        "phase": "allocator_telemetry",
        "protocol": {
            "samples": 13,
            "profiles": 2,
            "warmups": 3,
            "trials": 30,
            "seed": 75075,
            "chunk_size": 65536,
            "block_size": 65536,
        },
        "provenance": {
            "source_sha": "expected",
            "runner_sha": "e" * 64,
            "probe_sha": "f" * 64,
            "binary_sha": "1" * 64,
            "manifest_sha": "2" * 64,
            "preregistration_sha": "3" * 64,
        },
        "results": results,
    }

    win = largest <= 65536
    go_largest = largest <= 4194304
    go_auxiliary = auxiliary_ratio <= 1
    decision = "WIN" if win and go_auxiliary else "GO" if go_largest and go_auxiliary else "NO_GO"
    bundle["summary"] = {
        "max_largest_single_allocation_bytes": largest,
        "max_auxiliary_memory_bound_ratio": auxiliary_ratio,
        "win_largest_single_allocation_bytes": win,
        "go_largest_single_allocation_bytes": go_largest,
        "go_auxiliary_memory_bound_ratio": go_auxiliary,
        "decision": decision,
    }
    return bundle


class AllocatorTelemetryRunnerTests(unittest.TestCase):
    def test_validate_bundle_requires_13_samples_and_30_trials(self):
        bundle = fixture_bundle()
        self.assertIs(MODULE.validate_bundle(bundle), bundle)

        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(fixture_bundle(samples=12))
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(fixture_bundle(trials=29))

    def test_validate_bundle_rejects_roundtrip_or_provenance_drift(self):
        bundle = fixture_bundle()
        bundle["results"][0]["static_profile"]["trials"][0]["roundtrip_exact"] = False
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle)

        bundle = fixture_bundle()
        bundle["provenance"]["source_sha"] = "drift"
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle, expected_source_sha="expected")

    def test_validate_bundle_rejects_counter_and_ratio_invariants(self):
        bundle = fixture_bundle()
        trial = bundle["results"][0]["dynamic_profile"]["trials"][0]
        trial["allocated_bytes"] = 10
        trial["deallocated_bytes"] = 20
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle)

        bundle = fixture_bundle()
        trial = bundle["results"][0]["dynamic_profile"]["trials"][0]
        trial["auxiliary_ratio_denominator_bytes"] = 0
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle)

    def test_criterion_result_is_derived_from_raw_rows(self):
        bundle = fixture_bundle(largest=100000, auxiliary_ratio=0.25)
        result = MODULE.summarize(bundle)
        self.assertEqual(result["decision"], "GO")
        self.assertTrue(result["go_auxiliary_memory_bound_ratio"])

        bundle = fixture_bundle(largest=4194305, auxiliary_ratio=0.25)
        self.assertEqual(MODULE.summarize(bundle)["decision"], "NO_GO")

    def test_win_requires_the_stricter_allocation_bar(self):
        bundle = fixture_bundle(largest=65536, auxiliary_ratio=0.25)
        result = MODULE.summarize(bundle)
        self.assertEqual(result["decision"], "WIN")
        self.assertTrue(result["win_largest_single_allocation_bytes"])

    def test_taskset_command_is_singleton_and_reenters_the_runner(self):
        with mock.patch.object(MODULE.shutil, "which", return_value="/usr/bin/taskset"):
            command = MODULE.taskset_argv(7, ["--manifest", "manifest.json"])
        self.assertEqual(command[:4], ["/usr/bin/taskset", "--cpu-list", "7", sys.executable])
        self.assertEqual(command[-3:], [str(MODULE.Path(__file__).parents[1] / "allocator_telemetry_runner.py"), "--manifest", "manifest.json"])

    def test_validate_bundle_rejects_summary_drift_and_unknown_mode(self):
        bundle = fixture_bundle()
        bundle["summary"]["decision"] = "GO"
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle)

        bundle = fixture_bundle()
        bundle["results"][0]["dynamic_profile"]["mode"] = "unknown"
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
