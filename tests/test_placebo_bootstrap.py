"""Stationary bootstrap: same seed, a usable percentile SE, shared time index."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.null_model import NULL_SEED, stationary_bootstrap_placebo, stationary_indices  # noqa: E402


def _panel(seed: int = 0, n: int = 240) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    common = rng.normal(size=n)
    gold = common + rng.normal(scale=0.15, size=n)
    csi = common + rng.normal(scale=0.15, size=n)
    frame = pd.DataFrame(
        {
            "ret_gold": gold,
            "ret_csi": csi,
            "ret_hsi": common + rng.normal(scale=0.4, size=n),
            "ret_dxy": rng.normal(size=n),
            "ret_brent": rng.normal(size=n),
            "dgpr": rng.normal(size=n),
        },
        index=pd.period_range("2000-01", periods=n, freq="M"),
    )
    return frame


class PlaceboBootstrapTest(unittest.TestCase):
    def test_same_seed_is_identical(self):
        panel = _panel()
        events = [{"id": "a", "date": "2010-06-15", "month": "2010-06"}]
        first = stationary_bootstrap_placebo(panel, events, 12, reps=300, seed=NULL_SEED)
        second = stationary_bootstrap_placebo(panel, events, 12, reps=300, seed=NULL_SEED)
        self.assertEqual(first["by_event"]["a"]["gold"]["pct"], second["by_event"]["a"]["gold"]["pct"])
        self.assertEqual(first["by_event"]["a"]["haven"]["pct"], second["by_event"]["a"]["haven"]["pct"])

    def test_percentile_se_is_small_at_two_thousand_draws(self):
        panel = _panel()
        events = [{"id": "a", "date": "2010-06-15", "month": "2010-06"}]
        packed = stationary_bootstrap_placebo(panel, events, 12, reps=2000, seed=NULL_SEED)
        se = packed["by_event"]["a"]["gold"]["se"]
        self.assertLess(se, 0.06)
        self.assertEqual(packed["block"], 12)

    def test_shared_index_keeps_gold_csi_correlation(self):
        panel = _panel()
        width = 12
        reps = 400
        rng = np.random.default_rng(NULL_SEED + width * 1009)
        index = stationary_indices(len(panel), width, reps, width, rng)
        gold = panel["ret_gold"].to_numpy(dtype=float)[index]
        csi = panel["ret_csi"].to_numpy(dtype=float)[index]
        gold_c = gold - gold.mean(axis=1, keepdims=True)
        csi_c = csi - csi.mean(axis=1, keepdims=True)
        denom = np.sqrt((gold_c * gold_c).sum(axis=1) * (csi_c * csi_c).sum(axis=1))
        boot = ((gold_c * csi_c).sum(axis=1) / denom).mean()
        original = float(np.corrcoef(panel["ret_gold"], panel["ret_csi"])[0, 1])
        self.assertLess(abs(float(boot) - original), 0.05)


if __name__ == "__main__":
    unittest.main()
