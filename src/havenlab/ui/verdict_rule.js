function verdictText(input) {
  const en = input.lang === "en";
  const allowed = [];
  const pathOnly = [];
  const down = [];
  const other = [];
  const partial = [];
  (input.events || []).forEach(event => {
    if (event.g == null || !isFinite(event.g)) return;
    if (event.partial) {
      partial.push(event.name);
      return;
    }
    if (event.g > 0 && event.c != null && event.c < 0) {
      const judged = claimRule({
        g: event.g,
        c: event.c,
        b: event.b == null ? 0 : event.b,
        anchorIsGold: true,
        showCsi: true,
        showBrent: true,
        pct: event.pct == null ? null : event.pct,
        q: event.q == null ? null : event.q,
        lang: input.lang,
      });
      const mark = en ? "safe-haven split" : "避险分流";
      if (judged.claim.indexOf(mark) >= 0) allowed.push(event.name);
      else pathOnly.push(event.name);
      return;
    }
    if (event.g < 0) down.push(event.name);
    else other.push(event.name);
  });
  const join = list => list.length ? list.join(en ? "; " : "、") : (en ? "none" : "没有");
  let text = en
    ? "At the selected " + input.width + "-month window"
    : "按当前 " + input.width + " 个月窗口";
  if (allowed.length) {
    text += en
      ? ", the safe-haven split wording applies to: " + join(allowed)
      : "，可以写成避险分流的是：" + join(allowed);
  }
  text += en
    ? ". Gold rose while CSI 300 fell, described only as a price path, for: " + join(pathOnly) + ". Gold itself fell for: " + join(down) + ". The rest did not split: " + join(other) + ". Incomplete windows are left out of those lists"
    : "。黄金上涨且沪深300下跌、只按价格路径描述的是：" + join(pathOnly) + "。黄金本身下跌的是：" + join(down) + "。其余没有反向分开：" + join(other) + "。不完整的窗口不放进这几句";
  if (partial.length) text += en ? " (" + partial.join("; ") + ")" : "（" + partial.join("、") + "）";
  text += en ? ". " : "。";
  if (input.nEvents != null && input.nMideast != null) {
    text += en
      ? input.nMideast + " of " + input.nEvents + " built-in dates are tagged Middle East, and all of them were chosen after the prices were known. "
      : input.nEvents + " 个内置日期里有 " + input.nMideast + " 个标成中东，而且都是事后挑选的。";
  }
  const pack = input.placebo;
  if (pack) {
    text += en
      ? "The gold percentile uses " + pack.n_draw + " ordinary months drawn from " + pack.n_pool + " complete windows that do not contain an event month, seed " + pack.seed + "."
      : "分位见总表最后一列，用的是种子 " + pack.seed + " 抽出的 " + pack.n_draw + " 个普通月份，母体是 " + pack.n_pool + " 个不包含事件月的完整窗口。";
  }
  return text;
}
