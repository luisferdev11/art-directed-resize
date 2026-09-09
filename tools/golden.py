"""Golden set: ¿acierta el rol quien lo deduce, frente a quien lo ordena por tamano?

QUE SE MIDE. La asignacion de rol sobre la misma pieza, por dos caminos:

  ordenar por tamano   el camino determinista de `parse_svg.py`: los bloques se
                       ordenan por cuerpo descendente y se reparten los cuatro
                       roles en ese orden. Necesita el SVG con sus nodos de texto.
  leer la pieza        `semantic.py`: un modelo multimodal mira el JPEG plano, sin
                       capas ni nodos, y asigna el rol por funcion comunicativa.

LA VERDAD DE TERRENO son los `data-name` de las capas del master. Los pone una
persona al disenar, y son exactamente la etiqueta manual que pide un golden set.
El sistema tiene PROHIBIDO leerlos -es la regla dura de `parse_svg.py`- y este
banco de pruebas si puede: para eso es un banco de pruebas.

N=3, Y SE DECLARA. Tres masters no sostienen una comparacion de modelos ni una
cifra de producto. Sostienen una sola afirmacion: que existe una clase de pieza
donde ordenar por tamano se equivoca por construccion y leer la pieza no. Esa
clase se construye a proposito en la variante B, porque es real: un aviso legal
fijado en cuerpo grande aparece en promociones reguladas continuamente.
"""
from __future__ import annotations
import json, os, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lxml import etree
from PIL import Image

import parse_svg
import semantic

SVG = "http://www.w3.org/2000/svg"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(ROOT, "tools", "shot.sh")
WORK = os.path.join(ROOT, "out", "_golden")
NAME2ROLE = {"headline": "headline", "subhead": "subhead",
             "campaign dates": "support", "legal": "legal"}


def truth(path):
    """Rol por bloque, leido de los nombres de capa. Solo el banco los lee."""
    root = etree.parse(path).getroot()
    out = {}
    for g in root.findall("{%s}g" % SVG):
        role = NAME2ROLE.get((g.get("data-name") or "").lower())
        if not role:
            continue
        s = " ".join(" ".join((t.text or "").split())
                     for t in g.findall("{%s}text" % SVG)).strip()
        if s:
            out[role] = s
    return out


def variants():
    """Tres masters. El primero es el real; los otros dos se derivan de el, y cada
    derivacion se declara aqui para que nadie tenga que adivinar que cambio."""
    os.makedirs(WORK, exist_ok=True)
    base = os.path.join(ROOT, "assets", "master.svg")
    made = [("A · master real", base,
             "jerarquia convencional: 92 / 30 / 20 / 13 px")]

    # B: el aviso legal en cuerpo grande y el dato operativo en cuerpo pequeno.
    # Ordenar por tamano da 92 > 34 > 30 > 12 y reparte headline, subhead, support,
    # legal en ese orden: acierta el titular y falla los otros tres POR DISENO.
    root = etree.parse(base).getroot()
    for g in root.findall("{%s}g" % SVG):
        n = (g.get("data-name") or "").lower()
        if n == "legal":
            for t in g.findall("{%s}text" % SVG):
                t.set("font-size", "34")
        elif n == "campaign dates":
            for t in g.findall("{%s}text" % SVG):
                t.set("font-size", "12")
    pb = os.path.join(WORK, "master-b.svg")
    open(pb, "wb").write(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    made.append(("B · legal en cuerpo grande", pb,
                 "legal a 34px y support a 12px: el orden por tamano queda invertido"))

    # C: el mismo contenido con el lockup al otro lado. No rompe el orden por
    # tamano; comprueba que leer la pieza no depende de donde esten las cosas.
    root = etree.parse(base).getroot()
    for g in root.findall("{%s}g" % SVG):
        if (g.get("data-name") or "").lower() == "logo":
            g.set("transform", "translate(-729,1140)")
    pc = os.path.join(WORK, "master-c.svg")
    open(pc, "wb").write(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    made.append(("C · lockup abajo a la izquierda", pc,
                 "mismo tipo, el lockup cambia de esquina"))
    return made


def flatten(svg_path, key):
    png = os.path.join(WORK, key + ".png")
    jpg = os.path.join(WORK, key + ".jpg")
    subprocess.run([SHOT, svg_path, png, "1080", "1350"], check=True,
                   capture_output=True, text=True)
    Image.open(png).convert("RGB").save(jpg, "JPEG", quality=92, optimize=True)
    os.remove(png)
    return jpg


def norm(s):
    return " ".join((s or "").lower().split())


def main():
    rows, tot = [], {"size": [0, 0], "model": [0, 0]}
    for label, svg, note in variants():
        key = label.split(" ")[0].lower()
        gt = truth(svg)
        # camino 1: ordenar por tamano, sobre el SVG con todos sus nodos
        by_size = {b.role: b.text for b in parse_svg.parse(svg, WORK).texts}
        # camino 2: leer el JPEG plano
        jpg = flatten(svg, key)
        sc = semantic.parse_raster(jpg, WORK)
        by_model = {b.role: b.text for b in sc.texts}
        prov = next((n for n in sc.notes if "escena semantica leida por" in n), "")

        r = {"label": label, "note": note, "roles": {}}
        for role, want in sorted(gt.items()):
            a = norm(by_size.get(role, "")) == norm(want)
            b = norm(by_model.get(role, "")) == norm(want)
            tot["size"][0] += a; tot["size"][1] += 1
            tot["model"][0] += b; tot["model"][1] += 1
            r["roles"][role] = {"esperado": want, "por_tamano": by_size.get(role, "-"),
                                "por_modelo": by_model.get(role, "-"),
                                "acierta_tamano": a, "acierta_modelo": b}
        r["proveedor"] = prov
        rows.append(r)

        print(f"\n{label}  ({note})")
        print(f"  {'rol':10} {'tamano':7} {'modelo':7}  esperado")
        for role, v in r["roles"].items():
            print(f"  {role:10} {'ok' if v['acierta_tamano'] else 'FALLA':7} "
                  f"{'ok' if v['acierta_modelo'] else 'FALLA':7}  {v['esperado'][:46]!r}")

    s, m = tot["size"], tot["model"]
    print(f"\nN={len(rows)} masters, {s[1]} asignaciones de rol")
    print(f"  ordenar por tamano : {s[0]}/{s[1]}")
    print(f"  leer la pieza      : {m[0]}/{m[1]}")
    print("\nN=3 no sostiene una comparacion de modelos. Sostiene que la clase de "
          "pieza\nde la variante B existe y que ordenar por tamano falla en ella por "
          "construccion.")
    out = os.path.join(WORK, "golden.json")
    json.dump({"n_masters": len(rows), "n_asignaciones": s[1],
               "aciertos_por_tamano": s[0], "aciertos_por_modelo": m[0],
               "detalle": rows}, open(out, "w"), indent=2, ensure_ascii=False)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
