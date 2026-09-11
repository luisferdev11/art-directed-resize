"""Filas de formato. Anadir un formato es anadir una fila: no se toca codigo.

Los insets son ASIMETRICOS y por plataforma. En 9:16 para Stories y Reels la
interfaz tapa aproximadamente el 14% superior y el 20% inferior; poner el titular
en el 15% inferior delata a alguien que nunca envio creatividad social.

El ORDEN DE LA LISTA es el orden del video, y `in_video` dice quien entra. Antes
habia una segunda lista con las claves del video, y se desincronizo del alcance:
un dato con dos fuentes acaba con dos valores. Aqui la fuente es una.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    w: int
    h: int
    insets: Tuple[float, float, float, float]   # top, right, bottom, left (fraccion del lado menor)
    in_video: bool = True
    note: str = ""

    @property
    def aspect(self) -> float:
        return self.w / self.h

    def safe_box(self) -> Tuple[float, float, float, float]:
        m = min(self.w, self.h)
        t, r, b, l = (f * m for f in self.insets)
        return (l, t, self.w - l - r, self.h - t - b)


# En el video, y en este orden. El 4:5 va PRIMERO a proposito: es donde el resize
# por constraints da un resultado correcto. Se abre reconociendolo, y por eso la
# comparacion se sostiene cuando llega el leaderboard.
FORMATS: List[Format] = [
    Format("portrait_4x5", "Instagram 4:5",      1080, 1350, (.055, .055, .055, .055),
           note="constraints do well here; it survives the 1:1 crop of the profile"),
    Format("story_9x16", "Story / Reel 9:16",    1080, 1920, (.140, .060, .200, .060),
           note="the platform UI covers the top and the bottom"),
    Format("leader_728", "Leaderboard 728x90",    728,   90, (.100, .040, .100, .040),
           note="8:1; ningun recorte a sangre contiene la region focal"),
    Format("mpu_300",    "MPU 300x250",           300,  250, (.060, .060, .060, .060),
           note="no cabe todo; algo debe caer"),
    Format("feed_1x1",   "Instagram feed 1:1",   1080, 1080, (.060, .060, .060, .060),
           note="linea base de referencia"),

    # Fuera del video: filas de configuracion, prueba de "lienzo arbitrario".
    Format("half_300x600", "Half page 300x600",   300,  600, (.060, .060, .060, .060),
           in_video=False, note="vertical angosto"),
    Format("screen_hd",  "Pantalla de centro",   1920, 1080, (.050, .050, .050, .050),
           in_video=False, note="the white is recomputed, not stretched"),
    Format("print_dl",   "Print DL vertical",     991, 2098, (.070, .070, .070, .070),
           in_video=False, note="lienzo arbitrario; fuera del video"),
]

BY_KEY = {f.key: f for f in FORMATS}
VIDEO_ORDER = [f.key for f in FORMATS if f.in_video]

# Margen por defecto para un set de tamanos arbitrario: 6% del lado menor, por los
# cuatro lados. No hay insets de plataforma que declarar cuando el tamano viene de
# una hoja de especificaciones, asi que se usa uno simetrico y se dice cual es.
GENERIC_INSET = 0.060


def from_sizes(spec: str) -> List[Format]:
    """Convierte 'AxB,CxD,...' en filas de formato.

    Existe para poder correr un set de especificaciones ajeno sin tocar codigo ni
    esta tabla. Es la misma afirmacion de la arquitectura llevada al limite: un
    formato es una fila, y las filas pueden llegar de fuera.
    """
    out: List[Format] = []
    seen = set()
    for tok in spec.replace(";", ",").split(","):
        tok = tok.strip().lower().replace("×", "x")
        if not tok:
            continue
        try:
            w, h = (int(round(float(v))) for v in tok.split("x", 1))
        except ValueError:
            raise ValueError(f"tamano no reconocido: {tok!r}")
        if w < 16 or h < 16:
            raise ValueError(f"tamano demasiado pequeno: {w}x{h}")
        key = f"{w}x{h}"
        if key in seen:
            continue
        seen.add(key)
        i = GENERIC_INSET
        out.append(Format(key, f"{w}x{h}", w, h, (i, i, i, i), in_video=False,
                          note="size from an external spec sheet"))
    return out
