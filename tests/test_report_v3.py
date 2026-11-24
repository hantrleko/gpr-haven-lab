"""Rule-engine tests on a synthetic v3 payload (no network, no data/raw)."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

import havenlab.engine as engine
from havenlab import general, report_v3

ROOT = Path(__file__).resolve().parents[1]
RULES = json.loads((ROOT / "src" / "havenlab" / "rules" / "rules_v3.json").read_text(encoding="utf-8"))
EVENT_DATE = "2018-06-01"


def _ramp(idx: pd.DatetimeIndex, center: pd.Timestamp, total_log: float, days: int = 30, sigma: float = 0.01, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    logp = 5.0 + np.cumsum(rng.normal(0.0, sigma, len(idx)))
    dnum = (idx - pd.Timestamp("1970-01-01")).days.to_numpy()
    cnum = (center - pd.Timestamp("1970-01-01")).days
    frac = np.clip((dnum - cnum) / days, 0.0, 1.0)
    return pd.Series(np.exp(logp + total_log * frac), index=idx)


def _synthetic_series() -> dict[str, pd.Series]:
    idx = pd.bdate_range("2006-11-01", "2020-12-31")
    center = pd.Timestamp(EVENT_DATE)
    series = {
        # gold: quiet history, +35% over the month after the event
        "gold": _ramp(idx, center, np.log(1.35), sigma=0.002, seed=1),
        # silver: noisy history, +11% -> clear_up but below the k=7 cut? (lands clear)
        "silver": _ramp(idx, center, np.log(1.11), sigma=0.01, seed=2),
        "jpy": _ramp(idx, center, 0.0, sigma=0.008, seed=3),
        "chf": _ramp(idx, center, 0.0, sigma=0.008, seed=4),
        "ust": _ramp(idx, center, 0.0, sigma=0.008, seed=5),  # ends lean_up by chance
        "dxy": _ramp(idx, center, 0.0, sigma=0.008, seed=7),
    }
    bidx = idx[idx >= "2014-09-17"]
    rb = np.random.default_rng(9).normal(0.0, 0.012, len(bidx))
    series["btc"] = pd.Series(300.0 * np.exp(np.cumsum(rb)), index=bidx)
    # benchmark drops 20% over the month after the event
    series["spx"] = _ramp(idx, center, np.log(0.80), sigma=0.01, seed=10)
    series["csi"] = _ramp(idx, center, 0.0, sigma=0.012, seed=11)
    series["hsi"] = _ramp(idx, center, 0.0, sigma=0.014, seed=12)
    series["brent"] = _ramp(idx, center, 0.0, sigma=0.015, seed=13)
    gidx = pd.date_range("2006-11-01", "2020-12-31", freq="D")
    rg = np.random.default_rng(14)
    for asset_id, base in (("gpr", 120.0), ("gpr_act", 60.0), ("gpr_threat", 80.0)):
        vals = base + np.cumsum(rg.normal(0.0, 0.5, len(gidx))) + rg.normal(0.0, 2.0, len(gidx))
        series[asset_id] = pd.Series(np.clip(vals, 1.0, None), index=gidx)
    return series


EVENTS = [
    {"id": "test_event", "date": EVENT_DATE, "name": "T", "name_en": "T"},
    {"id": "e2", "date": "2015-03-10", "name": "E2", "name_en": "E2"},
    {"id": "e3", "date": "2019-08-15", "name": "E3", "name_en": "E3"},
]


def _crash_series(gold_log_ret: float, silver_log_ret: float | None = None) -> dict[str, pd.Series]:
    """_synthetic_series with gold/silver replaced by post-event crashes.

    jpy is pinned to a mild up-drift: its random-walk draw happens to land
    clear_down at the event date, which would pollute the down-tail list.
    """
    series = _synthetic_series()
    idx = pd.bdate_range("2006-11-01", "2020-12-31")
    center = pd.Timestamp(EVENT_DATE)
    series["gold"] = _ramp(idx, center, gold_log_ret, sigma=0.002, seed=1)
    if silver_log_ret is not None:
        series["silver"] = _ramp(idx, center, silver_log_ret, sigma=0.01, seed=2)
    series["jpy"] = _ramp(idx, center, np.log(1.03), sigma=0.006, seed=23)
    return series


def _cell(report: dict, asset_id: str, horizon: str = "30") -> dict:
    row = next(h for h in report["havens"] if h["id"] == asset_id)
    return row["by_h"][horizon]


class ReportV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_asof = engine.ASOF
        engine.ASOF = pd.Timestamp("2020-12-31")
        series = _synthetic_series()
        cls.payload = general.general_payload(series)
        cls.decoded = report_v3.decode_series(cls.payload)

    @classmethod
    def tearDownClass(cls):
        engine.ASOF = cls._old_asof

    def report(self, date, benchmark="spx", kind="preset", exclude=None):
        return report_v3.build_report(self.decoded, RULES, EVENTS, date, benchmark, kind, exclude)

    def test_clear_drop_headline_and_k_adjusted_labels(self):
        rep = self.report(EVENT_DATE, exclude="test_event")
        self.assertEqual(rep["headline"]["code"], "clear_drop_clear")
        self.assertEqual(rep["headline"]["grade"], "strong")
        self.assertEqual(rep["bench"]["state"], "clear_drop")
        self.assertEqual(rep["k"], {"7": 7, "30": 7, "91": 7})
        cut = 1.0 - RULES["family_alpha"] / 7
        gold = _cell(rep, "gold")
        silver = _cell(rep, "silver")
        ust = _cell(rep, "ust")
        self.assertEqual(gold["label"], "clear_up")
        self.assertGreaterEqual(gold["pct"], cut)
        self.assertEqual(silver["label"], "clear_up")
        self.assertGreaterEqual(silver["pct"], cut)
        # ust lands between the lean bar and the k-adjusted clear bar
        self.assertGreaterEqual(ust["pct"], RULES["lean_hi"])
        self.assertLess(ust["pct"], cut)
        self.assertEqual(ust["label"], "lean_up")
        self.assertIn("Gold", rep["headline"]["en"])
        self.assertIn("They acted", rep["headline"]["en"])

    def test_no_drop_headline_when_benchmark_rises(self):
        rep = self.report("2019-08-15", kind="preset", exclude="e3")
        self.assertEqual(rep["bench"]["state"], "no_drop")
        self.assertEqual(rep["headline"]["code"], "no_drop")
        self.assertEqual(rep["headline"]["grade"], "none")
        codes = [c["code"] for c in rep["caveats"]]
        self.assertIn("no_test", codes)

    def test_incomplete_headline_near_series_end(self):
        rep = self.report("2020-12-25", kind="custom")
        self.assertEqual(rep["bench"]["state"], "incomplete")
        self.assertFalse(rep["bench"]["complete"])
        self.assertEqual(rep["headline"]["code"], "incomplete")
        self.assertIsNone(rep["bench"]["pct"])
        codes = [c["code"] for c in rep["caveats"]]
        self.assertIn("incomplete", codes)
        self.assertIn("gpr_lag", codes)

    def test_btc_missing_before_2014_and_unrated_caveat(self):
        rep = self.report("2013-06-03", kind="custom")
        btc = _cell(rep, "btc")
        self.assertEqual(btc["label"], "missing")
        self.assertIsNone(btc["ret"])
        self.assertIsNone(btc["pct"])
        self.assertEqual(rep["k"]["30"], 6)
        unrated = next(c for c in rep["caveats"] if c["code"] == "unrated")
        self.assertIn("Bitcoin", unrated["en"])
        self.assertIn("比特币", unrated["zh"])

    def test_exclude_event_id_removes_self_from_history(self):
        excl = self.report(EVENT_DATE, kind="preset", exclude="test_event")
        incl = self.report(EVENT_DATE, kind="custom", exclude=None)
        g_excl = next(h for h in excl["history"] if h["id"] == "gold")
        g_incl = next(h for h in incl["history"] if h["id"] == "gold")
        self.assertEqual(g_excl["n"], 2)
        self.assertEqual(g_incl["n"], 3)
        # the constructed event is a clear_up for gold, so it only counts when included
        self.assertEqual(g_excl["clear_up"], 0)
        self.assertGreaterEqual(g_incl["clear_up"], 1)

    def test_latest_report_date_is_benchmark_last_minus_30(self):
        rep = report_v3.build_report(self.decoded, RULES, EVENTS, None, "spx", "latest")
        last_day = self.decoded["series"]["spx"]["days"][-1]
        expected = (date(1970, 1, 1) + timedelta(days=last_day - 30)).isoformat()
        self.assertEqual(rep["date"], expected)
        self.assertEqual(rep["kind"], "latest")
        codes = [c["code"] for c in rep["caveats"]]
        self.assertNotIn("hindsight_preset", codes)
        self.assertNotIn("hindsight_custom", codes)

    def test_caveat_order_preset(self):
        rep = self.report(EVENT_DATE, kind="preset", exclude="test_event")
        self.assertEqual(
            [c["code"] for c in rep["caveats"]],
            ["no_forecast", "hindsight_preset", "multi", "futures"],
        )
        rep_custom = self.report(EVENT_DATE, kind="custom")
        self.assertEqual(
            [c["code"] for c in rep_custom["caveats"]],
            ["no_forecast", "hindsight_custom", "multi", "futures"],
        )

    def test_report_shape_and_history_rows(self):
        rep = self.report(EVENT_DATE, kind="preset", exclude="test_event")
        for key in ("date", "kind", "benchmark", "rules_version", "headline", "pressure", "bench", "shock", "havens", "k", "history", "evidence", "caveats"):
            self.assertIn(key, rep)
        self.assertEqual(rep["rules_version"], RULES["version"])
        self.assertEqual(len(rep["havens"]), 7)
        self.assertEqual(len(rep["history"]), 7)
        gold_hist = next(h for h in rep["history"] if h["id"] == "gold")
        self.assertEqual(gold_hist["n"], 2)
        counted = sum(gold_hist[label] for label in ("clear_up", "lean_up", "normal", "lean_down", "clear_down"))
        self.assertEqual(counted, gold_hist["n"])
        self.assertIsNotNone(gold_hist["median"])
        shock = next(s for s in rep["shock"] if s["id"] == "brent")
        self.assertIn("brent", [s["id"] for s in rep["shock"]])
        self.assertIsNotNone(shock["zh"])

    def _crash_report(self, gold_log_ret: float, silver_log_ret: float | None = None):
        payload = general.general_payload(_crash_series(gold_log_ret, silver_log_ret))
        decoded = report_v3.decode_series(payload)
        return report_v3.build_report(decoded, RULES, EVENTS, EVENT_DATE, "spx", "preset", "test_event")

    def test_down_tail_single_clear_down(self):
        rep = self._crash_report(np.log(0.70))
        self.assertEqual(rep["bench"]["state"], "clear_drop")
        down = [h["id"] for h in rep["havens"] if h["by_h"]["30"]["label"] == "clear_down"]
        self.assertEqual(down, ["gold"])
        self.assertTrue(rep["headline"]["zh"].endswith("黄金也明显下跌，没有起到避险作用。"))
        self.assertTrue(rep["headline"]["en"].endswith("Gold also fell clearly and did not act as a safe haven."))

    def test_down_tail_many_clear_down(self):
        rep = self._crash_report(np.log(0.70), np.log(0.80))
        down = [h["id"] for h in rep["havens"] if h["by_h"]["30"]["label"] == "clear_down"]
        self.assertEqual(down, ["gold", "silver"])
        self.assertTrue(rep["headline"]["zh"].endswith("黄金、白银也明显下跌，没有起到避险作用。"))
        self.assertTrue(rep["headline"]["en"].endswith("Gold and Silver also fell clearly and did not act as safe havens."))

    def test_rank_phrase_direction(self):
        # boundary through the helper: p < 0.5 weaker, p >= 0.5 stronger
        self.assertIn("weaker than", report_v3._rank_text(0.4999, "en", RULES))
        self.assertIn("stronger than", report_v3._rank_text(0.5, "en", RULES))
        self.assertIn("弱于历史上", report_v3._rank_text(0.3, "zh", RULES))
        self.assertIn("强于历史上", report_v3._rank_text(0.9, "zh", RULES))
        # integration: bench/shock sentences follow their own pct
        saw = {"weaker": False, "stronger": False}
        for date, kind in ((EVENT_DATE, "custom"), ("2015-03-10", "custom"), ("2019-08-15", "custom"), ("2020-06-15", "custom")):
            rep = self.report(date, kind=kind)
            for row, key in ((rep["bench"], "bench"), (rep["shock"][0], "shock")):
                if row["zh"] is None or row["pct"] is None:
                    continue
                if row["pct"] < 0.5:
                    self.assertIn("weaker than", row["en"], key)
                    self.assertIn("弱于历史上", row["zh"], key)
                    saw["weaker"] = True
                else:
                    self.assertIn("stronger than", row["en"], key)
                    self.assertIn("强于历史上", row["zh"], key)
                    saw["stronger"] = True
        self.assertTrue(saw["weaker"] and saw["stronger"])

    def test_latest_uses_pressure_latest_template(self):
        rep = report_v3.build_report(self.decoded, RULES, EVENTS, None, "spx", "latest")
        self.assertIn("over the last 30 days", rep["pressure"]["en"])
        self.assertIn("最近 30 天", rep["pressure"]["zh"])
        rep_custom = self.report(EVENT_DATE, kind="custom")
        self.assertIn("over the 30 days after the date", rep_custom["pressure"]["en"])
        self.assertIn("事件后 30 天", rep_custom["pressure"]["zh"])

    def test_multi_caveat_uses_top_threshold(self):
        rep = self.report(EVENT_DATE, kind="preset", exclude="test_event")
        multi = next(c for c in rep["caveats"] if c["code"] == "multi")
        self.assertIn("2.9", multi["zh"])
        self.assertIn("2.9", multi["en"])
        self.assertNotIn("97.1", multi["en"])
        self.assertNotIn("97.1", multi["zh"])


if __name__ == "__main__":
    unittest.main()
