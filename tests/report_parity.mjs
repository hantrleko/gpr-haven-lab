// Parity driver: node tests/report_parity.mjs <series.json> <rules.json> <events.json> <narrative_rules.json> <custom_spec.json> <out.json>
import { readFileSync, writeFileSync } from "node:fs";
import { buildAllNarratives, buildAllReports, buildCustomNarrative, decodeSeries, makeCtx } from "../src/havenlab/v3/report.js";

const [, , seriesPath, rulesPath, eventsPath, nrulesPath, customPath, outPath] = process.argv;
const payload = JSON.parse(readFileSync(seriesPath, "utf8"));
const rules = JSON.parse(readFileSync(rulesPath, "utf8"));
const events = JSON.parse(readFileSync(eventsPath, "utf8"));
const nrules = JSON.parse(readFileSync(nrulesPath, "utf8"));
const customSpecs = JSON.parse(readFileSync(customPath, "utf8"));
const decoded = decodeSeries(payload);
const ctx = makeCtx(decoded, rules);
ctx.narrativeRules = nrules;
const out = {
  reports: buildAllReports(payload, rules, events),
  narratives: buildAllNarratives(payload, rules, nrules, events),
  custom: customSpecs.map((spec) => buildCustomNarrative(ctx, spec.dates, spec.asset_ids, spec.bench_id)),
};
writeFileSync(outPath, JSON.stringify(out));
