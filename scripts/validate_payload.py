"""Check the published monthly payload against the lab's structural rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from havenlab.version import LAB_VERSION  # noqa: E402


def validate(payload: dict) -> list[str]:
    errors: list[str] = []
    months = payload.get("months") or []
    ret = payload.get("ret") or {}
    if not months:
        errors.append("months is empty")
    for name, values in ret.items():
        if not isinstance(values, list) or len(values) != len(months):
            errors.append(f"ret.{name} length {len(values) if isinstance(values, list) else 'n/a'} != months {len(months)}")
    events = payload.get("events") or []
    ids = [event.get("id") for event in events]
    if len(ids) != len(set(ids)):
        errors.append("event id values are not unique")
    for event in events:
        source = event.get("source") or ""
        source_2 = event.get("source_2") or ""
        if source == source_2:
            errors.append(f"{event.get('id')} source_2 repeats source")
        if not source.startswith("https://") or not source_2.startswith("https://"):
            errors.append(f"{event.get('id')} sources must both start with https://")
    slices = payload.get("slices") or {}
    for event_id, bucket in slices.items():
        lengths = {name: len((series or {}).get("dates") or []) for name, series in bucket.items()}
        close_lengths = {name: len((series or {}).get("close") or []) for name, series in bucket.items()}
        for name, length in lengths.items():
            if close_lengths.get(name) != length:
                errors.append(f"slices.{event_id}.{name} dates and close differ")
        if not lengths:
            errors.append(f"slices.{event_id} has no series")
    meta = payload.get("meta") or {}
    if meta.get("version") != LAB_VERSION:
        errors.append(f"meta.version {meta.get('version')} != {LAB_VERSION}")
    return errors


def main() -> int:
    path = ROOT / "docs" / "lab_data_monthly.json"
    if not path.exists():
        print(f"missing {path}", file=sys.stderr)
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("validate_payload ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
