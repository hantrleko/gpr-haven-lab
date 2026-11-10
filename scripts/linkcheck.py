"""GET the event source URLs. A failure is a warning and does not fail CI."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.events import EVENTS  # noqa: E402

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
}


def main() -> int:
    warnings = 0
    for event in EVENTS:
        for key in ("source", "source_2"):
            url = event.get(key) or ""
            try:
                resp = requests.get(url, headers=_UA, timeout=20, allow_redirects=True)
                if resp.status_code >= 400:
                    warnings += 1
                    print(f"warning {event['id']} {key} {resp.status_code} {url}")
            except Exception as exc:
                warnings += 1
                print(f"warning {event['id']} {key} {type(exc).__name__} {url}")
    print(f"linkcheck warnings: {warnings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
