// The condensed briefing: the former v3 report module moved below the fold.
// Slimmer pressure stripes are this section's signature element. All report
// text comes from the precomputed engine output in reports.json — the UI
// writes no conclusions of its own.

import { t } from "./i18n.js";
import { esc, fmtSigned, assetName, eventName } from "./util.js";
import { stripesSvg, monthIndexOf } from "./stripes.js";
import { gprChartSvg } from "./charts.js";

function gradeBadge(grade, lang, rules) {
  const name = rules.grades[grade] ? rules.grades[grade][lang] : grade;
  return `<span class="grade-badge grade-${esc(grade)}">${esc(name)}</span>`;
}

// ------------------------------------------------------------- haven table

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

function cellAt(havenRow, h) {
  return havenRow.by_h[String(h)];
}

function trackSvg(row, data, lang) {
  const rules = data.rules;
  const k30 = row.k30;
  const cut = k30 > 0 ? 1 - rules.family_alpha / k30 : null;
  const parts = [
    `<svg class="track" viewBox="0 0 100 26" preserveAspectRatio="none" role="img" aria-label="${esc(t(lang, "track_aria", { asset: assetName(data, row.id, lang) }))}">`,
    `<line x1="2" y1="13" x2="98" y2="13" stroke="#D5DCE3" stroke-width="1"/>`,
    `<line x1="80" y1="9" x2="80" y2="17" stroke="#5B6676" stroke-width="1"/>`,
  ];
  if (cut !== null) {
    const cx = pctX(Math.min(Math.max(cut, 0), 1));
    parts.push(`<line x1="${cx.toFixed(1)}" y1="9" x2="${cx.toFixed(1)}" y2="17" stroke="#3D4F8F" stroke-width="1.4"/>`);
  }
  const slots = [
    { h: 7, y: 5, kind: "circle", r: 2 },
    { h: 30, y: 13, kind: "circle", r: 3.4 },
    { h: 91, y: 21, kind: "square", half: 2.6 },
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

function havenTable(rep, data, lang) {
  const rules = data.rules;
  const k30 = rep.k ? rep.k[String(rules.primary)] : 0;
  const rows = rep.havens.map((h) => ({ ...h, k30 })).map((row) => {
    const cell = cellAt(row, rules.primary);
    const ret = cell && cell.ret !== null && cell.ret !== undefined ? `${fmtSigned(cell.ret, 1)}%` : "—";
    const label = cell ? rules.labels[cell.label][lang] : "—";
    return `
      <tr>
        <td class="asset-name">${esc(assetName(data, row.id, lang))}</td>
        <td class="num ret">${esc(ret)}</td>
        <td class="rating">${esc(label)}</td>
        <td class="track-cell">${trackSvg(row, data, lang)}</td>
      </tr>`;
  }).join("");
  return `
    <table class="haven-table">
      <thead><tr>
        <th>${esc(t(lang, "col_asset"))}</th>
        <th>${esc(t(lang, "col_ret"))}</th>
        <th>${esc(t(lang, "col_label"))}</th>
        <th>${esc(t(lang, "col_track"))}</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ------------------------------------------------------------------ section

export function currentReport(data, sel) {
  if (!data || !data.reports) return null;
  if (sel.mode === "preset") {
    const perBench = data.reports.events[sel.eventId];
    return perBench ? perBench[sel.bench] || null : null;
  }
  return data.reports.latest[sel.bench] || null;
}

export function renderBriefing(el, data, lang, sel, months) {
  const rep = currentReport(data, sel);
  const rules = data.rules;

  // control row: moment picker (latest + frozen events) + benchmark picker
  const events = [...data.eventList].sort((a, b) => (a.date < b.date ? -1 : 1));
  const evOpts = [`<option value="__latest"${sel.mode === "latest" ? " selected" : ""}>${esc(t(lang, "latest"))}</option>`];
  for (const ev of events) {
    const nm = eventName(ev, lang);
    evOpts.push(`<option value="${esc(ev.id)}"${sel.eventId === ev.id ? " selected" : ""}>${esc(nm)} (${esc(ev.date)})</option>`);
  }
  const benchOpts = data.benches
    .map((b) => `<option value="${esc(b)}"${b === sel.bench ? " selected" : ""}>${esc(assetName(data, b, lang))}</option>`)
    .join("");

  if (!rep) {
    el.innerHTML = `<h2>${esc(t(lang, "brf_title"))}</h2><p class="muted">${esc(t(lang, "loading"))}</p>`;
    return;
  }

  // pressure stripes — this section's signature element, slimmed down
  let stripes = `<p class="muted small">${esc(t(lang, "loading_series"))}</p>`;
  if (months) {
    let markerIdx = -1;
    if (rep.kind === "latest") markerIdx = months.length - 1;
    else if (rep.date) markerIdx = monthIndexOf(months, rep.date);
    const first = months[0].key;
    const last = months[months.length - 1].key;
    const marker = markerIdx >= 0 ? months[markerIdx].key : last;
    const aria = t(lang, "stripes_aria", { first, last, month: marker });
    stripes = stripesSvg(months, markerIdx, aria, { h: 48, stripeH: 48, label: false });
  }

  // GPR line around the pressure window
  let chart = "";
  const gpr = data.gprSeries();
  if (gpr && rep.pressure.start) {
    chart = `<figure class="gpr-fig">${gprChartSvg(gpr, rep.pressure.start, rules.gpr.window_days, t(lang, "gpr_line"))}<figcaption class="muted small">${esc(t(lang, "window_shade"))}</figcaption></figure>`;
  }

  const shocks = (rep.shock || []).map((s) => `<p class="shock-line">${esc(s[lang])}</p>`).join("");
  const caveats = (rep.caveats || []).map((c) => `<li>${esc(c[lang])}</li>`).join("");

  el.innerHTML = `
    <div class="brf-head">
      <h2>${esc(t(lang, "brf_title"))}</h2>
      <div class="brf-controls">
        <label class="brf-ctl"><span>${esc(t(lang, "brf_period"))}</span><select id="brf-period">${evOpts.join("")}</select></label>
        <label class="brf-ctl"><span>${esc(t(lang, "benchmark"))}</span><select id="brf-bench">${benchOpts}</select></label>
      </div>
    </div>
    <p class="brf-deck">${gradeBadge(rep.headline.grade, lang, rules)} <span class="brf-headline">${esc(rep.headline[lang])}</span></p>
    <div class="brf-stripes">${stripes}</div>
    <p class="brf-caption muted small">${esc(t(lang, "stripes_note"))}</p>
    <div class="brf-cols">
      <div class="brf-col">
        <h3 class="brf-sub">${esc(t(lang, "sec_pressure"))}</h3>
        <p class="brf-pressure">${esc(rep.pressure[lang])}</p>
        ${chart}
        ${shocks}
      </div>
      <div class="brf-col">
        <h3 class="brf-sub">${esc(t(lang, "sec_havens"))}</h3>
        <p class="brf-bench">${esc(rep.bench[lang])}</p>
        <div class="table-scroll">${havenTable(rep, data, lang)}</div>
      </div>
    </div>
    <div class="brf-foot">
      <p class="evidence-line">${gradeBadge(rep.evidence.grade, lang, rules)} <span>${esc(rep.evidence[lang])}</span></p>
      <h3 class="brf-sub">${esc(t(lang, "sec_caveats"))}</h3>
      <ul class="caveat-list">${caveats}</ul>
    </div>`;
}
