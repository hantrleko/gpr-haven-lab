"""Record whether each external source answered, without turning a failure into a blank success."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests

UA = {"User-Agent": "GPR-Haven-Lab/2.5"}

SOURCES = (
    {
        "id": "gpr",
        "role": "critical",
        "url": "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls",
        "kind": "xls",
    },
    {
        "id": "fred_lbma_am",
        "role": "probe",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GOLDAMGBD228NLBM",
        "kind": "csv",
    },
    {
        "id": "fred_lbma_pm",
        "role": "probe",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GOLDPMGBD228NLBM",
        "kind": "csv",
    },
    {
        "id": "yahoo_xauusd",
        "role": "probe",
        "url": "https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD=X?interval=1d&range=5d",
        "kind": "json",
    },
    {
        "id": "stooq_xauusd",
        "role": "probe",
        "url": "https://stooq.com/q/d/l/?s=xauusd&i=d",
        "kind": "csv",
    },
    {
        "id": "fred_dfii10",
        "role": "state",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10",
        "kind": "csv",
    },
    {
        "id": "fred_dtwexbgs",
        "role": "state",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS",
        "kind": "csv",
    },
    {
        "id": "fred_vixcls",
        "role": "state",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
        "kind": "csv",
    },
    {
        "id": "cftc_gold",
        "role": "state",
        "url": "https://publicreporting.cftc.gov/resource/6dca-aqww.json?cftc_contract_market_code=088691&$select=report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all,open_interest_all&$order=report_date_as_yyyy_mm_dd&$limit=5000",
        "kind": "cftc",
    },
    {
        "id": "epu_us",
        "role": "state",
        "url": "https://www.policyuncertainty.com/media/US_Policy_Uncertainty_Data.xlsx",
        "kind": "xlsx",
    },
    {
        "id": "gep",
        "role": "probe",
        "url": "https://www.policyuncertainty.com/media/GEP_Update.xlsx",
        "kind": "xlsx",
    },
)


def classify_body(status_code: int, body: bytes) -> str:
    """Map an HTTP body to ok, failed, or blocked. A challenge page is not a price file."""
    head = body[:800].lower()
    if status_code == 404:
        return "failed"
    if b"requires javascript" in head or b"verify your browser" in head:
        return "blocked"
    if status_code >= 400 or not body:
        return "failed"
    if b"<html" in head or b"<!doctype" in head:
        return "failed"
    return "ok"


def _span_csv(body: bytes) -> dict:
    import pandas as pd

    frame = pd.read_csv(BytesIO(body))
    if frame.empty:
        return {"rows": 0}
    date_col = "DATE" if "DATE" in frame.columns else frame.columns[0]
    dates = pd.to_datetime(frame[date_col], errors="coerce").dropna()
    if dates.empty:
        return {"rows": int(len(frame))}
    return {
        "rows": int(len(frame)),
        "start": dates.iloc[0].strftime("%Y-%m-%d"),
        "end": dates.iloc[-1].strftime("%Y-%m-%d"),
    }


def _span_cftc(body: bytes) -> dict:
    rows = json.loads(body.decode("utf-8"))
    if not isinstance(rows, list) or not rows:
        return {"rows": 0}
    dates = sorted(str(row.get("report_date_as_yyyy_mm_dd") or "")[:10] for row in rows)
    dates = [item for item in dates if item]
    return {"rows": len(rows), "start": dates[0], "end": dates[-1]}


def _span_xlsx(body: bytes) -> dict:
    import pandas as pd

    frame = pd.read_excel(BytesIO(body))
    return {"rows": int(len(frame)), "columns": [str(col) for col in list(frame.columns)[:8]]}


def check_source(spec: dict, timeout: int = 25) -> dict:
    row = {"id": spec["id"], "role": spec["role"], "url": spec["url"], "checked_at": _now()}
    try:
        resp = requests.get(spec["url"], timeout=timeout, headers=UA)
        body = resp.content or b""
        row["http_status"] = int(resp.status_code)
        row["bytes"] = len(body)
        row["status"] = classify_body(resp.status_code, body)
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = str(exc)[:180]
        return row
    if row["status"] != "ok":
        return row
    try:
        kind = spec["kind"]
        if kind == "csv":
            row.update(_span_csv(body))
        elif kind == "cftc":
            row.update(_span_cftc(body))
        elif kind == "xlsx":
            row.update(_span_xlsx(body))
        elif kind == "json":
            row["rows"] = 1
    except Exception as exc:
        row["parse_error"] = str(exc)[:180]
    return row


def run_checks(timeout: int = 25) -> dict:
    rows = [check_source(spec, timeout=timeout) for spec in SOURCES]
    return {
        "checked_at": _now(),
        "sources": rows,
        "critical_failed": [row["id"] for row in rows if row["role"] == "critical" and row["status"] != "ok"],
        "state_failed": [row["id"] for row in rows if row["role"] == "state" and row["status"] != "ok"],
    }


def write_status(path: Path, timeout: int = 25) -> dict:
    payload = run_checks(timeout=timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
