# 更新记录

## 2026-11-02 · V2.0

- **局部投影**：每个期限直接回归累计收益，不再把各期系数相加。同时给出地缘行动、地缘威胁，以及上月高压与否的状态依赖结果。页面可以切换 VAR 与这几组投影。
- **事件研究**：内置事件增加日度均值调整 CAR，估计窗为交易日 [-120, -20]，并报告跨事件的 Benjamini–Hochberg q 值。
- **强度**：滚动避险强度增加权重包络和第一主成分。2026-01-30 黄金期货跳变给出把该日收益记为 0 后的 1 月对照。
- **工程**：首屏先用月度包渲染，日度包后台加载。`build.py --from-derived` 可从派生月度表面板重建。`fetch_data.py --extended` 可选拉取白银、VIX、美债收益率和 TIPS。页面源码拆到 `src/havenlab/ui/`。论文表写到 `replication/tables_latex.tex`。

## 2026-10-25 · V1.0

- **可复现**：新增 `fetch_data.py`（GPR 官方 xls、Yahoo chart、akshare 沪深300、可选 FRED LBMA），`data/raw/manifest.json` 校验和。
- **数据分包**：首屏 `lab_data_monthly.json`，日度 `lab_data_daily.json`；保留完整 `lab_data.json`。
- **方法**：安慰剂增加非重叠窗口（默认分位）；JSON `windows` 含黄金–沪深300 相关变化 Fisher 近似区间；VAR 附带局部投影 `var.lp`。
- **工程**：`scripts/check.py` 本地冒烟；`docs/api/v1/manifest.json`；`replication/` 派生表；`CITATION.cff`；论文配套 `paper.html`、RSS、嵌入页。
- **品牌**：全站版本号 V1.0；移除冗余 `ef-logo.jpg`；页脚链复现流程。

## 2026-10-13 · V0.5

（见 git 历史。）

## 2026-10-13 · V0.4

（见 git 历史。）

## 2026-10-13 · V0.3

（见 git 历史。）

## 2026-10-13 · V0.2

（见 git 历史。）

## 2026-10-13 · V0.1

（见 git 历史。）
