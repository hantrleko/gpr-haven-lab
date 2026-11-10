function claimIntervalTail(input, low, high) {
  const pct = input.pct;
  if (pct == null || !isFinite(Number(pct))) return false;
  const lo = input.pct_lo == null ? Number(pct) : Number(input.pct_lo);
  const hi = input.pct_hi == null ? Number(pct) : Number(input.pct_hi);
  const cutLo = low == null ? 0.20 : low;
  const cutHi = high == null ? 0.80 : high;
  return (lo > 0 && hi <= cutLo) || (lo >= cutHi && hi < 1);
}
function claimRule(input) {
  const g = input.g;
  const c = input.c;
  const b = input.b;
  const en = input.lang === "en";
  const pct = input.pct;
  const q = input.q;
  const tailOk = claimIntervalTail(input);
  const mid = pct != null && !tailOk;
  const qFail = q != null && q > 0.10;
  const qText = q == null ? "" : (Math.round(Number(q) * 100) / 100).toFixed(2);
  let tone = "";
  let claim = en
    ? "These price paths do not point in one direction. "
    : "这组价格路径没有呈现单一方向。";
  const carFail = en
    ? "The gold CAR over the five sessions from the event day does not pass the multiple-comparison correction (q=" + qText + "). "
    : "事件日起 5 个交易日的黄金 CAR 未通过多重比较校正（q=" + qText + "）。";
  const carPass = en
    ? "The gold CAR q-value over the five sessions after the event is " + qText + ". "
    : "事件后 5 个交易日黄金 CAR 的 q 值为 " + qText + "。";
  if (input.anchorIsGold && g > 0 && c < 0 && input.showCsi) {
    const tail = tailOk;
    if (tail && !qFail) {
      claim = en
        ? "Gold rises while CSI 300 falls, which matches a safe-haven split in prices. "
        : "黄金上涨而沪深300下跌，价格路径与避险分流一致。";
      if (q != null) claim += carPass;
    } else if (qFail) {
      tone = "warn";
      const midBit = mid
        ? (en ? " The gold cumulative return sits in the middle of ordinary months." : "黄金累计收益落在普通月份的中间分位。")
        : "";
      claim = (en ? "Gold rises while CSI 300 falls." : "黄金上涨而沪深300下跌。") + midBit + carFail;
    } else if (pct == null) {
      tone = "warn";
      claim = en
        ? "Gold rises while CSI 300 falls. No ordinary-month percentile is available, so the paths are described without a split reading. "
        : "黄金上涨而沪深300下跌。没有普通月份分位，这次价格分开只按路径描述。";
    } else {
      tone = "warn";
      claim = en
        ? "Gold rises while CSI 300 falls, but the gold cumulative return sits in the middle of ordinary months, so the price split stays a path description. "
        : "黄金上涨而沪深300下跌，但黄金累计收益落在普通月份的中间分位，这次价格分开只按路径描述。";
      if (q != null) claim += carPass;
    }
  } else if (input.anchorIsGold && b > 0 && g < 0 && input.showBrent) {
    tone = "warn";
    claim = qFail
      ? (en ? "Brent rises while gold falls, so gold does not rise in this window. " : "布伦特上涨而黄金下跌，这段窗口里黄金没有上涨。")
      : (en ? "Brent rises while gold falls, so gold does not show the usual safe-haven rise in this window. " : "布伦特上涨而黄金下跌，这段窗口里黄金没有表现出典型的避险上涨。");
    if (qFail) claim += carFail;
  } else if (input.anchorIsGold && g < 0 && c < 0 && input.showCsi) {
    tone = "bad";
    claim = qFail
      ? (en ? "Gold and CSI 300 fall together, which looks more like tighter liquidity and real rates. " : "黄金与沪深300同时下跌，更像流动性和实际利率一起抽紧。")
      : (en ? "Gold and CSI 300 fall together, which looks more like tighter liquidity and real rates than gold alone taking the haven bid. " : "黄金与沪深300同时下跌，更像流动性和实际利率一起抽紧，而不是黄金单独承接避险买盘。");
    if (qFail) claim += carFail;
  } else if (input.anchorIsGold && g > 0 && c > 0 && input.showCsi) {
    if (qFail) {
      claim = en
        ? "Gold and CSI 300 rise together, so the two prices do not move apart. "
        : "黄金与沪深300同时上涨，两边价格没有反向分开。";
      claim += carFail;
    } else {
      claim = en
        ? "Gold and CSI 300 rise together, so the haven asset and the risk asset do not split. "
        : "黄金与沪深300同时上涨，避险资产和风险资产没有反向分开。";
    }
  } else if (qFail) {
    claim += carFail;
  }
  if (input.exploratory) claim = (en ? "[Exploratory] " : "[探索性]") + claim;
  return {tone: tone, claim: claim};
}
