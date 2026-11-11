"""Analog months have to recall a known twin and ignore data after the target."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from havenlab.regime import analog_months, count_runs


def _twin_frame() -> tuple[pd.DataFrame, pd.PeriodIndex]:
    index = pd.period_range("2000-01", periods=180, freq="M")
    rng = np.random.default_rng(0)
    data = {name: rng.uniform(-1.0, 1.0, index.size) for name in ("gpr", "real_rate", "dollar", "vix")}
    for name in data:
        data[name][70] = 5.0
        data[name][160] = 5.0
    data["ret_gold"] = rng.normal(size=index.size)
    data["ret_csi"] = rng.normal(size=index.size)
    data["high_gpr"] = np.zeros(index.size)
    return pd.DataFrame(data, index=index), index


class RegimeTest(unittest.TestCase):
    def test_incomplete_window_is_not_a_match(self) -> None:
        frame, index = _twin_frame()
        found = analog_months(frame, str(index[40]), k=5, reps=0)
        self.assertFalse(found["ok"])
        self.assertEqual(found["features"], [])

    def test_known_twin_is_recalled(self) -> None:
        frame, index = _twin_frame()
        found = analog_months(frame, str(index[160]), k=5, reps=30, seed=3)
        self.assertTrue(found["ok"])
        self.assertIn(str(index[70]), found["neighbors"])
        self.assertGreaterEqual(found["indep_runs"], 1)
        self.assertLessEqual(found["indep_runs"], found["k"])

    def test_shuffling_the_future_does_not_change_the_match(self) -> None:
        frame, index = _twin_frame()
        target = str(index[160])
        before = analog_months(frame, target, k=5, reps=0)
        shuffled = frame.copy()
        rng = np.random.default_rng(11)
        for column in ("gpr", "real_rate", "dollar", "vix", "ret_gold", "ret_csi"):
            tail = shuffled.iloc[161:][column].to_numpy(dtype=float).copy()
            rng.shuffle(tail)
            shuffled.iloc[161:, shuffled.columns.get_loc(column)] = tail
        after = analog_months(shuffled, target, k=5, reps=0)
        self.assertEqual(before["neighbors"], after["neighbors"])
        self.assertEqual(before["forward"], after["forward"])

    def test_runs_split_when_the_gap_is_wide(self) -> None:
        self.assertEqual(count_runs([1, 2, 3, 40], 12), 2)

    def test_permutation_scores_return_spread_not_distance(self) -> None:
        frame, index = _twin_frame()
        frame["ret_gold"] = 0.01
        found = analog_months(frame, str(index[160]), k=8, reps=40, seed=1)
        self.assertEqual(found["perm_statistic"], "iqr_gold_3m")
        self.assertEqual(found["perm_p"], 1.0)

    def test_future_gold_does_not_change_the_permutation(self) -> None:
        frame, index = _twin_frame()
        target = str(index[160])
        before = analog_months(frame, target, k=5, reps=20, seed=2)
        shuffled = frame.copy()
        rng = np.random.default_rng(11)
        tail = shuffled.iloc[161:]["ret_gold"].to_numpy(dtype=float).copy()
        rng.shuffle(tail)
        shuffled.iloc[161:, shuffled.columns.get_loc("ret_gold")] = tail
        after = analog_months(shuffled, target, k=5, reps=20, seed=2)
        self.assertEqual(before["neighbors"], after["neighbors"])
        self.assertEqual(before["perm_p"], after["perm_p"])


if __name__ == "__main__":
    unittest.main()
