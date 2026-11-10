"""Downside beta, tail dependence, and the side-by-side haven scores.

haven (v1) stays the headline. haven1_z only changes the average from raw
correlations to a Fisher-z average. haven2 uses downside betas and a
lower-tail GPR coefficient. Neither replaces v1.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

_CLIP = 0.999


def fisher_mean(values: list[float]) -> float:
    clipped = [float(np.clip(value, -_CLIP, _CLIP)) for value in values]
    return float(np.tanh(np.mean(np.arctanh(clipped))))


def haven1_z(c_csi: float, c_hsi: float, c_gpr: float, c_dxy: float) -> float:
    """v1 score with the three signed correlations averaged in Fisher z."""
    signed = fisher_mean([-(c_csi + c_hsi) / 2.0, c_gpr, -c_dxy])
    return 50.0 * (1.0 + signed)


def downside_beta(outcome: np.ndarray, conditioning: np.ndarray, quantile: float = 0.20, min_n: int = 36) -> tuple[float, float] | None:
    """Return (beta clipped to [-1, 1], raw beta) when the conditioning variable is below its quantile."""
    y = np.asarray(outcome, dtype=float)
    x = np.asarray(conditioning, dtype=float)
    mask = np.isfinite(y) & np.isfinite(x)
    y = y[mask]
    x = x[mask]
    if x.size < min_n:
        return None
    cutoff = float(np.quantile(x, quantile))
    down = x < cutoff
    if int(down.sum()) < 8:
        return None
    xd = x[down]
    yd = y[down]
    variance = float(np.var(xd, ddof=1))
    if variance <= 1e-12:
        return None
    raw = float(np.cov(yd, xd, ddof=1)[0, 1] / variance)
    return float(np.clip(raw, -1.0, 1.0)), raw


def tail_dependence(outcome: np.ndarray, conditioning: np.ndarray, quantile: float = 0.10, min_n: int = 60) -> float | None:
    """Lift of gold's own left tail when the conditioning series is in its left tail.

    Independent series score about 1. A number below 1 means gold is less often
    in its own left tail when the other series is.
    """
    y = np.asarray(outcome, dtype=float)
    x = np.asarray(conditioning, dtype=float)
    mask = np.isfinite(y) & np.isfinite(x)
    y = y[mask]
    x = x[mask]
    if y.size < min_n:
        return None
    qy = float(np.quantile(y, quantile))
    qx = float(np.quantile(x, quantile))
    p_y = float(np.mean(y < qy))
    if p_y <= 0:
        return None
    conditional = float(np.mean((y < qy) & (x < qx)) / max(np.mean(x < qx), 1e-12))
    return conditional / p_y


def haven2_score(beta_csi: float, beta_hsi: float, beta_dxy: float, gpr_beta: float) -> float:
    signed = fisher_mean([-(beta_csi + beta_hsi) / 2.0, gpr_beta, -beta_dxy])
    return 50.0 * (1.0 + signed)


def quantile_sensitivity(frame: pd.DataFrame, taus: tuple[float, ...] = (0.1, 0.5, 0.9)) -> dict:
    """Full-sample quantile regression of gold on CSI, the GPR change, and the dollar."""
    import statsmodels.api as sm
    from statsmodels.regression.quantile_regression import QuantReg

    needed = ["ret_gold", "ret_csi", "dgpr", "ret_dxy"]
    sample = frame[needed].dropna().astype(float)
    if len(sample) < 80:
        return {"n": int(len(sample)), "taus": {}}
    scale = float(sample["dgpr"].std(ddof=1) / (sample["ret_gold"].std(ddof=1) or 1.0))
    design = sm.add_constant(sample[["ret_csi", "dgpr", "ret_dxy"]])
    taus_out = {}
    for tau in taus:
        fitted = QuantReg(sample["ret_gold"], design).fit(q=tau, max_iter=2000)
        coef = float(fitted.params["dgpr"])
        taus_out[f"{tau:.1f}"] = {
            "dgpr": round(coef, 6),
            "dgpr_beta": round(float(np.clip(coef * scale, -1.0, 1.0)), 4),
            "csi": round(float(fitted.params["ret_csi"]), 4),
            "dxy": round(float(fitted.params["ret_dxy"]), 4),
            "n": int(fitted.nobs),
        }
    return {"n": int(len(sample)), "scale": round(scale, 6), "taus": taus_out}


def rolling_downside(panel: pd.DataFrame, window: int = 60) -> dict:
    n = len(panel)
    gold = panel["ret_gold"].to_numpy(dtype=float)
    csi = panel["ret_csi"].to_numpy(dtype=float)
    hsi = panel["ret_hsi"].to_numpy(dtype=float)
    dxy = panel["ret_dxy"].to_numpy(dtype=float)
    beta = {name: np.full(n, np.nan) for name in ("csi", "hsi", "dxy")}
    tail = np.full(n, np.nan)
    score = np.full(n, np.nan)
    sources = {"csi": csi, "hsi": hsi, "dxy": dxy}
    for i in range(window - 1, n):
        sl = slice(i - window + 1, i + 1)
        packed = {}
        for name, series in sources.items():
            found = downside_beta(gold[sl], series[sl], min_n=window)
            if found is None:
                packed = None
                break
            packed[name] = found[0]
            beta[name][i] = found[0]
        if packed is None:
            continue
        tail_value = tail_dependence(gold[sl], csi[sl], min_n=window)
        if tail_value is not None:
            tail[i] = tail_value
        score[i] = haven2_score(packed["csi"], packed["hsi"], packed["dxy"], 0.0)
    return {"beta": beta, "tail_csi": tail, "score_without_gpr": score}


def haven1_z_series(panel: pd.DataFrame, window: int = 36) -> np.ndarray:
    from havenlab.engine import pearson

    n = len(panel)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        block = panel.iloc[i - window + 1 : i + 1]
        c_csi, _n1 = pearson(block["ret_gold"], block["ret_csi"], min_n=24)
        c_hsi, _n2 = pearson(block["ret_gold"], block["ret_hsi"], min_n=24)
        c_gpr, _n3 = pearson(block["ret_gold"], block["dgpr"], min_n=24)
        c_dxy, _n4 = pearson(block["ret_gold"], block["ret_dxy"], min_n=24)
        if None in (c_csi, c_hsi, c_gpr, c_dxy):
            continue
        out[i] = haven1_z(c_csi, c_hsi, c_gpr, c_dxy)
    return out


def event_haven_versions(panel: pd.DataFrame, events: list[dict], gpr_beta: float | None) -> dict:
    """Event-window v1 and v1_z. v2 is the 60-month roll ending at the event month."""
    from havenlab.engine import event_window

    downside = rolling_downside(panel, 60)
    z_series = haven1_z_series(panel, 36)
    out = {}
    gpr_term = 0.0 if gpr_beta is None else float(gpr_beta)
    for event in events:
        month = str(event.get("month") or pd.Timestamp(event["date"]).to_period("M"))
        period = pd.Period(month, freq="M")
        if period not in panel.index:
            continue
        loc = int(panel.index.get_loc(period))
        packed = {}
        for width in (6, 12, 24):
            try:
                window = event_window(panel, month, width)
            except KeyError:
                continue
            after = window["haven_after"] or {}
            if not after:
                packed[str(width)] = None
                continue
            packed[str(width)] = {
                "haven": None if after.get("score") is None else round(float(after["score"]), 2),
                "haven1_z": round(
                    haven1_z(after["corr_gold_csi"], after["corr_gold_hsi"], after["corr_gold_dgpr"], after["corr_gold_dxy"]),
                    2,
                ),
                "n_after": window["n_after"],
                "haven2": None,
                "haven2_note": "Downside beta needs 60 months, so v2 is not an event-window score.",
            }
        if np.isfinite(downside["beta"]["csi"][loc]) and np.isfinite(downside["beta"]["hsi"][loc]) and np.isfinite(downside["beta"]["dxy"][loc]):
            v2 = haven2_score(
                float(downside["beta"]["csi"][loc]),
                float(downside["beta"]["hsi"][loc]),
                float(downside["beta"]["dxy"][loc]),
                gpr_term,
            )
            for slot in packed.values():
                if slot is not None:
                    slot["haven2"] = round(v2, 2)
                    slot["haven2_window"] = "rolling_60m_ending_event_month"
        if np.isfinite(z_series[loc]):
            for slot in packed.values():
                if slot is not None and slot.get("haven1_z") is None:
                    slot["haven1_z_roll36"] = round(float(z_series[loc]), 2)
        out[event["id"]] = packed
    downside["haven1_z"] = z_series
    downside["events"] = out
    return downside
