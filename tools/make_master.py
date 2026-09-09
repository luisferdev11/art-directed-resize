"""Autorea assets/master.svg: la pieza master del demo.

REGLA CRITICA: el master NO lleva data-role ni data-focal. Los nombres de capa son
realistas porque los disenadores nombran capas, pero la inferencia de roles NUNCA los
lee. Si alguien abre este archivo y ve pistas semanticas para la herramienta,
recreamos la queja del cliente ("requires a base Master example to be created first").
"""
from __future__ import annotations
import base64, io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from PIL import Image, ImageFont
from lxml import etree
import brand

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
W, H = 1080, 1350
SRC = "/home/pillofon/Downloads/PXL_20260330_105145119.jpg"
CROP = (45, 460, 45 + 2400, 460 + 3000)      # candidato A, elegido por composicion
OUT = "assets/master.svg"

COPY = {
    "headline": ["SPRING STYLE", "IS HERE"],
    "subhead":  "Up to 50% off across 120 stores",
    "support":  "12 - 28 SEPTEMBER",
    "legal":    "Terms and conditions apply. See centre for details.",
    "wordmark": "MERIDIAN QUARTER",
}

def font(weight, size):
    return ImageFont.truetype(os.path.join(brand.FONT_DIR, brand.WEIGHTS[weight][0]), size)

def b64_font(weight):
    with open(os.path.join(brand.FONT_DIR, brand.WEIGHTS[weight][0]), "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def sub(parent, tag, **kw):
    return etree.SubElement(parent, "{%s}%s" % (SVG, tag), **{k.replace("_", "-"): str(v) for k, v in kw.items()})

def text(parent, s, x, baseline, weight, size, fill, tracking=0.0):
    t = sub(parent, "text", x=round(x, 2), y=round(baseline, 2), fill=fill)
    t.set("font-family", "Lato")
    t.set("font-weight", str(brand.WEIGHTS[weight][1]))
    t.set("font-size", str(size))
    t.set("text-anchor", "start")
    if tracking:
        t.set("letter-spacing", str(tracking))
    t.text = s
    return t

# ---------- fotografia ----------
# 2x: los masters reales llevan pixel de sobra. El lienzo es 1080x1350 en
# unidades de usuario, pero la imagen empotrada trae 2160x2700 pixeles.
im = Image.open(SRC).crop(CROP).resize((W * 2, H * 2), Image.LANCZOS)
buf = io.BytesIO(); im.save(buf, "JPEG", quality=88, optimize=True)
photo_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
print(f"foto: {len(buf.getvalue())/1024:.0f} KB -> base64 {len(photo_b64)/1024:.0f} KB")

# ---------- documento ----------
root = etree.Element("{%s}svg" % SVG, nsmap={None: SVG, "xlink": XLINK})
root.set("width", str(W)); root.set("height", str(H))
root.set("viewBox", f"0 0 {W} {H}")
defs = sub(root, "defs")
style = sub(defs, "style")
style.text = "\n".join(
    f"@font-face{{font-family:'Lato';font-weight:{brand.WEIGHTS[w][1]};font-style:normal;"
    f"src:url(data:font/ttf;base64,{b64_font(w)}) format('truetype');}}"
    for w in ("black", "regular"))
clip = sub(defs, "clipPath", id="canvasClip", clipPathUnits="userSpaceOnUse")
sub(clip, "rect", x=0, y=0, width=W, height=H)

# capa foto, recortada al lienzo
g_photo = sub(root, "g", id="Photograph")
g_photo.set("data-name", "Photograph")
g_photo.set("clip-path", "url(#canvasClip)")
img = sub(g_photo, "image", x=0, y=0, width=W, height=H, preserveAspectRatio="xMidYMid meet")
img.set("{%s}href" % XLINK, f"data:image/jpeg;base64,{photo_b64}")
img.set("href", f"data:image/jpeg;base64,{photo_b64}")

INK, PAPER, ACCENT = brand.PALETTE["ink"], brand.PALETTE["paper"], brand.PALETTE["accent"]
M = 64.0

# titular: dos lineas, sobre el cielo claro (contraste medido 6.8-7.8:1)
g = sub(root, "g", id="Headline"); g.set("data-name", "Headline")
hs = 92
f = font("black", hs); asc, desc = f.getmetrics()
lead = round(hs * 1.02, 2)
y = 96 + asc
for line in COPY["headline"]:
    text(g, line, M, y, "black", hs, INK)
    y += lead

# subtitulo
g = sub(root, "g", id="Subhead"); g.set("data-name", "Subhead")
ss = 30
y = y - lead + font("regular", ss).getmetrics()[0] + 34
text(g, COPY["subhead"], M, y, "regular", ss, INK)

# elemento de campana
g = sub(root, "g", id="Campaign dates"); g.set("data-name", "Campaign dates")
cs = 20
y += font("black", cs).getmetrics()[0] + 18
# tinta, no acento: el naranja medido daba 1.06:1 sobre este fondo (exige 3.0).
# El acento se reserva para las decisiones del motor en los outputs.
text(g, COPY["support"], M, y, "black", cs, INK, tracking=1.6)

# lockup de logo, arriba a la derecha (contraste medido 7.8:1)
g = sub(root, "g", id="Logo"); g.set("data-name", "Logo")
ws = 15
fw = font("black", ws)
tw = fw.getlength(COPY["wordmark"]) + 1.6 * (len(COPY["wordmark"]) - 1)
r = 17.0
lx = W - M - tw - 14 - 2 * r
cy = 96 + r
sub(g, "circle", cx=round(lx + r, 2), cy=round(cy, 2), r=r,
    fill="none", stroke=INK, stroke_width=2.6)
for dy in (-6.4, 0.0, 6.4):
    half = (r ** 2 - dy ** 2) ** 0.5 * 0.94
    sub(g, "line", x1=round(lx + r - half, 2), y1=round(cy + dy, 2),
        x2=round(lx + r + half, 2), y2=round(cy + dy, 2), stroke=INK, stroke_width=1.7)
text(g, COPY["wordmark"], lx + 2 * r + 14, cy + fw.getmetrics()[0] / 2 - 3, "black", ws, INK, tracking=1.6)

# legal: abajo, en texto claro, DELIBERADAMENTE bajo el umbral de contraste.
# El motor debe detectarlo y anadir scrim en los outputs. Ver guion.md.
g = sub(root, "g", id="Legal"); g.set("data-name", "Legal")
ls = 13
text(g, COPY["legal"], M, H - 52, "regular", ls, PAPER)

os.makedirs("assets", exist_ok=True)
with open(OUT, "wb") as fh:
    fh.write(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))
kb = os.path.getsize(OUT) / 1024
print(f"escrito {OUT}  ({kb:.0f} KB)")
n_text = len(root.findall(".//{%s}text" % SVG))
print(f"elementos: {n_text} text, {len(root.findall('.//{%s}image' % SVG))} image, "
      f"{len(root.findall('.//{%s}g' % SVG))} grupos")
bad = [a for e in root.iter() for a in e.attrib if a.startswith("data-") and a != "data-name"]
print(f"atributos data-* semanticos (debe ser 0): {len(bad)}")
