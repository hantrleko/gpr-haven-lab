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
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR

from havenlab.events import EVENTS

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
    today = pd.Timestamp.today().normalize() if today is None else pd.Timestamp(today).normalize()
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
    end = min(panel.index[complete][-1], completed_month(today))
    if end < start:
        raise RuntimeError(f"Sample end {end} is before sample start {start}.")
    sample = panel.loc[start:end].copy()
    sample = sample.reindex(pd.period_range(start, end, freq="M"))
    months = sample.index.year * 12 + sample.index.month
    if not np.all(np.diff(months) == 1):
        raise RuntimeError("Monthly panel is not a continuous calendar.")
    sample.index.name = "period"
    return sample, daily


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
        "n_boot": BOOT_REPS,
        "boot_kept": int(len(draws)),
        "sample_start": str(endog.index[0]),
        "sample_end": str(endog.index[-1]),
    }


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


def _round_or_none(value, digits: int):
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def _list_or_none(series: pd.Series, digits: int) -> list:
    return [_round_or_none(value, digits) for value in series.to_numpy(dtype=float)]


def build_lab(today: pd.Timestamp | None = None) -> dict:
    panel, daily = build_panel(today)
    panel = add_rolling(panel)
    corrs = rolling_corr_frame(panel)
    var = fit_var(panel)
    events = []
    for event in EVENTS:
        paths = {name: trading_path(daily[name], event["date"]) for name in ASSETS}
        paths["gpr"] = gpr_on_gold_clock(paths["gold"], daily["gpr"])
        events.append({**event, "month": str(pd.Timestamp(event["date"]).to_period("M")), "path": paths})
    check_path = trading_path(daily["gold"], "2026-03-02", sessions=60)
    check_tau = 10
    check_index = check_path["tau"].index(check_tau)
    web_daily = {}
    for name, series in daily.items():
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
        "check": {"date": "2026-03-02", "tau": check_tau, "gold": round(check_path["value"][check_index], 4)},
    }


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
        events.append({key: event[key] for key in ("id", "date", "month", "group", "name", "note")})
    return {
        "meta": {
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
            "built": pd.Timestamp.today().strftime("%Y-%m-%d"),
            "check": lab["check"],
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
        },
        "events": events,
        "daily": lab["web_daily"],
    }


def canvas_payload(lab: dict) -> dict:
    full = web_payload(lab)
    full.pop("daily", None)
    full.pop("level", None)
    slim_events = []
    for event in lab["events"]:
        fixed = {}
        for name in ASSETS + ["gpr"]:
            packed = event["path"][name]
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
                "path": fixed,
            }
        )
    full["events"] = slim_events
    full["path_origin"] = -MAX_SESSIONS
    return full


def write_tables(lab: dict, output: Path) -> pd.DataFrame:
    output.mkdir(parents=True, exist_ok=True)
    panel: pd.DataFrame = lab["panel"]
    table = panel.copy()
    table.insert(0, "month", [str(period) for period in table.index])
    table.to_csv(output / "panel_monthly.csv", index=False)
    summary = summary_rows(panel)
    summary.to_csv(output / "event_window_summary.csv", index=False)
    provenance = {
        "built": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "sample": [str(panel.index[0]), str(panel.index[-1])],
        "gpr": "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls",
        "gold": "Yahoo Finance GC=F, COMEX front gold future",
        "brent": "Yahoo Finance BZ=F, ICE Brent front future",
        "dxy": "Yahoo Finance DX-Y.NYB, ICE US Dollar Index",
        "hsi": "Yahoo Finance ^HSI",
        "csi300": "Sina Finance sh000300 via akshare, price index",
        "returns": "100 * log month-end price change; not excess of the risk-free rate",
        "haven": "equal weight of equity hedge, GPR co-movement, and dollar hedge; 50 is zero correlation",
        "var": "recursive, GPR difference ordered first; AIC lag in 1..3; cumulative orthogonal IRF",
    }
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
