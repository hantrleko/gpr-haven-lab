let LAB = null;
const COLORS = {gold:"#C47B12", brent:"#D55E00", dxy:"#0072B2", csi:"#1F4E79", hsi:"#5B7C99", dgpr:"#1C1915"};
const SOURCES = {
  libya_2011: {url: "https://www.reuters.com/article/us-libya-idUSTRE71G0A620110222/", label: "Reuters, 2011-02-22"},
  crimea_2014: {url: "https://www.reuters.com/article/us-ukraine-crisis-idUSBREA1H0EM20140318/", label: "Reuters, 2014-03-18"},
  jcpoa_2018: {url: "https://www.reuters.com/article/us-iran-nuclear-trump-idUSKBN1I90Z1/", label: "Reuters, 2018-05-08"},
  hormuz_2019: {url: "https://www.reuters.com/article/us-mideast-attacks-idUSKCN1TE0X2/", label: "Reuters, 2019-06-13"},
  abqaiq_2019: {url: "https://www.reuters.com/article/us-saudi-aramco-fire-idUSKCN1VZ0H9/", label: "Reuters, 2019-09-14"},
  soleimani_2020: {url: "https://www.reuters.com/article/us-iraq-security-blast-idUSKBN1Z20GK/", label: "Reuters, 2020-01-03"},
  ukraine_2022: {url: "https://www.reuters.com/world/europe/russia-invades-ukraine-2022-02-24/", label: "Reuters, 2022-02-24"},
  embargo_2022: {url: "https://www.reuters.com/business/energy/eu-ban-russian-oil-2022-12-05/", label: "Reuters, 2022-12-05"},
  gaza_2023: {url: "https://www.reuters.com/world/middle-east/hamas-attack-israel-2023-10-07/", label: "Reuters, 2023-10-07"},
  iran_israel_2024: {url: "https://www.reuters.com/world/middle-east/iran-launches-drone-attack-israel-2024-04-13/", label: "Reuters, 2024-04-13"},
  us_iran_2025: {url: "https://carnegieendowment.org/middle-east/diwan/2025/06/the-united-states-has-attacked-irans-nuclear-facilities", label: "Carnegie, 2025-06-22"},
  hormuz_2026: {url: "https://www.reuters.com/business/energy/barclays-sees-1314-million-bpd-oil-supply-loss-prolonged-hormuz-disruption-2026-03-26/", label: "Reuters, 2026-03-26"},
  brexit_2016: {url: "https://www.bbc.co.uk/news/politics/eu_referendum/results", label: "BBC, 2016-06-24"},
  nk_2017: {url: "https://www.bbc.com/news/world-asia-41139445", label: "BBC, 2017-09-03"},
  taiwan_2022: {url: "https://www.reuters.com/world/asia-pacific/pelosi-expected-arrive-taiwan-tuesday-sources-say-2022-08-02/", label: "Reuters, 2022-08-02"},
};
const SCENES = [
  {id:"hormuz_2026", label:"2026 霍尔木兹", labelEn:"2026 Hormuz"},
  {id:"ukraine_2022", label:"2022 俄乌", labelEn:"2022 Ukraine"},
  {id:"gaza_2023", label:"2023 哈马斯", labelEn:"2023 Hamas"},
  {id:"brexit_2016", label:"2016 英国脱欧", labelEn:"2016 Brexit"},
  {id:"taiwan_2022", label:"2022 台海", labelEn:"2022 Taiwan Strait"},
  {id:"nk_2017", label:"2017 朝鲜核试验", labelEn:"2017 North Korea"},
];
const EVENT_EN = {
  libya_2011: "Libya escalation",
  crimea_2014: "Crimea annexation and sanctions",
  jcpoa_2018: "US exit from the Iran nuclear deal",
  hormuz_2019: "Hormuz tanker attacks",
  abqaiq_2019: "Abqaiq facility attack",
  soleimani_2020: "Soleimani strike",
  ukraine_2022: "Full-scale invasion of Ukraine",
  embargo_2022: "EU seaborne oil embargo on Russia",
  gaza_2023: "Hamas attack on Israel",
  iran_israel_2024: "Iran strikes Israel",
  us_iran_2025: "US strikes on Iranian nuclear sites",
  hormuz_2026: "Hormuz shipping disruption",
};
const NAMES_ZH = {gold:"黄金", brent:"布伦特", dxy:"美元指数", csi:"沪深300", hsi:"恒生", dgpr:"GPR变动"};
const NAMES_EN = {gold:"Gold", brent:"Brent", dxy:"Dollar index", csi:"CSI 300", hsi:"Hang Seng", dgpr:"GPR change"};
const NAMES = Object.assign({}, NAMES_ZH);
const PRICE_IDS = ["gold","brent","dxy","csi","hsi"];
const SCORE_IDS = ["brent","dxy","csi","hsi","dgpr"];
const VAR_IDS = ["dgpr","brent","dxy","gold","csi","hsi"];
const STORE_KEY = "gpr-haven-custom-v1";
const state = {eventId:"hormuz_2026", sessions:40, width:12, spec:null, sort:"time", overlay:[], base:"event", lang:"zh", irf:"var"};

function defaultSpec() {
  return {
    events: [],
    anchor: "gold",
    path: PRICE_IDS.slice(),
    score: [
      {id:"brent", role:"watch"},
      {id:"dxy", role:"hedge"},
      {id:"csi", role:"hedge"},
      {id:"hsi", role:"hedge"},
      {id:"dgpr", role:"comove"},
    ],
    varOn: VAR_IDS.slice(),
  };
}
function sanitizeSpec(raw) {
  const base = defaultSpec();
  if (!raw || typeof raw !== "object") return base;
  if (PRICE_IDS.includes(raw.anchor)) base.anchor = raw.anchor;
  if (Array.isArray(raw.path)) base.path = PRICE_IDS.filter(id => raw.path.includes(id));
  if (!base.path.includes(base.anchor)) base.path.unshift(base.anchor);
  if (Array.isArray(raw.score)) {
    base.score = SCORE_IDS.map(id => {
      const found = raw.score.find(item => item && item.id === id);
      const role = found && ["off","watch","hedge","comove"].includes(found.role) ? found.role : "off";
      return {id, role: id === base.anchor ? "off" : role};
    });
  }
  if (Array.isArray(raw.varOn)) {
    const kept = raw.varOn.filter(id => VAR_IDS.includes(id));
    base.varOn = kept.length >= 2 ? kept : VAR_IDS.slice();
  }
  if (Array.isArray(raw.events)) {
    base.events = raw.events.filter(item => item && item.id && item.date && item.name && /^\d{4}-\d{2}-\d{2}$/.test(item.date)).map(item => ({
      id: String(item.id),
      name: String(item.name).slice(0, 40),
      date: item.date,
      month: item.date.slice(0, 7),
      group: "自定事件",
      note: String(item.note || "页面上自定的事件。").slice(0, 160),
    }));
  }
  return base;
}
function loadSpec() {
  try { return sanitizeSpec(JSON.parse(localStorage.getItem(STORE_KEY))); }
  catch (err) { return defaultSpec(); }
}
function saveSpec() {
  const spec = state.spec;
  localStorage.setItem(STORE_KEY, JSON.stringify({
    events: spec.events, anchor: spec.anchor, path: spec.path, score: spec.score, varOn: spec.varOn,
  }));
}
function allEvents() { return LAB.events.concat(state.spec.events); }
function shownPairs() { return state.spec.score.filter(item => item.role !== "off" && item.id !== state.spec.anchor); }
function isPresetScore() {
  if (state.spec.anchor !== "gold") return false;
  const want = {brent:"watch", dxy:"hedge", csi:"hedge", hsi:"hedge", dgpr:"comove"};
  return state.spec.score.length === 5 && state.spec.score.every(item => want[item.id] === item.role);
}
function isPresetVar() {
  return state.spec.varOn.join(",") === VAR_IDS.join(",");
}
function seriesOf(block, id) { return id === "dgpr" ? block.dgpr : block[id]; }

function corr(xs, ys, minN=4) {
  const buf = [];
  for (let i = 0; i < xs.length; i++) {
    const x = xs[i], y = ys[i];
    if (x == null || y == null || !isFinite(x) || !isFinite(y)) continue;
    buf.push([x, y]);
  }
  const n = buf.length;
  if (n < minN) return null;
  let mx = 0, my = 0;
  for (const [x, y] of buf) { mx += x; my += y; }
  mx /= n; my /= n;
  let num = 0, dx = 0, dy = 0;
  for (const [x, y] of buf) {
    const a = x - mx, b = y - my;
    num += a * b; dx += a * a; dy += b * b;
  }
  if (dx <= 1e-12 || dy <= 1e-12) return null;
  return num / Math.sqrt(dx * dy);
}
function havenOfLegacy(block) {
  const cCsi = corr(block.gold, block.csi);
  const cHsi = corr(block.gold, block.hsi);
  const cGpr = corr(block.gold, block.dgpr);
  const cDxy = corr(block.gold, block.dxy);
  const cBrent = corr(block.gold, block.brent);
  if ([cCsi, cHsi, cGpr, cDxy].some(v => v == null)) return null;
  const equity = 50 * (1 - (cCsi + cHsi) / 2);
  const gpr = 50 * (1 + cGpr);
  const dollar = 50 * (1 - cDxy);
  return {score:(equity+gpr+dollar)/3, equity, gpr, dollar, cCsi, cHsi, cGpr, cDxy, cBrent, parts:null};
}
function havenOf(block, minN=4) {
  if (isPresetScore() && minN === 4) return havenOfLegacy(block);
  const anchor = seriesOf(block, state.spec.anchor);
  const legs = shownPairs().filter(item => item.role === "hedge" || item.role === "comove");
  if (!legs.length) return null;
  const corrs = {};
  const parts = [];
  for (const leg of legs) {
    const value = corr(anchor, seriesOf(block, leg.id), minN);
    if (value == null) return null;
    corrs[leg.id] = value;
    parts.push({id:leg.id, role:leg.role, corr:value, value: leg.role === "hedge" ? 50 * (1 - value) : 50 * (1 + value)});
  }
  shownPairs().forEach(item => {
    if (corrs[item.id] == null) {
      const value = corr(anchor, seriesOf(block, item.id), minN);
      if (value != null) corrs[item.id] = value;
    }
  });
  return {
    score: parts.reduce((sum, item) => sum + item.value, 0) / parts.length,
    parts,
    cCsi: corrs.csi ?? null,
    cHsi: corrs.hsi ?? null,
    cGpr: corrs.dgpr ?? null,
    cDxy: corrs.dxy ?? null,
    cBrent: corrs.brent ?? null,
  };
}
function sliceBlock(a, b) {
  return {
    gold: LAB.ret.gold.slice(a, b),
    brent: LAB.ret.brent.slice(a, b),
    dxy: LAB.ret.dxy.slice(a, b),
    csi: LAB.ret.csi.slice(a, b),
    hsi: LAB.ret.hsi.slice(a, b),
    dgpr: LAB.dgpr.slice(a, b),
    gpr: LAB.gpr.slice(a, b),
  };
}
function finiteSum(arr) {
  let s = 0, n = 0;
  for (const v of arr) {
    if (v == null || !isFinite(v)) continue;
    s += v; n++;
  }
  return {sum: n ? s : null, n};
}
function mean(arr) {
  const {sum, n} = finiteSum(arr);
  return n ? sum / n : null;
}
function analyze(month, width) {
  const idx = LAB.months.indexOf(month);
  if (idx < 0) return null;
  const n = LAB.months.length;
  const b0 = Math.max(0, idx - width);
  const a1 = Math.min(n, idx + width);
  const before = sliceBlock(b0, idx);
  const after = sliceBlock(idx, a1);
  const anchorId = state.spec.anchor;
  const anchorCount = finiteSum(after[anchorId]).n;
  const partial = b0 !== idx - width || a1 !== idx + width || anchorCount < width;
  return {
    partial, nBefore: idx - b0, nAfter: anchorCount, width,
    cum: {
      gold: finiteSum(after.gold).sum,
      brent: finiteSum(after.brent).sum,
      dxy: finiteSum(after.dxy).sum,
      csi: finiteSum(after.csi).sum,
      hsi: finiteSum(after.hsi).sum,
    },
    before: havenOf(before),
    after: havenOf(after),
    gprBefore: mean(before.gpr),
    gprAfter: mean(after.gpr),
  };
}
function dailyPack(name) {
  return LAB.daily && LAB.daily[name] ? LAB.daily[name] : null;
}
function indexedPath(pack, eventDate, sessions, baseMode) {
  if (!pack || !pack.dates || !pack.close) return null;
  const {dates, close} = pack;
  let i0 = 0;
  while (i0 < dates.length && dates[i0] < eventDate) i0++;
  if (i0 <= 0) return null;
  const mode = baseMode || state.base || "event";
  const base = mode === "pre" || close[i0] == null ? close[i0 - 1] : close[i0];
  if (!base) return null;
  const tau = [], value = [], date = [];
  for (let i = Math.max(0, i0 - sessions); i < i0; i++) {
    tau.push(i - i0); value.push(100 * close[i] / base); date.push(dates[i]);
  }
  for (let i = i0; i < Math.min(dates.length, i0 + sessions); i++) {
    tau.push(i - i0); value.push(100 * close[i] / base); date.push(dates[i]);
  }
  return {tau, value, date};
}
function fmt(v, d=1) {
  if (v == null || !isFinite(v)) return "—";
  const text = v.toFixed(d);
  return v > 0 ? "+" + text : text;
}
function activeEvent() {
  return allEvents().find(item => item.id === state.eventId) || LAB.events[0];
}
function eventTitle(event) {
  if (state.lang === "en") return event.name_en || EVENT_EN[event.id] || event.name;
  return event.name;
}
function eventNote(event) {
  if (state.lang === "en" && event.note_en) return event.note_en;
  return event.note;
}
function monthHasAfter(month) {
  const idx = LAB.months.indexOf(month);
  return idx >= 0 && idx < LAB.months.length - 1;
}
function sessionAfter(date) {
  const gold = dailyPack("gold");
  if (!gold) return true;
  return gold.dates.some(item => item > date);
}
function labVersion() {
  return (LAB && LAB.meta && LAB.meta.version) ? LAB.meta.version : "V2.0";
}
function placeboPack() {
  const raw = LAB.placebo && LAB.placebo[String(state.width)];
  if (!raw) return null;
  if (raw.blocked && raw.blocked.gold && raw.blocked.gold.length) return raw.blocked;
  return raw;
}
function goldPct(value, key) {
  const pack = placeboPack();
  const series = (pack && pack[key || "gold"]) || (pack && pack.gold);
  if (!series || !series.length || value == null || !isFinite(value)) return null;
  let n = 0;
  for (const item of series) if (item <= value + 1e-9) n++;
  return n / series.length;
}
function sentence(event, stats) {
  const title = eventTitle(event);
  if (!stats) {
    return state.lang === "en"
      ? {tone:"warn", text: title + " is outside the complete monthly sample. The sample ends in " + LAB.meta.sample_end + "."}
      : {tone:"warn", text:"这个月不在完整月度样本里。样本止于 " + LAB.meta.sample_end + "。"};
  }
  const anchor = state.spec.anchor;
  const names = state.spec.path.map(id => NAMES[id] + " " + fmt(stats.cum[id]) + "%").join(state.lang === "en" ? "; " : "，");
  const pair = shownPairs().find(item => item.id === "csi") || shownPairs()[0];
  const corrBit = pair && stats.after && stats.before && stats.before["c" + pairKey(pair.id)] != null && stats.after["c" + pairKey(pair.id)] != null
    ? (state.lang === "en"
      ? "The correlation of " + NAMES[anchor] + " with " + NAMES[pair.id] + " moves from " + stats.before["c" + pairKey(pair.id)].toFixed(2) + " to " + stats.after["c" + pairKey(pair.id)].toFixed(2) + ". "
      : NAMES[anchor] + "与" + NAMES[pair.id] + "的相关由 " + stats.before["c" + pairKey(pair.id)].toFixed(2) + " 变为 " + stats.after["c" + pairKey(pair.id)].toFixed(2) + "。")
    : (stats.after ? "" : (state.lang === "en" ? "This window has too few months for a correlation. " : "这个窗口的月份太少，相关没有计算。"));
  const g = stats.cum[anchor];
  const c = stats.cum.csi;
  const b = stats.cum.brent;
  let tone = "";
  let claim = state.lang === "en" ? "These price paths do not point in one direction. " : "这组价格路径没有呈现单一方向。";
  if (anchor === "gold" && g > 0 && c < 0 && state.spec.path.includes("csi")) claim = state.lang === "en" ? "Gold rises while CSI 300 falls, which matches a safe-haven split in prices. " : "黄金上涨而沪深300下跌，价格路径与避险分流一致。";
  else if (anchor === "gold" && b > 0 && g < 0 && state.spec.path.includes("brent")) { tone = "warn"; claim = state.lang === "en" ? "Brent rises while gold falls, so gold does not show the usual safe-haven rise in this window. " : "布伦特上涨而黄金下跌，这段窗口里黄金没有表现出典型的避险上涨。"; }
  else if (anchor === "gold" && g < 0 && c < 0 && state.spec.path.includes("csi")) { tone = "bad"; claim = state.lang === "en" ? "Gold and CSI 300 fall together, which looks more like tighter liquidity and real rates than gold alone taking the haven bid. " : "黄金与沪深300同时下跌，更像流动性和实际利率一起抽紧，而不是黄金单独承接避险买盘。"; }
  else if (anchor === "gold" && g > 0 && c > 0 && state.spec.path.includes("csi")) claim = state.lang === "en" ? "Gold and CSI 300 rise together, so the haven asset and the risk asset do not split. " : "黄金与沪深300同时上涨，避险资产和风险资产没有反向分开。";
  else claim = state.lang === "en" ? "The numbers above are cumulative log returns for the anchor and the selected series. " : "上面是锚资产和已选序列在这个窗口里的累计对数收益。";
  const pct = anchor === "gold" && stats.cum.gold != null ? goldPct(stats.cum.gold) : null;
  const pctBit = pct == null ? "" : (state.lang === "en"
    ? "Gold's after-window return sits near the " + Math.round(100 * pct) + "th percentile of blocked non-overlapping placebo months (not causal). "
    : "黄金事后累计收益约处于非重叠安慰剂月份分布的第 " + Math.round(100 * pct) + " 分位（非因果对照）。");
  const cut = stats.partial ? (state.lang === "en" ? "The after window is incomplete and uses only the months on hand. " : "事后窗口不完整，累计收益只覆盖可得月份。") : "";
  const windowBit = state.lang === "en"
    ? "Sample " + LAB.meta.sample_start + " to " + LAB.meta.sample_end + ", prices ±" + state.sessions + " sessions, correlation window " + state.width + " months. "
    : "样本 " + LAB.meta.sample_start + " 至 " + LAB.meta.sample_end + "，价格 ±" + state.sessions + " 个交易日，相关窗口 " + state.width + " 个月。";
  const caveat = state.lang === "en"
    ? "This describes the window. It is not causal identification. Event dates are hand anchors and have not been checked cable by cable."
    : " 这是窗口内的描述，不是因果识别。";
  const head = state.lang === "en"
    ? title + " (" + event.date + "), " + stats.nAfter + " months after: " + names + ". "
    : title + "（" + event.date + "）之后 " + stats.nAfter + " 个月：" + names + "。";
  return {tone, text: head + corrBit + claim + pctBit + cut + windowBit + caveat};
}
function pairKey(id) {
  return {brent:"Brent", dxy:"Dxy", csi:"Csi", hsi:"Hsi", dgpr:"Gpr"}[id];
}

function svgNode(name, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}
function drawChart(host, spec) {
  host.innerHTML = "";
  const width = spec.width || 860, height = spec.height || 300;
  const m = spec.margin || {l:54, r:12, t:12, b:36};
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`, role:"img"});
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", spec.long || spec.title || "图");
  if (spec.descId) svg.setAttribute("aria-describedby", spec.descId);
  const iw = width - m.l - m.r, ih = height - m.t - m.b;
  const pts = [];
  spec.series.forEach(series => {
    series.x.forEach((x, i) => {
      const y = series.y[i];
      if (x == null || y == null || !isFinite(x) || !isFinite(y)) return;
      pts.push({x, y});
    });
  });
  if (!pts.length) { host.appendChild(svg); return; }
  let x0 = Math.min(...pts.map(p => p.x)), x1 = Math.max(...pts.map(p => p.x));
  let y0 = Math.min(...pts.map(p => p.y)), y1 = Math.max(...pts.map(p => p.y));
  if (spec.includeZero) { y0 = Math.min(y0, 0); y1 = Math.max(y1, 0); }
  if (spec.ref != null) { y0 = Math.min(y0, spec.ref); y1 = Math.max(y1, spec.ref); }
  const pad = (y1 - y0) * 0.08 || 1;
  y0 -= pad; y1 += pad;
  if (x0 === x1) { x0 -= 1; x1 += 1; }
  const X = x => m.l + (x - x0) / (x1 - x0) * iw;
  const Y = y => m.t + (y1 - y) / (y1 - y0) * ih;
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const y = y0 + (y1 - y0) * i / ticks;
    svg.appendChild(svgNode("line", {x1:m.l, x2:width-m.r, y1:Y(y), y2:Y(y), stroke:"#eceae4"}));
    const label = svgNode("text", {x:m.l-6, y:Y(y)+4, "text-anchor":"end", fill:"#3a342c", "font-size":13});
    label.textContent = spec.yFormat ? spec.yFormat(y) : y.toFixed(spec.yDigits == null ? 0 : spec.yDigits);
    svg.appendChild(label);
  }
  if (spec.ref != null) svg.appendChild(svgNode("line", {x1:m.l, x2:width-m.r, y1:Y(spec.ref), y2:Y(spec.ref), stroke:"#c8c2b6", "stroke-dasharray":"3 3"}));
  if (spec.mark != null && spec.mark >= x0 && spec.mark <= x1) {
    svg.appendChild(svgNode("line", {x1:X(spec.mark), x2:X(spec.mark), y1:m.t, y2:height-m.b, stroke:"#8a8478", "stroke-dasharray":"3 3"}));
    if (spec.markLabel) {
      const markText = svgNode("text", {x:X(spec.mark) + 6, y:m.t + 14, fill:"#3a342c", "font-size":13});
      markText.textContent = spec.markLabel;
      svg.appendChild(markText);
    }
  }
  spec.series.forEach(series => {
    let d = "";
    series.x.forEach((x, i) => {
      const y = series.y[i];
      if (x == null || y == null || !isFinite(x) || !isFinite(y)) { d += " M "; return; }
      d += (d.endsWith("M ") || d === "" ? "M " : "L ") + X(x).toFixed(2) + " " + Y(y).toFixed(2) + " ";
    });
    svg.appendChild(svgNode("path", {d, fill:"none", stroke:series.color, "stroke-width":series.width || 1.6}));
    if (series.bandLo) {
      let band = "";
      const upper = [], lower = [];
      series.x.forEach((x, i) => {
        if ([series.bandLo[i], series.bandHi[i]].every(v => v != null && isFinite(v))) {
          upper.push([X(x), Y(series.bandHi[i])]);
          lower.push([X(x), Y(series.bandLo[i])]);
        }
      });
      band = upper.map((p,i) => (i ? "L":"M") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join(" ");
      for (let i = lower.length - 1; i >= 0; i--) band += " L " + lower[i][0].toFixed(2) + " " + lower[i][1].toFixed(2);
      band += " Z";
      const shade = svgNode("path", {d:band, fill:series.color, opacity:"0.18", stroke:"none"});
      svg.insertBefore(shade, svg.querySelector("path"));
    }
  });
  const xTicks = spec.xTicks || [x0, (x0+x1)/2, x1];
  xTicks.forEach(x => {
    if (x < x0 || x > x1) return;
    const label = svgNode("text", {x:X(x), y:height-14, "text-anchor":"middle", fill:"#3a342c", "font-size":13});
    label.textContent = spec.xFormat ? spec.xFormat(x) : String(Math.round(x));
    svg.appendChild(label);
  });
  host.appendChild(svg);
  const hit = [];
  spec.series.forEach(series => {
    series.x.forEach((x, i) => {
      const y = series.y[i];
      if (x == null || y == null || !isFinite(y)) return;
      hit.push({sx:X(x), label: series.name + "  " + (spec.xFormat ? spec.xFormat(x) : x) + "  " + (spec.yFormat ? spec.yFormat(y) : y.toFixed(2))});
    });
  });
  svg.addEventListener("mousemove", event => {
    const rect = svg.getBoundingClientRect();
    const sx = (event.clientX - rect.left) * width / rect.width;
    let best = null, dist = 1e9;
    hit.forEach(point => { const d = Math.abs(point.sx - sx); if (d < dist) { dist = d; best = point; } });
    const tip = document.getElementById("tip");
    if (!best || dist > 24) { tip.style.display = "none"; return; }
    tip.style.display = "block";
    tip.style.left = (event.clientX + 12) + "px";
    tip.style.top = (event.clientY + 12) + "px";
    tip.textContent = best.label;
  });
  svg.addEventListener("mouseleave", () => { document.getElementById("tip").style.display = "none"; });
}

function drawHeat(event, heat) {
  const host = document.getElementById("heat");
  host.innerHTML = "";
  const cell = 16, labelW = 118, head = 28;
  const width = labelW + heat.labels.length * cell + 8;
  const height = head + heat.pairs.length * cell + 8;
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`, width: width, height: height});
  const quarter = event.month ? event.month.slice(0,4) + "Q" + (Math.floor((Number(event.month.slice(5,7)) - 1) / 3) + 1) : "";
  heat.labels.forEach((label, i) => {
    if (!label.endsWith("Q1")) return;
    const text = svgNode("text", {x: labelW + i * cell, y: 16, fill:"#3a342c", "font-size":13});
    text.textContent = label.slice(0,4);
    svg.appendChild(text);
  });
  heat.pairs.forEach((pair, r) => {
    const text = svgNode("text", {x:0, y: head + r * cell + 12, fill:"#1c1915", "font-size":13});
    text.textContent = pair.name;
    svg.appendChild(text);
    pair.values.forEach((value, c) => {
      const rect = svgNode("rect", {
        x: labelW + c * cell, y: head + r * cell, width: cell - 1, height: cell - 1,
        fill: value == null ? "#f3f0e8" : (value < 0 ? "#0072b2" : "#d55e00"),
        opacity: value == null ? 1 : Math.max(0.08, Math.abs(value)),
      });
      const title = svgNode("title", {});
      title.textContent = pair.name + " " + heat.labels[c] + " " + (value == null ? "无" : value.toFixed(2));
      rect.appendChild(title);
      svg.appendChild(rect);
      if (heat.labels[c] === quarter) {
        svg.appendChild(svgNode("rect", {
          x: labelW + c * cell, y: head + r * cell, width: cell - 1, height: cell - 1,
          fill:"none", stroke:"#1c1915", "stroke-width":1.2,
        }));
      }
    });
  });
  host.appendChild(svg);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", state.lang === "en" ? "Rolling correlation heatmap" : "滚动相关热力图");
  svg.setAttribute("aria-describedby", "heat-cap");
  const quarterIndex = heat.labels.indexOf(quarter);
  fillSimpleTable("heat-table",
    (state.lang === "en" ? "Correlations in " : "事件所在季度 ") + (quarter || "—") + (state.lang === "en" ? ". The chart contains every quarter." : "。图里含全部季度。"),
    state.lang === "en" ? ["Pair", "Correlation"] : ["序列", "相关系数"],
    heat.pairs.map(pair => [pair.name, quarterIndex < 0 || pair.values[quarterIndex] == null ? "—" : Number(pair.values[quarterIndex]).toFixed(2)]));
}

function liveHeat() {
  const ids = shownPairs().map(item => item.id);
  const presetIds = ["brent","dxy","csi","hsi","dgpr"];
  if (state.spec.anchor === "gold" && ids.length === presetIds.length && presetIds.every(id => ids.includes(id))) return LAB.heatmap;
  const anchor = state.spec.anchor;
  const labels = [];
  const pairs = ids.map(id => ({id, name: NAMES[anchor] + "–" + NAMES[id], values: []}));
  LAB.months.forEach((month, i) => {
    const m = Number(month.slice(5, 7));
    if (![3, 6, 9, 12].includes(m) || i < 35) return;
    const sample = sliceBlock(i - 35, i + 1);
    labels.push(month.slice(0, 4) + "Q" + (m / 3));
    pairs.forEach(pair => {
      const value = corr(seriesOf(sample, anchor), seriesOf(sample, pair.id), 24);
      pair.values.push(value == null ? null : Math.round(value * 1000) / 1000);
    });
  });
  return {labels, pairs};
}
function rollingHaven() {
  if (isPresetScore()) return LAB.haven.score;
  return LAB.months.map((month, i) => {
    if (i < 35) return null;
    const stats = havenOf(sliceBlock(i - 35, i + 1), 24);
    return stats ? Math.round(stats.score * 100) / 100 : null;
  });
}
function altHaven(event) {
  const idx = LAB.months.indexOf(event.month);
  if (idx < 0) return null;
  const a1 = Math.min(LAB.months.length, idx + state.width);
  const gold = LAB.ret.gold.slice(idx, a1);
  const cCsi = corr(gold, LAB.ret.csi.slice(idx, a1));
  const cHsi = corr(gold, LAB.ret.hsi.slice(idx, a1));
  const cGpr = corr(gold, LAB.dgpr.slice(idx, a1));
  const cDxy = corr(gold, LAB.ret.dxy.slice(idx, a1));
  if ([cCsi, cHsi, cGpr, cDxy].some(v => v == null)) return null;
  const E = 50 * (1 - (cCsi + cHsi) / 2);
  const G = 50 * (1 + cGpr);
  const D = 50 * (1 - cDxy);
  const en = state.lang === "en";
  const rows = [
    [en ? "Paper: three components, equal weight" : "论文三项等权", (E + G + D) / 3],
    [en ? "Four correlations, equal weight" : "四对相关等权", (50 * (1 - cCsi) + 50 * (1 - cHsi) + G + D) / 4],
    [en ? "Equity weight 50%" : "权益权重 50%", 0.5 * E + 0.25 * G + 0.25 * D],
  ];
  if (LAB.dgpr_act) {
    const cAct = corr(gold, LAB.dgpr_act.slice(idx, a1));
    if (cAct != null) rows.push([en ? "GPR leg replaced by the act sub-index" : "GPR 换成行动子指数", (E + 50 * (1 + cAct) + D) / 3]);
  }
  if (LAB.dgpr_threat) {
    const cThreat = corr(gold, LAB.dgpr_threat.slice(idx, a1));
    if (cThreat != null) rows.push([en ? "GPR leg replaced by the threat sub-index" : "GPR 换成威胁子指数", (E + 50 * (1 + cThreat) + D) / 3]);
  }
  return rows;
}
function fillRobust(event) {
  const host = document.getElementById("robust");
  if (!host) return;
  const rows = altHaven(event);
  if (!rows) { host.innerHTML = ""; return; }
  host.innerHTML = "<table class='data-table'><caption>" + (state.lang === "en" ? "Same window, different weights. Not a published index. VAR order checks sit in the custom panel; only the paper order has a 90% band." : "同一窗口的加权稳健性。这不是文献标准指数。VAR 排序对照在自定面板里，只有论文顺序有 90% 区间。") + "</caption><thead><tr><th>" + (state.lang === "en" ? "Rule" : "算法") + "</th><th>" + (state.lang === "en" ? "Score" : "强度") + "</th></tr></thead><tbody>"
    + rows.map(row => "<tr><td>" + row[0] + "</td><td>" + row[1].toFixed(0) + "</td></tr>").join("")
    + "</tbody></table>";
}
function havenMedian() {
  const values = rollingHaven().filter(value => value != null && isFinite(value)).slice().sort((a, b) => a - b);
  if (!values.length) return 50;
  const mid = Math.floor(values.length / 2);
  return values.length % 2 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
}
function havenPercentile(score) {
  const values = rollingHaven().filter(value => value != null && isFinite(value));
  if (!values.length || score == null) return "—";
  return Math.round(100 * values.filter(value => value <= score).length / values.length);
}
function compareRows() {
  const anchor = state.spec.anchor;
  const other = ["csi", "brent", "hsi", "dxy"].find(id => id !== anchor && state.spec.path.includes(id)) || state.spec.path.find(id => id !== anchor);
  const rows = allEvents().map(event => {
    const stats = analyze(event.month, state.width);
    const excess = stats && other && stats.cum[anchor] != null && stats.cum[other] != null ? stats.cum[anchor] - stats.cum[other] : null;
    return {event, excess, haven: stats && stats.after ? stats.after.score : null, stats};
  });
  if (state.sort === "excess") rows.sort((a, b) => (b.excess ?? -1e9) - (a.excess ?? -1e9));
  if (state.sort === "haven") rows.sort((a, b) => (b.haven ?? -1e9) - (a.haven ?? -1e9));
  return {rows, other, anchor};
}
function drawCompare() {
  const host = document.getElementById("compare");
  if (!host) return;
  const packed = compareRows();
  const events = packed.rows.map(row => row.event);
  const values = packed.rows.map(row => row.excess);
  const other = packed.other;
  const anchor = packed.anchor;
  host.innerHTML = "";
  const width = 860;
  const rowH = 26;
  const height = 28 + events.length * rowH;
  const svg = svgNode("svg", {viewBox: "0 0 " + width + " " + height});
  const m = {l: 188, r: 56, t: 8, b: 16};
  const finite = values.filter(value => value != null);
  const max = Math.max(8, ...finite.map(value => Math.abs(value)));
  const zero = m.l + (width - m.l - m.r) / 2;
  const scale = (width - m.l - m.r) / 2 / max;
  svg.appendChild(svgNode("line", {x1: zero, x2: zero, y1: m.t, y2: height - m.b, stroke: "#1c1915"}));
  events.forEach((event, index) => {
    const y = m.t + index * rowH + 12;
    const label = svgNode("text", {x: m.l - 8, y: y + 4, "text-anchor": "end", fill: event.id === state.eventId ? "#1f4b73" : "#1c1915", "font-size": 13});
    label.textContent = eventTitle(event);
    svg.appendChild(label);
    const value = values[index];
    if (value == null) return;
    const x = zero + value * scale;
    svg.appendChild(svgNode("line", {
      x1: zero, x2: x, y1: y, y2: y,
      stroke: event.id === state.eventId ? "#1F4E79" : (value >= 0 ? "#C47B12" : "#5B7C99"),
      "stroke-width": event.id === state.eventId ? 8 : 5,
    }));
    const num = svgNode("text", {x: x + (value >= 0 ? 6 : -6), y: y + 4, "text-anchor": value >= 0 ? "start" : "end", fill: "#3a342c", "font-size": 13});
    num.textContent = (value > 0 ? "+" : "") + value.toFixed(1);
    svg.appendChild(num);
  });
  host.appendChild(svg);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", state.lang === "en" ? "Event comparison bars" : "事件对比柱状图");
  svg.setAttribute("aria-describedby", "compare-cap");
  const cap = document.getElementById("compare-cap");
  if (cap && other) cap.textContent = state.lang === "en"
    ? "Each bar is the " + state.width + "-month cumulative log return of " + NAMES[anchor] + " minus " + NAMES[other] + ". Warm is positive, cool is negative, and the selected event is darker. Sort by time, gap, or haven score. On a narrow screen, scroll sideways."
    : "柱长是事后 " + state.width + " 个月，" + NAMES[anchor] + "累计对数收益减去" + NAMES[other] + "。暖色为正，冷色为负，深色是当前事件。可按时间、差额或避险强度排序。窄屏可以左右滑动。";
  fillSimpleTable("compare-table", state.lang === "en" ? "Numbers behind the comparison bars" : "对比柱对应的数字",
    state.lang === "en" ? ["Event", "Gap", "Haven score"] : ["事件", "差额", "避险强度"],
    packed.rows.map(row => [eventTitle(row.event), row.excess == null ? "—" : row.excess.toFixed(1), row.haven == null ? "—" : row.haven.toFixed(0)]));
}
const OVERLAY_COLORS = ["#1F4E79", "#C47B12", "#D55E00"];
function paintOverlayPicks() {
  const host = document.getElementById("overlay-picks");
  if (!host) return;
  state.overlay = state.overlay.filter(id => id !== state.eventId && allEvents().some(event => event.id === id)).slice(0, 2);
  host.innerHTML = "";
  allEvents().forEach(event => {
    if (event.id === state.eventId) return;
    const label = document.createElement("label");
    label.className = "pick";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = state.overlay.includes(event.id);
    box.addEventListener("change", () => {
      if (box.checked && state.overlay.length >= 2) {
        box.checked = false;
        return;
      }
      state.overlay = box.checked ? state.overlay.concat([event.id]) : state.overlay.filter(id => id !== event.id);
      render();
    });
    label.append(box, document.createTextNode(eventTitle(event)));
    host.appendChild(label);
  });
}
function esc(text) {
  return String(text == null ? "" : text).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
}
function fillSimpleTable(id, caption, headers, rows) {
  const table = document.getElementById(id);
  if (!table) return;
  table.innerHTML = "<caption>" + esc(caption) + "</caption><thead><tr>" + headers.map(h => "<th>" + esc(h) + "</th>").join("") + "</tr></thead><tbody>"
    + rows.map(row => "<tr>" + row.map(cell => "<td>" + esc(cell) + "</td>").join("") + "</tr>").join("")
    + "</tbody>";
}
function drawOverlay() {
  const host = document.getElementById("overlay");
  if (!host) return;
  const ids = [state.eventId].concat(state.overlay).slice(0, 3);
  if (ids.length < 2) {
    host.innerHTML = "";
    return;
  }
  const anchor = state.spec.anchor;
  drawChart(host, {
    title: "锚资产路径叠加",
    height: 260, ref: 100, mark: 0, markLabel: "事件日",
    yFormat: v => v.toFixed(0),
    xTicks: [-state.sessions, 0, state.sessions - 1],
    series: ids.map((id, index) => {
      const event = allEvents().find(item => item.id === id);
      const path = indexedPath(dailyPack(anchor), event.date, state.sessions);
      return path
        ? {name: eventTitle(event), color: OVERLAY_COLORS[index], width: index === 0 ? 2.6 : 1.5, x: path.tau, y: path.value}
        : {name: eventTitle(event), color: OVERLAY_COLORS[index], x: [], y: []};
    }),
  });
}
function figureCaption() {
  const event = activeEvent();
  const stats = analyze(event.month, state.width);
  const anchor = state.spec.anchor;
  const en = state.lang === "en";
  const bits = state.spec.path.map(id => NAMES[id] + " " + fmt(stats && stats.cum[id]) + "%").join(en ? "; " : "，");
  if (en) {
    return "Figure. Price path around " + eventTitle(event) + " (" + event.date + "), " + state.sessions + " sessions, indexed to 100 at the " + (state.base === "pre" ? "last close before the event" : "event-day close") + ". Anchor: " + NAMES[anchor] + ". Cumulative log return over " + (stats ? stats.nAfter : "—") + " months after: " + bits + ". Sample " + LAB.meta.sample_start + " to " + LAB.meta.sample_end + ". Descriptive window, not causal identification. EF Lab " + labVersion() + ". For study only. Not investment advice.";
  }
  return "图 " + eventTitle(event) + "（" + event.date + "）前后 " + state.sessions + " 个交易日的价格路径，指数以" + (state.base === "pre" ? "事件前最后收盘" : "事件日收盘") + "为 100。锚资产为" + NAMES[anchor] + "。事后 " + (stats ? stats.nAfter : "—") + " 个月累计对数收益：" + bits + "。样本 " + LAB.meta.sample_start + " 至 " + LAB.meta.sample_end + "。GPR 为 Caldara–Iacoviello 日度 GPRD 的月均值；黄金、布伦特、美元指数和恒生来自 Yahoo Finance，沪深300来自新浪财经。描述性窗口，不是因果识别。EF Lab " + labVersion() + "，仅供学习与研究，不构成投资建议。";
}
function drawBoard(width) {
  const table = document.getElementById("board");
  const en = state.lang === "en";
  const anchor = state.spec.anchor;
  const other = ["csi","brent","hsi","dxy"].find(id => id !== anchor && state.spec.path.includes(id)) || state.spec.path.find(id => id !== anchor);
  const pair = shownPairs().find(item => item.id === "csi") || shownPairs()[0];
  const headers = en
    ? ["Event", "After " + NAMES[anchor], other ? NAMES[other] : "—", other ? NAMES[anchor] + " − " + NAMES[other] : "Gap", pair ? "Corr. change" : "Corr.", "Haven", "Months", "Gold percentile"]
    : ["事件", "事后" + NAMES[anchor], other ? NAMES[other] : "—", other ? NAMES[anchor] + "−" + NAMES[other] : "差额", pair ? "相关变化" : "相关", "避险强度", "月数", "黄金分位"];
  table.innerHTML = "<thead><tr>" + headers.map(h => "<th>" + h + "</th>").join("") + "</tr></thead>";
  const body = document.createElement("tbody");
  allEvents().forEach(event => {
    const stats = analyze(event.month, width);
    const tr = document.createElement("tr");
    tr.className = "click" + (event.id === state.eventId ? " active" : "");
    const key = pair ? "c" + pairKey(pair.id) : "";
    const delta = key && stats && stats.before && stats.after && stats.before[key] != null && stats.after[key] != null ? stats.after[key] - stats.before[key] : null;
    const excess = other && stats && stats.cum[anchor] != null && stats.cum[other] != null ? stats.cum[anchor] - stats.cum[other] : null;
    const pct = stats && !stats.partial ? goldPct(stats.cum.gold) : null;
    const cells = [
      eventTitle(event),
      fmt(stats && stats.cum[anchor]),
      other ? fmt(stats && stats.cum[other]) : "—",
      fmt(excess),
      delta == null ? "—" : fmt(delta, 2),
      stats && stats.after ? stats.after.score.toFixed(0) : "—",
      stats ? String(stats.nAfter) + (stats.partial ? "*" : "") : "—",
      pct == null ? "—" : Math.round(100 * pct) + "%",
    ];
    cells.forEach(text => { const td = document.createElement("td"); td.textContent = text; tr.appendChild(td); });
    tr.addEventListener("click", () => { state.eventId = event.id; render(); });
    body.appendChild(tr);
  });
  table.appendChild(body);
}

function applyI18n() {
  const en = state.lang === "en";
  Object.assign(NAMES, en ? NAMES_EN : NAMES_ZH);
  document.documentElement.lang = en ? "en" : "zh-CN";
  const button = document.getElementById("lang");
  if (button) button.textContent = en ? "中文" : "EN";
  document.querySelectorAll("[data-en]").forEach(node => {
    if (!node.dataset.zhText) node.dataset.zhText = node.textContent;
    node.textContent = en ? node.dataset.en : node.dataset.zhText;
  });
  document.querySelectorAll("#scenes button").forEach((node, index) => {
    if (SCENES[index]) node.textContent = en ? SCENES[index].labelEn : SCENES[index].label;
  });
  document.querySelectorAll("[data-quick]").forEach(node => { node.textContent = NAMES[node.dataset.quick] || node.textContent; });
  document.querySelectorAll("[data-path]").forEach(node => {
    if (node.parentElement && node.parentElement.lastChild) node.parentElement.lastChild.textContent = NAMES[node.dataset.path];
  });
  document.querySelectorAll("#anchor option").forEach(option => {
    if (NAMES[option.value]) option.textContent = NAMES[option.value];
  });
  const roleLabels = en
    ? {off:"Exclude", watch:"Watch", hedge:"Hedge", comove:"Comove"}
    : {off:"不纳入", watch:"对照", hedge:"对冲", comove:"同向"};
  document.querySelectorAll("[data-score] option").forEach(option => {
    if (roleLabels[option.value]) option.textContent = roleLabels[option.value];
  });
  document.querySelectorAll("[data-score]").forEach(select => {
    const label = select.previousElementSibling;
    if (label && NAMES[select.dataset.score]) label.textContent = NAMES[select.dataset.score];
  });
  const sortLabels = en
    ? {time:"By time", excess:"By relative return", haven:"By haven score"}
    : {time:"按时间", excess:"按相对表现", haven:"按避险强度"};
  document.querySelectorAll("[data-sort]").forEach(node => { if (sortLabels[node.dataset.sort]) node.textContent = sortLabels[node.dataset.sort]; });
  document.querySelectorAll("[data-title-en]").forEach(node => {
    if (!node.dataset.titleZh) node.dataset.titleZh = node.title || "";
    node.title = en ? node.dataset.titleEn : node.dataset.titleZh;
  });
  document.querySelectorAll("[data-ph-en]").forEach(node => {
    if (!node.dataset.phZh) node.dataset.phZh = node.placeholder || "";
    node.placeholder = en ? node.dataset.phEn : node.dataset.phZh;
  });
  document.getElementById("brand-title").textContent = en ? "EF Lab · Geopolitical Risk and Safe-Haven Lab" : "EF Lab · 地缘政治风险 × 避险资产实验室";
  document.getElementById("brand-sub").textContent = en ? "For study only. Not investment advice." : "Interactive Geopolitical Risk and Safe-Haven Lab · 仅供学习与研究，不构成投资建议";
  document.title = en ? "EF Lab | Geopolitical risk and safe havens" : "EF Lab | 地缘政治风险 × 避险资产";
  const foot = document.getElementById("site-foot");
  if (foot) foot.innerHTML = en
    ? 'Part of <a href="https://eugenefinance.tech">EF Lab · eugenefinance.tech</a> · ' + labVersion() + ' · For study only. Not investment advice. Past prices are not a forecast. Data are not updated automatically; the published sample ends in 2026-09. Reproduce with <code>fetch_data.py</code> and <code>build.py</code>. <a href="paper.html">Paper notes</a> · <a href="feed.xml">RSS</a>.'
    : 'Part of <a href="https://eugenefinance.tech">EF Lab · eugenefinance.tech</a> · ' + labVersion() + ' · 仅供学习与研究，不构成投资建议。历史走势不代表未来表现。数据不是自动日更，最近一次样本止于 2026-09。复现：<code>fetch_data.py</code> + <code>build.py</code> · <a href="paper.html">论文配套</a> · <a href="feed.xml">RSS</a>。';
  if (LAB) {
    document.getElementById("lede").textContent = en
      ? "Monthly sample " + LAB.meta.sample_start + " to " + LAB.meta.sample_end + ", " + LAB.meta.n_months + " months. Pick an event, then read the price path, the correlation change, and the site-defined haven score. Data change only when someone reruns build.py."
      : "月度样本 " + LAB.meta.sample_start + " 至 " + LAB.meta.sample_end + "，共 " + LAB.meta.n_months + " 个月。先选一个经典事件，再看价格路径、相关差和避险强度。数据要重新运行 build.py 才会更新，不是自动日更。";
    const sourceFoot = document.getElementById("foot");
    if (sourceFoot) sourceFoot.textContent = en
      ? "GPR is the monthly mean of Caldara–Iacoviello daily GPRD. Gold GC=F, Brent BZ=F, the dollar index DX-Y.NYB and Hang Seng ^HSI come from Yahoo Finance. CSI 300 is the Sina price index sh000300."
      : "GPR：Caldara–Iacoviello 日度 GPRD 的月均值。黄金 GC=F、布伦特 BZ=F、美元指数 DX-Y.NYB、恒生 ^HSI 来自 Yahoo Finance。沪深300是新浪 sh000300。";
  }
  const method = document.getElementById("method-body");
  if (method && !method.dataset.zh) method.dataset.zh = method.innerHTML;
  if (method) method.innerHTML = en ? "<p>GPR is the monthly mean of Caldara and Iacoviello's daily GPRD, downloaded 13 Oct 2026. Gold is COMEX GC=F, Brent is ICE BZ=F, the dollar is ICE DXY, Hang Seng is Yahoo ^HSI, and CSI 300 is the Sina price index sh000300, not the official vendor archive.</p><p class='note'>The haven score is this site's descriptive index, not a standard measure from the literature. In the paper preset, E = 50 × (1 − average correlation of gold with CSI 300 and Hang Seng), G = 50 × (1 + correlation of gold with the change in GPR), D = 50 × (1 − correlation of gold with DXY), and the score is (E+G+D)/3. Fifty means those correlations are zero. The page also reports equal-weight and equity-weighted variants, and GPR act versus threat sub-indices when those series are loaded.</p><p class='note'>The impulse response is a recursive monthly VAR. AIC chooses the lag from 1 to 3; this sample uses lag 1. Cholesky order: GPR change, Brent, dollar, gold, CSI 300, Hang Seng. Bands are a 90 percent residual bootstrap with 200 draws. A custom order is a lag-1 point estimate without bands. This is not structural identification.</p><p class='note'>Prices are aligned on each market's own sessions. Missing days are not filled across markets. The default correlation window is 12 months because a 6-month window has about six points. Event dates are hand anchors. The 2 March 2026 Hormuz date is traced from a 26 March 2026 Reuters story and has not been audited cable by cable. Data are rebuilt by running build.py; they are not updated automatically. The sample end is pinned at 2026-09.</p><p class='note'>The percentile compares an event's gold cumulative return with up to 120 ordinary months drawn from complete windows that do not contain a hand-dated event month. The seed is 20261013. A high percentile is not a causal effect. Most of the original dates are Middle East or oil episodes chosen after the fact. Brexit, the 2017 North Korean nuclear test, and the 2022 Pelosi visit are the non-Middle-East additions.</p><p class='note'>On 30 Jan 2026 the GC=F continuous future has a larger daily log drop than 15 Apr 2013. That series is not the LBMA fix. This build has no spot price, so a futures roll cannot be ruled out. Monthly returns are month-end to month-end and include that session in January 2026.</p>" : method.dataset.zh;
}
function render() {
  applyI18n();
  const event = activeEvent();
  const stats = analyze(event.month, state.width);
  const box = document.getElementById("readout");
  const said = sentence(event, stats);
  box.className = "readout " + (said.tone || "");
  const src = SOURCES[event.id];
  const srcLine = src
    ? "<p class='note'>" + (state.lang === "en" ? "Source: " : "来源：") + "<a href='" + src.url + "'>" + src.label + "</a> " + (state.lang === "en" ? "The date is a hand anchor, not an estimated break, and it has not been checked cable by cable." : "日期是手工锚点，不是估计出来的断点。本页没有逐条核对原始电讯。") + "</p>"
    : "<p class='note'>" + (state.lang === "en" ? "The date is a hand anchor. This row does not yet have its own source link." : "日期是手工锚点。这条还没有单独核对过的来源链接。") + "</p>";
  box.innerHTML = "<div>" + esc(said.text) + "</div><details><summary>" + (state.lang === "en" ? "Event note" : "事件背景") + "</summary><p class='note'>" + esc(eventNote(event)) + "</p>" + srcLine + "</details>";
  const anchor = state.spec.anchor;
  const score = stats && stats.after ? stats.after.score : null;
  const tone = score == null ? "" : score >= 60 ? "color:#0072b2" : score < 45 ? "color:#d55e00" : "";
  const preferred = ["brent","csi","hsi","dxy"].filter(id => id !== anchor && state.spec.path.includes(id));
  const extras = preferred.slice(0, 2);
  const statItems = [
    ["避险强度（事后）", score == null ? "—" : score.toFixed(0), tone],
    [NAMES[anchor] + "累计", fmt(stats && stats.cum[anchor]) + "%", ""],
  ];
  extras.forEach(id => statItems.push([NAMES[id] + "累计", fmt(stats && stats.cum[id]) + "%", ""]));
  statItems.push(["事后 GPR 月均", stats && stats.gprAfter != null ? Math.round(stats.gprAfter) + "，事前 " + Math.round(stats.gprBefore) : "—", ""]);
  document.getElementById("stats").innerHTML = statItems.map(([label, value, style]) => "<div class='stat'><b style='" + style + "'>" + value + "</b><span>" + label + "</span></div>").join("");
  const meter = document.getElementById("meter-fill");
  const meterLabel = document.getElementById("meter-label");
  if (score == null) {
    meter.style.width = "0";
    meterLabel.textContent = state.lang === "en" ? "This window does not produce a haven score." : "这个窗口没有算出避险强度。";
  } else {
    meter.style.width = Math.max(0, Math.min(100, score)) + "%";
    meter.style.background = score >= 60 ? "#0072B2" : score < 45 ? "#D55E00" : "#C47B12";
    meterLabel.textContent = state.lang === "en"
      ? "Haven score " + score.toFixed(0) + " / 100, about the " + havenPercentile(score) + "th percentile of the 36-month rolling history (median " + havenMedian().toFixed(0) + "). 50 means zero correlation. Blue is at least 60, orange is below 45."
      : "避险强度 " + score.toFixed(0) + " / 100，约在 36 个月滚动历史的第 " + havenPercentile(score) + " 百分位（中位数 " + havenMedian().toFixed(0) + "）。50 是零相关。蓝色 ≥ 60，橙色 < 45。";
  }

  const pathIds = state.spec.path.includes(anchor) ? state.spec.path : [anchor].concat(state.spec.path);
  const anchorPath = indexedPath(dailyPack(anchor), event.date, state.sessions);
  drawChart(document.getElementById("path"), {
    title: eventTitle(event) + (state.lang === "en" ? " price path" : " 前后价格路径"),
    long: (state.lang === "en" ? "Indexed price path around " : "事件前后价格路径：") + eventTitle(event),
    descId: "path-cap",
    height: 320, ref: 100, mark: 0, markLabel: state.lang === "en" ? "Event" : "事件日",
    yFormat: v => v.toFixed(0),
    xTicks: [-state.sessions, -20, 0, 20, state.sessions - 1],
    series: pathIds.map(name => {
      const path = indexedPath(dailyPack(name), event.date, state.sessions);
      return path ? {name: NAMES[name] + (name === anchor ? "（锚）" : ""), color: COLORS[name], width: name === anchor ? 2.6 : 1.25, x: path.tau, y: path.value} : {name: NAMES[name], color: COLORS[name], x:[], y:[]};
    }),
  });
  document.querySelectorAll("[data-quick]").forEach(button => {
    button.setAttribute("aria-pressed", String(state.spec.path.includes(button.dataset.quick)));
  });
  document.querySelectorAll("[data-sort]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.sort === state.sort));
  });
  document.getElementById("base-event").setAttribute("aria-pressed", String(state.base !== "pre"));
  document.getElementById("base-pre").setAttribute("aria-pressed", String(state.base === "pre"));
  document.getElementById("path-legend").innerHTML = pathIds.map(name => "<span><i class='swatch' style='background:" + COLORS[name] + "'></i>" + NAMES[name] + (name === anchor ? (state.lang === "en" ? " (anchor)" : "（锚）") : "") + "</span>").join("");
  document.getElementById("path-cap").textContent = state.lang === "en"
    ? "Warm lines are gold and Brent. Cool lines are the dollar, CSI 300 and Hang Seng. The thicker line is the anchor. The vertical line is the event day. The index is 100 at " + (state.base === "pre" ? "the last close before the event" : "the event-day close") + ". The table lists the index on the event day and at the end of the window."
    : "暖色是黄金和布伦特，冷色是美元、沪深300和恒生。更粗的线是锚资产。竖线是事件日。当前指数以" + (state.base === "pre" ? "事件前最后收盘" : "事件日收盘") + "为 100。旁边的表给出事件日和窗口末端的指数。";
  fillSimpleTable("path-table", state.lang === "en" ? "Index on the event day and at the end of the window" : "各资产在事件日和窗口末端的指数",
    state.lang === "en" ? ["Asset", "Event day", "End of window"] : ["资产", "事件日", "窗口末端"], pathIds.map(name => {
    const path = indexedPath(dailyPack(name), event.date, state.sessions);
    if (!path) return [NAMES[name], "—", "—"];
    const at0 = path.tau.indexOf(0);
    const last = path.value.length ? path.value[path.value.length - 1] : null;
    const atEvent = at0 >= 0 ? path.value[at0] : null;
    const num = value => value == null || !isFinite(value) ? "—" : Number(value).toFixed(1);
    return [NAMES[name], num(atEvent), num(last)];
  }));
  paintOverlayPicks();
  drawOverlay();

  const gprClock = anchorPath || indexedPath(dailyPack("gold"), event.date, state.sessions);
  const gprSeries = dailyPack("gpr");
  const gprMap = new Map(gprSeries ? gprSeries.dates.map((date, i) => [date, gprSeries.close[i]]) : []);
  drawChart(document.getElementById("gpr"), {
    title: state.lang === "en" ? "Daily GPR" : "GPR 日度水平",
    long: state.lang === "en" ? "Daily geopolitical risk in the same price window" : "同一价格窗口里的 GPR 日度水平",
    descId: "gpr-cap",
    height: 180, mark: 0, yDigits: 0,
    xTicks: [-state.sessions, 0, state.sessions - 1],
    series: gprClock ? [{name:"GPR", color:"#1c1915", x: gprClock.tau, y: gprClock.date.map(date => gprMap.get(date) ?? null)}] : [],
  });
  const gprRows = [];
  if (gprClock) {
    const marks = new Set([-state.sessions, -10, 0, 10, state.sessions - 1, gprClock.tau[gprClock.tau.length - 1]]);
    gprClock.tau.forEach((tau, index) => {
      if (!marks.has(tau)) return;
      const level = gprMap.get(gprClock.date[index]);
      gprRows.push([String(tau), gprClock.date[index], level == null ? "—" : Number(level).toFixed(1)]);
    });
  }
  fillSimpleTable("gpr-table", state.lang === "en" ? "GPR on selected sessions in the chart" : "图中若干交易日的 GPR",
    state.lang === "en" ? ["Session", "Date", "GPR"] : ["交易日", "日期", "GPR"], gprRows);

  drawCorrBars(stats);
  document.getElementById("corr-cap").textContent = stats
    ? (state.lang === "en"
      ? "Blue is before the event month and orange is after. The number on the right is after minus before. Before uses " + stats.nBefore + " months and excludes the event month. After uses " + stats.nAfter + " months and includes it." + (stats.partial ? " The window is cut by the end of the sample." : "") + " On a narrow screen, scroll the chart sideways. The table has the same numbers."
      : "蓝条是事前，橙条是事后。右侧数字是事后减事前。事前 " + stats.nBefore + " 个月，不含事件月；事后 " + stats.nAfter + " 个月，含事件月。" + (stats.partial ? " 窗口被样本端点截断。" : "") + "窄屏可以左右滑动。旁边的表是同一组数字。")
    : "";
  fillSimpleTable("corr-table", state.lang === "en" ? "Correlations before and after" : "事件前后相关系数",
    state.lang === "en" ? ["Pair", "Before", "After", "Change"] : ["序列", "事前", "事后", "差值"], shownPairs().map(item => {
    const key = "c" + pairKey(item.id);
    const before = stats && stats.before ? stats.before[key] : null;
    const after = stats && stats.after ? stats.after[key] : null;
    return [NAMES[state.spec.anchor] + "–" + NAMES[item.id], before == null ? "—" : before.toFixed(2), after == null ? "—" : after.toFixed(2), before == null || after == null ? "—" : (after - before).toFixed(2)];
  }));

  const after = stats && stats.after;
  const partHost = document.getElementById("parts");
  if (!after) partHost.innerHTML = "<p class='note'>" + (state.lang === "en" ? "Not enough months, or no series is marked hedge or comove." : "月份不足，或没有把任何变量设成对冲或同向。") + "</p>";
  else if (after.parts) {
    partHost.innerHTML = after.parts.map(part => "<p style='margin:8px 0'><b>" + NAMES[part.id] + " " + part.value.toFixed(0) + "</b><br><span class='note'>" + (part.role === "hedge" ? (state.lang === "en" ? "Hedge: a more negative correlation with the anchor raises this" : "对冲：和锚资产越负相关越高") : (state.lang === "en" ? "Comove: a more positive correlation with the anchor raises this" : "同向：和锚资产越正相关越高")) + (state.lang === "en" ? ", correlation " : "，相关 ") + part.corr.toFixed(2) + "</span></p>").join("") + "<p class='note'>" + (state.lang === "en" ? "These items are equal-weighted. 50 means the correlation is zero." : "这几项等权。50 对应相关系数为 0。") + "</p>";
  } else {
    partHost.innerHTML = [
      [state.lang === "en" ? "Equity hedge" : "权益对冲", after.equity, state.lang === "en" ? "Higher when gold's average correlation with CSI 300 and Hang Seng is more negative" : "黄金与沪深300、恒生的平均相关越负，这项越高"],
      [state.lang === "en" ? "GPR link" : "GPR 联动", after.gpr, state.lang === "en" ? "Higher when gold and the change in GPR move together" : "黄金收益与 GPR 变动越同向，这项越高"],
      [state.lang === "en" ? "Dollar hedge" : "美元对冲", after.dollar, state.lang === "en" ? "Higher when gold and the dollar index move apart" : "黄金与美元指数越反向，这项越高"],
    ].map(([name, value, hint]) => "<p style='margin:8px 0'><b>" + name + " " + value.toFixed(0) + "</b><br><span class='note'>" + hint + "</span></p>").join("");
  }
  fillRobust(event);

  const havenScores = rollingHaven();
  const havenX = [], havenY = [], dotX = [], dotColors = [];
  LAB.months.forEach((month, i) => {
    const value = havenScores[i];
    if (value == null) return;
    const xValue = i;
    havenX.push(xValue); havenY.push(value);
    const high = LAB.haven.high[i];
    let color = "#8a8478";
    if (high === 1 && value >= 60) color = "#0072b2";
    else if (high === 1 && value < 45) color = "#d55e00";
    else if (high === 1) color = "#e69f00";
    dotX.push({x:xValue, y:value, color});
  });
  const eventIndex = LAB.months.indexOf(event.month);
  drawChart(document.getElementById("haven"), {
    title: state.lang === "en" ? "36-month rolling haven score" : "36个月滚动避险强度",
    long: state.lang === "en" ? "Rolling haven score. The vertical line is the selected event." : "36个月滚动避险强度，竖线是当前事件月",
    descId: "haven-cap",
    height: 240, ref: 50, mark: eventIndex, yDigits: 0,
    xFormat: v => LAB.months[Math.round(v)] || "",
    xTicks: LAB.months.map((month, i) => month.endsWith("-01") ? i : null).filter(v => v != null && v % 24 === 0),
    series: [{
      name: state.lang === "en" ? "Haven score" : "避险强度",
      color:"#1c1915",
      x: havenX,
      y: havenY,
      bandLo: LAB.haven.lo ? havenX.map(i => LAB.haven.lo[i]) : null,
      bandHi: LAB.haven.hi ? havenX.map(i => LAB.haven.hi[i]) : null,
    }].concat(LAB.haven.pc1 ? [{
      name: "PC1",
      color: "#0072b2",
      width: 1.1,
      x: havenX.filter(i => LAB.haven.pc1[i] != null),
      y: havenX.map(i => LAB.haven.pc1[i]).filter(v => v != null),
    }] : []),
  });
  paintDots("haven", dotX, eventIndex);
  const havenRows = [];
  LAB.months.forEach((month, index) => {
    if (havenScores[index] == null) return;
    if (!month.endsWith("-01") && month !== event.month) return;
    havenRows.push([month, Number(havenScores[index]).toFixed(0), LAB.haven.high[index] === 1 ? (state.lang === "en" ? "yes" : "是") : (state.lang === "en" ? "no" : "否")]);
  });
  fillSimpleTable("haven-table", state.lang === "en" ? "January readings and the event month. The chart has every month." : "每年 1 月和事件月。图里是完整月度序列。",
    state.lang === "en" ? ["Month", "Score", "High GPR"] : ["月份", "强度", "高压"], havenRows);

  document.getElementById("heat-title").textContent = NAMES[state.spec.anchor] + (state.lang === "en" ? " rolling correlation, by quarter" : "滚动相关，按季度");
  if (window.__heavy) {
    drawHeat(event, liveHeat());
    drawIrf();
  }
  drawCompare();
  drawCar(event);
  drawBoard(state.width);
  refreshVariableControls();
  document.body.dataset.event = event.id;
  document.body.dataset.goldCum = stats && stats.cum[state.spec.anchor] != null ? stats.cum[state.spec.anchor].toFixed(4) : "";
  document.body.dataset.haven = score == null ? "" : score.toFixed(4);
  document.body.dataset.partial = stats ? String(stats.partial) : "";
  fillVerdict();
  fillGoldNote();
  const card = document.getElementById("card-link");
  if (card) {
    const builtIn = LAB.events.some(item => item.id === event.id);
    card.hidden = !builtIn;
    if (builtIn) card.href = "cards/" + event.id + ".jpg";
    card.textContent = state.lang === "en" ? "Vertical card" : "竖版卡片";
  }
  writeUrl();
  verifyCheck();
}

function paintDots(hostId, dots) {
  const svg = document.querySelector("#" + hostId + " svg");
  if (!svg || !dots.length) return;
  const width = 860, height = 240, m = {l:54, r:12, t:12, b:36};
  const iw = width - m.l - m.r, ih = height - m.t - m.b;
  const xs = dots.map(d => d.x), ys = dots.map(d => d.y);
  let y0 = Math.min(...ys, 50), y1 = Math.max(...ys, 50);
  const pad = (y1 - y0) * 0.08 || 1;
  y0 -= pad; y1 += pad;
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const X = x => m.l + (x - x0) / (x1 - x0) * iw;
  const Y = y => m.t + (y1 - y) / (y1 - y0) * ih;
  dots.forEach(dot => {
    if (LAB.haven.high[dot.x] !== 1) return;
    svg.appendChild(svgNode("circle", {cx:X(dot.x), cy:Y(dot.y), r:2.2, fill:dot.color}));
  });
}

function drawCorrBars(stats) {
  const host = document.getElementById("corr");
  host.innerHTML = "";
  const rows = shownPairs().map(item => [NAMES[state.spec.anchor] + "–" + NAMES[item.id], "c" + pairKey(item.id)]);
  if (!rows.length) {
    host.innerHTML = "<p class='note'>没有纳入相关的变量。</p>";
    return;
  }
  const width = 860, height = Math.max(160, 36 + rows.length * 42), m = {l:128, r:16, t:16, b:28};
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`});
  const iw = width - m.l - m.r, ih = height - m.t - m.b;
  const Y = i => m.t + (i + 0.5) * ih / rows.length;
  [-1, -0.5, 0, 0.5, 1].forEach(v => {
    const x = m.l + (v + 1) / 2 * iw;
    svg.appendChild(svgNode("line", {x1:x, x2:x, y1:m.t, y2:height-m.b, stroke:"#eceae4"}));
    const text = svgNode("text", {x, y:height-8, "text-anchor":"middle", fill:"#3a342c", "font-size":13});
    text.textContent = v.toFixed(1);
    svg.appendChild(text);
  });
  const zero = m.l + iw / 2;
  svg.appendChild(svgNode("line", {x1:zero, x2:zero, y1:m.t, y2:height-m.b, stroke:"#1c1915", "stroke-width":0.8}));
  rows.forEach((row, i) => {
    const text = svgNode("text", {x:m.l-8, y:Y(i)+4, "text-anchor":"end", fill:"#1c1915", "font-size":13});
    text.textContent = row[0];
    svg.appendChild(text);
    [["before","#0072b2",-6],["after","#d55e00",6]].forEach(([side, color, dy]) => {
      const block = stats && stats[side];
      const value = block ? block[row[1]] : null;
      if (value == null) return;
      const x = m.l + (value + 1) / 2 * iw;
      const y = Y(i) + dy;
      svg.appendChild(svgNode("line", {x1:zero, x2:x, y1:y, y2:y, stroke:color, "stroke-width":6}));
    });
    const before = stats && stats.before ? stats.before[row[1]] : null;
    const after = stats && stats.after ? stats.after[row[1]] : null;
    if (before != null && after != null) {
      const delta = svgNode("text", {x: width - m.r, y: Y(i) + 4, "text-anchor":"end", fill:"#1c1915", "font-size":13});
      const change = after - before;
      delta.textContent = (change > 0 ? "+" : "") + change.toFixed(2);
      svg.appendChild(delta);
    }
  });
  [["事前","#0072b2",0],["事后","#d55e00",1]].forEach(([name, color, i]) => {
    svg.appendChild(svgNode("rect", {x:m.l + i * 70, y:2, width:10, height:10, fill:color}));
    const text = svgNode("text", {x:m.l + 14 + i * 70, y:11, fill:"#3a342c", "font-size":13});
    text.textContent = state.lang === "en" ? (name === "事前" ? "Before" : "After") : name;
    svg.appendChild(text);
  });
  host.appendChild(svg);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", state.lang === "en" ? "Correlations before and after the event" : "事件前后相关系数");
  svg.setAttribute("aria-describedby", "corr-cap");
}

function invertMatrix(matrix) {
  const n = matrix.length;
  const a = matrix.map((row, i) => row.concat(Array.from({length:n}, (_, j) => i === j ? 1 : 0)));
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let row = col + 1; row < n; row++) if (Math.abs(a[row][col]) > Math.abs(a[pivot][col])) pivot = row;
    if (Math.abs(a[pivot][col]) < 1e-10) return null;
    const hold = a[col]; a[col] = a[pivot]; a[pivot] = hold;
    const div = a[col][col];
    for (let j = col; j < 2 * n; j++) a[col][j] /= div;
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const factor = a[row][col];
      for (let j = col; j < 2 * n; j++) a[row][j] -= factor * a[col][j];
    }
  }
  return a.map(row => row.slice(n));
}
function cholesky(matrix) {
  const n = matrix.length;
  const lower = Array.from({length:n}, () => Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let sum = 0;
      for (let k = 0; k < j; k++) sum += lower[i][k] * lower[j][k];
      if (i === j) {
        const value = matrix[i][i] - sum;
        if (value <= 1e-12) return null;
        lower[i][j] = Math.sqrt(value);
      } else lower[i][j] = (matrix[i][j] - sum) / lower[j][j];
    }
  }
  return lower;
}
function fitCustomVar(order) {
  if (order.length < 2) return null;
  const cols = order.map(id => id === "dgpr" ? LAB.dgpr : LAB.ret[id]);
  const sample = [];
  for (let t = 0; t < LAB.months.length; t++) {
    const row = cols.map(col => col[t]);
    if (row.every(value => value != null && isFinite(value))) sample.push(row);
  }
  const k = order.length;
  if (sample.length < k + 30) return null;
  const p = 1 + k;
  const xtx = Array.from({length:p}, () => Array(p).fill(0));
  const xty = Array.from({length:p}, () => Array(k).fill(0));
  for (let t = 1; t < sample.length; t++) {
    const x = [1].concat(sample[t - 1]);
    const y = sample[t];
    for (let i = 0; i < p; i++) {
      for (let j = 0; j < p; j++) xtx[i][j] += x[i] * x[j];
      for (let j = 0; j < k; j++) xty[i][j] += x[i] * y[j];
    }
  }
  const inv = invertMatrix(xtx);
  if (!inv) return null;
  const beta = Array.from({length:k}, () => Array(p).fill(0));
  for (let eq = 0; eq < k; eq++) {
    for (let i = 0; i < p; i++) {
      let total = 0;
      for (let j = 0; j < p; j++) total += inv[i][j] * xty[j][eq];
      beta[eq][i] = total;
    }
  }
  const resid = [];
  for (let t = 1; t < sample.length; t++) {
    const x = [1].concat(sample[t - 1]);
    const e = [];
    for (let eq = 0; eq < k; eq++) {
      let fitted = 0;
      for (let i = 0; i < p; i++) fitted += beta[eq][i] * x[i];
      e.push(sample[t][eq] - fitted);
    }
    resid.push(e);
  }
  const sigma = Array.from({length:k}, () => Array(k).fill(0));
  resid.forEach(e => { for (let i = 0; i < k; i++) for (let j = 0; j < k; j++) sigma[i][j] += e[i] * e[j]; });
  for (let i = 0; i < k; i++) for (let j = 0; j < k; j++) sigma[i][j] /= resid.length;
  const lower = cholesky(sigma);
  if (!lower) return null;
  let shock = lower.map(row => row[0]);
  if (shock[0] < 0) shock = shock.map(value => -value);
  const steps = [shock];
  for (let h = 1; h <= 12; h++) {
    const prev = steps[h - 1];
    const next = Array(k).fill(0);
    for (let eq = 0; eq < k; eq++) for (let v = 0; v < k; v++) next[eq] += beta[eq][1 + v] * prev[v];
    steps.push(next);
  }
  const cum = order.map(() => []);
  for (let eq = 0; eq < k; eq++) {
    let running = 0;
    steps.forEach(step => { running += step[eq]; cum[eq].push(Math.round(running * 10000) / 10000); });
  }
  return {order, cum, t: sample.length};
}
function drawIrf() {
  const host = document.getElementById("irf");
  const en = state.lang === "en";
  host.innerHTML = "";
  const headers = en ? ["Variable", "h=0", "h=6", "h=12"] : ["变量", "h=0", "h=6", "h=12"];
  if (!isPresetVar()) {
    const fit = fitCustomVar(state.spec.varOn);
    document.getElementById("irf-title").textContent = fit
      ? (en ? "Cumulative response, custom order (lag 1, T=" + fit.t + ")" : "自定变量的累计脉冲响应（1 阶，T=" + fit.t + "）")
      : (en ? "Cumulative response, custom order" : "自定变量的累计脉冲响应");
    document.getElementById("irf-cap").textContent = fit
      ? (en
        ? "Order: " + fit.order.map(id => NAMES[id]).join(", ") + ". The first variable gets a one-standard-deviation positive shock. This is a point estimate with no bootstrap band. Return variables are cumulative monthly log-return points. Restore the paper preset for the six-variable chart with a 90% band."
        : "顺序：" + fit.order.map(id => NAMES[id]).join("、") + "。第一位受到 1 个标准差的正向冲击。这是点估计，没有自助区间。收益变量的纵轴是月度对数收益百分点的累加。恢复论文设定后才会回到带 90% 区间的六变量图。")
      : (en ? "Keep at least two monthly series to estimate this small VAR." : "至少留下两个有月度收益的变量，才能估计这个小 VAR。");
    if (!fit) { fillSimpleTable("irf-table", "", headers, []); return; }
    fit.order.forEach((id, index) => {
      const wrap = document.createElement("div");
      host.appendChild(wrap);
      drawChart(wrap, {
        title: NAMES[id],
        long: (en ? "Cumulative response of " : "累计响应：") + NAMES[id],
        descId: "irf-cap",
        width: 280, height: 160,
        margin: {l:42, r:8, t:16, b:28},
        includeZero: true, yDigits: 1,
        xTicks: [0, 6, 12],
        series: [{name: NAMES[id], color:"#0072b2", x: fit.cum[index].map((_, h) => h), y: fit.cum[index]}],
      });
      const caption = document.createElement("div");
      caption.className = "note";
      caption.textContent = NAMES[id] + (id === "dgpr" ? (en ? " (index points)" : "（指数点）") : "（%）");
      wrap.insertBefore(caption, wrap.firstChild);
    });
    fillSimpleTable("irf-table", en ? "Point estimates at selected horizons. No band, because the order is not the paper order." : "选定期限的点估计。顺序不是论文顺序，所以没有区间。",
      headers, fit.order.map((id, index) => [NAMES[id], fit.cum[index][0].toFixed(2), fit.cum[index][6].toFixed(2), fit.cum[index][12].toFixed(2)]));
    return;
  }
  const view = irfView();
  if (view && view.cum) {
    const keys = Object.keys(view.cum);
    const labels = {ret_brent:"布伦特", ret_dxy:"美元指数", ret_gold:"黄金", ret_csi:"沪深300", ret_hsi:"恒生"};
    const labelsEn = {ret_brent:"Brent", ret_dxy:"Dollar index", ret_gold:"Gold", ret_csi:"CSI 300", ret_hsi:"Hang Seng"};
    const modeName = {
      lp: en ? "Local projection, total GPR" : "局部投影，总 GPR",
      act: en ? "Local projection, GPR acts" : "局部投影，地缘行动",
      threat: en ? "Local projection, GPR threats" : "局部投影，地缘威胁",
      "state-high": en ? "State-dependent LP, high-GPR lag" : "状态依赖局部投影，上月高压",
      "state-low": en ? "State-dependent LP, not high-GPR" : "状态依赖局部投影，上月非高压",
    }[state.irf] || (en ? "Local projection" : "局部投影");
    document.getElementById("irf-title").textContent = modeName;
    document.getElementById("irf-cap").textContent = en
      ? "Each horizon regresses the cumulative log return on a one-standard-deviation shock. The band is a HAC 90% interval. This is not the VAR bootstrap, and it is not structural identification."
      : "每个期限单独把累计对数收益对 1 个标准差的冲击做回归。阴影是 HAC 90% 区间。这不是 VAR 自助区间，也不是结构识别。";
    const horizon = (LAB.var.lp && LAB.var.lp.horizon) || keys.map((_, i) => i);
    keys.forEach(key => {
      const wrap = document.createElement("div");
      host.appendChild(wrap);
      const name = en ? (labelsEn[key] || key) : (labels[key] || key);
      drawChart(wrap, {
        title: name,
        long: (en ? "Cumulative response of " : "累计响应：") + name,
        descId: "irf-cap",
        width: 280, height: 160,
        margin: {l:42, r:8, t:16, b:28},
        includeZero: true, yDigits: 1,
        xTicks: [0, 6, 12],
        series: [{
          name: name, color:"#0072b2",
          x: horizon, y: view.cum[key],
          bandLo: view.lo[key], bandHi: view.hi[key],
        }],
      });
    });
    const cell = (key, h) => {
      const mid = view.cum[key][h];
      if (mid == null) return "—";
      const lo = view.lo[key][h], hi = view.hi[key][h];
      const text = Number(mid).toFixed(2);
      return lo == null ? text : text + " [" + Number(lo).toFixed(2) + ", " + Number(hi).toFixed(2) + "]";
    };
    fillSimpleTable("irf-table", en ? "Cumulative local projection at horizons 0, 6 and 12." : "局部投影在 0、6、12 期的累计响应。",
      headers, keys.map(key => [en ? (labelsEn[key] || key) : (labels[key] || key), cell(key, 0), cell(key, 6), cell(key, 12)]));
    return;
  }
  const spec = LAB.var;
  const orderNames = spec.keys.map((key, index) => NAMES[key] || spec.order[index]);
  document.getElementById("irf-title").textContent = en
    ? "Cumulative response to a GPR shock (lag " + spec.lags + ", T=" + spec.t + ")"
    : "GPR 冲击的累计脉冲响应（" + spec.lags + " 阶，T=" + spec.t + "）";
  document.getElementById("irf-cap").textContent = en
    ? "Recursive order: " + orderNames.join(", ") + ". The shade is a residual-bootstrap 90% band from " + spec.boot_kept + " draws. Return variables accumulate monthly log-return points. GPR is in index points. This is not structural identification. The table repeats horizons 0, 6 and 12."
    : "递归顺序：" + orderNames.join("、") + "。阴影是残差自助法 90% 区间，保留 " + spec.boot_kept + " 次。收益变量的纵轴是月度对数收益百分点的累加，近似价格水平变化；GPR 的纵轴是指数点。这不是结构因果。旁边的表给出 0、6、12 期。";
  spec.keys.forEach((key, index) => {
    const wrap = document.createElement("div");
    wrap.id = "irf-" + key;
    host.appendChild(wrap);
    drawChart(wrap, {
      title: orderNames[index],
      long: (en ? "Cumulative response of " : "累计响应：") + orderNames[index],
      descId: "irf-cap",
      width: 280, height: 160,
      margin: {l:42, r:8, t:16, b:28},
      includeZero: true, yDigits: 1,
      xTicks: [0, 6, 12],
      series: [{
        name: spec.order[index], color:"#0072b2",
        x: spec.horizon, y: spec.cum[key],
        bandLo: spec.lo[key], bandHi: spec.hi[key],
      }],
    });
    const caption = document.createElement("div");
    caption.className = "note";
    caption.textContent = orderNames[index] + "（" + spec.units[index] + "）";
    wrap.insertBefore(caption, wrap.firstChild);
  });
  const cell = (key, horizon) => {
    const index = spec.horizon.indexOf(horizon);
    if (index < 0 || spec.cum[key][index] == null) return "—";
    const mid = Number(spec.cum[key][index]).toFixed(2);
    const lo = spec.lo[key][index], hi = spec.hi[key][index];
    return lo == null ? mid : mid + " [" + Number(lo).toFixed(2) + ", " + Number(hi).toFixed(2) + "]";
  };
  fillSimpleTable("irf-table", en ? "Cumulative response at horizons 0, 6 and 12. Brackets are the 90% band." : "0、6、12 期累计响应。括号里是 90% 区间。",
    headers, spec.keys.map((key, index) => [orderNames[index], cell(key, 0), cell(key, 6), cell(key, 12)]));
}

function downloadPng(hostId, filename) {
  const svg = document.querySelector("#" + hostId + " svg");
  if (!svg) return;
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const box = (svg.getAttribute("viewBox") || "0 0 860 320").split(/[ ,]+/).map(Number);
  const w = box[2] || 860;
  const h = box[3] || 320;
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], {type:"image/svg+xml;charset=utf-8"}));
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = w * 2;
    canvas.height = h * 2;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fbfaf6";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
    });
    URL.revokeObjectURL(url);
  };
  img.src = url;
}
function csvCell(value) {
  if (value == null || value === "") return "";
  const text = String(value);
  return /[",\n]/.test(text) ? '"' + text.replaceAll('"', '""') + '"' : text;
}
function downloadEventCsv() {
  const anchor = state.spec.anchor;
  const other = ["csi", "brent", "hsi", "dxy"].find(id => id !== anchor && state.spec.path.includes(id)) || "";
  const lines = [
    ["note", "EF Lab " + labVersion() + "。超额=锚资产累计对数收益减对照资产，单位是百分点。避险强度是本站自定的三项等权分数，50 为零相关，不是文献标准指数。安慰剂分位默认用非重叠窗口。事后窗口从事件月起算。描述性结果，不是因果识别。样本 " + LAB.meta.sample_start + " 至 " + LAB.meta.sample_end + "。"],
    ["event", "date", "window_months", "n_after", "partial", "anchor", "anchor_cum", "other", "other_cum", "excess", "haven"],
  ];
  allEvents().forEach(event => {
    const stats = analyze(event.month, state.width);
    const anchorCum = stats && stats.cum[anchor];
    const otherCum = other && stats ? stats.cum[other] : null;
    lines.push([
      event.name, event.date, state.width, stats ? stats.nAfter : "", stats && stats.partial ? 1 : 0,
      NAMES[anchor], anchorCum == null ? "" : anchorCum.toFixed(4),
      other ? NAMES[other] : "", otherCum == null ? "" : otherCum.toFixed(4),
      anchorCum == null || otherCum == null ? "" : (anchorCum - otherCum).toFixed(4),
      stats && stats.after ? stats.after.score.toFixed(2) : "",
    ]);
  });
  const blob = new Blob(["\uFEFF" + lines.map(row => row.map(csvCell).join(",")).join("\n")], {type:"text/csv;charset=utf-8"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "event_windows.csv";
  link.click();
}
function download(hostId, filename) {
  const svg = document.querySelector("#" + hostId + " svg");
  if (!svg) {
    const status = document.getElementById("dl-status");
    if (status) status.textContent = state.lang === "en"
      ? "That chart is not drawn yet, so there is no SVG to download."
      : "这张图还没画出来，没有可下载的 SVG。";
    return;
  }
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const blob = new Blob([clone.outerHTML], {type:"image/svg+xml"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
function downloadGrid(hostId, filename, cols, cellW, cellH) {
  const svgs = [...document.querySelectorAll("#" + hostId + " svg")];
  if (!svgs.length) return;
  const rows = Math.ceil(svgs.length / cols);
  const wrap = svgNode("svg", {
    xmlns: "http://www.w3.org/2000/svg",
    viewBox: "0 0 " + (cols * cellW) + " " + (rows * cellH),
    width: cols * cellW,
    height: rows * cellH,
  });
  svgs.forEach((svg, index) => {
    const group = svgNode("g", {transform: "translate(" + ((index % cols) * cellW) + "," + (Math.floor(index / cols) * cellH) + ")"});
    group.innerHTML = svg.innerHTML;
    wrap.appendChild(group);
  });
  const blob = new Blob([wrap.outerHTML], {type:"image/svg+xml"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
function fillVerdict() {
  const host = document.getElementById("verdict");
  if (!host) return;
  const en = state.lang === "en";
  const split = [], down = [], other = [], partial = [];
  LAB.events.forEach(event => {
    const stats = analyze(event.month, state.width);
    const name = eventTitle(event);
    if (!stats || stats.cum.gold == null) return;
    if (stats.partial) { partial.push(name); return; }
    if (stats.cum.gold > 0 && stats.cum.csi < 0) split.push(name);
    else if (stats.cum.gold < 0) down.push(name);
    else other.push(name);
  });
  const mideast = LAB.events.filter(event => event.region === "mideast").length;
  const pack = LAB.placebo && LAB.placebo[String(state.width)];
  const join = list => list.length ? list.join(en ? "; " : "、") : (en ? "none" : "没有");
  if (en) {
    host.textContent = "At the selected " + state.width + "-month window, gold rose while CSI 300 fell for: " + join(split) + ". Gold itself fell for: " + join(down) + ". The rest did not split: " + join(other) + ". Incomplete windows are left out of those lists" + (partial.length ? " (" + partial.join("; ") + ")" : "") + ". " + mideast + " of " + LAB.events.length + " built-in dates are tagged Middle East, and all of them were chosen after the prices were known. " + (pack ? "The gold percentile uses " + pack.n_draw + " ordinary months drawn from " + pack.n_pool + " complete windows that do not contain an event month, seed " + pack.seed + "." : "");
  } else {
    host.textContent = "按当前 " + state.width + " 个月窗口，黄金上涨且沪深300下跌的是：" + join(split) + "。黄金本身下跌的是：" + join(down) + "。其余没有反向分开：" + join(other) + "。不完整的窗口不放进这三句" + (partial.length ? "（" + partial.join("、") + "）" : "") + "。" + LAB.events.length + " 个内置日期里有 " + mideast + " 个标成中东，而且都是事后挑选的。分位见总表最后一列" + (pack ? "，用的是种子 " + pack.seed + " 抽出的 " + pack.n_draw + " 个普通月份，母体是 " + pack.n_pool + " 个不包含事件月的完整窗口。" : "。");
  }
}
function fillGoldNote() {
  const host = document.getElementById("gold-note");
  const jumps = LAB.meta && LAB.meta.gold_jumps || [];
  if (!host || !jumps.length) return;
  const top = jumps[0];
  const prior = jumps.find(item => item.date === "2013-04-15") || jumps[1];
  const en = state.lang === "en";
  host.textContent = en
    ? "Data check: on " + top.date + " GC=F went from " + top.prev_close + " to " + top.close + ", a log return of " + top.log_return + "%. On " + (prior ? prior.date : "2013-04-15") + " the same file shows " + (prior ? prior.log_return : "—") + "%. No LBMA or spot series is in this build, so this is not confirmed as a cash crash. A futures roll can create a one-day jump, and the January 2026 monthly return includes that session. The next two closes were " + (top.next_closes || []).join(", ") + "."
    : "核对： " + top.date + " 的 GC=F 从 " + top.prev_close + " 收到 " + top.close + "，对数收益 " + top.log_return + "%；同文件里 " + (prior ? prior.date : "2013-04-15") + " 是 " + (prior ? prior.log_return : "—") + "%。这次没有配上 LBMA 或现货，不能写成现货崩盘。连续合约换月可能造成单日跳变，2026 年 1 月的月度收益包含这一天。随后两个收盘是 " + (top.next_closes || []).join("、") + "。";
}
function readUrl() {
  const q = new URLSearchParams(location.search);
  const lang = q.get("lang");
  if (lang === "en" || lang === "zh") state.lang = lang;
  const width = Number(q.get("w"));
  if ([6, 12, 24].includes(width)) state.width = width;
  const sessions = Number(q.get("d"));
  if ([20, 40, 60].includes(sessions)) state.sessions = sessions;
  const id = q.get("e");
  if (id && LAB.events.some(event => event.id === id)) state.eventId = id;
}
function writeUrl() {
  const q = new URLSearchParams();
  if (LAB.events.some(event => event.id === state.eventId)) q.set("e", state.eventId);
  q.set("w", String(state.width));
  q.set("d", String(state.sessions));
  if (state.lang === "en") q.set("lang", "en");
  const next = "?" + q.toString();
  if (location.search !== next) history.replaceState(null, "", next);
}
function irfView() {
  const lp = LAB.var && LAB.var.lp;
  if (!lp || state.irf === "var") return null;
  if (state.irf === "state-high") return lp.state && lp.state.high;
  if (state.irf === "state-low") return lp.state && lp.state.low;
  if (state.irf === "act") return lp.act;
  if (state.irf === "threat") return lp.threat;
  return lp.total || lp;
}
function drawCar(event) {
  const car = LAB.car && LAB.car.by_event && LAB.car.by_event[event.id];
  const en = state.lang === "en";
  const headers = en ? ["Asset", "[-1,+5]", "[-1,+20]", "[0,+40]"] : ["资产", "[-1,+5]", "[-1,+20]", "[0,+40]"];
  if (!car) {
    fillSimpleTable("car-table", en ? "CAR is reported for the built-in events." : "累计异常收益只对内置事件计算。", headers, []);
    return;
  }
  const windows = ["m1_p5", "m1_p20", "p0_p40"];
  const rows = PRICE_IDS.map(name => {
    const asset = car[name] || {};
    return [NAMES[name]].concat(windows.map(key => {
      const cell = asset[key];
      if (!cell) return "—";
      const q = cell.q == null ? "" : " q=" + Number(cell.q).toFixed(2);
      return Number(cell.car).toFixed(2) + " (t=" + Number(cell.t).toFixed(2) + q + ")";
    }));
  });
  fillSimpleTable("car-table", en ? "CAR in percentage points. q is the Benjamini-Hochberg value." : "单位是百分点。q 是 Benjamini–Hochberg 校正值。", headers, rows);
}
function verifyCheck() {
  const path = indexedPath(dailyPack("gold"), LAB.meta.check.date, 60, "pre");
  if (!path) return;
  const at = path.tau.indexOf(LAB.meta.check.tau);
  const got = path.value[at];
  const ok = Math.abs(got - LAB.meta.check.gold) < 0.05;
  document.body.dataset.check = ok ? "ok" : "fail";
  document.body.dataset.goldTau = String(got);
}

function seg(host, values, current, onPick) {
  host.innerHTML = "";
  values.forEach(item => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label;
    button.setAttribute("aria-pressed", String(item.value === current));
    button.addEventListener("click", () => onPick(item.value));
    host.appendChild(button);
  });
}
function boot() {
  try {
    const savedLang = localStorage.getItem("gpr-haven-lang");
    if (savedLang === "en" || savedLang === "zh") state.lang = savedLang;
  } catch (err) {}
  readUrl();
  Object.assign(NAMES, state.lang === "en" ? NAMES_EN : NAMES_ZH);
  state.spec = loadSpec();
  state.spec.events = state.spec.events.filter(event => monthHasAfter(event.month) && sessionAfter(event.date));
  document.getElementById("lede").textContent = "月度样本 " + LAB.meta.sample_start + " 至 " + LAB.meta.sample_end + "，共 " + LAB.meta.n_months + " 个月。先选一个经典事件，再看价格路径、相关差和避险强度。";
  const dateInput = document.getElementById("ev-date");
  const prevMonth = LAB.months[LAB.months.length - 2] || LAB.meta.sample_start;
  dateInput.min = LAB.meta.sample_start + "-01";
  dateInput.max = prevMonth + "-28";
  const select = document.getElementById("event");
  select.addEventListener("change", () => { state.eventId = select.value; render(); });
  document.getElementById("ev-add").addEventListener("click", () => {
    const name = document.getElementById("ev-name").value.trim();
    const date = document.getElementById("ev-date").value;
    const note = document.getElementById("ev-note").value.trim();
    const msg = document.getElementById("ev-msg");
    if (!name || !date) { msg.textContent = "名称和日期都要填。例：名称「俄乌冲突全面升级」，日期 2022-02-24。"; return; }
    if (name.length < 2) { msg.textContent = "名称至少两个字。"; return; }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) { msg.textContent = "日期要是 YYYY-MM-DD。"; return; }
    const month = date.slice(0, 7);
    const en = state.lang === "en";
    if (!LAB.months.includes(month)) {
      msg.textContent = en
        ? "That month is outside the sample (" + LAB.meta.sample_start + " to " + LAB.meta.sample_end + ")."
        : "这个月不在样本里（" + LAB.meta.sample_start + " 至 " + LAB.meta.sample_end + "）。";
      return;
    }
    if (!monthHasAfter(month) || !sessionAfter(date)) {
      msg.textContent = en
        ? "This date has no post-event month. The sample ends in " + LAB.meta.sample_end + ", so 2026-09-28 is rejected. Pick an earlier date."
        : "这个日期后面没有事后月份。样本止于 " + LAB.meta.sample_end + "，所以 2026-09-28 这种末尾日期不会加入，否则图没有事后数据。请换早一些的日期。";
      return;
    }
    const id = "custom-" + Date.now();
    state.spec.events.push({id, name, date, month, group:"自定事件", note: note || "页面上自定的事件。"});
    state.eventId = id;
    msg.textContent = "已加入「" + name + "」（" + date + "）。它出现在上方事件列表，并已切换过去。";
    document.getElementById("ev-name").value = "";
    document.getElementById("ev-note").value = "";
    saveSpec();
    render();
  });
  document.getElementById("reset-spec").addEventListener("click", () => {
    const events = state.spec.events.slice();
    state.spec = defaultSpec();
    state.spec.events = events;
    state.eventId = "hormuz_2026";
    state.width = 12;
    state.sessions = 40;
    state.overlay = [];
    state.sort = "time";
    state.base = "event";
    saveSpec();
    refreshVariableControls();
    render();
  });
  bindVariableControls();
  const sessionsHost = document.getElementById("seg-sessions");
  const widthHost = document.getElementById("seg-width");
  const irfHost = document.getElementById("seg-irf");
  const paintSeg = () => {
    const en = state.lang === "en";
    seg(sessionsHost, [{value:20,label:en?"20d":"20日"},{value:40,label:en?"40d":"40日"},{value:60,label:en?"60d":"60日"}], state.sessions, value => { state.sessions = value; render(); });
    seg(widthHost, [{value:6,label:en?"6 months":"6个月"},{value:12,label:en?"12 months":"12个月"},{value:24,label:en?"24 months":"24个月"}], state.width, value => { state.width = value; render(); });
    if (irfHost) {
      seg(irfHost, [
        {value:"var", label:en?"VAR":"VAR"},
        {value:"lp", label:en?"LP":"局部投影"},
        {value:"act", label:en?"Acts":"行动"},
        {value:"threat", label:en?"Threats":"威胁"},
        {value:"state-high", label:en?"High GPR":"高压"},
        {value:"state-low", label:en?"Calm":"非高压"},
      ], state.irf, value => { state.irf = value; window.__heavy = true; drawIrf(); });
    }
  };
  const oldRender = render;
  render = function () {
    const busy = document.getElementById("busy");
    busy.hidden = false;
    requestAnimationFrame(() => {
      paintSeg();
      fillEvents();
      paintEventList();
      oldRender();
      busy.hidden = true;
    });
  };
  document.getElementById("dl-path").addEventListener("click", () => download("path", "event_path.svg"));
  document.getElementById("dl-path-png").addEventListener("click", () => downloadPng("path", "event_path.png"));
  document.getElementById("dl-gpr").addEventListener("click", () => download("gpr", "event_gpr.svg"));
  document.getElementById("dl-gpr-png").addEventListener("click", () => downloadPng("gpr", "event_gpr.png"));
  document.getElementById("dl-corr").addEventListener("click", () => download("corr", "event_corr.svg"));
  document.getElementById("dl-corr-png").addEventListener("click", () => downloadPng("corr", "event_corr.png"));
  document.getElementById("dl-haven").addEventListener("click", () => download("haven", "haven_regime.svg"));
  document.getElementById("dl-haven-png").addEventListener("click", () => downloadPng("haven", "haven_regime.png"));
  document.getElementById("dl-heat").addEventListener("click", () => download("heat", "rolling_corr.svg"));
  document.getElementById("dl-heat-png").addEventListener("click", () => downloadPng("heat", "rolling_corr.png"));
  document.getElementById("dl-compare").addEventListener("click", () => download("compare", "event_compare.svg"));
  document.getElementById("dl-compare-png").addEventListener("click", () => downloadPng("compare", "event_compare.png"));
  document.getElementById("dl-csv").addEventListener("click", downloadEventCsv);
  document.getElementById("base-event").addEventListener("click", () => { state.base = "event"; render(); });
  document.getElementById("base-pre").addEventListener("click", () => { state.base = "pre"; render(); });
  document.getElementById("dl-caption").addEventListener("click", () => {
    const text = figureCaption();
    const out = document.getElementById("caption-out");
    out.textContent = text;
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(() => { out.textContent = "已复制。 " + text; }).catch(() => {});
  });
  ["brent", "dxy", "csi", "hsi"].forEach(id => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost";
    button.style.marginLeft = "0";
    button.dataset.quick = id;
    button.textContent = NAMES[id];
    button.addEventListener("click", () => {
      if (id === state.spec.anchor) return;
      state.spec.path = state.spec.path.includes(id) ? state.spec.path.filter(item => item !== id) : state.spec.path.concat([id]);
      if (!state.spec.path.includes(state.spec.anchor)) state.spec.path.push(state.spec.anchor);
      saveSpec();
      refreshVariableControls();
      render();
    });
    document.getElementById("quick-assets").appendChild(button);
  });
  [{id:"time", label:"按时间"}, {id:"excess", label:"按相对表现"}, {id:"haven", label:"按避险强度"}].forEach(item => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost";
    button.style.marginLeft = "0";
    button.dataset.sort = item.id;
    button.textContent = item.label;
    button.addEventListener("click", () => { state.sort = item.id; render(); });
    document.getElementById("compare-sort").appendChild(button);
  });
  document.getElementById("dl-irf").addEventListener("click", () => {
    if (!document.querySelector("#irf svg")) {
      window.__heavy = true;
      drawIrf();
    }
    if (!document.querySelector("#irf svg")) {
      const status = document.getElementById("dl-status");
      if (status) status.textContent = state.lang === "en"
        ? "The impulse-response chart is not drawn yet, so there is no SVG to download. Scroll to that section and try again."
        : "脉冲响应图还没画出来，没有可下载的 SVG。请先滚到这一节，再点一次。";
      return;
    }
    const status = document.getElementById("dl-status");
    if (status) status.textContent = "";
    downloadGrid("irf", "var_irf_gpr.svg", 3, 280, 160);
  });
  document.getElementById("copy-link").addEventListener("click", () => {
    writeUrl();
    const status = document.getElementById("dl-status");
    const text = location.href;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        if (status) status.textContent = state.lang === "en" ? "Link copied." : "链接已复制。";
      }).catch(() => { if (status) status.textContent = text; });
    } else if (status) status.textContent = text;
  });
  document.getElementById("foot").textContent = "GPR：Caldara–Iacoviello 日度 GPRD 的月均值。黄金 GC=F、布伦特 BZ=F、美元指数 DX-Y.NYB、恒生 ^HSI 来自 Yahoo Finance。沪深300是新浪 sh000300。";
  document.getElementById("lang").addEventListener("click", () => {
    state.lang = state.lang === "en" ? "zh" : "en";
    try { localStorage.setItem("gpr-haven-lang", state.lang); } catch (err) {}
    render();
  });
  const presetHost = document.getElementById("var-presets");
  [
    ["论文顺序", "Paper order", ["dgpr","brent","dxy","gold","csi","hsi"]],
    ["油价在前", "Oil first", ["brent","dgpr","dxy","gold","csi","hsi"]],
    ["黄金在前", "Gold first", ["gold","dgpr","brent","dxy","csi","hsi"]],
  ].forEach(([zh, en, order]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost";
    button.style.marginLeft = "0";
    button.dataset.en = en;
    button.textContent = zh;
    button.addEventListener("click", () => {
      state.spec.varOn = order.slice();
      saveSpec();
      refreshVariableControls();
      render();
    });
    presetHost.appendChild(button);
  });
  const scenes = document.getElementById("scenes");
  SCENES.forEach(scene => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost";
    button.style.marginLeft = "0";
    button.textContent = scene.label;
    button.addEventListener("click", () => { state.eventId = scene.id; render(); });
    scenes.appendChild(button);
  });
  render();
}

let eventSig = "";
function fillEvents() {
  const events = allEvents();
  const sig = state.lang + "|" + events.map(item => item.id).join("|");
  const select = document.getElementById("event");
  if (sig !== eventSig) {
    select.innerHTML = "";
    [["海峡与石油", "Strait and oil"], ["制裁", "Sanctions"], ["冲突升级", "Escalation"], ["其他", "Other"], ["自定事件", "Custom"]].forEach(([group, groupEn]) => {
      const members = events.filter(item => item.group === group);
      if (!members.length) return;
      const optgroup = document.createElement("optgroup");
      optgroup.label = state.lang === "en" ? groupEn : group;
      members.forEach(event => {
        const option = document.createElement("option");
        option.value = event.id;
        option.textContent = event.date.slice(0, 7) + "  " + eventTitle(event);
        optgroup.appendChild(option);
      });
      select.appendChild(optgroup);
    });
    eventSig = sig;
  }
  if ([...select.options].some(option => option.value === state.eventId)) select.value = state.eventId;
}
function paintEventList() {
  const host = document.getElementById("ev-list");
  host.innerHTML = "";
  if (!state.spec.events.length) {
    host.innerHTML = "<p class='note'>" + (state.lang === "en" ? "No custom events yet." : "还没有自定事件。") + "</p>";
    return;
  }
  state.spec.events.forEach(event => {
    const row = document.createElement("div");
    row.className = "ev-item";
    const text = document.createElement("button");
    text.type = "button";
    text.className = "ghost mini";
    text.style.marginLeft = "0";
    text.textContent = event.date + "  " + eventTitle(event);
    text.addEventListener("click", () => { state.eventId = event.id; render(); });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost mini";
    remove.textContent = "删除";
    remove.addEventListener("click", () => {
      state.spec.events = state.spec.events.filter(item => item.id !== event.id);
      if (state.eventId === event.id) state.eventId = "hormuz_2026";
      saveSpec();
      render();
    });
    row.append(text, remove);
    host.appendChild(row);
  });
}
function moveVar(id, dir) {
  const list = state.spec.varOn.slice();
  const index = list.indexOf(id);
  const next = index + dir;
  if (index < 0 || next < 0 || next >= list.length) return;
  const hold = list[index];
  list[index] = list[next];
  list[next] = hold;
  state.spec.varOn = list;
  saveSpec();
  refreshVariableControls();
  render();
}
function refreshVariableControls() {
  document.getElementById("anchor").value = state.spec.anchor;
  document.querySelectorAll("[data-path]").forEach(box => {
    box.checked = state.spec.path.includes(box.dataset.path);
    box.disabled = box.dataset.path === state.spec.anchor;
  });
  document.querySelectorAll("[data-score]").forEach(select => {
    const item = state.spec.score.find(entry => entry.id === select.dataset.score);
    const blocked = select.dataset.score === state.spec.anchor;
    select.value = blocked ? "off" : item.role;
    select.disabled = blocked;
  });
  const host = document.getElementById("var-order");
  host.innerHTML = "";
  const ordered = state.spec.varOn.concat(VAR_IDS.filter(id => !state.spec.varOn.includes(id)));
  ordered.forEach(id => {
    const row = document.createElement("div");
    row.className = "var-row";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = "var-" + id;
    box.checked = state.spec.varOn.includes(id);
    box.addEventListener("change", () => {
      if (box.checked) {
        if (!state.spec.varOn.includes(id)) state.spec.varOn = state.spec.varOn.concat([id]);
      } else state.spec.varOn = state.spec.varOn.filter(item => item !== id);
      if (state.spec.varOn.length < 2) {
        box.checked = true;
        if (!state.spec.varOn.includes(id)) state.spec.varOn = state.spec.varOn.concat([id]);
        return;
      }
      saveSpec();
      refreshVariableControls();
      render();
    });
    const name = document.createElement("label");
    name.htmlFor = box.id;
    name.textContent = NAMES[id] + (state.spec.varOn[0] === id ? (state.lang === "en" ? " (shock)" : "（冲击）") : "");
    name.style.minWidth = "92px";
    const up = document.createElement("button");
    up.type = "button";
    up.className = "ghost mini";
    up.textContent = state.lang === "en" ? "Up" : "上移";
    up.disabled = !state.spec.varOn.includes(id);
    up.addEventListener("click", () => moveVar(id, -1));
    const down = document.createElement("button");
    down.type = "button";
    down.className = "ghost mini";
    down.textContent = state.lang === "en" ? "Down" : "下移";
    down.disabled = !state.spec.varOn.includes(id);
    down.addEventListener("click", () => moveVar(id, 1));
    row.append(box, name, up, down);
    host.appendChild(row);
  });
}
function bindVariableControls() {
  const anchor = document.getElementById("anchor");
  PRICE_IDS.forEach(id => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = NAMES[id];
    anchor.appendChild(option);
  });
  anchor.addEventListener("change", () => {
    state.spec.anchor = anchor.value;
    if (!state.spec.path.includes(state.spec.anchor)) state.spec.path.push(state.spec.anchor);
    state.spec.score.forEach(item => { if (item.id === state.spec.anchor) item.role = "off"; });
    saveSpec();
    refreshVariableControls();
    render();
  });
  const pathHost = document.getElementById("path-picks");
  PRICE_IDS.forEach(id => {
    const label = document.createElement("label");
    label.className = "pick";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.dataset.path = id;
    box.addEventListener("change", () => {
      if (id === state.spec.anchor) { box.checked = true; return; }
      state.spec.path = PRICE_IDS.filter(name => {
        const input = document.querySelector("[data-path='" + name + "']");
        return name === state.spec.anchor || input.checked;
      });
      saveSpec();
      render();
    });
    label.append(box, document.createTextNode(NAMES[id]));
    pathHost.appendChild(label);
  });
  const scoreHost = document.getElementById("score-picks");
  SCORE_IDS.forEach(id => {
    const row = document.createElement("div");
    row.className = "pick";
    const name = document.createElement("label");
    name.textContent = NAMES[id];
    name.style.width = "72px";
    const select = document.createElement("select");
    select.id = "score-" + id;
    name.htmlFor = select.id;
    select.dataset.score = id;
    [["off","不纳入"],["watch","对照"],["hedge","对冲"],["comove","同向"]].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });
    select.addEventListener("change", () => {
      const item = state.spec.score.find(entry => entry.id === id);
      item.role = id === state.spec.anchor ? "off" : select.value;
      saveSpec();
      render();
    });
    row.append(name, select);
    scoreHost.appendChild(row);
  });
  refreshVariableControls();
}
async function start() {
  const busy = document.getElementById("busy");
  busy.hidden = false;
  busy.textContent = "正在载入数据…";
  try {
    const monthlyResp = await fetch("lab_data_monthly.json");
    if (monthlyResp.ok) LAB = await monthlyResp.json();
    else LAB = await (await fetch("lab_data.json")).json();
  } catch (err) {
    busy.hidden = false;
    busy.textContent = "没有载入 lab_data_monthly.json / lab_data.json。请打开网站，或在本目录运行本地服务器，不要直接双击 html 文件。";
    return;
  }
  busy.hidden = true;
  boot();
  if (!LAB.daily) {
    fetch("lab_data_daily.json").then(resp => resp.ok ? resp.json() : null).then(extra => {
      if (!extra) return;
      Object.assign(LAB, extra);
      if (state.spec) state.spec.events = state.spec.events.filter(event => monthHasAfter(event.month) && sessionAfter(event.date));
      render();
      verifyCheck();
    }).catch(() => {});
  }
  const watch = new IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting)) return;
    watch.disconnect();
    window.__heavy = true;
    drawHeat(activeEvent(), liveHeat());
    drawIrf();
  }, {rootMargin: "280px"});
  const heat = document.getElementById("heat");
  if (heat) watch.observe(heat);
}
start();
