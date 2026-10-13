"""Vertical share cards, one event per image.

Each card states the six-month gold and CSI 300 cumulative log returns and
draws those two paths. The event name does not say whether gold rose or fell.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

from havenlab.engine import ROOT, event_window

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


def _sentence(window: dict) -> tuple[str, str]:
    gold = window["cum"]["gold"]
    csi = window["cum"]["csi"]
    gold_txt = "—" if gold is None else f"{gold:+.1f}%"
    csi_txt = "—" if csi is None else f"{csi:+.1f}%"
    if window["partial"]:
        tail = "窗口被样本末端截断。"
    elif gold is not None and csi is not None and gold > 0 and csi < 0:
        tail = "黄金上涨、沪深300下跌，价格上像避险分流。"
    elif gold is not None and gold < 0:
        tail = "黄金在这段窗口里下跌。"
    else:
        tail = "黄金和沪深300没有反向分开。"
    line = f"事后 {window['n_after']} 个月：黄金 {gold_txt}，沪深300 {csi_txt}。"
    return line, tail


def export_cards(lab: dict, dest: Path) -> None:
    _font()
    dest.mkdir(parents=True, exist_ok=True)
    logo_path = ROOT / "app" / "ef-logo.jpg"
    logo = plt.imread(logo_path) if logo_path.exists() else None
    panel = lab["panel"]
    for event in lab["events"]:
        window = event_window(panel, event["month"], 6)
        gold = _rebase(event["path"]["gold"])
        csi = _rebase(event["path"]["csi"])
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
        line, tail = _sentence(window)
        fig.text(0.08, 0.70, line, fontsize=18, color="#1c1915")
        fig.text(0.08, 0.66, tail, fontsize=16, color="#3a342c")
        ax = fig.add_axes((0.10, 0.18, 0.82, 0.42))
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
        fig.text(0.08, 0.05, "描述性窗口，不是因果识别。EF Lab V0.5", fontsize=11, color="#3a342c")
        fig.savefig(dest / f"{event['id']}.jpg", format="jpg", facecolor=fig.get_facecolor())
        plt.close(fig)


def copy_cards(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.glob("*.jpg"):
        shutil.copyfile(path, dest / path.name)
