from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "allocator_telemetry_runner.py"
SPEC = importlib.util.spec_from_file_location("allocator_telemetry_runner", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def canonical_manifest() -> dict:
    return MODULE.load_canonical_manifest()


def fixture_bundle(*, samples: int = 13, trials: int = 30, largest: int = 4096, auxiliary_ratio: float = 0.25) -> dict:
    manifest = canonical_manifest()["samples"][:samples]
    results = []
    for sample_index, manifest_sample in enumerate(manifest):
        profiles = {}
        input_bytes = manifest_sample["byte_count"]
        for profile in ("static", "dynamic"):
            frame_bytes = 1024 + sample_index
            auxiliary_peak = int(frame_bytes * auxiliary_ratio)
            profiles[profile] = {
                "frame_bytes": frame_bytes,
                "frame_sha256": ("a" if profile == "static" else "b") * 64,
                "mode": "web",
                "trials": [
                    {
                        "trial_no": trial_no,
                        "roundtrip_exact": True,
                        "decoded_sha256": manifest_sample["sha256"],
                        "allocation_count": 4,
                        "allocated_bytes": 4096,
                        "deallocated_bytes": 4096,
                        "peak_live_bytes": 4096,
                        "largest_single_allocation_bytes": largest,
                        "caller_input_bytes": frame_bytes,
                        "declared_output_bytes": input_bytes,
                        "decoder_retained_peak_bytes": frame_bytes + input_bytes + auxiliary_peak,
                        "allocator_live_bytes_after": 0,
                        "auxiliary_peak_bytes": auxiliary_peak,
                        "auxiliary_ratio_numerator_bytes": auxiliary_peak,
                        "auxiliary_ratio_denominator_bytes": frame_bytes,
                        "auxiliary_memory_bound_ratio": auxiliary_peak / frame_bytes,
                    }
                    for trial_no in range(1, trials + 1)
                ],
            }
        results.append(
            {
                "sample_id": manifest_sample["sample_id"],
                "path": manifest_sample["path"],
                "input_bytes": input_bytes,
                "input_sha256": manifest_sample["sha256"],
                "static_profile": profiles["static"],
                "dynamic_profile": profiles["dynamic"],
            }
        )
    bundle = {
        "schema_version": 2,
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
            "source_sha": "a" * 64,
            "runner_sha": "e" * 64,
            "probe_source_sha": "f" * 64,
            "probe_sha": "1" * 64,
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
    def validate(self, bundle: dict, *, source: str | None = None) -> dict:
        return MODULE.validate_bundle(
            bundle,
            expected_source_sha=source,
            expected_manifest=canonical_manifest(),
        )

    def test_validate_bundle_requires_13_samples_and_30_trials(self):
        bundle = fixture_bundle()
        self.assertIs(self.validate(bundle), bundle)

        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(fixture_bundle(samples=12))
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(fixture_bundle(trials=29))

    def test_validate_bundle_rejects_roundtrip_or_provenance_drift(self):
        bundle = fixture_bundle()
        bundle["results"][0]["static_profile"]["trials"][0]["roundtrip_exact"] = False
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(bundle)

        bundle = fixture_bundle()
        bundle["provenance"]["source_sha"] = "a" * 63 + "b"
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(bundle, source="a" * 64)

    def test_validate_bundle_rejects_manifest_and_decoded_identity_drift(self):
        bundle = fixture_bundle()
        bundle["results"][0]["sample_id"] = "not-canonical"
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(bundle)

        bundle = fixture_bundle()
        bundle["results"][0]["static_profile"]["trials"][0]["decoded_sha256"] = "a" * 64
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(bundle)

    def test_validate_bundle_rejects_counter_and_ratio_invariants(self):
        bundle = fixture_bundle()
        trial = bundle["results"][0]["dynamic_profile"]["trials"][0]
        trial["allocated_bytes"] = 10
        trial["deallocated_bytes"] = 20
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(bundle)

        bundle = fixture_bundle()
        trial = bundle["results"][0]["dynamic_profile"]["trials"][0]
        trial["auxiliary_ratio_denominator_bytes"] = 0
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(bundle)

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
            self.validate(bundle)

        bundle = fixture_bundle()
        bundle["results"][0]["dynamic_profile"]["mode"] = "unknown"
        with self.assertRaises(MODULE.MeasurementVoid):
            self.validate(bundle)

    def test_run_rejects_noncanonical_manifest_path(self):
        with tempfile.TemporaryDirectory() as directory:
            copied_manifest = Path(directory) / "manifest.v3.json"
            copied_manifest.write_bytes(MODULE.CANONICAL_MANIFEST.read_bytes())
            args = MODULE.argparse.Namespace(
                manifest=copied_manifest,
                probe=Path(directory) / "missing-probe",
                out=Path(directory) / "bundle.json",
                journal=Path(directory) / "journal.jsonl",
            )
            with self.assertRaises(MODULE.MeasurementVoid):
                MODULE.run(args)

    def test_run_executes_probe_and_writes_only_validated_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            probe = root / "fake-probe"
            output = root / "bundle.json"
            journal = root / "journal.jsonl"
            values = {
                "source_sha": "a" * 64,
                "runner_sha": "f" * 64,
                "probe_source_sha": "b" * 64,
                "probe_sha": "c" * 64,
                "binary_sha": "c" * 64,
                "manifest_sha": "d" * 64,
                "preregistration_sha": "e" * 64,
            }
            bundle = fixture_bundle()
            bundle["provenance"].update(values)
            probe.write_text(
                "#!/bin/sh\nprintf '%s\\n' '" + json.dumps(bundle) + "'\n",
                encoding="utf-8",
            )
            probe.chmod(probe.stat().st_mode | 0o111)

            def fake_hash(path: Path) -> str:
                path = path.resolve()
                if path == probe.resolve():
                    return values["probe_sha"]
                if path == MODULE.PROBE_SOURCE.resolve():
                    return values["probe_source_sha"]
                if path == MODULE.CANONICAL_MANIFEST.resolve():
                    return values["manifest_sha"]
                if path == MODULE.PREREGISTRATION.resolve():
                    return values["preregistration_sha"]
                if path == MODULE_PATH.resolve():
                    return values["runner_sha"]
                raise AssertionError(f"unexpected hash path: {path}")

            args = MODULE.argparse.Namespace(
                manifest=MODULE.CANONICAL_MANIFEST,
                probe=probe,
                out=output,
                journal=journal,
            )
            with (
                mock.patch.object(MODULE, "require_clean_tree"),
                mock.patch.object(MODULE, "admission", return_value={"effective_affinity": [0], "hostname": "test", "load_per_cpu": 0.0, "max_temperature_c": 10.0}),
                mock.patch.object(MODULE, "git_sha", return_value=values["source_sha"]),
                mock.patch.object(MODULE, "sha256_file", side_effect=fake_hash),
            ):
                self.assertEqual(MODULE.run(args), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), bundle)
            self.assertIn('"event":"validated"', journal.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
