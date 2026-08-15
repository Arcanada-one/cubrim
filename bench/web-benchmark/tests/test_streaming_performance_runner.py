from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "streaming_performance_runner.py"
SPEC = importlib.util.spec_from_file_location("streaming_performance_runner", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def fixture_bundle() -> tuple[dict, dict]:
    manifest_samples = [
        {"sample_id": f"sample-{index}", "path": f"payload-{index}", "byte_count": 10 + index, "sha256": f"{index + 1:064x}"}
        for index in range(13)
    ]
    samples = []
    trials = []
    for index, manifest_sample in enumerate(manifest_samples):
        frame_bytes = 100 + index
        sample = {**manifest_sample, "frame_bytes": frame_bytes, "frame_sha256": f"{index + 20:064x}"}
        samples.append(sample)
        for mode in ("streaming", "whole_buffer"):
            for run_index in range(MODULE.WARMUPS + MODULE.TRIALS):
                warmup = run_index < MODULE.WARMUPS
                trial_index = run_index + 1 if warmup else run_index - MODULE.WARMUPS + 1
                first_input = 10 if mode == "streaming" else frame_bytes
                auxiliary = 20 if mode == "streaming" else 0
                trials.append(
                    {
                        "sample_id": sample["sample_id"],
                        "mode": mode,
                        "trial_index": trial_index,
                        "warmup": warmup,
                        "input_bytes": sample["byte_count"],
                        "frame_bytes": frame_bytes,
                        "first_output_input_bytes": first_input,
                        "first_output_before_eof": mode == "streaming",
                        "first_output_latency_ns": 1,
                        "last_input_latency_ns": 2,
                        "output_complete_latency_ns": 3,
                        "declared_output_bytes": sample["byte_count"],
                        "decoder_retained_peak_bytes": frame_bytes + sample["byte_count"] + auxiliary,
                        "auxiliary_peak_bytes": auxiliary,
                        "auxiliary_memory_bound_ratio": auxiliary / frame_bytes,
                        "finish_ok": True,
                        "roundtrip_exact": True,
                        "sink_exact": True,
                        "status": "valid",
                    }
                )
    bundle = {
        "schema_version": 1,
        "task_id": "CUBR-0075",
        "phase": "streaming_performance",
        "status": "COMPLETE",
        "protocol": {
            "samples": 13,
            "modes": 2,
            "warmups": 3,
            "trials": 30,
            "seed": 75075,
            "block_size": 65536,
            "input_chunk_size": 4096,
        },
        "samples": samples,
        "independent_block_probe": {
            "success": False,
            "positive_control": True,
            "negative_control": True,
            "evidence": "ordered positive control and predecessor-free negative control",
        },
        "provenance": {key: "value" for key in ("source_commit", "probe_source_sha256", "probe_binary_sha256", "runner_sha256", "prereg_sha256", "manifest_sha256", "host", "arch", "cpu_affinity", "rustc")},
        "trials": trials,
    }
    return bundle, {"samples": manifest_samples}


class StreamingPerformanceRunnerTests(unittest.TestCase):
    def test_valid_complete_matrix_is_no_go_only_for_explicit_capability(self):
        bundle, manifest = fixture_bundle()
        measurement = MODULE.validate_bundle(bundle, manifest)
        self.assertEqual(measurement["streaming_measured_trials"], 390)
        self.assertEqual(measurement["max_first_output_after_input_bytes"], 10)
        self.assertFalse(measurement["independent_block_decode_success"])
        self.assertEqual(measurement["decision"], "NO_GO")

    def test_missing_cell_is_void(self):
        bundle, manifest = fixture_bundle()
        bundle["trials"].pop()
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle, manifest)

    def test_raw_memory_mutation_is_void(self):
        bundle, manifest = fixture_bundle()
        trial = next(row for row in bundle["trials"] if row["mode"] == "streaming" and not row["warmup"])
        trial["auxiliary_memory_bound_ratio"] = 0.0
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle, manifest)

    def test_supplied_summary_cannot_override_raw_trials(self):
        bundle, manifest = fixture_bundle()
        bundle["measurement"] = {"decision": "GO"}
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle, manifest)

    def test_integrity_failure_is_void(self):
        bundle, manifest = fixture_bundle()
        bundle["trials"][0]["roundtrip_exact"] = False
        with self.assertRaises(MODULE.MeasurementVoid):
            MODULE.validate_bundle(bundle, manifest)


if __name__ == "__main__":
    unittest.main()
