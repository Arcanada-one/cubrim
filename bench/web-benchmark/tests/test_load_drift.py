"""The drift read has to be right, because its output is quoted as a finding.

load_drift.py is what says a bundle that passed every check was measured on a
host that changed underneath it. Its arithmetic is small enough to check
directly against bundles whose answer is known by construction.
"""

import sys
import unittest
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

from load_drift import drift_report  # noqa: E402

CODECS = ("gzip-9", "brotli-11")
SAMPLES = ("sample-a", "sample-b")


def _bundle(duration_for) -> dict:
    """One bundle, 30 trials a cell, `duration_for(trial_no)` seconds apart."""
    trials = []
    for sample in SAMPLES:
        for codec in CODECS:
            for trial_no in range(1, 31):
                duration = duration_for(trial_no)
                trials.append(
                    {
                        "sample_id": sample,
                        "codec_key": codec,
                        "trial_no": trial_no,
                        # Ordering is by measured_at, not by trial_no: the real
                        # schedule is randomized, so the read must not assume
                        # the two agree.
                        "measured_at": f"2026-01-01T00:{trial_no:02d}:00Z",
                        "compressed_bytes": 1234,
                        "metrics": {
                            "compression_duration": duration,
                            "decompression_duration": duration / 2,
                        },
                    }
                )
    return {
        "resource_results": trials,
        "environment": {"admission": {"accepted": True, "load_per_cpu": 0.25}},
    }


class LoadDriftTests(unittest.TestCase):
    def test_a_steady_host_reports_no_drift(self):
        report = drift_report(_bundle(lambda trial_no: 10.0))
        self.assertEqual(report["cells"], 4)
        self.assertEqual(report["trials"], 120)
        self.assertEqual(report["cells_with_varying_compressed_bytes"], 0)
        for metric in ("compression_duration", "decompression_duration"):
            self.assertAlmostEqual(report[metric]["median_last_over_first"], 1.0)
            self.assertEqual(report[metric]["cells_over_1_25x"], 0)

    def test_a_host_that_slows_down_shows_up_in_every_cell(self):
        # Doubling across the window: the last third's median is 2x the first
        # third's, in both directions, in all four cells.
        report = drift_report(_bundle(lambda trial_no: 10.0 * (1 + trial_no / 30)))
        for metric in ("compression_duration", "decompression_duration"):
            self.assertGreater(report[metric]["median_last_over_first"], 1.5)
            self.assertEqual(report[metric]["cells_over_1_25x"], 4)

    def test_a_host_that_speeds_up_is_reported_too(self):
        # Drift is not assumed to have a direction; a run that started on a
        # busy host and finished on a quiet one is equally uncomparable.
        report = drift_report(_bundle(lambda trial_no: 10.0 * (2 - trial_no / 30)))
        self.assertLess(
            report["compression_duration"]["median_last_over_first"], 0.8
        )

    def test_varying_compressed_bytes_is_surfaced_not_swallowed(self):
        # If size moves within a cell the premise is broken somewhere else and
        # the drift numbers should not be read as a load story.
        bundle = _bundle(lambda trial_no: 10.0)
        bundle["resource_results"][0]["compressed_bytes"] = 999
        self.assertEqual(
            drift_report(bundle)["cells_with_varying_compressed_bytes"], 1
        )

    def test_the_window_is_measured_from_the_trials_themselves(self):
        report = drift_report(_bundle(lambda trial_no: 10.0))
        self.assertEqual(report["window_seconds"], 29 * 60)


if __name__ == "__main__":
    unittest.main()
