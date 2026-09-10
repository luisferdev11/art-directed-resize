"""El solver de layout. Aqui vive el producto.

LA TESIS. El emplazamiento del texto no se elige de una lista de anclajes: se BUSCA
densamente sobre un campo de costo derivado de los pixeles. Es lo que hace que el
layout se mueva cuando cambia la foto, y esa es la unica prueba que distingue esto
de un template.

Por que no un solver de restricciones de proposito general: el objetivo es no convexo
y derivado de pixeles. "El texto va sobre zona de baja saliencia" no es una restriccion
lineal y no se expresa en Cassowary. CP-SAT obligaria a discretizar, y al discretizar
ya construiste el generador de candidatos. Frente a annealing o CMA-ES: la busqueda
densa sobre imagen integral aproxima eso de forma DETERMINISTA, y el determinismo es
requisito de producto en una herramienta de marca.

DOS HIPOTESIS ESTRUCTURALES:
  bleed  la foto cubre el lienzo
  panel  la foto no cabe sin cortar el sujeto, asi que ocupa un panel lateral a un
         aspecto sano y el resto es campo de marca. Es una decision estructural
         EMERGENTE de una falla de restriccion medida, no una plantilla por formato.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

import brand
import crop as cropmod
import text as T
import vision
from formats import Format
from scene import Scene

Rect = Tuple[float, float, float, float]

STACK_W_FRACTIONS = (0.42, 0.55, 0.68, 0.82, 0.95)
POS_STEPS = 11
THIRDS = (1 / 3, 2 / 3)
GAP = {"subhead": 0.55, "support": 0.75}
# El scrim se dimensiona con margen sobre el contraste exigido. El solver decide
# sobre el fondo que PREDICE -el recorte remuestreado a lienzo- y el emisor entrega
# ese raster recomprimido a JPEG y reescalado por el visor: no son los mismos
# pixeles. Medido, la desviacion llegaba al 4.6% y dejaba un bloque en 4.30 contra
# 4.5 exigido. Un 8% cubre esa deriva sin oscurecer la fotografia de forma visible.
SCRIM_MARGIN = 1.08
ALL_ROLES = ("headline", "subhead", "support")


# ------------------------------------------------------------------ tipografia
def _fit_stack(scene: Scene, width: float, max_h: float,
               pol: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Ajusta la pila preservando la JERARQUIA del master, bajo una politica.

    Solo el titular se maximiza contra el ancho. Los demas DERIVAN su cuerpo del
    ratio que tenian en el master, acotado por abajo al piso de legibilidad.
    Maximizar cada bloque destruye la jerarquia y produce un muro de texto.
    """
    head = scene.by_role("headline")
    if head is None:
        return None
    roles = pol.get("roles", ALL_ROLES)
    lead_2 = pol.get("leading", 1.16)
    hf = T.fit_block(head.text, width, max_h, head.weight, 1.02, max_lines=3,
                     tracking=head.tracking, min_size=brand.MIN_SIZE["headline"])
    if hf is None:
        return None
    out = [{"role": "headline", "fit": hf, "gap": 0.0, "block": head,
            "weight": head.weight}]
    total = hf.height
    notes: List[str] = []

    for role in roles[1:]:
        blk = scene.by_role(role)
        if blk is None:
            continue
        ratio = blk.size / head.size
        want = T.snap_down(hf.size * ratio) or brand.MIN_SIZE[role]
        floor = brand.MIN_SIZE[role]
        if want < floor:
            want = T.snap_up(floor) or floor
        w_eff = blk.weight
        # jerarquia por PESO cuando el piso comprimio el contraste de tamano
        master_contrast = head.size / max(blk.size, 1e-9)
        got_contrast = hf.size / max(want, 1e-9)
        if got_contrast < brand.HIERARCHY_MIN_RATIO * master_contrast:
            if pol.get("light_secondary") and w_eff >= 400:
                w_eff = brand.LIGHT_WEIGHT
                notes.append(
                    f"{role}: el piso de legibilidad redujo el contraste de tamano a "
                    f"{got_contrast:.2f}:1 frente a {master_contrast:.2f}:1 del master, "
                    f"asi que la jerarquia se re-expresa en peso ({blk.weight} a {w_eff})")
            else:
                notes.append(
                    f"{role}: contraste de tamano comprimido a {got_contrast:.2f}:1 "
                    f"frente a {master_contrast:.2f}:1 del master")
        f = T.fit_at_size(blk.text, width, want, w_eff, lead_2, max_lines=4,
                          tracking=blk.tracking)
        if f is None:
            return None
        gap = GAP.get(role, 0.6) * f.size
        if total + gap + f.height > max_h:
            return None
        total += gap + f.height
        out.append({"role": role, "fit": f, "gap": gap, "block": blk, "weight": w_eff})
    return {"items": out, "height": total, "notes": notes}


def _baselines(items: List[Dict[str, Any]], top: float) -> None:
    y = top
    for it in items:
        f = it["fit"]
        y += it["gap"]
        first = y + T.ascent(it["weight"], f.size)
        it["baselines"] = [first + k * f.leading for k in range(f.n_lines)]
        it["top"] = y
        y += f.height


# --------------------------------------------------------------------- color
def _line_rects(x: float, top: float, fit, weight: int) -> List[Rect]:
    """Un rectangulo por LINEA de tinta, medido como lo mide el validador.

    La legibilidad ocurre linea a linea, no por bloque. Un titular de tres lineas
    puede tener dos sobre cielo y la tercera sobre un rotulo rojo, y el percentil
    calculado sobre el rectangulo de las tres juntas se lo traga: en la prueba de
    las fotos, "IS HERE" salio a 1.38:1 contra 3.0 exigido mientras el bloque
    afirmaba cumplir. Lo encontro medir el archivo entregado, no el ojo.
    """
    k = fit.size / T.REF
    _, desc, cap, cap_top = T.metrics_ref(weight)
    h = (cap + desc * 0.4) * k
    out = []
    y = top
    for i, line in enumerate(fit.lines):
        base = y + T.ascent(weight, fit.size) + i * fit.leading
        out.append((x, base - cap * k - cap_top * k,
                    T.advance(line, weight, fit.size, 0.0), h))
    return out


def _pick_color(lum, rgb, rects, size, weight):
    """Color y scrim para un bloque, decididos por su PEOR linea.

    `rects` es la lista de rectangulos de linea. Se elige el color que mejor le va
    a la linea mas comprometida, y el scrim se dimensiona para esa misma linea: es
    la unica forma de que el bloque entero cumpla lo que afirma.
    """
    if not isinstance(rects, list):
        rects = [rects]
    need = vision.required_contrast(size, weight)
    opts = []
    for key in ("ink", "light"):
        hexv = brand.PALETTE[key]
        tl = vision.hex_luminance(hexv)
        opts.append((min(vision.worst_contrast(lum, r, tl) for r in rects), hexv, tl))
    opts.sort(key=lambda o: -o[0])
    got, hexv, tl = opts[0]
    if got >= need:
        return hexv, got, need, None
    scrim_hex = "#000000" if tl > 0.5 else "#FFFFFF"
    alphas = [vision.scrim_alpha(rgb, r, tl, need * SCRIM_MARGIN, scrim_hex)
              for r in rects]
    if any(a is None for a in alphas):
        return hexv, got, need, None
    return hexv, got, need, max(alphas)


def _best_contrast(lum, rect) -> float:
    return max(vision.worst_contrast(lum, rect, vision.hex_luminance(brand.PALETTE[k]))
               for k in ("ink", "light"))


def _apply_scrim(rgb: np.ndarray, rect: Rect, hexv: str, alpha: float) -> None:
    """Compone un scrim sobre el lienzo de trabajo, en sitio."""
    H, W = rgb.shape[:2]
    x0, y0 = max(0, int(rect[0])), max(0, int(rect[1]))
    x1 = min(W, int(np.ceil(rect[0] + rect[2])))
    y1 = min(H, int(np.ceil(rect[1] + rect[3])))
    if x1 <= x0 or y1 <= y0:
        return
    tint = np.array([int(hexv.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], np.float64)
    patch = rgb[y0:y1, x0:x1].astype(np.float64)
    rgb[y0:y1, x0:x1] = (patch * (1 - alpha) + tint * alpha).astype(np.uint8)


def _overlap(a: Rect, b: Rect) -> bool:
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or
                a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


# --------------------------------------------------------------------- panel
def _panel_geometry(fmt: Format, master_cx: float) -> Tuple[Rect, Rect]:
    """(rect del panel de foto, rect del campo de marca).

    El panel va al lado OPUESTO al titular del master, para que el texto conserve
    su lado. Su ancho se acota para que el aspecto del panel sea sano.
    """
    W, H = float(fmt.w), float(fmt.h)
    pw = min(brand.PANEL_MAX_W * W, H * brand.PANEL_TARGET_ASPECT)
    pw = max(pw, min(0.22 * W, H * 1.2))
    if master_cx <= 0.5:                     # titular a la izquierda -> panel derecha
        panel = (W - pw, 0.0, pw, H)
        field = (0.0, 0.0, W - pw, H)
    else:
        panel = (0.0, 0.0, pw, H)
        field = (pw, 0.0, W - pw, H)
    return panel, field


def _compose_backdrop(fmt: Format, rgb: np.ndarray, crect: Rect,
                      panel: Optional[Rect]) -> np.ndarray:
    """El fondo PREDICHO sobre el que se mediran contraste y coste.

    Un solo camino de codigo: con panel, el lienzo es campo de marca con la foto
    compuesta dentro del panel. Asi el campo de costo y el contraste son correctos
    por construccion en las dos hipotesis.
    """
    W, H = int(fmt.w), int(fmt.h)
    x0, y0, cw, ch = (int(round(v)) for v in crect)
    vis = rgb[y0:y0 + ch, x0:x0 + cw]
    if panel is None:
        return cv2.resize(vis, (W, H), interpolation=cv2.INTER_AREA)
    ink = brand.PALETTE["ink"].lstrip("#")
    bg = np.zeros((H, W, 3), dtype=np.uint8)
    bg[:, :] = [int(ink[i:i + 2], 16) for i in (0, 2, 4)]
    px, py, pw, ph = (int(round(v)) for v in panel)
    pw, ph = max(1, min(pw, W - px)), max(1, min(ph, H - py))
    bg[py:py + ph, px:px + pw] = cv2.resize(vis, (pw, ph), interpolation=cv2.INTER_AREA)
    return bg


# --------------------------------------------------------------------- solver
def solve(scene: Scene, fmt: Format, prep: Dict[str, Any]) -> Dict[str, Any]:
    W, H = float(fmt.w), float(fmt.h)
    reasons: List[str] = []
    mh = scene.by_role("headline")
    master_top = (mh.rect[1] / scene.height) if mh else 0.1
    master_cx = ((mh.rect[0] + mh.rect[2] / 2) / scene.width) if mh else 0.5

    # --- 1. hipotesis y recorte ---------------------------------------------
    hard = bool(prep.get("face_hard", True))
    crect, cdiag = cropmod.choose(prep["px_w"], prep["px_h"], fmt.aspect,
                                  prep["sal_ii"], prep["grid"], prep["face"],
                                  face_hard=hard)
    cdiag0 = dict(cdiag)          # el diagnostico del intento A SANGRE, antes del panel
    unsat = bool(cdiag.get("face_unsatisfiable"))
    panel = field = None
    if unsat:
        panel, field = _panel_geometry(fmt, master_cx)
        p_aspect = panel[2] / panel[3]
        crect, cdiag = cropmod.choose(prep["px_w"], prep["px_h"], p_aspect,
                                      prep["sal_ii"], prep["grid"], prep["face"],
                                      face_hard=hard)
        still = bool(cdiag.get("face_unsatisfiable"))
        # La razon se cuenta distinta segun COMO fallo la restriccion, porque son dos
        # fallas distintas y decir la equivocada es peor que no decir nada.
        if hard:
            need_h = (prep["face"][3] / 0.45) if prep["face"] else 0.0
            reasons.append(
                f"a {fmt.aspect:.1f}:1 ningun recorte a sangre contiene la region focal "
                f"por encima de la escala minima de sujeto: haria falta {need_h:.0f}px de "
                f"alto, o {need_h*fmt.aspect:.0f}px de ancho, y la fuente tiene "
                f"{prep['px_w']}px. La foto degrada a panel de "
                f"{panel[2]:.0f}x{panel[3]:.0f} ({p_aspect:.1f}:1) y se promueve el "
                f"campo de marca"
                + ("" if not still else
                   "; el sujeto sigue apretado incluso en el panel"))
        else:
            cov = float(cdiag0.get("soft_cover", 0.0))
            reasons.append(
                f"a {fmt.aspect:.1f}:1 el mejor recorte a sangre conserva solo el "
                f"{cov:.0%} de la region del sujeto, bajo el {cropmod.SOFT_MIN_COVER:.0%} "
                f"exigido: la region es una extension y no una cara, asi que no cabe "
                f"entera. La foto degrada a panel de {panel[2]:.0f}x{panel[3]:.0f} "
                f"({p_aspect:.1f}:1) y se promueve el campo de marca")
    else:
        # "region focal contenida" solo si de verdad lo esta. Con la region blanda el
        # encuadre puede conservar el 80% de un grupo, y decir "contenida" ahi seria
        # exactamente la clase de afirmacion que este manifest existe para no hacer.
        cov = float(cdiag.get("cover", 1.0))
        if cdiag.get("face_soft") and cov < 0.995:
            estado = (f"region del sujeto conservada al {cov:.0%} "
                      f"(es una extension, no una cara: se maximiza, no se exige)")
        else:
            estado = "region focal contenida"
        reasons.append(f"recorte {crect[2]:.0f}x{crect[3]:.0f}px de la fuente "
                       f"({crect[2]/prep['px_w']:.0%} del ancho); {estado}")

    ppi = vision.effective_ppi(prep["px_w"], crect[2] / prep["px_w"],
                               panel[2] if panel else W)
    if ppi < 72.0:
        reasons.append(f"PPI efectivo {ppi:.0f} bajo 72 nominal: "
                       f"suministrar fuente de mayor resolucion")

    # --- 2. fondo predicho, campo de costo ----------------------------------
    canvas_px = _compose_backdrop(fmt, prep["rgb"], crect, panel)
    lum = vision.luminance(canvas_px)
    grid = (64, max(8, int(round(64 / max(fmt.aspect, 1e-6)))))
    cf = vision.cost_field(canvas_px, grid)

    # LA CARA ES ZONA PROHIBIDA TAMBIEN PARA EL TEXTO. Era restriccion dura solo en
    # el recorte, y el campo de costo se apoyaba en saliencia generica: sobre una
    # foto con un objeto muy llamativo -un rotulo rojo enorme- la saliencia se va a
    # ese objeto, la cara queda barata y el titular aterriza en la frente del sujeto.
    # El sistema protegia la cara al encuadrar y la tapaba al escribir. Se marca su
    # region, con margen porque la caja de Haar corta el pelo y la barbilla.
    # SE VEDAN TODAS LAS CARAS, no solo la region focal. Vedar unicamente
    # `prep["face"]` bastaba mientras el sujeto era una persona. Sobre un grupo de
    # once, la region focal es la banda del modelo y el resto de las cabezas quedaban
    # baratas: medido en el MPU de la foto de la piramide, el titular aterrizaba sobre
    # las caras que el veto no cubria. `prep["faces"]` -las caras con acuerdo de las
    # dos cascadas- ya estaba calculado y no se consumia en ningun sitio.
    vedadas: List[Rect] = []
    if prep.get("face"):
        vedadas.append(tuple(prep["face"]))
    for f in (prep.get("faces") or []):
        vedadas.append(tuple(f))

    if vedadas:
        cx0, cy0, cw0, ch0 = crect
        tx, ty, tw, th = panel if panel else (0.0, 0.0, W, H)
        m = 0.25                      # la caja de Haar corta el pelo y la barbilla
        puestas = 0
        primera = None
        for (fx, fy, fw_, fh_) in vedadas:
            px_ = tx + (fx - cx0) * tw / max(cw0, 1e-9)
            py_ = ty + (fy - cy0) * th / max(ch0, 1e-9)
            pw_ = fw_ * tw / max(cw0, 1e-9)
            ph_ = fh_ * th / max(ch0, 1e-9)
            px_, py_ = px_ - pw_ * m, py_ - ph_ * m
            pw_, ph_ = pw_ * (1 + 2 * m), ph_ * (1 + 2 * m)
            a = max(0, int(px_ * grid[0] / W)); b = max(0, int(py_ * grid[1] / H))
            c = min(grid[0], int(np.ceil((px_ + pw_) * grid[0] / W)))
            d = min(grid[1], int(np.ceil((py_ + ph_) * grid[1] / H)))
            if c > a and d > b:
                cf[b:d, a:c] = 1.0
                puestas += 1
                if primera is None:
                    primera = (pw_, ph_, px_, py_)
        if puestas == 1 and primera:
            reasons.append(
                f"region de la cara vedada al texto: {primera[0]:.0f}x{primera[1]:.0f}px "
                f"en ({primera[2]:.0f},{primera[3]:.0f}) del lienzo, con 25% de margen")
        elif puestas > 1:
            reasons.append(
                f"{puestas} regiones de cara vedadas al texto, con 25% de margen cada "
                f"una: cuando hay varias cabezas no basta vedar la region focal")

    ii = vision.integral(cf)
    gx, gy = grid[0] / W, grid[1] / H

    def cost_of(r: Rect) -> float:
        a, b = max(0, int(r[0] * gx)), max(0, int(r[1] * gy))
        c = min(grid[0], max(a + 1, int(np.ceil((r[0] + r[2]) * gx))))
        d = min(grid[1], max(b + 1, int(np.ceil((r[1] + r[3]) * gy))))
        return vision.rect_mean(ii, a, b, c, d)

    # Area util para el texto. Con panel es la INTERSECCION del campo de marca con
    # el area segura de la plataforma: aplicar un margen propio al campo se saltaba
    # los insets declarados del formato (10% arriba y abajo en el leaderboard), y
    # el validador lo detecto.
    sx, sy, sw, sh = fmt.safe_box()
    if field:
        m = min(fmt.w, fmt.h) * brand.SAFE_FRACTION
        x0 = max(sx, field[0] + m)
        y0 = max(sy, field[1] + m)
        x1 = min(sx + sw, field[0] + field[2] - m)
        y1 = min(sy + sh, field[1] + field[3] - m)
        sx, sy, sw, sh = x0, y0, max(x1 - x0, 1.0), max(y1 - y0, 1.0)

    # Banda reservada para el legal. Sin esto, la pila ocupa todo el alto y el legal
    # aterriza encima (el validador lo detecto en el leaderboard: 69.7 de 72px de
    # pila, mas el legal anclado al fondo de la MISMA caja).
    # Se reserva un limite inferior basado en su piso de legibilidad; el cuerpo real
    # se resuelve despues por ratio, acotado a la banda. Si la escalera retira el
    # legal, la reserva se libera y la pila gana ese espacio.
    legal_blk = scene.by_role("legal")
    legal_reserve = (brand.MIN_SIZE["legal"] * 1.9) if legal_blk else 0.0

    # --- 3. escalera de degradacion -----------------------------------------
    best: Optional[Dict[str, Any]] = None
    fired: List[str] = []
    stack_notes: List[str] = []
    keep_legal = True
    for step, pol in brand.DEGRADE_LADDER:
        cand = None
        reserve = legal_reserve if pol.get("legal", True) else 0.0
        stack_h = sh - reserve
        if stack_h <= 0:
            continue
        for wf in STACK_W_FRACTIONS:
            st = _fit_stack(scene, sw * wf, stack_h, pol)
            if st is None:
                continue
            bw = max(i["fit"].width for i in st["items"])
            bh = st["height"]
            for iy in range(POS_STEPS):
                for ix in range(POS_STEPS):
                    px = sx + (sw - bw) * ix / (POS_STEPS - 1)
                    py = sy + (stack_h - bh) * iy / (POS_STEPS - 1)
                    rect = (px, py, bw, bh)
                    c = cost_of(rect)
                    ratio = 1e9
                    yy = py
                    for it in st["items"]:
                        yy += it["gap"]
                        nd = vision.required_contrast(it["fit"].size, it["weight"])
                        ratio = min(ratio, _best_contrast(
                            lum, (px, yy, bw, it["fit"].height)) / nd)
                        yy += it["fit"].height
                    legib = min(ratio, 1.8) / 1.8
                    hsz = st["items"][0]["fit"].size / min(W, H)
                    fx = (px + bw / 2) / W
                    asym = min(abs(fx - THIRDS[0]), abs(fx - THIRDS[1]))
                    score = (-2.6 * c) + (1.5 * hsz) - (0.5 * asym) \
                            - (0.45 * abs((py / H) - master_top)) \
                            - (0.30 * abs(fx - master_cx)) \
                            + (0.95 * legib) - (0.55 * (1.0 if ratio < 1.0 else 0.0))
                    if cand is None or score > cand["score"]:
                        cand = {"score": score, "rect": rect, "stack": st, "cost": c}
        if cand is None:
            continue
        # el legal se intenta aparte; si la politica lo excluye, no entra
        keep_legal = pol.get("legal", True)
        best, stack_notes = cand, cand["stack"]["notes"]
        fired = [n for n, _ in brand.DEGRADE_LADDER[:
                 [k for k, _ in brand.DEGRADE_LADDER].index(step) + 1]][1:]
        break

    if best is None:
        return {"format": fmt, "failed": True,
                "reasons": reasons + ["ninguna politica de la escalera produce un "
                                      "layout valido en el area segura"]}

    st = best["stack"]
    px, py, bw, bh = best["rect"]
    _baselines(st["items"], py)
    placed = [i["role"] for i in st["items"]]
    dropped = [r for r in ALL_ROLES if scene.by_role(r) and r not in placed]
    reasons.extend(stack_notes)
    if fired:
        reasons.append("escalera de degradacion aplicada: " + " -> ".join(fired))
    for r in dropped:
        reasons.append(f"{r} retirado: no cabe por encima de su piso de legibilidad "
                       f"sin comprimir la jerarquia")
    reasons.append(f"texto emplazado en ({px:.0f},{py:.0f}) por busqueda densa sobre el "
                   f"campo de costo: coste {best['cost']:.3f} en escala 0-1")

    # --- 4. color y scrim ----------------------------------------------------
    blocks, scrims = [], []
    # Lienzo de TRABAJO: cada scrim que se decide se compone aqui, para que el
    # bloque siguiente mida el fondo que de verdad va a heredar. Sin esto, el
    # titular pedia scrim blanco y el subtitulo negro, cada uno contra el fondo
    # limpio, y en el archivo se anulaban: el subtitulo salia a 2.52:1 contra 3.0.
    work = canvas_px.copy()
    lum_w = lum
    for it in st["items"]:
        f, blk = it["fit"], it["block"]
        r = (px, it["top"], f.width, f.height)
        lines_r = _line_rects(px, it["top"], f, it["weight"])
        got_after = None
        fill, got, need, alpha = _pick_color(lum_w, work, lines_r, f.size,
                                             it["weight"])
        if alpha:
            pad = f.size * 0.35
            srect = (r[0] - pad, r[1] - pad, r[2] + 2 * pad, r[3] + 2 * pad)
            shex = "#000000" if fill == brand.PALETTE["light"] else "#FFFFFF"
            scrims.append({"for": blk.role, "alpha": alpha, "fill": shex,
                           "rect": srect})
            _apply_scrim(work, srect, shex, alpha)
            lum_w = vision.luminance(work)
            # Se RE-MIDE sobre el lienzo ya compuesto. Antes se escribia el objetivo
            # en la casilla del resultado: el manifest afirmaba haber alcanzado el
            # contraste exigido sin haberlo comprobado nunca.
            got_after = min(vision.worst_contrast(
                lum_w, r2, vision.hex_luminance(fill)) for r2 in lines_r)
            reasons.append(f"{blk.role}: contraste medido {got:.2f}:1 contra {need:.1f} "
                           f"exigido, scrim con alpha {alpha:.2f}")
        elif fill == brand.PALETTE["light"]:
            reasons.append(f"{blk.role}: tipografia invertida a claro, contraste {got:.2f}:1")
        blocks.append({"role": blk.role, "x": px, "size": f.size, "weight": it["weight"],
                       "fill": fill, "tracking": blk.tracking, "lines": f.lines,
                       "baselines": it["baselines"], "rect": r, "contrast": got,
                       "required": need, "scrimmed": alpha is not None,
                       "achieved": got_after if alpha is not None else got})

    # --- 5. legal ------------------------------------------------------------
    # Va en su banda reservada al pie del area util. El orden importa: primero se
    # decide si CABE y si no colisiona, y solo entonces se compromete scrim y bloque.
    # Al reves quedaba un scrim huerfano sobre un legal retirado.
    legal = scene.by_role("legal")
    if legal and not keep_legal:
        reasons.append("legal retirado por la escalera de degradacion")
        dropped.append("legal")
    elif legal:
        want = T.snap_down(st["items"][0]["fit"].size * (legal.size / mh.size)) if mh else None
        want = max(want or brand.MIN_SIZE["legal"], brand.MIN_SIZE["legal"])
        f = T.fit_at_size(legal.text, sw * 0.92, want, legal.weight, 1.18, max_lines=3)
        why = None
        r = None
        if f is None:
            why = "no cabe a lo ancho por encima de su piso de legibilidad"
        else:
            r = (sx, sy + sh - f.height, f.width, f.height)
            if f.height > legal_reserve * 1.6:
                why = (f"necesita {f.height:.0f}px y la banda reservada es "
                       f"{legal_reserve:.0f}px")
            elif any(_overlap(r, b["rect"]) for b in blocks):
                why = "colisionaba con la pila de texto"
        if why:
            reasons.append(f"legal retirado: {why}")
            dropped.append("legal")
        else:
            got_after = None
            fill, got, need, alpha = _pick_color(
                lum_w, work, _line_rects(sx, r[1], f, legal.weight),
                f.size, legal.weight)
            if alpha:
                pad = f.size * 0.5
                srect = (r[0] - pad, r[1] - pad, r[2] + 2 * pad, r[3] + 2 * pad)
                shex = "#000000" if fill == brand.PALETTE["light"] else "#FFFFFF"
                scrims.append({"for": "legal", "alpha": alpha, "fill": shex,
                               "rect": srect})
                _apply_scrim(work, srect, shex, alpha)
                lg_lines = _line_rects(sx, r[1], f, legal.weight)
                got_after = min(vision.worst_contrast(
                    vision.luminance(work), r2, vision.hex_luminance(fill))
                    for r2 in lg_lines)
                reasons.append(f"legal: contraste medido {got:.2f}:1 contra {need:.1f} "
                               f"exigido, scrim con alpha {alpha:.2f}")
            bl = [r[1] + T.ascent(legal.weight, f.size) + k * f.leading
                  for k in range(f.n_lines)]
            blocks.append({"role": "legal", "x": sx, "size": f.size,
                           "weight": legal.weight, "fill": fill, "tracking": 0.0,
                           "lines": f.lines, "baselines": bl, "rect": r,
                           "contrast": got, "required": need,
                           "scrimmed": alpha is not None,
                           "achieved": got_after if alpha is not None else got})

    # --- 6. lockup -----------------------------------------------------------
    lock = None
    if scene.lockup:
        lk = scene.lockup
        lx0, ly0, lw0, lh0 = lk.rect
        avail = sw * 0.34
        k = max(brand.LOGO_MIN_PX / lw0, min(W, H) * 0.16 / lw0)
        k = min(k, avail / lw0)
        mark_only = False
        # Un minimo de ancho del lockup no garantiza que su wordmark se lea. Primero
        # se intenta SUBIR la escala para salvarlo; si no cabe, el lockup degrada a
        # marca sola, que es lo que hace un sistema de marca real a tamano reducido.
        if lk.wordmark_size and lk.wordmark_size * k < brand.LOGO_WORDMARK_MIN:
            k_need = brand.LOGO_WORDMARK_MIN / lk.wordmark_size
            if k_need * lw0 <= avail:
                reasons.append(
                    f"lockup escalado a {k_need:.2f}x en lugar de {k:.2f}x: a la escala "
                    f"anterior el wordmark caia a {lk.wordmark_size*k:.1f}px, bajo su "
                    f"piso de {brand.LOGO_WORDMARK_MIN:g}px")
                k = k_need
            elif lk.mark_rect:
                mark_only = True
                mw = lk.mark_rect[2]
                # 0.22 del lado corto daba una marca de 55px en un 300x250: el 18%
                # del ancho, estampada sobre el sujeto. Una marca real en un banner
                # de ese tamano ronda el 8-10% del lado corto.
                k = min(max(brand.LOGO_MARK_MIN_PX / mw, min(W, H) * 0.10 / mw),
                        avail / mw)
                lx0, ly0, lw0, lh0 = lk.mark_rect
                reasons.append(
                    f"lockup degradado a marca sola: el wordmark habria quedado a "
                    f"{lk.wordmark_size*brand.LOGO_MIN_PX/lk.rect[2]:.1f}px y no hay "
                    f"ancho para subir la escala. La marca va a {mw*k:.0f}px")
        nw, nh = lw0 * k, lh0 * k
        clear = nh * brand.LOGO_CLEAR
        cands = []
        for cx_, cy_ in ((sx + sw - nw, sy), (sx, sy),
                         (sx + sw - nw, sy + sh - nh), (sx, sy + sh - nh)):
            r = (cx_ - clear, cy_ - clear, nw + 2 * clear, nh + 2 * clear)
            ov = any(_overlap((cx_, cy_, nw, nh), b["rect"]) for b in blocks)
            cands.append((cost_of(r) + (9.0 if ov else 0.0), cx_, cy_))
        cands.sort()
        _, cx_, cy_ = cands[0]
        # Variante clara u oscura del logo, decidida por el fondo real. El lockup
        # conservaba el color de tinta del master, y sobre el campo de marca
        # (tambien tinta) quedaba invisible. Un sistema de marca tiene las dos.
        lrect = (cx_, cy_, nw, nh)
        ink_l = vision.hex_luminance(brand.PALETTE["ink"])
        invert = (vision.worst_contrast(lum, lrect, ink_l) < 2.5)
        if invert:
            reasons.append("logo en variante clara: sobre este fondo la tinta daba "
                           f"{vision.worst_contrast(lum, lrect, ink_l):.2f}:1")
        lock = {"xform": f"translate({cx_-lx0*k:.2f},{cy_-ly0*k:.2f}) scale({k:.4f})",
                "rect": lrect, "scale": k, "mark_only": mark_only, "invert": invert}
        reasons.append(f"lockup a escala uniforme {k:.2f}x, {nw:.0f}px de ancho, "
                       f"clear-space {clear:.0f}px, esquina de menor coste")

    return {"format": fmt, "failed": False, "crop_px": crect, "crop_diag": cdiag,
            "ppi": ppi, "blocks": blocks, "scrims": scrims, "lockup": lock,
            "panel": panel, "field": field, "dropped": dropped, "ladder": fired,
            "reasons": reasons, "hypothesis": "panel" if panel else "bleed",
            "cost": best["cost"]}
