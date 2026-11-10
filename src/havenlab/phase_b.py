"""Assemble the Phase B objects from a monthly panel."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from havenlab.haven_metrics import event_haven_versions, quantile_sensitivity
from havenlab.null_model import NULL_REPS, NULL_REPS_FAST, NULL_SEED, stationary_bootstrap_placebo
from havenlab.spec_curve import build_spec_curve
from havenlab.states import (
    car_estimation_robust,
    conditional_bundle,
    daily_quantile_curve,
    load_state_panel,
)

ROOT_STATES = "states_monthly.csv"


def _states(root) -> pd.DataFrame:
    replication = root / "replication" / ROOT_STATES
    if replication.exists():
        frame = pd.read_csv(replication)
        if "month" not in frame.columns:
            return pd.DataFrame()
        frame.index = pd.PeriodIndex(frame["month"].astype(str), freq="M")
        return frame.drop(columns=["month"])
    loaded = load_state_panel(root / "data" / "raw")
    if loaded.empty:
        return loaded
    table = loaded.copy()
    table.insert(0, "month", [str(period) for period in table.index])
    replication.parent.mkdir(exist_ok=True)
    table.to_csv(replication, index=False)
    return loaded


def _round_series(values: np.ndarray, digits: int = 2) -> list:
    out = []
    for value in values:
        out.append(None if not np.isfinite(value) else round(float(value), digits))
    return out


def compute_phase_b(root, panel: pd.DataFrame, events: list[dict], daily: dict, car: dict, fast: bool = False) -> dict:
    reps = NULL_REPS_FAST if fast else NULL_REPS
    print(f"Phase B bootstrap reps={reps}", flush=True)
    placebo = {}
    shift = []
    for width in (6, 12, 24):
        packed = stationary_bootstrap_placebo(panel, events, width, reps=reps, seed=NULL_SEED)
        shift.extend(packed.pop("shift"))
        placebo[str(width)] = packed
    quant = quantile_sensitivity(panel)
    gpr_beta = None
    if quant.get("taus") and quant["taus"].get("0.1"):
        gpr_beta = quant["taus"]["0.1"]["dgpr_beta"]
    versions = event_haven_versions(panel, events, gpr_beta)
    betas = versions["beta"]
    v2 = []
    for csi, hsi, dxy in zip(betas["csi"], betas["hsi"], betas["dxy"]):
        if not (np.isfinite(csi) and np.isfinite(hsi) and np.isfinite(dxy)):
            v2.append(None)
            continue
        from havenlab.haven_metrics import haven2_score

        v2.append(round(haven2_score(float(csi), float(hsi), float(dxy), 0.0 if gpr_beta is None else float(gpr_beta)), 2))
    loaded_states = _states(root)
    states = loaded_states.reindex(panel.index) if not loaded_states.empty else pd.DataFrame(index=panel.index)
    horizon = 4 if fast else 12
    conditional = conditional_bundle(panel, states, horizon=horizon)
    spec = build_spec_curve(panel, events, placebo, car or {}, fast=fast)
    daily_pack = daily or {}
    has_daily = daily_pack.get("gold") is not None and not getattr(daily_pack.get("gold"), "empty", True)
    diffs = [abs(float(row["diff"])) for row in shift if row.get("diff") is not None]
    return {
        "placebo_v2": placebo,
        "placebo_shift": shift,
        "placebo_shift_max": None if not diffs else round(max(diffs), 4),
        "quantile": quant,
        "haven_versions": {
            "headline": "haven",
            "switch_rule": "haven2 becomes the headline only after its cross-spec dispersion is smaller than v1. That decision is not made in this release.",
            "haven1_z": _round_series(versions["haven1_z"]),
            "haven2": v2,
            "beta_csi": _round_series(betas["csi"], 3),
            "beta_hsi": _round_series(betas["hsi"], 3),
            "beta_dxy": _round_series(betas["dxy"], 3),
            "tail_csi": _round_series(versions["tail_csi"], 3),
            "events": versions["events"],
            "gpr_beta_tau10": gpr_beta,
        },
        "conditional": conditional,
        "spec_curve": spec,
        "daily_quantile": daily_quantile_curve(daily_pack) if has_daily else {},
        "car_robust": car_estimation_robust(daily_pack, events) if has_daily else {},
        "macro_status": _macro_status(root, states),
        "spot_check": _spot_check(root),
    }


def _macro_status(root, states: pd.DataFrame) -> dict:
    from havenlab.states import HY_SPEC, STATE_SPECS, _describe_state

    status = {}
    for name, series_id, label in STATE_SPECS:
        path = root / "data" / "raw" / f"state_{name}.csv"
        if path.exists():
            status[name] = _describe_state(path, series_id, label)
            marker = path.with_suffix(".local")
            if marker.exists():
                status[name]["note"] = marker.read_text(encoding="utf-8").strip()
                status[name]["source"] = "local file"
        elif name in states.columns and states[name].notna().any():
            values = states[name].dropna()
            status[name] = {
                "id": series_id,
                "label": label,
                "status": "ok",
                "rows": int(values.size),
                "start": str(values.index[0]),
                "end": str(values.index[-1]),
                "in_model": True,
                "source": "replication/states_monthly.csv",
            }
        else:
            status[name] = {
                "id": series_id,
                "label": label,
                "status": "missing",
                "in_model": False,
                "note": "No local file. This state is not in the interaction regression.",
            }
    _name, series_id, label = HY_SPEC
    hy_path = root / "data" / "raw" / f"state_{_name}.csv"
    if hy_path.exists():
        status[_name] = _describe_state(hy_path, series_id, label)
    else:
        status[_name] = {
            "id": series_id,
            "label": label,
            "status": "short_history",
            "rows": 793,
            "start": "2023-11-10",
            "in_model": False,
            "note": "FRED ICE high-yield OAS is about two years long. Shown only. It is not a regression state.",
        }
    notes_path = root / "replication" / "state_notes.json"
    if notes_path.exists():
        notes = json.loads(notes_path.read_text(encoding="utf-8"))
        for name, extra in notes.items():
            if name not in status or not isinstance(extra, dict):
                continue
            status[name].update(extra)
    return status


def _spot_check(root) -> dict:
    path = root / "replication" / "spot_source_check.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
