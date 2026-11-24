"""Registry shape and the derived-CSV round trip for the v3 series."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from havenlab import engine, general
from havenlab.assets import ASSETS_GENERAL, GPR_ASSETS


class RegistryTest(unittest.TestCase):
    def test_ids_unique_fields_and_roles(self):
        ids = [spec["id"] for spec in ASSETS_GENERAL]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len({spec["raw_file"] for spec in ASSETS_GENERAL}), len(ASSETS_GENERAL))
        for spec in ASSETS_GENERAL:
            self.assertIn(spec["role"], {"haven", "risk", "shock"})
            for key in ("name_zh", "name_en", "source", "symbol", "kind", "note_zh", "note_en"):
                self.assertTrue(spec[key])

    def test_only_fx_assets_invert(self):
        inverted = {spec["id"] for spec in ASSETS_GENERAL if spec["invert"]}
        self.assertEqual(inverted, {"jpy", "chf"})

    def test_gpr_ids_kept_separate(self):
        self.assertEqual([spec["id"] for spec in GPR_ASSETS], ["gpr", "gpr_act", "gpr_threat"])
        for spec in GPR_ASSETS:
            self.assertNotIn("role", spec)
            self.assertNotIn("raw_file", spec)


class LoaderTest(unittest.TestCase):
    def setUp(self):
        self._asof = engine.ASOF
        engine.ASOF = pd.Timestamp("2031-03-04")

    def tearDown(self):
        engine.ASOF = self._asof

    @staticmethod
    def _yahoo_csv(path: Path, rows: list[tuple[str, float]]) -> None:
        frame = pd.DataFrame(
            {
                "datetime_utc": [f"{day} 00:00:00+0000" for day, _value in rows],
                "close": [value for _day, value in rows],
                "adjclose": [value for _day, value in rows],
            }
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    def test_jpy_loads_inverted_capped_and_floored(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            self._yahoo_csv(
                raw / "jpy.csv",
                [
                    ("2006-01-03", 120.0),
                    ("2031-01-02", 150.0),
                    ("2031-01-03", 100.0),
                    ("2031-03-05", 90.0),
                ],
            )
            series = general.load_general_daily(raw)
        self.assertIn("jpy", series)
        jpy = series["jpy"]
        self.assertEqual([stamp.strftime("%Y-%m-%d") for stamp in jpy.index], ["2031-01-02", "2031-01-03"])
        self.assertAlmostEqual(jpy.iloc[0], 1.0 / 150.0)
        self.assertAlmostEqual(jpy.iloc[1], 1.0 / 100.0)

    def test_missing_files_land_in_unavailable_without_error(self):
        payload = general.general_payload({})
        self.assertEqual(payload["series"], {})
        self.assertEqual(
            set(payload["meta"]["unavailable"]),
            {spec["id"] for spec in ASSETS_GENERAL} | {spec["id"] for spec in GPR_ASSETS},
        )


class RoundTripTest(unittest.TestCase):
    def setUp(self):
        self._asof = engine.ASOF
        engine.ASOF = pd.Timestamp("2031-03-04")

    def tearDown(self):
        engine.ASOF = self._asof

    def test_csv_round_trip_and_delta_decode(self):
        index = pd.DatetimeIndex(["2031-01-02", "2031-01-03", "2031-01-06", "2031-01-07", "2031-01-10"])
        series = {
            "jpy": pd.Series([0.0066667, 0.01, 0.0099999, 0.0111111, 0.0123456], index=index, name="jpy"),
            "gpr": pd.Series([100.0, 101.256, 99.5, 100.749, 98.0], index=index, name="gpr"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "assets_daily.csv"
            general.write_derived_csv(series, csv_path)
            reloaded = general.load_general_from_derived(csv_path)
            payload_a = general.general_payload(series)
            payload_b = general.general_payload(reloaded)
        self.assertEqual(payload_a, payload_b)
        self.assertEqual(payload_a["meta"]["built"], "2031-03-04")
        for asset_id, encoded in payload_a["series"].items():
            offsets = np.cumsum([int(step) for step in encoded["dt"]])
            dates = [pd.Timestamp(encoded["t0"]) + pd.Timedelta(days=int(offset)) for offset in offsets]
            self.assertEqual([stamp.strftime("%Y-%m-%d") for stamp in dates], [stamp.strftime("%Y-%m-%d") for stamp in index])
            expected = series[asset_id].to_numpy(dtype=float)
            if asset_id in {spec["id"] for spec in GPR_ASSETS}:
                expected = np.round(expected, 2)
            else:
                expected = np.array([float(f"{value:.6g}") for value in expected])
            self.assertTrue(np.allclose(encoded["v"], expected, rtol=0, atol=1e-12))


if __name__ == "__main__":
    unittest.main()
