"""Vertical share cards, one event per image.

Each card states the six-month gold and CSI 300 cumulative log returns and
draws those two paths. The event name does not say whether gold rose or fell.
When gold is up and CSI 300 is down, the tail uses the same three branches as
``claim_rule.js``: a middle placebo percentile, or a five-session gold CAR
q-value above 0.10, does not get the safe-haven-split wording.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

from havenlab.engine import ROOT, event_window
from havenlab.version import LAB_VERSION

SITE = "https://hantrleko.github.io/gpr-haven-lab/"


def _font() -> None:
    for candidate in (Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")):
        if not candidate.exists():
            continue
        font_manager.fontManager.addfont(str(candidate))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(candidate)).get_name()
        plt.rcParams["axes.unicode_minus"] = False
        return


def _rebase(path: dict) -> tuple[list[int], list[float]] | None:
    if not path["tau"] or 0 not in path["tau"]:
        return None
    base = path["value"][path["tau"].index(0)]
    if base is None or not np.isfinite(base) or base == 0:
        return None
    xs, ys = [], []
    for tau, value in zip(path["tau"], path["value"]):
        if value is None or not np.isfinite(value):
            continue
        xs.append(int(tau))
        ys.append(100.0 * float(value) / float(base))
    return xs, ys


def _q_text(q: float) -> str:
    return f"{math.floor(float(q) * 100 + 0.5) / 100:.2f}"


def split_claim(g: float, c: float, pct: float | None, q: float | None, pct_lo: float | None = None, pct_hi: float | None = None) -> str:
    """Chinese gold-up / CSI-down branch of claim_rule.js."""
    from havenlab.claim_text import interval_tail

    tail_ok = interval_tail(pct, pct_lo, pct_hi)
    mid = pct is not None and not tail_ok
    q_fail = q is not None and float(q) > 0.10
    q_text = "" if q is None else _q_text(float(q))
    car_fail = f"事件日起 5 个交易日的黄金 CAR 未通过多重比较校正（q={q_text}）。"
    car_pass = f"事件后 5 个交易日黄金 CAR 的 q 值为 {q_text}。"
    if tail_ok and not q_fail:
        claim = "黄金上涨而沪深300下跌，价格路径与避险分流一致。"
        if q is not None:
            claim += car_pass
        return claim
    if q_fail:
        mid_bit = "黄金累计收益落在普通月份的中间分位。" if mid else ""
        return "黄金上涨而沪深300下跌。" + mid_bit + car_fail
    if pct is None:
        return "黄金上涨而沪深300下跌。没有普通月份分位，这次价格分开只按路径描述。"
    claim = "黄金上涨而沪深300下跌，但黄金累计收益落在普通月份的中间分位，这次价格分开只按路径描述。"
    if q is not None:
        claim += car_pass
    return claim


def _sentence(window: dict, pct: float | None = None, q: float | None = None) -> tuple[str, str]:
    gold = window["cum"]["gold"]
    csi = window["cum"]["csi"]
    gold_txt = "—" if gold is None else f"{gold:+.1f}%"
    csi_txt = "—" if csi is None else f"{csi:+.1f}%"
    if window["partial"]:
        tail = "窗口被样本末端截断。"
    elif gold is not None and csi is not None and gold > 0 and csi < 0:
        tail = split_claim(gold, csi, pct, q).rstrip()
    elif gold is not None and gold < 0:
        tail = "黄金在这段窗口里下跌。"
    else:
        tail = "黄金和沪深300没有反向分开。"
    line = f"事后 {window['n_after']} 个月：黄金 {gold_txt}，沪深300 {csi_txt}。"
    return line, tail


def _blocked_gold(lab: dict) -> list[float]:
    bundle = (lab.get("placebo") or {}).get("6") or {}
    blocked = bundle.get("blocked") or {}
    series = blocked.get("gold") or bundle.get("gold") or []
    return [float(item) for item in series if item is not None]


def _gold_pct(value: float | None, series: list[float]) -> float | None:
    if value is None or not series:
        return None
    n = sum(1 for item in series if item <= float(value) + 1e-9)
    return n / len(series)


def _car_q(lab: dict, event_id: str) -> float | None:
    try:
        q = lab["car"]["by_event"][event_id]["gold"]["m1_p5"]["q"]
    except (KeyError, TypeError):
        return None
    if q is None:
        return None
    return float(q)


def export_cards(lab: dict, dest: Path) -> None:
    _font()
    dest.mkdir(parents=True, exist_ok=True)
    logo = None
    for logo_path in (ROOT / "docs" / "logo.webp", ROOT / "app" / "logo.webp", ROOT / "app" / "ef-logo.jpg"):
        if not logo_path.exists():
            continue
        try:
            logo = plt.imread(logo_path)
            break
        except Exception:
            logo = None
    panel = lab["panel"]
    placebo_gold = _blocked_gold(lab)
    for event in lab["events"]:
        window = event_window(panel, event["month"], 6)
        pct = _gold_pct(window["cum"]["gold"], placebo_gold)
        q = _car_q(lab, event["id"])
        path = event.get("path") or {}
        gold = _rebase(path["gold"]) if path.get("gold") else None
        csi = _rebase(path["csi"]) if path.get("csi") else None
        fig = plt.figure(figsize=(9, 12), dpi=120, facecolor="#fbfaf6")
        fig.text(0.5, 0.46, "EF", ha="center", va="center", fontsize=120, color="#1f4b73", alpha=0.06)
        if logo is not None:
            ax_logo = fig.add_axes((0.08, 0.90, 0.12, 0.07))
            ax_logo.imshow(logo)
            ax_logo.axis("off")
        fig.text(0.24, 0.945, "EF Lab", fontsize=18, color="#1f4b73", fontweight="bold")
        fig.text(0.24, 0.915, "仅供学习与研究，不构成投资建议", fontsize=11, color="#3a342c")
        fig.text(0.08, 0.84, event["name"], fontsize=28, color="#1c1915", fontweight="bold")
        fig.text(0.08, 0.80, event.get("name_en", ""), fontsize=14, color="#3a342c")
        fig.text(0.08, 0.76, event["date"], fontsize=14, color="#3a342c")
        line, tail = _sentence(window, pct, q)
        fig.text(0.08, 0.70, line, fontsize=18, color="#1c1915")
        fig.text(0.08, 0.66, tail, fontsize=16, color="#3a342c")
        after = window.get("haven_after") or {}
        score = after.get("score")
        se = after.get("se")
        if score is not None and se is not None:
            lo = float(after.get("ci_lo"))
            hi = float(after.get("ci_hi"))
            short = int(window.get("n_after") or 0) < 24
            if short or not (lo > 60 or hi < 45):
                bar_color = "#8a8478"
            elif lo > 60:
                bar_color = "#0072B2"
            else:
                bar_color = "#D55E00"
            note = f"强度 {score:.0f} [{lo:.0f}, {hi:.0f}]"
            if short:
                note += " · 样本不足以判定"
            elif lo < 50 < hi:
                note += " · 区间跨过 50，不解读为强或弱"
            fig.text(0.08, 0.62, note, fontsize=13, color="#3a342c")
            bar = fig.add_axes((0.10, 0.585, 0.55, 0.012))
            bar.set_xlim(0, 100)
            bar.set_ylim(0, 1)
            bar.axvspan(max(0.0, lo), min(100.0, hi), color=bar_color, alpha=0.35)
            bar.plot([score], [0.5], marker="|", color="#1c1915", markersize=10)
            bar.axvline(50, color="#c8c2b6", lw=0.6)
            bar.set_yticks([])
            bar.set_xticks([])
            for spine in bar.spines.values():
                spine.set_visible(False)
        ax = fig.add_axes((0.10, 0.16, 0.82, 0.40))
        ax.set_facecolor("#fbfaf6")
        if gold:
            ax.plot(gold[0], gold[1], color="#C47B12", lw=2.4, label="黄金")
        if csi:
            ax.plot(csi[0], csi[1], color="#1F4E79", lw=1.6, label="沪深300")
        ax.axvline(0, color="#8a8478", lw=0.8, ls="--")
        ax.axhline(100, color="#c8c2b6", lw=0.8, ls="--")
        ax.set_ylabel("事件日收盘 = 100")
        ax.legend(frameon=False, loc="best")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        link = f"{SITE}?e={event['id']}&w=6&d=40"
        fig.text(0.08, 0.08, link, fontsize=11, color="#1f4b73")
        fig.text(0.08, 0.05, f"描述性窗口，不是因果识别。EF Lab {LAB_VERSION}", fontsize=11, color="#3a342c")
        fig.savefig(dest / f"{event['id']}.jpg", format="jpg", facecolor=fig.get_facecolor())
        plt.close(fig)


def copy_cards(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.glob("*.jpg"):
        shutil.copyfile(path, dest / path.name)
