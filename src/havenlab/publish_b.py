"""Static event pages, the frozen registry, and API v2 files."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from havenlab.claim_text import claim_rule
from havenlab.engine import event_window
from havenlab.events import EVENTS
from havenlab.version import API_VERSION, LAB_VERSION

SITE = "https://hantrleko.github.io/gpr-haven-lab"
FREEZE = {
    "version": "2.3",
    "frozen_at": "2026-11-10",
    "n_events": 15,
    "rule": "No new event enters the built-in registry until this file and the inclusion rule are committed before the shock.",
}


def _esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def write_registry(root: Path) -> None:
    path = root / "events" / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"freeze": FREEZE, "events": EVENTS}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _svg(series: dict | None) -> str:
    if not series or not series.get("close"):
        return "<p>价格路径在实验室首页。这一页不另存一份图。</p>"
    values = [item for item in series["close"] if isinstance(item, (int, float))]
    if len(values) < 2:
        return "<p>价格路径在实验室首页。</p>"
    width, height = 640, 180
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    step = (width - 16) / (len(values) - 1)
    points = []
    for index, value in enumerate(values):
        x = 8 + index * step
        y = 10 + (hi - value) / span * (height - 20)
        points.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="price path">'
        f'<polyline fill="none" stroke="#1f4b73" stroke-width="1.6" points="{" ".join(points)}"/>'
        "</svg>"
    )


def _claim(panel, event: dict, payload: dict, lang: str) -> str:
    month = str(event.get("month") or event["date"][:7])
    try:
        window = event_window(panel, month, 12)
    except KeyError:
        return "这个事件月不在完整样本里。" if lang != "en" else "This event month is outside the complete sample."
    band = (((payload.get("placebo_v2") or {}).get("12") or {}).get("by_event") or {}).get(event["id"], {}).get("gold") or {}
    car = ((((payload.get("car") or {}).get("by_event") or {}).get(event["id"]) or {}).get("gold") or {}).get("m1_p5") or {}
    judged = claim_rule(
        {
            "g": window["cum"].get("gold"),
            "c": window["cum"].get("csi"),
            "b": window["cum"].get("brent"),
            "anchorIsGold": True,
            "showCsi": True,
            "showBrent": True,
            "pct": band.get("pct"),
            "pct_lo": band.get("pct_lo"),
            "pct_hi": band.get("pct_hi"),
            "q": car.get("q"),
            "lang": lang,
        }
    )
    return judged["claim"]


def _window_rows(panel, event: dict, payload: dict) -> str:
    month = str(event.get("month") or event["date"][:7])
    versions = (((payload.get("haven_versions") or {}).get("events") or {}).get(event["id"]) or {})
    rows = []
    for width in (6, 12, 24):
        try:
            window = event_window(panel, month, width)
        except KeyError:
            continue
        after = window["haven_after"] or {}
        slot = versions.get(str(width)) or {}
        row = (((payload.get("placebo_v2") or {}).get(str(width)) or {}).get("by_event") or {}).get(event["id"]) or {}
        band = row.get("gold") or {}
        blocked = band.get("blocked") or row.get("blocked") or {}
        score = after.get("score")
        se = after.get("se")
        pct_cell = "不完整" if window.get("partial") and band.get("pct") is None else _pct(band)
        blocked_cell = _pct(blocked)
        if blocked.get("n") is not None:
            blocked_cell += f" (n={blocked['n']})"
        rows.append(
            "<tr>"
            f"<td>{width}</td>"
            f"<td>{_num(window['cum'].get('gold'))}</td>"
            f"<td>{_num(window['cum'].get('csi'))}</td>"
            f"<td>{_num(score)}</td>"
            f"<td>{_num(se)}</td>"
            f"<td>{_num(slot.get('haven1_z'))}</td>"
            f"<td>{_num(slot.get('haven2'))}</td>"
            f"<td>{pct_cell}</td>"
            f"<td>{blocked_cell}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _num(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.2f}"


def _pct(band: dict) -> str:
    if not band or band.get("pct") is None:
        return "—"
    if band.get("pct_lo") is None or band.get("pct_hi") is None:
        return f"{100 * float(band['pct']):.1f}%"
    return f"{100 * float(band['pct']):.1f}% [{100 * float(band['pct_lo']):.1f}%, {100 * float(band['pct_hi']):.1f}%]"


def _page(event: dict, panel, payload: dict, lang: str, prev_id: str | None, next_id: str | None, digest: str) -> str:
    en = lang == "en"
    title = event["name_en"] if en else event["name"]
    other = "zh" if en else "en"
    home = "../../../" if en else "../../"
    other_href = f"../../../e/{event['id']}/" if en else f"../../en/e/{event['id']}/"
    self_href = f"{SITE}/en/e/{event['id']}/" if en else f"{SITE}/e/{event['id']}/"
    alt_href = f"{SITE}/e/{event['id']}/" if en else f"{SITE}/en/e/{event['id']}/"
    claim = _claim(panel, event, payload, "en" if en else "zh")
    slices = ((payload.get("slices") or {}).get(event["id"]) or {})
    gold = slices.get("gold")
    gpr = slices.get("gpr")
    nav_prev = f'<a href="../{prev_id}/">{"Previous" if en else "上一个"}</a>' if prev_id else ""
    nav_next = f'<a href="../{next_id}/">{"Next" if en else "下一个"}</a>' if next_id else ""
    cite = (
        f"EF Lab. {title}. GPR Haven Lab {LAB_VERSION}, payload {digest}. "
        f"Accessed {payload.get('meta', {}).get('built')}. {self_href}"
    )
    bib = (
        f"@misc{{gprhaven{event['id']},\n"
        f"  title = {{{title}}},\n"
        f"  author = {{EF Lab}},\n"
        f"  year = {{2026}},\n"
        f"  note = {{{LAB_VERSION}, payload {digest}}}\n"
        "}"
    )
    linked = {
        "@context": "https://schema.org",
        "@type": "Report",
        "name": title,
        "datePublished": event["date"],
        "inLanguage": "en" if en else "zh-CN",
        "isBasedOn": f"{SITE}/api/v2/event/{event['id']}.json",
    }
    return f"""<!DOCTYPE html>
<html lang="{'en' if en else 'zh-CN'}">
<head>
<meta charset="utf-8">
<title>{_esc(title)} · GPR Haven Lab</title>
<link rel="canonical" href="{self_href}">
<link rel="alternate" hreflang="{'en' if en else 'zh-CN'}" href="{self_href}">
<link rel="alternate" hreflang="{ 'zh-CN' if en else 'en' }" href="{alt_href}">
<meta property="og:title" content="{_esc(title)}">
<meta property="og:image" content="{SITE}/cards/{event['id']}.jpg">
<meta name="description" content="{_esc(claim[:180])}">
<style>
body {{ margin: 0; background: #f3f0e8; color: #1c1915; font: 16px/1.5 "Segoe UI", "Microsoft YaHei", sans-serif; }}
main {{ max-width: 820px; margin: 0 auto; padding: 32px 20px 64px; }}
table {{ border-collapse: collapse; width: 100%; background: #fbfaf6; }}
td, th {{ border-bottom: 1px solid #ddd6c8; padding: 6px 8px; text-align: right; }}
td:first-child, th:first-child {{ text-align: left; }}
a {{ color: #1f4b73; }}
</style>
<script type="application/ld+json">{json.dumps(linked, ensure_ascii=False)}</script>
</head>
<body>
<main>
<p><a href="{home}">{'Lab' if en else '实验室'}</a> · <a href="{other_href}">{other}</a></p>
<h1>{_esc(title)}</h1>
<p>{_esc(event['date'])} · {_esc(event['group'])}</p>
<p><strong>{_esc(claim)}</strong></p>
<h2>{'Price path' if en else '价格路径'}</h2>
{_svg(gold)}
<h2>{'Windows' if en else '窗口'}</h2>
<table>
<thead><tr><th>W</th><th>Gold</th><th>CSI</th><th>v1</th><th>SE</th><th>v1_z</th><th>v2</th><th>bootstrap</th><th>blocked</th></tr></thead>
<tbody>
{_window_rows(panel, event, payload)}
</tbody>
</table>
<p>{'v2 is the 60-month downside score ending in the event month, not a 12-month score. The headline on the lab page remains v1.' if en else 'v2 是止于事件月的 60 个月下行分数，不是 12 个月窗口分数。实验室首页的头条仍是 v1。'}</p>
<h2>GPR</h2>
{_svg(gpr)}
<h2>{'Sources' if en else '来源'}</h2>
<ul>
<li><a href="{_esc(event['source'])}">{_esc(event.get('source_label') or event['source'])}</a></li>
<li><a href="{_esc(event['source_2'])}">{_esc(event.get('source_2_label') or event['source_2'])}</a></li>
</ul>
<p>{'Opened' if en else '查阅'} {_esc(event.get('accessed'))}</p>
<h2>Cite this</h2>
<p>{_esc(cite)}</p>
<pre>{_esc(bib)}</pre>
<p>{nav_prev} {nav_next}</p>
</main>
</body>
</html>
"""


def write_static(root: Path, lab: dict, payload: dict, docs: Path) -> None:
    panel = lab["panel"]
    digest = (payload.get("meta") or {}).get("payload_hash") or "pending"
    ordered = list(EVENTS)
    for lang, folder in (("zh", docs / "e"), ("en", docs / "en" / "e")):
        for index, event in enumerate(ordered):
            prev_id = ordered[index - 1]["id"] if index else None
            next_id = ordered[index + 1]["id"] if index + 1 < len(ordered) else None
            target = folder / event["id"] / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_page(event, panel, payload, lang, prev_id, next_id, digest), encoding="utf-8")
    urls = [f"{SITE}/", f"{SITE}/en/"]
    for event in ordered:
        urls.append(f"{SITE}/e/{event['id']}/")
        urls.append(f"{SITE}/en/e/{event['id']}/")
    body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    body.extend(f"<url><loc>{url}</loc></url>" for url in urls)
    body.append("</urlset>")
    (docs / "sitemap.xml").write_text("\n".join(body) + "\n", encoding="utf-8")
    (docs / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://hantrleko.github.io/gpr-haven-lab/sitemap.xml\n",
        encoding="utf-8",
    )


def write_api_v2(docs: Path, lab: dict, payload: dict) -> None:
    api = docs / "api" / "v2"
    (api / "event").mkdir(parents=True, exist_ok=True)
    (api / "daily").mkdir(parents=True, exist_ok=True)
    meta = payload.get("meta") or {}
    panel = {
        "month": payload.get("months") or [],
        "ret_gold": (payload.get("ret") or {}).get("gold"),
        "ret_csi": (payload.get("ret") or {}).get("csi"),
        "ret_hsi": (payload.get("ret") or {}).get("hsi"),
        "ret_dxy": (payload.get("ret") or {}).get("dxy"),
        "ret_brent": (payload.get("ret") or {}).get("brent"),
        "gpr": payload.get("gpr"),
        "dgpr": payload.get("dgpr"),
        "haven": (payload.get("haven") or {}).get("score"),
    }
    blob = json.dumps(panel, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:16]
    core = {"month": panel["month"], "ret_gold": panel["ret_gold"], "gpr": panel["gpr"]}
    _dump(api / "panel.json", panel)
    _dump(api / f"panel.{digest}.json", panel)
    _dump(api / "panel.core.json", core)
    for stale in api.glob("panel.*.json"):
        if stale.name != f"panel.{digest}.json":
            stale.unlink()
    events = payload.get("events") or []
    _dump(api / "events.json", {"freeze": meta.get("event_registry_freeze"), "events": events})
    slices = payload.get("slices") or {}
    for event in events:
        event_id = event["id"]
        _dump(
            api / "event" / f"{event_id}.json",
            {
                "event": event,
                "placebo_v2": {
                    width: ((payload.get("placebo_v2") or {}).get(width) or {}).get("by_event", {}).get(event_id)
                    for width in ("6", "12", "24")
                },
                "haven_versions": ((payload.get("haven_versions") or {}).get("events") or {}).get(event_id),
                "car": ((payload.get("car") or {}).get("by_event") or {}).get(event_id),
                "car_robust": ((payload.get("car_robust") or {}).get("by_event") or {}).get(event_id),
                "spec": ((payload.get("spec_curve") or {}).get("by_event") or {}).get(event_id),
            },
        )
        if slices.get(event_id):
            _dump(api / "daily" / f"{event_id}.json", slices[event_id])
    manifest = {
        "lab": "gpr-haven-lab",
        "version": LAB_VERSION,
        "api_version": API_VERSION,
        "schemas": meta.get("schemas"),
        "sample": [meta.get("sample_start"), meta.get("sample_end")],
        "built": meta.get("built"),
        "payload_hash": meta.get("payload_hash"),
        "registry_hash": (meta.get("spec_registry") or {}).get("hash"),
        "update": "weekly",
        "license": "MIT",
        "fields": "GitHub Pages cannot run ?fields=. Use panel.core.json for month, ret_gold, and gpr.",
        "cache": "Pages cannot set Cache-Control. Fetch this manifest with no-store. The hashed panel file is content-addressed.",
        "endpoints": {
            "manifest": "api/v2/manifest.json",
            "events": "api/v2/events.json",
            "event": "api/v2/event/{id}.json",
            "panel": "api/v2/panel.json",
            "panel_hashed": f"api/v2/panel.{digest}.json",
            "panel_core": "api/v2/panel.core.json",
            "daily": "api/v2/daily/{id}.json",
        },
    }
    _dump(api / "manifest.json", manifest)


def _dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
