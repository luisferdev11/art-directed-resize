"""Tipografia: medicion, particion de lineas y resolucion cerrada del cuerpo.

LA IDEA CENTRAL. La medicion de PIL es exactamente lineal en el tamano de fuente
(verificado: ratio 2.0000 entre 100px y 50px). Consecuencia util: para un numero
FIJO de lineas L, la particion optima de palabras es invariante a escala, porque
todos los anchos escalan por el mismo factor y el argmin no depende de s.

Asi que el cuerpo se resuelve en forma CERRADA en lugar de por busqueda:
  1. particionar en L lineas a un tamano de referencia
  2. s = ref * ancho_caja / ancho_de_la_linea_mas_larga
  3. verificar que L * interlinea * s cabe en el alto
  4. bajar al peldano mas cercano de la escala tipografica de la marca

Y el objetivo al particionar no es irregularidad estetica: es MINIMIZAR EL ANCHO
DE LA LINEA MAS LARGA, porque eso maximiza directamente el cuerpo alcanzable.
El desempate si es por regularidad.

Calibracion medida contra Blink (ver tools/gate24_calibrate.py): PIL sobreestima
el ancho ~1% (Black 0.9899, Regular 0.9918, peor desviacion 1.22%). Se conserva la
medida de PIL sin corregir porque errar por exceso es el lado seguro, y encima se
mantiene un gutter de SAFETY.
"""
from __future__ import annotations
from functools import lru_cache
from itertools import combinations
from typing import List, Optional, Sequence, Tuple
import os

from PIL import ImageFont

import brand

REF = 100.0        # tamano de referencia para medir
SAFETY = 1.04      # gutter sobre el ancho medido
MAX_ENUM_WORDS = 14

BLINK_RATIO = {900: 0.9899, 700: 0.9910, 400: 0.9918, 300: 0.9918, 100: 0.9918}


@lru_cache(maxsize=64)
def _font(weight: int, size_px: int) -> ImageFont.FreeTypeFont:
    name = next((k for k, (_, w) in brand.WEIGHTS.items() if w == weight), "regular")
    return ImageFont.truetype(os.path.join(brand.FONT_DIR, brand.WEIGHTS[name][0]), size_px)


@lru_cache(maxsize=4096)
def advance_ref(word: str, weight: int) -> float:
    """Ancho de avance de una palabra al tamano de referencia."""
    return float(_font(weight, int(REF)).getlength(word))


def advance(text: str, weight: int, size: float, tracking: float = 0.0) -> float:
    """Ancho de avance a un tamano arbitrario, por escalado lineal."""
    w = advance_ref(text, weight) * size / REF
    if tracking and len(text) > 1:
        w += tracking * (len(text) - 1)
    return w


@lru_cache(maxsize=64)
def metrics_ref(weight: int) -> Tuple[float, float, float, float]:
    """(ascent, descent, cap_height, cap_top_desde_origen) al tamano de referencia."""
    f = _font(weight, int(REF))
    asc, desc = f.getmetrics()
    bb = f.getbbox("H")
    return float(asc), float(desc), float(bb[3] - bb[1]), float(bb[1])


def ascent(weight: int, size: float) -> float:
    return metrics_ref(weight)[0] * size / REF


def optical_baseline(box_top: float, box_h: float, weight: int, size: float) -> float:
    """Baseline que centra opticamente por CAP-HEIGHT, no por bbox de la cadena.

    El bbox incluye holgura de ascender y descender; con 74px utiles en un
    leaderboard, 4px de error de baseline se ven.
    """
    asc, _, cap_h, cap_top = metrics_ref(weight)
    k = size / REF
    cap_h *= k
    return box_top + (box_h - cap_h) / 2.0 + (asc * k - cap_top * k)


# --------------------------------------------------------------- particion
def _line_widths_ref(words: Sequence[str], breaks: Sequence[int], weight: int,
                     tracking: float) -> List[float]:
    space = advance_ref(" ", weight)
    out, start = [], 0
    for end in list(breaks) + [len(words)]:
        chunk = words[start:end]
        w = sum(advance_ref(x, weight) for x in chunk) + space * (len(chunk) - 1)
        if tracking:
            nchars = sum(len(x) for x in chunk) + (len(chunk) - 1)
            w += tracking * REF / max(REF, 1) * (nchars - 1)
        out.append(w)
        start = end
    return out


def partition(words: Sequence[str], n_lines: int, weight: int,
              tracking: float = 0.0) -> Optional[List[float]]:
    """Anchos de linea (al tamano de referencia) de la mejor particion en n_lines.

    Objetivo lexicografico: (menor ancho maximo, menor varianza). El primero
    maximiza el cuerpo alcanzable; el segundo evita rags feos entre empates.
    Enumeracion exhaustiva: con <=14 palabras es optimo y trivial.
    """
    n = len(words)
    if n_lines < 1 or n_lines > n:
        return None
    if n_lines == 1:
        return _line_widths_ref(words, [], weight, tracking)
    if n > MAX_ENUM_WORDS:                       # salida greedy declarada
        per = n / n_lines
        brk = [int(round(per * i)) for i in range(1, n_lines)]
        return _line_widths_ref(words, brk, weight, tracking)
    best, best_key = None, None
    for brk in combinations(range(1, n), n_lines - 1):
        ws = _line_widths_ref(words, brk, weight, tracking)
        mx = max(ws)
        mean = sum(ws) / len(ws)
        var = sum((w - mean) ** 2 for w in ws)
        key = (round(mx, 4), round(var, 4))
        if best_key is None or key < best_key:
            best, best_key = ws, key
    return best


def snap_down(size: float) -> Optional[float]:
    """Baja al peldano mas cercano de la escala tipografica de la marca.

    El solver ELIGE de la escala en lugar de inventar un tamano: es lo que hace
    que el output se lea disenado y no ajustado a la fuerza.
    """
    ok = [s for s in brand.TYPE_SCALE if s <= size + 1e-9]
    return float(max(ok)) if ok else None


def snap_up(size: float) -> Optional[float]:
    """Sube al peldano mas cercano de la escala. Necesario al aplicar el piso de
    legibilidad: snap_down(13) da 12, que queda POR DEBAJO del piso."""
    ok = [s for s in brand.TYPE_SCALE if s >= size - 1e-9]
    return float(min(ok)) if ok else None


@lru_cache(maxsize=2048)
def _words(text: str) -> Tuple[str, ...]:
    return tuple(text.split())


class Fit:
    __slots__ = ("size", "n_lines", "lines", "width", "height", "leading", "reason")

    def __init__(self, size, n_lines, lines, width, height, leading, reason=""):
        self.size, self.n_lines, self.lines = size, n_lines, lines
        self.width, self.height, self.leading, self.reason = width, height, leading, reason

    def __repr__(self):
        return f"Fit({self.size:g}px x{self.n_lines} {self.width:.0f}x{self.height:.0f})"


def _tracking_ref(tracking: float, size: float) -> float:
    """Tracking expresado a escala de REFERENCIA.

    `letter-spacing` en SVG es ABSOLUTO en px: no escala con el cuerpo. Pero
    `partition` devuelve anchos a REF y quien la llama los multiplica por size/REF,
    lo que escalaba tambien el tracking. A 11px el ajuste creia que un tracking de
    1.6 anadia 2.8px cuando anade 25.6, y el bloque se salia del area segura 22.8px.
    Lo encontro el validador sobre un master con otra fotografia, no el ojo.

    Pre-escalando aqui, el `* size/REF` posterior devuelve el tracking a su valor
    absoluto y la cuenta cuadra con `advance()`, que es lo que mide el validador.
    """
    return tracking * REF / size if (tracking and size > 0) else 0.0


def fit_block(text: str, box_w: float, box_h: float, weight: int,
              leading_factor: float = 1.14, max_lines: int = 6,
              tracking: float = 0.0, min_size: float = 0.0) -> Optional[Fit]:
    """Cuerpo maximo de la escala que cabe en (box_w, box_h). Forma cerrada por L.

    Devuelve None si ninguna L cabe por encima de min_size: eso es una violacion
    de restriccion que el solver debe reportar, NUNCA encoger en silencio.
    """
    ws = _words(text)
    if not ws:
        return None
    usable_w = box_w / SAFETY
    best: Optional[Fit] = None
    for L in range(1, min(max_lines, len(ws)) + 1):
        # El tracking pre-escalado depende del cuerpo, y aqui el cuerpo es justo lo
        # que se despeja. Se itera: la primera pasada lo ignora, las siguientes lo
        # corrigen con el cuerpo ya estimado. Sin tracking, la primera ya es exacta.
        widths = partition(ws, L, weight, 0.0)
        if widths is None or max(widths) <= 0:
            continue
        size = REF * usable_w / max(widths)             # <-- la forma cerrada
        for _ in range(2 if tracking else 0):
            w2 = partition(ws, L, weight, _tracking_ref(tracking, size))
            if w2 is None or max(w2) <= 0:
                break
            widths = w2
            size = REF * usable_w / max(widths)
        mx = max(widths)
        size = min(size, box_h / (L * leading_factor))
        snapped = snap_down(size)
        if snapped is None or snapped < min_size:
            continue
        # El cuerpo acaba de bajar a un peldano de la escala, asi que el tracking
        # pre-escalado queda desfasado y el ancho se subestimaba en un par de px,
        # siempre por defecto: justo la direccion que desborda.
        if tracking:
            w3 = partition(ws, L, weight, _tracking_ref(tracking, snapped))
            if w3 is None or max(w3) <= 0:
                continue
            widths, mx = w3, max(w3)
            if mx * snapped / REF > usable_w + 0.5:
                continue
        lead = snapped * leading_factor
        h = (L - 1) * lead + snapped * (metrics_ref(weight)[2] / REF) + snapped * 0.22
        if h > box_h + 0.5:
            continue
        if best is None or snapped > best.size:
            k = snapped / REF
            best = Fit(snapped, L, _lines_from(ws, widths, weight,
                                               _tracking_ref(tracking, snapped)),
                       mx * k, h, lead)
    return best


def _lines_from(words: Tuple[str, ...], widths: List[float], weight: int,
                tracking: float) -> List[str]:
    """Reconstruye el texto de cada linea a partir de los anchos de la particion."""
    space = advance_ref(" ", weight)
    out, i = [], 0
    for target in widths:
        acc, chunk = 0.0, []
        while i < len(words):
            w = advance_ref(words[i], weight)
            nxt = acc + w + (space if chunk else 0.0)
            if chunk and nxt > target + 0.51:
                break
            chunk.append(words[i]); acc = nxt; i += 1
        out.append(" ".join(chunk))
    if i < len(words):                     # nunca perder palabras
        out[-1] = (out[-1] + " " + " ".join(words[i:])).strip()
    return out


def longest_word_size(text: str, box_w: float, weight: int) -> float:
    """Cuerpo maximo al que la palabra mas ancha cabe en box_w.

    Si esto queda bajo el piso de legibilidad, ninguna particion salva el bloque:
    es violacion de restriccion y bandera REVISAR, no puntos suspensivos.
    """
    ws = _words(text)
    if not ws:
        return float("inf")
    mx = max(advance_ref(w, weight) for w in ws)
    return REF * (box_w / SAFETY) / max(mx, 1e-9)


def fit_at_size(text: str, box_w: float, size: float, weight: int,
                leading_factor: float = 1.14, max_lines: int = 6,
                tracking: float = 0.0) -> Optional[Fit]:
    """Ajusta a un cuerpo FIJO, eligiendo el minimo de lineas que cabe en box_w.

    Sirve para preservar la jerarquia: el titular se resuelve por busqueda y los
    demas bloques derivan su cuerpo del ratio del master, no de maximizarse.
    """
    ws = _words(text)
    if not ws:
        return None
    usable = box_w / SAFETY
    tr_ref = _tracking_ref(tracking, size)
    for L in range(1, min(max_lines, len(ws)) + 1):
        widths = partition(ws, L, weight, tr_ref)
        if widths is None:
            continue
        if max(widths) * size / REF <= usable + 0.5:
            lead = size * leading_factor
            h = (L - 1) * lead + size * (metrics_ref(weight)[2] / REF) + size * 0.22
            k = size / REF
            return Fit(size, L, _lines_from(ws, widths, weight, tr_ref),
                       max(widths) * k, h, lead)
    return None
