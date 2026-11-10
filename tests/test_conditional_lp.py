"""The interaction keeps a known high-state response near twice the low state."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.states import interaction_response  # noqa: E402


class ConditionalLPTest(unittest.TestCase):
    def test_high_state_is_about_twice_the_low_state(self):
        rng = np.random.default_rng(3)
        n = 420
        shock = rng.normal(size=n)
        state = rng.integers(0, 2, size=n).astype(float)
        y = 1.0 * shock + 1.0 * shock * state + rng.normal(scale=0.15, size=n)
        index = pd.RangeIndex(n)
        packed = interaction_response(
            pd.Series(y, index=index),
            pd.Series(shock, index=index),
            pd.Series(state, index=index),
            horizon=0,
            scale=1.0,
        )
        low = packed["low"][0]
        high = packed["high"][0]
        self.assertIsNotNone(low)
        ratio = high / low
        self.assertGreater(ratio, 1.5)
        self.assertLess(ratio, 2.5)


if __name__ == "__main__":
    unittest.main()
