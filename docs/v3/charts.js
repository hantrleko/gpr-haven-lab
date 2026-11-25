// Daily GPR line for the 30-day pressure window: 90 days before the window
// start through the window end, window shaded.

function parseIso(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 86400000;
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// gpr: {days, values}; startISO: pressure.start (s_G); winDays: window length.
export function gprChartSvg(gpr, startISO, winDays, ariaLabel) {
  if (!gpr || !gpr.days.length || !startISO) return "";
  const sG = parseIso(startISO);
  const first = gpr.days[0];
  const last = gpr.days[gpr.days.length - 1];
  const x0 = Math.max(first, sG - 90);
  const x1 = Math.min(last, sG + winDays);
  if (x1 <= x0) return "";
  const W = 640;
  const H = 150;
  const padL = 34;
  const padR = 8;
  const padT = 10;
  const padB = 22;
  const iw = W - padL - padR;
  const ih = H - padT - padB;
  const X = (d) => padL + ((d - x0) / (x1 - x0)) * iw;
  let lo = Infinity;
  let hi = -Infinity;
  const pts = [];
  for (let i = 0; i < gpr.days.length; i += 1) {
    const d = gpr.days[i];
    if (d < x0 || d > x1) continue;
    const v = gpr.values[i];
    if (v < lo) lo = v;
    if (v > hi) hi = v;
    pts.push([d, v]);
  }
  if (pts.length < 2) return "";
  const span = hi - lo || 1;
  lo -= span * 0.08;
  hi += span * 0.08;
  const Y = (v) => padT + ih - ((v - lo) / (hi - lo)) * ih;
  const line = pts.map(([d, v], i) => `${i ? "L" : "M"}${X(d).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const shadeL = X(Math.max(x0, sG));
  const shadeR = X(Math.min(x1, sG + winDays));
  const iso = (d) => new Date(d * 86400000).toISOString().slice(0, 10);
  const parts = [
    `<svg class="gpr-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(ariaLabel)}">`,
    `<rect x="${shadeL.toFixed(1)}" y="${padT}" width="${(shadeR - shadeL).toFixed(1)}" height="${ih}" fill="#DCE6EE" opacity="0.55"/>`,
    `<line x1="${shadeL.toFixed(1)}" y1="${padT}" x2="${shadeL.toFixed(1)}" y2="${padT + ih}" stroke="#5B6676" stroke-width="1" stroke-dasharray="3 3"/>`,
    `<line x1="${shadeR.toFixed(1)}" y1="${padT}" x2="${shadeR.toFixed(1)}" y2="${padT + ih}" stroke="#5B6676" stroke-width="1" stroke-dasharray="3 3"/>`,
    `<path d="${line}" fill="none" stroke="#3D4F8F" stroke-width="1.6" vector-effect="non-scaling-stroke"/>`,
    `<text x="${padL}" y="${H - 6}" font-size="10" fill="#5B6676">${esc(iso(x0))}</text>`,
    `<text x="${W - padR}" y="${H - 6}" font-size="10" fill="#5B6676" text-anchor="end">${esc(iso(x1))}</text>`,
    `</svg>`,
  ];
  return parts.join("");
}
