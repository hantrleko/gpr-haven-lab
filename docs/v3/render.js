// Rendering: every visible string comes from the report object's zh/en
// fields or the UI dictionary — the UI never writes its own conclusions.

import { t, ASSET_SHORT } from "./i18n.js";
import { stripesSvg, monthIndexOf } from "./stripes.js";
import { gprChartSvg } from "./charts.js";

export function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function floorRound(x, d) {
  return Math.floor(Math.abs(x) * Math.pow(10, d) + 0.5) / Math.pow(10, d);
}

function roundsToZero(x, d) {
  return Math.floor(Math.abs(x) * Math.pow(10, d) + 0.5) === 0;
}

// signed magnitude, same convention as the engine's sentence numbers
export function fmtSigned(x, d = 1) {
  const mag = floorRound(x, d).toFixed(d);
  if (roundsToZero(x, d)) return mag;
  return (x > 0 ? "+" : "-") + mag;
}

export function assetName(ctx, id, lang) {
  const entry = ctx.data.assets[id];
  return entry ? entry["name_" + lang] || id : id;
}

function mobileNote(ctx, titleKey, textKey) {
  return `<div class="note note-mobile"><h3>${esc(t(ctx.lang, titleKey))}</h3><p>${esc(t(ctx.lang, textKey))}</p></div>`;
}

function gradeBadge(grade, lang, rules) {
  const name = rules.grades[grade] ? rules.grades[grade][lang] : grade;
  return `<span class="grade-badge grade-${esc(grade)}">${esc(name)}</span>`;
}

function cellAt(havenRow, h) {
  return havenRow.by_h[String(h)];
}

// ---------------------------------------------------------------- stripes --

export function renderStripes(ctx) {
  const el = ctx.els.stripes;
  if (!ctx.months) {
    el.innerHTML = `<p class="muted">${esc(t(ctx.lang, "loading_series"))}</p>`;
    return;
  }
  const rep = ctx.report;
  let markerIdx = -1;
  if (rep) {
    if (rep.kind === "latest") {
      markerIdx = ctx.months.length - 1;
    } else if (rep.date) {
      markerIdx = monthIndexOf(ctx.months, rep.date);
    }
  }
  const first = ctx.months[0].key;
  const last = ctx.months[ctx.months.length - 1].key;
  const marker = markerIdx >= 0 ? ctx.months[markerIdx].key : last;
  const aria = t(ctx.lang, "stripes_aria", { first, last, month: marker });
  el.innerHTML = stripesSvg(ctx.months, markerIdx, aria) + mobileNote(ctx, "rail_stripes_t", "stripes_note");
}

// ----------------------------------------------------------------- hero ---

export function renderHero(ctx) {
  const { rep, lang, rules } = ctx;
  const el = ctx.els.hero;
  if (!rep) {
    const msg = ctx.seriesFailed && ctx.state.mode === "custom" ? t(lang, "err_no_series") : t(lang, "loading_report");
    el.innerHTML = `<h1 class="hero-title muted">${esc(msg)}</h1>`;
    return;
  }
  el.innerHTML = `
    <h1 class="hero-title">${esc(rep.headline[lang])}</h1>
    <p class="hero-grade">${gradeBadge(rep.headline.grade, lang, rules)}</p>
    <p class="hero-deck">${esc(rep.pressure[lang])}</p>`;
}

// -------------------------------------------------------------- pressure --

export function renderPressure(ctx) {
  const { rep, lang, data } = ctx;
  const el = ctx.els.pressure;
  if (!rep) {
    el.innerHTML = `<h2>${esc(t(lang, "sec_pressure"))}</h2><p class="muted">…</p>`;
    return;
  }
  const gpr = data.gprSeries();
  let chart = "";
  if (gpr && rep.pressure.start) {
    const winDays = data.rules.gpr.window_days;
    chart = gprChartSvg(gpr, rep.pressure.start, winDays, t(lang, "gpr_line"));
  } else if (!data.payload) {
    chart = `<p class="muted">${esc(t(lang, "loading_series"))}</p>`;
  }
  const shocks = (rep.shock || [])
    .map((s) => `<p class="shock-line">${esc(s[lang])}</p>`)
    .join("");
  el.innerHTML = `
    <h2>${esc(t(lang, "sec_pressure"))}</h2>
    ${chart ? `<figure class="gpr-fig">${chart}<figcaption class="muted">${esc(t(lang, "window_shade"))}</figcaption></figure>` : ""}
    ${shocks}
    ${mobileNote(ctx, "rail_gpr_t", "gpr_note")}`;
}

// ---------------------------------------------------------------- havens --

const H_LABELS = {
  clear_up: { fill: "#3D4F8F", stroke: "none", sw: 0 },
  lean_up: { fill: "#8FA9C4", stroke: "none", sw: 0 },
  normal: { fill: "#5B6676", stroke: "none", sw: 0, op: 0.4 },
  clear_down: { fill: "none", stroke: "#5B6676", sw: 2.2 },
  lean_down: { fill: "none", stroke: "#5B6676", sw: 1.2, op: 0.7 },
};

function pctX(pct) {
  return 2 + pct * 96;
}

function trackSvg(row, ctx) {
  const { rules, lang } = ctx;
  const k30 = row.k30;
  const cut = k30 > 0 ? 1 - rules.family_alpha / k30 : null;
  const parts = [
    `<svg class="track" viewBox="0 0 100 30" preserveAspectRatio="none" role="img" aria-label="${esc(t(lang, "track_aria", { asset: assetName(ctx, row.id, lang) }))}">`,
    `<line x1="2" y1="15" x2="98" y2="15" stroke="#D5DCE3" stroke-width="1"/>`,
    `<line x1="80" y1="11" x2="80" y2="19" stroke="#5B6676" stroke-width="1"/>`,
  ];
  if (cut !== null) {
    const cx = pctX(Math.min(Math.max(cut, 0), 1));
    parts.push(`<line x1="${cx.toFixed(1)}" y1="11" x2="${cx.toFixed(1)}" y2="19" stroke="#3D4F8F" stroke-width="1.4"/>`);
  }
  const slots = [
    { h: 7, y: 6, kind: "circle", r: 2 },
    { h: 30, y: 15, kind: "circle", r: 3.4 },
    { h: 91, y: 24, kind: "square", half: 2.6 },
  ];
  for (const slot of slots) {
    const cell = cellAt(row, slot.h);
    if (!cell || cell.pct === null || cell.pct === undefined) {
      parts.push(`<text x="3" y="${slot.y + 3}" font-size="8" fill="#5B6676">—</text>`);
      continue;
    }
    const st = H_LABELS[cell.label] || H_LABELS.normal;
    const x = pctX(Math.min(Math.max(cell.pct, 0), 1)).toFixed(1);
    const op = st.op !== undefined ? ` opacity="${st.op}"` : "";
    const fill = st.fill === "none" ? "none" : st.fill;
    const stroke = st.stroke === "none" ? "none" : st.stroke;
    const common = `fill="${fill}" stroke="${stroke}" stroke-width="${st.sw}"${op}`;
    if (slot.kind === "circle") {
      parts.push(`<circle cx="${x}" cy="${slot.y}" r="${slot.r}" ${common}/>`);
    } else {
      parts.push(`<rect x="${(parseFloat(x) - slot.half).toFixed(1)}" y="${slot.y - slot.half}" width="${slot.half * 2}" height="${slot.half * 2}" ${common}/>`);
    }
  }
  parts.push(`</svg>`);
  return parts.join("");
}

export function renderHavens(ctx) {
  const { rep, lang, rules } = ctx;
  const el = ctx.els.havens;
  if (!rep) {
    el.innerHTML = `<h2>${esc(t(lang, "sec_havens"))}</h2><p class="muted">…</p>`;
    return;
  }
  const k30 = rep.k ? rep.k[String(rules.primary)] : 0;
  const rows = rep.havens.map((h) => ({ ...h, k30 })).map((row) => {
    const cell = cellAt(row, rules.primary);
    const ret = cell && cell.ret !== null && cell.ret !== undefined ? `${fmtSigned(cell.ret, 1)}%` : "—";
    const label = cell ? rules.labels[cell.label][lang] : "—";
    return `
      <tr>
        <td class="asset-name">${esc(assetName(ctx, row.id, lang))}</td>
        <td class="num ret">${esc(ret)}</td>
        <td class="rating">${esc(label)}</td>
        <td class="track-cell">${trackSvg(row, ctx)}</td>
      </tr>`;
  }).join("");
  el.innerHTML = `
    <h2>${esc(t(lang, "sec_havens"))}</h2>
    <p class="section-lead">${esc(rep.bench[lang])}</p>
    <div class="table-scroll">
    <table class="haven-table">
      <thead><tr>
        <th>${esc(t(lang, "col_asset"))}</th>
        <th>${esc(t(lang, "col_ret"))}</th>
        <th>${esc(t(lang, "col_label"))}</th>
        <th>${esc(t(lang, "col_track"))}</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    </div>
    ${mobileNote(ctx, "rail_haven_t", "haven_note")}`;
}

// --------------------------------------------------------------- history --

const MATRIX_CLASS = {
  clear_up: "m-cu",
  lean_up: "m-lu",
  normal: "m-no",
  lean_down: "m-ld",
  clear_down: "m-cd",
};

function presetCellLabel(ctx, eventId, havenId) {
  const perBench = ctx.data.reports.events[eventId];
  const rep = perBench && perBench[ctx.bench];
  if (!rep) return null;
  const row = rep.havens.find((h) => h.id === havenId);
  return row ? row.by_h["30"].label : null;
}

export function renderHistory(ctx) {
  const { rep, lang, rules, data } = ctx;
  const el = ctx.els.history;
  if (!rep) {
    el.innerHTML = `<h2>${esc(t(lang, "sec_history"))}</h2><p class="muted">…</p>`;
    return;
  }
  const hist = rep.history || [];
  const histLabels = ["clear_up", "lean_up", "normal", "lean_down", "clear_down"];
  const histKeys = ["hist_cu", "hist_lu", "hist_no", "hist_ld", "hist_cd"];
  const caption = t(lang, "hist_caption", { n: Math.max(0, ...hist.map((r) => r.n || 0)) });
  const summary = hist.map((row) => row[lang]).join(" ");
  const histRows = hist
    .map((row) => {
      const med = row.median !== null && row.median !== undefined ? `${fmtSigned(row.median, 1)}%` : "—";
      const counts = histLabels.map((lb) => `<td class="num">${row[lb] ?? "—"}</td>`).join("");
      return `<tr><th scope="row">${esc(assetName(ctx, row.id, lang))}</th>${counts}<td class="num med">${esc(med)}</td></tr>`;
    })
    .join("");
  const headCells = histKeys.map((k) => `<th>${esc(t(lang, k))}</th>`).join("");
  const maxN = Math.max(0, ...hist.map((r) => r.n || 0));
  const fewer = hist
    .filter((r) => (r.n || 0) < maxN)
    .map((r) => (lang === "zh" ? `${assetName(ctx, r.id, lang)}（${r.n}/${maxN}）` : `${assetName(ctx, r.id, lang)} (${r.n} of ${maxN})`))
    .join(lang === "zh" ? "、" : ", ");
  const foot = fewer ? `<p class="note hist-foot">${esc(t(lang, "hist_fewer", { list: fewer }))}</p>` : "";
  const events = [...data.eventList].sort((a, b) => (a.date < b.date ? -1 : 1));
  const short = ASSET_SHORT[lang] || ASSET_SHORT.en;
  const head = rules.havens
    .map((h) => {
      const full = assetName(ctx, h, lang);
      return `<th scope="col" title="${esc(full)}" aria-label="${esc(full)}">${esc(short[h] || full)}</th>`;
    })
    .join("");
  const body = events
    .map((ev) => {
      const cells = rules.havens
        .map((h) => {
          const label = presetCellLabel(ctx, ev.id, h);
          const cls = MATRIX_CLASS[label] || "m-na";
          const labelText = label ? rules.labels[label][lang] : t(lang, "legend_unrated");
          const glyph = label && MATRIX_CLASS[label] ? "" : "—";
          return `<td class="mx ${cls}"><span class="sr-only">${esc(labelText)}</span>${glyph}</td>`;
        })
        .join("");
      const name = (lang === "zh" ? ev.name : ev.name_en) || ev.name || ev.name_en || ev.id;
      return `<tr><th scope="row"><button type="button" class="preset-link" data-event="${esc(ev.id)}"><span class="ev-name">${esc(name)}</span><span class="ev-date">${esc(ev.date)}</span></button></th>${cells}</tr>`;
    })
    .join("");
  const legend = ["clear_up", "lean_up", "normal", "lean_down", "clear_down"]
    .map((lb) => `<span class="lg"><i class="sw m-${lb === "clear_up" ? "cu" : lb === "lean_up" ? "lu" : lb === "normal" ? "no" : lb === "lean_down" ? "ld" : "cd"}"></i>${esc(rules.labels[lb][lang])}</span>`)
    .join("") + `<span class="lg"><i class="sw m-na"></i>${esc(t(lang, "legend_unrated"))}</span>`;
  el.innerHTML = `
    <h2>${esc(t(lang, "sec_history"))}</h2>
    <p class="note hist-cap">${esc(caption)}</p>
    <div class="table-scroll">
    <table class="hist-table">
      <caption class="sr-only">${esc(summary)}</caption>
      <thead><tr><th scope="col">${esc(t(lang, "hist_asset"))}</th>${headCells}<th>${esc(t(lang, "hist_med"))}</th></tr></thead>
      <tbody>${histRows}</tbody>
    </table>
    </div>
    ${foot}
    <h3 class="subhead">${esc(t(lang, "matrix_title"))}</h3>
    <div class="matrix-wrap">
      <table class="matrix">
        <thead><tr><th scope="col">${esc(t(lang, "hist_event"))}</th>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <p class="legend">${legend}</p>`;
}

// -------------------------------------------------------------- evidence --

export function renderEvidence(ctx) {
  const { rep, lang, rules } = ctx;
  const el = ctx.els.evidence;
  if (!rep) {
    el.innerHTML = `<h2>${esc(t(lang, "sec_evidence"))}</h2><p class="muted">…</p>`;
    return;
  }
  el.innerHTML = `
    <h2>${esc(t(lang, "sec_evidence"))}</h2>
    <p class="evidence-line">${gradeBadge(rep.evidence.grade, lang, rules)} <span>${esc(rep.evidence[lang])}</span></p>
    <p class="note">${esc(t(lang, "evidence_explain"))}</p>
    ${mobileNote(ctx, "rail_evidence_t", "evidence_note")}`;
}

// -------------------------------------------------------------- caveats ---

export function renderCaveats(ctx) {
  const { rep, lang } = ctx;
  const el = ctx.els.caveats;
  if (!rep) {
    el.innerHTML = `<h2>${esc(t(lang, "sec_caveats"))}</h2><p class="muted">…</p>`;
    return;
  }
  const items = (rep.caveats || []).map((c) => `<li>${esc(c[lang])}</li>`).join("");
  el.innerHTML = `<h2>${esc(t(lang, "sec_caveats"))}</h2><ul class="caveat-list">${items}</ul>`;
}

// ---------------------------------------------------------------- footer --

export function renderFooter(ctx) {
  const { data, lang, report } = ctx;
  const el = ctx.els.footer;
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
  el.innerHTML = `
    <p class="footer-links">
      <a href="https://github.com/hantrleko/gpr-haven-lab/blob/main/docs/methods/v3.md" rel="noopener">${esc(t(lang, "footer_methods"))}</a>
      <a href="../index.html">${esc(t(lang, "footer_classic"))}</a>
    </p>
    <p class="muted footer-src">${esc(t(lang, "footer_sources"))}${esc(parts.join("；"))}</p>
    <p class="muted">${esc(t(lang, "footer_built", { built }))} · ${esc(t(lang, "not_advice"))}</p>`;
}

// ------------------------------------------------------------------ rail --

export function renderRail(ctx) {
  const { lang } = ctx;
  const el = ctx.els.rail;
  el.innerHTML = `
    <section class="note"><h3>${esc(t(lang, "rail_stripes_t"))}</h3><p>${esc(t(lang, "stripes_note"))}</p></section>
    <section class="note"><h3>${esc(t(lang, "rail_gpr_t"))}</h3><p>${esc(t(lang, "gpr_note"))}</p></section>
    <section class="note"><h3>${esc(t(lang, "rail_haven_t"))}</h3><p>${esc(t(lang, "haven_note"))}</p></section>
    <section class="note"><h3>${esc(t(lang, "rail_evidence_t"))}</h3><p>${esc(t(lang, "evidence_note"))}</p></section>`;
}

export function renderAll(ctx) {
  renderStripes(ctx);
  renderHero(ctx);
  renderPressure(ctx);
  renderHavens(ctx);
  renderHistory(ctx);
  renderEvidence(ctx);
  renderCaveats(ctx);
  renderFooter(ctx);
  renderRail(ctx);
}
