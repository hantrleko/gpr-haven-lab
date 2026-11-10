"""Exhaustive specification curve for the event-window haven score.

324 specs = 3 windows x 2 bases x 3 session lengths x 3 weight rules
x 3 GPR definitions x 2 null models. The impulse response is not in this
grid. Base and session length change the picture, not the monthly score;
those repeated estimates stay in the curve on purpose.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

WIDTHS = (6, 12, 24)
BASES = ("event", "pre")
SESSIONS = (20, 40, 60)
WEIGHTS = ("equal", "pc1", "envelope")
GPR = ("total", "act", "threat")
NULLS = ("bootstrap", "blocked")
GPR_COLUMN = {"total": "dgpr", "act": "dgpr_act", "threat": "dgpr_threat"}


def specification_grid() -> list[dict]:
    rows = []
    for width in WIDTHS:
        for base in BASES:
            for sessions in SESSIONS:
                for weights in WEIGHTS:
                    for gpr in GPR:
                        for null in NULLS:
                            rows.append(
                                {
                                    "w": width,
                                    "base": base,
                                    "sessions": sessions,
                                    "weights": weights,
                                    "gpr": gpr,
                                    "null": null,
                                }
                            )
    return rows


def registry_hash(rows: list[dict] | None = None) -> str:
    payload = rows if rows is not None else specification_grid()
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _legs(block: pd.DataFrame, gpr_col: str) -> tuple[float, float, float] | None:
    from havenlab.engine import pearson

    if gpr_col not in block.columns:
        return None
    c_csi, _n1 = pearson(block["ret_gold"], block["ret_csi"], min_n=4)
    c_hsi, _n2 = pearson(block["ret_gold"], block["ret_hsi"], min_n=4)
    c_gpr, _n3 = pearson(block["ret_gold"], block[gpr_col], min_n=4)
    c_dxy, _n4 = pearson(block["ret_gold"], block["ret_dxy"], min_n=4)
    if None in (c_csi, c_hsi, c_gpr, c_dxy):
        return None
    equity = 50.0 * (1.0 - (c_csi + c_hsi) / 2.0)
    gpr_link = 50.0 * (1.0 + c_gpr)
    dollar = 50.0 * (1.0 - c_dxy)
    return equity, gpr_link, dollar


def _combine(legs: tuple[float, float, float], weights: str, loadings: np.ndarray | None) -> float:
    from havenlab.engine import _haven_weight_envelope

    equity, gpr_link, dollar = legs
    if weights == "envelope":
        bounds = _haven_weight_envelope(equity, gpr_link, dollar)
        if bounds is None:
            return (equity + gpr_link + dollar) / 3.0
        return (bounds[0] + bounds[1]) / 2.0
    if weights == "pc1" and loadings is not None:
        raw = float(loadings @ np.array(legs))
        scale = float(np.abs(loadings).sum()) or 1.0
        return raw / scale
    return (equity + gpr_link + dollar) / 3.0


def _pc1_loadings(panel: pd.DataFrame) -> np.ndarray | None:
    from havenlab.engine import pearson

    rows = []
    for i in range(35, len(panel)):
        block = panel.iloc[i - 35 : i + 1]
        found = _legs(block, "dgpr")
        if found is not None:
            rows.append(found)
    if len(rows) < 30:
        return None
    matrix = np.asarray(rows, dtype=float)
    matrix = (matrix - matrix.mean(axis=0)) / (matrix.std(axis=0, ddof=1) + 1e-8)
    _u, _s, vt = np.linalg.svd(matrix, full_matrices=False)
    loadings = np.abs(vt[0])
    return loadings / loadings.sum()


def _tail(pct: float | None, lo: float | None, hi: float | None, low: float, high: float) -> bool:
    if pct is None:
        return False
    left = pct if lo is None else lo
    right = pct if hi is None else hi
    return (left > 0 and right <= low) or (left >= high and right < 1)


def build_spec_curve(panel: pd.DataFrame, events: list[dict], placebo_v2: dict, car: dict, fast: bool = False) -> dict:
    rows = specification_grid()
    if fast:
        rows = rows[:: max(len(rows) // 60, 1)][:60]
    loadings = _pc1_loadings(panel)
    cache: dict[tuple, tuple[float, float, float] | None] = {}
    estimates: dict[str, list] = {event["id"]: [] for event in events}
    claims: dict[str, list] = {event["id"]: [] for event in events}
    for spec in rows:
        width = int(spec["w"])
        column = GPR_COLUMN[spec["gpr"]]
        null = placebo_v2.get(str(width), {}).get("by_event", {})
        for event in events:
            month = str(event.get("month") or pd.Timestamp(event["date"]).to_period("M"))
            period = pd.Period(month, freq="M")
            if period not in panel.index:
                estimates[event["id"]].append(None)
                claims[event["id"]].append(0)
                continue
            loc = int(panel.index.get_loc(period))
            stop = min(len(panel), loc + width)
            key = (event["id"], width, column)
            if key not in cache:
                cache[key] = _legs(panel.iloc[loc:stop], column)
            found = cache[key]
            if found is None:
                estimates[event["id"]].append(None)
                claims[event["id"]].append(0)
                continue
            score = round(_combine(found, spec["weights"], loadings), 2)
            estimates[event["id"]].append(score)
            gold = float(panel["ret_gold"].iloc[loc:stop].sum())
            csi = float(panel["ret_csi"].iloc[loc:stop].sum())
            band = (null.get(event["id"]) or {}).get("gold") or {}
            blocked = band.get("blocked") or {}
            if spec["null"] == "blocked":
                pct, lo, hi = blocked.get("pct"), blocked.get("pct"), blocked.get("pct")
            else:
                pct, lo, hi = band.get("pct"), band.get("pct_lo"), band.get("pct_hi")
            q = (((car.get("by_event") or {}).get(event["id"]) or {}).get("gold") or {}).get("m1_p5", {}).get("q")
            gate = gold > 0 and csi < 0 and _tail(pct, lo, hi, 0.20, 0.80) and (q is None or float(q) <= 0.10)
            claims[event["id"]].append(1 if gate else 0)
    by_event = {}
    for event_id, values in estimates.items():
        finite = [float(item) for item in values if item is not None]
        ordered = sorted(finite)
        flags = claims[event_id]
        share_pos = None if not finite else round(float(np.mean(np.asarray(finite) > 0)), 4)
        share_gate = None if not flags else round(float(np.mean(flags)), 4)
        median = None if not ordered else round(float(np.median(ordered)), 2)
        q25 = None if not ordered else round(float(np.percentile(ordered, 25)), 2)
        q75 = None if not ordered else round(float(np.percentile(ordered, 75)), 2)
        default_index = next(
            (
                i
                for i, spec in enumerate(rows)
                if spec["w"] == 12 and spec["base"] == "event" and spec["sessions"] == 40 and spec["weights"] == "equal" and spec["gpr"] == "total" and spec["null"] == "bootstrap"
            ),
            None,
        )
        pctl = None
        if default_index is not None and values[default_index] is not None and ordered:
            pctl = round(float(np.mean(np.asarray(ordered) <= values[default_index])), 4)
        by_event[event_id] = {
            "metric": "haven_v1",
            "estimates": values,
            "claim": flags,
            "median": median,
            "iqr": [q25, q75],
            "share_positive": share_pos,
            "share_claim_gate": share_gate,
            "pctl_of_default": pctl,
        }
    return {
        "n_specs": len(rows),
        "registry_hash": registry_hash(rows),
        "full_grid": 324,
        "fast": bool(fast),
        "dims": {"w": list(WIDTHS), "base": list(BASES), "sessions": list(SESSIONS), "weights": list(WEIGHTS), "gpr": list(GPR), "null": list(NULLS)},
        "specs": rows,
        "by_event": by_event,
        "gate_sensitivity": _gate_table(panel, events, placebo_v2, car),
    }


def _gate_table(panel: pd.DataFrame, events: list[dict], placebo_v2: dict, car: dict) -> list[dict]:
    """How many events pass the gold-up / CSI-down gate as the tail cut moves."""
    out = []
    null = placebo_v2.get("12", {}).get("by_event", {})
    for low, high in ((0.15, 0.85), (0.20, 0.80), (0.25, 0.75)):
        passed = []
        for event in events:
            month = str(event.get("month") or pd.Timestamp(event["date"]).to_period("M"))
            period = pd.Period(month, freq="M")
            if period not in panel.index:
                continue
            loc = int(panel.index.get_loc(period))
            stop = min(len(panel), loc + 12)
            gold = float(panel["ret_gold"].iloc[loc:stop].sum())
            csi = float(panel["ret_csi"].iloc[loc:stop].sum())
            band = (null.get(event["id"]) or {}).get("gold") or {}
            q = (((car.get("by_event") or {}).get(event["id"]) or {}).get("gold") or {}).get("m1_p5", {}).get("q")
            if gold > 0 and csi < 0 and _tail(band.get("pct"), band.get("pct_lo"), band.get("pct_hi"), low, high) and (q is None or float(q) <= 0.10):
                passed.append(event["id"])
        out.append({"low": low, "high": high, "n_pass": len(passed), "events": passed})
    return out
