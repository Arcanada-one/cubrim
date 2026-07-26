import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

from adapters import ProcessMeasurement, ToolIdentity
from model import PHASE_A_WARMUPS, BenchmarkSample, RunnerConfig
from run import PhaseARunner, RedactedJournal, _git_code_sha


class FakeAdapter:
    name = "gzip"
    flags = ("-9",)
    capabilities = {"whole_buffer_decode": True}

    def identity(self):
        return ToolIdentity(
            name="gzip",
            version="gzip test",
            binary_path="/usr/bin/gzip",
            binary_sha256="b" * 64,
            codec_code_sha="c" * 40,
            flags=self.flags,
        )


class FakeExecutor:
    def __init__(self, payload: bytes, fail: bool = False):
        self.payload = payload
        self.fail = fail

    def compress(self, adapter, source, target):
        if self.fail:
            raise TimeoutError("timed out while reading /secret/input")
        target.write_bytes(b"compressed")
        return ProcessMeasurement(1_250_000, 4096, hashlib.sha256(b"compressed").hexdigest())

    def decompress(self, adapter, source, target):
        target.write_bytes(self.payload)
        return ProcessMeasurement(
            750_000,
            8192,
            hashlib.sha256(self.payload).hexdigest(),
        )


class VersionMismatchAdapter(FakeAdapter):
    def identity(self):
        raise ValueError("codec version mismatch")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.payload = b"lossless payload"
        self.sample_hash = hashlib.sha256(self.payload).hexdigest()
        self.sample = BenchmarkSample(
            sample_id="sample-a",
            path="payloads/sample-a.bin",
            sha256=self.sample_hash,
            byte_count=len(self.payload),
            media_type="application/octet-stream",
            size_class="small",
        )

    def test_config_requires_fixed_warmups_and_at_least_thirty_trials(self):
        with self.assertRaisesRegex(ValueError, "at least 30"):
            RunnerConfig(trials=29, warmups=PHASE_A_WARMUPS)
        with self.assertRaisesRegex(ValueError, "fixed"):
            RunnerConfig(trials=30, warmups=PHASE_A_WARMUPS + 1)

    def test_measured_runs_reject_a_dirty_runner_tree(self):
        responses = [
            SimpleNamespace(stdout="a" * 40 + "\n"),
            SimpleNamespace(stdout=" M bench/web-benchmark/run.py\n"),
        ]
        with patch("run.subprocess.run", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "clean committed"):
                _git_code_sha(require_clean=True)

    def test_accepted_trial_has_exact_roundtrip_hashes_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "payloads" / "sample-a.bin"
            source.parent.mkdir()
            source.write_bytes(self.payload)
            journal = RedactedJournal(root / "journal" / "voids.jsonl")
            runner = PhaseARunner(
                corpus_root=root,
                output_root=root / "out",
                journal=journal,
                runner_code_sha="a" * 40,
                environment={"host": "Arcana-DEVS", "cpu": "test", "os": "test"},
                config=RunnerConfig(),
                executor=FakeExecutor(self.payload),
            )

            trial = runner.run_trial(self.sample, FakeAdapter(), trial_no=1, randomized_order=7)

            self.assertEqual(trial.original_sha256, self.sample_hash)
            self.assertEqual(trial.decoded_sha256, self.sample_hash)
            self.assertEqual(trial.original_bytes, trial.decoded_bytes)
            self.assertTrue(trial.roundtrip_exact)
            self.assertEqual(trial.runner_code_sha, "a" * 40)
            self.assertEqual(trial.codec_code_sha, "c" * 40)
            self.assertEqual(trial.randomized_order, 7)
            self.assertEqual(trial.trial_no, 1)
            self.assertEqual(trial.metrics["compression_duration"], 1.25)
            self.assertEqual(trial.metrics["decompression_duration"], 0.75)
            self.assertEqual(trial.metrics["peak_memory"], 8192)
            self.assertFalse(journal.path.exists())

    def test_void_is_journal_only_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "payloads" / "sample-a.bin"
            source.parent.mkdir()
            source.write_bytes(self.payload)
            journal = RedactedJournal(root / "journal" / "voids.jsonl")
            runner = PhaseARunner(
                corpus_root=root,
                output_root=root / "out",
                journal=journal,
                runner_code_sha="a" * 40,
                environment={"host": "Arcana-DEVS"},
                config=RunnerConfig(),
                executor=FakeExecutor(self.payload, fail=True),
            )

            trial = runner.try_trial(self.sample, FakeAdapter(), trial_no=1, randomized_order=2)
            self.assertIsNone(trial)
            record = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertEqual(record["reason"], "timeout")
            self.assertEqual(record["sample_id"], "sample-a")
            self.assertNotIn("secret", json.dumps(record).lower())
            self.assertNotIn("error", record)

    def test_version_mismatch_is_journaled_and_never_becomes_a_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "payloads" / "sample-a.bin"
            source.parent.mkdir()
            source.write_bytes(self.payload)
            journal = RedactedJournal(root / "journal" / "voids.jsonl")
            runner = PhaseARunner(
                corpus_root=root,
                output_root=root / "out",
                journal=journal,
                runner_code_sha="a" * 40,
                environment={"host": "Arcana-DEVS"},
                config=RunnerConfig(),
                executor=FakeExecutor(self.payload),
            )
            self.assertIsNone(
                runner.try_trial(
                    self.sample,
                    VersionMismatchAdapter(),
                    trial_no=1,
                    randomized_order=1,
                )
            )
            record = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertEqual(record["reason"], "invalid_input_or_capability")

    def test_bundle_has_resource_trials_and_distinct_empty_page_scopes(self):
        runner = PhaseARunner.for_bundle_only(
            runner_code_sha="a" * 40,
            environment={"host": "Arcana-DEVS"},
        )
        bundle = runner.bundle([])
        self.assertEqual(bundle["resource_results"], [])
        self.assertEqual(
            bundle["page_results"],
            {
                "explicit_wasm_application": [],
                "transparent_http_page": [],
            },
        )
        self.assertNotIn("voids", bundle)
        self.assertEqual(bundle["environment"]["code_sha"], "a" * 40)

    def test_failed_host_admission_produces_no_trials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = RedactedJournal(root / "journal" / "voids.jsonl")
            runner = PhaseARunner(
                corpus_root=root,
                output_root=root / "out",
                journal=journal,
                runner_code_sha="a" * 40,
                environment={"admission": {"accepted": False}},
                config=RunnerConfig(),
                executor=FakeExecutor(self.payload),
            )
            with self.assertRaisesRegex(RuntimeError, "admission"):
                runner.execute((self.sample,), (FakeAdapter(),))
            record = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertEqual(record, {"reason": "failed_admission"})


if __name__ == "__main__":
    unittest.main()
