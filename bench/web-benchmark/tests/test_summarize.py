import json
import math
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


BENCH_DIR = Path(__file__).resolve().parents[1]
CANONICAL_MANIFEST = BENCH_DIR.parent / "web-corpus" / "manifest.v1.json"
CANONICAL_MANIFEST_SHA256 = (
    "9a0fcb56b9af5c98cd987d1ad289f5adde4b073480646fb472d784b0bbf58599"
)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "valid-trials.json"
sys.path.insert(0, str(BENCH_DIR))

import summarize
from summarize import summarize_bundle, verify_bundle
from model import stable_fingerprint


def canonical_bundle():
    environment = {
        "code_sha": "a" * 40,
        "cpu": "fixture-cpu",
        "os": "fixture-os",
        "affinity": [0],
        "admission": {
            "load_1m": 0.1,
            "load_per_cpu": 0.1,
            "max_load_per_cpu": 1.0,
            "temperature_c": 40.0,
            "max_temperature_c": 90,
            "accepted": True,
        },
    }
    sample = {
        "sample_id": "sample-a",
        "path": "payloads/sample-a.bin",
        "sha256": "c" * 64,
        "byte_count": 100,
        "media_type": "application/octet-stream",
        "size_class": "small",
        "media_family": "binary",
        "source_ref": "project-authored:fixture",
        "license_id": "MIT",
        "redistributable": True,
    }
    flags = {
        "gzip": ["-9", "-c"],
        "brotli": ["--quality=11", "--stdout"],
        "zstd": ["-19", "--quiet", "--stdout"],
    }
    tools = []
    for codec in ("gzip", "brotli", "zstd"):
        provenance = {
            "name": codec,
            "version": f"{codec} fixture",
            "binary_sha256": stable_fingerprint({"binary": codec}),
            "flags": flags[codec],
            "binary_package": codec,
            "binary_package_version": "1.0-1",
            "source_package": codec,
            "source_package_version": "1.0-1",
            "upstream_release_sha": "b" * 40,
            "upstream_source_reference": f"https://example.com/{codec}/commit/" + "b" * 40,
        }
        tools.append(
            {
                **provenance,
                "binary_path": f"/usr/bin/{codec}",
                "capabilities": {
                    "whole_buffer_decode": True,
                    "incremental_decode": False,
                },
                "codec_build_provenance_sha256": stable_fingerprint(provenance),
            }
        )
    trials = []
    order = 0
    for trial_no in range(1, 31):
        for tool in tools:
            order += 1
            compressed_bytes = 10 + trial_no
            trials.append(
                {
                    "sample_id": sample["sample_id"],
                    "codec_key": tool["name"],
                    "trial_no": trial_no,
                    "randomized_order": order,
                    "measured_at": "2026-01-01T00:00:30Z",
                    "runner_code_sha": environment["code_sha"],
                    "codec_build_provenance_sha256": tool[
                        "codec_build_provenance_sha256"
                    ],
                    "environment_fingerprint": stable_fingerprint(environment),
                    "tool_fingerprint": stable_fingerprint(tool),
                    "tool_version": tool["version"],
                    "tool_binary_sha256": tool["binary_sha256"],
                    "tool_flags": tool["flags"],
                    "original_sha256": sample["sha256"],
                    "compressed_sha256": f"{order:064x}",
                    "decoded_sha256": sample["sha256"],
                    "original_bytes": sample["byte_count"],
                    "compressed_bytes": compressed_bytes,
                    "decoded_bytes": sample["byte_count"],
                    "roundtrip_exact": True,
                    "metrics": {
                        "compressed_bytes": compressed_bytes,
                        "compression_ratio": compressed_bytes / sample["byte_count"],
                        "compression_duration": trial_no,
                        "decompression_duration": trial_no / 2,
                        "peak_memory": 4096,
                    },
                }
            )
    bundle = {
        "schema_version": 1,
        "scope": "resource_codec",
        "phase": "A",
        "run_timing": {
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:01:00Z",
        },
        "corpus": {
            "manifest_name": "manifest.v1.json",
            "manifest_sha256": "e" * 64,
            "manifest_schema_version": 1,
            "sample_count": 1,
            "samples": [sample],
        },
        "toolchain": tools,
        "protocol": {
            "codecs": ["gzip", "brotli", "zstd"],
            "warmups": 3,
            "trials_per_cell": 30,
            "randomized_order_seed": 74074,
            "bootstrap_iterations": 100,
            "bootstrap_confidence": 0.95,
            "timeout_seconds": 60,
            "max_input_bytes": 2 * 1024 * 1024,
            "max_output_bytes": 64 * 1024 * 1024,
            "max_expansion_ratio": 64,
            "network_isolation": "systemd_user_unit_plus_seccomp_network_deny",
            "wall_clock": "time.monotonic_ns",
            "peak_rss": "gnu_time_verbose",
        },
        "environment": environment,
        "applicability": {
            "time_to_first_decoded_byte": {
                "available": False,
                "reason": "phase_a_codecs_do_not_offer_incremental_decode",
            },
            "energy": {
                "available": False,
                "reason": "readable_calibrated_rapl_unavailable",
            },
        },
        "resource_results": trials,
        "resource_summaries": [],
        "page_results": {
            "explicit_wasm_application": [],
            "transparent_http_page": [],
        },
    }
    return summarize.finalize_bundle(bundle, bootstrap_iterations=100)


def canonical_production_bundle(trials_per_cell=30):
    bundle = canonical_bundle()
    manifest = json.loads(CANONICAL_MANIFEST.read_text(encoding="utf-8"))
    templates = {
        (trial["codec_key"], trial["trial_no"]): trial
        for trial in bundle["resource_results"]
    }
    trials = []
    order = 0
    for sample in manifest["samples"]:
        for trial_no in range(1, trials_per_cell + 1):
            for codec in ("gzip", "brotli", "zstd"):
                order += 1
                template_trial_no = ((trial_no - 1) % 30) + 1
                trial = deepcopy(templates[(codec, template_trial_no)])
                trial.update(
                    {
                        "sample_id": sample["sample_id"],
                        "trial_no": trial_no,
                        "randomized_order": order,
                        "original_sha256": sample["sha256"],
                        "compressed_sha256": f"{order:064x}",
                        "decoded_sha256": sample["sha256"],
                        "original_bytes": sample["byte_count"],
                        "decoded_bytes": sample["byte_count"],
                    }
                )
                trial["metrics"]["compression_ratio"] = (
                    trial["compressed_bytes"] / sample["byte_count"]
                )
                trials.append(trial)
    bundle["corpus"] = {
        "manifest_name": CANONICAL_MANIFEST.name,
        "manifest_sha256": CANONICAL_MANIFEST_SHA256,
        "manifest_schema_version": manifest["schema_version"],
        "sample_count": len(manifest["samples"]),
        "samples": manifest["samples"],
    }
    bundle["resource_results"] = trials
    bundle["resource_summaries"] = []
    bundle["protocol"]["trials_per_cell"] = trials_per_cell
    return bundle


class SummarizeTests(unittest.TestCase):
    def setUp(self):
        self.bundle = canonical_bundle()

    def test_seeded_summary_uses_all_trials_without_best_run_selection(self):
        first = summarize_bundle(self.bundle, seed=74074, bootstrap_iterations=500)
        second = summarize_bundle(self.bundle, seed=74074, bootstrap_iterations=500)
        self.assertEqual(first, second)
        compressed = next(
            row for row in first["summaries"] if row["metric_name"] == "compressed_bytes"
        )
        self.assertEqual(compressed["sample_count"], 30)
        self.assertEqual(compressed["median"], 25.5)
        self.assertEqual(compressed["p95"], 39)
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

    def test_verify_rejects_partial_metrics(self):
        partial = deepcopy(self.bundle)
        for trial in partial["resource_results"]:
            trial["metrics"]["compression_ratio"] = (
                trial["compressed_bytes"] / trial["original_bytes"]
            )
        del partial["resource_results"][0]["metrics"]["compression_ratio"]
        with self.assertRaisesRegex(ValueError, "exactly"):
            verify_bundle(partial)

    def test_verify_rejects_secret_environment_fields(self):
        secret = deepcopy(self.bundle)
        secret["environment"]["AWS_SECRET_ACCESS_KEY"] = "secret"
        with self.assertRaisesRegex(ValueError, "environment fields"):
            verify_bundle(secret)

    def test_verify_rejects_invalid_ordered_or_future_run_timestamps(self):
        invalid_order = deepcopy(self.bundle)
        invalid_order["run_timing"] = {
            "started_at": "2026-01-01T00:01:00Z",
            "completed_at": "2026-01-01T00:00:00Z",
        }
        with self.assertRaisesRegex(ValueError, "precedes"):
            verify_bundle(invalid_order)

        invalid_trial = deepcopy(self.bundle)
        invalid_trial["resource_results"][0]["measured_at"] = "2025-12-31T23:59:59Z"
        with self.assertRaisesRegex(ValueError, "outside run timing"):
            verify_bundle(invalid_trial)

        future = deepcopy(self.bundle)
        future["run_timing"] = {
            "started_at": "2999-01-01T00:00:00Z",
            "completed_at": "2999-01-01T00:01:00Z",
        }
        with self.assertRaisesRegex(ValueError, "future"):
            verify_bundle(future)

    def test_verify_requires_thirty_distinct_trials_per_sample_codec(self):
        incomplete = deepcopy(self.bundle)
        incomplete["resource_results"] = incomplete["resource_results"][:-1]
        with self.assertRaisesRegex(ValueError, "complete configured"):
            verify_bundle(incomplete)

    def test_production_verifier_pins_canonical_manifest_and_sample_identity(self):
        production = canonical_production_bundle()
        summarize.verify_bundle(
            production,
            require_summaries=False,
            require_canonical_corpus=True,
        )
        self.assertEqual(len(production["resource_results"]), 8 * 3 * 30)

        mutations = (
            ("digest", lambda value: value["corpus"].__setitem__("manifest_sha256", "f" * 64)),
            ("count", lambda value: value["corpus"].__setitem__("sample_count", 7)),
            (
                "sample ID",
                lambda value: value["corpus"]["samples"][0].__setitem__(
                    "sample_id", "substitute"
                ),
            ),
            (
                "sample path",
                lambda value: value["corpus"]["samples"][0].__setitem__(
                    "path", "payloads/substitute.bin"
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                invalid = deepcopy(production)
                mutate(invalid)
                with self.assertRaisesRegex(ValueError, "canonical|sample count"):
                    summarize.verify_bundle(
                        invalid,
                        require_summaries=False,
                        require_canonical_corpus=True,
                    )

    def test_fixture_verification_remains_synthetic_and_flexible(self):
        verify_bundle(self.bundle, require_summaries=True)
        self.assertEqual(self.bundle["corpus"]["sample_count"], 1)

    def test_production_verifier_accepts_more_than_thirty_trials_per_cell(self):
        production = canonical_production_bundle(trials_per_cell=31)
        summarize.verify_bundle(
            production,
            require_summaries=False,
            require_canonical_corpus=True,
        )
        self.assertEqual(len(production["resource_results"]), 8 * 3 * 31)

    def test_verify_rejects_stale_or_selective_summary(self):
        self.assertTrue(hasattr(summarize, "finalize_bundle"))
        finalized = summarize.finalize_bundle(
            self.bundle,
            seed=74074,
            bootstrap_iterations=500,
        )
        invalid = deepcopy(finalized)
        invalid["resource_summaries"][0]["sample_count"] = 29
        with self.assertRaisesRegex(ValueError, "summary"):
            verify_bundle(invalid, require_summaries=True)
        self.assertEqual(
            {row["metric_name"] for row in finalized["resource_summaries"]},
            set(summarize.PHASE_A_METRICS),
        )

    def test_bundle_cli_atomically_updates_the_same_bundle_without_losing_trials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "phase-a.json"
            raw = canonical_production_bundle()
            raw["resource_summaries"] = []
            path.write_text(json.dumps(raw), encoding="utf-8")
            original_trials = deepcopy(raw["resource_results"])
            completed = subprocess.run(
                (
                    sys.executable,
                    str(BENCH_DIR / "summarize.py"),
                    "--verify",
                    "--bundle",
                    str(path),
                    "--bootstrap-iterations",
                    "100",
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                cwd=directory,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            finalized = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(finalized["resource_results"], original_trials)
            verify_bundle(
                finalized,
                require_summaries=True,
                require_canonical_corpus=True,
            )
            self.assertEqual(len(finalized["resource_results"]), 8 * 3 * 30)
            self.assertFalse(list(path.parent.glob(".phase-a.json.*.tmp")))

    def test_bundle_cli_rejects_synthetic_corpus_without_overwriting_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "phase-a.json"
            synthetic = deepcopy(self.bundle)
            synthetic["resource_summaries"] = []
            original = json.dumps(synthetic, sort_keys=True)
            path.write_text(original, encoding="utf-8")
            completed = subprocess.run(
                (
                    sys.executable,
                    str(BENCH_DIR / "summarize.py"),
                    "--verify",
                    "--bundle",
                    str(path),
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                cwd=directory,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("canonical", completed.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_bundle_cli_rejects_partial_trial_without_overwriting_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "phase-a.json"
            invalid = canonical_production_bundle()
            invalid["resource_summaries"] = []
            del invalid["resource_results"][0]["metrics"]["compression_ratio"]
            original = json.dumps(invalid, sort_keys=True)
            path.write_text(original, encoding="utf-8")
            completed = subprocess.run(
                (
                    sys.executable,
                    str(BENCH_DIR / "summarize.py"),
                    "--verify",
                    "--bundle",
                    str(path),
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                cwd=directory,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
