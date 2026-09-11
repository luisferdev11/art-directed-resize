"""Segundo backend de layout: resize por TEMPLATE + CONSTRAINTS.

Es el mecanismo del competidor, implementado FIELMENTE contra el mismo `Scene`.
No es una parodia: si la comparacion se ve amanada, el argumento se invierte.

Que hace un resize por constraints, y que no:
  · cada elemento lleva un constraint horizontal y otro vertical, tal como los
    define Figma. Al cambiar el lienzo, el elemento se reposiciona segun su regla.
  · el cuerpo tipografico NO cambia salvo que el constraint sea SCALE. El texto
    refluye al ancho de su caja, y ya.
  · la fotografia se escala para llenar el marco y se recorta al centro.

Y lo que NO hace, que es el punto entero: **no mira la fotografia**. No sabe donde
esta el sujeto, no mide contraste contra el fondo nuevo, no decide que un aspecto
de 8:1 no admite esa foto a sangre. Un constraint es una regla geometrica sobre
una caja, y una caja no tiene opinion sobre lo que hay debajo.

REGLAS DE JUSTICIA (plan-demo.md §6, demo-alcance.md §2), todas verificables aqui:
  1. Los constraints son los que un disenador competente pondria, y son los que el
     propio brief nombra: titular LEFT+TOP, logo RIGHT+TOP, legal LEFT+BOTTOM,
     foto SCALE. No son los peores posibles.
  2. Los constraints usados salen impresos en el artefacto, para que se auditen.
  3. Se emiten TODOS los formatos, incluidos aquellos donde este mecanismo gana. En
     4:5 y en 1:1 el template coincide con el objetivo y el resultado es correcto.
  4. La plantilla portrait ES el master. No se degrada a proposito: se autorea desde
     la pieza que el disenador ya hizo, que es exactamente el flujo del competidor.
  5. El resultado se mide con la MISMA instrumentacion que el nuestro (contraste
     WCAG por percentiles, campo de costo derivado de pixeles), y se reporta tal
     cual. Las violaciones se nombran; no se corrigen, porque corregirlas seria
     dejar de implementar su mecanismo.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

import brand
import text as T
import vision
from formats import BY_KEY, Format
from scene import Scene

Rect = Tuple[float, float, float, float]

# Constraints tal como los nombra Figma.
LEFT, RIGHT, LEFT_RIGHT, CENTER, SCALE = "LEFT", "RIGHT", "LEFT_RIGHT", "CENTER", "SCALE"
TOP, BOTTOM, TOP_BOTTOM = "TOP", "BOTTOM", "TOP_BOTTOM"

INK = brand.PALETTE["ink"]
LIGHT = brand.PALETTE["light"]
LEADING = 1.16          # line-height del estilo de texto, autoreado en el template
TOL = 1.5               # misma holgura que check.py: una brecha de 1px no es un hallazgo


# --------------------------------------------------------------- las plantillas
# TRES plantillas, la familia de aspecto que el competidor usa. La portrait es el
# master tal cual (1080x1350, las cifras salen de parsearlo); landscape y square
# son las adaptaciones a mano que un disenador hace una vez, y que despues el
# sistema reutiliza para todo. Ese "una vez, a mano" es la queja del cliente:
# "requires a base Master example to be created first".
TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "portrait", "canvas": (1080.0, 1350.0), "native": "portrait_4x5",
        "photo": {"rect": (0.0, 0.0, 1080.0, 1350.0), "h": SCALE, "v": SCALE},
        "text": [
            {"role": "headline", "rect": (64.0, 96.5, 672.0, 221.0), "h": LEFT, "v": TOP,
             "size": 92.0, "weight": 900, "fill": INK, "tracking": 0.0},
            {"role": "subhead", "rect": (64.0, 299.5, 480.0, 36.0), "h": LEFT, "v": TOP,
             "size": 30.0, "weight": 400, "fill": INK, "tracking": 0.0},
            {"role": "support", "rect": (64.0, 342.6, 320.0, 24.0), "h": LEFT, "v": TOP,
             "size": 20.0, "weight": 900, "fill": INK, "tracking": 1.6},
            {"role": "legal", "rect": (64.0, 1287.5, 560.0, 16.0), "h": LEFT, "v": BOTTOM,
             "size": 13.0, "weight": 400, "fill": LIGHT, "tracking": 0.0},
        ],
        "scrims": [
            {"rect": (0.0, 1262.0, 1080.0, 88.0), "h": LEFT_RIGHT, "v": BOTTOM,
             "fill": "#000000", "alpha": 0.35, "for": "legal"},
        ],
        "logo": {"rect": (793.5, 96.0, 222.5, 34.0), "h": RIGHT, "v": TOP},
    },
    {
        "name": "landscape", "canvas": (1920.0, 1080.0), "native": "screen_hd",
        "photo": {"rect": (0.0, 0.0, 1920.0, 1080.0), "h": SCALE, "v": SCALE},
        "text": [
            {"role": "headline", "rect": (96.0, 120.0, 900.0, 300.0), "h": LEFT, "v": TOP,
             "size": 104.0, "weight": 900, "fill": LIGHT, "tracking": 0.0},
            {"role": "subhead", "rect": (96.0, 452.0, 660.0, 44.0), "h": LEFT, "v": TOP,
             "size": 32.0, "weight": 400, "fill": LIGHT, "tracking": 0.0},
            {"role": "support", "rect": (96.0, 512.0, 420.0, 28.0), "h": LEFT, "v": TOP,
             "size": 24.0, "weight": 900, "fill": LIGHT, "tracking": 1.9},
            {"role": "legal", "rect": (96.0, 1002.0, 760.0, 18.0), "h": LEFT, "v": BOTTOM,
             "size": 14.0, "weight": 400, "fill": LIGHT, "tracking": 0.0},
        ],
        "scrims": [
            {"rect": (0.0, 0.0, 1120.0, 600.0), "h": LEFT, "v": TOP,
             "fill": "#000000", "alpha": 0.42, "for": "stack"},
            {"rect": (0.0, 976.0, 1920.0, 104.0), "h": LEFT_RIGHT, "v": BOTTOM,
             "fill": "#000000", "alpha": 0.35, "for": "legal"},
        ],
        "logo": {"rect": (1617.5, 96.0, 222.5, 34.0), "h": RIGHT, "v": TOP},
    },
    {
        "name": "square", "canvas": (1080.0, 1080.0), "native": "feed_1x1",
        "photo": {"rect": (0.0, 0.0, 1080.0, 1080.0), "h": SCALE, "v": SCALE},
        "text": [
            {"role": "headline", "rect": (64.0, 88.0, 640.0, 240.0), "h": LEFT, "v": TOP,
             "size": 88.0, "weight": 900, "fill": LIGHT, "tracking": 0.0},
            {"role": "subhead", "rect": (64.0, 350.0, 480.0, 36.0), "h": LEFT, "v": TOP,
             "size": 30.0, "weight": 400, "fill": LIGHT, "tracking": 0.0},
            {"role": "support", "rect": (64.0, 396.0, 320.0, 24.0), "h": LEFT, "v": TOP,
             "size": 20.0, "weight": 900, "fill": LIGHT, "tracking": 1.6},
            {"role": "legal", "rect": (64.0, 1017.5, 560.0, 16.0), "h": LEFT, "v": BOTTOM,
             "size": 13.0, "weight": 400, "fill": LIGHT, "tracking": 0.0},
        ],
        "scrims": [
            {"rect": (0.0, 0.0, 790.0, 470.0), "h": LEFT, "v": TOP,
             "fill": "#000000", "alpha": 0.42, "for": "stack"},
            {"rect": (0.0, 992.0, 1080.0, 88.0), "h": LEFT_RIGHT, "v": BOTTOM,
             "fill": "#000000", "alpha": 0.35, "for": "legal"},
        ],
        "logo": {"rect": (793.5, 88.0, 222.5, 34.0), "h": RIGHT, "v": TOP},
    },
]

BY_NAME = {t["name"]: t for t in TEMPLATES}


def constraint_table(tpl: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(elemento, constraint horizontal, constraint vertical). Para imprimirlo en
    el artefacto: la regla de justicia 2 exige que se puedan auditar."""
    rows = [("fotografia", tpl["photo"]["h"], tpl["photo"]["v"])]
    rows += [(e["role"], e["h"], e["v"]) for e in tpl["text"]]
    for sc in tpl.get("scrims", []):
        rows.append((f"scrim de {sc['for']}", sc["h"], sc["v"]))
    rows.append(("lockup", tpl["logo"]["h"], tpl["logo"]["v"]))
    return rows


# ------------------------------------------------------------ seleccion y resize
def pick_template(fmt: Format) -> Tuple[Dict[str, Any], str]:
    """El template mas cercano POR TAMANO, que es su regla declarada.

    La distancia es logaritmica en las dos dimensiones. En pixeles crudos, un
    lienzo grande dominaria la suma y todo formato pequeno caeria en el mismo
    template por el motivo equivocado; en log, 728 esta tan lejos de 1080 como
    1080 de 1602. Es la lectura mas favorable de "por proximidad de tamano".
    """
    W, H = float(fmt.w), float(fmt.h)
    scored = []
    for t in TEMPLATES:
        tw, th = t["canvas"]
        d = abs(np.log(W / tw)) + abs(np.log(H / th))
        scored.append((float(d), t))
    scored.sort(key=lambda s: s[0])
    d, tpl = scored[0]
    tw, th = tpl["canvas"]
    why = (f"template '{tpl['name']}' ({tw:.0f}x{th:.0f}) chosen by size proximity: "
           f"tamano: distancia {d:.2f} frente a "
           + ", ".join(f"{t['name']} {dd:.2f}" for dd, t in scored[1:]) + ".")
    if d < 1e-9:
        why += " The target matches the template: this is its best case."
    return tpl, why


def _apply(off: float, ext: float, span0: float, span1: float, mode: str
           ) -> Tuple[float, float]:
    """Un eje, un constraint. Identico en horizontal y en vertical."""
    if mode in (LEFT, TOP):
        return off, ext
    if mode in (RIGHT, BOTTOM):
        return span1 - (span0 - off - ext) - ext, ext
    if mode in (LEFT_RIGHT, TOP_BOTTOM):
        return off, span1 - (span0 - off - ext) - off
    if mode == CENTER:
        return (off + ext / 2.0) / span0 * span1 - ext / 2.0, ext
    if mode == SCALE:
        k = span1 / span0
        return off * k, ext * k
    raise ValueError(f"constraint desconocido: {mode}")


def resize_rect(rect: Rect, canvas0: Tuple[float, float],
                canvas1: Tuple[float, float], h: str, v: str) -> Rect:
    x, y, w, hh = rect
    nx, nw = _apply(x, w, canvas0[0], canvas1[0], h)
    ny, nh = _apply(y, hh, canvas0[1], canvas1[1], v)
    return (nx, ny, nw, nh)


# ------------------------------------------------------------------- tipografia
def _wrap(words: List[str], weight: int, size: float, box_w: float,
          tracking: float) -> List[str]:
    """Reflujo greedy al ancho de la caja. Una palabra mas ancha que la caja
    desborda, que es lo que hace un motor de texto: no encoge por su cuenta."""
    lines: List[str] = []
    cur: List[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and T.advance(trial, weight, size, tracking) > box_w:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _lay_text(el: Dict[str, Any], rect: Rect) -> Dict[str, Any]:
    """Texto a cuerpo FIJO refluido al ancho de la caja. El cuerpo no cambia: el
    constraint del elemento no es SCALE, y eso es fiel al mecanismo."""
    size, weight, tr = el["size"], el["weight"], el.get("tracking", 0.0)
    words = el["_text"].split()
    fit = T.fit_at_size(el["_text"], rect[2], size, weight, LEADING,
                        max_lines=6, tracking=tr)
    if fit is not None:
        lines, ink_w = fit.lines, fit.width
    else:
        lines = _wrap(words, weight, size, rect[2], tr)
        ink_w = max((T.advance(s, weight, size, tr) for s in lines), default=0.0)
    lead = size * LEADING
    cap = T.metrics_ref(weight)[2] * size / T.REF
    height = (len(lines) - 1) * lead + cap + size * 0.22
    baselines = [rect[1] + T.ascent(weight, size) + k * lead for k in range(len(lines))]
    return {"lines": lines, "baselines": baselines, "width": ink_w,
            "height": height, "leading": lead}


def _breaches_natively(tpl: Dict[str, Any], el: Dict[str, Any], edge: str) -> bool:
    """?El elemento ya invadia el area segura EN EL LIENZO DEL PROPIO TEMPLATE?

    Importa para no cargarle al mecanismo un defecto que viene del autorado. El
    legal del master queda a 47px del borde inferior y el 4:5 declara 59: eso ya
    esta mal en el master, y nuestro motor lo corrige, pero no es culpa del resize.
    Lo que SI es del resize es arrastrar ese mismo margen a un 9:16, donde el inset
    declarado es 216px porque la UI de la plataforma tapa el 20% inferior.
    """
    nat = BY_KEY.get(tpl.get("native", ""))
    if nat is None:
        return False
    nx, ny, nw, nh = nat.safe_box()
    fit = _lay_text(el, el["rect"])
    r = (el["rect"][0], el["rect"][1], fit["width"], fit["height"])
    return {"left": r[0] - nx, "top": r[1] - ny,
            "right": (nx + nw) - (r[0] + r[2]),
            "bottom": (ny + nh) - (r[1] + r[3])}[edge] < -TOL


# ------------------------------------------------------------------ el backend
def solve(scene: Scene, fmt: Format, prep: Dict[str, Any]) -> Dict[str, Any]:
    """Misma firma y misma forma de retorno que `solve.solve()`, contra el mismo
    `Scene`. Ese es el argumento estructural: son dos backends de layout, no dos
    proyectos, y el seam que lo permite es `scene.py`."""
    W, H = float(fmt.w), float(fmt.h)
    tpl, why = pick_template(fmt)
    c0 = tpl["canvas"]
    reasons: List[str] = [why]
    violations: List[str] = []
    inherited: List[str] = []   # defectos del master, no del mecanismo

    # --- 1. la fotografia: SCALE, o sea llenar el marco y recortar al centro ---
    src_w, src_h = float(prep["px_w"]), float(prep["px_h"])
    if src_w / src_h > W / H:
        cw, ch = src_h * (W / H), src_h
    else:
        cw, ch = src_w, src_w / (W / H)
    crect = ((src_w - cw) / 2.0, (src_h - ch) / 2.0, cw, ch)
    reasons.append(
        f"photo: CENTRE crop of {cw:.0f}x{ch:.0f}px to fill the frame. "
        f"The constraint does not know where the subject is: it crops by geometry")
    ppi = vision.effective_ppi(src_w, cw / src_w, W)
    if ppi < 72.0:
        reasons.append(f"PPI efectivo {ppi:.0f} bajo 72 nominal")

    # --- 2. el fondo real, para MEDIR lo que el mecanismo produjo -------------
    x0, y0, cwi, chi = (int(round(v)) for v in crect)
    vis = prep["rgb"][y0:y0 + chi, x0:x0 + cwi]
    canvas_px = cv2.resize(vis, (int(W), int(H)), interpolation=cv2.INTER_AREA)

    # el scrim autoreado va compuesto ANTES de medir: el disenador lo puso, y
    # medir sin el seria cargarle al mecanismo un contraste que si tiene.
    scrims: List[Dict[str, Any]] = []
    for sc in tpl.get("scrims", []):
        sr = resize_rect(sc["rect"], c0, (W, H), sc["h"], sc["v"])
        scrims.append({"for": sc["for"], "alpha": sc["alpha"], "fill": sc["fill"],
                       "rect": sr})
        a, b, c, d = (int(round(v)) for v in
                      (max(sr[0], 0), max(sr[1], 0),
                       min(sr[0] + sr[2], W), min(sr[1] + sr[3], H)))
        if c > a and d > b:
            patch = canvas_px[b:d, a:c].astype(np.float64)
            tint = np.array([int(sc["fill"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)],
                            dtype=np.float64)
            canvas_px[b:d, a:c] = (patch * (1 - sc["alpha"])
                                   + tint * sc["alpha"]).astype(np.uint8)

    lum = vision.luminance(canvas_px)
    grid = (64, max(8, int(round(64 / max(fmt.aspect, 1e-6)))))
    ii = vision.integral(vision.cost_field(canvas_px, grid))
    gx, gy = grid[0] / W, grid[1] / H

    def cost_of(r: Rect) -> float:
        a = max(0, int(r[0] * gx)); b = max(0, int(r[1] * gy))
        c = min(grid[0], max(a + 1, int(np.ceil((r[0] + r[2]) * gx))))
        d = min(grid[1], max(b + 1, int(np.ceil((r[1] + r[3]) * gy))))
        return vision.rect_mean(ii, a, b, c, d)

    # --- 3. cada bloque, por su constraint -----------------------------------
    sbx, sby, sbw, sbh = fmt.safe_box()
    blocks: List[Dict[str, Any]] = []
    for el in tpl["text"]:
        blk = scene.by_role(el["role"])
        if blk is None:
            continue
        el = dict(el, _text=blk.text)
        r = resize_rect(el["rect"], c0, (W, H), el["h"], el["v"])
        lay = _lay_text(el, r)
        ink = (r[0], r[1], lay["width"], lay["height"])
        need = vision.required_contrast(el["size"], el["weight"])
        inside = (ink[0] >= -TOL and ink[1] >= -TOL
                  and ink[0] + ink[2] <= W + TOL and ink[1] + ink[3] <= H + TOL)
        # Medir contraste de un bloque que ya esta fuera del lienzo devuelve 0.00 y
        # no significa nada. Se mide lo que se ve; lo demas ya tiene su violacion.
        got = (vision.worst_contrast(lum, ink, vision.hex_luminance(el["fill"]))
               if inside else float("nan"))
        blocks.append({"role": el["role"], "x": r[0], "size": el["size"],
                       "weight": el["weight"], "fill": el["fill"],
                       "tracking": el.get("tracking", 0.0), "lines": lay["lines"],
                       "baselines": lay["baselines"], "rect": ink,
                       "contrast": got if inside else 0.0, "required": need,
                       "scrimmed": False, "achieved": got if inside else 0.0,
                       "measurable": inside})
        if el["size"] < brand.MIN_SIZE.get(el["role"], 0.0) - 1e-9:
            violations.append(f"{el['role']}: {el['size']:g}px, under its floor of "
                              f"legibilidad de {brand.MIN_SIZE[el['role']]:g}px")
        if not inside:
            violations.append(
                f"{el['role']}: it falls outside the canvas. The box landed at "
                f"({ink[0]:.0f},{ink[1]:.0f}) {ink[2]:.0f}x{ink[3]:.0f} sobre "
                f"{W:.0f}x{H:.0f}. The constraint repositions; it does not refit the body size")
        # Area segura del formato. Un constraint de offset fijo conserva el margen
        # que tenia en el template y NUNCA lo confronta con los insets declarados
        # del objetivo. En 9:16 eso mete el legal bajo la UI de la plataforma.
        else:
            m = {"left": ink[0] - sbx, "top": ink[1] - sby,
                 "right": (sbx + sbw) - (ink[0] + ink[2]),
                 "bottom": (sby + sbh) - (ink[1] + ink[3])}
            worst = min(m, key=m.get)
            if m[worst] < -TOL:
                inset = {"left": sbx, "top": sby,
                         "right": W - sbx - sbw, "bottom": H - sby - sbh}[worst]
                have = inset + m[worst]
                txt = (f"{el['role']}: it invades the safe area by {worst}. It sits "
                       f"{have:.0f}px from the edge and the format declares {inset:.0f}px")
                if _breaches_natively(tpl, el, worst):
                    inherited.append(txt + ". It already happened on the template's own "
                                     "template: viene del autorado del master, no del resize")
                else:
                    violations.append(txt + ". The margin is inherited from the template and is not "
                                      "vuelve a comprobar contra los insets del objetivo")
        if inside and got < need - 1e-9:
            violations.append(
                f"{el['role']}: contraste medido {got:.2f}:1 contra {need:.1f} exigido. "
                f"The colour is authored into the template and is not re-measured against the "
                f"fotografia nueva")

    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            a, b = blocks[i]["rect"], blocks[j]["rect"]
            if not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]
                    or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]):
                violations.append(f"{blocks[i]['role']} y {blocks[j]['role']} se solapan")

    # --- 4. el lockup: escala uniforme por su constraint ---------------------
    lock = None
    if scene.lockup:
        lg = tpl["logo"]
        lr = resize_rect(lg["rect"], c0, (W, H), lg["h"], lg["v"])
        lx0, ly0, lw0, _ = scene.lockup.rect
        k = lr[2] / lw0
        lock = {"xform": f"translate({lr[0]-lx0*k:.2f},{lr[1]-ly0*k:.2f}) scale({k:.4f})",
                "rect": lr, "scale": k, "mark_only": False, "invert": False}
        reasons.append(f"lockup by constraint {lg['h']}+{lg['v']}: {lr[2]:.0f}px "
                       f"wide at ({lr[0]:.0f},{lr[1]:.0f})")
        if lr[0] < -0.5 or lr[0] + lr[2] > W + 0.5 or lr[1] + lr[3] > H + 0.5:
            violations.append(f"lockup: it falls outside the canvas at {lr[2]:.0f}px wide "
                              f"against {W:.0f}px. RIGHT+TOP does not rescale")
        wm = scene.lockup.wordmark_size * k
        if scene.lockup.wordmark_size and wm < brand.LOGO_WORDMARK_MIN:
            violations.append(f"lockup: the wordmark lands at {wm:.1f}px, under its floor of "
                              f"{brand.LOGO_WORDMARK_MIN:g}px. There is no degradation to mark-only")

    stack = [b["rect"] for b in blocks]
    if stack:
        sx = min(r[0] for r in stack); sy = min(r[1] for r in stack)
        bb = (sx, sy, max(r[0] + r[2] for r in stack) - sx,
              max(r[1] + r[3] for r in stack) - sy)
        cost = cost_of((max(bb[0], 0.0), max(bb[1], 0.0),
                        min(bb[2], W), min(bb[3], H)))
    else:
        cost = 0.0
    reasons.append(f"placement cost over the SAME cost field: "
                   f"{cost:.3f} on a 0-1 scale. It was not searched for: it is where the box landed")
    for v in violations:
        reasons.append("violation -> " + v)
    for v in inherited:
        reasons.append("inherited from the master -> " + v)

    return {"format": fmt, "failed": False, "crop_px": crect, "crop_diag": {},
            "ppi": ppi, "blocks": blocks, "scrims": scrims, "lockup": lock,
            "panel": None, "field": None, "dropped": [], "ladder": [],
            "reasons": reasons, "hypothesis": "template:" + tpl["name"],
            "cost": cost, "template": tpl["name"], "violations": violations,
            "inherited": inherited,
            "constraints": [list(r) for r in constraint_table(tpl)]}
