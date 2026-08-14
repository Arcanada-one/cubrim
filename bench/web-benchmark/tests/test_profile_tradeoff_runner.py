from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "profile_tradeoff_runner.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("profile_tradeoff_runner", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProfileTradeoffRunnerTests(unittest.TestCase):
    def test_bootstrap_is_deterministic_and_order_independent(self) -> None:
        values = [50_000_000.0, 60_000_000.0, 70_000_000.0]
        self.assertEqual(MODULE.bootstrap_median(values, 75075), MODULE.bootstrap_median(values[::-1], 75075))

    def test_nearest_rank_is_conservative_at_endpoints(self) -> None:
        self.assertEqual(MODULE.nearest_rank([3.0, 1.0, 2.0], 0.025), 1.0)
        self.assertEqual(MODULE.nearest_rank([3.0, 1.0, 2.0], 0.975), 3.0)


if __name__ == "__main__":
    unittest.main()
