"""Adaptador de entrada: IMAGEN PLANA -> Scene, con un modelo multimodal.

EL CRITERIO QUE DECIDE. Sobre un master aplanado a JPEG el parser de SVG extrae 0
elementos, 0 roles, 0 logo y 0 jerarquia: no hay nada que parsear. La feature de AI
esta demostrada cuando el sistema adapta ESE archivo y produce los formatos con los
roles correctos.

EL REPARTO DE TRABAJO, que es la decision de arquitectura de este modulo:

  el modelo hace lo que solo un modelo puede hacer
      transcribir el copy, y sobre todo asignar el ROL POR FUNCION. Hoy la
      inferencia de rol del camino SVG es ordenar por tamano de fuente. Un aviso
      legal fijado en cuerpo grande rompe ese orden y no rompe al modelo.

  los pixeles y las metricas de fuente hacen lo que hacen mejor
      DONDE esta cada cosa y CUANTO mide. Un VLM da cajas aproximadas; una mascara
      de color sobre la region propuesta da el bbox exacto de la tinta, y despejar
      el cuerpo contra las metricas reales de Lato da el tamano sin preguntarselo a
      nadie. El PESO se queda con el modelo: es la unica casilla que este adaptador
      no verifica, y se dice en voz alta en lugar de sugerir que todo esta medido.

No es reparto por prudencia: es que cada mitad es mejor en su mitad. El resultado
entra por el mismo `Scene` que el camino SVG, asi que el solver, el emisor y el
validador no se enteran de por donde entro la pieza.

DEGRADACION. Si la cadena de proveedores se agota, o si la respuesta no valida
contra el esquema, se cae al camino determinista Y SE REGISTRA en `scene.notes`,
que sale impreso en la hoja de contactos. Un fallback invisible es una mentira
diferida.
"""
from __future__ import annotations
import base64, io, json, os, re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from lxml import etree
from PIL import Image

import brand
import providers
import text as T
import trace as TR
from scene import Lockup, Photo, Scene, TextBlock

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ROLES = ("headline", "subhead", "support", "legal")
PROMPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "prompts")
PROMPT = os.path.join(PROMPTS, "scene_from_image.txt")
PROMPT_FOCAL = os.path.join(PROMPTS, "focal_region.txt")
GRID = 1000.0            # rejilla normalizada que se le pide al modelo
LEADING = 1.16           # interlineado supuesto al resolver el cuerpo desde la altura
COLOR_TOL = 78.0         # distancia euclidea en RGB para la mascara de tinta


# ------------------------------------------------------------------- el esquema
def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """El modelo devuelve JSON. A veces lo envuelve en un bloque de codigo, y a
    veces antepone una frase. Se recorta al primer objeto balanceado."""
    s = re.sub(r"^\s*```(?:json)?|```\s*$", "", (raw or "").strip(),
               flags=re.MULTILINE).strip()
    i = s.find("{")
    if i < 0:
        return None
    depth, in_str, esc = 0, False, False
    for j in range(i, len(s)):
        c = s[j]
        if in_str:
            esc = (c == "\\") and not esc
            if c == '"' and not esc:
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[i:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


def validate(d: Any, W: float, H: float) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Valida y NORMALIZA. Devuelve (escena, errores). Si hay errores, no hay escena.

    Se valida de verdad: tipos, rangos, roles conocidos, cajas dentro del lienzo y
    al menos un titular. Un esquema que solo comprueba que las claves existen deja
    pasar basura y la basura llega al SVG entregado.
    """
    errs: List[str] = []
    if not isinstance(d, dict):
        return None, ["la respuesta no es un objeto JSON"]
    texts = d.get("texts")
    if not isinstance(texts, list) or not texts:
        return None, ["'texts' ausente o vacio"]

    def box(v, what) -> Optional[Tuple[float, float, float, float]]:
        if not (isinstance(v, (list, tuple)) and len(v) == 4
                and all(isinstance(x, (int, float)) for x in v)):
            errs.append(f"{what}: bbox mal formado")
            return None
        x0, y0, x1, y1 = (float(x) for x in v)
        if x1 < x0 or y1 < y0:
            x0, x1 = min(x0, x1), max(x0, x1)
            y0, y1 = min(y0, y1), max(y0, y1)
        x0, x1 = x0 / GRID * W, x1 / GRID * W
        y0, y1 = y0 / GRID * H, y1 / GRID * H
        x0, y0 = max(0.0, x0), max(0.0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            errs.append(f"{what}: bbox degenerado tras normalizar")
            return None
        return (x0, y0, x1 - x0, y1 - y0)

    out: List[Dict[str, Any]] = []
    seen = set()
    for i, t in enumerate(texts):
        if not isinstance(t, dict):
            errs.append(f"texts[{i}]: no es un objeto"); continue
        role = str(t.get("role", "")).strip().lower()
        if role not in ROLES:
            errs.append(f"texts[{i}]: rol desconocido {role!r}"); continue
        if role in seen:
            errs.append(f"texts[{i}]: rol {role} duplicado"); continue
        body = " ".join(str(t.get("text", "")).split())
        if not body:
            errs.append(f"texts[{i}]: texto vacio"); continue
        r = box(t.get("bbox"), f"texts[{i}]")
        if r is None:
            continue
        col = str(t.get("color_hex", "")).strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", col):
            errs.append(f"texts[{i}]: color_hex invalido {col!r}"); continue
        seen.add(role)
        out.append({"role": role, "text": body, "rect": r, "fill": col.upper(),
                    "size": float(t.get("size_px") or 0.0),
                    "weight": int(t.get("weight") or 400),
                    "lines": max(1, int(t.get("lines") or 1))})
    if not any(o["role"] == "headline" for o in out):
        errs.append("no se identifico un titular")
    if errs:
        return None, errs

    logo = None
    lg = d.get("logo")
    if isinstance(lg, dict):
        lr = box(lg.get("bbox"), "logo")
        mr = box(lg.get("mark_bbox"), "logo.mark") if lg.get("mark_bbox") else None
        if lr:
            logo = {"rect": lr, "mark_rect": mr or lr,
                    "wordmark_size": float(lg.get("wordmark_size_px") or 0.0)}
    ph = d.get("photo") if isinstance(d.get("photo"), dict) else {}
    return {"texts": out, "logo": logo,
            "focal": box(ph.get("focal"), "photo.focal") if ph.get("focal") else None,
            "description": str(ph.get("description", ""))}, []


# -------------------------------------------------- medicion sobre los pixeles
def _ink_mask(rgb: np.ndarray, rect, fill: str, pad: float = 0.35) -> Tuple[np.ndarray, Any]:
    """Mascara de la tinta dentro de la caja propuesta, por distancia de color.

    El VLM propone una region; la mascara la ajusta al pixel. Sirve dos veces: para
    medir el bbox real del texto y para construir la mascara de reconstruccion.
    """
    Hh, Ww = rgb.shape[:2]
    x, y, w, h = rect
    px, py = w * pad, h * pad
    x0, y0 = int(max(0, x - px)), int(max(0, y - py))
    x1, y1 = int(min(Ww, x + w + px)), int(min(Hh, y + h + py))
    if x1 <= x0 or y1 <= y0:
        return np.zeros((Hh, Ww), np.uint8), None
    tgt = np.array([int(fill.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], np.float64)
    patch = rgb[y0:y1, x0:x1].astype(np.float64)
    d = np.sqrt(((patch - tgt) ** 2).sum(axis=2))
    m = (d < COLOR_TOL).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    # Solo los glifos DE ESTE bloque. La region se expande para no cortar el texto,
    # y al expandirla entra tinta ajena: el lockup comparte color y altura con el
    # titular, y sin este filtro el bbox del titular medía 848px en vez de 627 y el
    # cuerpo salia a 126px. Se conservan las componentes cuyo centroide cae dentro
    # de la caja que propuso el modelo, sin el margen.
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        cx, cy = cent[i][0] + x0, cent[i][1] + y0
        if x <= cx <= x + w and y <= cy <= y + h and stats[i, cv2.CC_STAT_AREA] >= 4:
            keep[lab == i] = 1
    if keep.sum() < 24:
        keep = m
    full = np.zeros((Hh, Ww), np.uint8)
    full[y0:y1, x0:x1] = keep
    ys, xs = np.nonzero(keep)
    if len(xs) < 24:
        return full, None
    return full, (x0 + xs.min(), y0 + ys.min(),
                  xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)


def _solve_type(body: str, tight, n_lines: int, weight: int) -> Tuple[float, str]:
    """El CUERPO, resuelto contra las metricas reales de Lato a partir del ancho.

    Por defecto se mide el ANCHO: la altura de tinta depende del interlineado y de
    si la cadena tiene descendentes, y ninguna de las dos cosas se ve en un JPEG,
    mientras que el ancho de avance de una cadena conocida a un peso conocido escala
    lineal con el cuerpo. La excepcion es una linea en caja alta, donde la altura ES
    la cap-height y da el cuerpo exacto aunque el bloque lleve tracking.

    El PESO se queda como lo dio el modelo, y esto es una decision, no un descuido.
    Se intento derivarlo del ancho y no se puede: cuerpo y peso mueven el ancho a la
    vez, una medida no despeja dos incognitas, y el intento empeoro tres de cuatro
    bloques frente a la respuesta del modelo. Se declara: el peso es el unico campo
    de la escena que este adaptador NO verifica.
    """
    words = tuple(body.split())
    L = max(1, min(n_lines, len(words)))
    cap = T.metrics_ref(weight)[2] / T.REF

    # Caso exacto por ALTURA: una linea en caja alta sin descendentes. Ahi la tinta
    # va del borde superior de la mayuscula a la linea base, o sea exactamente la
    # cap-height, y el cuerpo se despeja sin suponer nada. Es el unico caso en que
    # la altura es de fiar, y cubre justo el bloque que el ancho falla: el support
    # del master lleva tracking de 1.6 y por ancho salia a 30px en lugar de 20.
    if L == 1 and not any(c.islower() for c in body):
        return float(tight[3]) / max(cap, 1e-6), f"cap-height de {tight[3]}px"

    widths = T.partition(words, L, weight, 0.0)
    if not widths or max(widths) <= 0:
        return (float(tight[3]) / max((L - 1) * LEADING + cap, 1e-6),
                f"altura de {tight[3]}px, interlineado supuesto")
    return T.REF * float(tight[2]) / max(widths), f"ancho de tinta de {tight[2]}px"


def _logo_nodes(rgb: np.ndarray, rect, mask: np.ndarray, recolor: str = ""):
    """El lockup viene de pixeles, asi que sale como pixeles con alpha.

    Se recorta la region y se hace transparente todo lo que no es tinta, para que el
    logo se pose sobre la fotografia sin arrastrar su fondo. Un <image> con data URI
    es un nodo lxml como cualquier otro: el emisor lo coloca sin saber que no es
    geometria vectorial.
    """
    x, y, w, h = (int(round(v)) for v in rect)
    x, y = max(0, x), max(0, y)
    w = min(w, rgb.shape[1] - x); h = min(h, rgb.shape[0] - y)
    if w < 4 or h < 4:
        return []
    patch = rgb[y:y + h, x:x + w]
    if recolor:
        tint = [int(recolor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
        patch = np.full_like(patch, tint)
    a = mask[y:y + h, x:x + w] * 255
    a = cv2.GaussianBlur(a, (3, 3), 0)
    im = Image.fromarray(np.dstack([patch, a]).astype(np.uint8), "RGBA")
    buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    el = etree.Element("{%s}image" % SVG, nsmap={None: SVG, "xlink": XLINK})
    for k, v in (("x", x), ("y", y), ("width", w), ("height", h)):
        el.set(k, str(v))
    el.set("preserveAspectRatio", "xMidYMid meet")
    el.set("{%s}href" % XLINK, uri); el.set("href", uri)
    return [el]


def _plate(rgb: np.ndarray, mask: np.ndarray, out_dir: str) -> str:
    """La plancha limpia: la fotografia sin el texto quemado encima.

    Sin esto el sistema re-compone texto sobre una imagen que ya lo lleva dentro, y
    todos los formatos salen con el copy duplicado. Se reconstruye con inpainting
    clasico (Telea), no con un modelo generativo: es una dependencia que ya esta,
    es determinista y no abre brand safety. Es una APROXIMACION y se declara: bajo
    un titular de 92px la reconstruccion inventa textura plausible, no la original.
    """
    m = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=2)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    clean = cv2.inpaint(bgr, m, 9, cv2.INPAINT_TELEA)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "plate.jpg")
    cv2.imwrite(path, clean, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return path


# ----------------------------------------------------------------- el adaptador
def parse_raster(path: str, out_dir: str = "out/_work") -> Scene:
    im = Image.open(path).convert("RGB")
    W, H = float(im.size[0]), float(im.size[1])
    rgb = np.asarray(im)
    notes: List[str] = [f"entrada RASTER {int(W)}x{int(H)}px: sin capas, sin nodos de "
                        f"texto, sin metadatos. El parser de SVG extrae 0 elementos"]

    prompt = open(PROMPT).read().replace("{W}", str(int(W))).replace("{H}", str(int(H)))
    # Una traza por MASTER, no por formato: la llamada al modelo ocurre una sola vez
    # y de ella salen todos los tamanos. Es la unidad que hay que poder medir.
    with TR.Span("escena desde raster", input={"master": os.path.basename(path),
                                               "lienzo": f"{int(W)}x{int(H)}"}) as sp:
        TR.trace_meta(name="scene-from-raster",
                      tags=["scene", "raster"],
                      metadata={"master": os.path.basename(path),
                                "lienzo": f"{int(W)}x{int(H)}"})
        data, provider, log = providers.complete_vision(
            prompt, path, accept=lambda raw: validate(_parse_json(raw), W, H))
        notes.extend("proveedor · " + l for l in log)
        sp.update(output={"proveedor": provider,
                          "roles": [t["role"] for t in (data or {}).get("texts", [])]},
                  metadata={"intentos": len([l for l in log if ":" in l]),
                            "fallback": provider != providers.CHAIN[0]["name"]})
        # Un score por corrida: cuantos de los cuatro roles se recuperaron. Es la
        # senal de calidad mas barata que existe y no necesita ninguna etiqueta.
        if data:
            sp.score("roles_recuperados", len(data["texts"]) / 4.0,
                     "1.0 = los cuatro roles del master")
    if data is None:
        # Aqui no hay camino determinista al que caer: sobre un raster el parser de
        # SVG extrae cero elementos, que es justamente el punto de partida. Se falla
        # ruidosamente en lugar de entregar una escena vacia que el solver rellenaria
        # con lo que pillase.
        raise ValueError("la cadena de proveedores se agoto sin una escena valida; "
                         "ver la bitacora de proveedores")

    notes.append(f"observabilidad · {TR.estado()}")
    notes.append(f"escena semantica leida por {provider}: "
                 + ", ".join(f"{t['role']}={t['size']:.0f}px" for t in data["texts"]))

    # GUARDA: EL TEXTO PINTADO DENTRO DE LA FOTO NO ES COPY DE CAMPANA.
    #
    # `lleva_copy` decide por donde entra la pieza, y cuando se equivoca el dano es
    # DESTRUCTIVO: `_plate()` borra por inpainting lo que crea copy sobrepuesto, y eso
    # no se deshace. Medido sobre un anuncio con "DRINK Coca-Cola / Delicious and
    # Refreshing" PINTADO en el costado de una camioneta: el modelo lo leyo como
    # titular, el inpainting dejo manchones borrosos sobre el vehiculo en los cinco
    # formatos, y luego lo re-escribio como texto vivo encima, asi que en el MPU se lee
    # dos veces.
    #
    # `prompts/scene_from_image.txt` ya lo dice -"un cartel de una tienda que aparece
    # DENTRO de la fotografia no es copy de campana"-. Afinar el prompt con este caso
    # seria ajustarlo a la foto que tengo delante. Lo que se puede hacer sin inventar un
    # criterio es CORROBORAR con la otra respuesta que el modelo ya dio en la misma
    # llamada: donde esta el sujeto.
    #
    # No es un umbral ajustado, es una pregunta de contencion: el copy sobrepuesto va
    # FUERA del sujeto -es lo que lo hace legible-, y el texto fotografiado esta DENTRO.
    # Si el titular cae mayormente dentro de la region focal, esta pintado sobre el
    # sujeto y la pieza es una fotografia, no una composicion.
    #
    # Se falla ruidosamente en lugar de degradar aqui: quien llama tiene una ruta mejor
    # -aplicar la campana SOBRE la fotografia, dejandola intacta- y es la correcta para
    # este caso. El demo ya cae a ella cuando la escena no valida.
    foc = data.get("focal")
    if foc:
        cab = next((t for t in data["texts"] if t["role"] == "headline"), None)
        if cab:
            hx, hy, hw, hh = cab["rect"]
            fx, fy, fw, fh = foc
            ix = max(0.0, min(hx + hw, fx + fw) - max(hx, fx))
            iy = max(0.0, min(hy + hh, fy + fh) - max(hy, fy))
            dentro = (ix * iy) / max(hw * hh, 1e-9)
            if dentro >= 0.60:
                raise ValueError(
                    f"el titular cae {dentro:.0%} DENTRO de la region del sujeto "
                    f"({fw:.0f}x{fh:.0f}px): es texto fotografiado, no copy "
                    f"sobrepuesto. Borrarlo por inpainting destruiria el sujeto, asi "
                    f"que la pieza entra como FOTOGRAFIA y no como composicion")

    mask = np.zeros(rgb.shape[:2], np.uint8)
    blocks: List[TextBlock] = []
    for t in data["texts"]:
        m, tight = _ink_mask(rgb, t["rect"], t["fill"])
        if tight is None:
            notes.append(f"{t['role']}: la mascara de tinta no encontro glifos en la "
                         f"caja propuesta; se usan las cifras del modelo")
            size, weight, rect = t["size"], t["weight"], t["rect"]
        else:
            mask |= m
            weight = t["weight"]
            size, how = _solve_type(t["text"], tight, t["lines"], weight)
            rect = (float(tight[0]), float(tight[1]), float(tight[2]), float(tight[3]))
            notes.append(f"{t['role']}: el modelo estimo {t['size']:.0f}px; medido "
                         f"sobre pixeles da {size:.0f}px a peso {weight} ({how})")
        blocks.append(TextBlock(role=t["role"], words=t["text"].split(),
                                size=round(size, 1), weight=weight, fill=t["fill"],
                                tracking=0.0, rect=rect,
                                n_lines_master=t["lines"]))
    blocks.sort(key=lambda b: -b.size)

    lockup = None
    if data["logo"]:
        lr = data["logo"]["rect"]
        lm, tight = _ink_mask(rgb, lr, brand.PALETTE["ink"], pad=0.12)
        if tight is not None:
            mask |= lm
            lr = (float(tight[0]), float(tight[1]), float(tight[2]), float(tight[3]))
        nodes = _logo_nodes(rgb, lr, lm)
        mrect = data["logo"]["mark_rect"]
        light = brand.PALETTE["light"]
        lockup = Lockup(rect=lr, nodes=nodes,
                        mark_nodes=_logo_nodes(rgb, mrect, lm) or nodes,
                        light_nodes=_logo_nodes(rgb, lr, lm, light),
                        light_mark_nodes=_logo_nodes(rgb, mrect, lm, light),
                        mark_rect=mrect,
                        wordmark_size=data["logo"]["wordmark_size"] or 0.0)
        notes.append(f"lockup recuperado como raster con alpha, {lr[2]:.0f}x{lr[3]:.0f}px, "
                     "en variante oscura y clara. El emisor recolorea vectores, y estos "
                     "son pixeles, asi que el adaptador entrega las dos hechas")

    plate = _plate(rgb, mask, out_dir)
    notes.append("fotografia reconstruida por inpainting bajo el texto y el lockup "
                 f"-> {plate}. Es una aproximacion, no la placa original")
    if data.get("description"):
        notes.append("foto segun el modelo: " + data["description"])

    pim = Image.open(plate)
    return Scene(width=W, height=H,
                 photo=Photo(rect=(0.0, 0.0, W, H), src_path=plate,
                             px_w=pim.size[0], px_h=pim.size[1]),
                 texts=blocks, lockup=lockup, notes=notes)


# ------------------------------------------------------- la region que no se corta
# "grupo" entro despues, y lo pidio el propio modelo. Sobre una foto de once
# personas respondio sujeto="grupo", el esquema lo rechazo por desconocido y la
# cadena cayo al siguiente proveedor gastando catorce segundos. La respuesta era
# correcta y la lista estaba corta: un esquema demasiado estrecho no protege, filtra
# lo que no supo prever quien lo escribio.
SUJETOS = ("persona", "grupo", "producto", "comida", "edificio", "ilustracion",
           "tipografia", "animal", "paisaje", "ninguno")

# QUE SUJETOS DAN UNA CAJA COMPACTA, Y CUALES UNA EXTENSION.
#
# Se deriva de `focal_proxy`, no de una intuicion sobre que sujetos "son anchos".
# Mirando sus tres ramas: `persona` devuelve un CUADRADO de la cabeza -compacto, y
# cualquier formato puede contenerlo-. `grupo` y todo lo demas conservan el ANCHO
# entero de la caja del modelo, porque ese ancho ES la extension del sujeto y
# encogerlo pierde justo lo que importa. Una caja a ancho completo no cabe en ninguna
# ventana mas estrecha que la fuente, asi que exigir contenerla al 99.5% declara
# insatisfacible y degrada la foto a panel en casi todos los formatos.
#
# Por eso la contencion dura solo aplica a `persona`. Para el resto la restriccion
# correcta es "conservar la mayor parte", que es `crop.choose(face_hard=False)`.
#
# LA PRIMERA VERSION DE ESTO ERA UNA LISTA A MANO -grupo, edificio, paisaje,
# tipografia- y estaba mal. Dejaba fuera `ilustracion`, que cae en la misma rama de
# ancho completo, y lo dejaba fuera porque la corrida que tenia delante habia salido
# bien. Salio bien por otra razon: el modelo habia etiquetado esa ilustracion como
# `persona`. La misma imagen, otra corrida, respondio `ilustracion` -"madera con bate
# y cara" en lugar de "persona de madera con bate"- y degrado a panel en 3 de 5
# formatos. Elegir la etiqueta no es determinista y el codigo no puede depender de
# que caiga del lado bueno.
#
# La leccion, que es la del proyecto entero: la lista se deriva del mecanismo, no de
# los casos que uno vio.
SUJETOS_COMPACTOS = frozenset({"persona"})


def es_extenso(sujeto: str) -> bool:
    """True si la region del sujeto es una extension y no se puede exigir entera."""
    return sujeto not in SUJETOS_COMPACTOS


def _valida_focal(d, W: float, H: float):
    """Valida la respuesta del modelo sobre la region focal."""
    if not isinstance(d, dict):
        return None, ["no es un objeto JSON"]
    v = d.get("focal")
    if not (isinstance(v, (list, tuple)) and len(v) == 4
            and all(isinstance(x, (int, float)) for x in v)):
        return None, ["focal mal formada"]
    suj = str(d.get("sujeto", "")).strip().lower()
    if suj not in SUJETOS:
        return None, [f"sujeto desconocido {suj!r}"]
    try:
        conf = float(d.get("confianza", 0.0))
    except (TypeError, ValueError):
        return None, ["confianza no numerica"]
    x0, y0, x1, y1 = (float(x) for x in v)
    x0, x1 = sorted((x0 / GRID * W, x1 / GRID * W))
    y0, y1 = sorted((y0 / GRID * H, y1 / GRID * H))
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    w, h = x1 - x0, y1 - y0
    if w < 8 or h < 8:
        return None, ["focal degenerada"]
    # Una caja que cubre casi todo no restringe nada, y como restriccion dura del
    # recorte es peor que no tener ninguna: obligaria a no recortar.
    if (w * h) / (W * H) > 0.80:
        return None, [f"focal cubre el {(w*h)/(W*H):.0%} de la imagen: no restringe"]
    return {"rect": (x0, y0, w, h), "sujeto": suj, "confianza": conf,
            "lleva_copy": bool(d.get("lleva_copy", False)),
            "que_es": str(d.get("que_es", ""))[:70],
            "por_que": str(d.get("por_que", ""))[:160]}, []


def focal_from_model(path: str, min_conf: float = 0.45):
    """Que parte de la imagen no se puede perder, segun un modelo.

    SE LLAMA SOLO CUANDO EL CAMINO BARATO NO SABE. Las dos cascadas de Haar puestas
    de acuerdo resuelven una fotografia con una cara de frente en milisegundos y
    gratis; cuando no coinciden, o cuando la pieza no es una fotografia de una
    persona -una ilustracion, un producto, un plato, tipografia sobre un fondo-, no
    hay geometria que consultar y la pregunta pasa a ser semantica.

    Es el mismo patron que decide todo lo demas en este sistema: la via barata y
    fiable primero, el modelo donde solo un modelo puede responder. Y por eso el
    coste sigue siendo por master y no por formato.

    Devuelve None si la cadena falla, si el esquema no valida o si el propio modelo
    declara poca confianza: un paisaje sin foco claro es una respuesta legitima, y
    entonces manda la saliencia.
    """
    im = Image.open(path)
    W, H = float(im.size[0]), float(im.size[1])
    prompt = (open(PROMPT_FOCAL).read()
              .replace("{W}", str(int(W))).replace("{H}", str(int(H))))
    with TR.Span("region focal", input={"imagen": os.path.basename(path),
                                        "lienzo": f"{int(W)}x{int(H)}"}) as sp:
        TR.trace_meta(name="focal-region", tags=["focal", "crop"],
                      metadata={"imagen": os.path.basename(path)})
        data, provider, log = providers.complete_vision(
            prompt, path, accept=lambda raw: _valida_focal(_parse_json(raw), W, H))
        if data is None:
            sp.update(level="WARNING", status_message="sin region focal utilizable")
            return None, log
        if data["confianza"] < min_conf:
            sp.update(output=data, level="WARNING",
                      status_message=f"confianza {data['confianza']:.2f} bajo el minimo")
            log.append(f"el modelo declara confianza {data['confianza']:.2f}, bajo el "
                       f"minimo de {min_conf:.2f}: manda la saliencia")
            return None, log
        data["proveedor"] = provider
        sp.update(output=data)
        sp.score("focal_confianza", data["confianza"], data["que_es"])
        return data, log


def focal_proxy(rect, sujeto: str, W: float, H: float):
    """Adapta la caja del modelo a lo que la guarda del recorte sabe acotar.

    `crop.choose` compara `alto_de_la_caja / alto_del_recorte` contra un suelo y un
    techo, calibrados sobre una cara. Solo mira el ALTO. Encoger tambien el ancho
    -que es lo que hacia la primera version- pierde justo lo que importa en un
    grupo: el modelo devolvia del 25% al 73% del ancho y quedaba en 36% a 62%, o sea
    la gente de los extremos fuera. El ancho es la extension del sujeto y no se toca.

    Que se conserva de cada caja depende de que sea el sujeto:

      persona   la cabeza, arriba. La caja del modelo incluye el torso y pasaria del
                techo en casi todos los formatos, degradando la foto a panel siempre.
      grupo     la banda de las caras, que es la parte alta. Conservar hasta los pies
                obliga a recortes que no caben y no anade nada.
      lo demas  el objeto entero; si es demasiado alto se encoge hacia su centro,
                porque un producto o un plato no tienen "parte de arriba" util.
    """
    x, y, w, h = rect
    tope = 0.40 * H
    if sujeto == "persona":
        lado = min(w, h * 0.32, tope)
        return (x + w / 2.0 - lado / 2.0, y + h * 0.02, lado, lado)
    if sujeto == "grupo":
        nh = min(h * 0.55, tope)
        return (x, y + h * 0.02, w, nh)
    if h <= tope:
        return rect
    nh = tope
    return (x, y + (h - nh) / 2.0, w, nh)
