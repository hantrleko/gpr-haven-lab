"""Benchmarks for the pinned sample. These do not refit the VAR."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.engine import (  # noqa: E402
    SAMPLE_END,
    build_panel,
    event_window,
    gold_daily_jumps,
    placebo_sample,
)
from havenlab.events import EVENTS  # noqa: E402


class BenchmarkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel, cls.daily = build_panel()

    def test_sample_end_stays_pinned(self):
        self.assertEqual(str(SAMPLE_END), "2026-09")
        self.assertEqual(str(self.panel.index[0]), "2007-08")
        self.assertEqual(str(self.panel.index[-1]), "2026-09")
        later, _daily = build_panel(pd.Timestamp("2027-12-31"))
        self.assertEqual(str(later.index[-1]), "2026-09")
        self.assertEqual(len(later), len(self.panel))

    def test_known_event_windows(self):
        hormuz = event_window(self.panel, "2026-03", 6)
        self.assertFalse(hormuz["partial"])
        self.assertAlmostEqual(hormuz["cum"]["gold"], -15.79, delta=0.05)
        self.assertAlmostEqual(hormuz["cum"]["brent"], 22.19, delta=0.05)
        self.assertAlmostEqual(hormuz["cum"]["csi"], -1.83, delta=0.05)
        self.assertAlmostEqual(hormuz["haven_after"]["score"], 46.85, delta=0.15)

        ukraine = event_window(self.panel, "2022-02", 6)
        self.assertFalse(ukraine["partial"])
        self.assertAlmostEqual(ukraine["cum"]["gold"], -1.80, delta=0.05)
        self.assertAlmostEqual(ukraine["haven_after"]["score"], 69.44, delta=0.15)

        tail = event_window(self.panel, "2026-09", 6)
        self.assertTrue(tail["partial"])
        self.assertEqual(tail["n_after"], 1)

    def test_gold_jump_is_the_futures_print(self):
        jumps = gold_daily_jumps(self.daily["gold"], 2)
        self.assertEqual(jumps[0]["date"], "2026-01-30")
        self.assertAlmostEqual(jumps[0]["log_return"], -11.40, delta=0.08)
        self.assertEqual(jumps[1]["date"], "2013-04-15")
        self.assertAlmostEqual(jumps[1]["log_return"], -9.81, delta=0.08)

    def test_placebo_draw_is_stable(self):
        first = placebo_sample(self.panel, EVENTS, 6)
        second = placebo_sample(self.panel, EVENTS, 6)
        self.assertEqual(first["gold"], second["gold"])
        self.assertEqual(first["n_draw"], 120)
        self.assertGreater(first["n_pool"], 120)
        hormuz = event_window(self.panel, "2026-03", 6)["cum"]["gold"]
        rank = sum(value <= hormuz for value in first["gold"]) / len(first["gold"])
        self.assertGreaterEqual(rank, 0)
        self.assertLessEqual(rank, 1)

    def test_non_mideast_events_exist(self):
        ids = {event["id"] for event in EVENTS}
        self.assertTrue({"brexit_2016", "nk_2017", "taiwan_2022"} <= ids)
        for event in EVENTS:
            self.assertIn(event["region"], {"mideast", "other"})
            self.assertTrue(event["name_en"])
            self.assertNotIn("黄金下跌", event["name"])
            self.assertNotIn("黄金上涨", event["name"])


if __name__ == "__main__":
    unittest.main()
