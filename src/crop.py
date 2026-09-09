"""Eleccion del recorte: que region de la fotografia sobrevive en cada formato.

La cara es restriccion DURA cuando existe: en creatividad de retail property no se
recorta una cara. La saliencia es objetivo suave. Y se prefiere el sujeto fuera del
centro geometrico, porque centrar todo lee como plantilla.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

import numpy as np

import vision

Rect = Tuple[float, float, float, float]

SCALES = (1.00, 0.92, 0.84, 0.76, 0.68, 0.60, 0.52)
STEPS = 13                     # posiciones por eje
THIRDS = (1 / 3, 2 / 3)


def _inter_area(a: Rect, b: Rect) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def choose(px_w: int, px_h: int, target_aspect: float,
           sal_ii: np.ndarray, grid: Tuple[int, int],
           face: Optional[Rect], min_face_frac: float = 0.055,
           max_face_frac: float = 0.45
           ) -> Tuple[Rect, Dict[str, float]]:
    """Devuelve (recorte en pixeles de la fuente, diagnostico).

    Dos guardas sobre la cara, y hacen falta las dos:
      min_face_frac: por debajo, el sujeto es ilegible.
      max_face_frac: por encima, el recorte es una tira que corta la cabeza. Contener
        la caja de la cara NO basta: si la cara ocupa el 76% del alto de una tira 8:1,
        la restriccion dice verde y el resultado se lee roto.

    Cuando ninguna ventana satisface ambas, el recorte a sangre es INSATISFACIBLE y
    se marca `face_unsatisfiable`: el solver debe entonces degradar la foto a panel.
    Esa es una decision estructural emergente de una falla de restriccion medida.
    """
    gw, gh = grid
    sx, sy = gw / px_w, gh / px_h
    best, best_score, diag = None, -1e18, {}
    face_ok_any = False

    for s in SCALES:
        # ventana mas grande con el aspecto pedido, escalada por s
        cw = min(px_w, px_h * target_aspect) * s
        ch = cw / target_aspect
        if cw < 32 or ch < 32 or cw > px_w or ch > px_h:
            continue
        for iy in range(STEPS):
            for ix in range(STEPS):
                x = (px_w - cw) * ix / max(STEPS - 1, 1)
                y = (px_h - ch) * iy / max(STEPS - 1, 1)
                rect = (x, y, cw, ch)

                # --- restriccion dura: la cara entera, y no minuscula ---------
                if face is not None:
                    if _inter_area(rect, face) < 0.995 * face[2] * face[3]:
                        continue
                    frac = face[3] / ch
                    if frac < min_face_frac or frac > max_face_frac:
                        continue
                    face_ok_any = True

                # --- masa de saliencia contenida, O(1) -----------------------
                gx0 = int(round(x * sx)); gy0 = int(round(y * sy))
                gx1 = min(gw, max(gx0 + 1, int(round((x + cw) * sx))))
                gy1 = min(gh, max(gy0 + 1, int(round((y + ch) * sy))))
                mass = vision.rect_mean(sal_ii, gx0, gy0, gx1, gy1)

                # --- preferencias suaves --------------------------------------
                res = cw / px_w                      # conservar resolucion
                pos = 0.0
                if face is not None:
                    fx = (face[0] + face[2] / 2 - x) / cw
                    fy = (face[1] + face[3] / 2 - y) / ch
                    pos = -min(abs(fx - THIRDS[0]), abs(fx - THIRDS[1])) \
                          - 0.6 * min(abs(fy - THIRDS[0]), abs(fy - THIRDS[1]))
                score = 2.2 * mass + 1.0 * res + 0.9 * pos
                if score > best_score:
                    best, best_score = rect, score
                    diag = {"mass": mass, "res": res, "pos": pos, "scale": s}

    if best is None:
        # ninguna ventana satisface la cara: el formato debe degradar la foto.
        # No se recorta la cara a la fuerza; se informa y el solver decide.
        cw = min(px_w, px_h * target_aspect)
        ch = cw / target_aspect
        best = ((px_w - cw) / 2, (px_h - ch) / 2, cw, ch)
        diag = {"mass": 0.0, "res": cw / px_w, "pos": 0.0, "scale": 1.0,
                "face_unsatisfiable": 1.0}
    diag["face_contained"] = 1.0 if face_ok_any else 0.0
    return best, diag


def prepare(photo_path: str, grid: Tuple[int, int] = (96, 96)):
    """Precomputa lo que se reutiliza en todos los formatos."""
    from PIL import Image
    import cv2
    im = Image.open(photo_path).convert("RGB")
    rgb = np.asarray(im)
    sal_box, face = vision.focal_region(rgb)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    S = vision.saliency(cv2.resize(gray, grid, interpolation=cv2.INTER_AREA))
    lo, hi = np.percentile(S, 2), np.percentile(S, 98)
    S = np.clip((S - lo) / max(hi - lo, 1e-9), 0, 1)
    return {"rgb": rgb, "px_w": im.size[0], "px_h": im.size[1],
            "sal_box": sal_box, "face": face,
            "sal_ii": vision.integral(S), "grid": grid}
