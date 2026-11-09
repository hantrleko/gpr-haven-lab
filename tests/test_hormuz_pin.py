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
        self.assertLess(abs(gold - (-15.79)), 0.05)


if __name__ == "__main__":
    unittest.main()
