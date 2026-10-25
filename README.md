# 地缘政治风险 × 避险资产实验室

在线页面：<https://hantrleko.github.io/gpr-haven-lab/>

当前版本 **V1.0**。每日改动记在 `CHANGELOG.md`。

交互页面用来对照事件叙事。`figs/` 里的 PDF 是同一套定义导出的图。页面右上角可以切到英文。选中的事件和窗口写在网址里，例如 `https://hantrleko.github.io/gpr-haven-lab/?e=ukraine_2022&w=12&d=40`。论文配套说明见 [`docs/paper.html`](docs/paper.html)。

## 打开

在线页面由 `docs/` 发布到 GitHub Pages。本地预览不要直接双击 html，在 `app/` 目录运行本地服务器，例如 `python -m http.server 8891`。首屏加载 `lab_data_monthly.json`，日度序列在 `lab_data_daily.json`。

数据不是自动日更。样本终点固定在 `2026-09`（`SAMPLE_END`）。换一天运行 `build.py` 也不会把样本延到下一个月，除非改这个常数。

## 重跑（V1.0 推荐流程）

```powershell
pip install -r requirements.txt
python fetch_data.py
python build.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/check.py
```

`fetch_data.py` 把原始文件写到 `data/raw/`（不进 git）。`build.py` 生成页面、`figs/`、`replication/` 派生表和 `docs/api/v1/manifest.json`。

若你已有 V0.5 时代的六个 raw 文件，可跳过 `fetch_data.py`，直接 `build.py`。

| 文件 | 内容 |
|---|---|
| `gold_gc.csv` | 雅虎 `GC=F` |
| `brent_bz.csv` | 雅虎 `BZ=F` |
| `dxy.csv` | 雅虎 `DX-Y.NYB` |
| `hsi.csv` | 雅虎 `^HSI` |
| `csi300_sina.csv` | 新浪 `sh000300` |
| `data_gpr_daily_recent.xls` | Caldara–Iacoviello 日度 GPR |
| `gold_lbma_fred.csv` | 可选，FRED LBMA 定盘对照 |

## 许可

代码许可见 `LICENSE`。行情数据不能凭这个许可再分发。引用软件请见 `CITATION.cff`。

## 序列与方法

与 V0.5 相同：GPR 月内均值、月末对数收益×100、自定避险强度、递归 VAR + 自助区间。V1.0 新增：

- 安慰剂：**非重叠**普通月份窗口为默认分位；重叠池在 `placebo.<w>.overlapping`。
- 相关变化：`windows.<event>.<w>.corr_gold_csi` 含近似 90% 区间。
- 脉冲：`var.lp` 为 GPR 冲击的局部投影累计响应（描述性，非结构因果）。

## 图与输出

- `figs/`：论文图（含 6m/12m 相关变化、超额收益等）
- `output/panel_monthly.csv`、`output/event_window_summary.csv`
- `replication/`：每次构建复制的派生表
