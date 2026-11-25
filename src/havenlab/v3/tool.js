// Custom test panel: pick assets, pick up to five dates, run the same fixed
// narrative rules in the browser via buildCustomNarrative. State is shareable
// through the URL (?d=…,…&assets=…,…&b=…). Errors are plain-language inline.

import { t } from "./i18n.js";
import { esc, assetName, unitSquares, verdictChip, hitCount, medianText } from "./util.js";
import { makeCtx, buildCustomNarrative } from "./report.js";

// The narrative-layer universe: the eight assets the frozen narratives cover.
export const TOOL_ASSETS = ["gold", "silver", "jpy", "chf", "ust", "btc", "dxy", "brent"];
const MAX_DATES = 5;
const DEFAULT_ASSETS = ["gold", "ust", "btc"];

export function createTool(el) {
  const state = {
    assets: new Set(DEFAULT_ASSETS),
    dates: ["", "", "", "", ""],
    bench: "spx",
    ran: false,
    paramError: false,
  };
  let engineCtx = null;

  function dispName(data, id, lang) {
    return assetName(data, id, lang);
  }

  function render(data, lang) {
    const chips = TOOL_ASSETS
      .map((id) => {
        const on = state.assets.has(id);
        return `<button type="button" class="achip" data-asset="${esc(id)}" aria-pressed="${on}">${esc(dispName(data, id, lang))}</button>`;
      })
      .join("");
    const dateInputs = state.dates
      .map((v, i) => `<input type="date" class="tdate" data-slot="${i}" value="${esc(v)}" aria-label="${esc(t(lang, "tool_dates"))} ${i + 1}">`)
      .join("");
    const benches = data.benches
      .map((b) => `<option value="${esc(b)}"${b === state.bench ? " selected" : ""}>${esc(dispName(data, b, lang))}</option>`)
      .join("");
    el.innerHTML = `
      <h2>${esc(t(lang, "tool_title"))}</h2>
      <p class="section-note">${esc(t(lang, "tool_intro"))}</p>
      <div class="tool-form">
        <div class="tool-row">
          <span class="tool-label">${esc(t(lang, "tool_assets"))}</span>
          <div class="chip-set">${chips}</div>
        </div>
        <div class="tool-row">
          <span class="tool-label">${esc(t(lang, "tool_dates"))}</span>
          <div class="date-set">${dateInputs}</div>
        </div>
        <div class="tool-row tool-actions">
          <label class="tool-label" for="tool-bench">${esc(t(lang, "tool_bench"))}</label>
          <select id="tool-bench">${benches}</select>
          <button type="button" class="btn-run" id="tool-run">${esc(t(lang, "tool_run"))}</button>
          <button type="button" class="btn-copy" id="tool-copy"${state.ran ? "" : " disabled"}>${esc(t(lang, "tool_copy"))}</button>
        </div>
        <p class="tool-error" id="tool-error" hidden></p>
      </div>
      <div class="tool-out" id="tool-out"></div>
      <p class="tool-note">${esc(t(lang, "tool_note"))}</p>`;

    // input bounds once series meta is available
    const first = firstDate(data);
    const last = lastDate(data);
    el.querySelectorAll(".tdate").forEach((inp) => {
      if (first) inp.min = first;
      if (last) inp.max = last;
    });

    // wiring
    el.querySelectorAll(".achip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.asset;
        if (state.assets.has(id)) state.assets.delete(id);
        else state.assets.add(id);
        btn.setAttribute("aria-pressed", state.assets.has(id) ? "true" : "false");
      });
    });
    el.querySelectorAll(".tdate").forEach((inp) => {
      inp.addEventListener("change", () => {
        state.dates[Number(inp.dataset.slot)] = inp.value;
      });
    });
    el.querySelector("#tool-bench").addEventListener("change", (ev) => {
      state.bench = ev.target.value;
    });
    el.querySelector("#tool-run").addEventListener("click", () => run(data, lang, { push: true, scroll: true }));
    el.querySelector("#tool-copy").addEventListener("click", () => copyLink(lang));
    if (state.ran) run(data, lang, { push: false, scroll: false });
  }

  function firstDate(data) {
    const entry = data.assets[state.bench] || data.assets.spx;
    return entry && entry.first ? entry.first : null;
  }

  function lastDate(data) {
    const entry = data.assets[state.bench] || data.assets.spx;
    return entry && entry.last ? entry.last : null;
  }

  function error(msg) {
    const box = el.querySelector("#tool-error");
    if (!box) return;
    if (!msg) {
      box.hidden = true;
      box.textContent = "";
    } else {
      box.hidden = false;
      box.textContent = msg;
    }
  }

  function collectDates(data, lang) {
    const out = [];
    const first = firstDate(data);
    const last = lastDate(data);
    for (let i = 0; i < state.dates.length; i += 1) {
      const v = state.dates[i];
      if (!v) continue;
      if (!/^\d{4}-\d{2}-\d{2}$/.test(v) || (first && v < first) || (last && v > last)) {
        return { error: t(lang, "tool_err_bad_date", { i: i + 1, min: first || "…", max: last || "…" }) };
      }
      out.push(v);
    }
    const uniq = [...new Set(out)].sort();
    return { dates: uniq };
  }

  function run(data, lang, opts = {}) {
    if (!data.decoded) {
      error(t(lang, "tool_loading"));
      return false;
    }
    const assets = TOOL_ASSETS.filter((id) => state.assets.has(id));
    if (!assets.length) {
      error(t(lang, "tool_err_no_assets"));
      return false;
    }
    const { dates, error: derr } = collectDates(data, lang);
    if (derr) {
      error(derr);
      return false;
    }
    if (!dates.length) {
      error(t(lang, "tool_err_no_dates"));
      return false;
    }
    if (!engineCtx) {
      engineCtx = makeCtx(data.decoded, data.rules);
      engineCtx.narrativeRules = data.narrativeRules;
    }
    let entries;
    try {
      entries = buildCustomNarrative(engineCtx, dates, assets, state.bench);
    } catch (err) {
      error(String(err && err.message ? err.message : err));
      return false;
    }
    state.ran = true;
    error(state.paramError ? t(lang, "tool_err_param") : null);
    renderOut(data, lang, entries);
    if (opts.push) pushUrl();
    const copyBtn = el.querySelector("#tool-copy");
    if (copyBtn) copyBtn.disabled = false;
    if (opts.scroll) {
      const out = el.querySelector("#tool-out");
      if (out) out.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
    }
    return true;
  }

  function renderOut(data, lang, entries) {
    const out = el.querySelector("#tool-out");
    const labels = data.narrativeRules.labels;
    const rows = entries
      .map((entry) => {
        const name = dispName(data, entry.asset, lang);
        const chip = verdictChip(entry.verdict, labels, lang);
        const hits = hitCount(entry.n_pos, entry.n_valid, lang);
        const med = medianText(entry.median);
        const units = unitSquares(entry.rows, lang, null);
        const sum = entry["summary_" + lang] || entry.summary_en || entry.summary_zh;
        return `<div class="tres">
          <div class="sb-row">
            <span class="sb-claim">${esc(name)}</span>
            <span class="sb-verdict">${chip}</span>
            <span class="sb-hits">${hits}</span>
            <span class="sb-median num">${esc(med)}</span>
            <span class="sb-events">${units}</span>
          </div>
          ${sum ? `<p class="tres-sum">${esc(sum)}</p>` : ""}
        </div>`;
      })
      .join("");
    out.innerHTML = `<div class="scoreboard tool-board">${rows}</div>`;
  }

  function buildUrl() {
    const params = new URLSearchParams(location.search);
    const assets = TOOL_ASSETS.filter((id) => state.assets.has(id));
    const filled = [...new Set(state.dates.filter(Boolean))].sort();
    if (filled.length) params.set("d", filled.join(","));
    else params.delete("d");
    if (assets.length) params.set("assets", assets.join(","));
    else params.delete("assets");
    if (state.bench !== "spx") params.set("b", state.bench);
    else params.delete("b");
    // commas are legal sub-delims — keep them literal for readable shared links
    const qs = params.toString().replace(/%2C/gi, ",");
    return location.pathname + (qs ? "?" + qs : "");
  }

  function pushUrl() {
    history.pushState(null, "", buildUrl());
  }

  async function copyLink(lang) {
    const url = location.origin + buildUrl();
    const btn = el.querySelector("#tool-copy");
    try {
      await navigator.clipboard.writeText(url);
    } catch (err) {
      const tmp = document.createElement("textarea");
      tmp.value = url;
      document.body.appendChild(tmp);
      tmp.select();
      document.execCommand("copy");
      tmp.remove();
    }
    if (btn) {
      const orig = t(lang, "tool_copy");
      btn.textContent = t(lang, "tool_copied");
      setTimeout(() => { btn.textContent = orig; }, 1500);
    }
  }

  // Parse ?d=…&assets=…&b=… into state. Returns true if any tool param was present.
  function readUrl(data) {
    const params = new URLSearchParams(location.search);
    const d = params.get("d");
    const a = params.get("assets");
    const b = params.get("b");
    if (!d && !a && !b) return false;
    state.paramError = false;
    if (d) {
      const parts = d.split(",").map((s) => s.trim()).filter(Boolean);
      const valid = parts.filter((s) => /^\d{4}-\d{2}-\d{2}$/.test(s));
      if (valid.length !== parts.length) state.paramError = true;
      const slots = [...new Set(valid)].sort().slice(0, MAX_DATES);
      if (valid.length > MAX_DATES) state.paramError = true;
      state.dates = ["", "", "", "", ""];
      slots.forEach((v, i) => { state.dates[i] = v; });
    }
    if (a) {
      const parts = a.split(",").map((s) => s.trim()).filter(Boolean);
      const valid = parts.filter((s) => TOOL_ASSETS.includes(s));
      if (!valid.length || valid.length !== parts.length) state.paramError = true;
      if (valid.length) state.assets = new Set(valid);
    }
    if (b) {
      if (data.benches.includes(b)) state.bench = b;
      else state.paramError = true;
    }
    return Boolean(d || a);
  }

  return { render, run, readUrl, state };
}
