"""Hand-dated geopolitical episodes used by the lab.

Dates are annotation anchors, not estimated break points. Monthly windows use
the calendar month of `date`. Daily paths set t = 0 to the first session on or
after `date`, so a weekend onset sits between t = -1 and t = 0.
"""

from __future__ import annotations

EVENTS: list[dict[str, str]] = [
    {
        "id": "libya_2011",
        "date": "2011-02-22",
        "group": "冲突升级",
        "name": "利比亚冲突升级",
        "note": "2011年2月22日卡扎菲发表镇压演说，利比亚抗议转入内战，随后数月油价上行。",
    },
    {
        "id": "crimea_2014",
        "date": "2014-03-18",
        "group": "制裁",
        "name": "克里米亚并入与制裁",
        "note": "2014年3月18日俄罗斯完成对克里米亚的吞并，欧美制裁随后加码。",
    },
    {
        "id": "jcpoa_2018",
        "date": "2018-05-08",
        "group": "制裁",
        "name": "美国退出伊核协议",
        "note": "2018年5月8日美国宣布退出JCPOA，并重启对伊朗制裁。",
    },
    {
        "id": "hormuz_2019",
        "date": "2019-06-13",
        "group": "海峡与石油",
        "name": "霍尔木兹油轮遇袭",
        "note": "2019年6月13日阿曼湾两艘油轮遇袭，霍尔木兹通航风险上升。",
    },
    {
        "id": "abqaiq_2019",
        "date": "2019-09-14",
        "group": "海峡与石油",
        "name": "阿布凯克设施遇袭",
        "note": "2019年9月14日沙特阿布凯克与胡赖斯石油设施遇袭，短期打断大量原油产能。",
    },
    {
        "id": "soleimani_2020",
        "date": "2020-01-03",
        "group": "冲突升级",
        "name": "苏莱曼尼遇袭",
        "note": "2020年1月3日美国击毙伊朗将领苏莱曼尼，美伊冲突短暂升级。事后6个月会穿过2020年3月的疫情冲击，油价大跌不能写成这次袭击的效应。",
    },
    {
        "id": "ukraine_2022",
        "date": "2022-02-24",
        "group": "冲突升级",
        "name": "俄乌冲突全面升级",
        "note": "2022年2月24日俄罗斯对乌克兰发动全面军事行动。",
    },
    {
        "id": "embargo_2022",
        "date": "2022-12-05",
        "group": "制裁",
        "name": "欧盟对俄海运原油禁运",
        "note": "2022年12月5日欧盟对俄罗斯海运原油的进口禁令与七国集团价格上限同时生效。",
    },
    {
        "id": "gaza_2023",
        "date": "2023-10-07",
        "group": "冲突升级",
        "name": "哈马斯袭击以色列",
        "note": "2023年10月7日哈马斯袭击以色列，加沙冲突开始。",
    },
    {
        "id": "iran_israel_2024",
        "date": "2024-04-13",
        "group": "冲突升级",
        "name": "伊朗直接打击以色列",
        "note": "2024年4月13日伊朗向以色列发射无人机和导弹。",
    },
    {
        "id": "us_iran_2025",
        "date": "2025-06-22",
        "group": "冲突升级",
        "name": "美国打击伊朗核设施",
        "note": "2025年6月22日（周日）美国打击福尔多、纳坦兹和伊斯法罕。GPR日度峰值在6月23日。6月13日前后已有以色列对伊朗的连续打击，事件月同为2025-06。",
    },
    {
        "id": "hormuz_2026",
        "date": "2026-03-02",
        "group": "海峡与石油",
        "name": "霍尔木兹航运中断",
        "note": "2026年2月28日（周六）美以对伊朗开战，3月2日是其后第一个交易日，霍尔木兹航运从这一周起受阻。日期是按路透 2026-03-26 的报道回溯的手工锚点，本实验室没有逐条核对原始电讯。GPR月度均值在2026年3月达到本样本高位。",
    },
]

DEFAULT_EVENT = "hormuz_2026"
