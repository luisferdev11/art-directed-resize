"""El modelo Scene: representacion agnostica del formato.

Este es el UNICO seam del sistema. SVG es un adaptador en los dos extremos.
Es lo que permite afirmar con honestidad que IDML, PSD y Figma serian mas
adaptadores contra el mismo nucleo, sin reescribir la logica de decision.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

Rect = Tuple[float, float, float, float]      # x, y, w, h

ROLES = ("headline", "subhead", "support", "legal")


@dataclass
class TextBlock:
    """Un bloque de copy con un rol. Las lineas son como venian en el master;
    el solver puede re-partirlas."""
    role: str
    words: List[str]
    size: float                  # cuerpo en el master
    weight: int
    fill: str
    tracking: float
    rect: Rect                   # bbox en coordenadas del master
    n_lines_master: int = 1

    @property
    def text(self) -> str:
        return " ".join(self.words)


@dataclass
class Lockup:
    """El logo. Escala uniforme, nunca se recorta.

    Se guardan por separado la MARCA (geometria vectorial) y el WORDMARK (texto),
    para poder degradar a marca sola cuando el wordmark no alcanza su piso de
    legibilidad. Es practica normal de sistemas de marca.
    """
    rect: Rect
    nodes: List[Any] = field(default_factory=list)        # todos los elementos lxml
    mark_nodes: List[Any] = field(default_factory=list)   # solo geometria
    # Variante clara YA construida. El camino SVG la deriva recoloreando el vector
    # en el emisor; un lockup que viene de pixeles no se puede recolorear asi, y
    # entonces el adaptador de entrada entrega las dos versiones hechas.
    light_nodes: List[Any] = field(default_factory=list)
    light_mark_nodes: List[Any] = field(default_factory=list)
    mark_rect: Optional[Rect] = None                      # bbox de la marca sola
    wordmark_size: float = 0.0
    role: str = "logo"


@dataclass
class Photo:
    rect: Rect
    src_path: str                # ruta al pixel original, no el data URI
    px_w: int = 0
    px_h: int = 0


@dataclass
class Scene:
    width: float
    height: float
    photo: Optional[Photo] = None
    texts: List[TextBlock] = field(default_factory=list)
    lockup: Optional[Lockup] = None
    notes: List[str] = field(default_factory=list)    # trazas de la inferencia

    def by_role(self, role: str) -> Optional[TextBlock]:
        for t in self.texts:
            if t.role == role:
                return t
        return None

    @property
    def aspect(self) -> float:
        return self.width / self.height
