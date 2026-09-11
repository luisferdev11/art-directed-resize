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
    ("how-it-works.html", "How it works, how it scales",
     "architecture: today and in production, with the proposed parts marked"),
    ("evolution.html", "How it changed",
     "eight steps, each one a failure that was measured first"),
    ("whats-next.html", "What's next",
     "the plan to a product: infra, agent, scale, data and deployment"),
    ("writeup.html", "The write-up",
     "architecture notes on building with models"),
    ("meridian-quarter/face-off.html", "Head to head",
     "constraints against art-directed decisions, 8 pairs"),
    ("meridian-quarter/index.html", "Campaign · art-directed",
     "this engine on the SVG master, 8 formats"),
    ("meridian-quarter/constraints/index.html", "Campaign · constraints",
     "the rival mechanism, on its own"),
    ("meridian-flat/index.html", "From a flat JPEG",
     "no layers, no nodes: a model reads the scene"),
    ("swap/index.html", "The photograph swap",
     "same master, three photographs: which mechanism moves, and which does not"),
    ("rollout/index.html", "One folder per centre",
     "three centres, three self-contained folders"),
    ("generic66/spec.html", "The 66 sizes",
     "a whole media spec, with no templates authored"),
    ("generic66/index.html", "The 66 · contact sheet",
     "all 66 pieces with their triage"),
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
           f'&larr; index</a>']
    for rel, label, _ in SHEETS:
        p = os.path.join(root, rel)
        if not os.path.exists(p) and rel != current:
            continue
        if rel == current:
            out.append(f"<span>{label}</span>")
        else:
            out.append(f'<a href="{os.path.relpath(p, here)}">{label}</a>')
    return '<nav class="nav">' + "".join(out) + "</nav>"
