"""Phase C: causal regimes, walk-forward scores, and the public forecast line."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from havenlab.regime import build_regime, causal_percentile
from havenlab.validation import forecast_table, summarize_walk, walk_forward
from havenlab.version import LAB_VERSION

NEGATIVE = (
    "若 pinball loss 改善 < 8% 或 PIT 偏离，本页将直接声明："
    "本状态机对未来 3 个月的黄金收益分布没有可靠的条件化能力，"
    "此前的“避险分流”描述仅限于同期价格路径，不构成任何前瞻性判断。"
)


def analysis_frame(panel: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "gpr": panel["gpr"].astype(float),
            "ret_gold": panel["ret_gold"].astype(float),
            "ret_csi": panel["ret_csi"].astype(float),
            "high_gpr": panel["high_gpr"].astype(float),
        },
        index=panel.index,
    )
    rename = {"tips10": "real_rate", "dollar_broad": "dollar", "vix": "vix"}
    for source, dest in rename.items():
        if source in states.columns:
            frame[dest] = pd.to_numeric(states[source].reindex(panel.index), errors="coerce")
    return frame


def _states(root: Path) -> pd.DataFrame:
    path = root / "replication" / "states_monthly.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "month" not in frame.columns:
        return pd.DataFrame()
    frame.index = pd.PeriodIndex(frame["month"].astype(str), freq="M")
    return frame.drop(columns=["month"])


def _crowding(root: Path, panel: pd.DataFrame, events: list[dict]) -> dict:
    path = root / "replication" / "cot_monthly.csv"
    if not path.exists():
        return {
            "status": "missing",
            "note": "CFTC 净多头还没有进入复现表。ETF 流量没有解析，所以 0.5/0.5 的拥挤度不计算。",
            "by_event": {},
        }
    frame = pd.read_csv(path)
    frame.index = pd.PeriodIndex(frame["month"].astype(str), freq="M")
    column = "cot_pct" if "cot_pct" in frame.columns else frame.columns[-1]
    by_event = {}
    for event in events:
        month = pd.Timestamp(event["date"]).to_period("M")
        if month not in frame.index or not pd.notna(frame.loc[month, column]):
            by_event[event["id"]] = None
            continue
        by_event[event["id"]] = round(float(frame.loc[month, column]), 4)
    eligible = frame.index[frame.index <= panel.index[-1]]
    latest = frame.index[-1] if len(eligible) == 0 else eligible[-1]
    return {
        "status": "ok",
        "column": column,
        "end": str(latest),
        "latest": None if not pd.notna(frame.loc[latest, column]) else round(float(frame.loc[latest, column]), 4),
        "by_event": by_event,
        "high_gpr": _high_gpr_followthrough(panel, frame, column),
        "note": "这里只是 CFTC 非商业净多头除以持仓量的 60 个月滚动分位。ETF 流量没有入库，所以不把这一列叫做两腿拥挤度。",
    }


def _high_gpr_followthrough(panel: pd.DataFrame, cot: pd.DataFrame, column: str) -> dict:
    """Describe the next 3-month gold return when GPR is already in its high bin."""
    gold = panel["ret_gold"].astype(float)
    high = panel["high_gpr"].astype(float)
    crowded: list[float] = []
    other: list[float] = []
    down = 0
    down_crowded = 0
    for loc, month in enumerate(panel.index):
        if loc + 3 >= len(panel) or month not in cot.index:
            continue
        flag = high.loc[month]
        pct = cot.loc[month, column]
        if isinstance(flag, pd.Series):
            flag = flag.iloc[-1]
        if isinstance(pct, pd.Series):
            pct = pct.iloc[-1]
        if not np.isfinite(flag) or float(flag) < 1 or not np.isfinite(pct):
            continue
        window = gold.iloc[loc + 1 : loc + 4]
        if not np.isfinite(window.to_numpy(dtype=float)).all():
            continue
        forward = float(window.sum())
        if float(pct) >= 0.9:
            crowded.append(forward)
        else:
            other.append(forward)
        if forward < 0:
            down += 1
            if float(pct) >= 0.9:
                down_crowded += 1

    def pack(samples: list[float]) -> dict:
        if not samples:
            return {"n": 0, "median_gold_3m": None}
        return {"n": len(samples), "median_gold_3m": round(float(np.median(samples)), 2)}

    return {
        "rule": "只看 GPR 已处在自身过去 60 个月 75 分位之上的月份，统计其后 3 个月黄金累计收益。0.9 以上记为拥挤。",
        "crowded": pack(crowded),
        "not_crowded": pack(other),
        "gold_down_n": down,
        "gold_down_and_crowded_n": down_crowded,
    }


def _forecast_line(regime: dict, validation: dict) -> dict:
    latest = regime.get("latest") or {}
    gold = ((latest.get("forward") or {}).get("3") or {}).get("gold") or {}
    timeline = regime.get("timeline") or []
    cell = None
    for row in reversed(timeline):
        if row.get("cell"):
            cell = row
            break
    body = {
        "issued": "2026-11-11",
        "state_month": latest.get("month"),
        "state": None if cell is None else cell.get("cell"),
        "analog_k": latest.get("k"),
        "indep_runs": latest.get("indep_runs"),
        "perm_statistic": latest.get("perm_statistic"),
        "perm_p": latest.get("perm_p"),
        "q10_3m": gold.get("p10"),
        "q50_3m": gold.get("p50"),
        "q90_3m": gold.get("p90"),
        "n": gold.get("n"),
        "model_version": LAB_VERSION,
        "validation_pass": (validation.get("gates") or {}).get("pass"),
        "resolved": None,
        "note": "状态月是样本钉里的最后一个完整月，不是发行日当天的行情。",
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["hash"] = hashlib.sha256(encoded).hexdigest()[:16]
    return body


def _append_forecast(path: Path, line: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    rows = [json.loads(item) for item in existing.splitlines() if item.strip()]
    if any(row.get("state_month") == line.get("state_month") and row.get("model_version") == line.get("model_version") for row in rows):
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def _dimensions(frame: pd.DataFrame) -> list[dict]:
    labels = (
        ("gpr", "地缘压力"),
        ("real_rate", "实际利率"),
        ("dollar", "美元"),
        ("vix", "风险厌恶"),
    )
    rows = []
    for name, label in labels:
        if name not in frame.columns:
            rows.append({"id": name, "label": label, "status": "missing"})
            continue
        pct = causal_percentile(frame[name].to_numpy(dtype=float))
        latest = pct[-1]
        previous = pct[-2] if pct.size > 1 else np.nan
        rows.append(
            {
                "id": name,
                "label": label,
                "status": "ok" if np.isfinite(latest) else "short",
                "pct": None if not np.isfinite(latest) else round(float(latest), 3),
                "prev": None if not np.isfinite(previous) else round(float(previous), 3),
            }
        )
    return rows


def _top_moves(panel: pd.DataFrame) -> list[str]:
    tail = panel["dgpr"].astype(float).iloc[-12:]
    ordered = tail.reindex(tail.abs().sort_values(ascending=False).index).head(3)
    return [f"{month} {value:+.1f}" for month, value in ordered.items()]


def _state_note(root: Path, regime: dict, forecast: dict, moves: list[str]) -> None:
    issued = pd.Timestamp("2026-10-13")
    week = issued.isocalendar()
    slug = f"{week.year}-W{int(week.week):02d}"
    folder = root / "docs" / "state"
    folder.mkdir(parents=True, exist_ok=True)
    latest = regime.get("latest") or {}
    gold = ((latest.get("forward") or {}).get("3") or {}).get("gold") or {}
    features = "、".join(latest.get("features") or []) or "无"
    label_sentence = (
        f"六格综合标签是 {forecast.get('state')}。"
        if forecast.get("state")
        else "六格综合标签没有形成。"
    )
    text = (
        f"样本最后完整月是 {forecast.get('state_month')}，{label_sentence}"
        f"实际利率和美元没有入库，单靠一项不能标松紧。这是历史分类，不是对下个月的预测。"
        f"相似月用到的维度是 {features}。"
        f"与它相距至少 12 个月的相似月有 {latest.get('k')} 个，分成 {latest.get('indep_runs')} 个独立区间。"
        f"置换检验比较这些月份之后 3 个月黄金收益的四分位距是否比随机月份更窄，p 值是 {latest.get('perm_p')}（{latest.get('perm_reps')} 次）。"
        f"这些相似月之后 3 个月的黄金累计收益，10/50/90 分位是 "
        f"{gold.get('p10')} / {gold.get('p50')} / {gold.get('p90')}（n={gold.get('n')}）。"
        f"样本内最近 12 个月 GPR 变动绝对值最大的三个月是：{'、'.join(moves)}。本页没有 11 月的实时 GPR。"
        f"前 12 个月的前瞻记录只积累，不作为预测成绩公布。"
    )
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>状态笔记 {slug}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
<main>
  <p><a href="../index.html">返回实验室</a> · <a href="index.html">全部笔记</a></p>
  <h1>状态笔记 {slug}</h1>
  <p>对应构建日 2026-10-13 的样本钉，不是日历上的实时一周。</p>
  <p>{text}</p>
</main>
</body>
</html>
"""
    (folder / f"{slug}.html").write_text(page, encoding="utf-8", newline="\n")
    index = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>状态笔记</title></head>
<body>
<main>
  <p><a href="../index.html">返回实验室</a></p>
  <h1>状态笔记</h1>
  <ul><li><a href="{slug}.html">{slug}</a></li></ul>
</main>
</body>
</html>
"""
    (folder / "index.html").write_text(index, encoding="utf-8", newline="\n")


def compute_phase_c(root: Path, panel: pd.DataFrame, events: list[dict], fast: bool = False) -> dict:
    frame = analysis_frame(panel, _states(root))
    regime = build_regime(frame, events, fast=fast)
    regime["dimensions"] = _dimensions(frame)
    rows = walk_forward(frame)
    validation = summarize_walk(rows) if not rows.empty else {"gates": {"pass": False}, "baselines": {}}
    validation["negative_template"] = NEGATIVE
    validation["declare_no_skill"] = not (
        validation.get("gates", {}).get("improvement_at_least_8pct")
        and validation.get("gates", {}).get("pit_ks_p_above_0_10")
    )
    out_dir = root / "output"
    out_dir.mkdir(exist_ok=True)
    if not rows.empty:
        forecast_table(rows).to_csv(out_dir / "oos_metrics.csv", index=False)
    (out_dir / "oos_summary.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    forecast = _forecast_line(regime, validation)
    _append_forecast(root / "registry" / "forecasts.jsonl", forecast)
    _state_note(root, regime, forecast, _top_moves(panel))
    return {
        "regime": regime,
        "validation": validation,
        "crowding": _crowding(root, panel, events),
        "forecast": forecast,
    }
