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
    """Para logs: deja ver que hay clave sin revelarla."""
    if not s:
        return "(sin clave)"
    return f"{s[:4]}...{s[-2:]} ({len(s)} chars)"
