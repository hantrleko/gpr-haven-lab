"""Derived COT and US EPU series. Raw files stay out of git.

The blended crowding index needs ETF flows as well. Those are not parsed here,
so this module publishes the COT percentile alone and does not average in a zero.
"""

from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
import requests

from havenlab.regime import causal_percentile

CFTC_URL = (
    "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
    "?cftc_contract_market_code=088691"
    "&$select=report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all,open_interest_all"
    "&$order=report_date_as_yyyy_mm_dd&$limit=5000"
)
EPU_URL = "https://www.policyuncertainty.com/media/US_Policy_Uncertainty_Data.xlsx"
UA = {"User-Agent": "GPR-Haven-Lab/2.5"}


def cot_monthly(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    dates = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"], errors="coerce")
    long = pd.to_numeric(frame["noncomm_positions_long_all"], errors="coerce")
    short = pd.to_numeric(frame["noncomm_positions_short_all"], errors="coerce")
    oi = pd.to_numeric(frame["open_interest_all"], errors="coerce")
    ratio = (long - short) / oi
    series = pd.Series(ratio.to_numpy(), index=dates).replace([float("inf"), float("-inf")], pd.NA).dropna()
    series = series[series.index.notna()].sort_index()
    monthly = series.resample("ME").last().dropna()
    monthly.index = monthly.index.to_period("M")
    pct = causal_percentile(monthly.to_numpy(dtype=float))
    return pd.DataFrame({"month": [str(period) for period in monthly.index], "net_oi": monthly.to_numpy(dtype=float), "cot_pct": pct})


def epu_monthly(body: bytes) -> pd.DataFrame:
    frame = pd.read_excel(BytesIO(body))
    frame = frame.dropna(subset=["Year", "Month"])
    year = pd.to_numeric(frame["Year"], errors="coerce")
    month = pd.to_numeric(frame["Month"], errors="coerce")
    value_col = "News_Based_Policy_Uncert_Index"
    value = pd.to_numeric(frame[value_col], errors="coerce")
    keep = year.notna() & month.notna() & value.notna() & (month >= 1) & (month <= 12)
    periods = pd.PeriodIndex.from_fields(year=year[keep].astype(int), month=month[keep].astype(int), freq="M")
    out = pd.DataFrame({"month": [str(period) for period in periods], "epu_news": value[keep].to_numpy(dtype=float)})
    return out.drop_duplicates("month", keep="last").sort_values("month")


def write_flows(root) -> dict:
    cot_resp = requests.get(CFTC_URL, timeout=60, headers=UA)
    cot_resp.raise_for_status()
    cot = cot_monthly(cot_resp.json())
    epu_resp = requests.get(EPU_URL, timeout=60, headers=UA)
    epu_resp.raise_for_status()
    epu = epu_monthly(epu_resp.content)
    folder = root / "replication"
    folder.mkdir(exist_ok=True)
    cot.to_csv(folder / "cot_monthly.csv", index=False)
    epu.to_csv(folder / "epu_us_monthly.csv", index=False)
    note = {
        "cot": "CFTC legacy futures-only, COMEX gold 088691, non-commercial net divided by open interest, month-end print. cot_pct is a trailing 60-month percentile.",
        "epu": "Baker, Bloom and Davis news-based US EPU. The global GEP workbook returned HTTP 404 and is not used.",
        "crowding": "The 0.5 COT + 0.5 ETF blend is not published. ETF flows were not parsed, and a one-leg average would invent the missing half.",
        "wgc": "Goldhub holdings were not copied. The terms were not checked, so no WGC series is stored.",
    }
    (folder / "flow_notes.json").write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"cot_rows": int(len(cot)), "cot_end": cot["month"].iloc[-1], "epu_rows": int(len(epu)), "epu_end": epu["month"].iloc[-1]}
