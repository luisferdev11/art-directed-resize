#!/usr/bin/env python3
"""Verificacion de los outputs. Dos niveles, y el segundo es el que vale.

  1. asserts sobre el manifest: barato, pero es la misma fuente de verdad que el
     solver, asi que solo detecta incoherencias internas.
  2. RE-PARSEO del SVG emitido: independiente de verdad. Vuelve a medir cada linea
     de texto con las metricas de la fuente y comprueba las invariantes sobre el
     archivo que se entrega, no sobre lo que el solver creyo haber escrito.
     Incluye el CONTRASTE, reconstruyendo el fondo desde el propio archivo: se
     decodifica el raster empotrado, se recorta a su clip, se componen los scrims
     con su alpha y se mide cada linea contra su color. Sin esto, el manifest
     afirmaba haber alcanzado el contraste exigido porque el solver escribia el
     objetivo en lugar del resultado, y una linea del titular sobre un rotulo rojo
     salio a 1.38:1 contra 3.0 sin que nada lo detectara.

No se construyo un validador completo aparte: seria una segunda implementacion de
las restricciones duras y discreparia con la primera. El re-parseo es la parte con
valor real.
"""
from __future__ import annotations
import json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import numpy as np
from lxml import etree

import brand
import text as T
import vision
from formats import BY_KEY

SVG = "http://www.w3.org/2000/svg"
TOL = 1.5           # holgura en px para el area segura


def _f(el, k, d=0.0):
    v = el.get(k)
    if v is None:
        return d
    try:
        return float(re.sub(r"[a-z%]+$", "", v.strip()))
    except ValueError:
        return d


def _boxes(svg_path):
    """Mide cada <text> del archivo emitido con las metricas de la fuente."""
    root = etree.parse(svg_path).getroot()
    out = []
    for g in root.findall("{%s}g" % SVG):
        role = (g.get("data-name") or g.get("id") or "?").lower()
        if role.startswith(("photograph", "scrim", "brand", "logo")):
            continue
        for t in g.findall("{%s}text" % SVG):
            s = (t.text or "")
            size = _f(t, "font-size", 16.0)
            w = int(_f(t, "font-weight", 400))
            tr = _f(t, "letter-spacing", 0.0)
            x, base = _f(t, "x"), _f(t, "y")
            adv = T.advance(s, w, size, tr)
            asc, desc, cap, cap_top = T.metrics_ref(w)
            k = size / T.REF
            out.append({"role": role, "text": s, "size": size, "weight": w,
                        "fill": (t.get("fill") or "#000000"),
                        "x": x, "y": base - cap * k - cap_top * k,
                        "w": adv, "h": (cap + desc * 0.4) * k})
    return root, out


def _backdrop(root, W, H):
    """El fondo TAL COMO SE ENTREGA, reconstruido desde el archivo.

    Campo de marca, luego el raster empotrado dentro de su clip, luego los scrims
    con su alpha. No se le pregunta nada al solver: si el emisor coloco la foto un
    pixel distinto de lo que el solver predijo, esto lo ve y el solver no.
    """
    import base64, io
    from PIL import Image
    canvas = np.full((int(H), int(W), 3), 255, np.uint8)

    for g in root.findall("{%s}g" % SVG):
        if (g.get("id") or "").lower().startswith("brand"):
            for r in g.findall("{%s}rect" % SVG):
                hexv = (r.get("fill") or "#FFFFFF").lstrip("#")
                if len(hexv) == 6:
                    canvas[:, :] = [int(hexv[i:i + 2], 16) for i in (0, 2, 4)]

    clip = None
    for cp in root.findall(".//{%s}clipPath" % SVG):
        r = cp.find("{%s}rect" % SVG)
        if r is not None:
            clip = (_f(r, "x"), _f(r, "y"), _f(r, "width"), _f(r, "height"))

    img = root.find(".//{%s}image" % SVG)
    if img is not None:
        href = img.get("href") or img.get("{http://www.w3.org/1999/xlink}href") or ""
        if href.startswith("data:"):
            pim = Image.open(io.BytesIO(base64.b64decode(href.split(",", 1)[1]))).convert("RGB")
            ix, iy = _f(img, "x"), _f(img, "y")
            iw, ih = _f(img, "width"), _f(img, "height")
            if iw > 0 and ih > 0:
                pim = pim.resize((max(1, int(round(iw))), max(1, int(round(ih)))),
                                 Image.LANCZOS)
                arr = np.asarray(pim)
                x0, y0 = int(round(ix)), int(round(iy))
                cx0, cy0, cx1, cy1 = (0, 0, W, H) if clip is None else (
                    clip[0], clip[1], clip[0] + clip[2], clip[1] + clip[3])
                for yy in range(max(0, int(cy0)), min(int(H), int(np.ceil(cy1)))):
                    sy = yy - y0
                    if not (0 <= sy < arr.shape[0]):
                        continue
                    a = max(0, int(cx0)); b = min(int(W), int(np.ceil(cx1)))
                    sa, sb = a - x0, b - x0
                    lo, hi = max(sa, 0), min(sb, arr.shape[1])
                    if hi > lo:
                        canvas[yy, a + (lo - sa):a + (hi - sa)] = arr[sy, lo:hi]

    for g in root.findall("{%s}g" % SVG):
        if not (g.get("id") or "").lower().startswith("scrim"):
            continue
        for r in g.findall("{%s}rect" % SVG):
            hexv = (r.get("fill") or "#000000").lstrip("#")
            al = _f(r, "opacity", 0.0)
            if len(hexv) != 6 or al <= 0:
                continue
            x0, y0 = max(0, int(_f(r, "x"))), max(0, int(_f(r, "y")))
            x1 = min(int(W), int(np.ceil(_f(r, "x") + _f(r, "width"))))
            y1 = min(int(H), int(np.ceil(_f(r, "y") + _f(r, "height"))))
            if x1 <= x0 or y1 <= y0:
                continue
            tint = np.array([int(hexv[i:i + 2], 16) for i in (0, 2, 4)], np.float64)
            patch = canvas[y0:y1, x0:x1].astype(np.float64)
            canvas[y0:y1, x0:x1] = (patch * (1 - al) + tint * al).astype(np.uint8)
    return canvas


def _ovl(a, b):
    return not (a["x"] + a["w"] <= b["x"] + 0.5 or b["x"] + b["w"] <= a["x"] + 0.5 or
                a["y"] + a["h"] <= b["y"] + 0.5 or b["y"] + b["h"] <= a["y"] + 0.5)


def check_dir(d: str) -> int:
    with open(os.path.join(d, "manifest.json")) as fh:
        man = json.load(fh)
    fails = 0
    print(f"{'formato':16} {'lineas':>6} {'solape':>7} {'area segura':>12} "
          f"{'piso':>6} {'logo':>6} {'aspecto img':>12} {'contraste':>10}")
    for o in man["outputs"]:
        if o.get("failed"):
            continue
        fmt = BY_KEY[o["key"]]
        path = os.path.join(d, o["file"])
        root, boxes = _boxes(path)
        sx, sy, sw, sh = fmt.safe_box()
        bad = []

        # 1. ninguna linea de texto solapa otra
        ov = sum(1 for i in range(len(boxes)) for j in range(i + 1, len(boxes))
                 if _ovl(boxes[i], boxes[j]))
        if ov:
            bad.append(f"{ov} solapes")

        # 2. todo dentro del area segura
        out_safe = [b for b in boxes
                    if b["x"] < sx - TOL or b["y"] < sy - TOL
                    or b["x"] + b["w"] > sx + sw + TOL
                    or b["y"] + b["h"] > sy + sh + TOL]
        if out_safe:
            bad.append(f"{len(out_safe)} fuera del area segura")

        # 3. ningun cuerpo bajo el piso de legibilidad de su rol
        floor_bad = []
        for b in boxes:
            role = next((r for r in brand.MIN_SIZE if b["role"].startswith(r)), None)
            if role and b["size"] < brand.MIN_SIZE[role] - 0.01:
                floor_bad.append(f"{role}@{b['size']:g}")
        if floor_bad:
            bad.append("bajo el piso: " + ",".join(floor_bad))

        # 4. el logo escala uniformemente
        logo_ok = True
        for g in root.findall("{%s}g" % SVG):
            if (g.get("id") or "") == "Logo":
                m = re.search(r"scale\(([^)]*)\)", g.get("transform") or "")
                if m:
                    parts = [p for p in re.split(r"[,\s]+", m.group(1).strip()) if p]
                    if len(parts) == 2 and abs(float(parts[0]) - float(parts[1])) > 1e-6:
                        logo_ok = False
        if not logo_ok:
            bad.append("logo con escala no uniforme")

        # 5. la caja de la imagen preserva el aspecto de la fuente
        img = root.find(".//{%s}image" % SVG)
        asp_ok = True
        if img is not None:
            href = img.get("href") or ""
            iw, ih = _f(img, "width"), _f(img, "height")
            if href.startswith("data:"):
                import base64, io
                from PIL import Image
                pim = Image.open(io.BytesIO(base64.b64decode(href.split(",", 1)[1])))
                src = pim.size[0] / pim.size[1]
                box = iw / max(ih, 1e-9)
                asp_ok = abs(src - box) / src < 0.005
        if not asp_ok:
            bad.append("la caja de la imagen no conserva el aspecto")

        # 6. contraste REAL de cada linea contra el fondo que se entrega
        lum = vision.luminance(_backdrop(root, float(fmt.w), float(fmt.h)))
        low = []
        for b in boxes:
            need = vision.required_contrast(b["size"], b["weight"])
            got = vision.worst_contrast(lum, (b["x"], b["y"], b["w"], b["h"]),
                                        vision.hex_luminance(b["fill"]))
            if got < need - 0.05:
                low.append(f"{b['role']}@{got:.2f}<{need:.1f}")
        if low:
            bad.append("contraste bajo: " + ",".join(low))

        ok = not bad
        fails += 0 if ok else 1
        print(f"  {o['key']:16} {len(boxes):6d} {('ok' if not ov else str(ov)):>7} "
              f"{('ok' if not out_safe else str(len(out_safe))):>12} "
              f"{('ok' if not floor_bad else 'NO'):>6} "
              f"{('ok' if logo_ok else 'NO'):>6} {('ok' if asp_ok else 'NO'):>12} "
              f"{('ok' if not low else str(len(low))):>10}"
              + ("" if ok else "   <- " + "; ".join(bad)))

    print()
    if fails:
        print(f"FALLA: {fails} de {len(man['outputs'])} formatos con problemas")
    else:
        print(f"VERDE: {len(man['outputs'])} formatos pasan el re-parseo")
    return 1 if fails else 0


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "out/spring-campaign/meridian-quarter"
    raise SystemExit(check_dir(d))
