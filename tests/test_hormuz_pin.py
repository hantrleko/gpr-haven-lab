"""Pin the published Hormuz window without reading raw quotes."""

from __future__ import annotations

import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HormuzPinTest(unittest.TestCase):
    def test_six_month_gold_cum_stays_near_published_value(self):
        path = ROOT / "replication" / "event_window_summary.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        hit = [
            row for row in rows
            if row["event_id"] == "hormuz_2026" and row["window_months"] == "6"
        ]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["event_date"], "2026-03-02")
        gold = float(hit[0]["gold_cum"])
        self.assertLess(abs(gold - (-17.12)), 0.05)

    def test_hormuz_twelve_month_interval_and_gaza_width(self):
        path = ROOT / "replication" / "event_window_summary.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        hormuz = next(row for row in rows if row["event_id"] == "hormuz_2026" and row["window_months"] == "12")
        self.assertLess(abs(float(hormuz["haven_after"]) - 46.09), 0.5)
        self.assertLess(abs(float(hormuz["haven_after_se"]) - 8.15), 0.5)
        gaza6 = next(row for row in rows if row["event_id"] == "gaza_2023" and row["window_months"] == "6")
        gaza12 = next(row for row in rows if row["event_id"] == "gaza_2023" and row["window_months"] == "12")
        self.assertGreater(float(gaza6["haven_after_se"]), float(gaza12["haven_after_se"]))
        self.assertGreater(float(gaza6["haven_after_se"]), 12.0)


if __name__ == "__main__":
    unittest.main()
