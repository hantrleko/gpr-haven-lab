"""Spot gold is the published series. Futures rolls are a robustness check."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.engine import (  # noqa: E402
    RAW,
    _month_level_return,
    load_gold_basis,
    repair_roll_jumps,
)


class RollJumpTest(unittest.TestCase):
    def test_january_2026_gap_is_recorded_and_spot_month_is_kept(self):
        index = pd.bdate_range("2025-12-01", "2026-02-27")
        spot = pd.Series(1800.0 * np.exp(np.linspace(0.0, 0.04, len(index))), index=index)
        fut = spot.copy()
        stamp = pd.Timestamp("2026-01-30")
        self.assertIn(stamp, fut.index)
        fut.loc[stamp] = float(fut.loc[stamp]) * float(np.exp(-0.08))
        repaired, jumps = repair_roll_jumps(fut, spot)
        row = next(item for item in jumps if item["date"] == "2026-01-30")
        self.assertLess(row["fut_log_return"], row["spot_log_return"])
        self.assertAlmostEqual(row["gap_pp"], row["fut_log_return"] - row["spot_log_return"], delta=0.05)
        spot_month = float(_month_level_return(spot)["ret"].loc["2026-01"])
        repaired_month = float(_month_level_return(repaired)["ret"].loc["2026-01"])
        self.assertLess(abs(spot_month - repaired_month), 0.05)

    def test_primary_month_matches_the_spot_file(self):
        if not (RAW / "gold_lbma_fred.csv").exists():
            self.skipTest("run fetch_data.py before checking the spot file")
        spot, _repaired, diag = load_gold_basis()
        january = diag["january_2026"]
        self.assertIsNotNone(january["repair_gap_pp"])
        self.assertIsNotNone(january["spot_pp"])
        published = float(_month_level_return(spot)["ret"].loc["2026-01"])
        self.assertLess(abs(published - january["spot_pp"]), 0.05)
        self.assertEqual(diag["primary"], "spot")


if __name__ == "__main__":
    unittest.main()
