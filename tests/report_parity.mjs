// Parity driver: node tests/report_parity.mjs <series.json> <rules.json> <events.json> <out.json>
import { readFileSync, writeFileSync } from "node:fs";
import { buildAllReports } from "../src/havenlab/v3/report.js";

const [, , seriesPath, rulesPath, eventsPath, outPath] = process.argv;
const payload = JSON.parse(readFileSync(seriesPath, "utf8"));
const rules = JSON.parse(readFileSync(rulesPath, "utf8"));
const events = JSON.parse(readFileSync(eventsPath, "utf8"));
const out = buildAllReports(payload, rules, events);
writeFileSync(outPath, JSON.stringify(out));
