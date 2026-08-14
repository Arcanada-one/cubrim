import unittest

from hostile_truncated_runner import (
    CASE_IDS,
    FAMILIES,
    GO_P99_ADD_NS,
    GO_P99_MULTIPLIER,
    GO_RUNTIME_NS,
    SIZES,
    WIN_P99_ADD_NS,
    WIN_P99_MULTIPLIER,
    WIN_RUNTIME_NS,
    nearest_rank,
    payload_for,
)


class HostileTruncatedRunnerTests(unittest.TestCase):
    def test_protocol_covers_three_families_and_five_sizes(self) -> None:
        self.assertEqual(FAMILIES, ("structured_text", "structured_json", "high_entropy"))
        self.assertEqual(SIZES, (4096, 8192, 16384, 32768, 65536))
        self.assertEqual(len(FAMILIES) * len(SIZES), 15)
        self.assertEqual(len(CASE_IDS), 10)
        self.assertEqual(CASE_IDS[-3:], ("mutation-magic", "mutation-version", "mutation-mode"))

    def test_synthetic_payloads_are_exactly_sized_and_content_addressable(self) -> None:
        for family in FAMILIES:
            for size in SIZES:
                first = payload_for(family, size, 75075 + size)
                second = payload_for(family, size, 75075 + size)
                self.assertEqual(len(first), size)
                self.assertEqual(first, second)

    def test_valid_p99_and_frozen_time_ceiling_formulas(self) -> None:
        values = [100_000_000, 200_000_000, 300_000_000]
        p99 = int(nearest_rank(values, 0.99))
        self.assertEqual(p99, 300_000_000)
        self.assertEqual(max(GO_RUNTIME_NS, GO_P99_MULTIPLIER * p99 + GO_P99_ADD_NS), 1_210_000_000)
        self.assertEqual(max(WIN_RUNTIME_NS, WIN_P99_MULTIPLIER * p99 + WIN_P99_ADD_NS), 1_000_000_000)


if __name__ == "__main__":
    unittest.main()
