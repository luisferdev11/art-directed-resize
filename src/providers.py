"""Adaptador multiproveedor con degradacion en cadena.

Un solo `complete_vision(prompt, image)` y detras una lista ordenada de proveedores.
Si el primero falla -por red, por cuota, por un 5xx o porque devuelve algo que no
valida-, se pasa al siguiente Y SE REGISTRA POR QUE. El registro no es decorativo:
un fallback silencioso convierte una degradacion de servicio en un misterio de
calidad tres semanas despues.

Por que `requests` y no los SDK de cada proveedor: DeepInfra y Groq exponen la forma
de chat-completions de OpenAI, asi que un solo camino de codigo cubre los dos y el
tercero es una funcion de veinte lineas. Tres SDK serian tres dependencias, tres
ciclos de deprecacion y ninguna capacidad extra.

CREDENCIALES: propias, cargadas de `.env`, que esta en .gitignore. Este repositorio
es publico. Jamas credenciales del empleador. Las claves se registran redactadas.
"""
from __future__ import annotations
import base64, json, mimetypes, os, time
from typing import Any, Dict, List, Optional, Tuple

import requests

import secrets_env as S
import trace as T

TIMEOUT = 120

# Orden de la cadena. El principal es open-weight y de costo bajo; los dos ultimos
# son techo de calidad y alternativa, no produccion.
CHAIN: List[Dict[str, Any]] = [
    {"name": "deepinfra", "key": "DEEPINFRA_API_KEY", "kind": "openai",
     "url": "https://api.deepinfra.com/v1/openai/chat/completions",
     "model": "Qwen/Qwen3-VL-235B-A22B-Instruct"},
    {"name": "deepinfra-30b", "key": "DEEPINFRA_API_KEY", "kind": "openai",
     "url": "https://api.deepinfra.com/v1/openai/chat/completions",
     "model": "Qwen/Qwen3-VL-30B-A3B-Instruct"},
    {"name": "groq", "key": "GROQ_API_KEY", "kind": "openai",
     "url": "https://api.groq.com/openai/v1/chat/completions",
     "model": "meta-llama/llama-4-scout-17b-16e-instruct"},
    {"name": "gemini", "key": "GEMINI_API_KEY", "kind": "gemini",
     "url": "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent",
     "model": "gemini-2.5-flash", "budgeted": True},
]

# Techo de gasto por sesion para el proveedor de pago. Sin esto, un bucle de
# reintentos sobre una imagen grande es una factura.
_spent_usd = 0.0
GEMINI_USD_PER_CALL = 0.004      # estimacion conservadora para una imagen + 2k tokens

# Tope de lo que se guarda en la traza. Una escena semantica cabe de sobra; el limite
# es contra un proveedor que devuelva basura larga.
TRACE_OUTPUT_MAX = 20000


def _data_uri(path: str) -> Tuple[str, str]:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as fh:
        return mime, base64.b64encode(fh.read()).decode("ascii")


def _mensajes(prompt: str, mime: str, b64: str):
    """El payload de chat, en la forma de OpenAI.

    Se construye UNA vez y sirve para dos cosas: es lo que se manda al proveedor, y
    es lo que se manda a la traza. Que sean el mismo objeto no es elegancia: es la
    unica forma de que la traza documente lo que de verdad se pregunto, en lugar de
    una descripcion de lo que se pregunto.
    """
    return [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}]


def _call_openai(p: Dict[str, Any], key: str, prompt: str, mime: str, b64: str) -> str:
    body = {"model": p["model"], "temperature": 0.0, "max_tokens": 2048,
            "messages": _mensajes(prompt, mime, b64)}
    r = requests.post(p["url"], headers={"Authorization": f"Bearer {key}"},
                      json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_gemini(p: Dict[str, Any], key: str, prompt: str, mime: str, b64: str) -> str:
    body = {"contents": [{"parts": [{"text": prompt},
                                    {"inline_data": {"mime_type": mime, "data": b64}}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2048}}
    r = requests.post(p["url"], headers={"x-goog-api-key": key},
                      json=body, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    return "".join(part.get("text", "")
                   for part in j["candidates"][0]["content"]["parts"])


def _budget_ok(p: Dict[str, Any], log: List[str]) -> bool:
    global _spent_usd
    if not p.get("budgeted"):
        return True
    cap = float(S.get("GEMINI_SESSION_BUDGET_USD") or 0.0)
    if _spent_usd + GEMINI_USD_PER_CALL > cap:
        log.append(f"{p['name']}: omitido, la llamada estimada en "
                   f"${GEMINI_USD_PER_CALL:.3f} superaria el tope de sesion "
                   f"de ${cap:.2f} (gastado ${_spent_usd:.3f})")
        return False
    _spent_usd += GEMINI_USD_PER_CALL
    return True


def complete_vision(prompt: str, image_path: str,
                    accept=None,
                    log: Optional[List[str]] = None) -> Tuple[Any, str, List[str]]:
    """Devuelve (resultado aceptado, nombre del proveedor, bitacora).

    `accept(texto_crudo) -> (valor, errores)` es la VALIDACION DEL ESQUEMA, y corre
    DENTRO de la cadena a proposito. Un proveedor que responde 200 con un JSON que
    no valida ha fallado igual que uno que devuelve 500, y debe disparar el mismo
    fallback. Validar despues del bucle desperdicia los proveedores restantes y
    convierte un problema recuperable en una caida.

    Resultado None significa que la cadena entera se agoto.
    """
    log = log if log is not None else []
    # Una sola codificacion para toda la cadena. Antes cada transporte leia y
    # codificaba el archivo otra vez, asi que un fallback pagaba el base64 dos veces.
    mime, b64 = _data_uri(image_path)
    intento = 0
    for p in CHAIN:
        intento += 1
        key = S.get(p["key"])
        if not key:
            log.append(f"{p['name']}: sin clave en .env, se salta")
            continue
        if not _budget_ok(p, log):
            continue
        t0 = time.time()
        # Un span por INTENTO, no por llamada. El intento que falla es justo el que
        # hay que poder contar: la tasa de fallback es la senal mas temprana de que
        # el proveedor principal se degrada, y no existe si el fallo no se registra.
        # LA TRAZA LLEVA LA PREGUNTA ENTERA: el prompt y la imagen.
        #
        # Antes llevaba `prompt_chars` y el nombre del archivo, que es una descripcion
        # de la pregunta y no la pregunta. Para depurar una decision del modelo hace
        # falta lo que se le mando, y el SDK de Langfuse reconoce la data URI y sube la
        # imagen a su media store en lugar de guardar el base64 en el registro.
        with T.Span(f"vision:{p['name']}", kind="generation",
                    model=p["model"],
                    input=_mensajes(prompt, mime, b64),
                    metadata={"provider": p["name"], "url": p["url"],
                              "attempt": intento,
                              "image": os.path.basename(image_path),
                              "prompt_chars": len(prompt),
                              "image_kb": round(len(b64) * 3 / 4 / 1024)}) as sp:
            try:
                fn = _call_openai if p["kind"] == "openai" else _call_gemini
                out = fn(p, key, prompt, mime, b64)
                if not (out or "").strip():
                    raise ValueError("empty response")
                if accept is not None:
                    value, errs = accept(out)
                    if value is None:
                        log.append(f"{p['name']} ({p['model']}): respondio en "
                                   f"{time.time()-t0:.1f}s pero el esquema NO VALIDA, se "
                                   f"pasa al siguiente. " + "; ".join(errs[:3]))
                        sp.update(level="WARNING",
                                  status_message="schema did not validate",
                                  metadata={"provider": p["name"], "attempt": intento,
                                            "result": "invalid_schema",
                                            "errors": errs[:3],
                                            "latency_s": round(time.time() - t0, 2)})
                        continue
                else:
                    value = out
                # Se nombra la VARIABLE DE ENTORNO, no la clave. Antes se registraba
                # un prefijo de la clave "para depurar" y ese fragmento acabo en el
                # sitio publicado. El nombre de la variable distingue proveedores igual
                # de bien y no es un secreto.
                log.append(f"{p['name']} ({p['model']}): ok en {time.time()-t0:.1f}s, "
                           f"clave de {p['key']} {S.redact(key)}")
                # La respuesta ENTERA, no su tamano. Guardar `len(out)` hacia la
                # traza inservible para lo unico que se necesita en Langfuse: ver que
                # devolvio el modelo cuando el esquema valido pero la escena salio mal.
                # Se acota por si un proveedor devuelve algo enorme.
                sp.update(output={"response": out[:TRACE_OUTPUT_MAX],
                                  "truncated": len(out) > TRACE_OUTPUT_MAX,
                                  "chars": len(out)},
                          metadata={"provider": p["name"], "attempt": intento,
                                    "result": "ok",
                                    "latency_s": round(time.time() - t0, 2)})
                T.trace_meta(metadata={"final_provider": p["name"],
                                       "final_model": p["model"],
                                       "attempts": intento})
                return value, p["name"], log
            except Exception as e:
                detail = str(e)
                if isinstance(e, requests.HTTPError) and e.response is not None:
                    detail = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                log.append(f"{p['name']} ({p['model']}): FALLO en {time.time()-t0:.1f}s, "
                           f"{type(e).__name__}. {detail[:220]}")
                sp.update(level="ERROR", status_message=f"{type(e).__name__}",
                          metadata={"provider": p["name"], "attempt": intento,
                                    "resultado": "fallo", "detalle": detail[:220],
                                    "latency_s": round(time.time() - t0, 2)})
    log.append("la cadena de proveedores se agoto sin una respuesta utilizable")
    return None, "", log
