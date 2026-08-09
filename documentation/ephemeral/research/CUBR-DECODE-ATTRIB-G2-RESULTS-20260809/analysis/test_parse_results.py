#!/usr/bin/env python3

import importlib.util
import math
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True


HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw"
MODULE_PATH = HERE / "parse_results.py"


def load_parser():
    spec = importlib.util.spec_from_file_location("parse_results", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ParseResultsTest(unittest.TestCase):
    def setUp(self):
        self.parser = load_parser()

    def test_perf_stat_parses_required_numeric_events(self):
        counters = self.parser.parse_perf_stat(RAW / "dickens.max" / "pstat1.txt")
        self.assertEqual(counters["cycles"], 479_452_639_967)
        self.assertEqual(counters["instructions"], 707_352_175_522)
        self.assertEqual(counters["cache-misses"], 3_887_391_138)
        self.assertEqual(counters["dTLB-load-misses"], 822_945_163)
        self.assertNotIn("LLC-loads", counters)

    def test_full_symbol_report_retains_tail_and_named_shares(self):
        report = self.parser.parse_symbol_report(
            HERE / "full-symbols" / "dickens.max.txt"
        )
        self.assertEqual(report["rows"], 257)
        self.assertTrue(math.isclose(report["rounded_sum"], 99.87, abs_tol=0.001))
        self.assertEqual(report["named"]["cm2_predict_bit"], 49.72)
        self.assertEqual(report["named"]["cm2_ctr_upd"], 32.81)
        self.assertEqual(report["named"]["cm2_decode_shell"], 0.46)

    def test_cell_metrics_are_per_file_and_g3_controls_cycles(self):
        journal = self.parser.parse_journal(RAW / "journal.jsonl")
        dickens = self.parser.build_cell_metrics(
            "dickens/max", 10_192_446, RAW, HERE, journal
        )
        self.assertTrue(dickens["cycles_reportable"])
        self.assertTrue(math.isclose(dickens["cycles1_per_bit"], 5879.999756, abs_tol=1e-6))
        self.assertTrue(math.isclose(dickens["ipc1"], 1.475333, abs_tol=1e-6))

        xray = self.parser.build_cell_metrics(
            "x-ray/max", 8_474_240, RAW, HERE, journal
        )
        self.assertEqual(xray["instrument_class"], "instrument-perturbed")
        self.assertFalse(xray["cycles_reportable"])
        self.assertIsNone(xray["cycles1_per_bit"])
        self.assertTrue(xray["symbols_reportable"])

    def test_robust_prediction_axes_and_indeterminate_axes(self):
        result = self.parser.build_result(RAW, HERE)
        self.assertEqual(result["predictions"]["P1"]["status"], "SUPPORTED")
        self.assertTrue(
            math.isclose(
                result["cells"]["dickens/max"]["cm2_named_machinery_share"],
                92.85,
                abs_tol=0.001,
            )
        )
        self.assertTrue(
            math.isclose(
                result["cells"]["dickens/max"]["cm2_named_machinery_amdahl_ceiling"],
                13.986014,
                abs_tol=1e-6,
            )
        )
        self.assertTrue(
            math.isclose(
                result["cells"]["xml/max"]["cm2_named_machinery_share"],
                90.66,
                abs_tol=0.001,
            )
        )
        self.assertEqual(result["predictions"]["P2"]["status"], "INDETERMINATE")
        self.assertEqual(result["predictions"]["P3"]["status"], "INDETERMINATE")
        self.assertEqual(result["predictions"]["P4"]["status"], "SUPPORTED")
        self.assertTrue(
            math.isclose(
                result["cells"]["x-ray/max"]["geocm_replay_share"],
                98.20,
                abs_tol=0.001,
            )
        )
        self.assertEqual(result["predictions"]["P5"]["status"], "INDETERMINATE")


if __name__ == "__main__":
    unittest.main()
