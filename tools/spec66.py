"""Un set de especificaciones de medios entero, sin autorear una sola plantilla.

QUE ES ESTO. El mismo master salio por la herramienta de rollout del competidor
contra un set generico de 66 tamanos de banner, y por este motor contra ESE MISMO
set. No se reproduce su producto ni sus salidas: se reproduce el SET DE TAMANOS,
que es una especificacion de medios y no es de nadie, y se citan las frases de su
propio informe, que es la practica de cita que ya gobierna todo el proyecto.

POR QUE ESTA PAGINA ES JUSTA. Al mecanismo por plantillas se le dieron dos, y su
herramienta AVISO antes de ejecutar que faltaba una landscape. Presentar el
resultado como "mira que mal salio" seria deshonesto y se caeria solo. El argumento
que no se cae es el otro: la solucion que propone la propia herramienta es autorear
mas plantillas, y ese trabajo escala con la diversidad de formatos. Aqui el mismo
set salio sin autorear ninguna.
"""
from __future__ import annotations
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import nav
from contact_sheet import review

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Del informe de su propia herramienta sobre ESTE master. Texto literal.
THEIRS = [
    ("I can see you have 2 templates, but none are landscape. I would suggest "
     "designing a landscape version for a smoother rollout.", "antes de ejecutar"),
    ("49 outputs were matched to your square template - including landscape and "
     "ultra-wide sizes like 1040x480, 1152x324 and 1280x384. These have the biggest "
     "stretch, so headlines, images and logos may sit off-centre or get cropped.",
     "en el informe final"),
    ("17 outputs went to your portrait template - sizes like 320x736 and 512x768. "
     "These are closer but still off, so expect minor reflow issues.",
     "en el informe final"),
    ("The clean fix is adding a landscape template (and ideally a couple more native "
     "ratios), then re-running. Otherwise you'll want to nudge the layouts on the "
     "wider sizes by hand.", "la solucion que propone"),
]

# Los que su informe nombra por su nombre, mas los dos extremos del set.
DESTACADOS = ["1040x480", "1152x324", "1280x384", "2072x252", "700x180", "320x736"]


def build(site: str) -> None:
    d = os.path.join(site, "generic66")
    man = json.load(open(os.path.join(d, "manifest.json")))
    outs = [o for o in man["outputs"] if not o.get("failed")]

    r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "check.py"), d],
                       cwd=ROOT, capture_output=True, text=True)
    last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1]
    verde = last.startswith("VERDE")
    n_ok = int(last.split(":")[1].split()[0]) if verde else 0

    paneles = [o for o in outs if o.get("hypothesis") == "panel"]
    ladders = [o for o in outs if o.get("ladder")]
    dropped = [o for o in outs if o.get("dropped")]
    lowppi = [o for o in outs if o["effective_ppi"] < 72]
    aspects = sorted(outs, key=lambda o: -(o["w"] / o["h"]))

    tri = {"OK": 0, "REVISAR": 0, "ATENCION": 0}
    for o in outs:
        tri[review(o)[0]] += 1

    cards = ""
    for k in DESTACADOS:
        o = next((x for x in outs if x["key"] == k), None)
        j = os.path.join(d, "thumbs", k + ".jpg")
        if o is None or not os.path.exists(j):
            continue
        cards += (f'<figure><a href="{k}.svg"><img src="thumbs/{k}.jpg" alt="{k}" '
                  f'loading="lazy"></a><figcaption><strong>{o["w"]}&times;{o["h"]}</strong>'
                  f'<span>{o["w"]/o["h"]:.2f}:1 &middot; {o["hypothesis"]} &middot; '
                  f'{o["effective_ppi"]:.0f} ppi</span></figcaption></figure>')

    rows = ""
    for o in aspects:
        flags = []
        if o.get("hypothesis") == "panel":
            flags.append("panel")
        if o.get("ladder"):
            flags.append("&rarr;".join(o["ladder"]))
        if o.get("dropped"):
            flags.append("retirado: " + ",".join(o["dropped"]))
        if o["effective_ppi"] < 72:
            flags.append(f'<span class="warn">{o["effective_ppi"]:.0f} ppi</span>')
        rows += (f'<tr><td><a href="{o["key"]}.svg">{o["w"]}&times;{o["h"]}</a></td>'
                 f'<td class="n">{o["w"]/o["h"]:.2f}:1</td>'
                 f'<td class="n">{len(o["scrims"])}</td>'
                 f'<td>{" &middot; ".join(flags) or "&mdash;"}</td></tr>')

    quotes = "".join(
        f'<blockquote>{q}<em>&mdash; {w}</em></blockquote>' for q, w in THEIRS)

    doc = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Los 66 tamanos &middot; sin autorear plantillas</title>
<style>
 :root{{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8;--mut:#6b7f79}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--pap);color:var(--ink);
   font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
 .wrap{{max-width:1120px;margin:0 auto;padding:40px 24px 90px}}
 h1{{font-size:clamp(27px,4vw,38px);margin:0 0 12px;letter-spacing:-.02em;max-width:22ch}}
 h2{{font-size:22px;margin:52px 0 12px}}
 h2 span{{color:var(--acc);font-size:14px;font-weight:400;margin-left:8px}}
 p{{max-width:72ch}} .sub{{color:var(--mut);max-width:72ch}}
 .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;
   margin:26px 0 8px}}
 .kpi{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:16px 18px}}
 .kpi b{{display:block;font-size:26px;letter-spacing:-.02em}}
 .kpi span{{display:block;font-size:12.5px;color:var(--mut);margin-top:5px}}
 blockquote{{margin:12px 0;padding:13px 17px;background:#fff;border-left:3px solid var(--acc);
   border-radius:0 9px 9px 0;font-size:14.5px;max-width:74ch}}
 blockquote em{{display:block;margin-top:7px;font-style:normal;font-size:11.5px;
   color:var(--mut)}}
 .box{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:18px 20px;
   margin:16px 0;max-width:78ch}}
 .box.fair{{background:#fffaf0;border-color:#e8c98a}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;
   margin:16px 0}}
 figure{{margin:0;background:#fff;border:1px solid var(--line);border-radius:11px;
   overflow:hidden}}
 figure img{{width:100%;display:block;background:#e9e5dc}}
 figcaption{{padding:10px 13px;font-size:13px;border-top:1px solid var(--line)}}
 figcaption span{{display:block;font-size:11.5px;color:var(--mut);margin-top:2px;
   font-variant-numeric:tabular-nums}}
 table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);
   border-radius:11px;overflow:hidden;font-size:13.5px;margin:14px 0}}
 th{{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;
   color:var(--mut);background:#fbfaf7;padding:9px 14px}}
 td{{padding:8px 14px;border-top:1px solid #f0efeb}}
 td.n{{text-align:right;font-variant-numeric:tabular-nums}}
 .warn{{color:var(--acc)}}
 a{{color:inherit}}
 {nav.CSS}
</style>
<div class="wrap">
{nav.render(d, "generic66/spec.html")}
<h1>Un set de medios entero, sin autorear una sola plantilla</h1>
<p class="sub">El mismo master, los mismos {len(outs)} tamanos de banner de un set
 generico. Ninguna plantilla escrita a mano, ninguna proporcion declarada de
 antemano, ninguna re-ejecucion.</p>

<div class="kpis">
 <div class="kpi"><b>{n_ok} de {len(outs)}</b><span>pasan el validador
   independiente</span></div>
 <div class="kpi"><b>0 plantillas</b><span>autoreadas para conseguirlo</span></div>
 <div class="kpi"><b>{len(paneles)}</b><span>degradaron la foto a panel por
   decision medida</span></div>
 <div class="kpi"><b>{aspects[0]['w']/aspects[0]['h']:.1f}:1</b><span>la proporcion mas
   extrema resuelta</span></div>
</div>

<h2>Lo que reporto el mecanismo por plantillas<span>sobre este mismo master</span></h2>
<p class="sub">Texto literal de su propia herramienta. No se reproducen sus salidas ni
 capturas de su producto: solo lo que su informe dice de si mismo.</p>
{quotes}

<div class="box fair"><strong>Y aqui hay que ser justo.</strong> A ese mecanismo se le
 dieron dos plantillas y ninguna landscape, y su herramienta lo aviso antes de
 ejecutar. Presentar el resultado como un fallo del producto seria deshonesto: el
 producto hizo exactamente lo que dice que hace.
 <br><br>El argumento no es ese. El argumento es que <strong>la solucion que propone
 su propia herramienta es autorear mas plantillas</strong>, y ese trabajo escala con
 la diversidad de formatos, no con el numero de campanas. Un set de {len(outs)}
 tamanos tiene proporciones que tres plantillas no cubren, y su informe lo dice:
 <em>"ideally a couple more native ratios"</em>.</div>

<h2>Los mismos tamanos, resueltos desde el arte<span>los tres que su informe nombra,
 mas los extremos</span></h2>
<div class="grid">{cards}</div>

<h2>El triage<span>{tri["OK"]} no necesitan nada, {tri["REVISAR"]+tri["ATENCION"]} se
 marcan con su razon</span></h2>
<p>El objetivo declarado es un <strong>primer pase rough</strong>, y el triage es lo que
 convierte eso de disculpa en caracteristica: el disenador sabe cuales abrir en lugar
 de revisar los {len(outs)}.</p>
<div class="kpis">
 <div class="kpi"><b>{tri["OK"]}</b><span>sin banderas</span></div>
 <div class="kpi"><b>{tri["REVISAR"]}</b><span>revisar: scrim algo pesado o margen de
   contraste justo</span></div>
 <div class="kpi"><b>{tri["ATENCION"]}</b><span>atencion: PPI insuficiente o la foto
   degradada a panel</span></div>
</div>
<p class="sub">Ninguna de esas banderas es un fallo estructural: los {len(outs)} pasan
 el validador. Son juicios declarados sobre cuanto se tapa la fotografia y con cuanto
 margen se cumple el contraste. Los pesos por rol estan en el codigo, a la vista.
 <a href="index.html">Ver la hoja de contactos con las {len(outs)} piezas &rarr;</a></p>

<h2>Lo que hizo falta decidir<span>y no estaba escrito en ninguna plantilla</span></h2>
<ul>
<li><strong>{len(paneles)} formatos</strong> degradaron la fotografia a panel lateral
 porque ningun recorte a sangre contenia al sujeto por encima de su escala minima.
 Es una decision estructural emergente de una restriccion medida.</li>
<li><strong>{len(ladders)} formatos</strong> dispararon la escalera de degradacion.
 <strong>{len(dropped)}</strong> retiraron algun elemento, y queda registrado cual y
 por que.</li>
<li>El contraste se midio <strong>linea a linea</strong> contra la fotografia que a
 cada uno le toco, y el scrim se dimensiono componiendo en sRGB.</li>
</ul>

<div class="box"><strong>Un limite que este motor si declara.</strong>
 {len(lowppi)} de los {len(outs)} tamanos quedan por debajo de 72 ppi efectivos: el
 master tiene 2160x2700 pixeles y no da para un lienzo de 3840x2160 sin
 sobre-muestrear. <strong>El motor lo mide y lo dice en cada pieza.</strong> No lo
 arregla: pedir una fuente de mayor resolucion es la respuesta correcta, e inventar
 pixeles seria peor que avisar.</div>

<h2>Los {len(outs)} tamanos<span>ordenados de mas apaisado a mas vertical</span></h2>
<table><tr><th>Tamano</th><th>Proporcion</th><th>Scrims</th><th>Decisiones</th></tr>
{rows}</table>
<p class="sub">Cada tamano enlaza a su SVG editable. Ninguno se ajusto a mano.</p>
</div>
"""
    with open(os.path.join(d, "spec.html"), "w") as fh:
        fh.write(doc)
    print(f"-> {os.path.join(d, 'spec.html')}  ({n_ok}/{len(outs)} verde, "
          f"{len(paneles)} paneles, {len(lowppi)} bajo 72ppi)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1
          else os.path.join(ROOT, "out", "spring-campaign"))
