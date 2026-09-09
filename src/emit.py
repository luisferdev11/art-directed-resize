"""Adaptador de salida: Layout -> SVG editable.

Decisiones de emision que no son negociables (ver plan-demo.md §7):
  · un <text> POR LINEA, con x/y absolutos y text-anchor="start". Sin cadenas de
    <tspan dy="1.2em">: es lo mas portable que se puede emitir.
  · nunca dominant-baseline: soporte irregular. Los baselines se calculan.
  · la caja del <image> preserva EXACTAMENTE el aspecto de la fuente y se traslada;
    con preserveAspectRatio="xMidYMid meet" y la caja ya en aspecto, meet y slice
    son identicos y la distorsion es imposible por construccion.
  · la fuente se referencia por URL RELATIVA y los TTF viajan al lado. Los TTF de
    Lato pesan 660KB: empotrarlos en 8 formatos serian 21MB. Un paquete de diseno
    real entrega las fuentes al lado, asi que esto es mas fiel, no menos.
"""
from __future__ import annotations
import base64, io, os, shutil
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from lxml import etree
from PIL import Image

import brand
import text as T

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
BLEED = 0.15          # sangrado alrededor del recorte: el disenador puede re-panear
MAX_PX = 1.5          # pixeles empotrados = 1.5x el tamano de salida
# 2x daba SVG de 2.7MB y 16MB de campana. 1.5x a calidad 82 conserva nitidez
# retina razonable y baja el paquete a un tercio.


def _sub(parent, tag, **kw):
    return etree.SubElement(parent, "{%s}%s" % (SVG, tag),
                            **{k.replace("_", "-"): str(v) for k, v in kw.items()})


def copy_fonts(out_dir: str, weights) -> None:
    d = os.path.join(out_dir, "fonts")
    os.makedirs(d, exist_ok=True)
    for w in weights:
        name = next(k for k, (_, ww) in brand.WEIGHTS.items() if ww == w)
        f = brand.WEIGHTS[name][0]
        dst = os.path.join(d, f)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(brand.FONT_DIR, f), dst)


def font_css(weights, prefix: str = "fonts") -> str:
    out = []
    for w in sorted(set(weights)):
        name = next(k for k, (_, ww) in brand.WEIGHTS.items() if ww == w)
        out.append(f"@font-face{{font-family:'Lato';font-weight:{w};font-style:normal;"
                   f"src:url({prefix}/{brand.WEIGHTS[name][0]}) format('truetype');}}")
    return "\n".join(out)


def photo_placement(src_path: str, crop_px: Tuple[float, float, float, float],
                    target: Tuple[float, float, float, float]
                    ) -> Tuple[str, Tuple[float, float, float, float]]:
    """Recorta con sangrado, reescala y devuelve (data URI, caja del <image>).

    `target` es el rectangulo destino en unidades de usuario: el lienzo completo en
    la hipotesis de sangre, o el rect del PANEL cuando la foto degrada. La caja se
    calcula para que el recorte pedido caiga exactamente sobre ese destino,
    conservando el aspecto de la fuente empotrada.
    """
    tx, ty, W, H = target
    cx, cy, cw, ch = crop_px
    im = Image.open(src_path).convert("RGB")
    pw, ph = im.size
    bx, by = cw * BLEED, ch * BLEED
    ex0, ey0 = max(0.0, cx - bx), max(0.0, cy - by)
    ex1, ey1 = min(float(pw), cx + cw + bx), min(float(ph), cy + ch + by)
    box = (int(ex0), int(ey0), int(ex1), int(ey1))
    sub = im.crop(box)

    # resolucion empotrada: MAX_PX veces el ancho de salida, escalado al trozo con sangrado
    want_w = int(round(W * MAX_PX * (sub.size[0] / cw)))
    if want_w < sub.size[0]:
        sub = sub.resize((want_w, max(1, int(round(sub.size[1] * want_w / sub.size[0])))),
                         Image.LANCZOS)
    buf = io.BytesIO()
    sub.save(buf, "JPEG", quality=82, optimize=True)
    uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    k = W / cw                                          # unidades de usuario por pixel fuente
    iw = (ex1 - ex0) * k
    ih = (ey1 - ey0) * k
    ix = tx - (cx - ex0) * k
    iy = ty - (cy - ey0) * k
    return uri, (ix, iy, iw, ih)


def _recolor(node, frm: str, to: str) -> None:
    """Intercambia un color en el nodo y sus hijos: la variante clara del logo."""
    for k in ("fill", "stroke"):
        v = (node.get(k) or "").strip().lower()
        if v and v != "none" and v == frm.lower():
            node.set(k, to)
    for c in node:
        _recolor(c, frm, to)


def write(path: str, W: float, H: float, layout: Dict[str, Any],
          photo_uri: str, photo_box, lockup_nodes: Optional[List[Any]] = None,
          lockup_xform: Optional[str] = None, lockup_invert: bool = False) -> None:
    root = etree.Element("{%s}svg" % SVG, nsmap={None: SVG, "xlink": XLINK})
    root.set("width", str(int(W))); root.set("height", str(int(H)))
    root.set("viewBox", f"0 0 {int(W)} {int(H)}")

    weights = sorted({b["weight"] for b in layout["blocks"]} |
                     ({900} if lockup_nodes else set()))
    defs = _sub(root, "defs")
    _sub(defs, "style").text = font_css(weights)
    clip = _sub(defs, "clipPath", id="canvasClip", clipPathUnits="userSpaceOnUse")
    # con panel, la foto se recorta AL PANEL: el resto es campo de marca
    pr = layout.get("panel") or (0, 0, W, H)
    _sub(clip, "rect", x=round(pr[0], 2), y=round(pr[1], 2),
         width=round(pr[2], 2), height=round(pr[3], 2))

    # --- campo de marca, debajo de todo (hipotesis de foto degradada) --------
    if layout.get("panel"):
        gp = _sub(root, "g", id="Brand field"); gp.set("data-name", "Brand field")
        _sub(gp, "rect", x=0, y=0, width=int(W), height=int(H),
             fill=brand.PALETTE["ink"])

    # --- fotografia -----------------------------------------------------------
    g = _sub(root, "g", id="Photograph"); g.set("data-name", "Photograph")
    g.set("clip-path", "url(#canvasClip)")
    ix, iy, iw, ih = photo_box
    img = _sub(g, "image", x=round(ix, 2), y=round(iy, 2),
               width=round(iw, 2), height=round(ih, 2),
               preserveAspectRatio="xMidYMid meet")
    img.set("{%s}href" % XLINK, photo_uri)
    img.set("href", photo_uri)

    # --- scrim con alpha resuelto --------------------------------------------
    for s in layout.get("scrims", []):
        gs = _sub(root, "g", id=f"Scrim {s['for']}"); gs.set("data-name", f"Scrim {s['for']}")
        _sub(gs, "rect", x=round(s["rect"][0], 2), y=round(s["rect"][1], 2),
             width=round(s["rect"][2], 2), height=round(s["rect"][3], 2),
             fill=s["fill"], opacity=round(s["alpha"], 3))

    # --- texto: un <text> por linea, baselines absolutos ---------------------
    for b in layout["blocks"]:
        gt = _sub(root, "g", id=b["role"].capitalize())
        gt.set("data-name", b["role"].capitalize())
        for line, baseline in zip(b["lines"], b["baselines"]):
            t = _sub(gt, "text", x=round(b["x"], 2), y=round(baseline, 2), fill=b["fill"])
            t.set("font-family", "Lato")
            t.set("font-weight", str(b["weight"]))
            t.set("font-size", str(b["size"]))
            t.set("text-anchor", "start")
            if b.get("tracking"):
                t.set("letter-spacing", str(b["tracking"]))
            t.text = line

    # --- lockup: escala uniforme, nunca recortado ----------------------------
    if lockup_nodes:
        gl = _sub(root, "g", id="Logo"); gl.set("data-name", "Logo")
        gl.set("transform", lockup_xform or "")
        for n in lockup_nodes:
            c = deepcopy(n)
            if lockup_invert:
                _recolor(c, brand.PALETTE["ink"], brand.PALETTE["light"])
            gl.append(c)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))
