"""Stationary bootstrap null for event-window statistics.

The leave-one-event-window pool is kept only as a robustness column. The
published percentile is the share of Politis-Romano resamples at or below the
observed window statistic. Every column uses the same time index, so
cross-sectional correlation is left intact.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

NULL_SEED = 20261110
NULL_REPS = 2000
NULL_REPS_FAST = 200
_Z90 = 1.6448536269514722


def stationary_indices(n_obs: int, length: int, reps: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano indices, shape (reps, length), circular."""
    if n_obs < 4 or length < 1 or reps < 1:
        raise ValueError("bootstrap sample is too small")
    probability = 1.0 / float(max(int(block), 1))
    index = np.empty((reps, length), dtype=np.int32)
    index[:, 0] = rng.integers(0, n_obs, size=reps)
    restart = rng.random((reps, length)) < probability
    fresh = rng.integers(0, n_obs, size=(reps, length))
    for step in range(1, length):
        continued = (index[:, step - 1] + 1) % n_obs
        index[:, step] = np.where(restart[:, step], fresh[:, step], continued)
    return index


def _row_corr(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    left = left - left.mean(axis=1, keepdims=True)
    right = right - right.mean(axis=1, keepdims=True)
    denom = np.sqrt((left * left).sum(axis=1) * (right * right).sum(axis=1))
    out = np.full(left.shape[0], np.nan)
    ok = denom > 1e-12
    out[ok] = (left[ok] * right[ok]).sum(axis=1) / denom[ok]
    return out


def _haven_score(gold, csi, hsi, dxy, dgpr) -> np.ndarray:
    c_csi = _row_corr(gold, csi)
    c_hsi = _row_corr(gold, hsi)
    c_gpr = _row_corr(gold, dgpr)
    c_dxy = _row_corr(gold, dxy)
    equity = 50.0 * (1.0 - (c_csi + c_hsi) / 2.0)
    gpr_link = 50.0 * (1.0 + c_gpr)
    dollar = 50.0 * (1.0 - c_dxy)
    return (equity + gpr_link + dollar) / 3.0


def _percentile(draws: np.ndarray, value: float) -> dict:
    finite = draws[np.isfinite(draws)]
    if finite.size == 0 or not np.isfinite(value):
        return {"value": None, "pct": None, "pct_lo": None, "pct_hi": None, "se": None, "n_reps": 0}
    pct = float(np.mean(finite <= value))
    se = math.sqrt(max(pct * (1.0 - pct), 0.0) / float(finite.size))
    return {
        "value": round(float(value), 4),
        "pct": round(pct, 4),
        "pct_lo": round(max(0.0, pct - _Z90 * se), 4),
        "pct_hi": round(min(1.0, pct + _Z90 * se), 4),
        "se": round(se, 4),
        "n_reps": int(finite.size),
    }


def _histogram(draws: np.ndarray, bins: int = 24) -> dict:
    finite = draws[np.isfinite(draws)]
    if finite.size == 0:
        return {"edges": [], "counts": []}
    counts, edges = np.histogram(finite, bins=bins)
    return {"edges": [round(float(item), 4) for item in edges], "counts": [int(item) for item in counts]}


def _event_positions(panel: pd.DataFrame, events: list[dict]) -> list[tuple[str, int]]:
    located = []
    for event in events:
        month = str(event.get("month") or pd.Timestamp(event["date"]).to_period("M"))
        period = pd.Period(month, freq="M")
        if period not in panel.index:
            continue
        located.append((event["id"], int(panel.index.get_loc(period))))
    return located


def _observed(panel: pd.DataFrame, start: int, width: int) -> dict | None:
    stop = start + width
    if stop > len(panel):
        return None
    block = panel.iloc[start:stop]
    gold = block["ret_gold"].to_numpy(dtype=float)
    csi = block["ret_csi"].to_numpy(dtype=float)
    if not (np.isfinite(gold).all() and np.isfinite(csi).all()) or gold.size < width:
        return None
    hsi = block["ret_hsi"].to_numpy(dtype=float)
    dxy = block["ret_dxy"].to_numpy(dtype=float)
    dgpr = block["dgpr"].to_numpy(dtype=float)
    stacked = np.column_stack([gold, csi, hsi, dxy, dgpr])[None, :, :]
    score = _haven_score(stacked[:, :, 0], stacked[:, :, 1], stacked[:, :, 2], stacked[:, :, 3], stacked[:, :, 4])
    return {
        "gold": float(gold.sum()),
        "gold_excess_csi": float(gold.sum() - csi.sum()),
        "haven": None if not np.isfinite(score[0]) else float(score[0]),
    }


def _blocked_percentile(panel: pd.DataFrame, events: list[dict], width: int, value: float) -> dict:
    banned = {pos for _event_id, pos in _event_positions(panel, events)}
    pool = []
    for start in range(0, len(panel) - width + 1, width):
        if any(step in banned for step in range(start, start + width)):
            continue
        observed = _observed(panel, start, width)
        if observed is None:
            continue
        pool.append(observed["gold"])
    if not pool or not np.isfinite(value):
        return {"pct": None, "n": len(pool)}
    pct = float(np.mean(np.asarray(pool, dtype=float) <= value))
    return {"pct": round(pct, 4), "n": len(pool)}


def stationary_bootstrap_placebo(
    panel: pd.DataFrame,
    events: list[dict],
    width: int,
    reps: int = NULL_REPS,
    seed: int = NULL_SEED,
    expected_block: int | None = None,
) -> dict:
    """Synchronous stationary bootstrap of one window length."""
    block = int(width if expected_block is None else expected_block)
    needed = ["ret_gold", "ret_csi", "ret_hsi", "ret_dxy", "ret_brent", "dgpr"]
    frame = panel.dropna(subset=needed).copy()
    columns = {name: frame[name].to_numpy(dtype=float) for name in needed}
    n_obs = len(frame)
    rng = np.random.default_rng(seed + int(width) * 1009)
    index = stationary_indices(n_obs, width, reps, block, rng)
    taken = {name: values[index] for name, values in columns.items()}
    gold = taken["ret_gold"].sum(axis=1)
    excess = gold - taken["ret_csi"].sum(axis=1)
    haven = _haven_score(taken["ret_gold"], taken["ret_csi"], taken["ret_hsi"], taken["ret_dxy"], taken["dgpr"])
    draws = {"gold": gold, "gold_excess_csi": excess, "haven": haven}
    by_event = {}
    shift = []
    for event_id, pos in _event_positions(panel, events):
        observed = _observed(panel, pos, width)
        if observed is None:
            continue
        packed = {key: _percentile(draws[key], observed[key]) for key in draws if observed[key] is not None}
        blocked = _blocked_percentile(panel, events, width, observed["gold"])
        packed["blocked"] = blocked
        if "gold" in packed:
            packed["gold"]["blocked"] = blocked
        by_event[event_id] = packed
        if packed["gold"]["pct"] is not None and blocked["pct"] is not None:
            shift.append(
                {
                    "event_id": event_id,
                    "width": width,
                    "bootstrap_pct": packed["gold"]["pct"],
                    "blocked_pct": blocked["pct"],
                    "blocked_n": blocked["n"],
                    "diff": round(packed["gold"]["pct"] - blocked["pct"], 4),
                }
            )
    return {
        "method": "stationary_bootstrap",
        "block": block,
        "reps": int(reps),
        "seed": int(seed),
        "n_obs": int(n_obs),
        "null": {key: _histogram(value) for key, value in draws.items()},
        "by_event": by_event,
        "shift": shift,
    }
