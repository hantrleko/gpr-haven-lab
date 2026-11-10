# 复现包（V2.4.0）

本目录在每次 `python build.py` 后从 `output/` 同步派生表，便于 Zenodo / 附录引用。

1. 安装依赖：`pip install -r requirements.txt`
2. 下载原始数据：`python fetch_data.py`（文件落在 `data/raw/`，不进 git）
3. 构建：`python build.py`。没有原始行情时用 `python build.py --from-derived`。
4. 校验：`python scripts/check.py`
5. 论文表：`tables_latex.tex`，日度异常收益：`event_daily_car.csv`。

代码许可见仓库根目录 `LICENSE`；行情原始文件不在 MIT 许可范围内。
