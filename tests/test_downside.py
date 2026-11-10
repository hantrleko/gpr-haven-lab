"""Downside beta sees a left-tail hedge that Pearson averages away."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.haven_metrics import downside_beta  # noqa: E402


class DownsideBetaTest(unittest.TestCase):
    def test_left_tail_hedge_is_negative_while_pearson_stays_near_zero(self):
        rng = np.random.default_rng(7)
        equity = rng.normal(size=500)
        gold = rng.normal(scale=0.2, size=500)
        cutoff = np.quantile(equity, 0.20)
        down = equity < cutoff
        gold[down] = -1.2 * equity[down]
        # The other four fifths move with equities, which pulls the symmetric correlation back toward zero.
        gold[~down] += 0.85 * equity[~down]
        clipped, raw = downside_beta(gold, equity)
        pearson = float(np.corrcoef(gold, equity)[0, 1])
        self.assertLess(raw, -0.5)
        self.assertLess(clipped, 0)
        self.assertLess(abs(pearson), 0.25)


if __name__ == "__main__":
    unittest.main()
