// Monthly GPR pressure stripes: one stripe per month, colored by that
// month's mean daily GPR percentile across the full monthly history.
// UI-only descriptive coloring — it feeds no rating.

const STOPS = [
  [0.0, [220, 230, 238]], // #DCE6EE
  [0.5, [143, 169, 196]], // #8FA9C4
  [0.85, [61, 79, 143]], // #3D4F8F
  [1.0, [122, 31, 61]], // #7A1F3D
];

function stripeColor(p) {
  let i = 0;
  while (i < STOPS.length - 2 && p > STOPS[i + 1][0]) i += 1;
  const [p0, c0] = STOPS[i];
  const [p1, c1] = STOPS[i + 1];
  const f = p1 === p0 ? 0 : (p - p0) / (p1 - p0);
  const mix = c0.map((v, j) => Math.round(v + (c1[j] - v) * f));
  return `rgb(${mix[0]},${mix[1]},${mix[2]})`;
}

function monthKey(day) {
  return new Date(day * 86400000).toISOString().slice(0, 7);
}

// -> [{key:"YYYY-MM", mean, pct}] chronological
export function monthlyGpr(gpr) {
  const buckets = new Map();
  const days = gpr.days;
  const vals = gpr.values;
  for (let i = 0; i < days.length; i += 1) {
    const key = monthKey(days[i]);
    const b = buckets.get(key) || { sum: 0, n: 0 };
    b.sum += vals[i];
    b.n += 1;
    buckets.set(key, b);
  }
  const keys = [...buckets.keys()].sort();
  const means = keys.map((k) => buckets.get(k).sum / buckets.get(k).n);
  const n = means.length;
  return keys.map((key, i) => {
    const m = means[i];
    let less = 0;
    let equal = 0;
    for (const o of means) {
      if (o < m) less += 1;
      else if (o === m) equal += 1;
    }
    return { key, mean: m, pct: (less + 0.5 * equal) / n };
  });
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// months: output of monthlyGpr; markerIdx: index into months (-1 for none).
export function stripesSvg(months, markerIdx, ariaLabel) {
  const W = 1000;
  const H = 96;
  const stripeH = 68;
  const n = months.length;
  const w = W / n;
  const parts = [
    `<svg class="stripes" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(ariaLabel)}">`,
    `<rect x="0" y="0" width="${W}" height="${stripeH}" fill="#F5F7F8"/>`,
    `<g class="stripes-draw">`,
  ];
  for (let i = 0; i < n; i += 1) {
    parts.push(
      `<rect x="${(i * w).toFixed(2)}" y="0" width="${(w * 0.94).toFixed(2)}" height="${stripeH}" fill="${stripeColor(months[i].pct)}"/>`,
    );
  }
  parts.push(`</g>`);
  if (markerIdx >= 0 && markerIdx < n) {
    const cx = markerIdx * w + w / 2;
    const lx = Math.min(Math.max(cx, 34), W - 34);
    parts.push(
      `<rect class="stripe-marker" x="${(cx - w * 0.9).toFixed(2)}" y="-4" width="${(w * 1.8).toFixed(2)}" height="${stripeH + 8}" fill="#7A1F3D"/>`,
      `<text x="${lx.toFixed(1)}" y="88" text-anchor="middle" font-size="11" fill="#1B2430">${esc(months[markerIdx].key)}</text>`,
    );
  }
  parts.push(`</svg>`);
  return parts.join("");
}

export function monthIndexOf(months, isoDate) {
  const key = isoDate.slice(0, 7);
  return months.findIndex((m) => m.key === key);
}
