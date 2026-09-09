"""Compuertas 2 y 4: calibracion PIL<->Blink y @font-face base64 en dos motores.

Genera un SVG con la fuente empotrada, lo rasteriza con Chromium headless,
mide el bbox de tinta por fila con numpy y lo compara con la medida de PIL.
El objetivo es convertir un misterio en un numero.
"""
from __future__ import annotations
import base64, os, subprocess, sys, tempfile
import numpy as np
from lxml import etree
from PIL import Image, ImageFont

FONTS = {
    "Black":   "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
    "Regular": "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
}
SVG = "http://www.w3.org/2000/svg"
CASES = [  # (peso, texto, tamano_px)
    ("Black",   "MERIDIAN QUARTER", 96),
    ("Black",   "MERIDIAN QUARTER", 40),
    ("Black",   "SPRING STYLE", 24),
    ("Regular", "Up to 50% off across 120 stores", 28),
    ("Regular", "Up to 50% off across 120 stores", 14),
    ("Regular", "Terms and conditions apply.", 12),
]
PAD, ROW_GAP, X0 = 40, 60, 40

def b64(p):
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def build_svg(rows, W, H):
    faces = "\n".join(
        f"@font-face{{font-family:'LatoTest{w}';src:url(data:font/ttf;base64,{b64(p)}) format('truetype');}}"
        for w, p in FONTS.items())
    svg = etree.Element("{%s}svg" % SVG, nsmap={None: SVG},
                        width=str(W), height=str(H), viewBox=f"0 0 {W} {H}")
    d = etree.SubElement(svg, "{%s}defs" % SVG)
    st = etree.SubElement(d, "{%s}style" % SVG); st.text = faces
    etree.SubElement(svg, "{%s}rect" % SVG, x="0", y="0", width=str(W), height=str(H), fill="#ffffff")
    for (w, txt, size), baseline in rows:
        t = etree.SubElement(svg, "{%s}text" % SVG,
                             x=str(X0), y=str(baseline), fill="#000000")
        t.set("font-family", f"LatoTest{w}")
        t.set("font-size", str(size))
        t.set("text-anchor", "start")
        t.text = txt
    return etree.tostring(svg, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# --- medir con PIL ------------------------------------------------------------
pil = []
for w, txt, size in CASES:
    f = ImageFont.truetype(FONTS[w], size)
    asc, desc = f.getmetrics()
    pil.append({"w": w, "txt": txt, "size": size,
                "adv": f.getlength(txt), "bbox": f.getbbox(txt),
                "asc": asc, "desc": desc})

# --- construir SVG con filas separadas ----------------------------------------
rows, y = [], PAD
for c, m in zip(CASES, pil):
    y += m["asc"]
    rows.append((c, y))
    y += m["desc"] + ROW_GAP
W = int(max(m["adv"] for m in pil)) + 2 * X0
H = y + PAD
out_svg = os.path.abspath("out/_calib.svg")
os.makedirs("out", exist_ok=True)
with open(out_svg, "wb") as f:
    f.write(build_svg(rows, W, H))
print(f"SVG de calibracion: {out_svg}  ({W}x{H})")

# --- rasterizar con Chromium --------------------------------------------------
png = os.path.abspath("out/_calib.png")
tmp = tempfile.mkdtemp(prefix="chrome-calib-")
cmd = ["chromium", "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
       f"--user-data-dir={tmp}", f"--screenshot={png}",
       f"--window-size={W},{H}", "--default-background-color=FFFFFFFF",
       f"file://{out_svg}"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
if not os.path.exists(png):
    print("FALLA compuerta 4 (Chromium no rasterizo):\n", r.stderr[-1500:]); sys.exit(1)

a = np.array(Image.open(png).convert("L"))
print(f"PNG: {a.shape[1]}x{a.shape[0]}")

# --- medir tinta por fila -----------------------------------------------------
ink_cols = (a < 128)
print(f"\n{'peso':8} {'px':>4} {'PIL adv':>9} {'Blink':>8} {'ratio':>7}  texto")
ratios = {}
for (c, baseline), m in zip(rows, pil):
    top = max(0, baseline - m["asc"] - 4)
    bot = min(a.shape[0], baseline + m["desc"] + 4)
    band = ink_cols[top:bot]
    xs = np.where(band.any(axis=0))[0]
    if len(xs) == 0:
        print(f"  {m['w']:8} {m['size']:4} sin tinta -> FALLA @font-face")
        continue
    blink = xs.max() - xs.min() + 1
    # PIL: ancho de tinta = bbox[2]-bbox[0]
    pil_ink = m["bbox"][2] - m["bbox"][0]
    ratio = blink / pil_ink
    ratios.setdefault(m["w"], []).append(ratio)
    print(f"  {m['w']:8} {m['size']:4} {pil_ink:9.1f} {blink:8d} {ratio:7.4f}  {m['txt'][:30]}")

print("\n=== constante de calibracion por peso ===")
for w, rs in ratios.items():
    arr = np.array(rs)
    print(f"  {w:8}  media={arr.mean():.4f}  min={arr.min():.4f}  max={arr.max():.4f}  "
          f"desv max={100*max(abs(arr-1)):.2f}%")
print("\nCompuerta 4: @font-face base64 renderizo en Blink -> OK")
