# 交接

维护预算是每周 30 分钟：看一次周更是否成功，读一眼 CI，确认状态笔记是否生成。超出这个预算的功能不要加。

## 三条命令

```powershell
pip install -r requirements.txt
python fetch_data.py
python build.py
```

没有原始行情时，用 `python build.py --from-derived`。它读 `data/sample_pin.json`，不会把样本从 2026-09 往前推。

数据源体检：

```powershell
python fetch_data.py --sources-check --strict
```

`--strict` 只在 GPR 主文件失败时返回非零。状态序列失败会写进 `data/sources_status.json` 并打到 stderr。

## 五个数据源

| 用途 | 位置 |
|---|---|
| GPR | matteoiacoviello.com 的日度 xls |
| 黄金现货 | 新浪 `XAU`，文件 `data/raw/gold_lbma_fred.csv` |
| 期货与汇率 | Yahoo `GC=F`、`BZ=F`、`DX-Y.NYB`、`^HSI` |
| 沪深300 | 新浪 `sh000300` |
| 状态与资金面 | FRED `DFII10`、`DTWEXBGS`、`VIXCLS`；CFTC 黄金持仓；美国 EPU |

## 两个已知的坑

- FRED 的 `GOLDAMGBD228NLBM` 和 `GOLDPMGBD228NLBM` 返回 404。不要再把它们当成现货主序列。
- Stooq 的 `xauusd` 会返回一段要求 JavaScript 的页面，不是价格。这条备选作废。

VIX 若 FRED 超时，复现表里可能只有本机 CBOE 收盘，截止日期写在 `replication/state_notes.json`。实际利率或美元缺失时，六格综合状态留空。

## 引用

`CITATION.cff` 还没有 Zenodo DOI。打 tag 并完成归档之后，把返回的 DOI 写进 `identifiers`，不要先编一个。
