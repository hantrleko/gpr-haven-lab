"""Walk-forward parameters stay frozen, and a tied forecast does not pass the gate."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from havenlab.validation import pinball, summarize_walk, walk_forward

ROOT = Path(__file__).resolve().parents[1]


def _history() -> pd.DataFrame:
    index = pd.period_range("1998-01", periods=240, freq="M")
    rng = np.random.default_rng(4)
    gpr = np.cumsum(rng.normal(scale=0.2, size=index.size))
    real = np.cumsum(rng.normal(scale=0.05, size=index.size))
    ret = rng.normal(scale=2.0, size=index.size)
    return pd.DataFrame(
        {"gpr": gpr, "real_rate": real, "vix": np.abs(gpr) + 10, "ret_gold": ret, "ret_csi": ret * 0.2},
        index=index,
    )


class ValidationTest(unittest.TestCase):
    def test_pinball_signs(self) -> None:
        self.assertAlmostEqual(pinball(1.0, 0.0, 0.10), 0.10)
        self.assertAlmostEqual(pinball(-1.0, 0.0, 0.10), 0.90)

    def test_later_months_do_not_change_an_earlier_forecast(self) -> None:
        frame = _history()
        first = walk_forward(frame)
        changed = frame.copy()
        changed.loc[changed.index > pd.Period("2016-06", freq="M"), "gpr"] += 25
        second = walk_forward(changed)
        left = first.loc[first["month"] == "2016-03", "model"].iloc[0]
        right = second.loc[second["month"] == "2016-03", "model"].iloc[0]
        self.assertIsInstance(left, dict)
        self.assertEqual(left, right)

    def test_identical_forecasts_do_not_pass(self) -> None:
        row = {
            "month": "2016-01",
            "y": 0.0,
            "model": {"q10": -1.0, "q50": 0.0, "q90": 1.0},
            "unconditional": {"q10": -1.0, "q50": 0.0, "q90": 1.0},
            "gpr": {"q10": -1.0, "q50": 0.0, "q90": 1.0},
            "real_rate": {"q10": -1.0, "q50": 0.0, "q90": 1.0},
        }
        summary = summarize_walk(pd.DataFrame([row] * 30))
        self.assertFalse(summary["gates"]["pass"])
        self.assertFalse(summary["gates"]["improvement_at_least_8pct"])

    def test_missing_real_rate_baseline_blocks_the_claim(self) -> None:
        row = {
            "month": "2016-01",
            "y": 0.0,
            "model": {"q10": -5.0, "q50": 0.0, "q90": 1.0},
            "unconditional": {"q10": -1.0, "q50": 4.0, "q90": 8.0},
            "gpr": {"q10": -1.0, "q50": 4.0, "q90": 8.0},
            "real_rate": None,
        }
        summary = summarize_walk(pd.DataFrame([row] * 30))
        self.assertFalse(summary["gates"]["all_three_baselines_present"])
        self.assertFalse(summary["gates"]["pass"])

    def test_negative_template_was_written_before_the_score(self) -> None:
        text = (ROOT / "docs" / "validation.md").read_text(encoding="utf-8")
        self.assertIn("没有可靠的条件化能力", text)
        self.assertIn("8%", text)


if __name__ == "__main__":
    unittest.main()
