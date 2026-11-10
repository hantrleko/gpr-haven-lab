const fs = require("fs");
const vm = require("vm");

const code = fs.readFileSync("src/havenlab/ui/claim_rule.js", "utf8");
const context = {};
vm.createContext(context);
vm.runInContext(code, context);

function assertOk(cond, message) {
  if (!cond) {
    console.error(message);
    process.exit(1);
  }
}

const mid = context.claimRule({
  g: 10, c: -5, b: 0,
  anchorIsGold: true, showCsi: true, showBrent: true,
  pct: 0.55, q: null, lang: "zh",
});
assertOk(!mid.claim.includes("避险分流"), "middle percentile must not say 避险分流: " + mid.claim);

const tail = context.claimRule({
  g: 10, c: -5, b: 0,
  anchorIsGold: true, showCsi: true, showBrent: true,
  pct: 0.95, q: 0.04, lang: "zh",
});
assertOk(tail.claim.includes("避险分流"), "tail percentile should keep the split wording: " + tail.claim);
assertOk(tail.claim.includes("0.04"), "tail percentile should include q: " + tail.claim);

const failed = context.claimRule({
  g: 10, c: -5, b: 0,
  anchorIsGold: true, showCsi: true, showBrent: true,
  pct: 0.95, q: 0.2, lang: "zh",
});
assertOk(!failed.claim.includes("避险"), "failed q must not use 避险: " + failed.claim);
assertOk(failed.claim.includes("未通过多重比较校正"), "failed q must name the correction: " + failed.claim);

const crossing = context.claimRule({
  g: 10, c: -5, b: 0,
  anchorIsGold: true, showCsi: true, showBrent: true,
  pct: 0.18, pct_lo: 0.03, pct_hi: 0.34, q: 0.04, lang: "zh",
});
assertOk(!crossing.claim.includes("避险分流"), "an interval that leaves the tail must not say 避险分流: " + crossing.claim);

const inside = context.claimRule({
  g: 10, c: -5, b: 0,
  anchorIsGold: true, showCsi: true, showBrent: true,
  pct: 0.92, pct_lo: 0.85, pct_hi: 0.97, q: 0.04, lang: "zh",
});
assertOk(inside.claim.includes("避险分流"), "a whole interval in the tail should say 避险分流: " + inside.claim);

const explore = context.claimRule({
  g: 10, c: -5, b: 0,
  anchorIsGold: true, showCsi: true, showBrent: true,
  pct: 0.55, q: null, lang: "zh", exploratory: true,
});
assertOk(explore.claim.startsWith("[探索性]"), "exploratory prefix missing: " + explore.claim);

console.log("claim_rule ok");
