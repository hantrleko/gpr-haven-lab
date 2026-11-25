// Rule-based v3 event reports (docs/methods/v3.md, rules/rules_v3.json).
// ES module mirror of src/havenlab/report_v3.py — keep the two in lockstep.
// No DOM access; runs in Node >= 18 and browsers.

const DAY_MS = 86400000;

function parseDay(text) {
  const parts = text.split("-");
  return Date.UTC(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2])) / DAY_MS;
}

function dayStr(day) {
  return new Date(day * DAY_MS).toISOString().slice(0, 10);
}

// Binary search on a sorted int array: last index with days[i] <= x (-1 if none).
function lastLE(days, x) {
  let lo = 0;
  let hi = days.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (days[mid] <= x) lo = mid + 1;
    else hi = mid;
  }
  return lo - 1;
}

// Last index with days[i] < x (-1 if none).
function lastLT(days, x) {
  let lo = 0;
  let hi = days.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (days[mid] < x) lo = mid + 1;
    else hi = mid;
  }
  return lo - 1;
}

// First index with days[i] > x (== count of elements <= x).
function firstGT(days, x) {
  return lastLE(days, x) + 1;
}

export function decodeSeries(payload) {
  const assets = {};
  for (const entry of payload.meta.assets) assets[entry.id] = entry;
  const series = {};
  for (const [assetId, enc] of Object.entries(payload.series)) {
    const days = [];
    let day = parseDay(enc.t0);
    for (const gap of enc.dt) {
      day += gap;
      days.push(day);
    }
    series[assetId] = { days, values: enc.v.map(Number) };
  }
  return { assets, series };
}

function makeCtx(decoded, rules) {
  return { assets: decoded.assets, series: decoded.series, rules, hist: {}, gprPref: null, rates: {} };
}

function assetName(ctx, assetId, lang) {
  const entry = ctx.assets[assetId];
  return entry ? entry["name_" + lang] : assetId;
}

function joinNames(names, lang, rules) {
  if (lang === "zh") return names.join(rules.list_join.zh);
  const lj = rules.list_join;
  if (names.length <= 1) return names.length ? names[0] : "";
  if (names.length === 2) return names[0] + lj.en_last + names[1];
  return names.slice(0, -1).join(lj.en) + lj.en_last + names[names.length - 1];
}

// ---------------------------------------------------------------------------
// windows, history, percentiles
// ---------------------------------------------------------------------------

function ret(pe, ps) {
  return 100 * Math.log(pe / ps);
}

function history(ctx, assetId, h) {
  const key = assetId + "|" + h;
  const cached = ctx.hist[key];
  if (cached !== undefined) return cached;
  const out = [];
  const ser = ctx.series[assetId];
  if (ser && ser.days.length) {
    const days = ser.days;
    const vals = ser.values;
    const lastDay = days[days.length - 1];
    for (let i = 0; i < days.length; i++) {
      const t = days[i];
      if (t + h > lastDay) break;
      const j = lastLE(days, t + h);
      out.push([t, ret(vals[j], vals[i])]);
    }
  }
  ctx.hist[key] = out;
  return out;
}

function windowCell(ctx, assetId, h, day) {
  const missing = { status: "missing", ret: null, pct: null, n: null, complete: null };
  const ser = ctx.series[assetId];
  if (!ser || !ser.days.length) return missing;
  const days = ser.days;
  const vals = ser.values;
  const s = lastLT(days, day);
  if (s < 0) return missing;
  const sDay = days[s];
  const lastDay = days[days.length - 1];
  if (sDay + h > lastDay) {
    return { status: "incomplete", ret: ret(vals[vals.length - 1], vals[s]), pct: null, n: null, complete: false };
  }
  const e = lastLE(days, sDay + h);
  const r = ret(vals[e], vals[s]);
  let less = 0;
  let equal = 0;
  let n = 0;
  for (const [t, rh] of history(ctx, assetId, h)) {
    if (Math.abs(t - sDay) <= h) continue;
    n += 1;
    if (rh < r) less += 1;
    else if (rh === r) equal += 1;
  }
  const pct = n ? (less + 0.5 * equal) / n : null;
  const status = n >= ctx.rules.min_history ? "ok" : "short_history";
  return { status, ret: r, pct, n, complete: true };
}

function labelCell(cell, k, rules) {
  const { ret: r, pct } = cell;
  const alpha = rules.family_alpha;
  if (r > 0) {
    if (pct >= 1 - alpha / k) return "clear_up";
    if (pct >= rules.lean_hi) return "lean_up";
    return "normal";
  }
  if (r < 0) {
    if (pct <= alpha / k) return "clear_down";
    if (pct <= rules.lean_lo) return "lean_down";
    return "normal";
  }
  return "normal";
}

function rateHavens(ctx, day) {
  const cached = ctx.rates[day];
  if (cached !== undefined) return cached;
  const rules = ctx.rules;
  const havens = rules.havens;
  const horizons = rules.horizons;
  const cells = {};
  for (const aid of havens) {
    for (const h of horizons) cells[aid + "|" + h] = windowCell(ctx, aid, h, day);
  }
  const k = {};
  for (const h of horizons) {
    k[h] = havens.reduce((acc, aid) => acc + (cells[aid + "|" + h].status === "ok" ? 1 : 0), 0);
  }
  const out = {};
  for (const aid of havens) {
    out[aid] = {};
    for (const h of horizons) {
      const cell = cells[aid + "|" + h];
      cell.label = cell.status === "ok" ? labelCell(cell, k[h], rules) : cell.status;
      out[aid][h] = cell;
    }
  }
  ctx.rates[day] = out;
  return out;
}

// ---------------------------------------------------------------------------
// sentence helpers
// ---------------------------------------------------------------------------

function fmtMag(x, d) {
  const p = Math.pow(10, d);
  const v = Math.floor(Math.abs(x) * p + 0.5) / p;
  return v.toFixed(d);
}

function roundsToZero(x, d) {
  return Math.floor(Math.abs(x) * Math.pow(10, d) + 0.5) === 0;
}

function fmtSigned(x, d) {
  const mag = fmtMag(x, d);
  if (roundsToZero(x, d)) return mag;
  return (x > 0 ? "+" : "-") + mag;
}

function pctInt(p) {
  return fmtMag(p * 100, 0);
}

function fill(text, mapping) {
  for (const [key, value] of Object.entries(mapping)) {
    text = text.split("{" + key + "}").join(String(value));
  }
  return text;
}

function dirKey(ret) {
  if (roundsToZero(ret, 1)) return "flat";
  return ret > 0 ? "up" : "down";
}

function retText(ret, lang) {
  return lang === "zh" ? fmtMag(Math.abs(ret), 1) : fmtSigned(ret, 1);
}

function rankText(p, lang, rules) {
  if (p < 0.5) return fill(rules.rank.weaker[lang], { x: fmtMag((1 - p) * 100, 0) });
  return fill(rules.rank.stronger[lang], { x: fmtMag(p * 100, 0) });
}

// ---------------------------------------------------------------------------
// report sections
// ---------------------------------------------------------------------------

function benchRow(ctx, benchmark, day) {
  const rules = ctx.rules;
  const primary = rules.primary;
  const cell = windowCell(ctx, benchmark, primary, day);
  const status = cell.status;
  if (status === "missing" || status === "short_history") {
    return { id: benchmark, ret: null, pct: null, state: "missing", complete: null, zh: null, en: null };
  }
  if (status === "incomplete") {
    return { id: benchmark, ret: cell.ret, pct: null, state: "incomplete", complete: false, zh: null, en: null };
  }
  const r = cell.ret;
  const pct = cell.pct;
  let state;
  if (r < 0 && pct <= rules.bench_drop_p) state = "clear_drop";
  else if (r < 0) state = "small_drop";
  else state = "no_drop";
  const row = { id: benchmark, ret: r, pct, state, complete: true, zh: null, en: null };
  const tmpl = rules.sentences.bench;
  for (const lang of ["zh", "en"]) {
    row[lang] = fill(tmpl[lang], {
      bench: assetName(ctx, benchmark, lang),
      dir: rules.dir_words[dirKey(r)][lang],
      ret: retText(r, lang),
      rank: rankText(pct, lang, rules),
      state: rules.bench_states[state][lang],
    });
  }
  return row;
}

function shockRow(ctx, assetId, day) {
  const rules = ctx.rules;
  const primary = rules.primary;
  const cell = windowCell(ctx, assetId, primary, day);
  const row = { id: assetId, ret: cell.ret, pct: cell.pct, complete: cell.complete, zh: null, en: null };
  if (cell.status === "ok") {
    const tmpl = rules.sentences.shock;
    for (const lang of ["zh", "en"]) {
      row[lang] = fill(tmpl[lang], {
        asset: assetName(ctx, assetId, lang),
        dir: rules.dir_words[dirKey(cell.ret)][lang],
        ret: retText(cell.ret, lang),
        rank: rankText(cell.pct, lang, rules),
      });
    }
  }
  return row;
}

function gprPref(ctx) {
  if (ctx.gprPref === null) {
    const ser = ctx.series.gpr;
    const pref = [0];
    for (const v of ser.values) pref.push(pref[pref.length - 1] + v);
    ctx.gprPref = pref;
  }
  return ctx.gprPref;
}

function gprSection(ctx, day, kind) {
  const rules = ctx.rules.gpr;
  const win = rules.window_days;
  const lookback = rules.lookback_days;
  const minDays = rules.min_days;
  const ser = ctx.series.gpr;
  const lastStr = ser && ser.days.length ? dayStr(ser.days[ser.days.length - 1]) : null;

  function insufficient(mean, start) {
    const tmpl = ctx.rules.sentences.pressure_insufficient;
    return {
      row: { state: "insufficient", pct: null, mean, start: start === undefined ? null : start, last: lastStr, zh: tmpl.zh, en: tmpl.en },
      meta: { lag: false },
    };
  }

  if (!ser || !ser.days.length) {
    const r = insufficient(null);
    return { row: r.row, meta: r.meta };
  }
  const days = ser.days;
  const sIdx = lastLT(days, day);
  if (sIdx < 0) {
    const r = insufficient(null);
    return { row: r.row, meta: r.meta };
  }
  const sG = days[sIdx];
  const pref = gprPref(ctx);
  const lo = firstGT(days, sG);
  const hi = lastLE(days, sG + win);
  const cnt = hi >= lo ? hi - lo + 1 : 0;
  const mean = cnt > 0 ? (pref[hi + 1] - pref[lo]) / cnt : null;
  const refs = [];
  const uLo = firstGT(days, sG - lookback);
  const uHi = lastLE(days, sG);
  for (let ui = uLo; ui <= uHi; ui++) {
    const u = days[ui];
    const rLo = firstGT(days, u - win);
    const rHi = lastLE(days, u);
    const rCnt = rHi >= rLo ? rHi - rLo + 1 : 0;
    if (rCnt >= minDays) refs.push((pref[rHi + 1] - pref[rLo]) / rCnt);
  }
  const lag = sG + win > days[days.length - 1];
  const meta = { lag };
  if (cnt < minDays || refs.length === 0) {
    const r = insufficient(mean, dayStr(sG));
    return { row: r.row, meta };
  }
  let less = 0;
  let equal = 0;
  for (const r of refs) {
    if (r < mean) less += 1;
    else if (r === mean) equal += 1;
  }
  const pct = (less + 0.5 * equal) / refs.length;
  const g = ctx.rules.gpr;
  let state;
  if (pct >= g.very_high) state = "very_high";
  else if (pct >= g.high) state = "high";
  else state = "normal";
  const row = { state, pct, mean, start: dayStr(sG), last: lastStr, zh: null, en: null };
  const tmplName = kind === "latest" ? "pressure_latest" : "pressure";
  for (const lang of ["zh", "en"]) {
    row[lang] = fill(ctx.rules.sentences[tmplName][lang], {
      gpr: fmtMag(mean, 1),
      pct: pctInt(pct),
      state: ctx.rules.gpr_states[state][lang],
    });
  }
  return { row, meta };
}

function headlineRow(ctx, rated, bench, benchmark, primary) {
  const rules = ctx.rules;
  const strong = rules.havens.filter((aid) => rated[aid][primary].label === "clear_up");
  const lean = rules.havens.filter((aid) => rated[aid][primary].label === "lean_up");
  const state = bench.state;
  let code;
  if (state === "missing") code = "no_bench";
  else if (state === "incomplete") code = "incomplete";
  else if (state === "no_drop") code = "no_drop";
  else if (state === "clear_drop" && strong.length) code = "clear_drop_clear";
  else if (state === "small_drop" && strong.length) code = "small_drop_clear";
  else if (!strong.length && lean.length >= 2) code = "drop_lean_many";
  else if (!strong.length && lean.length === 1) code = "drop_lean_one";
  else code = "drop_none";
  const entry = rules.headlines[code];
  const row = { code, grade: entry.grade, zh: null, en: null };
  for (const lang of ["zh", "en"]) {
    row[lang] = fill(entry[lang], {
      bench: assetName(ctx, benchmark, lang),
      clear: joinNames(strong.map((a) => assetName(ctx, a, lang)), lang, rules),
      lean: joinNames(lean.map((a) => assetName(ctx, a, lang)), lang, rules),
      clear_verb: rules.clear_verb[strong.length === 1 ? "one" : "many"].en,
    });
  }
  if (state === "clear_drop" || state === "small_drop") {
    const down = rules.havens.filter((aid) => rated[aid][primary].label === "clear_down");
    if (down.length) {
      const tail = rules.headline_down_tail;
      row.zh += fill(tail.zh, { down: joinNames(down.map((a) => assetName(ctx, a, "zh")), "zh", rules) });
      const enKey = down.length === 1 ? "en_one" : "en_many";
      row.en += " " + fill(tail[enKey], { down: joinNames(down.map((a) => assetName(ctx, a, "en")), "en", rules) });
    }
  }
  return row;
}

function evidenceRow(ctx, headline) {
  const tmpl = ctx.rules.sentences.evidence;
  const grade = headline.grade;
  return {
    grade,
    zh: fill(tmpl.zh, { grade: ctx.rules.grades[grade].zh }),
    en: fill(tmpl.en, { grade: ctx.rules.grades[grade].en }),
  };
}

const RATED_LABELS = ["clear_up", "lean_up", "normal", "lean_down", "clear_down"];

function caveatsList(ctx, kind, rated, bench, k, gmeta, gprLast) {
  const rules = ctx.rules;
  const primary = rules.primary;
  const out = [];

  function add(code, zhMap, enMap) {
    const entry = rules.caveats[code];
    zhMap = zhMap || {};
    enMap = enMap || zhMap;
    out.push({ code, zh: fill(entry.zh, zhMap), en: fill(entry.en, enMap) });
  }

  add("no_forecast");
  if (kind === "preset") add("hindsight_preset");
  else if (kind === "custom") add("hindsight_custom");
  const kPrimary = k[primary];
  if (kPrimary > 1) {
    add("multi", { k: kPrimary, top: fmtMag((rules.family_alpha / kPrimary) * 100, 1) });
  }
  const havenIncomplete = rules.havens.some((a) => rated[a][primary].label === "incomplete");
  if (bench.state === "incomplete" || havenIncomplete) add("incomplete");
  const unrated = rules.havens.filter((a) => rated[a][primary].label === "short_history" || rated[a][primary].label === "missing");
  if (unrated.length) {
    add(
      "unrated",
      { assets: joinNames(unrated.map((a) => assetName(ctx, a, "zh")), "zh", rules) },
      { assets: joinNames(unrated.map((a) => assetName(ctx, a, "en")), "en", rules) },
    );
  }
  const futures = rules.futures_note_assets.filter((a) => ctx.series[a] && ctx.series[a].days.length);
  if (futures.length) {
    add(
      "futures",
      { assets: joinNames(futures.map((a) => assetName(ctx, a, "zh")), "zh", rules) },
      { assets: joinNames(futures.map((a) => assetName(ctx, a, "en")), "en", rules) },
    );
  }
  if (gmeta.lag && gprLast) add("gpr_lag", { last: gprLast });
  if (bench.state === "no_drop") {
    add("no_test", { bench: assetName(ctx, bench.id, "zh") }, { bench: assetName(ctx, bench.id, "en") });
  }
  return out;
}

function historyRows(ctx, events, excludeEventId) {
  const rules = ctx.rules;
  const primary = rules.primary;
  const eventDays = [];
  for (const event of events) {
    if (event.id === excludeEventId) continue;
    eventDays.push(parseDay(event.date));
  }
  const out = [];
  for (const aid of rules.havens) {
    const counts = {};
    for (const label of RATED_LABELS) counts[label] = 0;
    const rets = [];
    for (const day of eventDays) {
      const cell = rateHavens(ctx, day)[aid][primary];
      const label = cell.label;
      if (Object.prototype.hasOwnProperty.call(counts, label)) {
        counts[label] += 1;
        rets.push(cell.ret);
      }
    }
    const n = rets.length;
    const row = {
      id: aid,
      n,
      clear_up: counts.clear_up,
      lean_up: counts.lean_up,
      normal: counts.normal,
      lean_down: counts.lean_down,
      clear_down: counts.clear_down,
      median: null,
      zh: null,
      en: null,
    };
    if (n === 0) {
      const tmpl = rules.sentences.history_none;
      row.zh = fill(tmpl.zh, { asset: assetName(ctx, aid, "zh") });
      row.en = fill(tmpl.en, { asset: assetName(ctx, aid, "en") });
    } else {
      rets.sort((a, b) => a - b);
      const median = n % 2 ? rets[(n / 2) | 0] : (rets[n / 2 - 1] + rets[n / 2]) / 2;
      row.median = median;
      const tmpl = rules.sentences.history_row;
      for (const lang of ["zh", "en"]) {
        row[lang] = fill(tmpl[lang], {
          n,
          asset: assetName(ctx, aid, lang),
          clear: counts.clear_up,
          lean: counts.lean_up,
          median: fmtSigned(median, 1),
        });
      }
    }
    out.push(row);
  }
  return out;
}

// ---------------------------------------------------------------------------
// public API
// ---------------------------------------------------------------------------

function report(ctx, events, date, benchmark, kind, excludeEventId) {
  const rules = ctx.rules;
  let day;
  let dateStr;
  if (kind === "latest") {
    const days = ctx.series[benchmark].days;
    day = days[days.length - 1] - rules.latest_days;
    dateStr = dayStr(day);
  } else if (typeof date === "number") {
    day = date;
    dateStr = dayStr(day);
  } else {
    dateStr = date;
    day = parseDay(date);
  }
  const primary = rules.primary;
  const rated = rateHavens(ctx, day);
  const k = {};
  for (const h of rules.horizons) {
    k[h] = rules.havens.reduce((acc, aid) => acc + (rated[aid][h].status === "ok" ? 1 : 0), 0);
  }
  const bench = benchRow(ctx, benchmark, day);
  const shocks = [];
  for (const sid of rules.shocks) {
    const ser = ctx.series[sid];
    if (ser && ser.days.length) shocks.push(shockRow(ctx, sid, day));
  }
  const { row: pressure, meta: gmeta } = gprSection(ctx, day, kind);
  const headline = headlineRow(ctx, rated, bench, benchmark, primary);
  const history = historyRows(ctx, events, excludeEventId);
  const caveats = caveatsList(ctx, kind, rated, bench, k, gmeta, pressure.last);
  const evidence = evidenceRow(ctx, headline);
  const havens = [];
  for (const aid of rules.havens) {
    const byH = {};
    for (const h of rules.horizons) {
      const cell = rated[aid][h];
      byH[String(h)] = { ret: cell.ret, pct: cell.pct, label: cell.label, complete: cell.complete, n: cell.n };
    }
    havens.push({ id: aid, by_h: byH });
  }
  return {
    date: dateStr,
    kind,
    benchmark,
    rules_version: rules.version,
    headline,
    pressure,
    bench,
    shock: shocks,
    havens,
    k: Object.fromEntries(rules.horizons.map((h) => [String(h), k[h]])),
    history,
    evidence,
    caveats,
  };
}

export function buildReport(series, rules, events, opts = {}) {
  const ctx = makeCtx(series, rules);
  return report(
    ctx,
    events,
    opts.date,
    opts.benchmark,
    opts.kind || "custom",
    opts.excludeEventId !== undefined ? opts.excludeEventId : opts.exclude_event_id,
  );
}

export function buildAllReports(payload, rules, events) {
  const decoded = decodeSeries(payload);
  const ctx = makeCtx(decoded, rules);
  const benches = rules.benchmarks.filter((b) => decoded.series[b] && decoded.series[b].days.length);
  const out = {
    rules_version: rules.version,
    built: payload.meta.built,
    latest: {},
    events: {},
    event_list: events.map((e) => ({ id: e.id, date: e.date, name: e.name ?? null, name_en: e.name_en ?? null })),
  };
  for (const bench of benches) {
    out.latest[bench] = report(ctx, events, null, bench, "latest", null);
  }
  for (const event of events) {
    out.events[event.id] = {};
    for (const bench of benches) {
      out.events[event.id][bench] = report(ctx, events, event.date, bench, "preset", event.id);
    }
  }
  return out;
}
