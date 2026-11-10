"""State interactions, daily quantile curves, and CAR estimation-window checks.

High-yield OAS is recorded and shown. It is not a regression state: the FRED
series is too short to split.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

STATE_SPECS = (
    ("tips10", "DFII10", "10-year TIPS real yield"),
    ("breakeven", "T10YIE", "10-year breakeven inflation"),
    ("vix", "VIXCLS", "VIX"),
    ("dollar_broad", "DTWEXBGS", "broad dollar index"),
)
HY_SPEC = ("hy_oas", "BAMLH0A0HYM2", "high-yield OAS")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"


def _monthly_last(series: pd.Series) -> pd.Series:
    level = series.resample("ME").last().dropna()
    level.index = level.index.to_period("M")
    return level


def fetch_fred_states(raw_dir, timeout: int = 30) -> dict:
    """Download state files when they are missing. Failures stay out of the model."""
    import requests

    raw_dir.mkdir(parents=True, exist_ok=True)
    status = {}
    for name, series_id, label in STATE_SPECS + (HY_SPEC,):
        path = raw_dir / f"state_{name}.csv"
        if not path.exists() or path.stat().st_size < 50:
            try:
                resp = requests.get(
                    FRED.format(series=series_id),
                    timeout=timeout,
                    headers={"User-Agent": "GPR-Haven-Lab/2.4"},
                )
                resp.raise_for_status()
                if series_id.encode() not in resp.content:
                    raise RuntimeError(f"not a {series_id} csv")
                path.write_bytes(resp.content)
            except Exception as exc:
                status[name] = {"id": series_id, "label": label, "status": "missing", "error": str(exc)[:180]}
                continue
        status[name] = _describe_state(path, series_id, label)
    return status


def _describe_state(path, series_id: str, label: str) -> dict:
    frame = pd.read_csv(path)
    date_col = "DATE" if "DATE" in frame.columns else frame.columns[0]
    value_col = series_id if series_id in frame.columns else frame.columns[-1]
    values = pd.to_numeric(frame[value_col], errors="coerce")
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    ok = values.notna() & dates.notna()
    dates = dates[ok]
    values = values[ok]
    return {
        "id": series_id,
        "label": label,
        "status": "ok",
        "rows": int(ok.sum()),
        "start": None if dates.empty else dates.iloc[0].strftime("%Y-%m-%d"),
        "end": None if dates.empty else dates.iloc[-1].strftime("%Y-%m-%d"),
        "in_model": series_id != "BAMLH0A0HYM2",
        "note": "ICE high-yield OAS on FRED is too short to split. Shown only." if series_id == "BAMLH0A0HYM2" else "",
    }


def load_state_panel(raw_dir) -> pd.DataFrame:
    columns = {}
    for name, series_id, _label in STATE_SPECS:
        path = raw_dir / f"state_{name}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        date_col = "DATE" if "DATE" in frame.columns else frame.columns[0]
        value_col = series_id if series_id in frame.columns else frame.columns[-1]
        series = pd.Series(pd.to_numeric(frame[value_col], errors="coerce").to_numpy(), index=pd.to_datetime(frame[date_col], errors="coerce"))
        series = series[np.isfinite(series.to_numpy(dtype=float))]
        columns[name] = _monthly_last(series)
    if not columns:
        return pd.DataFrame()
    return pd.DataFrame(columns).sort_index()


def rolling_high_flag(level: pd.Series, window: int = 60) -> pd.Series:
    """1 when the month is in the top third of its own trailing window."""
    values = level.to_numpy(dtype=float)
    flag = np.full(len(values), np.nan)
    for i in range(window - 1, len(values)):
        hist = values[i - window + 1 : i + 1]
        hist = hist[np.isfinite(hist)]
        if hist.size < window or not np.isfinite(values[i]):
            continue
        flag[i] = float(values[i] >= np.quantile(hist, 2.0 / 3.0))
    return pd.Series(flag, index=level.index)


def interaction_response(target: pd.Series, shock: pd.Series, state: pd.Series, horizon: int, scale: float) -> dict:
    """y on shock, shock x state, and state. Low is state 0. High is state 1."""
    import statsmodels.api as sm
    from statsmodels.regression.linear_model import OLS

    low, high, gap, pvalue = [], [], [], []
    usable = pd.concat(
        [target.rename("y0"), shock.rename("shock"), state.rename("state")],
        axis=1,
    ).dropna()
    usable = usable[usable["state"].isin([0.0, 1.0])]
    n_high = int((usable["state"] == 1).sum())
    n_low = int((usable["state"] == 0).sum())
    for h in range(horizon + 1):
        y = target if h == 0 else target.rolling(h + 1).sum().shift(-h)
        reg = pd.concat([y.rename("y"), shock.rename("shock"), state.rename("state")], axis=1).dropna()
        reg = reg[reg["state"].isin([0.0, 1.0])]
        reg["interact"] = reg["shock"] * reg["state"]
        if len(reg) < 40 or reg["shock"].std(ddof=1) < 1e-8 or n_high < 24 or n_low < 24:
            low.append(None)
            high.append(None)
            gap.append(None)
            pvalue.append(None)
            continue
        fitted = OLS(reg["y"], sm.add_constant(reg[["shock", "interact", "state"]])).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": max(1, h + 1)},
        )
        b = float(fitted.params["shock"]) * scale
        c = float(fitted.params["interact"]) * scale
        se = float(fitted.bse["interact"]) * abs(scale)
        low.append(round(b, 4))
        high.append(round(b + c, 4))
        gap.append(round(c, 4))
        if se < 1e-12:
            pvalue.append(None)
        else:
            z = c / se
            pvalue.append(round(math.erfc(abs(z) / math.sqrt(2.0)), 4))
    return {"low": low, "high": high, "interaction": gap, "p": pvalue, "n_high": n_high, "n_low": n_low}


def conditional_bundle(panel: pd.DataFrame, states: pd.DataFrame, horizon: int = 12) -> dict:
    from havenlab.engine import LP_KEYS

    shock = panel["dgpr"].astype(float)
    scale = float(shock.std(ddof=1) or 1.0)
    rows = []
    flags = {"high_gpr": panel["high_gpr"].astype(float) if "high_gpr" in panel.columns else pd.Series(dtype=float)}
    for name in states.columns:
        flags[name] = rolling_high_flag(states[name].reindex(panel.index))
    for name, flag in flags.items():
        if flag.dropna().size < 80:
            continue
        assets = {}
        for key in LP_KEYS:
            assets[key] = interaction_response(panel[key].astype(float), shock, flag, horizon, scale)
        rows.append({"id": name, "assets": assets, "n_high": assets["ret_gold"]["n_high"], "n_low": assets["ret_gold"]["n_low"]})
    return {"horizon": list(range(horizon + 1)), "scale": round(scale, 4), "states": rows, "kind": "top_tercile_interaction"}


def fit_garch11(returns: np.ndarray) -> np.ndarray:
    """Gaussian GARCH(1,1) conditional standard deviation. Variance targeting."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    centered = r - r.mean()
    unconditional = float(np.var(centered, ddof=1))
    if unconditional <= 1e-12:
        return np.full(r.size, np.nan)

    def variance(alpha: float, beta: float) -> np.ndarray:
        omega = unconditional * (1.0 - alpha - beta)
        out = np.empty(centered.size)
        out[0] = unconditional
        for t in range(1, centered.size):
            out[t] = omega + alpha * centered[t - 1] ** 2 + beta * out[t - 1]
        return out

    best = (0.05, 0.90)
    best_nll = 1e300
    for alpha in (0.03, 0.06, 0.1):
        for beta in (0.85, 0.90, 0.94):
            if alpha + beta >= 0.995:
                continue
            s2 = variance(alpha, beta)
            if np.any(s2 <= 0):
                continue
            nll = float(0.5 * np.sum(np.log(s2) + centered**2 / s2))
            if nll < best_nll:
                best_nll = nll
                best = (alpha, beta)
    return np.sqrt(variance(*best))


def car_estimation_robust(daily: dict[str, pd.Series], events: list[dict]) -> dict:
    """Recompute the [-1, +5] gold CAR under three estimation windows."""
    series = daily.get("gold")
    if series is None or getattr(series, "empty", True):
        return {}
    ret = 100.0 * np.log(series[series > 0]).diff().dropna()
    windows = {"m120_m20": (-120, -20), "m250_m30": (-250, -30), "m60_m10": (-60, -10)}
    by_event: dict[str, dict] = {}
    buckets: dict[str, list[tuple[str, float]]] = {}
    for event in events:
        stamp = pd.Timestamp(event["date"]).normalize()
        loc = int(ret.index.searchsorted(stamp))
        packed = {}
        for key, (left, right) in windows.items():
            est_left = loc + left
            est_right = loc + right
            if est_left < 0 or loc + 6 > len(ret) or est_right - est_left < 30:
                continue
            est = ret.iloc[est_left:est_right]
            if len(est) < 30:
                continue
            mu = float(est.mean())
            sigma = float(est.std(ddof=1))
            if sigma < 1e-8:
                continue
            window = ret.iloc[loc - 1 : loc + 6]
            if len(window) < 7:
                continue
            car = float((window - mu).sum())
            stat = car / (sigma * math.sqrt(len(window)))
            pval = math.erfc(abs(stat) / math.sqrt(2.0))
            packed[key] = {"car": round(car, 3), "t": round(stat, 3), "p": round(pval, 4), "sigma": round(sigma, 3)}
            buckets.setdefault(key, []).append((event["id"], pval))
        if packed:
            by_event[event["id"]] = packed
    from havenlab.engine import _bh_qvalues

    for key, items in buckets.items():
        qvals = _bh_qvalues(np.array([item[1] for item in items], dtype=float))
        for (event_id, _pval), qval in zip(items, qvals):
            by_event[event_id][key]["q"] = round(float(qval), 4)
    return {
        "event_window": [-1, 5],
        "estimation": {key: [left, right] for key, (left, right) in windows.items()},
        "by_event": by_event,
    }


def daily_quantile_curve(daily: dict[str, pd.Series]) -> dict:
    """Predicted gold-return quantiles along a grid of daily GPR changes."""
    import statsmodels.api as sm
    from statsmodels.regression.quantile_regression import QuantReg

    gold = daily.get("gold")
    gpr = daily.get("gpr")
    dxy = daily.get("dxy")
    if gold is None or gpr is None or gold.empty or gpr.empty:
        return {}
    r_gold = 100.0 * np.log(gold[gold > 0]).diff()
    frame = pd.DataFrame({"gold": r_gold, "dgpr": gpr.diff(), "ddxy": 100.0 * np.log(dxy[dxy > 0]).diff() if dxy is not None and not dxy.empty else np.nan}).dropna()
    vix = daily.get("vix")
    if vix is not None and not vix.empty:
        frame["dvix"] = vix.reindex(frame.index).diff()
        frame = frame.dropna()
    if len(frame) < 500:
        return {"n": int(len(frame))}
    terms = ["dgpr", "ddxy"] + (["dvix"] if "dvix" in frame.columns else [])
    design = sm.add_constant(frame[terms])
    grid = np.linspace(float(frame["dgpr"].quantile(0.05)), float(frame["dgpr"].quantile(0.95)), 9)
    means = frame[terms].mean()
    curves = {}
    coefs = {}
    for tau in (0.05, 0.5, 0.95):
        fitted = QuantReg(frame["gold"], design).fit(q=tau, max_iter=2000)
        coefs[f"{tau:.2f}"] = {term: round(float(fitted.params[term]), 6) for term in terms}
        base = float(fitted.params["const"]) + sum(float(fitted.params[term]) * float(means[term]) for term in terms if term != "dgpr")
        curves[f"{tau:.2f}"] = [round(base + float(fitted.params["dgpr"]) * float(step), 4) for step in grid]
    sigma = fit_garch11(frame["gold"].to_numpy(dtype=float))
    return {
        "n": int(len(frame)),
        "grid": [round(float(step), 4) for step in grid],
        "curves": curves,
        "coef": coefs,
        "garch_sigma_median": None if not np.isfinite(sigma).any() else round(float(np.nanmedian(sigma)), 4),
    }
