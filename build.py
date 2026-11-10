"""Rebuild the panel, paper figures, and the local lab page."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from havenlab.cards import export_cards
from havenlab.engine import build_lab, canvas_payload, split_web_payload, web_payload, write_tables
from havenlab.figures import export_all
from havenlab.latex import write_latex
from havenlab.publish_b import write_api_v2, write_registry, write_static
from havenlab.ui_assemble import load_page
from havenlab.version import API_VERSION, LAB_VERSION


def _write_json(path: Path, payload: dict) -> None:
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    path.write_text(blob, encoding="utf-8")


def _carry_published_daily(payload: dict, docs_dir: Path) -> None:
    """Keep daily-only fields when rebuilding from the monthly panel."""
    previous_path = docs_dir / "lab_data_monthly.json"
    if not previous_path.exists():
        return
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    for key in ("car", "slices", "macro"):
        if previous.get(key):
            payload[key] = previous[key]
    for key in ("daily_quantile", "car_robust"):
        if not payload.get(key) and previous.get(key):
            payload[key] = previous[key]
    if not payload.get("slices"):
        slice_path = docs_dir / "slices.json"
        if slice_path.exists():
            payload["slices"] = json.loads(slice_path.read_text(encoding="utf-8"))
    prev_meta = previous.get("meta") or {}
    meta = payload.setdefault("meta", {})
    for key in (
        "gold_jumps",
        "gold_lbma",
        "gold_basis",
        "gold_jumps_repaired",
        "gold_basis_check",
        "gold_jump_check",
        "check",
        "macro",
        "from_derived",
    ):
        if prev_meta.get(key) not in (None, {}, []):
            meta[key] = prev_meta[key]
    daily_path = docs_dir / "lab_data_daily.json"
    if daily_path.exists():
        existing = json.loads(daily_path.read_text(encoding="utf-8"))
        if existing.get("daily"):
            payload["daily"] = existing["daily"]


def _split_slices_if_needed(monthly: dict, docs_dir: Path) -> str | None:
    slice_path = docs_dir / "slices.json"
    slices = monthly.get("slices") or None
    if not slices:
        monthly.pop("slices", None)
        return "slices.json" if slice_path.exists() else None
    raw = json.dumps(monthly, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(gzip.compress(raw)) <= 25 * 1024:
        if slice_path.exists():
            slice_path.unlink()
        return None
    monthly.pop("slices")
    _write_json(slice_path, slices)
    return "slices.json"


def _publish_payload(payload: dict, docs_dir: Path, from_derived: bool) -> str | None:
    if from_derived:
        _carry_published_daily(payload, docs_dir)
    full = json.loads(json.dumps(payload))
    monthly, daily = split_web_payload(full)
    slices_name = _split_slices_if_needed(monthly, docs_dir)
    digest = json.dumps(monthly, sort_keys=True, ensure_ascii=False).encode("utf-8")
    monthly_hash = hashlib.sha256(digest).hexdigest()[:16]
    monthly.setdefault("meta", {})["payload_hash"] = monthly_hash
    payload.setdefault("meta", {})["payload_hash"] = monthly_hash
    _write_json(docs_dir / "lab_data.json", payload)
    _write_json(docs_dir / "lab_data_monthly.json", monthly)
    hashed = docs_dir / f"lab_data_monthly.{monthly_hash}.json"
    _write_json(hashed, monthly)
    for stale in docs_dir.glob("lab_data_monthly.*.json"):
        if stale != hashed:
            stale.unlink()
    if not from_derived:
        _write_json(docs_dir / "lab_data_daily.json", daily)
    return slices_name


_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _rfc822(stamp) -> str:
    ts = pd.Timestamp(stamp)
    return f"{_WEEKDAYS[int(ts.dayofweek)]}, {int(ts.day):02d} {_MONTHS[int(ts.month) - 1]} {int(ts.year)} 00:00:00 +0000"


def write_feed(lab: dict, path: Path) -> None:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "EF Lab · 地缘政治风险 × 避险资产"
    ET.SubElement(channel, "link").text = "https://hantrleko.github.io/gpr-haven-lab/"
    ET.SubElement(channel, "description").text = "版本更新，以及最近八个内置事件。"
    ET.SubElement(channel, "language").text = "zh-CN"

    def add_item(title: str, link: str, guid: str, pub: str) -> None:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid").text = guid
        ET.SubElement(item, "pubDate").text = pub

    add_item(
        f"{LAB_VERSION}：零模型改为 stationary bootstrap，避险强度增加并列版本，事件页可以单独引用",
        "https://hantrleko.github.io/gpr-haven-lab/",
        f"version-{LAB_VERSION}",
        "Tue, 10 Nov 2026 00:00:00 +0000",
    )
    events = sorted(lab["events"], key=lambda event: event["date"], reverse=True)
    for event in events:
        add_item(
            f"{event['date']} {event['name']}",
            f"https://hantrleko.github.io/gpr-haven-lab/e/{event['id']}/",
            event["id"],
            _rfc822(event["date"]),
        )
    path.write_bytes(ET.tostring(rss, encoding="utf-8", xml_declaration=True))


def _write_api_manifest(docs_dir: Path, payload: dict, slices_name: str | None) -> None:
    api_dir = docs_dir / "api" / "v1"
    api_dir.mkdir(parents=True, exist_ok=True)
    meta = payload.get("meta", {})
    manifest = {
        "lab": "gpr-haven-lab",
        "version": LAB_VERSION,
        "api_version": API_VERSION,
        "sample": [meta.get("sample_start"), meta.get("sample_end")],
        "built": meta.get("built"),
        "payload_hash": meta.get("payload_hash"),
        "endpoints": {
            "monthly": f"lab_data_monthly.{meta.get('payload_hash')}.json",
            "monthly_alias": "lab_data_monthly.json",
            "daily": "lab_data_daily.json",
            "full": "lab_data.json",
        },
    }
    if slices_name:
        manifest["endpoints"]["slices"] = slices_name
    (api_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _apply_sample_pin(asof: str) -> tuple[Path, dict]:
    import havenlab.engine as engine

    pin_path = ROOT / "data" / "sample_pin.json"
    if pin_path.exists():
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
    else:
        pin = {"sample_end": "2026-09", "asof": "2026-10-13"}
    if asof == "auto":
        engine.ASOF = pd.Timestamp.today().normalize()
        engine.SAMPLE_END = engine.completed_month(engine.ASOF)
        pin["asof"] = engine.ASOF.strftime("%Y-%m-%d")
        pin["requested_sample_end"] = str(engine.SAMPLE_END)
    else:
        engine.SAMPLE_END = pd.Period(str(pin["sample_end"]), freq="M")
        engine.ASOF = pd.Timestamp(pin["asof"])
    return pin_path, pin


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the GPR haven lab.")
    parser.add_argument(
        "--from-derived",
        action="store_true",
        help="Rebuild monthly results from replication/panel_monthly.csv when raw quotes are absent.",
    )
    parser.add_argument("--fast", action="store_true", help="200 bootstrap draws, 60 specs, shorter conditional horizon. Not a release.")
    parser.add_argument("--asof", choices=("pin", "auto"), default="pin")
    parser.add_argument("--degraded", action="store_true", help="Show the source-outage banner. Does not move the sample pin.")
    args = parser.parse_args()
    pin_path, pin = _apply_sample_pin(args.asof)
    if args.fast:
        import havenlab.engine as engine

        engine.BOOT_REPS = 40
        print("FAST BUILD IS NOT A RELEASE")
    print(f"Building {LAB_VERSION} panel, haven score, and VAR...")
    lab = build_lab(from_derived=args.from_derived, fast=args.fast, degraded=args.degraded)
    summary = write_tables(lab, ROOT / "output")
    lab["summary"] = summary
    panel = lab["panel"]
    if args.asof == "auto":
        pin["sample_end"] = str(panel.index[-1])
        pin["asof"] = pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
        pin_path.write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Sample pin advanced to {pin['sample_end']}")
    print(f"Sample {panel.index[0]} to {panel.index[-1]}, {len(panel)} months")
    focus = panel.loc["2026-01":"2026-04", ["ret_gold", "ret_brent", "ret_dxy", "ret_csi", "ret_hsi", "gpr", "dgpr"]]
    print(focus.round(2).to_string())
    show = summary[summary["window_months"] == 6][
        ["event_name", "n_after", "partial", "gold_cum", "brent_cum", "csi_cum", "hsi_cum", "haven_after", "corr_gold_csi_before", "corr_gold_csi_after"]
    ]
    print(show.round(2).to_string(index=False))
    var = lab["var"]
    print(f"VAR lag {var['lags']}, T={var['t']}, bootstrap kept {var['boot_kept']}/{var['n_boot']}")
    if not args.from_derived:
        print("Exporting figures...")
        export_all(lab, ROOT / "figs")
    payload = web_payload(lab)
    template = load_page(ROOT).replace("__VERSION__", LAB_VERSION)
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.html").write_text(template, encoding="utf-8")
    slices_name = _publish_payload(payload, docs, from_derived=args.from_derived)
    _write_api_manifest(docs, payload, slices_name)
    write_registry(ROOT)
    write_static(ROOT, lab, payload, docs)
    write_api_v2(docs, lab, payload)
    shift_path = ROOT / "replication" / "placebo_shift.json"
    shift_path.write_text(
        json.dumps(
            {"max_abs_diff": lab.get("placebo_shift_max"), "rows": lab.get("placebo_shift") or []},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_feed(lab, docs / "feed.xml")
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    for stale in ("ef-logo.jpg",):
        target = docs / stale
        if target.exists():
            target.unlink()
    if not args.from_derived:
        export_cards(lab, docs / "cards")
    processed = ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "canvas_payload.json").write_text(
        json.dumps(canvas_payload(lab), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    rep = ROOT / "replication"
    rep.mkdir(exist_ok=True)
    car_csv = ROOT / "output" / "event_daily_car.csv"
    if not args.from_derived:
        shutil.copy2(ROOT / "output" / "panel_monthly.csv", rep / "panel_monthly.csv")
        shutil.copy2(ROOT / "output" / "event_window_summary.csv", rep / "event_window_summary.csv")
        shutil.copy2(ROOT / "output" / "provenance.json", rep / "provenance.json")
        if car_csv.exists():
            shutil.copy2(car_csv, rep / "event_daily_car.csv")
        write_latex(summary, car_csv, rep / "tables_latex.tex")
        if lab.get("slices"):
            (rep / "daily_slices.json").write_text(
                json.dumps(lab["slices"], ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
    print(f"Page {docs / 'index.html'}")


if __name__ == "__main__":
    main()
