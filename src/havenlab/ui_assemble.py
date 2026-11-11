"""Join the page parts into one HTML file for GitHub Pages.

`src/havenlab/ui/` is the source when all four parts exist. `build.py`
rewrites `template.html` from those parts so the published file stays in sync.
"""

from __future__ import annotations

from pathlib import Path

PARTS = ("head.html", "styles.css", "body.html", "app.js")


def _ui(root: Path) -> Path:
    return root / "src" / "havenlab" / "ui"


def parts_ready(root: Path) -> bool:
    folder = _ui(root)
    return all((folder / name).exists() for name in PARTS)


def assemble(root: Path) -> str:
    folder = _ui(root)
    head = (folder / "head.html").read_text(encoding="utf-8").rstrip()
    styles = (folder / "styles.css").read_text(encoding="utf-8").rstrip()
    body = (folder / "body.html").read_text(encoding="utf-8").strip()
    pieces = []
    for name in ("claim_rule.js", "verdict_rule.js"):
        path = folder / name
        if path.exists():
            pieces.append(path.read_text(encoding="utf-8").rstrip() + "\n")
    script = "".join(pieces) + (folder / "app.js").read_text(encoding="utf-8").rstrip()
    for name in ("phase_b.js", "phase_c.js"):
        extra = folder / name
        if extra.exists():
            script += "\n" + extra.read_text(encoding="utf-8").rstrip()
    return (
        f"{head}\n<style>\n{styles}\n</style>\n</head>\n{body}\n<script>\n{script}\n</script>\n</body>\n</html>\n"
    )


def load_page(root: Path) -> str:
    template = root / "src" / "havenlab" / "template.html"
    if parts_ready(root):
        page = assemble(root)
        template.write_text(page, encoding="utf-8")
        return page
    return template.read_text(encoding="utf-8")


def split_template(root: Path) -> None:
    text = (root / "src" / "havenlab" / "template.html").read_text(encoding="utf-8")
    head, rest = text.split("<style>", 1)
    styles, rest = rest.split("</style>", 1)
    rest = rest.split("</head>", 1)[1]
    body, script = rest.split("<script>", 1)
    script = script.rsplit("</script>", 1)[0]
    folder = _ui(root)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "head.html").write_text(head.rstrip() + "\n", encoding="utf-8")
    (folder / "styles.css").write_text(styles.strip() + "\n", encoding="utf-8")
    (folder / "body.html").write_text(body.strip() + "\n", encoding="utf-8")
    (folder / "app.js").write_text(script.strip() + "\n", encoding="utf-8")
