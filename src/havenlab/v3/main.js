// EF Lab narrative-test page — orchestration: load core data, render the
// scoreboard-first product, wire the custom tool's shareable URL state and
// the condensed briefing's controls. All judgment text comes from
// narratives.json / the engine; this file only wires UI.

import { V3Data } from "./data.js";
import { t } from "./i18n.js";
import { monthlyGpr } from "./stripes.js";
import { renderHero, renderMethods } from "./scoreboard.js";
import { renderDetails } from "./details.js";
import { createTool } from "./tool.js";
import { renderBriefing } from "./briefing.js";
import { esc } from "./util.js";

const els = {
  mastBuilt: document.getElementById("mast-built"),
  brandName: document.getElementById("brand-name"),
  hero: document.getElementById("hero"),
  methods: document.getElementById("methods-strip"),
  details: document.getElementById("details"),
  tool: document.getElementById("tool"),
  briefing: document.getElementById("briefing"),
  footer: document.getElementById("site-footer"),
  fatal: document.getElementById("fatal"),
  langBtns: [...document.querySelectorAll("[data-lang]")],
};

const state = {
  lang: "zh",
  data: null,
  months: null,
  seriesFailed: false,
  brf: { mode: "latest", eventId: null, bench: "spx" },
  toolParamsAtLoad: false,
};

let tool = null;

// ------------------------------------------------------------------ footer

function renderFooter() {
  const { data, lang } = state;
  const el = els.footer;
  const built = data.reports && data.reports.built ? data.reports.built : "";
  const srcMap = new Map();
  for (const a of Object.values(data.assets)) {
    const src = a.source || "";
    if (!srcMap.has(src)) srcMap.set(src, []);
    if (a.symbol) srcMap.get(src).push(a.symbol);
  }
  const srcLabel = { yahoo: "Yahoo Finance", sina: "Sina", "spot file": "LBMA spot file" };
  const parts = [...srcMap.entries()].map(([src, syms]) => `${srcLabel[src] || src}: ${syms.join(", ")}`);
  parts.push(t(lang, "footer_gpr"));
  const classicHref = location.pathname.includes("/v3/") ? "../classic/" : "classic/";
  el.innerHTML = `
    <p class="footer-links">
      <a href="https://github.com/hantrleko/gpr-haven-lab/blob/main/docs/methods/v3.md" rel="noopener">${esc(t(lang, "footer_methods"))}</a>
      <a href="${classicHref}">${esc(t(lang, "footer_classic"))}</a>
    </p>
    <p class="muted footer-src">${esc(t(lang, "footer_sources"))}${esc(parts.join("；"))}</p>
    <p class="muted">${esc(t(lang, "footer_built", { built }))} · ${esc(t(lang, "not_advice"))}</p>`;
}

// ------------------------------------------------------------------ chrome

function syncChrome() {
  const { lang, data } = state;
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.title = t(lang, "doc_title");
  els.brandName.textContent = t(lang, "brand_name");
  const built = data.reports && data.reports.built ? data.reports.built : "";
  els.mastBuilt.textContent = built ? t(lang, "footer_built", { built }) : "";
  for (const btn of els.langBtns) {
    btn.setAttribute("aria-pressed", btn.dataset.lang === lang ? "true" : "false");
  }
}

// ----------------------------------------------------------------- renders

function renderStatic() {
  const { data, lang } = state;
  syncChrome();
  renderHero(els.hero, data, lang);
  renderMethods(els.methods, data, lang);
  renderDetails(els.details, data, lang);
  tool.render(data, lang);
  renderBriefing(els.briefing, data, lang, state.brf, state.months);
  renderFooter();
  wireBriefingControls();
}

function renderBriefingOnly() {
  renderBriefing(els.briefing, state.data, state.lang, state.brf, state.months);
  wireBriefingControls();
}

function wireBriefingControls() {
  const period = document.getElementById("brf-period");
  const bench = document.getElementById("brf-bench");
  if (period) {
    period.addEventListener("change", () => {
      if (period.value === "__latest") {
        state.brf.mode = "latest";
        state.brf.eventId = null;
      } else {
        state.brf.mode = "preset";
        state.brf.eventId = period.value;
      }
      renderBriefingOnly();
    });
  }
  if (bench) {
    bench.addEventListener("change", () => {
      state.brf.bench = bench.value;
      renderBriefingOnly();
    });
  }
}

// ------------------------------------------------------------------- url --

function syncLangUrl() {
  const params = new URLSearchParams(location.search);
  if (state.lang === "zh") params.delete("lang");
  else params.set("lang", state.lang);
  const qs = params.toString();
  history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
}

function onLang(btn) {
  state.lang = btn.dataset.lang;
  syncLangUrl();
  renderStatic();
}

// -------------------------------------------------------------------- init

async function init() {
  state.lang = new URLSearchParams(location.search).get("lang") === "en" ? "en" : "zh";
  try {
    state.data = await new V3Data(document.documentElement.dataset.base || "").loadCore();
  } catch (err) {
    const file = String(err && err.message ? err.message : "").split("/").pop() || "reports.json";
    els.fatal.textContent = t("zh", "err_fetch", { file });
    els.fatal.classList.add("show");
    return;
  }

  if (!state.data.benches.includes(state.brf.bench)) state.brf.bench = state.data.benches[0] || "spx";

  tool = createTool(els.tool);
  state.toolParamsAtLoad = tool.readUrl(state.data);

  for (const btn of els.langBtns) btn.addEventListener("click", () => onLang(btn));
  window.addEventListener("popstate", () => {
    state.lang = new URLSearchParams(location.search).get("lang") === "en" ? "en" : "zh";
    const hasParams = tool.readUrl(state.data);
    renderStatic();
    if (hasParams && state.data.decoded) tool.run(state.data, state.lang, { push: false, scroll: false });
  });

  // re-render the small multiples when the layout width changes
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (state.data) renderDetails(els.details, state.data, state.lang);
    }, 220);
  });

  renderStatic();

  // series.json: stripes, GPR chart, asset display names, the custom tool
  try {
    await state.data.loadSeries();
    const gpr = state.data.gprSeries();
    state.months = gpr ? monthlyGpr(gpr) : null;
  } catch (err) {
    state.months = null;
    state.seriesFailed = true;
    const file = String(err && err.message ? err.message : "").split("/").pop() || "series.json";
    els.fatal.textContent = t(state.lang, "err_fetch", { file });
    els.fatal.classList.add("show");
  }
  renderStatic();

  // shareable auto-run: ?d=…&assets=… present at load → run and scroll
  if (state.toolParamsAtLoad && state.data.decoded) {
    const ok = tool.run(state.data, state.lang, { push: false, scroll: false });
    if (ok) {
      els.tool.scrollIntoView({ behavior: "auto", block: "start" });
    }
  }
}

init();
