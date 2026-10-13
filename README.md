# 地缘政治风险 × 避险资产实验室

在线页面：<https://hantrleko.github.io/gpr-haven-lab/>

当前版本 V0.5。每日改动记在 `CHANGELOG.md`。

交互页面用来对照事件叙事。`figs/` 里的 PDF 是同一套定义导出的图。页面右上角可以切到英文。选中的事件和窗口写在网址里，例如 `https://hantrleko.github.io/gpr-haven-lab/?e=ukraine_2022&w=12&d=40`。早报提到对应新闻时，用这个链接。每个内置事件还有一张竖版卡片，在 `cards/` 里，页面上的「竖版卡片」会打开它。

## 打开

在线页面由 `docs/` 发布到 GitHub Pages。本地预览不要直接双击 html，在 `app/` 目录运行本地服务器，例如 `python -m http.server 8877`。`app/` 和 `docs/` 的页面、`lab_data.json`、图片和卡片是同一套。

数据不是自动日更。样本终点固定在 `2026-09`（`SAMPLE_END`，按 2026-10-13 这个截止日期钉住）。换一天运行 `build.py` 也不会把样本延到下一个月，除非改这个常数。

可选事件包括霍尔木兹（2019、2026）、阿布凯克、伊核制裁、克里米亚、对俄原油禁运、俄乌、加沙、2024 与 2025 年的美伊冲突，以及英国脱欧、朝鲜第六次核试验、佩洛西访台。日期是手工锚点，页面上附了来源链接，没有逐条核对原始电讯。事件名不写黄金涨跌。日期框可以临时加一个事件日，但样本最后一个月（2026-09）没有事后月份，页面会拒绝。

默认相关窗口是 12 个月。6 个月大约只有 6 个点，仍可手选。总表最后一列是黄金累计收益相对普通月份的分位。这些普通月份按种子 20261013 抽取，窗口里不包含内置事件月。

## 重跑

```powershell
python build.py
python -m unittest tests.test_benchmark
```

原始行情不要提交。雅虎 `GC=F`、`BZ=F`、`DX-Y.NYB`、`^HSI` 和新浪 `sh000300` 的条款没有把再分发权授给本仓库，所以 `data/raw/` 里的这些文件只留在本机，并写在 `.gitignore` 里。GPR 日度文件从 [matteoiacoviello.com](https://www.matteoiacoviello.com/gpr.htm) 下载，引用 Caldara–Iacoviello，不在 MIT 许可里重新授权。

`lab_data.json` 和 `output/panel_monthly.csv` 是算出来给页面用的。MIT 许可只覆盖 `src/`、`build.py` 和页面模板，不覆盖这些价格。

要在另一台机器上重跑，把下列文件放到 `data/raw/`，再运行 `build.py`。样本终点仍是代码里的 `SAMPLE_END`。

| 文件 | 内容 |
|---|---|
| `gold_gc.csv` | 雅虎 `GC=F` |
| `brent_bz.csv` | 雅虎 `BZ=F` |
| `dxy.csv` | 雅虎 `DX-Y.NYB` |
| `hsi.csv` | 雅虎 `^HSI` |
| `csi300_sina.csv` | 新浪 `sh000300` |
| `data_gpr_daily_recent.xls` | Caldara–Iacoviello 日度 GPR |

## 许可

代码许可见 `LICENSE`。行情数据不能凭这个许可再分发。

## 序列

| 序列 | 来源 | 注意 |
|---|---|---|
| GPR | Caldara–Iacoviello 日度 GPRD，月内取均值 | 2026-10-13 从 matteoiacoviello.com 下载 |
| 黄金 | Yahoo `GC=F` | COMEX 近月期货，不是 LBMA 定盘价 |
| 布伦特 | Yahoo `BZ=F` | ICE 近月期货，月度收益含换月 |
| 美元 | Yahoo `DX-Y.NYB` | 洲际美元指数，不是美联储贸易加权美元 |
| 沪深300 | 新浪 `sh000300` | 价格指数。正文归档应换中证或 Wind/CSMAR |
| 恒生 | Yahoo `^HSI` | 价格指数 |

收益是月末收盘的对数差分再乘 100，没有减去无风险利率。

## 避险强度

在一个窗口里把三项等权平均，50 表示相关为 0。这是本实验室自定的描述性指标，不是文献里的标准避险指数：

- 权益对冲：黄金与沪深300、恒生的平均相关越负越高
- GPR 联动：黄金收益与 GPR 月度差分越同向越高
- 美元对冲：黄金与美元指数越反向越高

页面上的稳健性表会换成四对相关等权和权益权重 50%，也会把 GPR 那一项换成 Caldara–Iacoviello 的行动子指数或威胁子指数。自定面板里可以改 VAR 的变量排序。只有论文顺序带 90% 区间。

滚动图用过去 36 个月。高压月份是 GPR 高于自身过去 60 个月的 75% 分位。60 和 45 是实验室的着色阈值，不是估计出来的结构参数。短于 12 个月的相关只作对照。

## VAR

六变量月度 VAR。Cholesky 顺序：GPR 变动、布伦特、美元、黄金、沪深300、恒生。滞后在 1 到 3 阶里按 AIC 选取。图中是 1 个标准差正向 GPR 冲击的累计响应，阴影为残差自助法 90% 区间。这是递归顺序，不是结构识别。

## 图

- `figs/gold_excess_6m.pdf`：事件后 6 个月，黄金相对沪深300和恒生的累计收益差
- `figs/corr_delta_6m.pdf`、`figs/corr_delta_12m.pdf`：黄金与股指相关的变化
- `figs/haven_regime.pdf`：滚动避险强度
- `figs/rolling_corr_heatmap.pdf`：36 个月滚动相关
- `figs/var_irf_gpr.pdf`：累计脉冲响应
- `figs/events/`：每个事件的价格路径和相关柱

`output/event_window_summary.csv` 是 6 个月和 12 个月窗口的数字。`output/panel_monthly.csv` 是月度面板。
