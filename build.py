"""Rebuild the panel, paper figures, and the local lab page."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from havenlab.cards import copy_cards, export_cards
from havenlab.engine import build_lab, canvas_payload, split_web_payload, web_payload, write_tables
from havenlab.figures import export_all
from havenlab.version import API_VERSION, LAB_VERSION


def _write_json(path: Path, payload: dict) -> None:
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    path.write_text(blob, encoding="utf-8")


def _publish_payload(payload: dict, app_dir: Path, docs_dir: Path) -> None:
    full = json.loads(json.dumps(payload))
    monthly, daily = split_web_payload(full)
    digest = json.dumps(monthly, sort_keys=True, ensure_ascii=False).encode("utf-8")
    import hashlib

    monthly_hash = hashlib.sha256(digest).hexdigest()[:16]
    monthly.setdefault("meta", {})["payload_hash"] = monthly_hash
    payload.setdefault("meta", {})["payload_hash"] = monthly_hash
    for folder in (app_dir, docs_dir):
        _write_json(folder / "lab_data.json", payload)
        _write_json(folder / "lab_data_monthly.json", monthly)
        _write_json(folder / "lab_data_daily.json", daily)


def _write_api_manifest(docs_dir: Path, payload: dict) -> None:
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
            "monthly": "lab_data_monthly.json",
            "daily": "lab_data_daily.json",
            "full": "lab_data.json",
        },
    }
    (api_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    print(f"Building {LAB_VERSION} panel, haven score, and VAR...")
    lab = build_lab()
    summary = write_tables(lab, ROOT / "output")
    lab["summary"] = summary
    panel = lab["panel"]
    print(f"Sample {panel.index[0]} to {panel.index[-1]}, {len(panel)} months")
    focus = panel.loc["2026-01":"2026-04", ["ret_gold", "ret_brent", "ret_dxy", "ret_csi", "ret_hsi", "gpr", "dgpr"]]
    print(focus.round(2).to_string())
    show = summary[summary["window_months"] == 6][
        ["event_name", "n_after", "partial", "gold_cum", "brent_cum", "csi_cum", "hsi_cum", "haven_after", "corr_gold_csi_before", "corr_gold_csi_after"]
    ]
    print(show.round(2).to_string(index=False))
    var = lab["var"]
    print(f"VAR lag {var['lags']}, T={var['t']}, bootstrap kept {var['boot_kept']}/{var['n_boot']}")
    print("Exporting figures...")
    export_all(lab, ROOT / "figs")
    payload = web_payload(lab)
    template = (ROOT / "src" / "havenlab" / "template.html").read_text(encoding="utf-8")
    app = ROOT / "app"
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    app.mkdir(parents=True, exist_ok=True)
    (app / "index.html").write_text(template, encoding="utf-8")
    (docs / "index.html").write_text(template, encoding="utf-8")
    _publish_payload(payload, app, docs)
    _write_api_manifest(docs, payload)
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    for name in ("paper.html", "embed.html", "feed.xml"):
        src = docs / name
        if src.exists():
            shutil.copy2(src, app / name)
    for stale in ("ef-logo.jpg",):
        for folder in (app, docs):
            target = folder / stale
            if target.exists():
                target.unlink()
    card_dir = app / "cards"
    export_cards(lab, card_dir)
    copy_cards(card_dir, docs / "cards")
    processed = ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "canvas_payload.json").write_text(
        json.dumps(canvas_payload(lab), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    rep = ROOT / "replication"
    rep.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "output" / "panel_monthly.csv", rep / "panel_monthly.csv")
    shutil.copy2(ROOT / "output" / "event_window_summary.csv", rep / "event_window_summary.csv")
    shutil.copy2(ROOT / "output" / "provenance.json", rep / "provenance.json")
    print(f"Page {app / 'index.html'}")


if __name__ == "__main__":
    main()
