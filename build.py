"""Rebuild the panel, paper figures, and the local lab page."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from havenlab.engine import build_lab, canvas_payload, web_payload, write_tables
from havenlab.figures import export_all


def main() -> None:
    print("Building panel, haven score, and VAR...")
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
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (ROOT / "src" / "havenlab" / "template.html").read_text(encoding="utf-8")
    app = ROOT / "app" / "index.html"
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    app.parent.mkdir(parents=True, exist_ok=True)
    app.write_text(template, encoding="utf-8")
    (docs / "index.html").write_text(template, encoding="utf-8")
    (app.parent / "lab_data.json").write_text(blob, encoding="utf-8")
    (docs / "lab_data.json").write_text(blob, encoding="utf-8")
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    processed = ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "canvas_payload.json").write_text(
        json.dumps(canvas_payload(lab), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Page {app}")


if __name__ == "__main__":
    main()
