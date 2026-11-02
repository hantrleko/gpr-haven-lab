"""Local smoke checks (use when GitHub Actions workflow scope is unavailable)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    subprocess.check_call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], cwd=ROOT)
    monthly = json.loads((ROOT / "docs" / "lab_data_monthly.json").read_text(encoding="utf-8"))
    assert monthly["meta"]["version"] == "V2.0", monthly["meta"].get("version")
    assert "daily" not in monthly
    assert "car" in monthly and monthly["car"]["by_event"]["ukraine_2022"]["gold"]
    assert "state" in monthly["var"]["lp"]
    daily = json.loads((ROOT / "docs" / "lab_data_daily.json").read_text(encoding="utf-8"))
    assert "daily" in daily and daily["daily"]["gold"]["dates"]
    manifest = json.loads((ROOT / "docs" / "api" / "v1" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "V2.0"
    print("check.py ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
