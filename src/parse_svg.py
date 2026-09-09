"""Adaptador de entrada: SVG -> Scene, con inferencia de roles.

REGLA DURA: la inferencia NO LEE NOMBRES DE CAPA. Los nombres existen en el master
porque los disenadores nombran capas, pero el rol se deduce de tipo, tamano
relativo y area. Si el sistema dependiera de los nombres, el master seria un
archivo autoreado para la herramienta, que es exactamente la queja del cliente.

Se puede renombrar todo a "Layer 1" y el resultado no cambia.
"""
from __future__ import annotations
import base64, io, os, re
from typing import Any, Dict, List, Optional, Tuple

from lxml import etree
from PIL import Image

from scene import Lockup, Photo, Scene, TextBlock
import text as T

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
VECTOR_TAGS = {"path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}
LEGAL_RATIO = 0.30       # si el bloque mas chico mide < 30% del titular, es legal


def _tag(el) -> str:
    return etree.QName(el).localname


def _f(el, name: str, default: float = 0.0) -> float:
    v = el.get(name)
    if v is None:
        return default
    try:
        return float(re.sub(r"[a-z%]+$", "", v.strip()))
    except ValueError:
        return default


def _weight(el) -> int:
    v = el.get("font-weight") or "400"
    try:
        return int(float(v))
    except ValueError:
        return 700 if v in ("bold", "bolder") else 400


def _decode_image(el, out_dir: str, stem: str) -> Tuple[str, int, int]:
    href = el.get("{%s}href" % XLINK) or el.get("href") or ""
    if href.startswith("data:"):
        b64 = href.split(",", 1)[1]
        raw = base64.b64decode(b64)
        im = Image.open(io.BytesIO(raw))
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{stem}.jpg")
        im.convert("RGB").save(path, "JPEG", quality=95)
        return path, im.size[0], im.size[1]
    path = href
    im = Image.open(path)
    return path, im.size[0], im.size[1]


def _text_rect(el) -> Tuple[float, float, float, float, float, int, float]:
    size = _f(el, "font-size", 16.0)
    w = _weight(el)
    tr = _f(el, "letter-spacing", 0.0)
    x, base = _f(el, "x"), _f(el, "y")
    s = (el.text or "").strip()
    adv = T.advance(s, w, size, tr)
    asc = T.ascent(w, size)
    return x, base - asc, adv, size * 1.2, size, w, tr


RASTER_EXT = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp")


def parse(svg_path: str, work_dir: str = "out/_work") -> Scene:
    """Router de entrada por estructura de archivo.

    Un SVG trae su arbol y se lee midiendolo. Un raster no trae nada, y entonces la
    escena la deduce un modelo multimodal (`semantic.py`). Las dos ramas devuelven
    el MISMO `Scene`: aguas abajo, solver, emisor y validador son identicos.
    """
    if os.path.splitext(svg_path)[1].lower() in RASTER_EXT:
        import semantic
        return semantic.parse_raster(svg_path, work_dir)
    tree = etree.parse(svg_path)
    root = tree.getroot()
    W = _f(root, "width") or 1000.0
    H = _f(root, "height") or 1000.0
    sc = Scene(width=W, height=H)

    # --- 1. fotografia: el raster de mayor area ------------------------------
    images = root.findall(".//{%s}image" % SVG)
    if images:
        big = max(images, key=lambda e: (_f(e, "width") * _f(e, "height")) or 1.0)
        path, pw, ph = _decode_image(big, work_dir, "photo")
        sc.photo = Photo(rect=(_f(big, "x"), _f(big, "y"),
                               _f(big, "width") or W, _f(big, "height") or H),
                         src_path=path, px_w=pw, px_h=ph)
        sc.notes.append(f"foto: raster de mayor area, {pw}x{ph}px sobre "
                        f"{sc.photo.rect[2]:.0f}x{sc.photo.rect[3]:.0f} unidades")

    # --- 2. lockup: grupo con geometria vectorial ----------------------------
    bound_texts: set = set()
    best_g, best_area = None, None
    for g in root.findall(".//{%s}g" % SVG):
        vec = [c for c in g.iter() if _tag(c) in VECTOR_TAGS and _tag(c) != "rect"] or \
              [c for c in g.iter() if _tag(c) in VECTOR_TAGS]
        if not vec:
            continue
        xs, ys, xe, ye = [], [], [], []
        for c in vec:
            t = _tag(c)
            if t == "circle":
                cx, cy, r = _f(c, "cx"), _f(c, "cy"), _f(c, "r")
                xs.append(cx - r); ys.append(cy - r); xe.append(cx + r); ye.append(cy + r)
            elif t == "line":
                xs.append(min(_f(c, "x1"), _f(c, "x2"))); xe.append(max(_f(c, "x1"), _f(c, "x2")))
                ys.append(min(_f(c, "y1"), _f(c, "y2"))); ye.append(max(_f(c, "y1"), _f(c, "y2")))
            elif t == "rect":
                xs.append(_f(c, "x")); ys.append(_f(c, "y"))
                xe.append(_f(c, "x") + _f(c, "width")); ye.append(_f(c, "y") + _f(c, "height"))
        if not xs:
            continue
        gx, gy = min(xs), min(ys)
        gw, gh = max(xe) - gx, max(ye) - gy
        # texto dentro del grupo pertenece al lockup
        tx = g.findall(".//{%s}text" % SVG)
        for t_el in tx:
            x, y, w, h, *_ = _text_rect(t_el)
            gx, gy = min(gx, x), min(gy, y)
            gw = max(gx + gw, x + w) - gx
            gh = max(gy + gh, y + h) - gy
            bound_texts.add(id(t_el))
        area = gw * gh
        if area <= 0 or area > 0.25 * W * H:      # un logo es pequeno
            continue
        if best_area is None or area < best_area:
            best_g, best_area = (g, (gx, gy, gw, gh)), area
    if best_g:
        g, rect = best_g
        marks, wsize, mrect = [], 0.0, None
        mxs, mys, mxe, mye = [], [], [], []
        for c in g:
            t = _tag(c)
            if t == "text":
                wsize = max(wsize, _f(c, "font-size", 0.0))
            else:
                marks.append(c)
                if t == "circle":
                    cx, cy, rr = _f(c, "cx"), _f(c, "cy"), _f(c, "r")
                    mxs.append(cx - rr); mys.append(cy - rr)
                    mxe.append(cx + rr); mye.append(cy + rr)
                elif t == "line":
                    mxs.append(min(_f(c, "x1"), _f(c, "x2")))
                    mxe.append(max(_f(c, "x1"), _f(c, "x2")))
                    mys.append(min(_f(c, "y1"), _f(c, "y2")))
                    mye.append(max(_f(c, "y1"), _f(c, "y2")))
        if mxs:
            mrect = (min(mxs), min(mys), max(mxe) - min(mxs), max(mye) - min(mys))
        sc.lockup = Lockup(rect=rect, nodes=list(g), mark_nodes=marks,
                           mark_rect=mrect, wordmark_size=wsize)
        sc.notes.append(f"lockup: grupo con geometria vectorial, area menor, "
                        f"{rect[2]:.0f}x{rect[3]:.0f} en ({rect[0]:.0f},{rect[1]:.0f})"
                        + (f"; marca {mrect[2]:.0f}x{mrect[3]:.0f} y wordmark a "
                           f"{wsize:g}px" if mrect else ""))

    # --- 3. bloques de texto libres ------------------------------------------
    raw = []
    for el in root.findall(".//{%s}text" % SVG):
        if id(el) in bound_texts:
            continue
        s = (el.text or "").strip()
        if not s:
            continue
        x, y, w, h, size, weight, tr = _text_rect(el)
        raw.append({"s": s, "x": x, "y": y, "w": w, "h": h,
                    "size": size, "weight": weight, "tr": tr,
                    "fill": el.get("fill") or "#000000"})

    # fusionar lineas contiguas del mismo estilo (el titular son dos <text>)
    raw.sort(key=lambda r: (r["y"], r["x"]))
    blocks: List[Dict[str, Any]] = []
    for r in raw:
        m = None
        for b in blocks:
            if (abs(b["size"] - r["size"]) < 0.6 and b["weight"] == r["weight"]
                    and b["fill"] == r["fill"] and abs(b["x"] - r["x"]) < 2.5):
                gap = r["y"] - (b["y"] + b["h"] * (b["n"] - 1))
                if 0.4 * b["size"] <= gap <= 1.9 * b["size"]:
                    m = b
                    break
        if m:
            m["s"] += " " + r["s"]; m["n"] += 1
            m["w"] = max(m["w"], r["w"])
        else:
            blocks.append(dict(r, n=1))

    blocks.sort(key=lambda b: -b["size"])
    roles: List[str] = []
    if blocks:
        head = blocks[0]["size"]
        n = len(blocks)
        legal_last = n >= 2 and blocks[-1]["size"] < LEGAL_RATIO * head
        mid = ["subhead", "support"]
        for i, b in enumerate(blocks):
            if i == 0:
                roles.append("headline")
            elif legal_last and i == n - 1:
                roles.append("legal")
            else:
                roles.append(mid[min(len(roles) - 1, len(mid) - 1)] if len(roles) - 1 < len(mid) else "support")
        sc.notes.append("roles por rango de cuerpo: " + ", ".join(
            f"{r}={b['size']:g}px" for r, b in zip(roles, blocks)))
        if legal_last:
            sc.notes.append(f"el bloque menor ({blocks[-1]['size']:g}px) mide "
                            f"< {LEGAL_RATIO:.0%} del titular ({head:g}px) -> legal")

    for role, b in zip(roles, blocks):
        h_total = b["h"] * b["n"]
        sc.texts.append(TextBlock(role=role, words=b["s"].split(), size=b["size"],
                                  weight=b["weight"], fill=b["fill"], tracking=b["tr"],
                                  rect=(b["x"], b["y"], b["w"], h_total),
                                  n_lines_master=b["n"]))
    return sc
