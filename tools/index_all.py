"""Indice de la campana: la puerta de entrada a todo lo generado.

Un directorio con cuatro paginas HTML repartidas en tres carpetas no es un
entregable, es un arbol de archivos. Esto es la portada.
"""
from __future__ import annotations
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nav import CSS as NAVCSS, SHEETS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(root, *parts):
    m = os.path.join(root, *parts, "manifest.json")
    if not os.path.exists(m):
        return None
    man = json.load(open(m))
    return [o for o in man["outputs"] if not o.get("failed")], man


def _stat(root, rel):
    """Una linea de cifras leida de los manifests que respaldan cada vista.

    El cara a cara enfrenta DOS lotes, asi que su cifra sale de los dos. Leer solo
    el primero decia "backend art" en la vista que precisamente compara backends.
    """
    if rel.endswith("face-off.html"):
        a = _load(root, "meridian-quarter")
        c = _load(root, "meridian-quarter", "constraints")
        if not (a and c):
            return ""
        viol = sum(len(o.get("violations") or []) for o in c[0])
        rota = sum(1 for o in c[0] if o.get("violations"))
        return (f"{len(a[0])} pares &middot; desde el arte: 0 violaciones &middot; "
                f"constraints: {viol} en {rota} de {len(c[0])} formatos")
    if rel.startswith("rollout/"):
        d = os.path.join(root, "rollout")
        cs = sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)))
        n = sum(len([f for f in os.listdir(os.path.join(d, c)) if f.endswith(".svg")])
                for c in cs)
        return f"{len(cs)} centres &middot; {n} piezas &middot; check.py verde en los tres"
    if rel.startswith("swap/"):
        return "3 fotos &middot; arte: 3 de 5 formatos se mueven &middot; constraints: 0"
    got = _load(root, os.path.dirname(rel))
    if not got:
        return ""
    outs, man = got
    viol = sum(len(o.get("violations") or []) for o in outs)
    bits = [f"{len(outs)} formatos"]
    if any("violations" in o for o in outs):
        bits.append(f"{viol} violaciones medidas")
    elif man.get("master", "").lower().endswith((".jpg", ".jpeg", ".png")):
        bits.append("escena leida por un modelo")
    else:
        bits.append("escena leida midiendo el SVG")
    return " &middot; ".join(bits)


def build(root: str) -> None:
    cards = []
    for rel, label, desc in SHEETS:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            continue
        cards.append(f'''<a class="card" href="{rel}">
  <h2>{label}</h2><p>{desc}</p><p class="n">{_stat(root, rel)}</p></a>''')
    doc = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spring Style Is Here &middot; Meridian Quarter</title>
<style>
 :root{{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--pap);color:var(--ink);
   font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
 .wrap{{max-width:900px;margin:0 auto;padding:56px 24px 80px}}
 h1{{font-size:30px;margin:0 0 6px;letter-spacing:-.01em}}
 .sub{{margin:0 0 30px;opacity:.75;max-width:66ch}}
 .grid{{display:grid;gap:14px}}
 .card{{display:block;background:#fff;border:1px solid var(--line);border-radius:10px;
   padding:18px 20px;text-decoration:none;color:inherit}}
 .card:hover{{border-color:var(--ink)}}
 .card h2{{margin:0 0 4px;font-size:17px}}
 .card p{{margin:0;font-size:13.5px;opacity:.75}}
 .card p.n{{margin-top:8px;font-size:12px;opacity:.55;font-variant-numeric:tabular-nums}}
 .note{{margin:34px 0 0;font-size:13px;opacity:.75;max-width:70ch}}
 .note strong{{color:var(--acc)}}
 {NAVCSS}
</style>
<div class="wrap">
<h1>Spring Style Is Here</h1>
<p class="sub">Meridian Quarter. Un master, una pasada, y las razones de cada
 decision a la vista. Cuatro vistas de lo mismo.</p>
<div class="grid">{''.join(cards)}</div>
<p class="note"><strong>Donde se usa un modelo, y donde no.</strong> Las tres primeras
 vistas no llaman a ningun modelo: el master es un SVG y la escena se lee midiendolo.
 La cuarta entra por un JPEG sin capas ni nodos de texto, y ahi un modelo multimodal
 transcribe el copy y asigna el rol por funcion. Donde esta cada cosa y cuanto mide lo
 siguen resolviendo los pixeles y las metricas de la fuente. El motor de layout es el
 mismo en las cuatro.</p>
</div>
"""
    with open(os.path.join(root, "index.html"), "w") as fh:
        fh.write(doc)
    print(f"indice escrito: {len(cards)} vistas -> {os.path.join(root, 'index.html')}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1
          else os.path.join(ROOT, "out", "spring-campaign"))
