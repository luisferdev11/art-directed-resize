"""Navegacion entre los artefactos de una campana.

Existe porque sin ella el trabajo no se ve. La hoja de contactos del motor no
cambia cuando se anade un segundo backend ni una segunda puerta de entrada -y no
debe cambiar, porque su salida es la misma-, asi que quien abre ese archivo
concluye que no paso nada. Un artefacto que no se enlaza no existe.
"""
from __future__ import annotations
import os
from typing import List, Tuple

# Cada entrega, relativa a out/spring-campaign/. El orden es el del argumento:
# primero el cara a cara, que es la pieza central.
SHEETS: List[Tuple[str, str, str]] = [
    ("how-it-works.html", "Como funciona y como escala",
     "arquitectura: hoy y a produccion, con lo propuesto marcado"),
    ("evolution.html", "Como cambio",
     "ocho pasos, cada uno una falla que se midio primero"),
    ("whats-next.html", "Que sigue",
     "el plan a producto: infra, agente, escala, datos y despliegue"),
    ("writeup.html", "El writeup",
     "notas de arquitectura sobre construir con modelos"),
    ("meridian-quarter/face-off.html", "Cara a cara",
     "constraints contra decision desde el arte, 8 pares"),
    ("meridian-quarter/index.html", "Campana · desde el arte",
     "nuestro motor sobre el master SVG, 8 formatos"),
    ("meridian-quarter/constraints/index.html", "Campana · constraints",
     "el mecanismo rival, en solitario"),
    ("meridian-flat/index.html", "Desde un JPEG plano",
     "sin capas ni nodos: la escena la lee un modelo"),
    ("swap/index.html", "La prueba de las fotos",
     "mismo master, tres fotos: quien mueve el layout y quien no"),
    ("rollout/index.html", "Un archivo por centre",
     "tres centres, tres carpetas autocontenidas"),
    ("generic66/spec.html", "Los 66 tamanos",
     "un set de medios entero, sin autorear plantillas"),
    ("generic66/index.html", "Los 66 · hoja de contactos",
     "las 66 piezas con su triage"),
]

CSS = """
 .nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 26px;padding:0 0 18px;
   border-bottom:1px solid var(--line)}
 .nav a,.nav span{font-size:12.5px;padding:6px 12px;border-radius:99px;
   border:1px solid var(--line);background:#fff;text-decoration:none;line-height:1.2}
 .nav span{background:var(--ink);color:var(--pap);border-color:var(--ink);font-weight:600}
 .nav a:hover{border-color:var(--ink)}
"""


def _root(d: str) -> str:
    """La raiz de campanas, out/spring-campaign, subiendo desde el directorio dado."""
    d = os.path.abspath(d)
    while os.path.basename(d) not in ("spring-campaign", "") and os.path.dirname(d) != d:
        d = os.path.dirname(d)
    return d


def render(d: str, current: str) -> str:
    """Barra de navegacion. `current` es la ruta relativa a la raiz de campanas."""
    root = _root(d)
    here = os.path.abspath(d)
    out = [f'<a href="{os.path.relpath(os.path.join(root, "index.html"), here)}">'
           f'&larr; indice</a>']
    for rel, label, _ in SHEETS:
        p = os.path.join(root, rel)
        if not os.path.exists(p) and rel != current:
            continue
        if rel == current:
            out.append(f"<span>{label}</span>")
        else:
            out.append(f'<a href="{os.path.relpath(p, here)}">{label}</a>')
    return '<nav class="nav">' + "".join(out) + "</nav>"
