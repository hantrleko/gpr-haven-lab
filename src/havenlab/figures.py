"""Publication figures. One claim per figure. Okabe-Ito colors.

Question each figure answers is written in the function docstring and the title.
Audience: standalone figures that can also sit in a paper with a caption.
Output: PDF and PNG under figs/.
Color encodes the series or the sign of a contrast, not decoration.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

from havenlab.engine import ASSETS, HAVEN_ON, HEATMAP_PAIRS, ROLL, event_window
from havenlab.events import EVENTS

BLUE = "#0072B2"
VERMILLION = "#D55E00"
ORANGE = "#E69F00"
GREEN = "#009E73"
SKY = "#56B4E9"
PINK = "#CC79A7"
INK = "#1c1915"
MUTED = "#5c564c"
GRID = "#eceae4"
PAPER = "#ffffff"

SERIES_COLOR = {
    "gold": ORANGE,
    "brent": VERMILLION,
    "dxy": BLUE,
    "csi": GREEN,
    "hsi": PINK,
}
SERIES_LABEL = {
    "gold": "黄金",
    "brent": "布伦特",
    "dxy": "美元指数",
    "csi": "沪深300",
    "hsi": "恒生",
}

SOURCE = "来源：Caldara–Iacoviello GPRD 月均；Yahoo GC=F、BZ=F、DX-Y.NYB、^HSI；新浪沪深300。价格为月末收盘，收益为对数差分×100。"
SOURCE_DAILY = "来源：Caldara–Iacoviello 日度 GPRD；Yahoo GC=F、BZ=F、DX-Y.NYB、^HSI；新浪沪深300。指数以事件前最后收盘为 100。期货价格含换月。"


def set_style() -> None:
    for candidate in (Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")):
        if not candidate.exists():
            continue
        try:
            font_manager.fontManager.addfont(str(candidate))
            name = font_manager.FontProperties(fname=str(candidate)).get_name()
            plt.rcParams["font.family"] = name
            break
        except Exception:
            continue
    plt.rcParams.update(
        {
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.facecolor": PAPER,
            "axes.facecolor": PAPER,
            "axes.edgecolor": "#c8c2b6",
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "text.color": INK,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 9,
        }
    )


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = getattr(fig, "_lab_footer", "")
    try:
        fig.tight_layout()
    except Exception:
        pass
    fig.subplots_adjust(bottom=0.20)
    if text:
        fig.text(0.0, 0.012, text, ha="left", va="bottom", fontsize=7, color=MUTED)
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.15)
    fig.savefig(path.with_suffix(".png"), dpi=160, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def _footer(fig: plt.Figure, text: str) -> None:
    fig._lab_footer = text


def figure_excess(summary: pd.DataFrame, path: Path) -> None:
    """Did gold outperform equities in the six months after each event?"""
    part = summary[summary["window_months"] == 6].copy()
    labels = []
    for row in part.itertuples():
        mark = "*" if row.partial else ""
        labels.append(f"{row.event_name}{mark}")
    y = np.arange(len(part))
    fig, ax = plt.subplots(figsize=(6.6, 6.4))
    height = 0.38
    ax.barh(y + height / 2, part["gold_minus_csi"], height=height, color=BLUE, label="黄金 − 沪深300")
    ax.barh(y - height / 2, part["gold_minus_hsi"], height=height, color=ORANGE, label="黄金 − 恒生")
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("事件后 6 个月累计对数收益差（百分点）")
    ax.set_title("事件后 6 个月，黄金相对股指的累计表现")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    _footer(fig, SOURCE + " 正值表示黄金累计涨幅高于该股指。* 表示窗口被样本端点截断。")
    _save(fig, path)


def figure_corr_delta(summary: pd.DataFrame, path: Path, width: int) -> None:
    """Did gold-equity correlation fall after the event?"""
    part = summary[summary["window_months"] == width].copy()
    labels = [f"{row.event_name}{'*' if row.partial else ''}" for row in part.itertuples()]
    csi = part["corr_gold_csi_after"] - part["corr_gold_csi_before"]
    hsi = part["corr_gold_hsi_after"] - part["corr_gold_hsi_before"]
    y = np.arange(len(part))
    fig, ax = plt.subplots(figsize=(6.6, 6.4))
    height = 0.38
    ax.barh(y + height / 2, csi, height=height, color=BLUE, label="黄金–沪深300")
    ax.barh(y - height / 2, hsi, height=height, color=GREEN, label="黄金–恒生")
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel(f"相关系数变化（事后 − 事前），窗口 {width} 个月")
    ax.set_title(f"事件前后黄金与股指相关的变化（{width} 个月）")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    _footer(fig, SOURCE + " 负值表示事件后相关下降。短窗口相关不稳定。* 表示窗口不完整。")
    _save(fig, path)


def figure_haven(panel: pd.DataFrame, path: Path) -> None:
    """When GPR is in its own trailing top quartile, is the haven score high?"""
    score = panel["haven_score"]
    high = panel["high_gpr"]
    dates = panel.index.to_timestamp(how="end")
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    in_run = False
    start = None
    for stamp, flag in zip(dates, high.to_numpy(dtype=float)):
        on = np.isfinite(flag) and flag >= 1
        if on and not in_run:
            start = stamp
            in_run = True
        elif not on and in_run:
            ax.axvspan(start, stamp, color="#f3e2d2", linewidth=0)
            in_run = False
    if in_run:
        ax.axvspan(start, dates[-1], color="#f3e2d2", linewidth=0)
    ax.plot(dates, score, color=INK, linewidth=1.3, label=f"{ROLL} 个月避险强度")
    ax.axhline(50, color=MUTED, linewidth=0.8, linestyle="--", label="零相关基准 50")
    ax.axhline(HAVEN_ON, color=BLUE, linewidth=0.7, linestyle=":", label=f"高压下生效线 {HAVEN_ON:.0f}")
    ax.set_ylabel("避险强度")
    ax.set_xlabel("月份")
    ax.set_title("滚动避险强度与高压地缘月份")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.set_ylim(35, 85)
    _footer(fig, SOURCE + " 阴影为 GPR 高于自身过去 60 个月 75% 分位的月份。强度线用过去 36 个月相关。")
    _save(fig, path)


def figure_heatmap(corrs: pd.DataFrame, path: Path) -> None:
    """How has gold's rolling correlation with the other assets moved?"""
    labels = []
    matrix = []
    keys = [item[0] for item in HEATMAP_PAIRS]
    names = [item[1] for item in HEATMAP_PAIRS]
    for period, row in corrs.iterrows():
        if int(period.month) not in (3, 6, 9, 12):
            continue
        values = row[keys].to_numpy(dtype=float)
        if not np.isfinite(values).any():
            continue
        labels.append(f"{period.year}Q{period.quarter}")
        matrix.append(values)
    data = np.array(matrix).T
    cmap = LinearSegmentedColormap.from_list("oi_div", [BLUE, "#f7f4ee", VERMILLION])
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    image = ax.imshow(data, aspect="auto", cmap=cmap, vmin=-1, vmax=1, interpolation="nearest")
    ax.set_yticks(np.arange(len(names)))
    ax.set_yticklabels(names)
    ticks = [i for i, label in enumerate(labels) if label.endswith("Q1")]
    ax.set_xticks(ticks)
    ax.set_xticklabels([labels[i][:4] for i in ticks])
    ax.set_xlabel("季度（窗口止于该季末）")
    ax.set_title(f"黄金与其他序列的 {ROLL} 个月滚动相关")
    ax.grid(False)
    bar = fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    bar.set_label("相关系数")
    _footer(fig, SOURCE + " 蓝色为负相关，橙色为正相关。黄金–GPR 使用 GPR 月度差分。")
    _save(fig, path)


def figure_irf(var: dict, path: Path) -> None:
    """What is the cumulative price path after a positive GPR innovation?"""
    keys = var["keys"]
    horizon = np.asarray(var["horizon"])
    fig, axes = plt.subplots(2, 3, figsize=(7.6, 5.8), sharex=True)
    for ax, key, name, unit in zip(axes.ravel(), keys, var["order"], var["units"]):
        point = np.asarray(var["cum"][key], dtype=float)
        lower = np.asarray(var["lo"][key], dtype=float)
        upper = np.asarray(var["hi"][key], dtype=float)
        ax.fill_between(horizon, lower, upper, color=SKY, alpha=0.35, linewidth=0)
        ax.plot(horizon, point, color=BLUE, linewidth=1.4)
        ax.axhline(0, color=INK, linewidth=0.7)
        ax.set_title(f"{name}（{unit}）", fontsize=9)
        ax.set_ylabel("累计响应")
    for ax in axes[1, :]:
        ax.set_xlabel("月")
    fig.suptitle(
        f"正向 GPR 冲击的累计脉冲响应（VAR {var['lags']} 阶，T={var['t']}）",
        fontsize=11,
    )
    _footer(
        fig,
        "递归识别：GPR变动、布伦特、美元、黄金、沪深300、恒生。阴影为残差自助法 90% 区间。"
        "收益的累计响应是月度对数收益百分点之和。不是结构因果。",
    )
    _save(fig, path)


def figure_event_path(event: dict, path: Path, sessions: int = 40) -> None:
    """Price path around one dated event, indexed to the last close before it."""
    fig, (ax, axg) = plt.subplots(2, 1, figsize=(6.6, 5.2), sharex=True, height_ratios=[2.3, 1])
    for name in ASSETS:
        packed = event["path"][name]
        tau = np.asarray(packed["tau"])
        value = np.asarray(packed["value"], dtype=float)
        keep = (tau >= -sessions) & (tau < sessions)
        ax.plot(tau[keep], value[keep], color=SERIES_COLOR[name], linewidth=1.3, label=SERIES_LABEL[name])
    ax.axvline(0, color=MUTED, linewidth=0.8, linestyle="--")
    ax.axhline(100, color=GRID, linewidth=0.8)
    ax.set_ylabel("指数（事件前最后收盘 = 100）")
    ax.set_title(f"{event['name']}（{event['date']}）前后 {sessions} 个交易日")
    ax.legend(frameon=False, ncol=5, loc="upper left")
    gpr = event["path"]["gpr"]
    gtau = np.asarray(gpr["tau"])
    gval = np.asarray([np.nan if value is None else value for value in gpr["value"]], dtype=float)
    keep = (gtau >= -sessions) & (gtau < sessions)
    axg.plot(gtau[keep], gval[keep], color=INK, linewidth=1.2)
    axg.axvline(0, color=MUTED, linewidth=0.8, linestyle="--")
    axg.set_ylabel("GPR 日度水平")
    axg.set_xlabel("交易日（0 = 事件日或其后第一个交易日；GPR 对齐黄金交易日）")
    _footer(fig, SOURCE_DAILY)
    _save(fig, path)


def figure_event_corr(panel: pd.DataFrame, event: dict, path: Path, width: int = 12) -> None:
    """Before versus after correlations for one event."""
    window = event_window(panel, event["month"], width)
    before = window["haven_before"]
    after = window["haven_after"]
    if before is None or after is None:
        return
    labels = ["黄金–布伦特", "黄金–美元", "黄金–沪深300", "黄金–恒生", "黄金–GPR变动"]
    keys = ["corr_gold_brent", "corr_gold_dxy", "corr_gold_csi", "corr_gold_hsi", "corr_gold_dgpr"]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    ax.bar(x - 0.18, [before[key] for key in keys], width=0.36, color=BLUE, label=f"事前 {window['n_before']} 个月")
    ax.bar(x + 0.18, [after[key] for key in keys], width=0.36, color=VERMILLION, label=f"事后 {window['n_after']} 个月")
    ax.axhline(0, color=INK, linewidth=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("相关系数")
    ax.set_ylim(-1, 1)
    title = f"{event['name']}：事件前后相关（{width} 个月）"
    if window["partial"]:
        title += "，窗口不完整"
    ax.set_title(title)
    ax.legend(frameon=False)
    ax.grid(axis="x", visible=False)
    _footer(fig, SOURCE + " 事前不含事件月，事后含事件月。")
    _save(fig, path)


def export_all(lab: dict, fig_dir: Path) -> None:
    set_style()
    summary = lab["summary"]
    panel = lab["panel"]
    figure_excess(summary, fig_dir / "gold_excess_6m")
    figure_corr_delta(summary, fig_dir / "corr_delta_6m", 6)
    figure_corr_delta(summary, fig_dir / "corr_delta_12m", 12)
    figure_haven(panel, fig_dir / "haven_regime")
    figure_heatmap(lab["corrs"], fig_dir / "rolling_corr_heatmap")
    figure_irf(lab["var"], fig_dir / "var_irf_gpr")
    event_dir = fig_dir / "events"
    for event in lab["events"]:
        figure_event_path(event, event_dir / f"{event['id']}_path")
        figure_event_corr(panel, event, event_dir / f"{event['id']}_corr12", 12)
        figure_event_corr(panel, event, event_dir / f"{event['id']}_corr6", 6)
