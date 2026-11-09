const fs = require("fs");
const vm = require("vm");

const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync("src/havenlab/ui/claim_rule.js", "utf8"), context);
vm.runInContext(fs.readFileSync("src/havenlab/ui/verdict_rule.js", "utf8"), context);

function assertOk(cond, message) {
  if (!cond) {
    console.error(message);
    process.exit(1);
  }
}

const mid = context.verdictText({
  lang: "zh",
  width: 6,
  events: [{name: "甲", g: 10, c: -5, pct: 0.55, q: null, partial: false}],
});
assertOk(!mid.includes("避险分流"), "middle percentile paragraph must not say 避险分流: " + mid);
assertOk(mid.includes("甲"), "middle percentile event should be named: " + mid);
assertOk(mid.includes("只按价格路径描述"), "middle percentile event should stay a path description: " + mid);
assertOk(mid.indexOf("甲") > mid.indexOf("只按价格路径描述"), "middle percentile name belongs in the path sentence: " + mid);

const tail = context.verdictText({
  lang: "zh",
  width: 6,
  events: [{name: "乙", g: 10, c: -5, pct: 0.95, q: 0.04, partial: false}],
});
assertOk(tail.includes("避险分流"), "tail percentile should keep 避险分流: " + tail);
assertOk(tail.indexOf("乙") < tail.indexOf("只按价格路径描述"), "tail percentile name belongs in the split sentence: " + tail);

console.log("verdict_rule ok");
