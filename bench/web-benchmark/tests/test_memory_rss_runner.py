import unittest

from memory_rss_runner import SAMPLE_IDS, MeasurementVoid, linear_fit, parse_peak_rss


class MemoryRssRunnerTests(unittest.TestCase):
    def test_complete_preregistered_ladder_has_thirteen_cells(self) -> None:
        self.assertEqual(len(SAMPLE_IDS), 13)
        self.assertIn("cube-4096", SAMPLE_IDS)
        self.assertIn("raw-store-134217728", SAMPLE_IDS)

    def test_parses_gnu_time_peak_rss_in_bytes(self) -> None:
        report = "Maximum resident set size (kbytes): 1234\n"
        self.assertEqual(parse_peak_rss(report), 1234 * 1024)

    def test_rss_fit_is_linear_in_decoded_bytes(self) -> None:
        fit = linear_fit([(1.0, 3.0), (2.0, 5.0), (4.0, 9.0)])
        self.assertAlmostEqual(fit["slope"], 2.0)
        self.assertAlmostEqual(fit["intercept"], 1.0)
        self.assertAlmostEqual(fit["r_squared"], 1.0)
        self.assertEqual(fit["point_count"], 3)

    def test_rejects_missing_gnu_time_peak_rss(self) -> None:
        with self.assertRaises(MeasurementVoid):
            parse_peak_rss("no memory measurement\n")


if __name__ == "__main__":
    unittest.main()
