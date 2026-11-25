"""Narrative verdict layer boundary tests on hand-crafted synthetic ctx.

The series are daily, flat at 100 except at window endpoints, so the sign of
every horizon return is controlled exactly. Events are spaced 150 days apart,
wider than the longest horizon (91), so no endpoints collide.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from havenlab import report_v3

ROOT = Path(__file__).resolve().parents[1]
RULES = json.loads((ROOT / "src" / "havenlab" / "rules" / "rules_v3.json").read_text(encoding="utf-8"))
NRULES = json.loads((ROOT / "src" / "havenlab" / "rules" / "narratives_v3.json").read_text(encoding="utf-8"))

EVENTS = [
    {"id": "e1", "date": "2010-03-01"},
    {"id": "e2", "date": "2010-07-29"},
    {"id": "e3", "date": "2010-12-26"},
    {"id": "e4", "date": "2011-05-25"},
    {"id": "e5", "date": "2011-10-22"},
]


def _daily_days(start: str, end: str) -> list[int]:
    d0 = report_v3._parse_day(start)
    d1 = report_v3._parse_day(end)
    return list(range(d0, d1 + 1))


def _endpoint_series(event_dates: list[str], endpoint_vals, start="2009-11-01", end="2013-06-30") -> dict:
    """Daily series, value 100 everywhere except window endpoints.

    endpoint_vals: one dict per event mapping horizon (7/30/91) to the value
    at that horizon's window end. The window start is always 100, so 105 is a
    positive return, 95 negative, 100 exactly flat.
    """
    days = _daily_days(start, end)
    vals = [100.0] * len(days)
    index = {d: i for i, d in enumerate(days)}
    for date_str, per_h in zip(event_dates, endpoint_vals):
        s = report_v3._parse_day(date_str) - 1  # daily series: last close strictly before the event
        for h, target in per_h.items():
            if s + h in index:  # endpoints past the series end simply do not exist
                vals[index[s + h]] = target
    return {"days": days, "values": vals}


def _ctx(series_map: dict) -> report_v3._Ctx:
    decoded = {"assets": {aid: {"name_zh": aid, "name_en": aid} for aid in series_map}, "series": series_map}
    ctx = report_v3._Ctx(decoded, RULES)
    ctx.narrative_rules = NRULES
    return ctx


def _events(n: int) -> list:
    return EVENTS[:n]


def _dates(n: int) -> list[str]:
    return [e["date"] for e in EVENTS[:n]]


def _down_ctx(n: int, asset_targets: list, bench_target: float = 90.0) -> report_v3._Ctx:
    """n events, benchmark drops at every one, asset endpoints as given ({30: v} per event)."""
    dates = _dates(n)
    bench = _endpoint_series(dates, [{30: bench_target}] * n)
    asset = _endpoint_series(dates, asset_targets)
    return _ctx({"spx": bench, "gold": asset})


class VerdictBoundaryTest(unittest.TestCase):
    def aggregate(self, ctx, n, kind="haven", asset="gold", bench="spx"):
        return report_v3._aggregate_narrative(ctx, _events(n), asset, bench, kind, NRULES)

    def test_mostly_holds_boundary_three_of_four(self):
        ctx = _down_ctx(4, [{30: 105.0}, {30: 105.0}, {30: 105.0}, {30: 95.0}])
        agg = self.aggregate(ctx, 4)
        self.assertEqual(agg["n_valid"], 4)
        self.assertEqual(agg["n_pos"], 3)
        # 3 * 3 >= 2 * 4 exactly at the boundary
        self.assertEqual(agg["verdict"], "mostly_holds")

    def test_mixed_boundary_two_of_four(self):
        ctx = _down_ctx(4, [{30: 105.0}, {30: 105.0}, {30: 95.0}, {30: 95.0}])
        agg = self.aggregate(ctx, 4)
        self.assertEqual(agg["n_valid"], 4)
        self.assertEqual(agg["n_pos"], 2)
        # 2 * 3 = 6: neither >= 8 nor <= 4
        self.assertEqual(agg["verdict"], "mixed")

    def test_mostly_fails_boundary_one_of_four(self):
        ctx = _down_ctx(4, [{30: 105.0}, {30: 95.0}, {30: 95.0}, {30: 95.0}])
        agg = self.aggregate(ctx, 4)
        self.assertEqual(agg["n_valid"], 4)
        self.assertEqual(agg["n_pos"], 1)
        # 1 * 3 = 3 <= 4 exactly at the boundary
        self.assertEqual(agg["verdict"], "mostly_fails")

    def test_flat_window_is_not_positive(self):
        ctx = _down_ctx(4, [{30: 105.0}, {30: 95.0}, {30: 95.0}, {30: 100.0}])
        agg = self.aggregate(ctx, 4)
        flat_row = agg["rows"][3]
        self.assertEqual(flat_row["ret"], 0.0)
        self.assertEqual(agg["n_pos"], 1)
        self.assertEqual(agg["verdict"], "mostly_fails")

    def test_untestable_below_min_tests_any_split(self):
        # 3 of 3 positive would be mostly_holds, but n_valid = 3 < min_tests = 4
        ctx = _down_ctx(3, [{30: 105.0}] * 3)
        agg = self.aggregate(ctx, 3)
        self.assertEqual(agg["n_valid"], 3)
        self.assertEqual(agg["n_pos"], 3)
        self.assertEqual(agg["verdict"], "untestable")
        ctx_zero = _down_ctx(3, [{30: 95.0}] * 3)
        agg_zero = self.aggregate(ctx_zero, 3)
        self.assertEqual(agg_zero["n_pos"], 0)
        self.assertEqual(agg_zero["verdict"], "untestable")

    def test_transmission_counts_bench_up_events_as_valid(self):
        dates = _dates(4)
        bench_up = _endpoint_series(dates, [{30: 110.0}] * 4)
        asset = _endpoint_series(dates, [{30: 105.0}, {30: 95.0}, {30: 105.0}, {30: 95.0}])
        ctx = _ctx({"spx": bench_up, "gold": asset})
        trans = self.aggregate(ctx, 4, kind="transmission")
        self.assertEqual(trans["n_valid"], 4)
        self.assertEqual(trans["n_not_test"], 0)
        self.assertEqual(trans["n_pos"], 2)
        self.assertEqual(trans["verdict"], "mixed")
        self.assertTrue(all(row["status"] == "valid" for row in trans["rows"]))
        # the same data under haven rules is not a test at all
        haven = self.aggregate(ctx, 4, kind="haven")
        self.assertEqual(haven["n_valid"], 0)
        self.assertEqual(haven["n_not_test"], 4)
        self.assertEqual(haven["verdict"], "untestable")
        self.assertTrue(all(row["status"] == "not_a_test" for row in haven["rows"]))

    def test_flat_benchmark_is_not_a_test(self):
        dates = _dates(4)
        bench_flat = _endpoint_series(dates, [{30: 100.0}] * 4)
        asset = _endpoint_series(dates, [{30: 105.0}] * 4)
        ctx = _ctx({"spx": bench_flat, "gold": asset})
        agg = self.aggregate(ctx, 4)
        for row in agg["rows"]:
            self.assertEqual(row["bench_ret"], 0.0)
            self.assertEqual(row["status"], "not_a_test")
        self.assertEqual(agg["n_valid"], 0)

    def test_bench_up_skips_asset_check_so_missing_asset_is_not_counted(self):
        # asset series starts after e1: with the benchmark up at e1 the asset
        # is never consulted, so the row is not_a_test rather than missing.
        dates = _dates(4)
        bench_up = _endpoint_series(dates, [{30: 110.0}] * 4)
        asset = _endpoint_series(dates, [{30: 105.0}] * 4, start="2010-04-01")
        ctx = _ctx({"spx": bench_up, "gold": asset})
        agg = self.aggregate(ctx, 4)
        self.assertEqual(agg["rows"][0]["status"], "not_a_test")
        self.assertEqual(agg["n_missing"], 0)
        self.assertEqual(agg["n_not_test"], 4)

    def test_missing_and_incomplete_combine_into_n_missing(self):
        dates = _dates(5)
        bench = _endpoint_series(dates, [{30: 90.0}] * 5)
        # asset starts after e1 (-> missing at e1) and ends after e3 but before
        # the horizon-30 end of e4/e5. Asset-side missing and incomplete both
        # map to row status "missing"; only bench problems give "incomplete".
        asset = _endpoint_series(dates, [{}] * 5, start="2010-04-01", end="2011-06-10")
        ctx = _ctx({"spx": bench, "gold": asset})
        agg = self.aggregate(ctx, 5)
        statuses = [row["status"] for row in agg["rows"]]
        self.assertEqual(statuses, ["missing", "valid", "valid", "missing", "missing"])
        self.assertEqual(agg["n_valid"], 2)
        self.assertEqual(agg["n_missing"], 3)
        self.assertEqual(agg["n_not_test"], 0)
        self.assertEqual(agg["verdict"], "untestable")
        # rows that are not valid carry no asset return; bench_ret is present
        # whenever the benchmark window completed
        for row in agg["rows"]:
            if row["status"] == "valid":
                self.assertIsNotNone(row["ret"])
            else:
                self.assertIsNone(row["ret"])
            self.assertIsNotNone(row["bench_ret"])

    def test_bench_incomplete_rows_excluded_and_counted_in_n_missing(self):
        dates = _dates(5)
        # benchmark ends after e3's horizon-30 end but before e4's: e4 and e5
        # cannot be tested at all, whatever the asset does.
        bench = _endpoint_series(dates, [{30: 90.0}] * 5, end="2011-06-10")
        asset = _endpoint_series(dates, [{30: 105.0}] * 5)
        ctx = _ctx({"spx": bench, "gold": asset})
        agg = self.aggregate(ctx, 5)
        statuses = [row["status"] for row in agg["rows"]]
        self.assertEqual(statuses, ["valid", "valid", "valid", "incomplete", "incomplete"])
        self.assertEqual(agg["n_valid"], 3)
        self.assertEqual(agg["n_missing"], 2)
        self.assertEqual(agg["verdict"], "untestable")  # 3 < min_tests even though 3/3 positive
        # the horizon-30 benchmark return is not computable for incomplete rows
        self.assertIsNone(agg["rows"][3]["bench_ret"])
        self.assertIsNone(agg["rows"][4]["bench_ret"])
        self.assertIsNotNone(agg["rows"][0]["bench_ret"])

    def test_median_odd_picks_sorted_middle_exactly(self):
        # magnitudes ordered so that sorted order is not event order;
        # log is monotonic, so the median must be e1's return (target 103)
        ctx = _down_ctx(5, [{30: 103.0}, {30: 101.0}, {30: 105.0}, {30: 102.0}, {30: 104.0}])
        agg = self.aggregate(ctx, 5)
        rows = agg["rows"]
        median = agg["median"]
        self.assertEqual(median, rows[0]["ret"])  # e1, the sorted middle
        rets = sorted(row["ret"] for row in rows)
        self.assertEqual(median, rets[2])
        self.assertNotEqual(median, rows[2]["ret"])  # event order would give e3

    def test_median_even_averages_sorted_middle_pair_exactly(self):
        ctx = _down_ctx(4, [{30: 104.0}, {30: 101.0}, {30: 103.0}, {30: 102.0}])
        agg = self.aggregate(ctx, 4)
        rows = agg["rows"]
        # sorted by magnitude: e2 (101) < e4 (102) < e3 (103) < e1 (104)
        expected = (rows[3]["ret"] + rows[2]["ret"]) / 2.0
        self.assertEqual(agg["median"], expected)
        rets = sorted(row["ret"] for row in rows)
        self.assertEqual(agg["median"], (rets[1] + rets[2]) / 2.0)

    def test_median_none_when_no_valid_rows(self):
        dates = _dates(4)
        bench_up = _endpoint_series(dates, [{30: 110.0}] * 4)
        asset = _endpoint_series(dates, [{30: 105.0}] * 4)
        ctx = _ctx({"spx": bench_up, "gold": asset})
        agg = self.aggregate(ctx, 4)
        self.assertIsNone(agg["median"])

    def test_secondary_horizons_count_only_complete_positive_valid_rows(self):
        dates = _dates(5)
        bench = _endpoint_series(dates, [{30: 90.0}] * 5)
        # asset ends after e5's 30-day end (2011-11-20) but before its 91-day
        # end (2012-01-19): e5 is valid, its 91-day window incomplete.
        targets = [{7: 105.0, 30: 105.0, 91: 105.0}] * 5
        asset = _endpoint_series(dates, targets, end="2011-12-15")
        ctx = _ctx({"spx": bench, "gold": asset})
        agg = self.aggregate(ctx, 5)
        self.assertEqual(agg["n_valid"], 5)
        self.assertEqual(agg["n_pos"], 5)
        self.assertEqual(agg["n_pos7"], 5)  # e5's 7-day end precedes the truncation
        self.assertEqual(agg["n_pos91"], 4)  # e5's 91-day window incomplete -> non-positive

    def test_custom_dates_and_bench_summaries(self):
        ctx = _down_ctx(4, [{30: 105.0}] * 4)
        out = report_v3.build_custom_narrative(ctx, _dates(4), ["gold"], "spx")
        self.assertEqual(len(out), 1)
        entry = out[0]
        self.assertIsNone(entry["id"])
        self.assertIsNone(entry["zh"])
        self.assertIsNone(entry["en"])
        self.assertEqual(entry["kind"], "haven")
        self.assertEqual(entry["verdict"], "mostly_holds")
        self.assertIsNotNone(entry["summary_zh"])
        self.assertIsNotNone(entry["summary_en"])
        for row in entry["rows"]:
            self.assertIsNone(row["event"])
        # the fixed templates name the narrative-layer benchmark, so a
        # non-spx benchmark leaves the summaries null
        ctx_csi = _ctx({**ctx.series, "csi": ctx.series["spx"]})
        out_csi = report_v3.build_custom_narrative(ctx_csi, _dates(4), ["gold"], "csi")
        self.assertIsNone(out_csi[0]["summary_zh"])
        self.assertIsNone(out_csi[0]["summary_en"])

    def test_custom_requires_narrative_rules_on_ctx(self):
        decoded = {"assets": {}, "series": {}}
        ctx = report_v3._Ctx(decoded, RULES)
        with self.assertRaises(ValueError):
            report_v3.build_custom_narrative(ctx, ["2010-03-01"], ["gold"], "spx")

    def test_row_schema_exact_keys(self):
        ctx = _down_ctx(4, [{30: 105.0}] * 4)
        agg = self.aggregate(ctx, 4)
        for row in agg["rows"]:
            self.assertEqual(set(row.keys()), {"event", "date", "status", "ret", "bench_ret"})


if __name__ == "__main__":
    unittest.main()
