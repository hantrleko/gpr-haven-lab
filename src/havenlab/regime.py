"""Causal state labels and historical analog months.

Percentile ranks use a trailing window that ends at the month itself.
Z-scores for a target use only months up to that target. Neighbors are at
least ``min_gap`` months earlier, so their later returns do not reach the target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 60
MIN_CELL = 20
DEFAULT_K = 24
DEFAULT_GAP = 12
DEFAULT_REPS = 400
DEFAULT_SEED = 20261111
FEATURE_COLUMNS = ("gpr", "real_rate", "dollar", "vix")
TIGHT = ("宽松", "中性", "紧缩")
PRESS = ("低压", "高压")
CELL_ORDER = [f"{press}×{tight}" for press in PRESS for tight in TIGHT]


def causal_percentile(values: np.ndarray, window: int = WINDOW) -> np.ndarray:
    """Share of the trailing window at or below the current value. NaN until the window is full."""
    series = np.asarray(values, dtype=float)
    out = np.full(series.shape[0], np.nan)
    for i in range(window - 1, series.shape[0]):
        hist = series[i - window + 1 : i + 1]
        if not np.isfinite(hist).all():
            continue
        out[i] = float(np.mean(hist <= hist[-1]))
    return out


def causal_tercile(values: np.ndarray, window: int = WINDOW) -> np.ndarray:
    """0 low, 1 middle, 2 high, inside the trailing window. Ties at the lower cut stay low."""
    series = np.asarray(values, dtype=float)
    out = np.full(series.shape[0], np.nan)
    for i in range(window - 1, series.shape[0]):
        hist = series[i - window + 1 : i + 1]
        if not np.isfinite(hist).all():
            continue
        low, high = np.quantile(hist, [1.0 / 3.0, 2.0 / 3.0])
        value = hist[-1]
        if value <= low:
            out[i] = 0
        elif value > high:
            out[i] = 2
        else:
            out[i] = 1
    return out


def tightness_codes(terciles: np.ndarray) -> np.ndarray:
    """Map available terciles to loose / neutral / tight. Two finite columns are required."""
    grid = np.asarray(terciles, dtype=float)
    if grid.ndim == 1:
        grid = grid.reshape(-1, 1)
    out = np.full(grid.shape[0], np.nan)
    for i, row in enumerate(grid):
        usable = row[np.isfinite(row)]
        if usable.size < 2:
            continue
        high = int(np.sum(usable == 2))
        low = int(np.sum(usable == 0))
        if high >= 2:
            out[i] = 2
        elif low >= 2 and high == 0:
            out[i] = 0
        else:
            out[i] = 1
    return out


def cell_label(pressure: float, tightness: float) -> str | None:
    if not np.isfinite(pressure) or not np.isfinite(tightness):
        return None
    return f"{PRESS[int(pressure)]}×{TIGHT[int(tightness)]}"


def count_runs(positions: list[int], min_gap: int) -> int:
    """Selected months more than ``min_gap`` apart start a new independent run."""
    if not positions:
        return 0
    ordered = sorted(int(item) for item in positions)
    runs = 1
    for left, right in zip(ordered, ordered[1:]):
        if right - left > min_gap:
            runs += 1
    return runs


def _features(frame: pd.DataFrame, columns: list[str]) -> tuple[np.ndarray, list[str]]:
    kept = []
    names = []
    for name in columns:
        if name not in frame.columns:
            continue
        pct = causal_percentile(frame[name].to_numpy(dtype=float))
        if int(np.isfinite(pct).sum()) < WINDOW:
            continue
        kept.append(pct)
        names.append(name)
    if not kept:
        return np.zeros((len(frame), 0)), []
    return np.column_stack(kept), names


def _forward(values: np.ndarray, origin: int, horizon: int) -> float:
    window = values[origin + 1 : origin + 1 + horizon]
    if window.shape[0] < horizon or not np.isfinite(window).all():
        return float("nan")
    return float(window.sum())


def _return_iqr(series: np.ndarray, positions, horizon: int) -> float:
    clean = np.asarray([_forward(series, int(pos), horizon) for pos in positions], dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size < 4:
        return float("nan")
    q75, q25 = np.quantile(clean, [0.75, 0.25])
    return float(q75 - q25)


def _quantile_pack(samples: list[float]) -> dict:
    clean = np.asarray([value for value in samples if np.isfinite(value)], dtype=float)
    if clean.size == 0:
        return {"n": 0}
    probs = (10, 25, 50, 75, 90)
    cuts = np.quantile(clean, [p / 100 for p in probs])
    pack = {"n": int(clean.size)}
    for prob, cut in zip(probs, cuts):
        pack[f"p{prob}"] = round(float(cut), 2)
    return pack


def analog_months(
    frame: pd.DataFrame,
    target_month: str,
    k: int = DEFAULT_K,
    min_gap: int = DEFAULT_GAP,
    exclude_events: bool = False,
    event_months: set[str] | None = None,
    columns: tuple[str, ...] = FEATURE_COLUMNS,
    reps: int = DEFAULT_REPS,
    seed: int = DEFAULT_SEED,
    horizons: tuple[int, ...] = (1, 3, 6),
) -> dict:
    """Nearest earlier months on a z-scored trailing-percentile vector.

    Standardization uses rows ``0..target`` only. Shuffling any later row
    cannot change the neighbor set or the forward quantiles.
    """
    target = pd.Period(target_month, freq="M")
    if target not in frame.index:
        return {"ok": False, "reason": "month not in sample", "month": str(target)}
    t = int(frame.index.get_loc(target))
    pct, names = _features(frame, list(columns))
    if not names:
        return {"ok": False, "reason": "no usable features", "month": str(target)}
    keep = np.isfinite(pct[t])
    names = [name for name, flag in zip(names, keep) if flag]
    if not names:
        return {"ok": False, "reason": "target percentile is incomplete", "month": str(target), "features": []}
    used = pct[:, keep]
    hist = used[: t + 1]
    center = np.nanmean(hist, axis=0)
    scale = np.nanstd(hist, axis=0, ddof=1)
    scale = np.where(scale < 1e-12, np.nan, scale)
    z = (hist - center) / scale
    if not np.isfinite(z[t]).all():
        return {"ok": False, "reason": "target z is incomplete", "month": str(target), "features": names}
    blocked = {str(item) for item in (event_months or set())}
    eligible: list[tuple[float, int]] = []
    for s in range(t - min_gap + 1):
        if s + max(horizons) >= t:
            continue
        if not np.isfinite(z[s]).all():
            continue
        if exclude_events and str(frame.index[s]) in blocked:
            continue
        gap = z[s] - z[t]
        eligible.append((float(np.sqrt(np.dot(gap, gap))), s))
    eligible.sort(key=lambda item: (item[0], item[1]))
    if not eligible:
        return {"ok": False, "reason": "no eligible months", "month": str(target), "features": names}
    chosen = eligible[: min(k, len(eligible))]
    positions = [pos for _, pos in chosen]
    observed = float(np.mean([dist for dist, _ in chosen]))
    gold = frame["ret_gold"].to_numpy(dtype=float) if "ret_gold" in frame.columns else np.full(len(frame), np.nan)
    observed_iqr = _return_iqr(gold, positions, 3)
    perm_p = None
    perm_reps = 0
    # Nearest neighbors are closer by construction. The permutation therefore
    # asks whether their later 3-month gold returns are more concentrated
    # than a random draw of the same size from the eligible months.
    if reps > 0 and len(eligible) > len(chosen) and np.isfinite(observed_iqr):
        pool = np.asarray([pos for _, pos in eligible], dtype=int)
        rng = np.random.default_rng(seed)
        n_ok = 0
        n_le = 0
        for _draw in range(reps):
            pick = rng.choice(pool, size=len(positions), replace=False)
            value = _return_iqr(gold, pick, 3)
            if not np.isfinite(value):
                continue
            n_ok += 1
            n_le += int(value <= observed_iqr)
        if n_ok:
            perm_p = round(n_le / n_ok, 4)
            perm_reps = n_ok
    csi = frame["ret_csi"].to_numpy(dtype=float) if "ret_csi" in frame.columns else np.full(len(frame), np.nan)
    forward = {}
    for horizon in horizons:
        gold_samples = [_forward(gold, pos, horizon) for pos in positions]
        excess_samples = [
            _forward(gold, pos, horizon) - _forward(csi, pos, horizon) for pos in positions
        ]
        forward[str(horizon)] = {"gold": _quantile_pack(gold_samples), "excess_csi": _quantile_pack(excess_samples)}
    return {
        "ok": True,
        "month": str(target),
        "features": names,
        "k": len(chosen),
        "k_requested": int(k),
        "n_eligible": len(eligible),
        "indep_runs": count_runs(positions, min_gap),
        "min_gap": int(min_gap),
        "mean_distance": round(observed, 4),
        "perm_statistic": "iqr_gold_3m",
        "perm_observed": None if not np.isfinite(observed_iqr) else round(float(observed_iqr), 4),
        "perm_p": perm_p,
        "perm_reps": perm_reps,
        "perm_seed": int(seed),
        "neighbors": [str(frame.index[pos]) for pos in positions],
        "forward": forward,
        "exclude_events": bool(exclude_events),
    }


def describe_states(frame: pd.DataFrame) -> dict:
    """Six-cell labels from trailing terciles. Pressure reuses the existing high-GPR flag."""
    n = len(frame)
    pressure = frame["high_gpr"].to_numpy(dtype=float) if "high_gpr" in frame.columns else np.full(n, np.nan)
    tercile_names = [name for name in ("real_rate", "dollar", "vix") if name in frame.columns]
    if tercile_names:
        terciles = np.column_stack([causal_tercile(frame[name].to_numpy(dtype=float)) for name in tercile_names])
        tight = tightness_codes(terciles)
    else:
        tight = np.full(n, np.nan)
    labels = [cell_label(pressure[i], tight[i]) for i in range(n)]
    counts = {label: 0 for label in CELL_ORDER}
    for label in labels:
        if label in counts:
            counts[label] += 1
    timeline = []
    for i, label in enumerate(labels):
        if label is None and not np.isfinite(pressure[i]):
            continue
        timeline.append(
            {
                "month": str(frame.index[i]),
                "pressure": None if not np.isfinite(pressure[i]) else PRESS[int(pressure[i])],
                "tightness": None if not np.isfinite(tight[i]) else TIGHT[int(tight[i])],
                "cell": label,
            }
        )
    matrix = []
    for left in CELL_ORDER:
        row = []
        for right in CELL_ORDER:
            hits = 0
            for i in range(len(labels) - 1):
                if labels[i] == left and labels[i + 1] == right:
                    hits += 1
            row.append(hits)
        matrix.append(row)
    probs = []
    for row in matrix:
        total = sum(row)
        probs.append([None if total == 0 else round(item / total, 3) for item in row])
    missing = [name for name in ("real_rate", "dollar", "vix") if name not in frame.columns]
    note = "历史频率，不是概率预测。每个格子都标出观测数。少于 20 个月的格子不拿来陈述。"
    if sum(counts.values()) == 0:
        note += " 这次六个格子都是 0：综合松紧至少要两项三分位，缺了实际利率或美元就不会填格。"
    return {
        "min_cell": MIN_CELL,
        "features_for_tightness": tercile_names,
        "missing": missing,
        "counts": counts,
        "speakable": {label: count >= MIN_CELL for label, count in counts.items()},
        "timeline": timeline,
        "transitions": {
            "labels": CELL_ORDER,
            "counts": matrix,
            "probs": probs,
            "note": note,
        },
    }


def build_regime(frame: pd.DataFrame, events: list[dict], fast: bool = False) -> dict:
    described = describe_states(frame)
    reps = 80 if fast else DEFAULT_REPS
    event_months = set()
    by_event = {}
    for event in events:
        month = str(pd.Timestamp(event["date"]).to_period("M"))
        event_months.add(month)
        by_event[event["id"]] = analog_months(
            frame,
            month,
            exclude_events=False,
            event_months=event_months,
            reps=reps,
        )
    latest = str(frame.index[-1])
    current = analog_months(frame, latest, event_months=event_months, reps=reps)
    held_out = analog_months(frame, latest, exclude_events=True, event_months=event_months, reps=reps)
    described["by_event"] = by_event
    described["latest"] = current
    described["latest_excluding_events"] = {
        "k": held_out.get("k"),
        "indep_runs": held_out.get("indep_runs"),
        "perm_p": held_out.get("perm_p"),
        "neighbors": held_out.get("neighbors"),
    }
    described["rule"] = {
        "window": WINDOW,
        "pressure": "high_gpr，自身过去 60 个月的 75 分位",
        "tightness": "实际利率、美元、VIX 的滚动三分位。至少两项处在高档才标紧缩；至少两项处在低档且没有高档才标宽松。",
        "analog": "目标月及之前的百分位做 z 分。相似月至少早 12 个月。k=24。置换检验比较其后 3 个月黄金收益的四分位距是否比随机抽同样个数更窄，不比较状态距离。",
        "k": DEFAULT_K,
        "min_gap": DEFAULT_GAP,
        "seed": DEFAULT_SEED,
    }
    return described
