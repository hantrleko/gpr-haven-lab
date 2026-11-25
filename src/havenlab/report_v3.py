"""Rule-based v3 event reports (docs/methods/v3.md, rules/rules_v3.json).

Python side of the v3 report engine. src/havenlab/v3/report.js mirrors this
module operation for operation so the browser and the build agree bit for bit.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import struct
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# float-exact log
#
# V8's Math.log is the fdlibm e_log algorithm; CPython's math.log is not
# bit-identical to it (~3% of ratios differ by one ulp). Report percentiles
# compare returns with exact float equality, so the Python side uses a faithful
# fdlibm port. Verified bitwise against Node Math.log on 205k ratios.
# ---------------------------------------------------------------------------


def _hi_lo(x: float) -> tuple[int, int]:
    blob = struct.pack(">d", x)
    return int.from_bytes(blob[:4], "big"), int.from_bytes(blob[4:], "big")


def _from_hi_lo(hi: int, lo: int) -> float:
    return struct.unpack(">d", hi.to_bytes(4, "big") + lo.to_bytes(4, "big"))[0]


_LN2_HI = 6.93147180369123816490e-01
_LN2_LO = 1.90821492927058770002e-10
_LG1 = 6.666666666666735130e-01
_LG2 = 3.999999999940941908e-01
_LG3 = 2.857142874366239149e-01
_LG4 = 2.222219843214978396e-01
_LG5 = 1.818357216161805012e-01
_LG6 = 1.531383769920937332e-01
_LG7 = 1.479819860511658591e-01


def _log(x: float) -> float:
    """fdlibm e_log; bit-identical to JavaScript Math.log."""
    hx, ix = _hi_lo(x)
    if hx < 0x00100000 or hx >= 0x7FF00000:
        return math.log(x)
    k = (hx >> 20) - 1023
    hx &= 0x000FFFFF
    i = (hx + 0x95F64) & 0x100000
    x = _from_hi_lo(hx | (i ^ 0x3FF00000), ix)
    k += i >> 20
    f = x - 1.0
    if (0x000FFFFF & (2 + hx)) < 3:
        if f == 0.0:
            if k == 0:
                return 0.0
            dk = float(k)
            return dk * _LN2_HI + dk * _LN2_LO
        r = f * f * (0.5 - 0.33333333333333333 * f)
        if k == 0:
            return f - r
        dk = float(k)
        return dk * _LN2_HI - ((r - dk * _LN2_LO) - f)
    s = f / (2.0 + f)
    dk = float(k)
    z = s * s
    i = hx - 0x6147A
    w = z * z
    j = 0x6B851 - hx
    t1 = w * (_LG2 + w * (_LG4 + w * _LG6))
    t2 = z * (_LG1 + w * (_LG3 + w * (_LG5 + w * _LG7)))
    i |= j
    r = t2 + t1
    if i > 0:
        hfsq = 0.5 * f * f
        if k == 0:
            return f - (hfsq - s * (hfsq + r))
        return dk * _LN2_HI - ((hfsq - (s * (hfsq + r) + dk * _LN2_LO)) - f)
    if k == 0:
        return f - s * (f - r)
    return dk * _LN2_HI - ((s * (f - r) - dk * _LN2_LO) - f)


def _ret(pe: float, ps: float) -> float:
    return 100.0 * _log(pe / ps)


# ---------------------------------------------------------------------------
# dates and number formatting (mirrored in report.js)
# ---------------------------------------------------------------------------

_EPOCH = date(1970, 1, 1)


def _parse_day(text: str) -> int:
    year, month, day = (int(part) for part in text.split("-"))
    return (date(year, month, day) - _EPOCH).days


def _day_str(day: int) -> str:
    return (_EPOCH + timedelta(days=day)).isoformat()


def _fmt_mag(x: float, d: int) -> str:
    p = 10 ** d
    v = math.floor(abs(x) * p + 0.5) / p
    return f"{v:.{d}f}"


def _rounds_to_zero(x: float, d: int) -> bool:
    return math.floor(abs(x) * (10 ** d) + 0.5) == 0


def _fmt_signed(x: float, d: int) -> str:
    mag = _fmt_mag(x, d)
    if _rounds_to_zero(x, d):
        return mag
    return ("+" if x > 0 else "-") + mag


def _pct_int(p: float) -> str:
    return _fmt_mag(p * 100.0, 0)


def _fill(text: str, mapping: dict) -> str:
    for key, value in mapping.items():
        text = text.replace("{" + key + "}", str(value))
    return text


# ---------------------------------------------------------------------------
# decoded series
# ---------------------------------------------------------------------------


def decode_series(payload: dict) -> dict:
    assets = {entry["id"]: entry for entry in payload["meta"]["assets"]}
    series = {}
    for asset_id, enc in payload["series"].items():
        days = []
        day = _parse_day(enc["t0"])
        for gap in enc["dt"]:
            day += gap
            days.append(day)
        series[asset_id] = {"days": days, "values": [float(v) for v in enc["v"]]}
    return {"assets": assets, "series": series}


class _Ctx:
    __slots__ = ("assets", "series", "rules", "hist", "gpr_pref", "rates", "narrative_rules")

    def __init__(self, decoded: dict, rules: dict):
        self.assets = decoded["assets"]
        self.series = decoded["series"]
        self.rules = rules
        self.hist: dict = {}
        self.gpr_pref = None
        self.rates: dict = {}
        self.narrative_rules = None


def _name(ctx: _Ctx, asset_id: str, lang: str) -> str:
    entry = ctx.assets.get(asset_id)
    if entry:
        return entry["name_" + lang]
    return asset_id


def _join(names: list, lang: str, rules: dict) -> str:
    if lang == "zh":
        return rules["list_join"]["zh"].join(names)
    lj = rules["list_join"]
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return names[0] + lj["en_last"] + names[1]
    return lj["en"].join(names[:-1]) + lj["en_last"] + names[-1]


# ---------------------------------------------------------------------------
# windows, history, percentiles
# ---------------------------------------------------------------------------


def _last_le(days: list, x: int) -> int:
    return bisect.bisect_right(days, x) - 1


def _last_lt(days: list, x: int) -> int:
    return bisect.bisect_left(days, x) - 1


def _history(ctx: _Ctx, asset_id: str, h: int) -> list:
    key = (asset_id, h)
    cached = ctx.hist.get(key)
    if cached is not None:
        return cached
    out = []
    ser = ctx.series.get(asset_id)
    if ser:
        days, vals = ser["days"], ser["values"]
        last_day = days[-1]
        for i, t in enumerate(days):
            if t + h > last_day:
                break
            j = _last_le(days, t + h)
            out.append((t, _ret(vals[j], vals[i])))
    ctx.hist[key] = out
    return out


def _window(ctx: _Ctx, asset_id: str, h: int, day: int) -> dict:
    ser = ctx.series.get(asset_id)
    if not ser or not ser["days"]:
        return {"status": "missing", "ret": None, "pct": None, "n": None, "complete": None}
    days, vals = ser["days"], ser["values"]
    s = _last_lt(days, day)
    if s < 0:
        return {"status": "missing", "ret": None, "pct": None, "n": None, "complete": None}
    s_day = days[s]
    last_day = days[-1]
    if s_day + h > last_day:
        return {
            "status": "incomplete",
            "ret": _ret(vals[-1], vals[s]),
            "pct": None,
            "n": None,
            "complete": False,
        }
    e = _last_le(days, s_day + h)
    ret = _ret(vals[e], vals[s])
    less = 0
    equal = 0
    n = 0
    for t, r in _history(ctx, asset_id, h):
        if abs(t - s_day) <= h:
            continue
        n += 1
        if r < ret:
            less += 1
        elif r == ret:
            equal += 1
    pct = (less + 0.5 * equal) / n if n else None
    status = "ok" if n >= ctx.rules["min_history"] else "short_history"
    return {"status": status, "ret": ret, "pct": pct, "n": n, "complete": True}


def _label(cell: dict, k: int, rules: dict) -> str:
    ret, pct = cell["ret"], cell["pct"]
    alpha = rules["family_alpha"]
    if ret > 0.0:
        if pct >= 1.0 - alpha / k:
            return "clear_up"
        if pct >= rules["lean_hi"]:
            return "lean_up"
        return "normal"
    if ret < 0.0:
        if pct <= alpha / k:
            return "clear_down"
        if pct <= rules["lean_lo"]:
            return "lean_down"
        return "normal"
    return "normal"


def _rate_havens(ctx: _Ctx, day: int) -> dict:
    """Labeled haven cells for every horizon at one report date (cached)."""
    cached = ctx.rates.get(day)
    if cached is not None:
        return cached
    rules = ctx.rules
    havens, horizons = rules["havens"], rules["horizons"]
    cells = {}
    for aid in havens:
        for h in horizons:
            cells[(aid, h)] = _window(ctx, aid, h, day)
    k = {h: sum(1 for aid in havens if cells[(aid, h)]["status"] == "ok") for h in horizons}
    out = {}
    for aid in havens:
        out[aid] = {}
        for h in horizons:
            cell = cells[(aid, h)]
            cell["label"] = _label(cell, k[h], rules) if cell["status"] == "ok" else cell["status"]
            out[aid][h] = cell
    ctx.rates[day] = out
    return out


# ---------------------------------------------------------------------------
# sentence helpers
# ---------------------------------------------------------------------------


def _dir_key(ret: float) -> str:
    if _rounds_to_zero(ret, 1):
        return "flat"
    return "up" if ret > 0 else "down"


def _ret_text(ret: float, lang: str) -> str:
    if lang == "zh":
        return _fmt_mag(abs(ret), 1)
    return _fmt_signed(ret, 1)


def _rank_text(p: float, lang: str, rules: dict) -> str:
    if p < 0.5:
        return _fill(rules["rank"]["weaker"][lang], {"x": _fmt_mag((1.0 - p) * 100.0, 0)})
    return _fill(rules["rank"]["stronger"][lang], {"x": _fmt_mag(p * 100.0, 0)})


# ---------------------------------------------------------------------------
# report sections
# ---------------------------------------------------------------------------


def _bench(ctx: _Ctx, benchmark: str, day: int) -> dict:
    rules = ctx.rules
    primary = rules["primary"]
    cell = _window(ctx, benchmark, primary, day)
    status = cell["status"]
    if status in ("missing", "short_history"):
        return {"id": benchmark, "ret": None, "pct": None, "state": "missing", "complete": None, "zh": None, "en": None}
    if status == "incomplete":
        return {
            "id": benchmark,
            "ret": cell["ret"],
            "pct": None,
            "state": "incomplete",
            "complete": False,
            "zh": None,
            "en": None,
        }
    ret, pct = cell["ret"], cell["pct"]
    if ret < 0.0 and pct <= rules["bench_drop_p"]:
        state = "clear_drop"
    elif ret < 0.0:
        state = "small_drop"
    else:
        state = "no_drop"
    row = {"id": benchmark, "ret": ret, "pct": pct, "state": state, "complete": True, "zh": None, "en": None}
    tmpl = rules["sentences"]["bench"]
    for lang in ("zh", "en"):
        row[lang] = _fill(
            tmpl[lang],
            {
                "bench": _name(ctx, benchmark, lang),
                "dir": rules["dir_words"][_dir_key(ret)][lang],
                "ret": _ret_text(ret, lang),
                "rank": _rank_text(pct, lang, rules),
                "state": rules["bench_states"][state][lang],
            },
        )
    return row


def _shock(ctx: _Ctx, asset_id: str, day: int) -> dict:
    rules = ctx.rules
    primary = rules["primary"]
    cell = _window(ctx, asset_id, primary, day)
    row = {"id": asset_id, "ret": cell["ret"], "pct": cell["pct"], "complete": cell["complete"], "zh": None, "en": None}
    if cell["status"] == "ok":
        tmpl = rules["sentences"]["shock"]
        for lang in ("zh", "en"):
            row[lang] = _fill(
                tmpl[lang],
                {
                    "asset": _name(ctx, asset_id, lang),
                    "dir": rules["dir_words"][_dir_key(cell["ret"])][lang],
                    "ret": _ret_text(cell["ret"], lang),
                    "rank": _rank_text(cell["pct"], lang, rules),
                },
            )
    return row


def _gpr_pref(ctx: _Ctx):
    if ctx.gpr_pref is None:
        ser = ctx.series["gpr"]
        pref = [0.0]
        for v in ser["values"]:
            pref.append(pref[-1] + v)
        ctx.gpr_pref = pref
    return ctx.gpr_pref


def _gpr(ctx: _Ctx, day: int, kind: str) -> tuple[dict, dict]:
    rules = ctx.rules["gpr"]
    win, lookback, min_days = rules["window_days"], rules["lookback_days"], rules["min_days"]
    ser = ctx.series.get("gpr")
    last_str = _day_str(ser["days"][-1]) if ser and ser["days"] else None

    def insufficient(mean):
        tmpl = ctx.rules["sentences"]["pressure_insufficient"]
        return (
            {"state": "insufficient", "pct": None, "mean": mean, "start": None, "last": last_str,
             "zh": tmpl["zh"], "en": tmpl["en"]},
            {"lag": False},
        )

    if not ser or not ser["days"]:
        return insufficient(None)
    days = ser["days"]
    s_idx = _last_lt(days, day)
    if s_idx < 0:
        return insufficient(None)
    s_g = days[s_idx]
    pref = _gpr_pref(ctx)
    lo = bisect.bisect_right(days, s_g)
    hi = bisect.bisect_right(days, s_g + win) - 1
    cnt = hi - lo + 1 if hi >= lo else 0
    mean = (pref[hi + 1] - pref[lo]) / cnt if cnt > 0 else None
    refs = []
    u_lo = bisect.bisect_right(days, s_g - lookback)
    u_hi = bisect.bisect_right(days, s_g) - 1
    for ui in range(u_lo, u_hi + 1):
        u = days[ui]
        r_lo = bisect.bisect_right(days, u - win)
        r_hi = bisect.bisect_right(days, u) - 1
        r_cnt = r_hi - r_lo + 1 if r_hi >= r_lo else 0
        if r_cnt >= min_days:
            refs.append((pref[r_hi + 1] - pref[r_lo]) / r_cnt)
    lag = s_g + win > days[-1]
    meta = {"lag": lag}
    if cnt < min_days or not refs:
        out, _ = insufficient(mean)
        out["start"] = _day_str(s_g)
        return out, meta
    less = sum(1 for r in refs if r < mean)
    equal = sum(1 for r in refs if r == mean)
    pct = (less + 0.5 * equal) / len(refs)
    g = ctx.rules["gpr"]
    if pct >= g["very_high"]:
        state = "very_high"
    elif pct >= g["high"]:
        state = "high"
    else:
        state = "normal"
    row = {"state": state, "pct": pct, "mean": mean, "start": _day_str(s_g), "last": last_str, "zh": None, "en": None}
    tmpl_name = "pressure_latest" if kind == "latest" else "pressure"
    for lang in ("zh", "en"):
        row[lang] = _fill(
            ctx.rules["sentences"][tmpl_name][lang],
            {
                "gpr": _fmt_mag(mean, 1),
                "pct": _pct_int(pct),
                "state": ctx.rules["gpr_states"][state][lang],
            },
        )
    return row, meta


def _headline(ctx: _Ctx, rated: dict, bench: dict, benchmark: str, primary: int) -> dict:
    rules = ctx.rules
    strong = [aid for aid in rules["havens"] if rated[aid][primary]["label"] == "clear_up"]
    lean = [aid for aid in rules["havens"] if rated[aid][primary]["label"] == "lean_up"]
    state = bench["state"]
    if state == "missing":
        code = "no_bench"
    elif state == "incomplete":
        code = "incomplete"
    elif state == "no_drop":
        code = "no_drop"
    elif state == "clear_drop" and strong:
        code = "clear_drop_clear"
    elif state == "small_drop" and strong:
        code = "small_drop_clear"
    elif not strong and len(lean) >= 2:
        code = "drop_lean_many"
    elif not strong and len(lean) == 1:
        code = "drop_lean_one"
    else:
        code = "drop_none"
    entry = rules["headlines"][code]
    row = {"code": code, "grade": entry["grade"], "zh": None, "en": None}
    for lang in ("zh", "en"):
        row[lang] = _fill(
            entry[lang],
            {
                "bench": _name(ctx, benchmark, lang),
                "clear": _join([_name(ctx, a, lang) for a in strong], lang, rules),
                "lean": _join([_name(ctx, a, lang) for a in lean], lang, rules),
                "clear_verb": rules["clear_verb"]["one" if len(strong) == 1 else "many"]["en"],
            },
        )
    if state in ("clear_drop", "small_drop"):
        down = [aid for aid in rules["havens"] if rated[aid][primary]["label"] == "clear_down"]
        if down:
            tail = rules["headline_down_tail"]
            row["zh"] += _fill(tail["zh"], {"down": _join([_name(ctx, a, "zh") for a in down], "zh", rules)})
            en_key = "en_one" if len(down) == 1 else "en_many"
            row["en"] += " " + _fill(tail[en_key], {"down": _join([_name(ctx, a, "en") for a in down], "en", rules)})
    return row


def _evidence(ctx: _Ctx, headline: dict) -> dict:
    tmpl = ctx.rules["sentences"]["evidence"]
    grade = headline["grade"]
    return {
        "grade": grade,
        "zh": _fill(tmpl["zh"], {"grade": ctx.rules["grades"][grade]["zh"]}),
        "en": _fill(tmpl["en"], {"grade": ctx.rules["grades"][grade]["en"]}),
    }


def _caveats(ctx: _Ctx, kind: str, rated: dict, bench: dict, k: dict, gmeta: dict, gpr_last: str | None) -> list:
    rules = ctx.rules
    primary = rules["primary"]
    out = []

    def add(code, zh_map=None, en_map=None):
        entry = rules["caveats"][code]
        zh_map = zh_map or {}
        en_map = en_map or zh_map
        out.append({"code": code, "zh": _fill(entry["zh"], zh_map), "en": _fill(entry["en"], en_map)})

    add("no_forecast")
    if kind == "preset":
        add("hindsight_preset")
    elif kind == "custom":
        add("hindsight_custom")
    k_primary = k[primary]
    if k_primary > 1:
        add("multi", {"k": k_primary, "top": _fmt_mag(rules["family_alpha"] / k_primary * 100.0, 1)})
    haven_incomplete = any(rated[a][primary]["label"] == "incomplete" for a in rules["havens"])
    if bench["state"] == "incomplete" or haven_incomplete:
        add("incomplete")
    unrated = [a for a in rules["havens"] if rated[a][primary]["label"] in ("short_history", "missing")]
    if unrated:
        add(
            "unrated",
            {"assets": _join([_name(ctx, a, "zh") for a in unrated], "zh", rules)},
            {"assets": _join([_name(ctx, a, "en") for a in unrated], "en", rules)},
        )
    futures = [a for a in rules["futures_note_assets"] if a in ctx.series and ctx.series[a]["days"]]
    if futures:
        add(
            "futures",
            {"assets": _join([_name(ctx, a, "zh") for a in futures], "zh", rules)},
            {"assets": _join([_name(ctx, a, "en") for a in futures], "en", rules)},
        )
    if gmeta.get("lag") and gpr_last:
        add("gpr_lag", {"last": gpr_last})
    if bench["state"] == "no_drop":
        add("no_test", {"bench": _name(ctx, bench["id"], "zh")}, {"bench": _name(ctx, bench["id"], "en")})
    return out


_RATED_LABELS = ("clear_up", "lean_up", "normal", "lean_down", "clear_down")


def _history_rows(ctx: _Ctx, events: list, exclude_event_id: str | None) -> list:
    rules = ctx.rules
    primary = rules["primary"]
    event_days = []
    for event in events:
        if event["id"] == exclude_event_id:
            continue
        event_days.append(_parse_day(event["date"]))
    out = []
    for aid in rules["havens"]:
        counts = {label: 0 for label in _RATED_LABELS}
        rets = []
        for day in event_days:
            cell = _rate_havens(ctx, day)[aid][primary]
            label = cell["label"]
            if label in counts:
                counts[label] += 1
                rets.append(cell["ret"])
        n = len(rets)
        row = {
            "id": aid,
            "n": n,
            "clear_up": counts["clear_up"],
            "lean_up": counts["lean_up"],
            "normal": counts["normal"],
            "lean_down": counts["lean_down"],
            "clear_down": counts["clear_down"],
            "median": None,
            "zh": None,
            "en": None,
        }
        if n == 0:
            tmpl = rules["sentences"]["history_none"]
            row["zh"] = _fill(tmpl["zh"], {"asset": _name(ctx, aid, "zh")})
            row["en"] = _fill(tmpl["en"], {"asset": _name(ctx, aid, "en")})
        else:
            rets.sort()
            if n % 2:
                median = rets[n // 2]
            else:
                median = (rets[n // 2 - 1] + rets[n // 2]) / 2.0
            row["median"] = median
            tmpl = rules["sentences"]["history_row"]
            for lang in ("zh", "en"):
                row[lang] = _fill(
                    tmpl[lang],
                    {
                        "n": n,
                        "asset": _name(ctx, aid, lang),
                        "clear": counts["clear_up"],
                        "lean": counts["lean_up"],
                        "median": _fmt_signed(median, 1),
                    },
                )
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# narrative verdict layer (rules/narratives_v3.json, docs/methods/v3.md)
#
# Pre-registered-style mechanical aggregation over event dates, fixed on
# 2026-11-25 before outputs were examined. Mirrored in v3/report.js.
# ---------------------------------------------------------------------------

# Secondary horizons for the n_pos7 / n_pos91 counts. Validity is always
# decided at the primary horizon; a valid row whose 7/91-day window is not
# complete counts as non-positive at that horizon.
_NARR_H7 = 7
_NARR_H91 = 91


def _narrative_entries(events_or_dates: list) -> list:
    """Normalize event dicts or bare date strings to {event, date, day}."""
    out = []
    for item in events_or_dates:
        if isinstance(item, str):
            out.append({"event": None, "date": item, "day": _parse_day(item)})
        else:
            out.append({"event": item["id"], "date": item["date"], "day": _parse_day(item["date"])})
    return out


def _complete(cell: dict) -> bool:
    """A window return is computable iff the window closed (missing/incomplete exclude)."""
    return cell["complete"] is True


def _narrative_row(ctx: _Ctx, asset_id: str, bench_id: str, kind: str, h: int, entry: dict) -> dict:
    day = entry["day"]
    row = {"event": entry["event"], "date": entry["date"], "status": None, "ret": None, "bench_ret": None, "pos7": False, "pos91": False}
    bench = _window(ctx, bench_id, h, day)
    if not _complete(bench):
        row["status"] = "incomplete"
        return row
    row["bench_ret"] = bench["ret"]
    if kind == "haven" and bench["ret"] >= 0.0:
        row["status"] = "not_a_test"
        return row
    cell = _window(ctx, asset_id, h, day)
    if not _complete(cell):
        row["status"] = "missing"
        return row
    row["status"] = "valid"
    row["ret"] = cell["ret"]
    cell7 = _window(ctx, asset_id, _NARR_H7, day)
    row["pos7"] = _complete(cell7) and cell7["ret"] > 0.0
    cell91 = _window(ctx, asset_id, _NARR_H91, day)
    row["pos91"] = _complete(cell91) and cell91["ret"] > 0.0
    return row


def _aggregate_narrative(ctx: _Ctx, events_or_dates: list, asset_id: str, bench_id: str, kind: str, nrules: dict) -> dict:
    """Core aggregation: rows plus integer-math verdict for one asset.

    events_or_dates is a list of event dicts ({"id", "date"}) or bare
    YYYY-MM-DD strings (pseudo-events, used by the custom tool).
    """
    h = int(nrules["horizon"])
    min_tests = int(nrules["min_tests"])
    rows = [_narrative_row(ctx, asset_id, bench_id, kind, h, entry) for entry in _narrative_entries(events_or_dates)]
    n_valid = 0
    n_pos = 0
    n_not_test = 0
    n_missing = 0
    n_pos7 = 0
    n_pos91 = 0
    rets = []
    for row in rows:
        status = row["status"]
        if status == "valid":
            n_valid += 1
            if row["ret"] > 0.0:
                n_pos += 1
            if row["pos7"]:
                n_pos7 += 1
            if row["pos91"]:
                n_pos91 += 1
            rets.append(row["ret"])
        elif status == "not_a_test":
            n_not_test += 1
        else:  # "missing" and "incomplete" rows combine into n_missing
            n_missing += 1
    # Verdict thresholds in integer math exactly (fixed 2026-11-25, no tuning).
    if n_valid < min_tests:
        verdict = "untestable"
    elif n_pos * 3 >= 2 * n_valid:
        verdict = "mostly_holds"
    elif n_pos * 3 <= 1 * n_valid:
        verdict = "mostly_fails"
    else:
        verdict = "mixed"
    median = None
    if rets:
        rets.sort()
        n = len(rets)
        if n % 2:
            median = rets[n // 2]
        else:
            median = (rets[n // 2 - 1] + rets[n // 2]) / 2.0
    out_rows = [
        {"event": row["event"], "date": row["date"], "status": row["status"], "ret": row["ret"], "bench_ret": row["bench_ret"]}
        for row in rows
    ]
    return {
        "asset": asset_id,
        "kind": kind,
        "verdict": verdict,
        "n_valid": n_valid,
        "n_pos": n_pos,
        "n_not_test": n_not_test,
        "n_missing": n_missing,
        "n_pos7": n_pos7,
        "n_pos91": n_pos91,
        "median": median,
        "rows": out_rows,
    }


def _narrative_summaries(ctx: _Ctx, agg: dict, nrules: dict, asset_zh: str, asset_en: str) -> tuple:
    median = agg["median"]
    median_text = _fmt_signed(median, 1) if median is not None else "—"
    templates = nrules["summary_templates"]
    summary_zh = _fill(
        templates["zh"],
        {
            "n_valid": agg["n_valid"],
            "n_pos": agg["n_pos"],
            "median": median_text,
            "n_not_test": agg["n_not_test"],
            "n_missing": agg["n_missing"],
            "asset": asset_zh,
        },
    )
    summary_en = _fill(
        templates["en"],
        {
            "n_valid": agg["n_valid"],
            "n_pos": agg["n_pos"],
            "median": median_text,
            "n_not_test": agg["n_not_test"],
            "n_missing": agg["n_missing"],
            "asset": asset_en,
        },
    )
    return summary_zh, summary_en


def build_preset_narratives(ctx: _Ctx, events: list, nrules: dict) -> list:
    """The frozen narrative registry evaluated over the 15 built-in events."""
    bench_id = nrules["benchmark"]
    out = []
    for narr in nrules["narratives"]:
        agg = _aggregate_narrative(ctx, events, narr["asset"], bench_id, narr["kind"], nrules)
        asset_zh = narr.get("asset_zh") or _name(ctx, narr["asset"], "zh")
        asset_en = narr.get("asset_en") or _name(ctx, narr["asset"], "en")
        summary_zh, summary_en = _narrative_summaries(ctx, agg, nrules, asset_zh, asset_en)
        entry = {
            "id": narr["id"],
            "asset": narr["asset"],
            "kind": narr["kind"],
            "zh": narr["zh"],
            "en": narr["en"],
            "verdict": agg["verdict"],
            "n_valid": agg["n_valid"],
            "n_pos": agg["n_pos"],
            "n_not_test": agg["n_not_test"],
            "n_missing": agg["n_missing"],
            "n_pos7": agg["n_pos7"],
            "n_pos91": agg["n_pos91"],
            "median": agg["median"],
            "summary_zh": summary_zh,
            "summary_en": summary_en,
            "rows": agg["rows"],
        }
        out.append(entry)
    return out


def build_custom_narrative(ctx: _Ctx, dates: list, asset_ids: list, bench_id: str) -> list:
    """Custom-tool aggregation: bare dates as pseudo-events, haven rules.

    Same output structure as preset narratives. Narrative text fields
    (id/zh/en) are null — there is no pre-registered statement. Summaries are
    only written when bench_id is the narrative-layer benchmark, because the
    fixed template names that benchmark; otherwise they are null.
    """
    nrules = ctx.narrative_rules
    if nrules is None:
        raise ValueError("ctx.narrative_rules is required for build_custom_narrative")
    out = []
    for asset_id in asset_ids:
        agg = _aggregate_narrative(ctx, dates, asset_id, bench_id, "haven", nrules)
        if bench_id == nrules["benchmark"]:
            asset_zh = _name(ctx, asset_id, "zh")
            asset_en = _name(ctx, asset_id, "en")
            summary_zh, summary_en = _narrative_summaries(ctx, agg, nrules, asset_zh, asset_en)
        else:
            summary_zh, summary_en = None, None
        entry = {
            "id": None,
            "asset": asset_id,
            "kind": "haven",
            "zh": None,
            "en": None,
            "verdict": agg["verdict"],
            "n_valid": agg["n_valid"],
            "n_pos": agg["n_pos"],
            "n_not_test": agg["n_not_test"],
            "n_missing": agg["n_missing"],
            "n_pos7": agg["n_pos7"],
            "n_pos91": agg["n_pos91"],
            "median": agg["median"],
            "summary_zh": summary_zh,
            "summary_en": summary_en,
            "rows": agg["rows"],
        }
        out.append(entry)
    return out


def build_all_narratives(payload: dict, rules: dict, nrules: dict, events: list) -> dict:
    decoded = decode_series(payload)
    ctx = _Ctx(decoded, rules)
    ctx.narrative_rules = nrules
    return {
        "built": payload["meta"]["built"],
        "rules_version": nrules["version"],
        "benchmark": nrules["benchmark"],
        "horizon": nrules["horizon"],
        "narratives": build_preset_narratives(ctx, events, nrules),
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def _report(ctx: _Ctx, events: list, date, benchmark: str, kind: str, exclude_event_id):
    rules = ctx.rules
    if kind == "latest":
        days = ctx.series[benchmark]["days"]
        day = days[-1] - rules["latest_days"]
        date_str = _day_str(day)
    else:
        if isinstance(date, int):
            day = date
            date_str = _day_str(day)
        else:
            date_str = date
            day = _parse_day(date)
    primary = rules["primary"]
    rated = _rate_havens(ctx, day)
    k = {h: sum(1 for aid in rules["havens"] if rated[aid][h]["status"] == "ok") for h in rules["horizons"]}
    bench = _bench(ctx, benchmark, day)
    shocks = []
    for sid in rules["shocks"]:
        ser = ctx.series.get(sid)
        if ser and ser["days"]:
            shocks.append(_shock(ctx, sid, day))
    pressure, gmeta = _gpr(ctx, day, kind)
    gpr_last = pressure["last"]
    headline = _headline(ctx, rated, bench, benchmark, primary)
    history = _history_rows(ctx, events, exclude_event_id)
    caveats = _caveats(ctx, kind, rated, bench, k, gmeta, gpr_last)
    evidence = _evidence(ctx, headline)
    havens = []
    for aid in rules["havens"]:
        by_h = {}
        for h in rules["horizons"]:
            cell = rated[aid][h]
            by_h[str(h)] = {
                "ret": cell["ret"],
                "pct": cell["pct"],
                "label": cell["label"],
                "complete": cell["complete"],
                "n": cell["n"],
            }
        havens.append({"id": aid, "by_h": by_h})
    return {
        "date": date_str,
        "kind": kind,
        "benchmark": benchmark,
        "rules_version": rules["version"],
        "headline": headline,
        "pressure": pressure,
        "bench": bench,
        "shock": shocks,
        "havens": havens,
        "k": {str(h): k[h] for h in rules["horizons"]},
        "history": history,
        "evidence": evidence,
        "caveats": caveats,
    }


def build_report(series: dict, rules: dict, events: list, date, benchmark: str, kind: str, exclude_event_id=None) -> dict:
    ctx = _Ctx(series, rules)
    return _report(ctx, events, date, benchmark, kind, exclude_event_id)


def build_all_reports(payload: dict, rules: dict, events: list) -> dict:
    decoded = decode_series(payload)
    ctx = _Ctx(decoded, rules)
    benches = [
        b for b in rules["benchmarks"]
        if b in decoded["series"] and decoded["series"][b]["days"]
    ]
    out = {
        "rules_version": rules["version"],
        "built": payload["meta"]["built"],
        "latest": {},
        "events": {},
        "event_list": [
            {"id": e["id"], "date": e["date"], "name": e.get("name"), "name_en": e.get("name_en")}
            for e in events
        ],
    }
    for bench in benches:
        out["latest"][bench] = _report(ctx, events, None, bench, "latest", None)
    for event in events:
        out["events"][event["id"]] = {}
        for bench in benches:
            out["events"][event["id"]][bench] = _report(
                ctx, events, event["date"], bench, "preset", event["id"]
            )
    return out


def publish_reports(root: Path) -> None:
    """Write docs/v3/reports.json + rules.json and extend the v3 manifest."""
    root = Path(root)
    docs_v3 = root / "docs" / "v3"
    series_path = docs_v3 / "series.json"
    if not series_path.exists():
        return
    payload = json.loads(series_path.read_text(encoding="utf-8"))
    rules_path = root / "src" / "havenlab" / "rules" / "rules_v3.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    from havenlab.events import EVENTS

    events = [{"id": e["id"], "date": e["date"], "name": e["name"], "name_en": e["name_en"]} for e in EVENTS]
    reports = build_all_reports(payload, rules, events)
    blob = json.dumps(reports, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    raw = blob.encode("utf-8")
    (docs_v3 / "reports.json").write_text(blob, encoding="utf-8")
    rules_bytes = rules_path.read_bytes()
    (docs_v3 / "rules.json").write_bytes(rules_bytes)
    manifest_path = docs_v3 / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"schema": payload["meta"]["schema"], "built": payload["meta"]["built"], "files": {}}
    manifest["built"] = payload["meta"]["built"]
    files = manifest.setdefault("files", {})

    def entry(name: str, data: bytes) -> dict:
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    files["reports"] = entry("reports.json", raw)
    files["rules"] = entry("rules.json", rules_bytes)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish_narratives(root: Path) -> None:
    """Write docs/v3/narratives.json + narrative_rules.json into the v3 manifest."""
    root = Path(root)
    docs_v3 = root / "docs" / "v3"
    series_path = docs_v3 / "series.json"
    if not series_path.exists():
        return
    payload = json.loads(series_path.read_text(encoding="utf-8"))
    rules_path = root / "src" / "havenlab" / "rules" / "rules_v3.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    nrules_path = root / "src" / "havenlab" / "rules" / "narratives_v3.json"
    nrules = json.loads(nrules_path.read_text(encoding="utf-8"))
    from havenlab.events import EVENTS

    events = [{"id": e["id"], "date": e["date"], "name": e["name"], "name_en": e["name_en"]} for e in EVENTS]
    narratives = build_all_narratives(payload, rules, nrules, events)
    blob = json.dumps(narratives, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    raw = blob.encode("utf-8")
    (docs_v3 / "narratives.json").write_text(blob, encoding="utf-8")
    nrules_bytes = nrules_path.read_bytes()
    (docs_v3 / "narrative_rules.json").write_bytes(nrules_bytes)
    manifest_path = docs_v3 / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"schema": payload["meta"]["schema"], "built": payload["meta"]["built"], "files": {}}
    manifest["built"] = payload["meta"]["built"]
    files = manifest.setdefault("files", {})

    def entry(name: str, data: bytes) -> dict:
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    files["narratives"] = entry("narratives.json", raw)
    files["narrative_rules"] = entry("narrative_rules.json", nrules_bytes)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
