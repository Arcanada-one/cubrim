import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

from adapters import ProcessMeasurement
from model import PHASE_A_WARMUPS, BenchmarkSample, RunnerConfig
import run
from run import PhaseARunner, RedactedJournal, _git_code_sha, capture_environment

REPO_ROOT = getattr(run, "REPO_ROOT", None)


class FakeAdapter:
    name = "gzip-9"
    flags = ("-9",)
    capabilities = {"whole_buffer_decode": True}

    def identity(self):
        return SimpleNamespace(
            name="gzip-9",
            version="gzip test",
            binary_path="/usr/bin/gzip",
            binary_sha256="b" * 64,
            flags=self.flags,
            binary_package="gzip-9",
            binary_package_version="1.2.3-1",
            source_package="gzip-9",
            source_package_version="1.2.3-1",
            upstream_release_sha="c" * 40,
            upstream_source_reference="https://example.com/gzip/commit/" + "c" * 40,
            codec_build_provenance_sha256="d" * 64,
        )


class FakeExecutor:
    def __init__(self, payload: bytes, fail: bool = False):
        self.payload = payload
        self.fail = fail

    def compress(self, adapter, *paths):
        source, target = paths[-2:]
        if self.fail:
            raise TimeoutError("timed out while reading /secret/input")
        target.write_bytes(b"compressed")
        return ProcessMeasurement(1_250_000, 4096, hashlib.sha256(b"compressed").hexdigest())

    def decompress(self, adapter, *paths):
        source, target = paths[-2:]
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
        with patch("run.subprocess.run", side_effect=responses) as run_mock:
            with self.assertRaisesRegex(RuntimeError, "clean committed"):
                _git_code_sha(require_clean=True)
        for call in run_mock.call_args_list:
            self.assertEqual(call.kwargs.get("cwd"), REPO_ROOT)

    def test_runner_sha_is_independent_of_foreign_cwd(self):
        expected = _git_code_sha()
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                try:
                    actual = _git_code_sha()
                except subprocess.CalledProcessError as exc:
                    self.fail(f"runner SHA depended on caller cwd: {exc}")
                self.assertEqual(actual, expected)
            finally:
                os.chdir(previous)

    def test_absolute_cli_from_foreign_cwd_rejects_dirty_runner_worktree(self):
        probe = REPO_ROOT / ".cubr0074-dirty-tree-probe"
        self.assertFalse(probe.exists())
        with tempfile.TemporaryDirectory() as directory:
            try:
                probe.write_text("dirty\n", encoding="utf-8")
                completed = subprocess.run(
                    (
                        sys.executable,
                        str(BENCH_DIR / "run.py"),
                        "--phase-a",
                        "--check",
                        "--out",
                        str(Path(directory) / "out"),
                        "--journal",
                        str(Path(directory) / "journal"),
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    cwd=directory,
                )
            finally:
                probe.unlink(missing_ok=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("clean committed runner tree", completed.stderr)

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
            self.assertTrue(hasattr(trial, "codec_build_provenance_sha256"))
            self.assertEqual(trial.codec_build_provenance_sha256, "d" * 64)
            self.assertEqual(trial.randomized_order, 7)
            self.assertEqual(trial.trial_no, 1)
            self.assertRegex(
                trial.measured_at,
                r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$",
            )
            self.assertEqual(trial.metrics["compression_duration"], 1.25)
            self.assertEqual(trial.metrics["decompression_duration"], 0.75)
            self.assertEqual(trial.metrics["peak_memory"], 8192)
            self.assertEqual(
                trial.metrics["compression_ratio"],
                len(b"compressed") / len(self.payload),
            )
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
        self.assertEqual(bundle.get("phase"), "A")
        self.assertIn("protocol", bundle)
        self.assertEqual(bundle["protocol"]["warmups"], 3)
        self.assertIn("corpus", bundle)
        self.assertIn("toolchain", bundle)
        self.assertIn("resource_summaries", bundle)

    def test_environment_is_closed_and_does_not_capture_hostname(self):
        environment = capture_environment("a" * 40)
        self.assertEqual(
            set(environment),
            {"code_sha", "cpu", "os", "affinity", "admission"},
        )
        self.assertNotIn("host", json.dumps(environment).casefold())

    def test_run_timing_is_captured_during_execution_and_wraps_all_trials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "payloads" / "sample-a.bin"
            source.parent.mkdir()
            source.write_bytes(self.payload)
            runner = PhaseARunner(
                corpus_root=root,
                output_root=root / "out",
                journal=RedactedJournal(root / "journal" / "voids.jsonl"),
                runner_code_sha="a" * 40,
                environment={"admission": {"accepted": True}},
                config=RunnerConfig(),
                executor=FakeExecutor(self.payload),
            )
            start = "2026-01-01T00:00:00.000000Z"
            measured = "2026-01-01T00:00:01.000000Z"
            completed = "2026-01-01T00:00:02.000000Z"
            timestamps = [start, *([measured] * 33), completed]
            with (
                patch("run.utc_now", side_effect=timestamps),
                patch("summarize.finalize_bundle", side_effect=lambda bundle, **_: bundle),
            ):
                bundle = runner.execute((self.sample,), (FakeAdapter(),))

            self.assertEqual(
                bundle["run_timing"],
                {"started_at": start, "completed_at": completed},
            )
            self.assertEqual(len(bundle["resource_results"]), 30)
            self.assertEqual(
                {trial["measured_at"] for trial in bundle["resource_results"]},
                {measured},
            )

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

    def test_missing_or_non_object_host_admission_fails_before_execution(self):
        for environment in ({}, {"admission": None}, {"admission": []}):
            with self.subTest(environment=environment):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    journal = RedactedJournal(root / "journal" / "voids.jsonl")
                    executor = FakeExecutor(self.payload)
                    runner = PhaseARunner(
                        corpus_root=root,
                        output_root=root / "out",
                        journal=journal,
                        runner_code_sha="a" * 40,
                        environment=environment,
                        config=RunnerConfig(),
                        executor=executor,
                    )
                    with (
                        patch.object(executor, "compress") as compress,
                        patch.object(executor, "decompress") as decompress,
                        self.assertRaisesRegex(RuntimeError, "admission"),
                    ):
                        runner.execute((self.sample,), (FakeAdapter(),))
                    compress.assert_not_called()
                    decompress.assert_not_called()
                    record = json.loads(journal.path.read_text(encoding="utf-8"))
                    self.assertEqual(record, {"reason": "failed_admission"})


if __name__ == "__main__":
    unittest.main()
