"""The issued date on forecast lines and state notes follows the sample pin."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from havenlab import engine, phase_c


class IssueDateTest(unittest.TestCase):
    def setUp(self):
        self._asof = engine.ASOF
        engine.ASOF = pd.Timestamp("2031-03-04")

    def tearDown(self):
        engine.ASOF = self._asof

    def test_forecast_line_issued_follows_asof(self):
        line = phase_c._forecast_line(
            {"latest": {"month": "2031-02"}, "timeline": []},
            {"gates": {"pass": False}},
        )
        self.assertEqual(line["issued"], "2031-03-04")

    def test_state_note_week_follows_asof(self):
        regime = {
            "latest": {
                "month": "2031-02",
                "k": 0,
                "indep_runs": 0,
                "perm_p": None,
                "perm_reps": 0,
                "features": [],
                "forward": {"3": {"gold": {"p10": None, "p50": None, "p90": None, "n": 0}}},
            },
            "timeline": [],
        }
        forecast = {"state": None, "state_month": "2031-02"}
        with tempfile.TemporaryDirectory() as tmp:
            phase_c._state_note(Path(tmp), regime, forecast, [])
            page = Path(tmp) / "docs" / "state" / "2031-W10.html"
            self.assertTrue(page.exists())
            self.assertIn("2031-03-04", page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
