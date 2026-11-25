// Shared rendering helpers for the v3 narrative-test page.
// Everything here is presentation-only; verdicts and counts are computed by
// the engine and merely displayed.

import { t, ASSET_SHORT } from "./i18n.js";

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

export function assetName(data, id, lang) {
  const entry = data.assets[id];
  if (entry) return entry["name_" + lang] || id;
  const short = ASSET_SHORT[lang] && ASSET_SHORT[lang][id];
  return short || id;
}

export function eventName(ev, lang) {
  if (!ev) return "";
  return (lang === "zh" ? ev.name : ev.name_en) || ev.name || ev.name_en || ev.id;
}

// ------------------------------------------------------------- unit squares
//
// One square per event/date, chronological. Encoding:
//   valid & up            filled indigo       (u-up)
//   valid & down          hollow indigo ring  (u-down)
//   not_a_test            hatched gray        (u-na)
//   missing / incomplete  light gray          (u-miss)
//
// rows: narrative rows [{event, date, status, ret}]. nameFn(eventId) resolves
// display names for preset events; pseudo-events (event null) show the date.

function squareClass(row) {
  if (row.status === "valid") return row.ret > 0 ? "u-up" : "u-down";
  if (row.status === "not_a_test") return "u-na";
  return "u-miss";
}

function squareTip(row, lang, nameFn) {
  const name = row.event && nameFn ? nameFn(row.event) : null;
  const head = name ? `${row.date} ${name}` : row.date;
  if (row.status === "valid") return `${head}: ${fmtSigned(row.ret, 1)}%`;
  if (row.status === "not_a_test") return `${head}: ${t(lang, "tip_not_a_test")}`;
  return `${head}: ${t(lang, "tip_missing")}`;
}

export function unitSquares(rows, lang, nameFn) {
  const cells = rows
    .map((row) => {
      const cls = squareClass(row);
      const tip = squareTip(row, lang, nameFn);
      return `<span class="u ${cls}" title="${esc(tip)}"><span class="sr-only">${esc(tip)}</span></span>`;
    })
    .join("");
  return `<span class="units">${cells}</span>`;
}

// ------------------------------------------------------------------ chips --

// Verdict chip: labels come from narrative_rules.json, never hardcoded here.
export function verdictChip(verdict, labels, lang) {
  const label = labels && labels[verdict] ? labels[verdict][lang] : verdict;
  return `<span class="vchip v-${esc(verdict)}">${esc(label)}</span>`;
}

// Hit count "4/6" — raw counts straight from the aggregation.
export function hitCount(nPos, nValid, lang) {
  const aria = t(lang, "hit_aria", { n_pos: nPos, n_valid: nValid });
  return `<span class="hits" aria-label="${esc(aria)}"><b>${nPos}</b><i>/</i>${nValid}</span>`;
}

export function medianText(median) {
  return median === null || median === undefined ? "—" : `${fmtSigned(median, 1)}%`;
}
