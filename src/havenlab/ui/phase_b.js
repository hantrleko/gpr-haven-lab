function phaseText(zh, en) {
  return state.lang === "en" ? en : zh;
}
function nullBand(event) {
  const pack = LAB.placebo_v2 && LAB.placebo_v2[String(state.width)];
  const row = pack && pack.by_event && pack.by_event[event.id];
  if (!row || !row.gold) return null;
  if (!row.gold.blocked && row.blocked) row.gold.blocked = row.blocked;
  return row.gold;
}
function specIsExploratory() {
  if (!state.spec || state.spec.anchor !== "gold") return true;
  if (state.width !== 12 || state.sessions !== 40 || state.base !== "event") return true;
  if (state.spec.events && state.spec.events.length) return true;
  return !isPresetScore();
}
function drawPhaseB(event, stats) {
  try {
    drawNull(event);
    drawHavenVersions(event);
    drawDownside(event);
    drawConditional();
    drawDailyQuantile();
    drawSpecCurve(event);
    drawMacroStatus();
    const warn = document.getElementById("source-warn");
    if (warn) {
      const on = LAB.meta && LAB.meta.degraded;
      warn.hidden = !on;
      if (on) warn.textContent = phaseText("数据源异常，本次仅重建图表。", "A source failed. This build only redrew the charts.");
    }
  } catch (err) {
    console.error(err);
  }
}
function drawNull(event) {
  const host = document.getElementById("null-chart");
  const note = document.getElementById("null-note");
  if (!host) return;
  const pack = LAB.placebo_v2 && LAB.placebo_v2[String(state.width)];
  const band = nullBand(event);
  if (!pack || !pack.null || !pack.null.gold || !band) {
    host.innerHTML = "";
    if (note) {
      note.textContent = pack
        ? phaseText("这个窗口超出样本末端，不把更短的累计放进 " + state.width + " 个月的零分布。", "This window runs off the sample, so it is not placed on the " + state.width + "-month null.")
        : "";
    }
    return;
  }
  const hist = pack.null.gold;
  const mids = [];
  for (let i = 0; i < hist.counts.length; i++) mids.push((hist.edges[i] + hist.edges[i + 1]) / 2);
  drawChart(host, {
    title: phaseText("零分布", "Null"),
    height: 220,
    series: [{x: mids, y: hist.counts, color: "#1f4b73"}],
    mark: band.value,
    markLabel: phaseText("本次", "now"),
    yDigits: 0,
  });
  const blocked = band.blocked || {};
  if (note) {
    note.textContent = phaseText(
      "bootstrap 分位 " + pctText(band) + "，n=" + band.n_reps + "，block=" + pack.block + "。留出对照 " + (blocked.pct == null ? "—" : Math.round(100 * blocked.pct) + "%") + "（n=" + (blocked.n == null ? "—" : blocked.n) + "）。",
      "Bootstrap percentile " + pctText(band) + ", n=" + band.n_reps + ", block=" + pack.block + ". Leave-out column " + (blocked.pct == null ? "—" : Math.round(100 * blocked.pct) + "%") + " (n=" + (blocked.n == null ? "—" : blocked.n) + ")."
    );
  }
}
function pctText(band) {
  if (!band || band.pct == null) return "—";
  return Math.round(100 * band.pct) + "% [" + Math.round(100 * band.pct_lo) + "%, " + Math.round(100 * band.pct_hi) + "%]";
}
function drawHavenVersions(event) {
  const host = document.getElementById("haven-versions");
  if (!host || !LAB.haven_versions) return;
  const slot = LAB.haven_versions.events && LAB.haven_versions.events[event.id] && LAB.haven_versions.events[event.id][String(state.width)];
  const rows = [];
  if (slot) {
    rows.push(["v1", slot.haven, "headline"]);
    rows.push(["v1_z", slot.haven1_z, "Fisher z"]);
    rows.push(["v2", slot.haven2, slot.haven2_window || "60m"]);
  }
  host.innerHTML = "<table><thead><tr><th>version</th><th>score</th><th>note</th></tr></thead><tbody>"
    + rows.map(row => "<tr><td>" + row[0] + "</td><td>" + (row[1] == null ? "—" : row[1]) + "</td><td>" + row[2] + "</td></tr>").join("")
    + "</tbody></table><p class='note'>" + phaseText("头条仍是 v1。v2 要等 specification curve 的跨设定方差明显更小，才在下一阶段提议更换。", "The headline stays v1. haven2 is not promoted in this release.") + "</p>";
}
function drawDownside(event) {
  const host = document.getElementById("downside-chart");
  if (!host || !LAB.haven_versions || !LAB.haven_versions.beta_csi) return;
  const x = LAB.months.map((_, i) => i);
  const mark = LAB.months.indexOf(event.month);
  drawChart(host, {
    title: phaseText("下行 beta", "Downside beta"),
    height: 240,
    ref: 0,
    mark: mark,
    series: [
      {x: x, y: LAB.haven_versions.beta_csi, color: "#0072b2"},
      {x: x, y: LAB.haven_versions.beta_hsi, color: "#d55e00"},
      {x: x, y: LAB.haven_versions.beta_dxy, color: "#007a5a"},
    ],
    yDigits: 2,
  });
}
function drawConditional() {
  const host = document.getElementById("conditional");
  if (!host || !LAB.conditional || !LAB.conditional.states) return;
  host.innerHTML = "";
  LAB.conditional.states.forEach(stateRow => {
    const row = document.createElement("div");
    row.className = "cond-row";
    const title = document.createElement("h3");
    title.textContent = stateRow.id + "  n_high=" + stateRow.n_high + "  n_low=" + stateRow.n_low;
    row.appendChild(title);
    const grid = document.createElement("div");
    grid.className = "cond-grid";
    Object.keys(stateRow.assets || {}).forEach(key => {
      const cell = document.createElement("div");
      cell.className = "chart-host";
      const asset = stateRow.assets[key];
      const x = asset.low.map((_, i) => i);
      drawChart(cell, {
        title: key,
        width: 280,
        height: 140,
        margin: {l: 36, r: 8, t: 16, b: 22},
        includeZero: true,
        series: [
          {x: x, y: asset.low, color: "#1f4b73"},
          {x: x, y: asset.high, color: "#d55e00"},
        ],
        yDigits: 2,
      });
      grid.appendChild(cell);
    });
    row.appendChild(grid);
    host.appendChild(row);
  });
}
function conditionalCsv() {
  const lines = ["state,asset,horizon,low,high,interaction,p"];
  (LAB.conditional && LAB.conditional.states || []).forEach(stateRow => {
    Object.keys(stateRow.assets || {}).forEach(key => {
      const asset = stateRow.assets[key];
      asset.low.forEach((_, i) => {
        lines.push([stateRow.id, key, i, asset.low[i], asset.high[i], asset.interaction[i], asset.p[i]].join(","));
      });
    });
  });
  const blob = new Blob([lines.join("\n")], {type: "text/csv"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "conditional_response.csv";
  link.click();
}
function drawDailyQuantile() {
  const host = document.getElementById("daily-q");
  const pack = LAB.daily_quantile;
  if (!host || !pack || !pack.grid) return;
  const x = pack.grid;
  drawChart(host, {
    title: phaseText("日度分位", "Daily quantiles"),
    height: 240,
    series: [
      {x: x, y: pack.curves["0.05"], color: "#0072b2"},
      {x: x, y: pack.curves["0.50"], color: "#1c1915"},
      {x: x, y: pack.curves["0.95"], color: "#d55e00"},
    ],
    yDigits: 2,
  });
}
function drawSpecCurve(event) {
  const host = document.getElementById("spec-curve");
  const note = document.getElementById("spec-note");
  const curve = LAB.spec_curve;
  if (!host || !curve || !curve.by_event || !curve.by_event[event.id]) return;
  const row = curve.by_event[event.id];
  const values = (row.estimates || []).filter(item => item != null).slice().sort((a, b) => a - b);
  const n = values.length;
  const loCut = values.length ? values[Math.max(0, Math.floor(n * 0.2) - 1)] : null;
  const hiCut = values.length ? values[Math.min(n - 1, Math.floor(n * 0.8))] : null;
  const low = [], mid = [], high = [];
  values.forEach((value, index) => {
    const x = index + 1;
    low.push(value <= loCut ? value : null);
    mid.push(value > loCut && value < hiCut ? value : null);
    high.push(value >= hiCut ? value : null);
    void x;
  });
  const xs = values.map((_, index) => index + 1);
  drawChart(host, {
    title: "spec",
    height: 240,
    series: [
      {x: xs, y: low, color: "#0072b2", width: 2},
      {x: xs, y: mid, color: "#8a8478", width: 2},
      {x: xs, y: high, color: "#d55e00", width: 2},
    ],
    yDigits: 1,
  });
  if (note) {
    const gates = (curve.gate_sensitivity || []).map(item => item.low + "/" + item.high + ": " + item.n_pass).join(" · ");
    const specs = curve.specs || [];
    const idx = specs.findIndex(spec => spec.w === state.width && spec.base === state.base && spec.sessions === state.sessions && spec.weights === "equal" && spec.gpr === "total" && spec.null === "bootstrap");
    let mine = null;
    if (idx >= 0 && row.estimates[idx] != null && values.length) {
      mine = values.filter(item => item <= row.estimates[idx]).length / values.length;
    }
    const where = mine == null ? "" : phaseText("你的设定落在曲线第 " + Math.round(100 * mine) + " 百分位。", "Your setting is at percentile " + Math.round(100 * mine) + ". ");
    note.textContent = where + phaseText(
      "估计 " + n + " 个。中位数 " + row.median + "。默认设定的百分位 " + (row.pctl_of_default == null ? "—" : Math.round(100 * row.pctl_of_default)) + "。门槛敏感性 " + gates + "。registry " + curve.registry_hash + "。",
      n + " estimates. Median " + row.median + ". Default-spec percentile " + (row.pctl_of_default == null ? "—" : Math.round(100 * row.pctl_of_default)) + ". Gate counts " + gates + ". registry " + curve.registry_hash + "."
    );
  }
}
function drawMacroStatus() {
  const host = document.getElementById("macro-status");
  if (!host || !LAB.macro_status) return;
  const rows = Object.keys(LAB.macro_status).map(key => {
    const item = LAB.macro_status[key];
    return "<tr><td>" + key + "</td><td>" + (item.id || "") + "</td><td>" + (item.status || "") + "</td><td>" + (item.in_model ? "yes" : "no") + "</td><td>" + (item.note || item.start || "") + "</td></tr>";
  });
  host.innerHTML = "<table><tbody>" + rows.join("") + "</tbody></table>";
}
document.addEventListener("click", event => {
  const button = event.target.closest("#dl-conditional");
  if (button) conditionalCsv();
});
