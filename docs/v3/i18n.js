// UI strings for the v3 narrative-test page. Verdicts, summaries and report
// text come from narratives.json / the engine (zh/en fields); this dictionary
// covers chrome, labels and notes only. No judgment or count text lives here —
// every number on the scoreboard is computed from narratives.json at render
// time and interpolated into templates.

export const STR = {
  zh: {
    site_name: "EF Lab · 避险叙事检验",
    doc_title: "避险叙事检验 · EF Lab",
    brand: "EF Lab",
    brand_name: "避险叙事检验",
    err_fetch: "无法读取 {file}，请刷新页面重试。",
    loading: "加载中…",
    loading_series: "行情数据加载中…",

    // hero — {n} and {total} are computed from narratives.json at render time
    hero_headline: "在 {total} 个冻结的地缘事件中，只有 {n} 次事件后的一个月标普 500 下跌——大多数地缘事件根本不会构成真正的避险考验。",
    hero_deck: "{k} 条关于「危机时什么会涨」的流行说法，用同一套事先固定的规则逐事件检验；计数全部原始展示，逐格可复核。",
    key_intro: "每格 = 一个事件，按时间顺序：",
    key_up: "有效检验 · 上涨",
    key_down: "有效检验 · 下跌",
    key_na: "当月标普未跌，不构成考验",
    key_miss: "数据不全",
    col_claim: "说法",
    col_verdict: "判定",
    col_hits: "上涨 / 检验",
    col_median: "一个月中位数",
    col_events: "{total} 个事件",
    hit_aria: "{n_pos} / {n_valid}",
    tip_not_a_test: "标普 500 当月未跌——不构成避险考验",
    tip_missing: "数据不完整",

    // methodology strip
    ms_title: "怎么算的",
    ms_b1: "一次「有效检验」= 事件后一个月标普 500 下跌；该资产在同一窗口收益为正记一次「上涨」。传导类叙事（油价冲击）不要求标普下跌。",
    ms_b2: "至少 {min_tests} 次有效检验才下结论：上涨次数 × 3 ≥ 2 × 检验次数为「多数成立」，× 3 ≤ 检验次数为「多数不成立」，其余「好坏参半」，不足则「样本太少」。",
    ms_b3: "规则于 2026-11-25 写下并固定，先于查看结果，此后不因结果调整。",
    ms_b4: "计数全部原始展示，没有汇总分数，逐格可复核。",
    ms_link: "方法与数据全文 →",

    // per-narrative detail grid
    det_title: "逐叙事详情",
    det_note: "只画有效检验（事件后一个月收益，%）；竖虚线是中位数。",

    // custom tool
    tool_title: "自己测一测",
    tool_intro: "挑资产、选日期，同一套固定规则在浏览器里当场跑。",
    tool_assets: "资产",
    tool_dates: "日期（最多 5 个）",
    tool_bench: "基准",
    tool_run: "生成检验",
    tool_copy: "复制链接",
    tool_copied: "已复制",
    tool_err_no_assets: "请至少选择一个资产。",
    tool_err_no_dates: "请至少填写一个日期。",
    tool_err_bad_date: "第 {i} 个日期无效或超出数据范围（{min} 至 {max}）。",
    tool_err_param: "链接里的部分参数无效，已按可用部分运行。",
    tool_loading: "行情数据还在加载，稍候再试。",
    tool_note: "自定义日期是事后挑选的，结果天然偏乐观；窗口规则相同，不构成预测。",

    // briefing (the condensed former report module)
    brf_title: "最近 30 天简报",
    brf_period: "时点",
    benchmark: "基准",
    latest: "最近 30 天",
    sec_pressure: "地缘压力",
    sec_havens: "谁在避险",
    sec_evidence: "证据有多强",
    sec_caveats: "什么会推翻这个判断",
    deck_label: "结论",
    stripes_aria: "月度地缘政治风险指数色带，{first} 至 {last}，按当月均值在全部月份中的百分位着色；当前标记 {month}。",
    stripes_note: "每条竖条代表一个月：颜色是当月日度 GPR 均值在全部月份历史中的百分位，只作描述，不参与任何评级。",
    gpr_note: "GPR（地缘政治风险指数）由 Caldara 与 Iacoviello 编制，根据全球报纸中地缘风险相关词频的日度数据构造，数值越高表示新闻里的地缘风险越强。",
    haven_note: "「明显」的门槛随同时考察的资产数 k 收紧：k = 7 时要求收益落在该资产自己历史的前 2.9%（下跌则为后 2.9%）。每条刻度上的两条刻线分别是「偏强/偏弱」线（80%）和收紧后的「明显」线。",
    evidence_note: "证据等级只看这一次的价格走势在各自历史中有多罕见，不说明涨跌的原因，也不构成预测。",
    col_asset: "资产",
    col_ret: "30 天收益",
    col_label: "评级",
    col_track: "历史百分位",
    track_aria: "{asset} 三个期限的历史百分位：7 天、30 天、91 天",
    window_shade: "30 天窗口",
    gpr_line: "日度 GPR",
    incomplete_hint: "窗口未结束，数字还会变",
    evidence_explain: "等级只描述这一次的价格组合有多罕见：强 = 基准明显下跌且避险资产明显走强；中 = 基准小幅下跌，或只有部分资产明显走强；弱 = 有走强迹象但不足以排除偶然；无 = 基准没有下跌、窗口未结束或没有可评级的资产。它不说明原因。",

    // footer
    footer_methods: "方法与数据",
    footer_classic: "经典学术版",
    footer_sources: "数据来源：",
    footer_gpr: "GPR：Caldara–Iacoviello 日度指数",
    footer_built: "数据截至 {built}",
    not_advice: "不构成投资建议。",
  },
  en: {
    site_name: "EF Lab · Narrative Test",
    doc_title: "Narrative Test · EF Lab",
    brand: "EF Lab",
    brand_name: "Narrative Test",
    err_fetch: "Could not load {file}. Please reload the page.",
    loading: "Loading…",
    loading_series: "Loading market data…",

    hero_headline: "The S&P 500 fell in the month after only {n} of the {total} frozen events — most geopolitical events never become real safe-haven tests.",
    hero_deck: "{k} popular claims about what goes up in a crisis, tested event by event under one fixed rulebook. Every count is shown raw; check each square yourself.",
    key_intro: "One square per event, chronological:",
    key_up: "valid test · up",
    key_down: "valid test · down",
    key_na: "S&P 500 did not fall — not a test",
    key_miss: "incomplete data",
    col_claim: "Claim",
    col_verdict: "Verdict",
    col_hits: "Up / tests",
    col_median: "1-month median",
    col_events: "{total} events",
    hit_aria: "{n_pos} of {n_valid}",
    tip_not_a_test: "S&P 500 did not fall that month — not a safe-haven test",
    tip_missing: "Incomplete data",

    ms_title: "How it works",
    ms_b1: "A “valid test” means the S&P 500 fell in the month after the event; the asset scores an “up” if its own return over the same window is positive. Transmission narratives (oil shock) do not require the S&P to fall.",
    ms_b2: "A verdict needs at least {min_tests} valid tests: ups × 3 ≥ 2 × tests is “mostly holds”, × 3 ≤ tests is “mostly fails”, anything between is “mixed”, and below the minimum “too few tests”.",
    ms_b3: "The rules were written down and frozen on 2026-11-25, before the outputs were examined, and have not been tuned since.",
    ms_b4: "Every count is shown raw — no aggregate score — so each square can be checked by hand.",
    ms_link: "Full methods & data →",

    det_title: "Narrative by narrative",
    det_note: "Valid tests only (one-month return after the event, %); the dashed line marks the median.",

    tool_title: "Test your own",
    tool_intro: "Pick assets and dates — the same fixed rules run right here in your browser.",
    tool_assets: "Assets",
    tool_dates: "Dates (up to 5)",
    tool_bench: "Benchmark",
    tool_run: "Run the test",
    tool_copy: "Copy link",
    tool_copied: "Copied",
    tool_err_no_assets: "Pick at least one asset.",
    tool_err_no_dates: "Enter at least one date.",
    tool_err_bad_date: "Date {i} is invalid or outside the data range ({min} to {max}).",
    tool_err_param: "Some parameters in the link were invalid; ran with what was usable.",
    tool_loading: "Market data is still loading — try again in a moment.",
    tool_note: "Custom dates are picked after the fact, so results lean optimistic by construction. Same window rules; not a forecast.",

    brf_title: "The last 30 days",
    brf_period: "Moment",
    benchmark: "Benchmark",
    latest: "Last 30 days",
    sec_pressure: "Geopolitical pressure",
    sec_havens: "Which havens held up",
    sec_evidence: "How strong is the evidence",
    sec_caveats: "What would change this view",
    deck_label: "Verdict",
    stripes_aria: "Monthly geopolitical risk index strip, {first} to {last}, colored by each month's mean percentile across the full monthly history; current marker {month}.",
    stripes_note: "Each stripe is one month: the color is that month's mean daily GPR percentile across the full monthly history. It is descriptive only and feeds no rating.",
    gpr_note: "GPR (geopolitical risk index) is built by Caldara and Iacoviello from the frequency of geopolitical-risk terms in global newspapers, measured daily; higher values mean more geopolitical risk in the news.",
    haven_note: "The bar for 'clear' tightens with the number k of assets checked at once: at k = 7 a return must land in the top 2.9% of that asset's own history (bottom 2.9% for declines). The two ticks on each scale are the 'somewhat' line (80%) and the tightened 'clear' line.",
    evidence_note: "The evidence grade only says how unusual this episode's price moves were within their own histories. It says nothing about causes and is not a forecast.",
    col_asset: "Asset",
    col_ret: "30-day return",
    col_label: "Rating",
    col_track: "Historical percentile",
    track_aria: "{asset} historical percentiles at 7, 30 and 91 days",
    window_shade: "30-day window",
    gpr_line: "Daily GPR",
    incomplete_hint: "Window still open; numbers will keep changing",
    evidence_explain: "The grade only describes how unusual this episode's price pattern is: Strong = the benchmark fell sharply and havens rose clearly; Moderate = a modest benchmark drop or only some havens clearly stronger; Weak = some sign of haven demand but within the range of chance; None = the benchmark did not fall, the window is still open, or nothing could be rated. It does not explain causes.",

    footer_methods: "Methods & data",
    footer_classic: "Classic academic page",
    footer_sources: "Sources: ",
    footer_gpr: "GPR: Caldara–Iacoviello daily index",
    footer_built: "Data through {built}",
    not_advice: "Not investment advice.",
  },
};

// Short display names for tight spaces and for the window before series
// meta has loaded (the full bilingual names live in series.json).
export const ASSET_SHORT = {
  zh: { gold: "黄金", silver: "白银", jpy: "日元", chf: "瑞郎", ust: "美债", btc: "比特币", dxy: "美元", brent: "布伦特原油", spx: "标普500", csi: "沪深300", hsi: "恒生指数" },
  en: { gold: "Gold", silver: "Silver", jpy: "Yen", chf: "Franc", ust: "UST", btc: "BTC", dxy: "USD", brent: "Brent crude", spx: "S&P 500", csi: "CSI 300", hsi: "Hang Seng" },
};

// Compact event tags for the small-multiple charts, keyed by event id.
// zh names are already concise, so the zh column reuses the full names from
// reports.json; only English needs abbreviations.
export const EV_SHORT_EN = {
  libya_2011: "Libya ’11",
  crimea_2014: "Crimea ’14",
  brexit_2016: "Brexit ’16",
  nk_2017: "N. Korea nuke ’17",
  jcpoa_2018: "Iran deal exit ’18",
  hormuz_2019: "Hormuz tankers ’19",
  abqaiq_2019: "Abqaiq ’19",
  soleimani_2020: "Soleimani ’20",
  ukraine_2022: "Ukraine invasion ’22",
  taiwan_2022: "Pelosi Taiwan ’22",
  embargo_2022: "EU oil embargo ’22",
  gaza_2023: "Gaza ’23",
  iran_israel_2024: "Iran–Israel ’24",
  us_iran_2025: "US–Iran strikes ’25",
  hormuz_2026: "Hormuz disruption ’26",
};

export function t(lang, key, vars) {
  let s = (STR[lang] && STR[lang][key]) || STR.en[key] || key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split("{" + k + "}").join(String(v));
  return s;
}
