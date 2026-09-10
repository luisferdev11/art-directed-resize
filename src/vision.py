"""Analisis de imagen: luminancia, contraste por percentiles, saliencia,
region focal, campo de costo de emplazamiento y PPI efectivo del recorte.

El campo de costo es el corazon del sistema: hace que el emplazamiento del texto
se DERIVE de los pixeles de la fotografia en lugar de elegirse de una lista de
anclajes. Es lo que separa esto de un template.
"""
from __future__ import annotations
from typing import List, Optional, Tuple
import cv2
import numpy as np

Rect = Tuple[float, float, float, float]   # x, y, w, h


# ---------------------------------------------------------------- luminancia
def srgb_to_linear(a: np.ndarray) -> np.ndarray:
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def luminance(rgb_u8: np.ndarray) -> np.ndarray:
    """Luminancia relativa WCAG, en [0,1]."""
    a = rgb_u8.astype(np.float64) / 255.0
    lin = srgb_to_linear(a)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def hex_luminance(h: str) -> float:
    h = h.lstrip("#")
    rgb = np.array([[[int(h[i:i + 2], 16) for i in (0, 2, 4)]]], dtype=np.uint8)
    return float(luminance(rgb)[0, 0])


def contrast_ratio(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def worst_contrast(lum: np.ndarray, rect: Rect, text_lum: float) -> float:
    """Contraste en el PEOR caso bajo un rectangulo de texto.

    Se usan percentiles, no la media: la media esconde el brillo especular que se
    come una palabra entera. Para texto oscuro el enemigo es el fondo mas oscuro
    (p10); para texto claro, el mas brillante (p90).
    """
    x, y, w, h = (int(round(v)) for v in rect)
    H, W = lum.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    blk = lum[y0:y1, x0:x1]
    if text_lum > 0.5:                      # texto claro
        return contrast_ratio(text_lum, float(np.percentile(blk, 90)))
    return contrast_ratio(text_lum, float(np.percentile(blk, 10)))


def required_contrast(size_px: float, weight: int) -> float:
    """Umbral WCAG. 'Texto grande' es >=24px normal o >=18.66px bold."""
    large = size_px >= 24.0 or (weight >= 700 and size_px >= 18.66)
    return 3.0 if large else 4.5


def linear_to_srgb(a: np.ndarray) -> np.ndarray:
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.maximum(a, 0.0) ** (1 / 2.4) - 0.055)


def scrim_alpha(rgb_u8: np.ndarray, rect: Rect, text_lum: float,
                target: float, scrim_hex: str) -> Optional[float]:
    """Alpha minimo del scrim que lleva el peor percentil al contraste objetivo.

    NO hay forma cerrada, y creer que la habia era el error. El compositing de SVG
    ocurre sobre valores sRGB, no sobre luminancia: s' = a*scrim + (1-a)*fondo con
    s en sRGB. La luminancia es una funcion con gamma de esos valores, asi que
    despejar la mezcla en luminancia subestima el alpha, y mucho justo donde mas
    importa. Medido: sobre un fondo de luminancia 0.025 la formula lineal pedia
    alpha 0.136 esperando llegar a 0.157, y el archivo entregado se quedaba en
    0.062 -contraste 1.63:1 contra 3.0 exigido-. Lo encontro el validador al medir
    el SVG entregado en lugar de creerse el manifest.

    Se busca por biseccion sobre el alpha, componiendo sobre los pixeles reales. La
    luminancia del resultado es monotona en alpha, asi que la biseccion converge y
    da el minimo. Cuesta ~24 composiciones sobre un recorte pequeno: nada.
    """
    x, y, w, h = (int(round(v)) for v in rect)
    H, W = rgb_u8.shape[:2]
    patch = rgb_u8[max(0, y):min(H, y + h), max(0, x):min(W, x + w)]
    if patch.size == 0:
        return None
    light_text = text_lum > 0.5
    pct = 90 if light_text else 10
    tint = np.array([int(scrim_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)],
                    dtype=np.float64)
    base = patch.astype(np.float64)

    def reached(a: float) -> bool:
        mixed = (base * (1 - a) + tint * a).astype(np.uint8)
        worst = float(np.percentile(luminance(mixed), pct))
        return contrast_ratio(text_lum, worst) >= target

    if reached(0.0):
        return 0.0
    if not reached(1.0):
        return None
    lo, hi = 0.0, 1.0
    for _ in range(24):
        mid = (lo + hi) / 2.0
        if reached(mid):
            hi = mid
        else:
            lo = mid
    return float(hi)


# ---------------------------------------------------------------- saliencia
_SAL = cv2.saliency.StaticSaliencyFineGrained_create()


def saliency(gray: np.ndarray) -> np.ndarray:
    ok, S = _SAL.computeSaliency(gray)
    if not ok:
        return np.zeros_like(gray, dtype=np.float64)
    return S.astype(np.float64)


def _iou(a: Rect, b: Rect) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    i = (x1 - x0) * (y1 - y0)
    return i / (a[2] * a[3] + b[2] * b[3] - i)


def face_candidates(gray: np.ndarray) -> Tuple[List[Rect], List[Rect]]:
    """Candidatos de cada cascada por separado, para poder confrontarlas."""
    out = []
    for name in ("default", "alt2"):
        c = cv2.CascadeClassifier(
            cv2.data.haarcascades + f"haarcascade_frontalface_{name}.xml")
        out.append([tuple(map(float, r))
                    for r in c.detectMultiScale(gray, 1.08, 5, minSize=(28, 28))])
    return out[0], out[1]


def agreed_faces(gray: np.ndarray) -> List[Rect]:
    """Caras en las que las DOS cascadas coinciden, de mayor a menor.

    Un ensemble de dos detectores entrenados por separado, no un umbral ajustado a
    los casos que habia a mano. Una cascada frontal de 2001 sola es un generador de
    falsos positivos: sobre una foto de una persona con gorra y gafas frente a un
    edificio devolvieron ocho detecciones entre las dos y ninguna era una cara -un
    reloj de pulsera, ventanas de la fachada, postes sobre cesped-. Ninguna de esas
    ocho tenia acuerdo.
    """
    a, b = face_candidates(gray)
    fuera = []
    for x in a:
        v = max((_iou(x, y) for y in b), default=0.0)
        if v > 0.30:
            fuera.append(x)
    return sorted(fuera, key=lambda r: -r[2] * r[3])


def dominant_face(gray: np.ndarray) -> Optional[Rect]:
    """La cara cuando NO HAY DUDA, y None cuando la hay.

    Devolver None no es quedarse sin respuesta: es declarar que este detector no
    puede responder, para que quien llama escale a quien si puede.

    Hay duda en dos casos, y los dos importan:

      · CERO caras con acuerdo. O no hay nadie, o la pieza no es una fotografia de
        una persona: una ilustracion, un producto, tipografia sobre un color.

      · VARIAS caras con acuerdo. Medido sobre una foto de grupo: once caras
        corroboradas repartidas entre el 31% y el 69% del ancho. Elegir la mayor
        -que es lo que se hacia- fija el recorte a una persona y se come al resto.
        Cual de ellas sostiene la composicion, o si lo que importa es el grupo
        entero, es un juicio compositivo. La geometria no lo tiene.

    La tentacion aqui era escribir un agrupador con sus umbrales y una escalera de
    encogimiento. Seria mi criterio disfrazado de medicion, y ajustado a las fotos
    que tenia delante.
    """
    caras = agreed_faces(gray)
    return caras[0] if len(caras) == 1 else None


def people(gray: np.ndarray) -> List[Rect]:
    """Personas por HOG. Se conserva como senal auxiliar, no como autoridad.

    Se probo usarlo para corroborar caras y no sirve para eso: sus cajas vienen
    descentradas respecto de la cabeza, y ninguna cara REAL de las cuatro fotos de
    prueba caia dentro de su caja. Sirve para saber si hay gente, no donde.
    """
    h, w = gray.shape[:2]
    k = 900.0 / max(w, h, 1)
    small = cv2.resize(gray, (max(64, int(w * k)), max(64, int(h * k))),
                       interpolation=cv2.INTER_AREA) if k < 1.0 else gray
    kk = small.shape[1] / float(w)
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    try:
        rects, weights = hog.detectMultiScale(small, winStride=(8, 8),
                                              padding=(8, 8), scale=1.05)
    except cv2.error:
        return []
    return [(x / kk, y / kk, ww / kk, hh / kk)
            for (x, y, ww, hh), wt in zip(rects, weights) if float(wt) >= 0.30]


def focal_region(rgb_u8: np.ndarray, pct: float = 88.0) -> Tuple[Rect, Optional[Rect]]:
    """Devuelve (bbox de saliencia, bbox de cara o None), en coords de la imagen."""
    gray = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2GRAY)
    S = saliency(gray)
    thr = np.percentile(S, pct)
    ys, xs = np.where(S >= thr)
    if len(xs) == 0:
        H, W = gray.shape
        sal_box = (0.0, 0.0, float(W), float(H))
    else:
        sal_box = (float(xs.min()), float(ys.min()),
                   float(xs.max() - xs.min() + 1), float(ys.max() - ys.min() + 1))
    return sal_box, dominant_face(gray)


# ------------------------------------------------ campo de costo + integral
def cost_field(rgb_u8: np.ndarray, grid: Tuple[int, int] = (64, 36)) -> np.ndarray:
    """Campo de costo de emplazamiento, normalizado a [0,1]. Alto = mal sitio.

    Tres terminos: saliencia (no tapar el sujeto), varianza local de luminancia
    (fondo ruidoso perjudica la legibilidad) y gradiente de luminancia (bordes).
    """
    gw, gh = grid
    small = cv2.resize(rgb_u8, (gw * 8, gh * 8), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    S = saliency(gray)
    lum = luminance(small)
    mean = cv2.blur(lum, (9, 9))
    var = np.abs(cv2.blur(lum * lum, (9, 9)) - mean * mean)
    gx = cv2.Sobel(lum, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(lum, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.sqrt(gx * gx + gy * gy)

    def norm(a):
        lo, hi = np.percentile(a, 1), np.percentile(a, 99)
        return np.clip((a - lo) / max(hi - lo, 1e-9), 0.0, 1.0)

    field = 0.50 * norm(S) + 0.32 * norm(var) + 0.18 * norm(grad)
    return cv2.resize(field, (gw, gh), interpolation=cv2.INTER_AREA)


def integral(field: np.ndarray) -> np.ndarray:
    """Summed-area table con fila y columna cero, para consultas O(1)."""
    return np.pad(field, ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)


def rect_mean(ii: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> float:
    """Media del campo en el rectangulo [x0,x1) x [y0,y1). O(1)."""
    n = max((x1 - x0) * (y1 - y0), 1)
    total = ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]
    return float(total) / n


# ---------------------------------------------------------------- resolucion
def effective_ppi(src_px: float, crop_fraction: float, out_px: float,
                  nominal: float = 72.0) -> float:
    """PPI efectivo del recorte.

    Si el master trae 1200px y se usa el 25% para un lienzo de 1920, se esta
    sobre-muestreando 4x y en pantalla grande se ve blando. Un disenador lo nota.
    """
    available = src_px * max(crop_fraction, 1e-6)
    return nominal * available / max(out_px, 1e-6)
