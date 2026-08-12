"""Admission is a property of the measurement window, not of its first instant.

A Phase A run took 468 s on arcana-devs while the host went from 0.67 to 2.13
load per CPU. Every trial was accepted, every round trip was exact, and the
bundle recorded `accepted: true` beside the load figure from before the ramp.
Comparing the first third of each cell to the last third showed compression
timings drifting +20.5% and decompression +23.0% at the median, while
`compressed_bytes` was identical within all 65 cells: density does not care how
loaded the host is, and timing is nothing but a statement about the host.

These tests pin the check that refuses to keep measuring once the host stops
being quiet.
"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

from model import BenchmarkSample, RunnerConfig  # noqa: E402
from run import PhaseARunner, RedactedJournal  # noqa: E402
from tests.test_runner import FakeAdapter, FakeExecutor  # noqa: E402


class AdmissionWindowTests(unittest.TestCase):
    def setUp(self):
        self.payload = b"lossless payload"
        self.sample = BenchmarkSample(
            sample_id="sample-a",
            path="payloads/sample-a.bin",
            sha256=hashlib.sha256(self.payload).hexdigest(),
            byte_count=len(self.payload),
            media_type="application/octet-stream",
            size_class="small",
        )

    def _runner(self, root: Path) -> PhaseARunner:
        source = root / "payloads" / "sample-a.bin"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(self.payload)
        runner = PhaseARunner(
            corpus_root=root,
            output_root=root / "out",
            journal=RedactedJournal(root / "journal" / "voids.jsonl"),
            runner_code_sha="a" * 40,
            environment={
                "host": "test",
                "cpu": "test",
                "os": "test",
                "admission": {
                    "load_1m": 4.0,
                    "load_per_cpu": 0.25,
                    "max_load_per_cpu": 1.0,
                    "temperature_c": 40,
                    "max_temperature_c": 90,
                    "accepted": True,
                },
            },
            config=RunnerConfig(),
            executor=FakeExecutor(self.payload),
        )
        runner._load_ceiling = 1.0
        runner.observed_max_load_per_cpu = 0.25
        return runner

    def test_a_host_that_stays_quiet_is_never_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self._runner(root)
            with patch("run._current_load_per_cpu", return_value=0.4):
                for order in range(1, 120):
                    runner._reassert_admission(order)
            self.assertAlmostEqual(runner.observed_max_load_per_cpu, 0.4)
            self.assertFalse((root / "journal" / "voids.jsonl").exists())

    def test_a_host_that_stops_being_quiet_stops_the_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self._runner(root)
            with patch("run._current_load_per_cpu", return_value=2.13):
                with self.assertRaisesRegex(RuntimeError, "admission lapsed"):
                    runner._reassert_admission(1)

            journal = (root / "journal" / "voids.jsonl").read_text(encoding="utf-8")
            # The record has to say how loaded the host was, or the next reader
            # cannot tell a marginal overshoot from a saturated box.
            self.assertIn('"reason":"failed_admission_midrun"', journal)
            self.assertIn('"load_per_cpu_milli":2130', journal)
            self.assertIn('"randomized_order":1', journal)

    def test_the_check_is_sampled_rather_than_run_every_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = self._runner(Path(directory))
            with patch("run._current_load_per_cpu", return_value=0.4) as load:
                for order in range(1, 101):
                    runner._reassert_admission(order)
            self.assertEqual(load.call_count, 4)
            self.assertEqual(PhaseARunner.ADMISSION_RECHECK_EVERY, 25)

    def test_an_unreadable_load_average_does_not_fail_a_run(self):
        # A host without getloadavg is a host we cannot judge, which is not the
        # same as a host we have judged and found busy.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self._runner(root)
            with patch("run._current_load_per_cpu", return_value=None):
                runner._reassert_admission(1)
            self.assertFalse((root / "journal" / "voids.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
