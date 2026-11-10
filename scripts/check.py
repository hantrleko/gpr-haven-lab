"""Local smoke checks (use when GitHub Actions workflow scope is unavailable)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from havenlab.version import LAB_VERSION  # noqa: E402


def main() -> int:
    subprocess.check_call(["node", "--check", str(ROOT / "src" / "havenlab" / "ui" / "claim_rule.js")], cwd=ROOT)
    subprocess.check_call(["node", "--check", str(ROOT / "src" / "havenlab" / "ui" / "verdict_rule.js")], cwd=ROOT)
    subprocess.check_call(["node", "--check", str(ROOT / "src" / "havenlab" / "ui" / "app.js")], cwd=ROOT)
    subprocess.check_call(["node", "--check", str(ROOT / "src" / "havenlab" / "ui" / "phase_b.js")], cwd=ROOT)
    subprocess.check_call(["node", str(ROOT / "tests" / "test_claim_rule.js")], cwd=ROOT)
    subprocess.check_call(["node", str(ROOT / "tests" / "test_verdict_rule.js")], cwd=ROOT)
    subprocess.check_call(["node", str(ROOT / "tests" / "test_haven_se.js")], cwd=ROOT)
    subprocess.check_call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], cwd=ROOT)
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "validate_payload.py")], cwd=ROOT)
    monthly = json.loads((ROOT / "docs" / "lab_data_monthly.json").read_text(encoding="utf-8"))
    assert monthly["meta"]["version"] == LAB_VERSION, monthly["meta"].get("version")
    assert "daily" not in monthly
    assert "car" in monthly and monthly["car"]["by_event"]["ukraine_2022"]["gold"]
    assert "state" in monthly["var"]["lp"]
    hormuz = next(event for event in monthly["events"] if event["id"] == "hormuz_2026")
    assert hormuz["date"] == "2026-03-02"
    assert hormuz["source"].startswith("https://") and hormuz["source_2"].startswith("https://")
    assert hormuz["source"] != hormuz["source_2"]
    monthly_text = (ROOT / "docs" / "lab_data_monthly.json").read_text(encoding="utf-8")
    assert hormuz["source"] in monthly_text and hormuz["source_2"] in monthly_text
    daily = json.loads((ROOT / "docs" / "lab_data_daily.json").read_text(encoding="utf-8"))
    assert "daily" in daily and daily["daily"]["gold"]["dates"]
    manifest = json.loads((ROOT / "docs" / "api" / "v1" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == LAB_VERSION
    assert isinstance(monthly["meta"].get("gold_lbma"), dict) and monthly["meta"]["gold_lbma"]
    assert monthly["meta"].get("gold_basis_check", {}).get("max_month_diff_pp") is not None
    assert monthly.get("slices") or (ROOT / "docs" / "slices.json").exists()
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "没有配上现货" not in page
    assert monthly["meta"]["schemas"]["payload"] == "2.0.0"
    assert monthly["meta"]["haven_headline"] == "haven"
    assert monthly["placebo_v2"]["12"]["reps"] == 2000
    assert (ROOT / "docs" / "e" / "hormuz_2026" / "index.html").exists()
    assert (ROOT / "docs" / "api" / "v2" / "manifest.json").exists()
    assert "function claimRule" in page
    assert "function drawPhaseB" in page
    assert "function verdictText" in page
    assert "普通月份的中间分位" in page
    assert "function sourceLine" in page
    assert "const SOURCES" not in page
    print("check.py ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
