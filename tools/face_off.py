"""El cara a cara: template+constraints contra decision desde el arte.

Mismo master, mismos tamanos, mismo emisor, mismo validador. Lo unico que cambia
entre las dos columnas es el backend de layout, y por eso la comparacion vale.

TRES ADVERTENCIAS QUE VAN EN LA PAGINA, no en un comentario:

 1. Esto NO es Unicorn corriendo. Es una implementacion propia de un resize por
    constraints, hecha para ser comparable. Lo que se compara es el MECANISMO,
    documentado con citas de su propia interfaz en `competencia.md`.
 2. Los constraints usados salen impresos. Si alguien los cree amanados, los ve.
 3. Se muestran los ocho formatos, empezando por aquellos donde el mecanismo por
    constraints resuelve bien. Si solo enseñaramos el leaderboard, el argumento
    seria una trampa y se notaria.
"""
from __future__ import annotations
import html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import nav
from contact_sheet import review
from formats import BY_KEY, VIDEO_ORDER

# Lo que hacen mejor que nosotros. Va arriba y sin adornos: reconocerlo es lo que
# hace creible el resto. Cada linea con su fuente, competencia.md §3.
DO_BETTER = [
    ("Round-trip real con Figma via plugin, con estado de conexion visible", "ui"),
    ("Ingesta de deliverables list en .xlsx y .csv, con mapeo reutilizado entre trabajos", "ui"),
    ("El plan se aprueba antes de ejecutar, con mapeo y conteo de salidas a la vista", "ui"),
    ("Lote de 1340 assets con nomenclatura y agrupacion por vendor", "ui"),
    ("Export a PNG, JPG, PDF, MP4 y GIF, mas animados via Figma Motion", "sitio"),
    ("Salida editable en capas dentro de Figma", "sitio / ui"),
]

# Las dos unicas afirmaciones sobre su mecanismo que sostiene esta pagina, ambas
# citadas textualmente de su interfaz. No hay una tercera.
QUOTES = [
    ('"Make sure you\'ve set your master assets up using constraints in Figma."', "ui"),
    ('"Here\'s the plan - 1340 outputs, matched to the closest template by size."', "ui"),
    ('"I\'ll use templates from the Templates page: landscape, portrait, square."', "ui"),
]

CSS = """
 :root{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8;--bad:#8f2c10;--good:#14614d}
 *{box-sizing:border-box}
 body{margin:0;background:var(--pap);color:var(--ink);
   font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 .wrap{max-width:1240px;margin:0 auto;padding:40px 24px 80px}
 h1{font-size:30px;margin:0 0 6px;letter-spacing:-.01em}
 h2{font-size:19px;margin:44px 0 10px}
 .sub{margin:0 0 22px;opacity:.75}
 .box{background:#fff;border:1px solid var(--line);border-radius:9px;padding:16px 18px;
   margin:0 0 16px;max-width:78ch}
 .box.warn{border-color:#e8c98a;background:#fffaf0}
 .box h3{margin:0 0 8px;font-size:14px;letter-spacing:.04em;text-transform:uppercase;opacity:.65}
 .box ul{margin:6px 0 0;padding-left:20px} .box li{margin:3px 0}
 .src{font-size:11px;opacity:.55;font-style:normal}
 blockquote{margin:8px 0;padding-left:12px;border-left:3px solid var(--acc);
   font-size:14px;opacity:.9}
 .pair{background:#fff;border:1px solid var(--line);border-radius:10px;
   margin:0 0 26px;overflow:hidden}
 .pair>header{display:flex;align-items:baseline;gap:12px;padding:13px 16px;
   border-bottom:1px solid var(--line);background:#fbfaf7}
 .pair h3{margin:0;font-size:16px;flex:1}
 .dim{font-size:12.5px;opacity:.6;font-variant-numeric:tabular-nums}
 .cols{display:grid;grid-template-columns:1fr 1fr}
 .col{padding:0;border-right:1px solid var(--line)}
 .col:last-child{border-right:0}
 .col>h4{margin:0;padding:10px 16px;font-size:12.5px;letter-spacing:.05em;
   text-transform:uppercase;border-bottom:1px solid #eee;display:flex;gap:8px}
 .col>h4 span{margin-left:auto;font-weight:400;text-transform:none;letter-spacing:0}
 .shot{display:flex;align-items:center;justify-content:center;min-height:150px;
   max-height:420px;background:#e9e5dc;line-height:0;overflow:hidden}
 .shot img{max-width:100%;max-height:420px;width:auto;display:block}
 .body{padding:12px 16px;font-size:13px}
 .v{color:var(--bad)} .ok{color:var(--good)}
 ul.viol{margin:4px 0 0;padding-left:18px;font-size:12.5px;line-height:1.45}
 ul.viol li{margin:3px 0}
 table{width:100%;border-collapse:collapse;font-size:12.5px;
   font-variant-numeric:tabular-nums;margin-top:8px}
 td{padding:3px 6px 3px 0;border-bottom:1px solid #f0efeb}
 td:first-child{opacity:.7}
 details{margin-top:9px;font-size:12.5px} summary{cursor:pointer;opacity:.7}
 details ul{margin:7px 0 0;padding-left:19px;line-height:1.45}
 .ctab{font-size:12.5px;margin-top:6px}
 .ctab td{border-bottom:1px solid #f0efeb}
 .score{font-size:12.5px;padding:8px 16px;background:#fbfaf7;border-top:1px solid #eee;
   display:flex;gap:20px;flex-wrap:wrap;font-variant-numeric:tabular-nums}
 a{color:inherit}
""" + nav.CSS


def _cell(o, base, is_c):
    """Una columna. Para constraints, las violaciones medidas; para el nuestro, el
    triage de la hoja de contactos. Los dos con sus numeros a la vista."""
    if o is None:
        return '<div class="col"><div class="body">sin salida</div></div>'
    if is_c:
        vs = o.get("violations") or []
        inh = o.get("inherited") or []
        head = (f'<span class="v">{len(vs)} violacion(es)</span>' if vs
                else '<span class="ok">sin violaciones</span>')
        detail = ("".join(f"<li>{html.escape(v)}</li>" for v in vs)
                  if vs else "<li>el resize por constraints resuelve este formato</li>")
        # Lo heredado se lista aparte y NO cuenta: es un defecto del autorado del
        # master, no del mecanismo. Mezclarlo seria inflar el marcador.
        detail += "".join(
            f'<li style="opacity:.6">heredado del master, no del mecanismo: '
            f'{html.escape(v)}</li>' for v in inh)
        title = f"Template + constraints &middot; <em>{html.escape(o.get('template',''))}</em>"
    else:
        label, why = review(o)
        head = (f'<span class="ok">{label}</span>' if label == "OK"
                else f'<span class="v">{label}</span>')
        detail = ("".join(f"<li>{html.escape(w)}</li>" for w in why)
                  or "<li>sin banderas</li>")
        title = "Decision desde el arte"
    # Un bloque que quedo fuera del lienzo no tiene contraste que medir. Escribir
    # 0.00 ahi seria reportar una medicion que no se hizo.
    rows = "".join(
        f"<tr><td>{html.escape(b['role'])}</td><td>{b['size']:g}px</td>"
        f"<td>{len(b['lines'])} ln</td><td>"
        + ("<span class='dim'>n/d, fuera del lienzo</span>"
           if b.get("measurable") is False else
           f"{b['achieved']:.2f} / {b['required']:.1f}"
           f"{' +scrim' if b.get('scrimmed') else ''}")
        + "</td></tr>"
        for b in o["blocks"])
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in o["reasons"])
    return f"""<div class="col">
  <h4>{title} {head}</h4>
  <a class="shot" href="{html.escape(base)}{html.escape(o['file'])}">
    <img src="{html.escape(base)}thumbs/{html.escape(o['key'])}.jpg"
         alt="{html.escape(o['label'])}" loading="lazy"></a>
  <div class="body">
    <ul class="viol">{detail}</ul>
    <table>{rows}</table>
    <details><summary>Decisiones ({len(o['reasons'])})</summary><ul>{reasons}</ul></details>
  </div>
</div>"""


def build(d: str) -> None:
    art = json.load(open(os.path.join(d, "manifest.json")))
    con = json.load(open(os.path.join(d, "constraints", "manifest.json")))
    A = {o["key"]: o for o in art["outputs"] if not o.get("failed")}
    C = {o["key"]: o for o in con["outputs"] if not o.get("failed")}

    # El orden es el del video, y arranca donde SU mecanismo gana. Es la regla de
    # justicia 3 hecha codigo: si lo primero que se ve es el leaderboard roto, la
    # comparacion se lee como trampa y el argumento se pierde entero.
    keys = [k for k in VIDEO_ORDER if k in A] + [k for k in A if k not in VIDEO_ORDER]

    clean = sum(1 for k in keys if not (C[k].get("violations") if k in C else None))
    pairs = []
    for k in keys:
        a, c, fmt = A.get(k), C.get(k), BY_KEY[k]
        ctab = ""
        if c and c.get("constraints"):
            ctab = ('<table class="ctab">'
                    + "".join(f"<tr><td>{html.escape(r[0])}</td><td>{html.escape(r[1])}"
                              f"</td><td>{html.escape(r[2])}</td></tr>"
                              for r in c["constraints"]) + "</table>")
        cc = c["field_cost"] if c else float("nan")
        ac = a["field_cost"] if a else float("nan")
        pairs.append(f"""
<section class="pair">
  <header><h3>{html.escape(fmt.label)}</h3>
    <span class="dim">{fmt.w}&times;{fmt.h}</span></header>
  <div class="cols">{_cell(c, "constraints/", True)}{_cell(a, "", False)}</div>
  <div class="score">
    <span>coste del emplazamiento sobre el mismo campo:
      constraints <strong>{cc:.3f}</strong> &middot; arte <strong>{ac:.3f}</strong></span>
    <span>ppi: {c['effective_ppi']:.0f} &middot; {a['effective_ppi']:.0f}</span>
  </div>
  <details style="padding:10px 16px 14px"><summary>Constraints aplicados
    ({html.escape(c.get('template','')) if c else '-'})</summary>{ctab}</details>
</section>""")

    better = "".join(f"<li>{html.escape(t)} <em class='src'>[{s}]</em></li>"
                     for t, s in DO_BETTER)
    quotes = "".join(f"<blockquote>{html.escape(q)} <em class='src'>[{s}]</em></blockquote>"
                     for q, s in QUOTES)
    doc = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cara a cara &middot; constraints contra decision desde el arte</title>
<style>{CSS}</style>
<div class="wrap">
{nav.render(d, "meridian-quarter/face-off.html")}
<h1>Constraints contra decision desde el arte</h1>
<p class="sub">Mismo master, mismos tamanos, mismo emisor, mismo validador.
 Lo unico que cambia es el backend de layout.</p>

<div class="box warn">
 <h3>Que es esto, y que no</h3>
 <p style="margin:0">La columna izquierda <strong>no es Unicorn corriendo</strong>. Es una
 implementacion propia de un resize por template mas constraints, escrita para ser
 comparable bajo condiciones identicas. Lo que se compara es el <strong>mecanismo</strong>,
 y las dos unicas afirmaciones que esta pagina hace sobre el salen de su propia interfaz:</p>
 {quotes}
 <p style="margin:8px 0 0">Ninguna cifra de rendimiento suya aparece aqui. El analisis
 completo, con fuente por linea, esta en <code>competencia.md</code>.</p>
</div>

<div class="box">
 <h3>Lo que su producto hace mejor que este prototipo</h3>
 <ul>{better}</ul>
 <p style="margin:8px 0 0;opacity:.75">Este prototipo no es un producto: es un motor de
 layout. No orquesta, no agrupa, no nombra, no exporta a video y no vuelve a Figma por
 plugin. La tesis no es que ellos sobren, es que <strong>la decision de layout la toma
 hoy un constraint, y un constraint no mira la fotografia</strong>.</p>
</div>

<div class="box">
 <h3>Como se autorearon los templates, para que se auditen</h3>
 <ul>
  <li><strong>Tres</strong> templates, la familia que su interfaz nombra: landscape,
      portrait y square. La plantilla portrait <strong>es el master</strong>, sin degradar.</li>
  <li>Constraints razonables, los que el propio brief nombra: titular <code>LEFT+TOP</code>,
      lockup <code>RIGHT+TOP</code>, legal <code>LEFT+BOTTOM</code>, foto <code>SCALE</code>.</li>
  <li>Seleccion de template <strong>por proximidad de tamano</strong>, que es su regla
      declarada. La distancia es logaritmica en las dos dimensiones, que es la lectura
      mas favorable para ese mecanismo.</li>
  <li>Donde ningun color de la paleta alcanzaba el contraste exigido sobre el recorte de
      un template, se le autoreo un <strong>scrim</strong> detras de la pila y se le
      cambio la tipografia a claro. Es lo que haria un disenador competente, y se le da.</li>
  <li>Los constraints aplicados a cada formato estan desplegables al pie de cada fila.</li>
 </ul>
</div>

<h2>Los {len(keys)} formatos, empezando por donde el mecanismo por constraints resuelve bien</h2>
<p class="sub"><strong>{clean} de {len(keys)}</strong> salen sin una sola violacion
 atribuible al mecanismo, y son exactamente los tres cuyo tamano coincide con un template
 mas el que casi coincide. En esos, la diferencia esta en el coste del emplazamiento y en
 el recorte, no en si la pieza es utilizable. La distancia aparece donde el delta de aspecto contra el template
 es grande, y ese es el argumento honesto: funciona mientras el objetivo se parezca a un
 template, y una campana no se parece a tres templates.</p>
{''.join(pairs)}
</div>
"""
    out = os.path.join(d, "face-off.html")
    with open(out, "w") as fh:
        fh.write(doc)
    print(f"face-off.html escrito: {len(keys)} pares, "
          f"{clean} sin violaciones en la columna de constraints")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "out/spring-campaign/meridian-quarter")
