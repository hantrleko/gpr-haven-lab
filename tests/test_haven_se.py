"""The score interval uses the same delta-method formula in Python and on the page."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.engine import haven_delta_se  # noqa: E402


class HavenSeTest(unittest.TestCase):
    def test_hand_calculation(self):
        n = 36
        corrs = (0.2, -0.1, 0.3, -0.4)
        scale = math.sqrt(n - 3)
        ses = tuple((1.0 - r * r) / scale for r in corrs)
        se_e = 25.0 * math.sqrt(ses[0] ** 2 + ses[1] ** 2)
        se_g = 50.0 * ses[2]
        se_d = 50.0 * ses[3]
        expected = math.sqrt(se_e ** 2 + se_g ** 2 + se_d ** 2) / 3.0
        got = haven_delta_se(*corrs, n=n)
        self.assertAlmostEqual(got, expected, delta=1e-9)
        self.assertAlmostEqual(got, 4.1125, delta=0.02)


if __name__ == "__main__":
    unittest.main()
