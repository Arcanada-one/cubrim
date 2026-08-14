from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hypothesis_runner import (
    CUBE_SIZES,
    RAW_SIZES,
    bootstrap_median,
    evaluate_probe,
    loglog_fit,
    write_payload,
)


class HypothesisRunnerMathTests(unittest.TestCase):
    def test_bootstrap_median_is_reproducible(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        first = bootstrap_median(values, iterations=200, seed=74075)
        second = bootstrap_median(values, iterations=200, seed=74075)
        self.assertEqual(first, second)
        self.assertEqual(first["median"], 3.0)
        self.assertLessEqual(first["low"], first["median"])
        self.assertGreaterEqual(first["high"], first["median"])

    def test_loglog_fit_recovers_known_slope(self) -> None:
        fit = loglog_fit([(size, float(size * size)) for size in (4, 8, 16, 32)])
        self.assertAlmostEqual(fit["slope_alpha"], 2.0, places=12)
        self.assertAlmostEqual(fit["r_squared"], 1.0, places=12)

    def test_payload_generation_is_deterministic_and_sized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.payload"
            second = root / "second.payload"
            write_payload(first, CUBE_SIZES[0], "cube", 1234)
            write_payload(second, CUBE_SIZES[0], "cube", 1234)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first.stat().st_size, CUBE_SIZES[0])

            raw = root / "raw.payload"
            write_payload(raw, RAW_SIZES[0], "raw_store", 5678)
            self.assertEqual(raw.stat().st_size, RAW_SIZES[0])
            self.assertNotEqual(raw.read_bytes()[:64], b"\0" * 64)


class HypothesisEvaluationTests(unittest.TestCase):
    def _probe_output(self) -> dict[str, object]:
        samples: list[dict[str, object]] = []
        for ladder, sizes in (("cube", CUBE_SIZES), ("raw_store", RAW_SIZES)):
            for size in sizes:
                sample_id = f"{ladder}-{size}"
                samples.append(
                    {
                        "sample_id": sample_id,
                        "path": f"/tmp/{sample_id}.payload",
                        "expected_mode": ladder,
                        "mode": ladder,
                        "encoder_path": (
                            "cubrim-file-v1/base-cube-raw"
                            if ladder == "cube"
                            else "cubrim-file-v1/raw-store-wire"
                        ),
                        "input_bytes": size,
                        "input_sha256": "a" * 64,
                        "frame_bytes": size,
                        "frame_sha256": "b" * 64,
                        "trials": [
                            {
                                "trial_no": trial,
                                "randomized_order": trial,
                                "encode_ns": size,
                                "decode_ns": size,
                                "peak_memory_bytes": 4096,
                                "decoded_sha256": "a" * 64,
                                "roundtrip_exact": True,
                            }
                            for trial in range(1, 31)
                        ],
                    }
                )
        return {
            "schema_version": 1,
            "codec_key": "cubrim-file-v1",
            "codec_version": "0.3.2",
            "trials_per_cell": 30,
            "warmups": 3,
            "seed": 74075,
            "samples": samples,
        }

    def test_evaluator_emits_linearity_and_throughput_derived_rows(self) -> None:
        result = evaluate_probe(self._probe_output(), bootstrap_iterations=100, seed=74075)
        self.assertEqual(len(result["cells"]), 13)
        self.assertIn("cube-linearity", result["derived"])
        self.assertIn("raw_store-linearity", result["derived"])
        self.assertIn("cube-throughput", result["derived"])
        self.assertAlmostEqual(
            result["derived"]["cube-linearity"]["slope_alpha"], 1.0, places=12
        )
        self.assertAlmostEqual(
            result["derived"]["raw_store-linearity"]["slope_alpha"], 1.0, places=12
        )
        self.assertEqual(result["derived"]["cube-throughput"]["decision"], "WIN")

    def test_evaluator_rejects_incomplete_cell(self) -> None:
        probe = self._probe_output()
        probe["samples"][0]["trials"] = probe["samples"][0]["trials"][:-1]
        with self.assertRaises(RuntimeError):
            evaluate_probe(probe, bootstrap_iterations=100, seed=74075)

    def test_evaluator_rejects_competitive_mode_relabelled_as_cube(self) -> None:
        probe = self._probe_output()
        probe["samples"][0]["mode"] = "cm2"
        with self.assertRaises(RuntimeError):
            evaluate_probe(probe, bootstrap_iterations=100, seed=74075)


if __name__ == "__main__":
    unittest.main()
