function drawPhaseC(event) {
  if (typeof LAB === "undefined" || !LAB || !LAB.regime) return;
  try {
    drawStateNow();
    drawAnalogs(event);
    drawRibbon();
    drawTransitions();
    drawValidationBlock();
    drawCrowding(event);
  } catch (err) {
    console.error(err);
  }
}
function cText(zh, en) {
  return state.lang === "en" ? en : zh;
}
const CELL_EN = {
  "高压×紧缩": "High pressure × Tight",
  "高压×中性": "High pressure × Neutral",
  "高压×宽松": "High pressure × Loose",
  "低压×紧缩": "Low pressure × Tight",
  "低压×中性": "Low pressure × Neutral",
  "低压×宽松": "Low pressure × Loose",
};
const DIM_EN = {gpr: "Geopolitical pressure", real_rate: "Real rate", dollar: "Dollar", vix: "Risk aversion"};
function dimLabel(dim) {
  return state.lang === "en" ? (DIM_EN[dim.id] || dim.label) : dim.label;
}
function pressureName(value) {
  if (state.lang !== "en") return value || "";
  if (value === "高压") return "High pressure";
  if (value === "低压") return "Low pressure";
  return value || "";
}
function cellName(cell) {
  if (!cell) return cText("状态不足", "State unavailable");
  return state.lang === "en" ? (CELL_EN[cell] || cell) : cell;
}
function drawStateNow() {
  const label = document.getElementById("state-label");
  const bars = document.getElementById("state-bars");
  const note = document.getElementById("state-note");
  if (!label || !bars) return;
  const timeline = LAB.regime.timeline || [];
  const last = timeline.length ? timeline[timeline.length - 1] : {};
  const prev = timeline.length > 1 ? timeline[timeline.length - 2] : {};
  const name = last.cell
    ? cellName(last.cell)
    : (last.pressure ? pressureName(last.pressure) + cText(" · 松紧不足", " · tightness unavailable") : cText("状态不足", "State unavailable"));
  label.textContent = name + (last.month ? " · " + last.month : "");
  const changed = !!(prev.cell && last.cell && prev.cell !== last.cell);
  const dims = LAB.regime.dimensions || [];
  bars.innerHTML = dims.map(dim => {
    if (dim.status !== "ok" || dim.pct == null) {
      const why = dim.status === "short"
        ? cText("这个月没有读数", "No reading this month")
        : cText("没有这条序列", "Series missing");
      return "<div class='state-row'><span>" + dimLabel(dim) + "</span><span class='note'>" + why + "</span><span></span></div>";
    }
    const pct = Math.round(dim.pct * 100);
    const delta = dim.prev == null ? "" : " (" + (dim.pct - dim.prev >= 0 ? "+" : "") + Math.round((dim.pct - dim.prev) * 100) + ")";
    return "<div class='state-row'><span>" + dimLabel(dim) + "</span><span class='state-meter'><i style='width:" + pct + "%'></i></span><span>" + pct + "%" + delta + "</span></div>";
  }).join("");
  if (note) {
    const shift = !last.cell
      ? ""
      : changed
        ? cText("相对上月，综合标签从 " + cellName(prev.cell) + " 变为 " + cellName(last.cell) + "。", "The label changed from " + cellName(prev.cell) + " last month.")
        : cText("综合标签与上月相同。", "The label is unchanged from the previous month.");
    const missMap = {real_rate: "实际利率", dollar: "美元", vix: "风险厌恶"};
    const missing = (LAB.regime.missing || []).map(id => missMap[id] || id);
    const gap = missing.length
      ? cText("综合松紧没有形成，缺的是" + missing.join("、") + "。色带只区分 GPR 的高压和低压。", "Tightness is blank because " + (LAB.regime.missing || []).join(", ") + " are missing. The ribbon shows GPR pressure only.")
      : "";
    note.textContent = cText(
      "标签用的是截至该月的滚动分位，没有用到之后的数据。样本止于 " + last.month + "，这不是 11 月的实时状态。" + shift + gap,
      "Labels use trailing percentiles through that month. The sample ends at " + last.month + ". " + shift + gap
    );
  }
}
function drawAnalogs(event) {
  const note = document.getElementById("analog-note");
  const list = document.getElementById("analog-list");
  if (!note || !list) return;
  const shown = LAB.regime.latest;
  if (!shown || !shown.ok) {
    note.textContent = cText("这个月还没有足够长的滚动窗，或没有足够早的相似月。", "This month does not yet have a full trailing window or enough earlier months.");
    list.innerHTML = "";
    return;
  }
  const gold = ((shown.forward || {})["3"] || {}).gold || {};
  const used = (shown.features || []).join(", ") || cText("无", "none");
  const permZh = shown.perm_p == null
    ? "合格月份不多于 k，这次没有做置换。"
    : "置换检验比较的是这些月份之后 3 个月黄金收益的四分位距是否比随机月份更窄，p=" + shown.perm_p + "（" + shown.perm_reps + " 次，合格月 n=" + shown.n_eligible + "）。";
  const permEn = shown.perm_p == null
    ? "There are not more eligible months than k, so no permutation was run."
    : "The permutation asks whether the interquartile range of the next 3-month gold return is narrower than a random draw. p=" + shown.perm_p + " (" + shown.perm_reps + " draws, eligible n=" + shown.n_eligible + ").";
  let extraZh = "";
  let extraEn = "";
  const pack = LAB.regime.by_event && event ? LAB.regime.by_event[event.id] : null;
  if (pack && pack.ok) {
    const eventGold = ((pack.forward || {})["3"] || {}).gold || {};
    const eventPerm = pack.perm_p == null ? "这次没有置换检验。" : "置换 p=" + pack.perm_p + "。";
    extraZh = " 档案里的 " + pack.month + " 另有 " + pack.k + " 个相似月（" + pack.indep_runs + " 个独立区间，维度 " + (pack.features || []).join(", ") + "）。" + eventPerm + "其后 3 个月黄金 10/50/90 分位是 " + eventGold.p10 + " / " + eventGold.p50 + " / " + eventGold.p90 + "（n=" + eventGold.n + "）。";
    extraEn = " The archived month " + pack.month + " has " + pack.k + " similar months (" + pack.indep_runs + " runs). Next 3-month gold 10/50/90: " + eventGold.p10 + " / " + eventGold.p50 + " / " + eventGold.p90 + " (n=" + eventGold.n + ").";
  } else if (pack && !pack.ok) {
    extraZh = " 当前档案事件没有凑满滚动窗，没有相似月。";
    extraEn = " The archived event does not have a full trailing window, so it has no analogs.";
  }
  note.textContent = cText(
    "样本月末 " + shown.month + " 有 " + shown.k + " 个相似月（对应 " + shown.indep_runs + " 个独立区间），用到的维度是 " + used + "。" + permZh + "其后 3 个月黄金累计收益的 10/50/90 分位是 " + gold.p10 + " / " + gold.p50 + " / " + gold.p90 + "（n=" + gold.n + "）。" + extraZh,
    "Sample-end month " + shown.month + " has " + shown.k + " similar months (" + shown.indep_runs + " independent runs), using " + used + ". " + permEn + " The 10/50/90 percentiles are " + gold.p10 + " / " + gold.p50 + " / " + gold.p90 + " (n=" + gold.n + ")." + extraEn
  );
  const neighbors = shown.neighbors || [];
  list.innerHTML = "<p class='note'>" + neighbors.join(" · ") + "</p>";
}
function ribbonColor(row) {
  const cell = row.cell || "";
  if (cell.indexOf("高压") === 0 && cell.indexOf("紧缩") > 0) return "#d55e00";
  if (cell.indexOf("高压") === 0 || row.pressure === "高压") return "#c48a00";
  if (cell.indexOf("紧缩") > 0) return "#1f4b73";
  if (row.pressure === "低压") return "#d9d3c7";
  return "#eeeae2";
}
function drawRibbon() {
  const host = document.getElementById("regime-ribbon");
  if (!host) return;
  host.innerHTML = (LAB.regime.timeline || []).map(row => {
    const title = row.month + " " + (row.cell || row.pressure || "");
    return "<i title='" + title + "' style='background:" + ribbonColor(row) + "'></i>";
  }).join("");
}
function drawTransitions() {
  const host = document.getElementById("transition-table");
  const note = document.getElementById("transition-note");
  const matrix = LAB.regime.transitions;
  if (!host || !matrix) return;
  const labels = matrix.labels || [];
  const counts = matrix.counts || [];
  let html = "<table><tr><th></th>" + labels.map(label => "<th>" + label + "</th>").join("") + "</tr>";
  labels.forEach((label, i) => {
    const row = counts[i] || [];
    const total = row.reduce((sum, value) => sum + value, 0);
    html += "<tr><th>" + label + " (n=" + total + ")</th>" + row.map(value => "<td>" + value + "</td>").join("") + "</tr>";
  });
  host.innerHTML = html + "</table>";
  if (note) note.textContent = matrix.note || "";
}
function drawValidationBlock() {
  const host = document.getElementById("validation-body");
  if (!host || !LAB.validation) return;
  const gates = LAB.validation.gates || {};
  const bases = LAB.validation.baselines || {};
  const lines = Object.keys(bases).map(name => {
    const item = bases[name] || {};
    const improvement = item.improvement == null ? "—" : Math.round(item.improvement * 1000) / 10 + "%";
    const p = item.dm && item.dm.p != null ? item.dm.p : "—";
    const n = item.n == null ? "—" : item.n;
    return "<tr><td>" + name + "</td><td>" + improvement + "</td><td>" + p + "</td><td>n=" + n + "</td></tr>";
  }).join("");
  const model = LAB.validation.model || {};
  const verdict = LAB.validation.declare_no_skill
    ? (LAB.validation.negative_template || "")
    : cText("预先写下的通过门槛这次没有被否定。前瞻记录仍要积累满 12 个月才对外说预测成绩。", "The pre-written bar was not rejected. Prospective scores stay unpublished until 12 months of ledger entries exist.");
  host.innerHTML = "<p>" + verdict + "</p><p class='note'>pinball " + model.pinball + " · PIT p=" + model.pit_ks_p + " · 80% 覆盖 " + model.coverage_80 + " · n=" + model.n + "</p><table><tr><th></th><th>改善</th><th>DM p</th><th></th></tr>" + lines + "</table><p class='note'>" + cText("改善为负表示模型比该基线更差。DM 的 p 小只说明两边的损失不一样，不表示模型更好。", "A negative improvement means the model loses to that baseline. A small DM p means the losses differ; it does not mean the model is better.") + " pass=" + gates.pass + "</p>";
}
function drawCrowding(event) {
  const note = document.getElementById("crowding-note");
  if (!note) return;
  const pack = LAB.crowding || {};
  if (pack.status !== "ok") {
    note.textContent = pack.note || cText("拥挤度还没有序列。", "Crowding is not available.");
    return;
  }
  const value = pack.by_event && event ? pack.by_event[event.id] : null;
  const shown = value == null ? "—" : Math.round(value * 100) + "%";
  const split = pack.high_gpr || {};
  const down = split.gold_down_n == null ? "—" : split.gold_down_n;
  const both = split.gold_down_and_crowded_n == null ? "—" : split.gold_down_and_crowded_n;
  note.textContent = cText(
    "当前事件月的 CFTC 分位是 " + shown + "。样本内最新值 " + (pack.latest == null ? "—" : Math.round(pack.latest * 100) + "%") + "（止于 " + pack.end + "）。" + (pack.note || "") + " GPR 高压月里，其后 3 个月黄金下跌的有 " + down + " 个月，其中 CFTC 分位不低于 90% 的有 " + both + " 个。",
    "CFTC percentile in the selected event month is " + shown + ". Latest " + pack.latest + " through " + pack.end + ". This is the trailing 60-month percentile of non-commercial net length over open interest, not a two-leg crowding index. High-GPR months with a negative next 3-month gold return: " + down + ", of which " + both + " had a CFTC percentile of at least 90."
  );
  const table = document.getElementById("crowding-table");
  if (!table) return;
  const rows = (LAB.events || []).map(item => {
    const cell = pack.by_event ? pack.by_event[item.id] : null;
    const text = cell == null ? "—" : Math.round(cell * 100) + "%";
    const current = event && item.id === event.id ? " class='is-current'" : "";
    const name = state.lang === "en" ? (item.name_en || item.name) : item.name;
    return "<tr" + current + "><td>" + name + "</td><td>" + item.date + "</td><td>60 个月窗 · " + text + "</td></tr>";
  }).join("");
  table.innerHTML = "<table><tr><th>" + cText("事件", "Event") + "</th><th>" + cText("月份", "Month") + "</th><th>" + cText("CFTC 分位", "CFTC percentile") + "</th></tr>" + rows + "</table>";
}
