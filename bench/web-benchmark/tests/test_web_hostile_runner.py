import unittest

from web_hostile_runner import build_hostile_cases, summarize_results


class WebHostileRunnerTests(unittest.TestCase):
    def test_schedule_contains_prefix_ladder_and_header_mutations(self):
        frame = bytes([0xCB, 0x52, 0x49, 0x4D, 1, 18]) + bytes(range(64))

        cases = build_hostile_cases(frame)
        ids = [case["case_id"] for case in cases]

        self.assertIn("empty", ids)
        self.assertIn("short-header", ids)
        self.assertIn("mutation-magic", ids)
        self.assertIn("mutation-version", ids)
        self.assertIn("mutation-mode", ids)
        self.assertIn("mutation-checksum", ids)
        self.assertTrue(any(case_id.startswith("prefix-") for case_id in ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(case["expect_reject"] for case in cases))

    def test_summary_is_fail_closed_for_missing_or_faulted_cases(self):
        passed = summarize_results(
            [
                {"status": "rejected", "fault": False},
                {"status": "rejected", "fault": False},
            ],
            valid_roundtrip_exact=True,
        )
        self.assertEqual(passed["status"], "PASS")
        self.assertEqual(passed["rejected_count"], 2)

        failed = summarize_results(
            [
                {"status": "accepted", "fault": False},
                {"status": "rejected", "fault": True},
            ],
            valid_roundtrip_exact=True,
        )
        self.assertEqual(failed["status"], "FAIL")
        self.assertEqual(failed["rejected_count"], 1)


if __name__ == "__main__":
    unittest.main()
