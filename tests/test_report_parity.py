"""Python/JS parity for the v3 report engine (tests/report_parity.mjs)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import havenlab.engine as engine
from havenlab import general, report_v3
from tests.test_report_v3 import EVENTS as SYNTH_EVENTS
from tests.test_report_v3 import RULES, _synthetic_series

ROOT = Path(__file__).resolve().parents[1]
REAL_SERIES = ROOT / "docs" / "v3" / "series.json"
NRULES = json.loads((ROOT / "src" / "havenlab" / "rules" / "narratives_v3.json").read_text(encoding="utf-8"))

# Custom-tool parity inputs, valid inside both the synthetic panel (2006-2020)
# and the real one. Bench "csi" exercises the null-summary path, bench "spx"
# the filled-summary path.
CUSTOM_SPECS = [
    {"dates": ["2015-03-10", "2018-06-01", "2016-06-24", "2019-08-15", "2020-01-03"], "asset_ids": ["gold", "btc", "brent"], "bench_id": "spx"},
    {"dates": ["2010-03-01", "2014-03-18", "2017-09-03"], "asset_ids": ["silver", "ust"], "bench_id": "csi"},
]


def _real_events() -> list[dict]:
    from havenlab.events import EVENTS

    return [{"id": e["id"], "date": e["date"], "name": e["name"], "name_en": e["name_en"]} for e in EVENTS]


class _Compare:
    def __init__(self, case: unittest.TestCase):
        self.case = case

    def check(self, py, js, path="$"):
        case = self.case
        if isinstance(py, bool) or isinstance(js, bool):
            case.assertIs(py, js, path)
            return
        if py is None or js is None:
            case.assertIs(py, js, path)
            return
        if isinstance(py, str) or isinstance(js, str):
            case.assertEqual(py, js, path)
            return
        if isinstance(py, (int, float)) and isinstance(js, (int, float)):
            case.assertAlmostEqual(float(py), float(js), delta=1e-9, msg=path)
            return
        if isinstance(py, list) and isinstance(js, list):
            case.assertEqual(len(py), len(js), path)
            for i, (a, b) in enumerate(zip(py, js)):
                self.check(a, b, f"{path}[{i}]")
            return
        if isinstance(py, dict) and isinstance(js, dict):
            case.assertEqual(set(py.keys()), set(js.keys()), path)
            for key in py:
                self.check(py[key], js[key], f"{path}.{key}")
            return
        case.fail(f"{path}: type mismatch {type(py).__name__} vs {type(js).__name__}")


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class ReportParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_asof = engine.ASOF
        engine.ASOF = pd.Timestamp("2020-12-31")
        cls.payload = general.general_payload(_synthetic_series())
        cls.node = shutil.which("node")

    @classmethod
    def tearDownClass(cls):
        engine.ASOF = cls._old_asof

    def _parity(self, payload: dict, events: list[dict]):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            series_path = tmp / "series.json"
            rules_path = tmp / "rules.json"
            events_path = tmp / "events.json"
            nrules_path = tmp / "narrative_rules.json"
            custom_path = tmp / "custom.json"
            out_path = tmp / "out.json"
            series_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            rules_path.write_text(json.dumps(RULES, ensure_ascii=False), encoding="utf-8")
            events_path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
            nrules_path.write_text(json.dumps(NRULES, ensure_ascii=False), encoding="utf-8")
            custom_path.write_text(json.dumps(CUSTOM_SPECS, ensure_ascii=False), encoding="utf-8")
            ctx = report_v3._Ctx(report_v3.decode_series(payload), RULES)
            ctx.narrative_rules = NRULES
            expected = {
                "reports": report_v3.build_all_reports(payload, RULES, events),
                "narratives": report_v3.build_all_narratives(payload, RULES, NRULES, events),
                "custom": [
                    report_v3.build_custom_narrative(ctx, spec["dates"], spec["asset_ids"], spec["bench_id"])
                    for spec in CUSTOM_SPECS
                ],
            }
            subprocess.run(
                [
                    self.node,
                    "tests/report_parity.mjs",
                    str(series_path),
                    str(rules_path),
                    str(events_path),
                    str(nrules_path),
                    str(custom_path),
                    str(out_path),
                ],
                check=True,
                cwd=ROOT,
            )
            actual = json.loads(out_path.read_text(encoding="utf-8"))
        _Compare(self).check(expected, actual)

    def test_synthetic_payload_parity(self):
        self._parity(self.payload, SYNTH_EVENTS)

    @unittest.skipUnless(REAL_SERIES.exists(), "docs/v3/series.json not built yet")
    def test_real_series_parity(self):
        payload = json.loads(REAL_SERIES.read_text(encoding="utf-8"))
        self._parity(payload, _real_events())


if __name__ == "__main__":
    unittest.main()
