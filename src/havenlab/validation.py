"""Walk-forward quantile forecasts. Parameters are frozen each January.

The only scored object is the 10/50/90 percent forecast of the next three
months of cumulative gold returns. k stays at 24. It is not chosen to improve
the score.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from havenlab.regime import WINDOW, causal_percentile

HORIZON = 3
K = 24
MIN_GAP = 12
START = "2015-01"
TAUS = (0.10, 0.50, 0.90)
PASS_IMPROVEMENT = 0.08
MIN_BIN = 12


def pinball(y: float, forecast: float, tau: float) -> float:
    hit = 1.0 if y < forecast else 0.0
    return float((y - forecast) * (tau - hit))


def pit_value(y: float, q10: float, q50: float, q90: float) -> float:
    """Piecewise linear CDF through the three forecast quantiles, clipped to (0, 1)."""
    if not all(np.isfinite(value) for value in (y, q10, q50, q90)):
        return float("nan")
    if q50 < q10:
        q10, q50 = q50, q10
    if q90 < q50:
        q50, q90 = q90, q50
    left = max(q50 - q10, 1e-6)
    right = max(q90 - q50, 1e-6)
    if y <= q10:
        pit = 0.10 * (y - (q10 - left)) / left
    elif y <= q50:
        pit = 0.10 + 0.40 * (y - q10) / left
    elif y <= q90:
        pit = 0.50 + 0.40 * (y - q50) / right
    else:
        pit = 0.90 + 0.10 * (y - q90) / right
    return float(np.clip(pit, 1e-6, 1.0 - 1e-6))


def coverage_hit(y: float, q10: float, q90: float) -> bool:
    low, high = (q10, q90) if q10 <= q90 else (q90, q10)
    return bool(low <= y <= high)


def diebold_mariano(loss_model: np.ndarray, loss_base: np.ndarray, lag: int = HORIZON) -> dict:
    """Two-sided p-value for the mean loss gap. Newey-West lag equals the forecast horizon."""
    gap = np.asarray(loss_model, dtype=float) - np.asarray(loss_base, dtype=float)
    gap = gap[np.isfinite(gap)]
    n = int(gap.size)
    if n < 10:
        return {"n": n, "mean": None, "p": None}
    mean = float(gap.mean())
    centered = gap - mean
    gamma0 = float(np.dot(centered, centered) / n)
    variance = gamma0
    for step in range(1, lag + 1):
        weight = 1.0 - step / (lag + 1.0)
        gamma = float(np.dot(centered[step:], centered[:-step]) / n)
        variance += 2.0 * weight * gamma
    variance = max(variance, 0.0)
    se = math.sqrt(variance / n) if variance > 0 else 0.0
    if se < 1e-12:
        p_value = 1.0 if abs(mean) < 1e-12 else 0.0
    else:
        z = mean / se
        p_value = float(math.erfc(abs(z) / math.sqrt(2.0)))
    return {"n": n, "mean": round(mean, 6), "se": round(se, 6), "p": round(p_value, 4)}


def _forward(values: np.ndarray, origin: int, horizon: int = HORIZON) -> float:
    window = values[origin + 1 : origin + 1 + horizon]
    if window.shape[0] < horizon or not np.isfinite(window).all():
        return float("nan")
    return float(window.sum())


def _frozen_quantiles(samples: list[float]) -> dict | None:
    clean = np.asarray([value for value in samples if np.isfinite(value)], dtype=float)
    if clean.size < MIN_BIN:
        return None
    q10, q50, q90 = np.quantile(clean, TAUS)
    return {"q10": float(q10), "q50": float(q50), "q90": float(q90), "n": int(clean.size)}


def _frozen_z(pct: np.ndarray, cutoff: int) -> np.ndarray:
    """Z-scores using the mean and standard deviation of months up to the cutoff only."""
    hist = pct[: cutoff + 1]
    hist = hist[np.isfinite(hist)]
    out = np.full(pct.shape[0], np.nan)
    if hist.size < WINDOW:
        return out
    scale = float(hist.std(ddof=1))
    if scale < 1e-12:
        return out
    center = float(hist.mean())
    finite = np.isfinite(pct)
    out[finite] = (pct[finite] - center) / scale
    return out


def _series(frame: pd.DataFrame, name: str) -> np.ndarray | None:
    if name not in frame.columns:
        return None
    values = frame[name].to_numpy(dtype=float)
    if int(np.isfinite(values).sum()) < WINDOW:
        return None
    return values


def walk_forward(frame: pd.DataFrame, start: str = START, k: int = K, min_gap: int = MIN_GAP) -> pd.DataFrame:
    """One row per forecast month. Z moments and baseline bins freeze at the previous December."""
    ret = frame["ret_gold"].to_numpy(dtype=float)
    gpr = _series(frame, "gpr")
    if gpr is None:
        return pd.DataFrame()
    levels = {"gpr": gpr}
    for name in ("real_rate", "dollar", "vix"):
        values = _series(frame, name)
        if values is not None:
            levels[name] = values
    pct = {name: causal_percentile(values) for name, values in levels.items()}
    start_at = pd.Period(start, freq="M")
    cache: dict[int, dict] = {}
    rows = []
    for t, month in enumerate(frame.index):
        if month < start_at or t + HORIZON >= len(frame):
            continue
        cutoff_month = pd.Period(f"{month.year - 1}-12", freq="M")
        if cutoff_month not in frame.index:
            continue
        c = int(frame.index.get_loc(cutoff_month))
        if c < WINDOW - 1:
            continue
        outcome = _forward(ret, t)
        if not np.isfinite(outcome):
            continue
        if c not in cache:
            z = {name: _frozen_z(values, c) for name, values in pct.items()}
            known = [origin for origin in range(0, c - HORIZON + 1) if np.isfinite(_forward(ret, origin))]
            gpr_hist = gpr[c - WINDOW + 1 : c + 1]
            gpr_cut = float(np.quantile(gpr_hist, 0.75)) if np.isfinite(gpr_hist).all() else float("nan")
            real_edges = None
            if "real_rate" in levels and np.isfinite(levels["real_rate"][c - WINDOW + 1 : c + 1]).all():
                real_edges = tuple(np.quantile(levels["real_rate"][c - WINDOW + 1 : c + 1], [1.0 / 3.0, 2.0 / 3.0]))
            cache[c] = {"z": z, "known": known, "gpr_cut": gpr_cut, "real_edges": real_edges}
        frozen = cache[c]
        active = [name for name in pct if np.isfinite(frozen["z"][name][t])]
        library = []
        last_s = t - min_gap - HORIZON
        for s in range(0, last_s + 1):
            if any(not np.isfinite(frozen["z"][name][s]) for name in active):
                continue
            gap = np.array([frozen["z"][name][s] - frozen["z"][name][t] for name in active], dtype=float)
            library.append((float(np.sqrt(np.dot(gap, gap))), s))
        library.sort()
        picked = library[:k]
        analog_q = _frozen_quantiles([_forward(ret, s) for _, s in picked]) if len(picked) >= 8 else None
        known = frozen["known"]
        unconditional = _frozen_quantiles([_forward(ret, origin) for origin in known])
        gpr_cut = frozen["gpr_cut"]
        gpr_q = None
        if np.isfinite(gpr_cut) and np.isfinite(gpr[t]):
            gpr_high = bool(gpr[t] >= gpr_cut)
            gpr_q = _frozen_quantiles(
                [
                    _forward(ret, origin)
                    for origin in known
                    if np.isfinite(gpr[origin]) and bool(gpr[origin] >= gpr_cut) == gpr_high
                ]
            )
        real_q = None
        edges = frozen["real_edges"]
        if edges is not None and np.isfinite(levels["real_rate"][t]):
            low, high = edges

            def _bin(value: float) -> int:
                if value <= low:
                    return 0
                if value > high:
                    return 2
                return 1

            current = _bin(float(levels["real_rate"][t]))
            real_q = _frozen_quantiles(
                [
                    _forward(ret, origin)
                    for origin in known
                    if np.isfinite(levels["real_rate"][origin]) and _bin(float(levels["real_rate"][origin])) == current
                ]
            )
        rows.append(
            {
                "month": str(month),
                "cutoff": str(cutoff_month),
                "y": outcome,
                "model": analog_q,
                "unconditional": unconditional,
                "gpr": gpr_q,
                "real_rate": real_q,
                "n_analogs": len(picked),
                "features": active,
            }
        )
    return pd.DataFrame(rows)


def summarize_walk(rows: pd.DataFrame) -> dict:
    """Score the frozen forecasts. A missing real-rate baseline cannot be counted as a win."""

    def pack(column: str) -> dict:
        ys, losses, pits, hits = [], [], [], []
        for _, row in rows.iterrows():
            forecast = row[column]
            if not isinstance(forecast, dict):
                continue
            y = float(row["y"])
            point = float(np.mean([pinball(y, forecast[key], tau) for key, tau in zip(("q10", "q50", "q90"), TAUS)]))
            ys.append(y)
            losses.append(point)
            pits.append(pit_value(y, forecast["q10"], forecast["q50"], forecast["q90"]))
            hits.append(coverage_hit(y, forecast["q10"], forecast["q90"]))
        loss = np.asarray(losses, dtype=float)
        pit = np.asarray(pits, dtype=float)
        pit = pit[np.isfinite(pit)]
        ks_p = None
        if pit.size >= 20:
            from scipy import stats

            ks_p = round(float(stats.kstest(pit, "uniform").pvalue), 4)
        covered = float(np.mean(hits)) if hits else None
        return {
            "n": int(len(losses)),
            "pinball": None if not losses else round(float(np.mean(loss)), 4),
            "pit_ks_p": ks_p,
            "coverage_80": None if covered is None else round(covered, 4),
            "losses": loss,
        }

    model = pack("model")
    bases = {name: pack(name) for name in ("unconditional", "gpr", "real_rate")}
    comparisons = {}
    for name, base in bases.items():
        if model["n"] == 0 or base["n"] == 0 or model["pinball"] is None or base["pinball"] in (None, 0):
            comparisons[name] = {"available": base["n"] > 0, "improvement": None, "dm": {"p": None}}
            continue
        paired_m, paired_b = [], []
        for _, row in rows.iterrows():
            if not isinstance(row["model"], dict) or not isinstance(row[name], dict):
                continue
            y = float(row["y"])
            paired_m.append(float(np.mean([pinball(y, row["model"][key], tau) for key, tau in zip(("q10", "q50", "q90"), TAUS)])))
            paired_b.append(float(np.mean([pinball(y, row[name][key], tau) for key, tau in zip(("q10", "q50", "q90"), TAUS)])))
        base_loss = float(np.mean(paired_b))
        model_loss = float(np.mean(paired_m))
        improvement = (base_loss - model_loss) / base_loss if base_loss else None
        comparisons[name] = {
            "available": True,
            "n": len(paired_m),
            "pinball_model": round(model_loss, 4),
            "pinball_base": round(base_loss, 4),
            "improvement": None if improvement is None else round(float(improvement), 4),
            "dm": diebold_mariano(np.asarray(paired_m), np.asarray(paired_b)),
        }
    unconditional = comparisons["unconditional"]
    improvement = unconditional.get("improvement")
    pit_p = model["pit_ks_p"]
    coverage = model["coverage_80"]
    beats_pinball = improvement is not None and improvement >= PASS_IMPROVEMENT
    pit_ok = pit_p is not None and pit_p > 0.10
    cover_ok = coverage is not None and 0.70 <= coverage <= 0.90
    dm_ok = True
    all_present = True
    for name, item in comparisons.items():
        if not item.get("available"):
            all_present = False
            dm_ok = False
            continue
        dm_p = (item.get("dm") or {}).get("p")
        better = item.get("improvement") is not None and item["improvement"] > 0
        if dm_p is None or dm_p >= 0.10 or not better:
            dm_ok = False
    passed = bool(beats_pinball and pit_ok and cover_ok and dm_ok and all_present)
    public = {
        "model": {key: model[key] for key in ("n", "pinball", "pit_ks_p", "coverage_80")},
        "baselines": {
            name: {key: value for key, value in item.items() if key != "losses"}
            for name, item in comparisons.items()
        },
        "gates": {
            "improvement_at_least_8pct": beats_pinball,
            "pit_ks_p_above_0_10": pit_ok,
            "coverage_in_70_90": cover_ok,
            "dm_p_below_0_10_and_better_than_each_baseline": dm_ok,
            "all_three_baselines_present": all_present,
            "pass": passed,
        },
        "k": K,
        "horizon_months": HORIZON,
        "start": START,
        "parameter_rule": "每年 1 月冻结上一年 12 月之前的 z 分矩、GPR 75 分位和实际利率三分位。k=24，不按损失挑选。",
    }
    return public


def forecast_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Flat table for output/oos_metrics.csv. Nested forecasts become columns."""
    flat = []
    for _, row in rows.iterrows():
        item = {"month": row["month"], "cutoff": row["cutoff"], "y": None if not np.isfinite(row["y"]) else round(float(row["y"]), 4)}
        for name in ("model", "unconditional", "gpr", "real_rate"):
            forecast = row[name]
            if not isinstance(forecast, dict):
                item[f"{name}_q10"] = None
                item[f"{name}_q50"] = None
                item[f"{name}_q90"] = None
                continue
            item[f"{name}_q10"] = round(forecast["q10"], 4)
            item[f"{name}_q50"] = round(forecast["q50"], 4)
            item[f"{name}_q90"] = round(forecast["q90"], 4)
        flat.append(item)
    return pd.DataFrame(flat)
