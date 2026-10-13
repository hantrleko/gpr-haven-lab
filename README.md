# 地缘政治风险 × 避险资产实验室

在线页面：<https://hantrleko.github.io/gpr-haven-lab/>

交互页面用来对照事件叙事。`figs/` 里的 PDF 是同一套定义导出的图。

## 打开

在线页面由 `docs/index.html` 发布到 GitHub Pages。本地预览用 `app/index.html`，两份内容相同。

可选事件包括霍尔木兹（2019、2026）、阿布凯克、伊核制裁、克里米亚、对俄原油禁运、俄乌、加沙、2024 与 2025 年的美伊冲突。日期框可以临时加一个事件日。

## 重跑

```powershell
python build.py
```

原始文件在 `data/raw/`。构建不重新下载。样本自动停在已结束的月份。

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

在一个窗口里把三项等权平均，50 表示相关为 0：

- 权益对冲：黄金与沪深300、恒生的平均相关越负越高
- GPR 联动：黄金收益与 GPR 月度差分越同向越高
- 美元对冲：黄金与美元指数越反向越高

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
