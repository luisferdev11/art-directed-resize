"""Observabilidad de la parte que no es determinista.

QUE SE TRAZA Y POR QUE. El motor de layout no se traza: es determinista, no cuesta
dinero y su explicacion ya viaja en el manifest de cada pieza. Lo que si necesita
instrumentacion es el unico paso que no tiene ninguna de esas tres propiedades: la
llamada al modelo. Ahi se registran proveedor, modelo, latencia, si el esquema
valido, y CADA INTENTO FALLIDO antes del que respondio.

Ese ultimo punto es el que importa. Un fallback que funciona en silencio convierte
una degradacion de servicio en un misterio de calidad tres semanas despues, y la
tasa de fallback es la senal mas temprana que existe de que el proveedor principal
se esta cayendo. Si el intento fallido no se registra, esa senal no existe.

DEGRADACION. Si falta el SDK, faltan las claves o el servidor no responde, el
pipeline corre EXACTAMENTE IGUAL y lo dice una vez en el log. La traza es
instrumentacion, no una dependencia del camino critico: un sistema que se cae
porque su observabilidad se cayo es peor que uno sin observabilidad.
"""
from __future__ import annotations
import os
from typing import Any, Dict, Optional

import secrets_env as S

_client = None
_estado = None


def client():
    """Cliente Langfuse, o None. Se resuelve una vez y se recuerda el motivo."""
    global _client, _estado
    if _estado is not None:
        return _client
    pk, sk = S.get("LANGFUSE_PUBLIC_KEY"), S.get("LANGFUSE_SECRET_KEY")
    host = S.get("LANGFUSE_BASE_URL") or "http://localhost:3000"
    if not (pk and sk):
        _estado = "sin claves en .env; el pipeline corre sin trazas"
        return None
    try:
        from langfuse import Langfuse
        _client = Langfuse(public_key=pk, secret_key=sk, host=host, timeout=8)
        if not _client.auth_check():
            _client, _estado = None, f"Langfuse en {host} rechazo las claves"
        else:
            _estado = f"trazando a {host}"
    except Exception as e:  # SDK ausente, host caido, lo que sea
        _client, _estado = None, f"{type(e).__name__}: {str(e)[:90]}"
    return _client


def estado() -> str:
    client()
    return _estado or "sin resolver"


class Span:
    """Un span, o nada en absoluto. Se usa como context manager y nunca lanza.

    Si no hay cliente devuelve un objeto que acepta las mismas llamadas y las tira,
    para que el codigo instrumentado se lea igual con y sin observabilidad.
    """

    def __init__(self, name: str, kind: str = "span", **meta):
        self.name, self.kind, self.meta = name, kind, meta
        self._span = None
        self._ctx = None

    def __enter__(self):
        c = client()
        if c is None:
            return self
        try:
            fn = c.start_as_current_generation if self.kind == "generation" \
                else c.start_as_current_span
            self._ctx = fn(name=self.name, **self.meta)
            self._span = self._ctx.__enter__()
        except Exception:
            self._span, self._ctx = None, None
        return self

    def update(self, **kw):
        if self._span is not None:
            try:
                self._span.update(**kw)
            except Exception:
                pass
        return self

    def event(self, name: str, **kw):
        """Un intento fallido de la cadena tambien es un hecho que hay que guardar."""
        if self._span is not None:
            try:
                self._span.create_event(name=name, **kw)
            except Exception:
                pass
        return self

    def score(self, name: str, value, comment: str = ""):
        """Puntua LA TRAZA en curso, no un score suelto.

        `create_score` sin trace_id devuelve 400: un score que no cuelga de nada no
        se puede leer despues. Se puntua desde el span, que ya sabe a que traza
        pertenece.
        """
        if self._span is not None:
            try:
                self._span.score_trace(name=name, value=value, comment=comment,
                                       data_type="NUMERIC")
                return self
            except Exception:
                pass
        c = client()
        if c is not None:
            try:
                c.score_current_trace(name=name, value=value, comment=comment)
            except Exception:
                pass
        return self

    def __exit__(self, *exc):
        if self._ctx is not None:
            try:
                self._ctx.__exit__(*exc)
            except Exception:
                pass
        return False


def trace_meta(**kw) -> None:
    """Etiqueta la traza en curso: de que campana y de que master viene."""
    c = client()
    if c is None:
        return
    try:
        c.update_current_trace(**kw)
    except Exception:
        pass


def flush() -> None:
    c = client()
    if c is not None:
        try:
            c.flush()
        except Exception:
            pass
