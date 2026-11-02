"""Benchmarks for the pinned sample. These do not refit the VAR."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.engine import (  # noqa: E402
    SAMPLE_END,
    _panel_from_derived,
    add_rolling,
    build_panel,
    daily_event_study,
    event_window,
    fit_local_projection,
    gold_daily_jumps,
    gold_jump_sensitivity,
    local_projection_response,
    placebo_bundle,
    placebo_sample,
)
from havenlab.version import LAB_VERSION
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
        bundle = placebo_bundle(self.panel, EVENTS, 6)
        self.assertIn("blocked", bundle)
        self.assertLessEqual(bundle["blocked"]["n_gold"], bundle["overlapping"]["n_gold"])
        hormuz = event_window(self.panel, "2026-03", 6)["cum"]["gold"]
        rank = sum(value <= hormuz for value in bundle["gold"]) / len(bundle["gold"])
        self.assertGreaterEqual(rank, 0)
        self.assertLessEqual(rank, 1)

    def test_web_payload_version(self):
        path = ROOT / "docs" / "lab_data_monthly.json"
        if not path.exists():
            self.skipTest("run build.py before checking the published payload")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["meta"]["version"], LAB_VERSION)
        self.assertIn("windows", payload)
        self.assertIn("state", payload["var"]["lp"])
        self.assertIn("act", payload["var"]["lp"])
        self.assertIn("car", payload)
        self.assertIn("gold", payload["car"]["by_event"]["hormuz_2026"])
        self.assertNotIn("daily", payload)

    def test_non_mideast_events_exist(self):
        ids = {event["id"] for event in EVENTS}
        self.assertTrue({"brexit_2016", "nk_2017", "taiwan_2022"} <= ids)
        for event in EVENTS:
            self.assertIn(event["region"], {"mideast", "other"})
            self.assertTrue(event["name_en"])
            self.assertNotIn("黄金下跌", event["name"])
            self.assertNotIn("黄金上涨", event["name"])

    def test_local_projection_is_not_summed_across_horizons(self):
        rng = np.random.default_rng(0)
        shock = pd.Series(rng.normal(size=160))
        ret = pd.Series(0.4 * shock.to_numpy() + rng.normal(scale=0.05, size=160))
        out = local_projection_response(ret, shock, horizon=2, scale=1.0, min_n=30)
        self.assertAlmostEqual(out["cum"][0], 0.4, delta=0.08)
        self.assertAlmostEqual(out["cum"][2], 0.4, delta=0.15)
        self.assertLess(abs(out["cum"][2]), 0.9)

    def test_daily_car_and_gold_jump(self):
        car = daily_event_study(self.daily)
        hormuz = car["by_event"]["hormuz_2026"]["gold"]["m1_p5"]
        self.assertEqual(hormuz["n"], 7)
        self.assertIn("q", hormuz)
        rolled = add_rolling(self.panel)
        self.assertTrue(np.isfinite(rolled["haven_lo"]).any())
        self.assertTrue(np.isfinite(rolled["haven_pc1"]).any())
        jump = gold_jump_sensitivity(self.panel, self.daily)
        self.assertEqual(jump["date"], "2026-01-30")
        self.assertLess(jump["january_sum_daily"], jump["january_ex_jump"])
        lp = fit_local_projection(rolled, horizon=1)
        self.assertIn("high", lp["state"])
        self.assertIsNotNone(lp["state"]["high"])

    def test_derived_panel_keeps_the_pinned_sample(self):
        panel = _panel_from_derived(ROOT / "replication" / "panel_monthly.csv")
        self.assertEqual(str(panel.index[0]), "2007-08")
        self.assertEqual(str(panel.index[-1]), "2026-09")
        self.assertEqual(len(panel), len(self.panel))


if __name__ == "__main__":
    unittest.main()
