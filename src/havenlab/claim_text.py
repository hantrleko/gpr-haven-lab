"""Python mirror of src/havenlab/ui/claim_rule.js. Keep the two in lockstep."""

from __future__ import annotations

import math


def _q_text(q) -> str:
    if q is None:
        return ""
    return f"{math.floor(float(q) * 100 + 0.5) / 100:.2f}"


def interval_tail(pct, pct_lo=None, pct_hi=None, low: float = 0.20, high: float = 0.80) -> bool:
    if pct is None:
        return False
    try:
        point = float(pct)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(point):
        return False
    lo = point if pct_lo is None else float(pct_lo)
    hi = point if pct_hi is None else float(pct_hi)
    return (lo > 0 and hi <= low) or (lo >= high and hi < 1)


def claim_rule(payload: dict) -> dict:
    g = payload.get("g")
    c = payload.get("c")
    b = payload.get("b")
    en = payload.get("lang") == "en"
    pct = payload.get("pct")
    q = payload.get("q")
    tail_ok = interval_tail(pct, payload.get("pct_lo"), payload.get("pct_hi"))
    mid = pct is not None and not tail_ok
    q_fail = q is not None and float(q) > 0.10
    q_text = _q_text(q)
    tone = ""
    claim = (
        "These price paths do not point in one direction. "
        if en
        else "这组价格路径没有呈现单一方向。"
    )
    car_fail = (
        f"The gold CAR over the five sessions from the event day does not pass the multiple-comparison correction (q={q_text}). "
        if en
        else f"事件日起 5 个交易日的黄金 CAR 未通过多重比较校正（q={q_text}）。"
    )
    car_pass = (
        f"The gold CAR q-value over the five sessions after the event is {q_text}. "
        if en
        else f"事件后 5 个交易日黄金 CAR 的 q 值为 {q_text}。"
    )
    if payload.get("anchorIsGold") and g is not None and c is not None and g > 0 and c < 0 and payload.get("showCsi"):
        if tail_ok and not q_fail:
            claim = (
                "Gold rises while CSI 300 falls, which matches a safe-haven split in prices. "
                if en
                else "黄金上涨而沪深300下跌，价格路径与避险分流一致。"
            )
            if q is not None:
                claim += car_pass
        elif q_fail:
            tone = "warn"
            mid_bit = (
                (" The gold cumulative return sits in the middle of ordinary months." if en else "黄金累计收益落在普通月份的中间分位。")
                if mid
                else ""
            )
            claim = ("Gold rises while CSI 300 falls." if en else "黄金上涨而沪深300下跌。") + mid_bit + car_fail
        elif pct is None:
            tone = "warn"
            claim = (
                "Gold rises while CSI 300 falls. No ordinary-month percentile is available, so the paths are described without a split reading. "
                if en
                else "黄金上涨而沪深300下跌。没有普通月份分位，这次价格分开只按路径描述。"
            )
        else:
            tone = "warn"
            claim = (
                "Gold rises while CSI 300 falls, but the gold cumulative return sits in the middle of ordinary months, so the price split stays a path description. "
                if en
                else "黄金上涨而沪深300下跌，但黄金累计收益落在普通月份的中间分位，这次价格分开只按路径描述。"
            )
            if q is not None:
                claim += car_pass
    elif payload.get("anchorIsGold") and b is not None and g is not None and b > 0 and g < 0 and payload.get("showBrent"):
        tone = "warn"
        claim = (
            ("Brent rises while gold falls, so gold does not rise in this window. " if en else "布伦特上涨而黄金下跌，这段窗口里黄金没有上涨。")
            if q_fail
            else ("Brent rises while gold falls, so gold does not show the usual safe-haven rise in this window. " if en else "布伦特上涨而黄金下跌，这段窗口里黄金没有表现出典型的避险上涨。")
        )
        if q_fail:
            claim += car_fail
    elif payload.get("anchorIsGold") and g is not None and c is not None and g < 0 and c < 0 and payload.get("showCsi"):
        tone = "bad"
        claim = (
            ("Gold and CSI 300 fall together, which looks more like tighter liquidity and real rates. " if en else "黄金与沪深300同时下跌，更像流动性和实际利率一起抽紧。")
            if q_fail
            else ("Gold and CSI 300 fall together, which looks more like tighter liquidity and real rates than gold alone taking the haven bid. " if en else "黄金与沪深300同时下跌，更像流动性和实际利率一起抽紧，而不是黄金单独承接避险买盘。")
        )
        if q_fail:
            claim += car_fail
    elif payload.get("anchorIsGold") and g is not None and c is not None and g > 0 and c > 0 and payload.get("showCsi"):
        if q_fail:
            claim = (
                "Gold and CSI 300 rise together, so the two prices do not move apart. "
                if en
                else "黄金与沪深300同时上涨，两边价格没有反向分开。"
            )
            claim += car_fail
        else:
            claim = (
                "Gold and CSI 300 rise together, so the haven asset and the risk asset do not split. "
                if en
                else "黄金与沪深300同时上涨，避险资产和风险资产没有反向分开。"
            )
    elif q_fail:
        claim += car_fail
    if payload.get("exploratory"):
        claim = ("[Exploratory] " if en else "[探索性]") + claim
    return {"tone": tone, "claim": claim}
