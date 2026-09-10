"""Carga de credenciales desde .env, sin dependencias.

Las claves NUNCA se pegan en codigo, ni en el manifest, ni en el log. `.env` esta
en .gitignore. Este archivo es un artefacto publico: no se usan credenciales del
empleador bajo ninguna circunstancia.
"""
from __future__ import annotations
import os
from typing import Optional

_LOADED = False


def load(path: str = ".env") -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def get(name: str) -> Optional[str]:
    load()
    v = os.environ.get(name) or None
    return v


def redact(s: str) -> str:
    """Para logs: deja ver que HAY clave, y nada mas.

    La version anterior devolvia `{s[:4]}...{s[-2:]} ({len(s)} chars)`. Eso son seis
    caracteres de la clave y su longitud exacta, y esas notas viajan al manifest y de
    ahi al sitio publicado: el fragmento quedo en cuatro archivos y en todo el
    historial del repo. El riesgo practico de seis de treinta y dos caracteres es
    bajo; el problema es que el docstring de este modulo promete que las claves nunca
    se pegan en el manifest, y este helper era quien las pegaba. No se filtra un
    prefijo "para poder depurar": si hay que distinguir dos claves, se nombra la
    variable de entorno, que no es secreta.
    """
    return "(clave configurada)" if s else "(sin clave)"
