// EF Lab v3 report page — state, URL routing and render orchestration.
// All report text comes from report_v3 outputs; this file only wires UI.

import { V3Data } from "./data.js";
import { t } from "./i18n.js";
import { monthlyGpr } from "./stripes.js";
import { buildReport } from "./report.js";
import { renderAll, esc } from "./render.js";

const MIN_DATE = "2008-01-01";

const els = {
  hero: document.getElementById("hero"),
  stripes: document.getElementById("stripes"),
  pressure: document.getElementById("sec-pressure"),
  havens: document.getElementById("sec-havens"),
  history: document.getElementById("sec-history"),
  evidence: document.getElementById("sec-evidence"),
  caveats: document.getElementById("sec-caveats"),
  footer: document.getElementById("site-footer"),
  rail: document.getElementById("rail"),
  dateInput: document.getElementById("date-input"),
  eventSelect: document.getElementById("event-select"),
  benchSelect: document.getElementById("bench-select"),
  langBtns: [...document.querySelectorAll("[data-lang]")],
  dateMsg: document.getElementById("date-msg"),
  fatal: document.getElementById("fatal"),
};

const state = {
  lang: "zh",
  mode: "latest", // latest | preset | custom
  eventId: null,
  date: null,
  bench: "spx",
  data: null,
  report: null,
  months: null,
  dateError: null,
  seriesFailed: false,
};

const view = {
  data: null,
  state,
  els,
  get report() { return state.report; },
  get rep() { return state.report; },
  get months() { return state.months; },
  get lang() { return state.lang; },
  get bench() { return state.bench; },
  get seriesFailed() { return state.seriesFailed; },
  get rules() { return state.data ? state.data.rules : null; },
};

// ------------------------------------------------------------ url <-> state

function presetForDate(dateStr) {
  if (!state.data) return null;
  return state.data.eventList.find((e) => e.date === dateStr) || null;
}

function resolveFromUrl() {
  const params = new URLSearchParams(location.search);
  state.lang = params.get("lang") === "en" ? "en" : "zh";
  const b = params.get("b");
  if (state.data && state.data.benches.includes(b)) state.bench = b;
  const d = params.get("d");
  if (!d) {
    state.mode = "latest";
    state.eventId = null;
    state.date = null;
    state.dateError = null;
    return;
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) {
    state.mode = "latest";
    state.eventId = null;
    state.date = null;
    state.dateError = t(state.lang, "err_invalid");
    return;
  }
  const preset = presetForDate(d);
  if (preset) {
    state.mode = "preset";
    state.eventId = preset.id;
    state.date = d;
    state.dateError = null;
    return;
  }
  state.mode = "custom";
  state.eventId = null;
  state.date = d;
  state.dateError = null;
}

function syncUrl(replace = false) {
  const params = new URLSearchParams();
  if (state.mode !== "latest") params.set("d", state.date);
  if (state.bench !== "spx") params.set("b", state.bench);
  if (state.lang !== "zh") params.set("lang", state.lang);
  const qs = params.toString();
  const url = location.pathname + (qs ? "?" + qs : "");
  if (replace) history.replaceState(null, "", url);
  else history.pushState(null, "", url);
}

// --------------------------------------------------------------- reporting

function currentReport() {
  const data = state.data;
  if (!data || !data.reports) return null;
  if (state.mode === "latest") return data.reports.latest[state.bench] || null;
  if (state.mode === "preset") {
    const perBench = data.reports.events[state.eventId];
    return perBench ? perBench[state.bench] || null : null;
  }
  if (!data.decoded) return null; // series still loading
  return buildReport(data.decoded, data.rules, data.eventList, {
    date: state.date,
    benchmark: state.bench,
    kind: "custom",
  });
}

function validateDate(dateStr) {
  const max = state.data && state.data.benchLast(state.bench) ? state.data.benchLast(state.bench) : null;
  if (dateStr < MIN_DATE || (max && dateStr > max)) {
    return t(state.lang, "err_range", { min: MIN_DATE, max: max || "…" });
  }
  return null;
}

function setModeFromControls() {
  const d = els.dateInput.value;
  if (!d) {
    state.mode = "latest";
    state.eventId = null;
    state.date = null;
    state.dateError = null;
    syncUrl();
    refresh();
    return;
  }
  const preset = presetForDate(d);
  state.date = d;
  if (preset) {
    state.mode = "preset";
    state.eventId = preset.id;
  } else {
    state.mode = "custom";
    state.eventId = null;
  }
  state.dateError = validateDate(d);
  if (state.dateError) {
    // keep the report at latest so the page still answers something
    state.mode = "latest";
    state.eventId = null;
    state.date = null;
  }
  syncUrl();
  refresh();
}

function refresh() {
  state.report = currentReport();
  view.data = state.data;
  syncControls();
  renderAll(view);
}

// --------------------------------------------------------------- controls

function fillSelects() {
  const data = state.data;
  // benchmark options — only benches present in the data
  els.benchSelect.innerHTML = data.benches
    .map((b) => `<option value="${esc(b)}">${esc(data.assets[b] ? data.assets[b]["name_" + state.lang] : b)}</option>`)
    .join("");
  els.benchSelect.value = state.bench;
  // event options: latest + presets (chronological) + custom slot
  const events = [...data.eventList].sort((a, b) => (a.date < b.date ? -1 : 1));
  const opts = [`<option value="__latest">${esc(t(state.lang, "latest"))}</option>`];
  for (const ev of events) {
    const name = (state.lang === "zh" ? ev.name : ev.name_en) || ev.name || ev.name_en || ev.id;
    opts.push(`<option value="${esc(ev.id)}">${esc(name)} (${esc(ev.date)})</option>`);
  }
  opts.push(`<option value="__custom" ${state.mode === "custom" ? "selected" : ""}>${esc(t(state.lang, "custom_date"))}</option>`);
  els.eventSelect.innerHTML = opts.join("");
  if (state.mode === "latest") els.eventSelect.value = "__latest";
  else if (state.mode === "preset") els.eventSelect.value = state.eventId;
  else els.eventSelect.value = "__custom";
  els.dateInput.min = MIN_DATE;
  const last = data.benchLast(state.bench);
  if (last) els.dateInput.max = last;
  els.dateInput.value = state.mode === "latest" ? "" : state.date || "";
  for (const btn of els.langBtns) {
    btn.setAttribute("aria-pressed", btn.dataset.lang === state.lang ? "true" : "false");
  }
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.title = t(state.lang, "site_name");
}

function syncControls() {
  document.getElementById("site-name").textContent = t(state.lang, "site_name");
  document.getElementById("lbl-date").textContent = t(state.lang, "pick_date");
  document.getElementById("lbl-event").textContent = t(state.lang, "event");
  document.getElementById("lbl-bench").textContent = t(state.lang, "benchmark");
  fillSelects();
  els.dateMsg.textContent = state.dateError || "";
  els.dateMsg.classList.toggle("show", Boolean(state.dateError));
}

function onEventSelect() {
  const v = els.eventSelect.value;
  if (v === "__latest") {
    state.mode = "latest";
    state.eventId = null;
    state.date = null;
    state.dateError = null;
    els.dateInput.value = "";
  } else if (v === "__custom") {
    els.dateInput.focus();
    return;
  } else {
    const ev = state.data.eventList.find((e) => e.id === v);
    if (!ev) return;
    state.mode = "preset";
    state.eventId = ev.id;
    state.date = ev.date;
    state.dateError = validateDate(ev.date);
    els.dateInput.value = ev.date;
  }
  syncUrl();
  refresh();
}

function onBenchSelect() {
  state.bench = els.benchSelect.value;
  if (state.mode !== "latest" && state.date) {
    state.dateError = validateDate(state.date);
  }
  syncUrl();
  refresh();
}

function onLang(btn) {
  state.lang = btn.dataset.lang;
  syncUrl(true);
  refresh();
}

function onPresetClick(ev) {
  const id = ev.target.closest("[data-event]");
  if (!id) return;
  const eventId = id.dataset.event;
  const preset = state.data.eventList.find((e) => e.id === eventId);
  if (!preset) return;
  state.mode = "preset";
  state.eventId = eventId;
  state.date = preset.date;
  state.dateError = null;
  syncUrl();
  refresh();
  window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

// -------------------------------------------------------------------- init

async function init() {
  state.lang = new URLSearchParams(location.search).get("lang") === "en" ? "en" : "zh";
  try {
    state.data = await new V3Data("").loadCore();
  } catch (err) {
    const file = String(err && err.message ? err.message : "").split("/").pop() || "reports.json";
    els.fatal.textContent = t("zh", "err_fetch", { file });
    els.fatal.classList.add("show");
    els.hero.innerHTML = `<h1 class="hero-title">${esc(t("zh", "site_name"))}</h1>`;
    return;
  }
  view.data = state.data;
  resolveFromUrl();
  // default benchmark if URL asked for one not in data
  if (!state.data.benches.includes(state.bench)) state.bench = state.data.benches[0] || "spx";

  els.dateInput.addEventListener("change", setModeFromControls);
  els.eventSelect.addEventListener("change", onEventSelect);
  els.benchSelect.addEventListener("change", onBenchSelect);
  for (const btn of els.langBtns) btn.addEventListener("click", () => onLang(btn));
  els.history.addEventListener("click", onPresetClick);
  window.addEventListener("popstate", () => {
    resolveFromUrl();
    refresh();
  });

  refresh();

  // series.json: stripes, GPR chart, custom-date reports
  try {
    await state.data.loadSeries();
    const gpr = state.data.gprSeries();
    state.months = gpr ? monthlyGpr(gpr) : null;
    if (state.date) state.dateError = validateDate(state.date);
  } catch (err) {
    state.months = null;
    state.seriesFailed = true;
    const file = String(err && err.message ? err.message : "").split("/").pop() || "series.json";
    els.fatal.textContent = t(state.lang, "err_fetch", { file });
    els.fatal.classList.add("show");
  }
  refresh();
}

init();
