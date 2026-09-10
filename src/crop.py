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

# Region focal BLANDA. Peso de la cobertura en el score: por encima del de la masa de
# saliencia (2.2), para que conservar al sujeto mande sobre el resto de la composicion.
W_SOFT_COVER = 3.0
# Por debajo de esta cobertura, ni el mejor encuadre a sangre conserva al sujeto y la
# foto degrada a panel. 0.72 deja pasar a 4:5 y 1:1 sobre un grupo, y sigue mandando
# a panel las tiras de 8:1, que es donde el panel es la respuesta correcta.
SOFT_MIN_COVER = 0.72


def _inter_area(a: Rect, b: Rect) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def choose(px_w: int, px_h: int, target_aspect: float,
           sal_ii: np.ndarray, grid: Tuple[int, int],
           face: Optional[Rect], min_face_frac: float = 0.055,
           max_face_frac: float = 0.45, face_hard: bool = True
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

    `face_hard=False` -LA REGION ES BLANDA-
    ---------------------------------------
    Las dos guardas de arriba estan calibradas sobre UNA CARA. Aplicadas a la region
    de un GRUPO dicen "insatisfacible" casi siempre, y por una razon puramente
    geometrica: la caja de un grupo conserva todo el ancho del sujeto -es su
    extension, y encogerla deja fuera a la gente de los extremos-, asi que ninguna
    ventana mas estrecha que la fuente la contiene al 99.5%. Medido sobre tres fotos
    de grupo, el resultado era panel en 5 de 5, 4 de 5 y 2 de 5 formatos: la foto
    degradada no porque el encuadre fallara, sino porque la restriccion no sabia
    expresar "conserva a la mayor parte".

    Con la region blanda la COBERTURA sale del filtro y entra al SCORE con peso
    dominante. Se sigue prefiriendo contener el sujeto entero por encima de la masa
    de saliencia, pero un formato que no puede contenerlo del todo produce el mejor
    encuadre disponible en lugar de rendirse.

    Las guardas de PROPORCION siguen siendo filtro, tambien cuando la region es
    blanda: "que el recorte no sea una tira sobre el sujeto" vale igual para una cara
    que para un grupo. Relajar las dos a la vez sacaba el leaderboard 8:1 a sangre con
    coste 0.77 y 1.00 -el texto sin donde caer- en lugar de degradar a panel.

    Y no desaparece la degradacion a panel: si ni la mejor ventana alcanza
    SOFT_MIN_COVER de la region, se marca `face_unsatisfiable` igual. A 8:1 con un
    grupo, el panel sigue siendo la respuesta correcta; lo que se arregla es que a
    4:5 dejara de serlo.
    """
    gw, gh = grid
    sx, sy = gw / px_w, gh / px_h
    best, best_score, diag = None, -1e18, {}
    face_ok_any = False
    best_cover = 0.0

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

                # --- la region focal: dura por defecto, blanda si se pide ------
                #
                # BLANDA RELAJA LA CONTENCION, NO LAS PROPORCIONES. Las dos guardas
                # hacen trabajos distintos y solo una esta mal calibrada para un
                # grupo:
                #
                #   contencion al 99.5%  "no dejes fuera a nadie". Sobre una
                #       extension ancha es insatisfacible por geometria, y es la que
                #       mandaba la foto a panel en casi todos los formatos.
                #   min/max_face_frac    "que el recorte no sea una tira sobre el
                #       sujeto". Eso vale igual para una cara que para un grupo: a
                #       8:1 una banda de caras llena el alto, y el resultado es una
                #       tira sin aire ni sitio para el texto. Medido al relajar las
                #       dos: el leaderboard salia a sangre con coste 0.77 y 1.00
                #       -el texto sin donde caer- en lugar de degradar a panel, que
                #       ahi es la respuesta correcta.
                #
                # Asi que la cobertura pasa al score y las proporciones siguen siendo
                # filtro. El panel vuelve a aparecer donde debe, y solo donde debe.
                cover = 1.0
                if face is not None:
                    area = max(face[2] * face[3], 1e-9)
                    cover = _inter_area(rect, face) / area
                    frac = face[3] / ch
                    if frac < min_face_frac or frac > max_face_frac:
                        continue
                    if face_hard:
                        if cover < 0.995:
                            continue
                        face_ok_any = True
                    else:
                        if cover >= 0.995:
                            face_ok_any = True
                        best_cover = max(best_cover, cover)

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
                if face is not None and not face_hard:
                    # Peso por encima de la masa de saliencia (2.2): conservar al
                    # sujeto manda sobre el resto de la composicion.
                    score += W_SOFT_COVER * cover
                if score > best_score:
                    best, best_score = rect, score
                    diag = {"mass": mass, "res": res, "pos": pos, "scale": s,
                            "cover": cover}

    if best is None:
        # ninguna ventana satisface la cara: el formato debe degradar la foto.
        # No se recorta la cara a la fuerza; se informa y el solver decide.
        cw = min(px_w, px_h * target_aspect)
        ch = cw / target_aspect
        best = ((px_w - cw) / 2, (px_h - ch) / 2, cw, ch)
        diag = {"mass": 0.0, "res": cw / px_w, "pos": 0.0, "scale": 1.0,
                "face_unsatisfiable": 1.0}
    elif face is not None and not face_hard:
        # La region blanda no hace insatisfacible ninguna ventana, asi que el limite
        # se pone aqui: si ni la mejor conserva SOFT_MIN_COVER del sujeto, la foto no
        # cabe a sangre y el solver degrada a panel. Es la misma decision estructural
        # de antes, tomada sobre cuanto se conserva en lugar de sobre todo o nada.
        cov = diag.get("cover", 0.0)
        if cov < SOFT_MIN_COVER:
            diag["face_unsatisfiable"] = 1.0
            diag["soft_cover"] = cov
    diag["face_contained"] = 1.0 if face_ok_any else 0.0
    if face is not None and not face_hard:
        diag["face_soft"] = 1.0
        diag.setdefault("soft_cover", diag.get("cover", best_cover))
    return best, diag


def prepare(photo_path: str, grid: Tuple[int, int] = (96, 96)):
    """Precomputa lo que se reutiliza en todos los formatos."""
    from PIL import Image
    import cv2
    im = Image.open(photo_path).convert("RGB")
    rgb = np.asarray(im)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    sal_box, face = vision.focal_region(rgb)
    # La lista completa viaja aparte: quien decide necesita saber si la duda viene
    # de que no hay ninguna cara o de que hay muchas, y son dos casos distintos.
    caras = vision.agreed_faces(gray)
    S = vision.saliency(cv2.resize(gray, grid, interpolation=cv2.INTER_AREA))
    lo, hi = np.percentile(S, 2), np.percentile(S, 98)
    S = np.clip((S - lo) / max(hi - lo, 1e-9), 0, 1)
    # `face_hard`: la region que sale de las cascadas es UNA CARA, y las guardas de
    # `choose` estan calibradas para eso, asi que es dura. Quien la sustituya por una
    # region semantica -run.py, con la respuesta del modelo- decide si sigue siendolo.
    return {"rgb": rgb, "px_w": im.size[0], "px_h": im.size[1],
            "sal_box": sal_box, "face": face, "faces": caras, "face_hard": True,
            "sal_ii": vision.integral(S), "grid": grid}
