"""Download raw inputs into data/raw/ for a local rebuild.

Yahoo and Sina quotes are not redistributed from git. GPR is fetched from the
Caldara-Iacoviello site. LBMA via FRED is optional and may fail offline.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
YAHOO = {
    "gold_gc.csv": "GC=F",
    "brent_bz.csv": "BZ=F",
    "dxy.csv": "DX-Y.NYB",
    "hsi.csv": "^HSI",
}
YAHOO_EXTENDED = {
    "silver_si.csv": "SI=F",
    "vix.csv": "^VIX",
    "ust10.csv": "^TNX",
}
FRED_TIPS = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10"
FRED_LBMA = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GOLDAMGBD228NLBM"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _yahoo_chart(symbol: str, period1: int = 1162339200) -> pd.DataFrame:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{requests.utils.quote(symbol, safe='')}"
        f"?period1={period1}&period2={int(datetime.now(timezone.utc).timestamp())}&interval=1d"
    )
    resp = requests.get(url, timeout=60, headers={"User-Agent": "GPR-Haven-Lab/1.0"})
    resp.raise_for_status()
    payload = resp.json()["chart"]["result"][0]
    stamps = payload["timestamp"]
    quote = payload["indicators"]["quote"][0]
    adj = payload["indicators"].get("adjclose", [{}])[0].get("adjclose")
    close = quote["close"]
    rows = []
    for i, ts in enumerate(stamps):
        if ts is None:
            continue
        c = close[i] if i < len(close) else None
        a = adj[i] if adj and i < len(adj) else None
        if c is None and a is None:
            continue
        rows.append(
            {
                "datetime_utc": pd.Timestamp(ts, unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M:%S%z"),
                "close": c if c is not None else a,
                "adjclose": a if a is not None else c,
            }
        )
    return pd.DataFrame(rows)


def fetch_yahoo(extra: dict[str, str] | None = None) -> None:
    mapping = dict(YAHOO)
    if extra:
        mapping.update(extra)
    for filename, symbol in mapping.items():
        frame = _yahoo_chart(symbol)
        path = RAW / filename
        frame.to_csv(path, index=False)
        print(f"Wrote {path} ({len(frame)} rows, sha256={_sha256(path)[:12]})")


def fetch_gpr() -> None:
    resp = requests.get(GPR_URL, timeout=120, headers={"User-Agent": "GPR-Haven-Lab/1.0"})
    resp.raise_for_status()
    path = RAW / "data_gpr_daily_recent.xls"
    path.write_bytes(resp.content)
    print(f"Wrote {path} ({len(resp.content)} bytes, sha256={_sha256(path)[:12]})")


def fetch_csi() -> None:
    try:
        import akshare as ak
    except ImportError as err:
        raise SystemExit("akshare is required for CSI 300: pip install akshare") from err
    frame = ak.stock_zh_index_daily(symbol="sh000300")
    out = pd.DataFrame({"date": frame["date"], "close": frame["close"]})
    path = RAW / "csi300_sina.csv"
    out.to_csv(path, index=False)
    print(f"Wrote {path} ({len(out)} rows, sha256={_sha256(path)[:12]})")


def fetch_lbma_optional() -> None:
    path = RAW / "gold_lbma_fred.csv"
    try:
        resp = requests.get(FRED_LBMA, timeout=45, headers={"User-Agent": "GPR-Haven-Lab/1.0"})
        resp.raise_for_status()
        path.write_bytes(resp.content)
        print(f"Wrote optional {path} (sha256={_sha256(path)[:12]})")
    except Exception as exc:
        print(f"LBMA/FRED skipped: {exc}", file=sys.stderr)


def write_manifest() -> None:
    files = sorted(p for p in RAW.iterdir() if p.is_file())
    manifest = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": _sha256(p)} for p in files},
    }
    out = RAW / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


def fetch_tips_optional() -> None:
    path = RAW / "tips10_fred.csv"
    try:
        resp = requests.get(FRED_TIPS, timeout=45, headers={"User-Agent": "GPR-Haven-Lab/2.0"})
        resp.raise_for_status()
        path.write_bytes(resp.content)
        print(f"Wrote optional {path} (sha256={_sha256(path)[:12]})")
    except Exception as exc:
        print(f"TIPS/FRED skipped: {exc}", file=sys.stderr)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download raw inputs into data/raw/.")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Also download silver, VIX, 10-year yield, and 10-year TIPS.",
    )
    args = parser.parse_args()
    fetch_gpr()
    fetch_yahoo(YAHOO_EXTENDED if args.extended else None)
    fetch_csi()
    fetch_lbma_optional()
    if args.extended:
        fetch_tips_optional()
    write_manifest()
    print("Done. Run: python build.py")


if __name__ == "__main__":
    main()
