"""Monthly panel, haven score, event windows, and a small recursive VAR.

Price returns are 100 * monthly log changes of the last available close in
each calendar month. They are not excess returns. GPR is the monthly mean of
the Caldara-Iacoviello daily GPRD index; dgpr is its first difference.

Haven score, on a window of monthly observations:

    equity = 50 * (1 - average(corr(gold, CSI300), corr(gold, HSI)))
    gpr    = 50 * (1 + corr(gold, dgpr))
    dollar = 50 * (1 - corr(gold, DXY))
    score  = (equity + gpr + dollar) / 3

Zero correlation on all three legs scores 50. The 60 / 45 regime cutoffs are
lab conventions, not estimated thresholds.

The VAR is recursive. Cholesky order is dgpr, Brent, DXY, gold, CSI300, HSI,
so a GPR innovation can move prices in the same month and prices do not move
GPR in the same month. Lag length is AIC over 1, 2, and 3. Impulse responses
are cumulative sums of orthogonalized monthly responses: for a return, that
sum approximates the percent change in the price level.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR

from havenlab.events import EVENTS
from havenlab.version import API_VERSION, EVENT_REGISTRY_VERSION, LAB_VERSION

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

ROLL = 36
GPR_WIN = 60
GPR_Q = 0.75
HAVEN_ON = 60.0
HAVEN_OFF = 45.0
MAX_SESSIONS = 60
VAR_MAXLAG = 3
VAR_HORIZON = 12
BOOT_REPS = 200
BOOT_SEED = 42
# Reproduction pin. A later calendar day must not extend the sample until this
# period is edited on purpose.
ASOF = pd.Timestamp("2026-10-13")
SAMPLE_END = pd.Period("2026-09", freq="M")
PLACEBO_SEED = 20261013
PLACEBO_DRAW = 120

PRICE_FILES = {
    "gold": RAW / "gold_gc.csv",
    "brent": RAW / "brent_bz.csv",
    "dxy": RAW / "dxy.csv",
    "hsi": RAW / "hsi.csv",
}

VAR_SPEC = [
    ("dgpr", "GPR变动", "指数点"),
    ("ret_brent", "布伦特", "%"),
    ("ret_dxy", "美元指数", "%"),
    ("ret_gold", "黄金", "%"),
    ("ret_csi", "沪深300", "%"),
    ("ret_hsi", "恒生", "%"),
]

HEATMAP_PAIRS = [
    ("gold_brent", "黄金–布伦特", "ret_gold", "ret_brent"),
    ("gold_dxy", "黄金–美元", "ret_gold", "ret_dxy"),
    ("gold_csi", "黄金–沪深300", "ret_gold", "ret_csi"),
    ("gold_hsi", "黄金–恒生", "ret_gold", "ret_hsi"),
    ("gold_dgpr", "黄金–GPR变动", "ret_gold", "dgpr"),
]

ASSETS = ["gold", "brent", "dxy", "csi", "hsi"]


def completed_month(today: pd.Timestamp | None = None) -> pd.Period:
    today = ASOF if today is None else pd.Timestamp(today).normalize()
    period = today.to_period("M")
    if today.day < int(today.days_in_month):
        return period - 1
    return period


def _series_from_yahoo(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["datetime_utc"], utc=True).dt.tz_convert(None).dt.normalize()
    adj = pd.to_numeric(frame["adjclose"], errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    price = adj.where(adj.notna(), close)
    out = pd.Series(price.to_numpy(), index=pd.DatetimeIndex(dates), name=path.stem)
    out = out[np.isfinite(out.to_numpy()) & (out.to_numpy() > 0)]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def _series_csi() -> pd.Series:
    frame = pd.read_csv(RAW / "csi300_sina.csv")
    dates = pd.to_datetime(frame["date"]).dt.normalize()
    price = pd.to_numeric(frame["close"], errors="coerce")
    out = pd.Series(price.to_numpy(), index=pd.DatetimeIndex(dates), name="csi")
    out = out[np.isfinite(out.to_numpy()) & (out.to_numpy() > 0)]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def _gpr_daily_frame() -> pd.DataFrame:
    frame = pd.read_excel(
        RAW / "data_gpr_daily_recent.xls",
        usecols=["date", "GPRD", "GPRD_ACT", "GPRD_THREAT"],
    )
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ("GPRD", "GPRD_ACT", "GPRD_THREAT"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date"]).drop_duplicates("date", keep="last").set_index("date").sort_index()
    return frame


def _gpr_daily() -> pd.Series:
    out = _gpr_daily_frame()["GPRD"].dropna()
    out.name = "gpr"
    return out


def _monthly_mean_diff(series: pd.Series) -> pd.Series:
    level = series.dropna().resample("ME").mean()
    level.index = level.index.to_period("M")
    return level.diff()


def _month_level_return(series: pd.Series) -> pd.DataFrame:
    level = series.resample("ME").last()
    ret = 100.0 * np.log(level).diff()
    frame = pd.DataFrame({"level": level, "ret": ret})
    frame.index = frame.index.to_period("M")
    return frame


def build_panel(today: pd.Timestamp | None = None) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    daily = {name: _series_from_yahoo(path) for name, path in PRICE_FILES.items()}
    daily["csi"] = _series_csi()
    gpr_daily = _gpr_daily_frame()
    gpr = gpr_daily["GPRD"].dropna()
    gpr.name = "gpr"
    daily["gpr"] = gpr

    pieces = []
    for name in ASSETS:
        part = _month_level_return(daily[name]).rename(columns={"level": name, "ret": f"ret_{name}"})
        pieces.append(part)
    gpr_level = gpr.resample("ME").mean()
    gpr_level.index = gpr_level.index.to_period("M")
    gpr_frame = pd.DataFrame({
        "gpr": gpr_level,
        "dgpr": gpr_level.diff(),
        "dgpr_act": _monthly_mean_diff(gpr_daily["GPRD_ACT"]),
        "dgpr_threat": _monthly_mean_diff(gpr_daily["GPRD_THREAT"]),
    })
    panel = pd.concat(pieces + [gpr_frame], axis=1).sort_index()

    needed = ASSETS + ["gpr", "dgpr"] + [f"ret_{name}" for name in ASSETS]
    complete = panel[needed].notna().all(axis=1)
    if not bool(complete.any()):
        raise RuntimeError("No month has gold, Brent, dollar, CSI 300, Hang Seng, and GPR together.")
    start = panel.index[complete][0]
    clock_end = completed_month(today)
    end = min(panel.index[complete][-1], clock_end, SAMPLE_END)
    if end < start:
        raise RuntimeError(f"Sample end {end} is before sample start {start}.")
    sample = panel.loc[start:end].copy()
    sample = sample.reindex(pd.period_range(start, end, freq="M"))
    months = sample.index.year * 12 + sample.index.month
    if not np.all(np.diff(months) == 1):
        raise RuntimeError("Monthly panel is not a continuous calendar.")
    sample.index.name = "period"
    return sample, daily


def _clip_corr(value: float) -> float:
    return float(max(min(value, 0.9999), -0.9999))


def fisher_z(value: float | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    r = _clip_corr(float(value))
    return 0.5 * np.log((1.0 + r) / (1.0 - r))


def corr_delta_interval(
    before: float | None,
    n_before: int,
    after: float | None,
    n_after: int,
) -> dict[str, float | None]:
    """Approximate 90% interval for after-minus-before correlation change."""
    z1 = fisher_z(before)
    z2 = fisher_z(after)
    if z1 is None or z2 is None or n_before < 4 or n_after < 4:
        return {"delta": None, "lo": None, "hi": None}
    delta = z2 - z1
    se = float(np.sqrt(1.0 / (n_before - 3) + 1.0 / (n_after - 3)))
    return {
        "delta": round(float(after - before), 4),
        "lo": round(float(np.tanh(delta - 1.645 * se)), 4),
        "hi": round(float(np.tanh(delta + 1.645 * se)), 4),
    }


def pearson(x: np.ndarray, y: np.ndarray, min_n: int = 4) -> tuple[float | None, int]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    n = int(x.size)
    if n < min_n:
        return None, n
    if float(np.std(x)) <= 1e-12 or float(np.std(y)) <= 1e-12:
        return None, n
    return float(np.corrcoef(x, y)[0, 1]), n


def haven_from_frame(block: pd.DataFrame, min_n: int = 4) -> dict | None:
    pairs = {
        "corr_gold_csi": pearson(block["ret_gold"], block["ret_csi"], min_n),
        "corr_gold_hsi": pearson(block["ret_gold"], block["ret_hsi"], min_n),
        "corr_gold_dgpr": pearson(block["ret_gold"], block["dgpr"], min_n),
        "corr_gold_dxy": pearson(block["ret_gold"], block["ret_dxy"], min_n),
        "corr_gold_brent": pearson(block["ret_gold"], block["ret_brent"], min_n),
    }
    core = ["corr_gold_csi", "corr_gold_hsi", "corr_gold_dgpr", "corr_gold_dxy"]
    if any(pairs[key][0] is None for key in core):
        return None
    c_csi = pairs["corr_gold_csi"][0]
    c_hsi = pairs["corr_gold_hsi"][0]
    c_gpr = pairs["corr_gold_dgpr"][0]
    c_dxy = pairs["corr_gold_dxy"][0]
    equity = 50.0 * (1.0 - (c_csi + c_hsi) / 2.0)
    gpr_link = 50.0 * (1.0 + c_gpr)
    dollar = 50.0 * (1.0 - c_dxy)
    return {
        "score": (equity + gpr_link + dollar) / 3.0,
        "equity": equity,
        "gpr_link": gpr_link,
        "dollar": dollar,
        "n": int(min(pairs[key][1] for key in core)),
        **{key: pairs[key][0] for key in pairs},
    }


def add_rolling(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    n = len(out)
    score = np.full(n, np.nan)
    equity = np.full(n, np.nan)
    gpr_link = np.full(n, np.nan)
    dollar = np.full(n, np.nan)
    high = np.full(n, np.nan)
    gpr = out["gpr"].to_numpy(dtype=float)
    for i in range(n):
        if i >= GPR_WIN - 1:
            hist = gpr[i - GPR_WIN + 1 : i + 1]
            hist = hist[np.isfinite(hist)]
            if hist.size >= 48 and np.isfinite(gpr[i]):
                high[i] = float(gpr[i] >= np.quantile(hist, GPR_Q))
        if i < ROLL - 1:
            continue
        block = out.iloc[i - ROLL + 1 : i + 1]
        stats = haven_from_frame(block, min_n=24)
        if stats is None:
            continue
        score[i] = stats["score"]
        equity[i] = stats["equity"]
        gpr_link[i] = stats["gpr_link"]
        dollar[i] = stats["dollar"]
    out["haven_score"] = score
    out["haven_equity"] = equity
    out["haven_gpr"] = gpr_link
    out["haven_dollar"] = dollar
    out["high_gpr"] = high
    lo = np.full(n, np.nan)
    hi = np.full(n, np.nan)
    for i in range(n):
        if not np.isfinite(score[i]):
            continue
        bounds = _haven_weight_envelope(equity[i], gpr_link[i], dollar[i])
        if bounds is None:
            continue
        lo[i], hi[i] = bounds
    out["haven_lo"] = lo
    out["haven_hi"] = hi
    out["haven_pc1"] = _haven_pc1(equity, gpr_link, dollar, score)
    return out


def _haven_weight_envelope(equity: float, gpr_link: float, dollar: float) -> tuple[float, float] | None:
    """Score range when each of the three legs keeps a weight in [0.15, 0.70]."""
    if not all(np.isfinite(v) for v in (equity, gpr_link, dollar)):
        return None
    low, high = 1e9, -1e9
    for a in np.arange(0.15, 0.701, 0.05):
        for b in np.arange(0.15, 0.701, 0.05):
            c = 1.0 - float(a) - float(b)
            if c < 0.149 or c > 0.701:
                continue
            value = float(a) * equity + float(b) * gpr_link + c * dollar
            low = min(low, value)
            high = max(high, value)
    if not np.isfinite(low):
        return None
    return low, high


def _haven_pc1(equity: np.ndarray, gpr_link: np.ndarray, dollar: np.ndarray, score: np.ndarray) -> np.ndarray:
    """First principal component of the three legs, scaled to sit near the 0–100 score."""
    comp = np.column_stack([equity, gpr_link, dollar])
    out = np.full(comp.shape[0], np.nan)
    mask = np.isfinite(comp).all(axis=1) & np.isfinite(score)
    if int(mask.sum()) < 30:
        return out
    z = comp[mask]
    std = z.std(axis=0, ddof=1)
    std[std < 1e-8] = 1.0
    z = (z - z.mean(axis=0)) / std
    _u, _s, vt = np.linalg.svd(z, full_matrices=False)
    mapped = z @ vt[0]
    if np.corrcoef(mapped, score[mask])[0, 1] < 0:
        mapped = -mapped
    zz = (mapped - mapped.mean()) / (mapped.std(ddof=1) or 1.0)
    out[np.flatnonzero(mask)] = np.clip(50.0 + 15.0 * zz, 0.0, 100.0)
    return out


def _finite_sum(series: pd.Series) -> tuple[float | None, int]:
    values = series.to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return None, 0
    return float(values.sum()), int(values.size)


def event_window(panel: pd.DataFrame, month: str, width: int) -> dict:
    period = pd.Period(month, freq="M")
    if period not in panel.index:
        raise KeyError(month)
    i = panel.index.get_loc(period)
    b0 = i - width
    a1 = i + width
    partial = b0 < 0 or a1 > len(panel)
    before = panel.iloc[max(0, b0) : i]
    after = panel.iloc[i : min(len(panel), a1)]
    haven_before = haven_from_frame(before, min_n=4)
    haven_after = haven_from_frame(after, min_n=4)
    cums = {}
    counts = {}
    for name in ASSETS:
        total, n = _finite_sum(after[f"ret_{name}"])
        cums[name] = total
        counts[name] = n
    gpr_before, n_gpr_b = _finite_sum(before["gpr"])
    gpr_after, n_gpr_a = _finite_sum(after["gpr"])
    return {
        "month": month,
        "width": width,
        "partial": bool(partial or counts["gold"] < width or counts["csi"] < width),
        "n_before": int(len(before)),
        "n_after": int(counts["gold"]),
        "cum": cums,
        "haven_before": haven_before,
        "haven_after": haven_after,
        "gpr_before": None if n_gpr_b == 0 else gpr_before / n_gpr_b,
        "gpr_after": None if n_gpr_a == 0 else gpr_after / n_gpr_a,
    }


def rolling_corr_frame(panel: pd.DataFrame) -> pd.DataFrame:
    columns = {}
    n = len(panel)
    for key, _label, left, right in HEATMAP_PAIRS:
        values = np.full(n, np.nan)
        for i in range(ROLL - 1, n):
            block = panel.iloc[i - ROLL + 1 : i + 1]
            corr, _count = pearson(block[left], block[right], min_n=24)
            if corr is not None:
                values[i] = corr
        columns[key] = values
    return pd.DataFrame(columns, index=panel.index)


def heatmap_payload(corrs: pd.DataFrame) -> dict:
    labels = []
    columns = {key: [] for key, *_rest in HEATMAP_PAIRS}
    for period, row in corrs.iterrows():
        if int(period.month) not in (3, 6, 9, 12):
            continue
        if not np.isfinite(row.to_numpy(dtype=float)).any():
            continue
        labels.append(f"{period.year}Q{period.quarter}")
        for key, *_rest in HEATMAP_PAIRS:
            value = row[key]
            columns[key].append(None if not np.isfinite(value) else round(float(value), 3))
    return {
        "labels": labels,
        "pairs": [
            {"id": key, "name": label, "values": columns[key]}
            for key, label, *_rest in HEATMAP_PAIRS
        ],
    }


def _predict_row(coefs: np.ndarray, intercept: np.ndarray, history: np.ndarray, t: int) -> np.ndarray:
    predicted = intercept.copy()
    for lag in range(coefs.shape[0]):
        predicted = predicted + coefs[lag] @ history[t - 1 - lag]
    return predicted


def _oriented_coefs(result, history: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    coefs = np.asarray(result.coefs, dtype=float)
    intercept = np.ravel(np.asarray(result.intercept, dtype=float))
    p = int(result.k_ar)
    fitted = np.asarray(result.fittedvalues, dtype=float)[0]
    predicted = _predict_row(coefs, intercept, history, p)
    if np.allclose(predicted, fitted, atol=1e-5):
        return coefs, intercept
    flipped = np.transpose(coefs, (0, 2, 1))
    predicted = _predict_row(flipped, intercept, history, p)
    if np.allclose(predicted, fitted, atol=1e-5):
        return flipped, intercept
    raise RuntimeError("Could not match the VAR companion coefficients to fitted values.")


def fit_var(panel: pd.DataFrame) -> dict:
    columns = [item[0] for item in VAR_SPEC]
    endog = panel[columns].dropna().astype(float)
    if len(endog) < 80:
        raise RuntimeError(f"VAR sample is too short: {len(endog)} months.")
    selector = VAR(endog).select_order(VAR_MAXLAG)
    lag = int(selector.selected_orders["aic"])
    if lag < 1:
        lag = 1
    result = VAR(endog).fit(lag)
    history = endog.to_numpy(dtype=float)
    coefs, intercept = _oriented_coefs(result, history)
    point = np.cumsum(result.irf(VAR_HORIZON).orth_irfs[:, :, 0], axis=0)
    if point[0, 0] < 0:
        point = -point
    resid = np.asarray(result.resid, dtype=float)
    p = lag
    t_obs = history.shape[0]
    rng = np.random.default_rng(BOOT_SEED)
    draws = []
    for _rep in range(BOOT_REPS):
        simulated = np.empty_like(history)
        simulated[:p] = history[:p]
        shocks = resid[rng.integers(0, resid.shape[0], size=t_obs - p)]
        for t in range(p, t_obs):
            simulated[t] = _predict_row(coefs, intercept, simulated, t) + shocks[t - p]
        try:
            replicated = VAR(simulated).fit(p)
            cumulative = np.cumsum(replicated.irf(VAR_HORIZON).orth_irfs[:, :, 0], axis=0)
        except Exception:
            continue
        if cumulative[0, 0] < 0:
            cumulative = -cumulative
        if not np.isfinite(cumulative).all() or np.max(np.abs(cumulative)) > 1e4:
            continue
        draws.append(cumulative)
    if len(draws) < 40:
        raise RuntimeError(f"VAR bootstrap kept only {len(draws)} draws.")
    stack = np.stack(draws, axis=0)
    lower = np.quantile(stack, 0.05, axis=0)
    upper = np.quantile(stack, 0.95, axis=0)
    names = [item[1] for item in VAR_SPEC]
    units = [item[2] for item in VAR_SPEC]
    keys = [item[0] for item in VAR_SPEC]

    def pack(matrix: np.ndarray) -> dict[str, list[float]]:
        return {key: [round(float(value), 4) for value in matrix[:, index]] for index, key in enumerate(keys)}

    aic_raw = selector.ics["aic"]
    if isinstance(aic_raw, dict):
        aic_pairs = aic_raw.items()
    elif hasattr(aic_raw, "items") and not isinstance(aic_raw, list):
        aic_pairs = aic_raw.items()
    else:
        aic_pairs = enumerate(aic_raw)
    aic_table = {str(int(candidate)): round(float(value), 3) for candidate, value in aic_pairs}
    lp = fit_local_projection(panel)
    return {
        "lags": lag,
        "t": int(len(endog)),
        "aic": aic_table,
        "order": names,
        "units": units,
        "keys": keys,
        "horizon": list(range(VAR_HORIZON + 1)),
        "cum": pack(point),
        "lo": pack(lower),
        "hi": pack(upper),
        "lp": lp,
        "n_boot": BOOT_REPS,
        "boot_kept": int(len(draws)),
        "sample_start": str(endog.index[0]),
        "sample_end": str(endog.index[-1]),
    }


LP_KEYS = ["ret_brent", "ret_dxy", "ret_gold", "ret_csi", "ret_hsi"]
CAR_WINDOWS = {"m1_p5": (-1, 5), "m1_p20": (-1, 20), "p0_p40": (0, 40)}


def _two_sided_normal_p(stat: float) -> float:
    return float(math.erfc(abs(stat) / math.sqrt(2.0)))


def _bh_qvalues(pvals: np.ndarray) -> np.ndarray:
    m = int(pvals.size)
    if m == 0:
        return pvals
    order = np.argsort(pvals)
    ranked = pvals[order]
    q = np.empty(m, dtype=float)
    running = 1.0
    for i in range(m - 1, -1, -1):
        running = min(running, float(ranked[i]) * m / (i + 1))
        q[i] = running
    out = np.empty(m, dtype=float)
    out[order] = np.clip(q, 0.0, 1.0)
    return out


def local_projection_response(
    target: pd.Series,
    shock: pd.Series,
    horizon: int = VAR_HORIZON,
    controls: pd.DataFrame | None = None,
    scale: float = 1.0,
    min_n: int = 40,
) -> dict[str, list]:
    """Direct regression of the h-step cumulative outcome on the shock.

    The dependent variable at horizon h is already the sum of outcomes from 0
    through h. The coefficient is the cumulative response. It is not added to
    the previous horizon.
    """
    import statsmodels.api as sm
    from statsmodels.regression.linear_model import OLS

    cum: list = []
    lo: list = []
    hi: list = []
    for h in range(horizon + 1):
        y = target if h == 0 else target.rolling(h + 1).sum().shift(-h)
        pieces = [y.rename("y"), shock.rename("shock")]
        if controls is not None:
            pieces.append(controls)
        reg = pd.concat(pieces, axis=1).dropna()
        xcols = ["shock"] + [col for col in reg.columns if col not in ("y", "shock")]
        if len(reg) < min_n or float(reg["shock"].std(ddof=1) or 0) < 1e-8:
            cum.append(None)
            lo.append(None)
            hi.append(None)
            continue
        model = OLS(reg["y"], sm.add_constant(reg[xcols])).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": max(1, h + 1)},
        )
        beta = float(model.params["shock"]) * scale
        se = float(model.bse["shock"]) * abs(scale)
        cum.append(round(beta, 4))
        lo.append(round(beta - 1.645 * se, 4))
        hi.append(round(beta + 1.645 * se, 4))
    return {"cum": cum, "lo": lo, "hi": hi}


def _pack_lp(frame: pd.DataFrame, shock: pd.Series, scale: float, controls: pd.DataFrame | None, horizon: int) -> dict:
    packed = {}
    for key in LP_KEYS:
        packed[key] = local_projection_response(frame[key], shock, horizon, controls, scale)
    return {
        "cum": {key: packed[key]["cum"] for key in LP_KEYS},
        "lo": {key: packed[key]["lo"] for key in LP_KEYS},
        "hi": {key: packed[key]["hi"] for key in LP_KEYS},
        "scale": round(float(scale), 4),
    }


def fit_local_projection(panel: pd.DataFrame, horizon: int = VAR_HORIZON) -> dict:
    """Local projections of cumulative returns on a one-standard-deviation GPR move."""
    needed = ["dgpr", "dgpr_act", "dgpr_threat", *LP_KEYS]
    frame = panel[needed].dropna().astype(float)
    total_sd = float(frame["dgpr"].std(ddof=1))
    act_sd = float(frame["dgpr_act"].std(ddof=1) or 1.0)
    threat_sd = float(frame["dgpr_threat"].std(ddof=1) or 1.0)
    total = _pack_lp(frame, frame["dgpr"], total_sd, None, horizon)
    act = _pack_lp(frame, frame["dgpr_act"], act_sd, None, horizon)
    threat = _pack_lp(frame, frame["dgpr_threat"], threat_sd, None, horizon)
    state = _state_local_projection(panel, frame, total_sd, horizon)
    return {
        "horizon": list(range(horizon + 1)),
        "cum": total["cum"],
        "lo": total["lo"],
        "hi": total["hi"],
        "total": total,
        "act": act,
        "threat": threat,
        "state": state,
        "note": "Each horizon regresses the cumulative return on a 1 SD shock. HAC 90% band. Not structural.",
    }


def _state_local_projection(panel: pd.DataFrame, frame: pd.DataFrame, scale: float, horizon: int) -> dict:
    """Split the GPR move by whether the previous month was a high-GPR month."""
    if "high_gpr" not in panel.columns:
        return {"high": None, "low": None}
    regime = panel["high_gpr"].astype(float).shift(1).reindex(frame.index)
    usable = frame.loc[regime.notna()].copy()
    flag = regime.loc[regime.notna()].astype(float)
    if usable.empty or float(flag.sum()) < 24 or float((1 - flag).sum()) < 24:
        return {"high": None, "low": None, "note": "Too few months in one regime."}
    shock = usable["dgpr"]
    controls = pd.DataFrame({"regime": flag.to_numpy()}, index=usable.index)
    high_shock = shock * flag.to_numpy()
    low_shock = shock * (1.0 - flag.to_numpy())
    high = _pack_lp(usable, high_shock, scale, controls, horizon)
    low = _pack_lp(usable, low_shock, scale, controls, horizon)
    return {
        "high": high,
        "low": low,
        "n_high": int(flag.sum()),
        "n_low": int((1 - flag).sum()),
        "note": "Lagged high-GPR state. Both coefficients are scaled by the full-sample SD of dgpr.",
    }


def daily_event_study(daily: dict[str, pd.Series], events: list[dict] | None = None) -> dict:
    """Mean-adjusted cumulative abnormal returns on trading-day windows."""
    events = EVENTS if events is None else events
    returns = {}
    for name in ASSETS:
        series = daily.get(name)
        if series is None or series.empty:
            continue
        ret = 100.0 * np.log(series[series > 0]).diff().dropna()
        returns[name] = ret
    by_event: dict[str, dict] = {}
    buckets: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for event in events:
        stamp = pd.Timestamp(event["date"]).normalize()
        by_event[event["id"]] = {}
        for name, ret in returns.items():
            loc = int(ret.index.searchsorted(stamp))
            if loc < 130 or loc >= len(ret):
                continue
            est = ret.iloc[loc - 120 : loc - 20]
            if len(est) < 60:
                continue
            mu = float(est.mean())
            sigma = float(est.std(ddof=1))
            if sigma < 1e-8:
                continue
            asset_out: dict[str, dict] = {}
            for key, (left, right) in CAR_WINDOWS.items():
                start = loc + left
                stop = loc + right + 1
                if start < 0 or stop > len(ret):
                    continue
                window = ret.iloc[start:stop]
                if len(window) < (right - left + 1):
                    continue
                car = float((window - mu).sum())
                stat = car / (sigma * math.sqrt(len(window)))
                pval = _two_sided_normal_p(stat)
                asset_out[key] = {
                    "car": round(car, 3),
                    "t": round(stat, 3),
                    "p": round(pval, 4),
                    "n": int(len(window)),
                }
                buckets.setdefault((name, key), []).append((event["id"], pval))
            if asset_out:
                by_event[event["id"]][name] = asset_out
    for (name, key), items in buckets.items():
        qvals = _bh_qvalues(np.array([item[1] for item in items], dtype=float))
        for (event_id, _pval), qval in zip(items, qvals):
            by_event[event_id][name][key]["q"] = round(float(qval), 4)
    return {
        "windows": [{"id": key, "from": left, "to": right} for key, (left, right) in CAR_WINDOWS.items()],
        "method": "Mean-adjusted CAR. Estimation window is trading days [-120, -20]. Two-sided normal p. BH q is across events inside one asset and window.",
        "by_event": by_event,
    }


def gold_jump_sensitivity(panel: pd.DataFrame, daily: dict[str, pd.Series]) -> dict | None:
    series = daily.get("gold")
    if series is None or series.empty:
        return None
    series = series[series > 0].sort_index()
    stamp = pd.Timestamp("2026-01-30")
    if stamp not in series.index:
        return {"status": "missing", "date": "2026-01-30"}
    change = 100.0 * np.log(series).diff()
    january = (series.index >= "2026-01-01") & (series.index <= "2026-01-31")
    raw = float(change.loc[january].sum())
    adjusted = change.copy()
    adjusted.loc[stamp] = 0.0
    ex_jump = float(adjusted.loc[january].sum())
    month = pd.Period("2026-01", freq="M")
    published = None if month not in panel.index else float(panel.loc[month, "ret_gold"])
    return {
        "status": "ok",
        "date": "2026-01-30",
        "daily_log_pct": round(float(change.loc[stamp]), 2),
        "january_sum_daily": round(raw, 2),
        "january_ex_jump": round(ex_jump, 2),
        "january_month_end": None if published is None or not np.isfinite(published) else round(published, 2),
        "note": "ex_jump sets the 30 Jan 2026 log move to zero and keeps the other January sessions.",
    }


def optional_macro_monthly() -> dict[str, dict]:
    """Monthly log returns for optional series. Missing files are skipped."""
    files = {
        "silver": RAW / "silver_si.csv",
        "vix": RAW / "vix.csv",
        "ust10": RAW / "ust10.csv",
    }
    out: dict[str, dict] = {}
    for name, path in files.items():
        if not path.exists():
            continue
        try:
            month = _month_level_return(_series_from_yahoo(path))
        except Exception:
            continue
        out[name] = {
            "months": [str(period) for period in month.index],
            "ret": _list_or_none(month["ret"], 4),
        }
    tips = RAW / "tips10_fred.csv"
    if tips.exists():
        try:
            frame = pd.read_csv(tips)
            date_col = "DATE" if "DATE" in frame.columns else frame.columns[0]
            value_col = "DFII10" if "DFII10" in frame.columns else frame.columns[-1]
            series = pd.Series(
                pd.to_numeric(frame[value_col], errors="coerce").to_numpy(),
                index=pd.to_datetime(frame[date_col]),
            ).dropna()
            level = series.resample("ME").last()
            level.index = level.index.to_period("M")
            out["tips10"] = {
                "months": [str(period) for period in level.index],
                "level": _list_or_none(level, 4),
                "change": _list_or_none(level.diff(), 4),
            }
        except Exception:
            pass
    return out


def _panel_from_derived(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "month" not in frame.columns:
        raise RuntimeError(f"{path} has no month column.")
    frame.index = pd.PeriodIndex(frame["month"].astype(str), freq="M")
    frame.index.name = "period"
    needed = ["gold", "brent", "dxy", "csi", "hsi", "gpr", "dgpr"] + [f"ret_{name}" for name in ASSETS]
    missing = [col for col in needed if col not in frame.columns]
    if missing:
        raise RuntimeError(f"Derived panel is missing {missing}.")
    for col in ("dgpr_act", "dgpr_threat"):
        if col not in frame.columns:
            frame[col] = np.nan
    return frame.sort_index()


def trading_path(series: pd.Series, event_date: str, sessions: int = MAX_SESSIONS) -> dict:
    event = pd.Timestamp(event_date).normalize()
    pre = series[series.index < event].iloc[-sessions:]
    post = series[series.index >= event].iloc[:sessions]
    if pre.empty:
        return {"tau": [], "value": [], "date": []}
    base = float(pre.iloc[-1])
    tau: list[int] = []
    value: list[float] = []
    dates: list[str] = []
    for i, (stamp, price) in enumerate(pre.items()):
        tau.append(i - len(pre))
        value.append(100.0 * float(price) / base)
        dates.append(pd.Timestamp(stamp).strftime("%Y-%m-%d"))
    for i, (stamp, price) in enumerate(post.items()):
        tau.append(i)
        value.append(100.0 * float(price) / base)
        dates.append(pd.Timestamp(stamp).strftime("%Y-%m-%d"))
    return {"tau": tau, "value": value, "date": dates}


def gpr_on_gold_clock(gold_path: dict, gpr: pd.Series) -> dict:
    levels = []
    for text in gold_path["date"]:
        stamp = pd.Timestamp(text)
        if stamp in gpr.index:
            levels.append(round(float(gpr.loc[stamp]), 2))
        else:
            levels.append(None)
    return {"tau": gold_path["tau"], "value": levels, "date": gold_path["date"]}


def gold_daily_jumps(series: pd.Series, n: int = 2) -> list[dict]:
    """Largest daily log drops in the futures series, in percent."""
    price = series[series > 0].sort_index()
    change = 100.0 * np.log(price).diff()
    worst = change.nsmallest(n)
    rows = []
    for stamp, value in worst.items():
        loc = price.index.get_loc(stamp)
        prev = float(price.iloc[loc - 1]) if loc else None
        nxt = [float(price.iloc[loc + k]) for k in (1, 2) if loc + k < len(price)]
        rows.append(
            {
                "date": pd.Timestamp(stamp).strftime("%Y-%m-%d"),
                "log_return": round(float(value), 2),
                "close": round(float(price.loc[stamp]), 1),
                "prev_close": None if prev is None else round(prev, 1),
                "next_closes": [round(item, 1) for item in nxt],
            }
        )
    return rows


def _placebo_event_idx(panel: pd.DataFrame, events: list[dict]) -> set[int]:
    event_idx: set[int] = set()
    for event in events:
        month = str(event.get("month") or pd.Timestamp(event["date"]).to_period("M"))
        period = pd.Period(month, freq="M")
        if period not in panel.index:
            continue
        event_idx.add(int(panel.index.get_loc(period)))
    return event_idx


def _placebo_pools(panel: pd.DataFrame, events: list[dict], width: int, *, step: int) -> dict[str, list[float]]:
    event_idx = _placebo_event_idx(panel, events)
    gold: list[float] = []
    excess: list[float] = []
    haven: list[float] = []
    for i in range(0, len(panel) - width + 1, step):
        if any(k in event_idx for k in range(i, i + width)):
            continue
        window = event_window(panel, str(panel.index[i]), width)
        if window["partial"] or window["n_after"] < width or window["cum"]["gold"] is None:
            continue
        gold.append(float(window["cum"]["gold"]))
        csi = window["cum"]["csi"]
        if csi is not None:
            excess.append(float(window["cum"]["gold"] - csi))
        score = (window["haven_after"] or {}).get("score")
        if score is not None:
            haven.append(float(score))
    return {"gold": gold, "gold_excess_csi": excess, "haven": haven}


def _draw_placebo(pool: dict[str, list[float]], n_draw: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    out: dict = {"seed": seed}
    for key, values in pool.items():
        take = min(n_draw, len(values))
        if take == 0:
            out[key] = []
            out[f"n_{key}"] = 0
            continue
        picked = values if take == len(values) else [values[int(j)] for j in rng.choice(len(values), size=take, replace=False)]
        out[key] = [round(float(value), 4) for value in sorted(picked)]
        out[f"n_{key}"] = len(values)
    out["n_draw"] = len(out.get("gold") or [])
    return out


def placebo_sample(panel: pd.DataFrame, events: list[dict], width: int, n_draw: int = PLACEBO_DRAW, seed: int = PLACEBO_SEED) -> dict:
    """Overlapping-window placebo draw (legacy flat gold list)."""
    pool = _placebo_pools(panel, events, width, step=1)
    drawn = _draw_placebo(pool, n_draw, seed)
    return {
        "seed": seed,
        "n_pool": drawn.get("n_gold", 0),
        "n_draw": drawn["n_draw"],
        "gold": drawn["gold"],
    }


def placebo_bundle(panel: pd.DataFrame, events: list[dict], width: int, n_draw: int = PLACEBO_DRAW, seed: int = PLACEBO_SEED) -> dict:
    overlap_pool = _placebo_pools(panel, events, width, step=1)
    blocked_pool = _placebo_pools(panel, events, width, step=width)
    overlap = _draw_placebo(overlap_pool, n_draw, seed)
    blocked = _draw_placebo(blocked_pool, n_draw, seed + 1)
    overlap["mode"] = "overlapping"
    blocked["mode"] = "blocked_nonoverlap"
    return {
        "overlapping": overlap,
        "blocked": blocked,
        "seed": seed,
        "gold": blocked["gold"],
        "gold_excess_csi": blocked.get("gold_excess_csi") or [],
        "haven": blocked.get("haven") or [],
        "n_pool": blocked.get("n_gold", 0),
        "n_draw": blocked["n_draw"],
    }


def _round_or_none(value, digits: int):
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def _list_or_none(series: pd.Series, digits: int) -> list:
    return [_round_or_none(value, digits) for value in series.to_numpy(dtype=float)]


def build_lab(today: pd.Timestamp | None = None, from_derived: bool = False) -> dict:
    if from_derived:
        panel = add_rolling(_panel_from_derived(ROOT / "replication" / "panel_monthly.csv"))
        daily = {name: pd.Series(dtype=float) for name in ASSETS + ["gpr"]}
    else:
        panel, daily = build_panel(today)
        panel = add_rolling(panel)
    corrs = rolling_corr_frame(panel)
    var = fit_var(panel)
    events = []
    has_daily = not from_derived and not daily["gold"].empty
    for event in EVENTS:
        if has_daily:
            paths = {name: trading_path(daily[name], event["date"]) for name in ASSETS}
            paths["gpr"] = gpr_on_gold_clock(paths["gold"], daily["gpr"])
        else:
            paths = {}
        events.append({**event, "month": str(pd.Timestamp(event["date"]).to_period("M")), "path": paths})
    if has_daily:
        check_path = trading_path(daily["gold"], "2026-03-02", sessions=60)
        check_tau = 10
        check_index = check_path["tau"].index(check_tau)
        check = {"date": "2026-03-02", "tau": check_tau, "gold": round(check_path["value"][check_index], 4)}
        jumps = gold_daily_jumps(daily["gold"], n=2)
        lbma = _gold_lbma_check(daily["gold"])
        car = daily_event_study(daily, EVENTS)
        jump_check = gold_jump_sensitivity(panel, daily)
    else:
        check = {"date": "2026-03-02", "tau": 10, "gold": None}
        jumps = []
        lbma = None
        car = {"windows": [], "method": "skipped", "by_event": {}}
        jump_check = None
    web_daily = {}
    for name, series in daily.items():
        if series.empty:
            continue
        clipped = series[series.index >= "2007-01-01"]
        digits = 2 if name == "gpr" else 4
        web_daily[name] = {
            "dates": [pd.Timestamp(stamp).strftime("%Y-%m-%d") for stamp in clipped.index],
            "close": [round(float(value), digits) for value in clipped.to_numpy(dtype=float)],
        }
    return {
        "panel": panel,
        "daily": daily,
        "corrs": corrs,
        "var": var,
        "events": events,
        "web_daily": web_daily,
        "check": check,
        "placebo": {str(width): placebo_bundle(panel, events, width) for width in (6, 12, 24)},
        "gold_jumps": jumps,
        "gold_lbma": lbma,
        "car": car,
        "gold_jump_check": jump_check,
        "macro": {} if from_derived else optional_macro_monthly(),
        "from_derived": bool(from_derived),
    }


def _gold_lbma_check(gold_futures: pd.Series) -> dict | None:
    path = RAW / "gold_lbma_fred.csv"
    if not path.exists():
        return None
    try:
        lbma = pd.read_csv(path)
        col = "GOLDAMGBD228NLBM" if "GOLDAMGBD228NLBM" in lbma.columns else lbma.columns[-1]
        lbma["date"] = pd.to_datetime(lbma["DATE"] if "DATE" in lbma.columns else lbma.iloc[:, 0])
        spot = pd.Series(pd.to_numeric(lbma[col], errors="coerce").values, index=lbma["date"]).dropna()
        stamp = pd.Timestamp("2026-01-30")
        if stamp not in gold_futures.index or stamp not in spot.index:
            return {"status": "partial", "note": "LBMA file present but 2026-01-30 missing on one side."}
        f_ret = 100.0 * np.log(gold_futures.loc[stamp] / gold_futures.shift(1).loc[stamp])
        s_ret = 100.0 * np.log(spot.loc[stamp] / spot.shift(1).loc[stamp])
        return {
            "status": "ok",
            "date": "2026-01-30",
            "futures_log_pct": round(float(f_ret), 2),
            "lbma_log_pct": round(float(s_ret), 2),
        }
    except Exception as exc:
        return {"status": "error", "note": str(exc)[:200]}


def summary_rows(panel: pd.DataFrame, widths: tuple[int, ...] = (6, 12)) -> pd.DataFrame:
    rows = []
    for event in EVENTS:
        month = str(pd.Timestamp(event["date"]).to_period("M"))
        for width in widths:
            window = event_window(panel, month, width)
            before = window["haven_before"] or {}
            after = window["haven_after"] or {}
            rows.append(
                {
                    "event_id": event["id"],
                    "event_name": event["name"],
                    "group": event["group"],
                    "event_date": event["date"],
                    "event_month": month,
                    "window_months": width,
                    "partial": int(window["partial"]),
                    "n_before": window["n_before"],
                    "n_after": window["n_after"],
                    "gold_cum": window["cum"]["gold"],
                    "brent_cum": window["cum"]["brent"],
                    "dxy_cum": window["cum"]["dxy"],
                    "csi_cum": window["cum"]["csi"],
                    "hsi_cum": window["cum"]["hsi"],
                    "gold_minus_csi": None
                    if window["cum"]["gold"] is None or window["cum"]["csi"] is None
                    else window["cum"]["gold"] - window["cum"]["csi"],
                    "gold_minus_hsi": None
                    if window["cum"]["gold"] is None or window["cum"]["hsi"] is None
                    else window["cum"]["gold"] - window["cum"]["hsi"],
                    "corr_gold_csi_before": before.get("corr_gold_csi"),
                    "corr_gold_csi_after": after.get("corr_gold_csi"),
                    "corr_gold_hsi_before": before.get("corr_gold_hsi"),
                    "corr_gold_hsi_after": after.get("corr_gold_hsi"),
                    "corr_gold_brent_before": before.get("corr_gold_brent"),
                    "corr_gold_brent_after": after.get("corr_gold_brent"),
                    "corr_gold_dxy_before": before.get("corr_gold_dxy"),
                    "corr_gold_dxy_after": after.get("corr_gold_dxy"),
                    "corr_gold_dgpr_before": before.get("corr_gold_dgpr"),
                    "corr_gold_dgpr_after": after.get("corr_gold_dgpr"),
                    "haven_before": before.get("score"),
                    "haven_after": after.get("score"),
                    "gpr_mean_before": window["gpr_before"],
                    "gpr_mean_after": window["gpr_after"],
                }
            )
    return pd.DataFrame(rows)


def web_payload(lab: dict) -> dict:
    panel: pd.DataFrame = lab["panel"]
    var = lab["var"]
    events = []
    for event in lab["events"]:
        events.append(
            {
                key: event[key]
                for key in (
                    "id",
                    "date",
                    "month",
                    "group",
                    "region",
                    "name",
                    "name_en",
                    "note",
                    "note_en",
                    "source",
                    "source_label",
                    "source_2",
                    "source_2_label",
                    "accessed",
                )
                if key in event
            }
        )
    return {
        "meta": {
            "version": LAB_VERSION,
            "api_version": API_VERSION,
            "event_registry": EVENT_REGISTRY_VERSION,
            "sample_start": str(panel.index[0]),
            "sample_end": str(panel.index[-1]),
            "n_months": int(len(panel)),
            "roll": ROLL,
            "gpr_window": GPR_WIN,
            "haven_on": HAVEN_ON,
            "haven_off": HAVEN_OFF,
            "var_lags": var["lags"],
            "var_t": var["t"],
            "var_boot": var["boot_kept"],
            "built": ASOF.strftime("%Y-%m-%d"),
            "sample_pin": str(SAMPLE_END),
            "check": lab["check"],
            "gold_jumps": lab.get("gold_jumps") or [],
            "gold_lbma": lab.get("gold_lbma"),
            "gold_jump_check": lab.get("gold_jump_check"),
            "from_derived": bool(lab.get("from_derived")),
            "macro": sorted((lab.get("macro") or {}).keys()),
        },
        "months": [str(period) for period in panel.index],
        "ret": {name: _list_or_none(panel[f"ret_{name}"], 6) for name in ASSETS},
        "dgpr": _list_or_none(panel["dgpr"], 4),
        "dgpr_act": _list_or_none(panel["dgpr_act"], 4),
        "dgpr_threat": _list_or_none(panel["dgpr_threat"], 4),
        "gpr": _list_or_none(panel["gpr"], 2),
        "level": {name: _list_or_none(panel[name], 4) for name in ASSETS},
        "haven": {
            "score": _list_or_none(panel["haven_score"], 2),
            "equity": _list_or_none(panel["haven_equity"], 2),
            "gpr_link": _list_or_none(panel["haven_gpr"], 2),
            "dollar": _list_or_none(panel["haven_dollar"], 2),
            "lo": _list_or_none(panel["haven_lo"], 2),
            "hi": _list_or_none(panel["haven_hi"], 2),
            "pc1": _list_or_none(panel["haven_pc1"], 2),
            "high": [None if not np.isfinite(value) else int(value) for value in panel["high_gpr"].to_numpy(dtype=float)],
        },
        "heatmap": heatmap_payload(lab["corrs"]),
        "var": {
            "lags": var["lags"],
            "t": var["t"],
            "order": var["order"],
            "units": var["units"],
            "keys": var["keys"],
            "horizon": var["horizon"],
            "cum": var["cum"],
            "lo": var["lo"],
            "hi": var["hi"],
            "boot_kept": var["boot_kept"],
            "sample_start": var["sample_start"],
            "sample_end": var["sample_end"],
            "lp": var.get("lp"),
        },
        "events": events,
        "placebo": lab.get("placebo") or {},
        "daily": lab["web_daily"],
        "windows": _window_corr_payload(panel),
        "car": lab.get("car") or {},
        "macro": lab.get("macro") or {},
    }


def _window_corr_payload(panel: pd.DataFrame) -> dict:
    out: dict = {}
    for event in EVENTS:
        month = str(pd.Timestamp(event["date"]).to_period("M"))
        out[event["id"]] = {}
        for width in (6, 12, 24):
            try:
                window = event_window(panel, month, width)
            except KeyError:
                continue
            before = window["haven_before"] or {}
            after = window["haven_after"] or {}
            out[event["id"]][str(width)] = {
                "corr_gold_csi": corr_delta_interval(
                    before.get("corr_gold_csi"),
                    window["n_before"],
                    after.get("corr_gold_csi"),
                    window["n_after"],
                )
            }
    return out


def split_web_payload(payload: dict) -> tuple[dict, dict]:
    daily = {"daily": payload.pop("daily")}
    return payload, daily


def canvas_payload(lab: dict) -> dict:
    full = web_payload(lab)
    full.pop("daily", None)
    full.pop("level", None)
    slim_events = []
    for event in lab["events"]:
        fixed = {}
        for name in ASSETS + ["gpr"]:
            packed = (event.get("path") or {}).get(name) or {"tau": [], "value": []}
            slot = [None] * (MAX_SESSIONS * 2)
            for tau, val in zip(packed["tau"], packed["value"]):
                index = int(tau) + MAX_SESSIONS
                if val is None or not (0 <= index < len(slot)):
                    continue
                slot[index] = round(float(val), 2)
            fixed[name] = slot
        slim_events.append(
            {
                "id": event["id"],
                "date": event["date"],
                "month": event["month"],
                "group": event["group"],
                "name": event["name"],
                "note": event["note"],
                "source": event.get("source"),
                "source_label": event.get("source_label"),
                "source_2": event.get("source_2"),
                "source_2_label": event.get("source_2_label"),
                "accessed": event.get("accessed"),
                "path": fixed,
            }
        )
    full["events"] = slim_events
    full["path_origin"] = -MAX_SESSIONS
    return full


def _write_car_table(car: dict, path: Path) -> None:
    rows = []
    for event_id, assets in (car.get("by_event") or {}).items():
        for asset, windows in assets.items():
            for window_id, stats in windows.items():
                rows.append({"event_id": event_id, "asset": asset, "window": window_id, **stats})
    pd.DataFrame(rows).to_csv(path, index=False)


def write_tables(lab: dict, output: Path) -> pd.DataFrame:
    output.mkdir(parents=True, exist_ok=True)
    panel: pd.DataFrame = lab["panel"]
    table = panel.copy()
    table.insert(0, "month", [str(period) for period in table.index])
    table.to_csv(output / "panel_monthly.csv", index=False)
    summary = summary_rows(panel)
    summary.to_csv(output / "event_window_summary.csv", index=False)
    _write_car_table(lab.get("car") or {}, output / "event_daily_car.csv")
    provenance = {
        "built": ASOF.strftime("%Y-%m-%d"),
        "sample_pin": str(SAMPLE_END),
        "sample": [str(panel.index[0]), str(panel.index[-1])],
        "gpr": "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls",
        "gold": "Yahoo Finance GC=F, COMEX front gold future",
        "brent": "Yahoo Finance BZ=F, ICE Brent front future",
        "dxy": "Yahoo Finance DX-Y.NYB, ICE US Dollar Index",
        "hsi": "Yahoo Finance ^HSI",
        "csi300": "Sina Finance sh000300 via akshare, price index",
        "returns": "100 * log month-end price change; not excess of the risk-free rate",
        "haven": "equal weight of equity hedge, GPR co-movement, and dollar hedge; 50 is zero correlation. Site-defined, not a literature index.",
        "placebo": f"seed {PLACEBO_SEED}; overlapping pool plus blocked non-overlapping draw ({PLACEBO_DRAW})",
        "lp": "direct local projection of cumulative returns on a 1 SD shock; state split uses lagged high-GPR",
        "car": "mean-adjusted daily CAR, estimation [-120,-20], BH q across events",
        "lab_version": LAB_VERSION,
        "api_version": API_VERSION,
        "var": "recursive, GPR difference ordered first; AIC lag in 1..3; cumulative orthogonal IRF",
        "redistribution": "Yahoo and Sina raw files are not covered by the code license and are not redistributed from this repo.",
    }
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
