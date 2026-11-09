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

console.log("claim_rule ok");
