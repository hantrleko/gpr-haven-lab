from pathlib import Path

root = Path(r"F:\Hermes\Academic Research\Projects\GPR_Haven_Lab")
template = (root / "src" / "havenlab" / "canvas_template.tsx").read_text(encoding="utf-8")
payload = (root / "data" / "processed" / "canvas_payload.json").read_text(encoding="utf-8")
if "`" in payload or "${" in payload:
    raise SystemExit("payload needs escaping")
out = template.replace("__CANVAS_JSON__", payload)
dest = Path(r"C:\Users\HYC\.cursor\projects\f\canvases\gpr-haven-lab.canvas.tsx")
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(out, encoding="utf-8")
print(dest.stat().st_size)
