// Per-narrative small multiples: one compact horizontal bar chart per
// narrative, valid tests only, chronological top to bottom. Positive bars
// filled indigo, negative hollow; dashed claret line marks the median.
// All data from narratives.json rows — nothing hardcoded.

import { t, EV_SHORT_EN } from "./i18n.js";
import { esc, fmtSigned, eventName, verdictChip, hitCount } from "./util.js";

const ROW_H = 17;
const BAR_H = 11;
const PAD_T = 5;
const PAD_B = 5;
const LABEL_W = 118;
const VAL_W = 48;

function evTag(ev, lang) {
  if (!ev) return "";
  if (lang === "en") return EV_SHORT_EN[ev.id] || eventName(ev, lang);
  return eventName(ev, lang);
}

function chartSvg(narr, lang, evMap, width) {
  const rows = narr.rows
    .filter((r) => r.status === "valid")
    .sort((a, b) => (a.date < b.date ? -1 : 1));
  const H = rows.length * ROW_H + PAD_T + PAD_B;
  if (!rows.length) {
    return `<svg class="nchart" viewBox="0 0 ${width} 24" width="${width}" height="24" role="img"><text x="0" y="16" font-size="10.5" fill="#5B6676">—</text></svg>`;
  }
  const rets = rows.map((r) => r.ret);
  const xMin = Math.min(0, ...rets);
  const xMax = Math.max(0, ...rets);
  const span = xMax - xMin || 1;
  const pad = span * 0.06;
  const bx0 = LABEL_W + 6;
  const bx1 = width - VAL_W - 4;
  const X = (v) => bx0 + ((v - (xMin - pad)) / (span + 2 * pad)) * (bx1 - bx0);
  const zeroX = X(0);
  const medX = narr.median !== null && narr.median !== undefined ? X(narr.median) : null;

  const parts = [
    `<svg class="nchart" viewBox="0 0 ${width} ${H}" width="${width}" height="${H}" role="img" aria-label="${esc(narr[lang] || narr.en || "")}">`,
    // zero line behind the bars
    `<line x1="${zeroX.toFixed(1)}" y1="${PAD_T - 2}" x2="${zeroX.toFixed(1)}" y2="${H - PAD_B + 2}" stroke="#DDE3EA" stroke-width="1"/>`,
  ];

  rows.forEach((row, i) => {
    const y = PAD_T + i * ROW_H;
    const barY = y + (ROW_H - BAR_H) / 2;
    const ev = row.event ? evMap.get(row.event) : null;
    const tag = ev ? evTag(ev, lang) : row.date;
    const x1 = X(Math.min(0, row.ret));
    const x2 = X(Math.max(0, row.ret));
    const w = Math.max(0.8, x2 - x1);
    const barAttrs = row.ret > 0
      ? `fill="#3D4F8F"`
      : `fill="#FFFFFF" stroke="#3D4F8F" stroke-width="1" opacity="0.75"`;
    const tip = `${row.date} ${ev ? eventName(ev, lang) : ""}: ${fmtSigned(row.ret, 1)}%`;
    parts.push(
      `<text x="${LABEL_W}" y="${(barY + BAR_H / 2 + 3.5).toFixed(1)}" text-anchor="end" font-size="10.5" fill="#17202B">${esc(tag)}</text>`,
      `<rect x="${x1.toFixed(1)}" y="${barY.toFixed(1)}" width="${w.toFixed(1)}" height="${BAR_H}" rx="1" ${barAttrs}><title>${esc(tip)}</title></rect>`,
      `<text x="${(width - 4).toFixed(1)}" y="${(barY + BAR_H / 2 + 3.5).toFixed(1)}" text-anchor="end" font-size="10" fill="#5B6676" class="num">${esc(fmtSigned(row.ret, 1))}</text>`,
    );
  });

  if (medX !== null) {
    parts.push(
      `<line x1="${medX.toFixed(1)}" y1="${PAD_T - 2}" x2="${medX.toFixed(1)}" y2="${H - PAD_B + 2}" stroke="#7A1F3D" stroke-width="1.2" stroke-dasharray="3 2.5"/>`,
    );
  }
  parts.push(`</svg>`);
  return parts.join("");
}

export function renderDetails(el, data, lang) {
  const payload = data.narratives;
  if (!payload) {
    el.innerHTML = `<h2>${esc(t(lang, "det_title"))}</h2><p class="muted">${esc(t(lang, "loading"))}</p>`;
    return;
  }
  const labels = data.narrativeRules.labels;
  const evMap = new Map(data.eventList.map((ev) => [ev.id, ev]));

  // Card width follows the layout column so fonts stay crisp at any size.
  const cw = el.clientWidth || 1140;
  const cols = cw >= 900 ? 2 : 1;
  const width = Math.max(300, Math.min(560, Math.floor((cw - (cols - 1) * 44) / cols) - 8));

  const cards = payload.narratives
    .map((narr) => {
      const claim = narr[lang] || narr.en || narr.zh || narr.id;
      const chip = verdictChip(narr.verdict, labels, lang);
      const hits = hitCount(narr.n_pos, narr.n_valid, lang);
      return `<figure class="ncard">
        <figcaption class="ncard-head">
          <span class="ncard-claim">${esc(claim)}</span>
          <span class="ncard-meta">${chip}${hits}</span>
        </figcaption>
        ${chartSvg(narr, lang, evMap, width)}
      </figure>`;
    })
    .join("");

  el.innerHTML = `
    <h2>${esc(t(lang, "det_title"))}</h2>
    <p class="section-note">${esc(t(lang, "det_note"))}</p>
    <div class="ngrid">${cards}</div>`;
}
