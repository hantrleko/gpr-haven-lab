"""Daily series for the v3 general payload.

Full builds load data/raw, write replication/assets_daily.csv, reload it, and
publish docs/v3/. --from-derived builds read that CSV only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from havenlab import engine
from havenlab.assets import ASSETS_GENERAL, GPR_ASSETS

SCHEMA = "3.0.0-p1"
PRICE_START = pd.Timestamp("2006-11-01")
DERIVED_NAME = "assets_daily.csv"
GPR_COLUMNS = {spec["id"]: spec["column"] for spec in GPR_ASSETS}
ASSET_IDS = {spec["id"] for spec in ASSETS_GENERAL}


def _series_csi_file(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["date"]).dt.normalize()
    price = pd.to_numeric(frame["close"], errors="coerce")
    out = pd.Series(price.to_numpy(), index=pd.DatetimeIndex(dates), name="csi")
    out = out[np.isfinite(out.to_numpy()) & (out.to_numpy() > 0)]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def _gpr_frame(raw: Path) -> pd.DataFrame:
    path = raw / "data_gpr_daily_recent.xls"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_excel(path, usecols=["date", "GPRD", "GPRD_ACT", "GPRD_THREAT"])
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ("GPRD", "GPRD_ACT", "GPRD_THREAT"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date"]).drop_duplicates("date", keep="last").set_index("date").sort_index()
    return frame


def _load_one(spec: dict, raw: Path) -> pd.Series | None:
    path = raw / spec["raw_file"]
    if not path.exists():
        return None
    if spec["id"] == "gold":
        spot, _source = engine._read_spot_file(path)
        return spot
    if spec["id"] == "csi":
        return _series_csi_file(path)
    return engine._series_from_yahoo(path)


def _round_prices(series: pd.Series) -> pd.Series:
    return series.map(lambda value: float(f"{value:.6g}"))


def _round_gpr(series: pd.Series) -> pd.Series:
    return series.round(2)


def _clean_window(series: pd.Series, asof: pd.Timestamp) -> pd.Series:
    series = series[(series.index >= PRICE_START) & (series.index <= asof)]
    series = series[np.isfinite(series.to_numpy()) & (series.to_numpy() > 0)]
    return series[~series.index.duplicated(keep="last")].sort_index()


def load_general_daily(raw_dir: Path | None = None) -> dict[str, pd.Series]:
    """One daily price series per registry asset, capped at engine.ASOF."""
    raw = Path(raw_dir) if raw_dir is not None else engine.RAW
    asof = pd.Timestamp(engine.ASOF).normalize()
    out: dict[str, pd.Series] = {}
    for spec in ASSETS_GENERAL:
        try:
            series = _load_one(spec, raw)
        except Exception:
            continue
        if series is None or series.empty:
            continue
        series = _clean_window(series, asof)
        if series.empty:
            continue
        if spec["invert"]:
            series = 1.0 / series
        series.name = spec["id"]
        out[spec["id"]] = _round_prices(series)
    try:
        frame = _gpr_frame(raw)
    except Exception:
        frame = pd.DataFrame()
    if not frame.empty:
        frame = frame[frame.index <= asof]
        for asset_id, column in GPR_COLUMNS.items():
            series = frame[column].dropna()
            series = series[np.isfinite(series.to_numpy())]
            if series.empty:
                continue
            series = series[~series.index.duplicated(keep="last")].sort_index()
            series.name = asset_id
            out[asset_id] = _round_gpr(series)
    return out


def write_derived_csv(series: dict[str, pd.Series], path: Path) -> None:
    frame = pd.DataFrame({key: values for key, values in series.items()}).sort_index()
    if isinstance(frame.index, pd.DatetimeIndex):
        frame.index = frame.index.normalize().strftime("%Y-%m-%d")
    frame.index.name = "date"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, float_format="%.6g")


def load_general_from_derived(path: Path) -> dict[str, pd.Series]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    out: dict[str, pd.Series] = {}
    for column in frame.columns:
        series = frame[column].dropna()
        if series.empty:
            continue
        out[column] = pd.Series(series.to_numpy(dtype=float), index=series.index, name=column)
    return out


def _payload_round(asset_id: str, values: np.ndarray) -> np.ndarray:
    if asset_id in GPR_COLUMNS:
        return np.round(values.astype(float), 2)
    return np.array([float(f"{value:.6g}") for value in values], dtype=float)


def general_payload(series: dict[str, pd.Series]) -> dict:
    built = pd.Timestamp(engine.ASOF).date().isoformat()
    assets_meta = []
    for spec in ASSETS_GENERAL:
        s = series.get(spec["id"])
        if s is None or s.empty:
            continue
        entry = {key: spec[key] for key in (
            "id", "name_zh", "name_en", "role", "source", "symbol", "invert", "kind", "note_zh", "note_en",
        )}
        entry["first"] = s.index[0].strftime("%Y-%m-%d")
        entry["last"] = s.index[-1].strftime("%Y-%m-%d")
        entry["n"] = int(len(s))
        assets_meta.append(entry)
    gpr_meta = []
    for spec in GPR_ASSETS:
        s = series.get(spec["id"])
        if s is None or s.empty:
            continue
        gpr_meta.append({
            "id": spec["id"],
            "name_zh": spec["name_zh"],
            "name_en": spec["name_en"],
            "first": s.index[0].strftime("%Y-%m-%d"),
            "last": s.index[-1].strftime("%Y-%m-%d"),
            "n": int(len(s)),
        })
    unavailable = [spec["id"] for spec in ASSETS_GENERAL if spec["id"] not in series or series[spec["id"]].empty]
    unavailable += [spec["id"] for spec in GPR_ASSETS if spec["id"] not in series or series[spec["id"]].empty]
    payload_series = {}
    for asset_id in sorted(series):
        s = series[asset_id].sort_index()
        if s.empty:
            continue
        dates = pd.DatetimeIndex(s.index).normalize()
        values = _payload_round(asset_id, s.to_numpy(dtype=float))
        dt = [0] + [int((dates[i] - dates[i - 1]).days) for i in range(1, len(dates))]
        payload_series[asset_id] = {
            "t0": dates[0].strftime("%Y-%m-%d"),
            "dt": dt,
            "v": [float(value) for value in values],
        }
    return {
        "meta": {
            "schema": SCHEMA,
            "built": built,
            "assets": assets_meta,
            "gpr": gpr_meta,
            "unavailable": unavailable,
        },
        "series": payload_series,
    }


def build_general(root: Path, from_derived: bool) -> None:
    derived = root / "replication" / DERIVED_NAME
    if from_derived:
        if not derived.exists():
            return
        series = load_general_from_derived(derived)
    else:
        series = load_general_daily()
        write_derived_csv(series, derived)
        series = load_general_from_derived(derived)
    payload = general_payload(series)
    docs_v3 = root / "docs" / "v3"
    docs_v3.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    raw = blob.encode("utf-8")
    (docs_v3 / "series.json").write_text(blob, encoding="utf-8")
    manifest = {
        "schema": SCHEMA,
        "built": payload["meta"]["built"],
        "files": {
            "series": {
                "path": "series.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
        },
    }
    (docs_v3 / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
