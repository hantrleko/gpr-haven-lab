// Hero + narrative scoreboard: the page's core graphic.
// Every number here is computed from narratives.json at render time — the
// headline count, the hit fractions, the medians, the unit squares. Nothing
// is hardcoded.

import { t } from "./i18n.js";
import { esc, fmtSigned, eventName, unitSquares, verdictChip, hitCount, medianText } from "./util.js";

function chronoRows(narr) {
  return [...narr.rows].sort((a, b) => (a.date < b.date ? -1 : 1));
}

// The structural fact: of the frozen events, in how many did the benchmark
// actually fall over the event month. All narratives share the same event
// list and benchmark, so any row set answers it; use the first.
export function structuralCount(narrativesPayload) {
  const first = narrativesPayload.narratives[0];
  const rows = first ? first.rows : [];
  const total = rows.length;
  const n = rows.filter((r) => r.bench_ret !== null && r.bench_ret !== undefined && r.bench_ret < 0).length;
  return { n, total };
}

function heroHeadline(lang, n, total) {
  // Only the key structural number is claret; the total stays ink.
  let html = t(lang, "hero_headline");
  html = html.split("{total}").join(`<span class="keynum-total">${total}</span>`);
  html = html.split("{n}").join(`<span class="keynum">${n}</span>`);
  return html; // authored template + integers — no user input reaches this
}

export function renderHero(el, data, lang) {
  const payload = data.narratives;
  if (!payload || !payload.narratives.length) {
    el.innerHTML = `<h1 class="hero-title muted">${esc(t(lang, "loading"))}</h1>`;
    return;
  }
  const { n, total } = structuralCount(payload);
  const k = payload.narratives.length;
  const labels = data.narrativeRules.labels;

  const evMap = new Map(data.eventList.map((ev) => [ev.id, ev]));
  const nameFn = (id) => {
    const ev = evMap.get(id);
    return ev ? eventName(ev, lang) : id;
  };

  const headCells = [
    `<span class="sb-claim">${esc(t(lang, "col_claim"))}</span>`,
    `<span class="sb-verdict">${esc(t(lang, "col_verdict"))}</span>`,
    `<span class="sb-hits">${esc(t(lang, "col_hits"))}</span>`,
    `<span class="sb-median">${esc(t(lang, "col_median"))}</span>`,
    `<span class="sb-events">${esc(t(lang, "col_events", { total }))}</span>`,
  ].join("");

  const rows = payload.narratives
    .map((narr) => {
      const claim = narr[lang] || narr.en || narr.zh || narr.id;
      const chip = verdictChip(narr.verdict, labels, lang);
      const hits = hitCount(narr.n_pos, narr.n_valid, lang);
      const med = medianText(narr.median);
      const units = unitSquares(chronoRows(narr), lang, nameFn);
      return `<div class="sb-row" data-narr="${esc(narr.id)}">
        <span class="sb-claim">${esc(claim)}</span>
        <span class="sb-verdict">${chip}</span>
        <span class="sb-hits">${hits}</span>
        <span class="sb-median num">${esc(med)}</span>
        <span class="sb-events">${units}</span>
      </div>`;
    })
    .join("");

  const key = `<p class="unit-key">${esc(t(lang, "key_intro"))}
    <span class="kg"><span class="u u-up"></span>${esc(t(lang, "key_up"))}</span>
    <span class="kg"><span class="u u-down"></span>${esc(t(lang, "key_down"))}</span>
    <span class="kg"><span class="u u-na"></span>${esc(t(lang, "key_na"))}</span>
    <span class="kg"><span class="u u-miss"></span>${esc(t(lang, "key_miss"))}</span>
  </p>`;

  el.innerHTML = `
    <h1 class="hero-title">${heroHeadline(lang, n, total)}</h1>
    <p class="hero-deck">${esc(t(lang, "hero_deck", { k }))}</p>
    ${key}
    <div class="scoreboard" aria-label="${esc(t(lang, "col_events", { total }))}">
      <div class="sb-row sb-head">${headCells}</div>
      ${rows}
    </div>`;
}

// --------------------------------------------------------- methods strip --

export function renderMethods(el, data, lang) {
  const minTests = data.narrativeRules.min_tests;
  const bullets = ["ms_b1", "ms_b2", "ms_b3", "ms_b4"]
    .map((key) => `<li>${esc(t(lang, key, { min_tests: minTests }))}</li>`)
    .join("");
  el.innerHTML = `
    <h2 class="strip-title">${esc(t(lang, "ms_title"))}</h2>
    <ul class="ms-list">${bullets}</ul>
    <p class="ms-more"><a href="https://github.com/hantrleko/gpr-haven-lab/blob/main/docs/methods/v3.md" rel="noopener">${esc(t(lang, "ms_link"))}</a></p>`;
}
