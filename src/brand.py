"""Marca ficticia del demo. Es la superficie de configuracion por marca.

MERIDIAN QUARTER es una marca INVENTADA para este demo. Cualquier parecido con un
centro existente es involuntario. Ver assets/LICENSES.md.
"""
from __future__ import annotations

FONT_DIR = "/usr/share/fonts/truetype/lato"
WEIGHTS = {  # nombre logico -> (archivo, font-weight CSS)
    "hairline": ("Lato-Hairline.ttf", 100),
    "light":    ("Lato-Light.ttf", 300),
    "regular":  ("Lato-Regular.ttf", 400),
    "bold":     ("Lato-Bold.ttf", 700),
    "black":    ("Lato-Black.ttf", 900),
}

PALETTE = {
    "ink":    "#0E2A26",   # verde-negro profundo, armoniza con el vidrio del domo
    "paper":  "#F4F1EA",   # blanco cálido
    "accent": "#E4572E",   # naranja
    "light":  "#FFFFFF",
}

# Escala tipografica de la marca. El solver ELIGE de esta escala, no inventa tamanos:
# es lo que hace que el output se lea disenado en lugar de ajustado a la fuerza.
TYPE_SCALE = [10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 56, 64, 72, 88, 104, 128]

# Piso de legibilidad por rol, en px de altura de lienzo de referencia (1000px).
# Debajo de esto el elemento se degrada o cae; nunca se encoge en silencio.
MIN_SIZE = {"headline": 18.0, "subhead": 13.0, "support": 11.0, "legal": 9.0}

# Reglas duras de marca.
LOGO_MIN_PX = 56.0        # ancho minimo del lockup completo
LOGO_CLEAR = 0.5          # clear-space = 0.5x la altura del lockup
# Un minimo de ANCHO no basta: a 56px el wordmark del lockup salia a 3.8px, ilegible.
# Cuando el wordmark no alcanza su piso, el lockup degrada a MARCA SOLA, que es lo
# que hacen los sistemas de marca reales a tamano reducido.
LOGO_WORDMARK_MIN = 7.5   # piso de legibilidad del wordmark dentro del lockup
LOGO_MARK_MIN_PX = 20.0   # ancho minimo de la marca sola
SAFE_FRACTION = 0.045     # margen base, fraccion de la dimension menor

# LA ESCALERA DE DEGRADACION. Este dict es la superficie de configuracion por marca:
# en el producto seria un YAML por marca, aqui es una lista ordenada y se muestra tal cual.
#
# Se aplica en orden hasta que el candidato cumple las restricciones duras. Nunca se
# comprime al piso en silencio: si no cabe, algo CAE y se registra por que.
#
# Dos pasos que NO estan aqui a proposito: bajar un peldano de la escala tipografica y
# re-partir en mas lineas ya los resuelve el ajuste en forma cerrada de text.py, que
# prueba varios anchos y elige el mayor cuerpo que cabe. Listarlos seria decorativo.
DEGRADE_LADDER = [
    ("none",            {}),
    ("tighten_leading", {"leading": 1.05}),
    ("weight_for_size", {"leading": 1.05, "light_secondary": True}),
    ("drop_legal",      {"leading": 1.05, "light_secondary": True, "legal": False}),
    ("drop_support",    {"leading": 1.05, "light_secondary": True, "legal": False,
                         "roles": ("headline", "subhead")}),
    ("drop_subhead",    {"leading": 1.05, "light_secondary": True, "legal": False,
                         "roles": ("headline",)}),
]

# Cuando el contraste de TAMANO entre titular y subtitulo cae por debajo de esta
# fraccion del que tenia el master, la jerarquia se re-expresa en PESO. El piso de
# legibilidad capa el ratio de cuerpos, y Lato va de Hairline a Black.
HIERARCHY_MIN_RATIO = 0.80
LIGHT_WEIGHT = 300

# Hipotesis de foto degradada a panel, para aspectos donde no cabe a sangre.
PANEL_MAX_W = 0.46        # fraccion del lienzo que ocupa el panel de foto
PANEL_TARGET_ASPECT = 3.0  # aspecto sano maximo para el panel
