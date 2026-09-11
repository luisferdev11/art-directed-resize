#!/usr/bin/env python3
"""Audita las CIFRAS del guion contra las salidas en disco.

`guion.md` dice numeros en voz alta sobre una pantalla donde el cliente puede
contarlos. Ya pasó una vez que el guion afirmaba una degradacion que el codigo no
hacia (`pendientes.md` §7 fila 1), y la leccion escrita fue "auditar contra la
salida, no contra la memoria". Esto convierte esa leccion en un comando.

Encontrado con este script en su primera pasada: el guion decia "treinta y siete de
los sesenta y seis no necesitan nada" y el triage daba 38.

QUE NO HACE, y por eso no sustituye la lectura:
  · no juzga si una frase induce a error, solo si un numero cuadra;
  · no mide el tiempo de ejecucion ni la duracion del video;
  · no verifica lo que solo existe en `docs/how-it-works.html` o en el README.

Uso:  python3 tools/audit_guion.py
Sale 1 si alguna cifra no cuadra.
"""
from __future__ import annotations
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "src"))

GUION = os.path.join(ROOT, "guion.md")
CAMPANA = os.path.join(ROOT, "out", "spring-campaign")

# Numeros escritos con letra, que es como se dicen en el video. Solo los que el
# guion usa: inventar un parser general seria mas codigo que casos.
PALABRAS = {
    "cero": 0, "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "treinta y cinco": 35, "treinta y siete": 37, "treinta y ocho": 38,
    "sesenta y seis": 66, "sesenta y cinco": 65,
}


def num(s: str):
    """Convierte '38', 'treinta y ocho' o 'sesenta y seis' a int, o None."""
    t = " ".join(s.lower().split())
    if t in PALABRAS:
        return PALABRAS[t]
    try:
        return int(t)
    except ValueError:
        return None


def manifest(sub: str):
    p = os.path.join(CAMPANA, sub, "manifest.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


# --------------------------------------------------------- verdades desde disco
def v_n_tamanos():
    m = manifest("generic66")
    return len(m["outputs"]) if m else None


def v_triage_ok():
    m = manifest("generic66")
    if not m:
        return None
    import contact_sheet as cs
    n = 0
    for o in m["outputs"]:
        r = cs.review(o)
        et = r[0] if isinstance(r, (list, tuple)) else r
        n += 1 if et == "OK" else 0
    return n


def v_bajo_72ppi():
    m = manifest("generic66")
    if not m:
        return None
    return sum(1 for o in m["outputs"] if o.get("effective_ppi", 1e9) < 72.0)


def v_decisiones_arte():
    """El '15' de 'quince de treinta y cinco decisiones', desde la pagina del swap.

    La pagina publica la tabla por decision -recorte 5 de 5, colores 3 de 5...- y no
    el total; el total solo sale por stdout de `swap_test.py`. Se suma la columna del
    arte, que es de donde sale el 15, en lugar de recalcular la comparacion aqui:
    duplicar esa logica seria una segunda fuente de verdad que puede derivar.
    """
    p = os.path.join(CAMPANA, "swap", "index.html")
    if not os.path.exists(p):
        return None
    h = open(p).read()
    i = h.find("Layout decisions redone")
    if i < 0:
        return None
    tabla = h[i:h.find("</table>", i)]
    filas = re.findall(r'<td>[^<]+</td><td class="n[^"]*">(\d+) de \d+</td>', tabla)
    return sum(int(x) for x in filas) if filas else None


def v_aciertos_tamano():
    p = os.path.join(ROOT, "out", "_golden", "golden.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p))["aciertos_por_tamano"]


def v_aciertos_modelo():
    p = os.path.join(ROOT, "out", "_golden", "golden.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p))["aciertos_por_modelo"]


def v_sin_violaciones():
    """Formatos donde el mecanismo rival no comete ninguna violacion propia."""
    m = manifest(os.path.join("meridian-quarter", "constraints"))
    if not m:
        return None
    return sum(1 for o in m["outputs"] if not o.get("violations"))


# Cada regla: (nombre, regex sobre guion.md con UN grupo que captura el numero,
#              funcion que calcula la verdad, nota)
REGLAS = [
    ("el set de medios",
     r"(sesenta y seis|66) tamaños", v_n_tamanos,
     "outputs en el manifest de generic66"),
    ("los que no necesitan nada",
     r"(Treinta y siete|Treinta y ocho|\d+) de los sesenta y\s*\n?>?\s*seis no necesitan nada",
     v_triage_ok, "triage OK sobre los 66"),
    ("resolucion insuficiente",
     r"(Ocho|ocho|\d+) quedan bajo 72 ppi", v_bajo_72ppi,
     "effective_ppi < 72 en el manifest"),
    ("decisiones que se rehacen",
     r"rehace (quince|\d+) de treinta y cinco decisiones", v_decisiones_arte,
     "suma de la columna del arte en la tabla del swap"),
    ("los que salen igual de bien",
     r"(Tres|tres|\d+) de los ocho salen as[ií]", v_sin_violaciones,
     "formatos sin violaciones propias del mecanismo rival"),
]


def main() -> int:
    if not os.path.exists(GUION):
        print(f"no existe {GUION}")
        return 1
    g = open(GUION).read()

    print("=" * 72)
    print("  CIFRAS DEL GUION CONTRA LA SALIDA EN DISCO")
    print("=" * 72)
    fallos = 0
    for nombre, patron, verdad_fn, fuente in REGLAS:
        real = verdad_fn()
        m = re.search(patron, g, re.I)
        if real is None:
            print(f"  {nombre:32s} SIN SALIDA  falta {fuente}")
            fallos += 1
            continue
        if not m:
            print(f"  {nombre:32s} NO HALLADA  la frase cambio: revisala a mano")
            fallos += 1
            continue
        dicho = num(m.group(1))
        if dicho is None:
            print(f"  {nombre:32s} ILEGIBLE    '{m.group(1)}'")
            fallos += 1
        elif dicho != real:
            print(f"  {nombre:32s} NO CUADRA   el guion dice {dicho}, "
                  f"la salida dice {real}  ({fuente})")
            fallos += 1
        else:
            print(f"  {nombre:32s} ok          {real}  ({fuente})")

    # El golden no se dice en el guion, pero se dice en la portada y en P5.
    print()
    print(f"  (referencia, no esta en el guion: asignacion de rol "
          f"{v_aciertos_tamano()}/12 por tamano, {v_aciertos_modelo()}/12 leyendo)")

    print()
    print("=" * 72)
    if fallos:
        print(f"  {fallos} cifra(s) que no cuadran. NO GRABAR hasta arreglarlas.")
        print("=" * 72)
        return 1
    print("  VERDE: cada cifra del guion coincide con una salida en disco.")
    print()
    print("  LO QUE ESTO NO APRUEBA:")
    print("    · que las frases no induzcan a error, solo que los numeros cuadren")
    print("    · el cronometro por debajo de 90 s en una sola toma")
    print("    · que una persona no tecnica lo vea sin contexto y lo explique")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
