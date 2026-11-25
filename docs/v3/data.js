// Loading and decoding for the v3 page: manifest, precomputed reports,
// rules, then the (large) series payload used for stripes, charts and
// custom-date reports.

import { decodeSeries } from "./report.js";

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(url);
  return res.json();
}

export class V3Data {
  constructor(base = "") {
    this.base = base;
    this.manifest = null;
    this.reports = null;
    this.rules = null;
    this.payload = null;
    this.decoded = null;
    this.eventList = [];
    this.benches = [];
    this.assets = {};
    this.gprMeta = null;
  }

  // reports.json + rules.json — enough for latest and preset reports.
  async loadCore() {
    this.manifest = await fetchJson(this.base + "manifest.json");
    const [reports, rules] = await Promise.all([
      fetchJson(this.base + "reports.json"),
      fetchJson(this.base + "rules.json"),
    ]);
    this.reports = reports;
    this.rules = rules;
    this.eventList = Array.isArray(reports.event_list) ? reports.event_list : [];
    this.benches = Object.keys(reports.latest || {});
    return this;
  }

  // series.json — needed for the stripes, the GPR chart and custom dates.
  async loadSeries() {
    this.payload = await fetchJson(this.base + "series.json");
    this.decoded = decodeSeries(this.payload);
    this.assets = this.decoded.assets;
    this.gprMeta = this.payload.meta && this.payload.meta.gpr ? this.payload.meta.gpr[0] : null;
    return this;
  }

  benchLast(bench) {
    const entry = this.assets[bench];
    return entry && entry.last ? entry.last : null;
  }

  gprSeries() {
    return this.decoded && this.decoded.series.gpr ? this.decoded.series.gpr : null;
  }
}
