"""Download raw inputs into data/raw/ for a local rebuild.

Yahoo and Sina quotes are not redistributed from git. GPR is fetched from the
Caldara-Iacoviello site. Gold spot is required: FRED's LBMA series was removed
in 2022, so the fetch tries that file, then the LBMA AM JSON, then a spot
quote on the Yahoo chart host already used for GC=F. Total failure exits.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from io import StringIO
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
LBMA_AM_JSON = "https://prices.lbma.org.uk/json/gold_am.json"
_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/csv,text/plain,*/*",
}


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


def _csv_body(content: bytes) -> bool:
    head = content[:300].lower()
    return b"date" in head and b"<html" not in head and b"<!doctype" not in head


def _write_spot(frame: pd.DataFrame, source: str) -> None:
    path = RAW / "gold_lbma_fred.csv"
    out = frame.copy()
    out["SOURCE"] = source
    out.to_csv(path, index=False)
    print(f"Wrote {path} ({len(out)} rows, source={source}, sha256={_sha256(path)[:12]})")


def _lbma_from_json(payload: list) -> pd.DataFrame:
    rows = []
    for item in payload:
        values = item.get("v") or []
        if not values or values[0] in (None, ""):
            continue
        price = float(values[0])
        if price <= 0:
            continue
        rows.append({"DATE": str(item["d"])[:10], "GOLDAMGBD228NLBM": price})
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("LBMA JSON had no USD AM prints")
    return frame.drop_duplicates("DATE").sort_values("DATE")


def _yahoo_spot(symbol: str) -> pd.DataFrame:
    frame = _yahoo_chart(symbol)
    dates = pd.to_datetime(frame["datetime_utc"], utc=True).dt.strftime("%Y-%m-%d")
    price = pd.to_numeric(frame["close"], errors="coerce")
    out = pd.DataFrame({"DATE": dates, "XAU": price})
    out = out[out["XAU"] > 0].drop_duplicates("DATE").sort_values("DATE")
    if len(out) < 500:
        raise RuntimeError(f"{symbol} returned {len(out)} rows")
    return out


def _sina_xau() -> pd.DataFrame:
    url = (
        "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_XAU=/"
        "GlobalFuturesService.getGlobalFuturesDailyKLine"
    )
    resp = requests.get(
        url,
        params={"symbol": "XAU", "source": "web"},
        headers={**_BROWSER, "Referer": "https://finance.sina.com.cn/"},
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.text
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        raise RuntimeError("Sina XAU response has no JSON array")
    frame = pd.read_json(StringIO(text[start : end + 1]))
    date_col = "date" if "date" in frame.columns else frame.columns[0]
    value_col = "close" if "close" in frame.columns else frame.columns[-1]
    out = pd.DataFrame(
        {
            "DATE": pd.to_datetime(frame[date_col], errors="coerce").dt.strftime("%Y-%m-%d"),
            "XAU": pd.to_numeric(frame[value_col], errors="coerce"),
        }
    )
    out = out.dropna()
    out = out[out["XAU"] > 0].drop_duplicates("DATE").sort_values("DATE")
    if len(out) < 500:
        raise RuntimeError(f"Sina XAU returned {len(out)} rows")
    return out


def _eastmoney_xau() -> pd.DataFrame:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    headers = dict(_BROWSER)
    headers["Referer"] = "https://quote.eastmoney.com/"
    end = "20500101"
    rows: list[tuple[str, float]] = []
    seen: set[str] = set()
    for _page in range(90):
        params = {
            "secid": "122.XAU",
            "klt": "101",
            "fqt": "1",
            "lmt": "80",
            "end": end,
            "fields1": "f1",
            "fields2": "f51,f53",
        }
        klines = None
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=30)
                resp.raise_for_status()
                klines = resp.json()["data"]["klines"]
                break
            except Exception as exc:
                last_error = exc
                time.sleep(0.8 * (attempt + 1))
        if klines is None:
            raise RuntimeError(f"eastmoney page failed: {last_error}")
        if not klines:
            break
        first = klines[0].split(",")[0]
        for row in klines:
            date, close = row.split(",")[:2]
            if date in seen:
                continue
            seen.add(date)
            rows.append((date, float(close)))
        if first <= "2000-01-01":
            break
        end = (pd.Timestamp(first) - pd.Timedelta(days=1)).strftime("%Y%m%d")
        time.sleep(0.25)
    frame = pd.DataFrame(rows, columns=["DATE", "XAU"])
    if len(frame) < 500:
        raise RuntimeError(f"eastmoney returned {len(frame)} rows")
    return frame.drop_duplicates("DATE").sort_values("DATE")


def fetch_lbma() -> None:
    """Write data/raw/gold_lbma_fred.csv. Exit if every spot source fails."""
    errors: list[str] = []
    try:
        resp = requests.get(FRED_LBMA, timeout=45, headers=_BROWSER)
        resp.raise_for_status()
        if not _csv_body(resp.content) or b"GOLDAMGBD228NLBM" not in resp.content:
            raise RuntimeError(f"FRED response is not the series CSV ({resp.status_code}, {len(resp.content)} bytes)")
        path = RAW / "gold_lbma_fred.csv"
        path.write_bytes(resp.content)
        print(f"Wrote {path} (sha256={_sha256(path)[:12]})")
        return
    except Exception as exc:
        errors.append(f"FRED: {exc}")
    try:
        resp = requests.get(LBMA_AM_JSON, timeout=60, headers={**_BROWSER, "Referer": "https://www.lbma.org.uk/"})
        resp.raise_for_status()
        _write_spot(_lbma_from_json(resp.json()), "lbma_gold_am")
        return
    except Exception as exc:
        errors.append(f"LBMA JSON: {exc}")
    for symbol in ("XAU=X", "XAUUSD=X"):
        try:
            _write_spot(_yahoo_spot(symbol), f"yahoo:{symbol}")
            return
        except Exception as exc:
            errors.append(f"Yahoo {symbol}: {exc}")
    try:
        _write_spot(_sina_xau(), "sina:XAU")
        return
    except Exception as exc:
        errors.append(f"Sina XAU: {exc}")
    try:
        _write_spot(_eastmoney_xau(), "eastmoney:122.XAU")
        return
    except Exception as exc:
        errors.append(f"Eastmoney: {exc}")
    raise SystemExit("现货黄金没有抓到。FRED 的 GOLDAMGBD228NLBM 已于 2022 年下架，其余来源也失败：" + " | ".join(errors))


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


def fetch_states() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from havenlab.states import fetch_fred_states

    try:
        print(fetch_fred_states(RAW, timeout=45))
    except Exception as exc:
        print(f"State series skipped: {exc}", file=sys.stderr)


def probe_stooq() -> None:
    """Cross-check only. This never replaces the published Sina spot file."""
    try:
        resp = requests.get(
            "https://stooq.com/q/d/l/?s=xauusd&i=d",
            timeout=25,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200 and resp.text.startswith("Date"):
            (RAW / "gold_stooq.csv").write_bytes(resp.content)
            print("Wrote gold_stooq.csv as a cross-check. The published series is unchanged.")
        else:
            print(f"Stooq probe is not a CSV ({resp.status_code}).", file=sys.stderr)
    except Exception as exc:
        print(f"Stooq probe skipped: {exc}", file=sys.stderr)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download raw inputs into data/raw/.")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Also download silver, VIX, 10-year yield, and 10-year TIPS.",
    )
    parser.add_argument(
        "--sources-check",
        action="store_true",
        help="Probe each external source once and write data/sources_status.json.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when a critical source is down.")
    args = parser.parse_args()
    if args.sources_check:
        sys.path.insert(0, str(ROOT / "src"))
        from havenlab.source_check import write_status

        status = write_status(ROOT / "data" / "sources_status.json")
        for row in status["sources"]:
            print(f"{row['id']}: {row['status']} http={row.get('http_status')} start={row.get('start')} rows={row.get('rows')}")
        if status["state_failed"]:
            print("STATE SOURCE FAILED: " + ", ".join(status["state_failed"]), file=sys.stderr)
        if args.strict and status["critical_failed"]:
            raise SystemExit("critical source failed: " + ", ".join(status["critical_failed"]))
        return
    fetch_gpr()
    fetch_yahoo(YAHOO_EXTENDED if args.extended else None)
    fetch_csi()
    fetch_lbma()
    if args.extended:
        fetch_tips_optional()
    fetch_states()
    probe_stooq()
    write_manifest()
    print("Done. Run: python build.py")


if __name__ == "__main__":
    main()
