"""Hoja de contactos de la campana: como un disenador revisa el lote.

No inlinea los SVG: renderiza un thumbnail PNG por formato con Chromium y enlaza
al SVG editable. Inlinear ocho SVG con su foto en base64 daba 16MB de HTML.
El encuadre honesto: el PNG es lo que veras, el SVG es lo que puedes editar.

El PUNTAJE DE REVISION es el diferenciador: convierte "primer pase rough" de
disculpa en caracteristica. El disenador abre la campana y sabe cuales revisar.
"""
from __future__ import annotations
import html, json, os, subprocess, sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nav

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(ROOT, "tools", "shot.sh")
THUMB_W = 520


# Peso por rol al evaluar cuanto cuesta tapar la fotografia con un scrim.
# Tapar detras del titular cuesta mas que detras de una linea de legal.
# ESTOS PESOS SON UN JUICIO DECLARADO, NO UNA PROBABILIDAD CALIBRADA.
SCRIM_ROLE_W = {"headline": 1.00, "subhead": 0.80, "support": 0.60, "legal": 0.35}
SEV_ATTN, SEV_REVIEW = 0.42, 0.28


def review(o):
    """Puntaje de revision. Convierte "primer pase rough" de disculpa en
    caracteristica: el disenador sabe cuales revisar en lugar de revisar todo.

    Tres senales, cada una mapeada a una frase humana. La tercera del plan
    (margen al mejor candidato estructuralmente distinto) llega con las hipotesis
    estructurales; se declara en lugar de inventarse un numero.

    Un scrim NO es un defecto: es practica normal de diseno. Marcar cualquier
    scrim dejaria los ocho formatos en rojo y el triage seria inutil. Lo que se
    mide es CUANTO se tapa la foto y DONDE.
    """
    flags, sev = [], 0.0

    # 1. cuanto se tapa la fotografia, ponderado por rol
    worst = 0.0
    for sc in o.get("scrims", []):
        worst = max(worst, sc["alpha"] * SCRIM_ROLE_W.get(sc["for"], 0.6))
    if worst:
        sev = max(sev, worst)
        heavy = [sc for sc in o["scrims"]
                 if sc["alpha"] * SCRIM_ROLE_W.get(sc["for"], 0.6) >= SEV_REVIEW]
        if heavy:
            flags.append(", ".join(
                f"scrim of {sc['alpha']:.0%} behind {sc['for']}" for sc in heavy)
                + ": covers more of the photograph than one would like")
        elif o["scrims"]:
            mx = max(o["scrims"], key=lambda s: s["alpha"])
            flags.append(f"{len(o['scrims'])} scrim(s), the largest at {mx['alpha']:.0%} "
                         f"behind {mx['for']}: within the normal range for that role")

    # 2. la foto no cabe en este aspecto
    if o.get("hypothesis") == "panel":
        sev = max(sev, 0.95)
        flags.append("the photograph cannot bleed at this aspect without cutting "
                     "the subject: degraded to a panel")

    # 3. resolucion insuficiente de la fuente
    if o.get("effective_ppi", 999) < 72:
        sev = max(sev, 0.90)
        flags.append(f"PPI efectivo {o['effective_ppi']:.0f} bajo 72 nominal: "
                     f"suministrar fuente de mayor resolucion")

    # margen de contraste al filo, sin scrim que lo respalde
    tight = [b for b in o.get("blocks", [])
             if not b.get("scrimmed")
             and b.get("achieved", 9) / max(b["required"], 1e-9) < 1.05]
    if tight:
        sev = max(sev, 0.32)
        flags.append(f"{len(tight)} block(s) with under 5% contrast headroom")

    label = "ATENCION" if sev >= SEV_ATTN else ("REVISAR" if sev >= SEV_REVIEW else "OK")
    return label, flags


def build(d: str) -> None:
    with open(os.path.join(d, "manifest.json")) as fh:
        man = json.load(fh)
    tdir = os.path.join(d, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    cards = []
    for o in man["outputs"]:
        if o.get("failed"):
            continue
        # RUTAS ABSOLUTAS: con una relativa, file://out/x.svg hace que Chromium
        # trate "out" como host y el thumbnail sale siendo la pagina de error.
        svg = os.path.abspath(os.path.join(d, o["file"]))
        png = os.path.abspath(os.path.join(tdir, o["key"] + ".png"))
        jpg = os.path.abspath(os.path.join(tdir, o["key"] + ".jpg"))
        r = subprocess.run([SHOT, svg, png, str(o["w"]), str(o["h"])],
                           check=False, capture_output=True, text=True)
        if not os.path.exists(png):
            print(f"  ! {o['key']}: sin thumbnail. {r.stderr.strip()}", file=sys.stderr)
            continue
        im = Image.open(png).convert("RGB")
        # Guarda contra la pagina de error, que es un plano casi uniforme: si el
        # render no tiene variacion, no es la pieza. Mejor fallar ruidosamente que
        # entregar una hoja de contactos con capturas de error.
        import numpy as np
        sd = float(np.asarray(im.resize((64, 64))).std())
        if sd < 12.0:
            print(f"  ! {o['key']}: el thumbnail parece pagina de error o plano "
                  f"(desv={sd:.1f}). Revisar shot.sh.", file=sys.stderr)
        th = max(1, int(round(THUMB_W * o["h"] / o["w"])))
        # JPEG, no PNG: son thumbnails dominados por fotografia y en PNG pesaban
        # 4.4MB en total. A calidad 82 bajan a menos de medio mega.
        im.resize((THUMB_W, th), Image.LANCZOS).save(jpg, "JPEG", quality=82,
                                                     optimize=True, progressive=True)
        os.remove(png)
        label, why = review(o)
        cards.append((o, label, why))

    order = {"ATENCION": 0, "REVISAR": 1, "OK": 2}
    cards.sort(key=lambda c: (order[c[1]], -c[0]["w"] * c[0]["h"]))
    n_att = sum(1 for c in cards if c[1] != "OK")

    rows = []
    for o, label, why in cards:
        blocks = "".join(
            f"<tr><td>{html.escape(b['role'])}</td><td>{b['size']:g}px</td>"
            f"<td>{len(b['lines'])} ln</td>"
            f"<td>{b['achieved']:.2f} / {b['required']:.1f}"
            f"{' <em>+scrim</em>' if b.get('scrimmed') else ''}</td></tr>"
            for b in o["blocks"])
        reasons = "".join(f"<li>{html.escape(r)}</li>" for r in o["reasons"])
        note = "".join(f"<li>{html.escape(w)}</li>" for w in why) or "<li>no flags</li>"
        rows.append(f"""
<article class="card {label.lower()}">
  <header>
    <h2>{html.escape(o['label'])}</h2>
    <span class="dim">{o['w']}&times;{o['h']}</span>
    <span class="badge">{label}</span>
  </header>
  <a class="shot" href="{html.escape(o['file'])}">
    <img src="thumbs/{html.escape(o['key'])}.jpg" alt="{html.escape(o['label'])}"
         loading="lazy">
  </a>
  <div class="meta">
    <p class="flags"><strong>Revision:</strong></p><ul class="flags">{note}</ul>
    <table>{blocks}</table>
    <details><summary>Decisiones ({len(o['reasons'])})</summary><ul>{reasons}</ul></details>
    <p class="dl"><a href="{html.escape(o['file'])}">{html.escape(o['file'])}</a> ·
       recorte {o['crop_px'][2]:.0f}&times;{o['crop_px'][3]:.0f}px ·
       {o['effective_ppi']:.0f} ppi · coste {o['field_cost']:.3f}</p>
  </div>
</article>""")

    # Que vista es esta, para el <title> y para marcarla en la barra
    rel = os.path.relpath(os.path.join(os.path.abspath(d), "index.html"),
                          nav._root(d)).replace(os.sep, "/")
    label = next((l for r, l, _ in nav.SHEETS if r == rel), "Campana")
    NAVBAR = nav.render(d, rel)
    NAVCSS = nav.CSS
    TITLE = f"{label} &middot; Meridian Quarter"
    inf = "".join(f"<li>{html.escape(x)}</li>" for x in man["inference"])
    doc = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
<style>
 :root{{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--pap);color:var(--ink);
   font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
 .wrap{{max-width:1180px;margin:0 auto;padding:40px 24px 80px}}
 h1{{font-size:28px;margin:0 0 6px;letter-spacing:-.01em}}
 .sub{{margin:0 0 4px;opacity:.75}}
 .lede{{margin:18px 0 0;padding:16px 18px;background:#fff;border:1px solid var(--line);
   border-radius:8px;max-width:70ch}}
 .lede strong{{color:var(--acc)}}
 .infer{{margin:18px 0 34px;font-size:13.5px;opacity:.8}}
 .infer ul{{margin:6px 0 0;padding-left:20px}}
 .grid{{display:grid;gap:22px;align-items:start;
   grid-template-columns:repeat(auto-fill,minmax(340px,1fr))}}
 .card{{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;
   display:flex;flex-direction:column}}
 .card header{{display:flex;align-items:center;gap:10px;padding:12px 14px;
   border-bottom:1px solid var(--line)}}
 .card h2{{font-size:15px;margin:0;flex:1}}
 .dim{{font-size:12.5px;opacity:.6;font-variant-numeric:tabular-nums}}
 .badge{{font-size:11px;font-weight:700;letter-spacing:.06em;padding:3px 8px;border-radius:99px;
   background:#e7efe9;color:#14614d}}
 .card.revisar .badge{{background:#fdf0d5;color:#7a5200}}
 .card.atencion .badge{{background:#fbe0d8;color:#8f2c10}}
 .card.revisar{{border-color:#e8c98a}} .card.atencion{{border-color:#e5a68f}}
 /* Altura acotada: sin esto, el DL vertical dominaba la rejilla y el leaderboard
    de 8:1 quedaba como una tira invisible de 64px. Fondo neutro para que las
    piezas muy anchas se distingan del lienzo. */
 .shot{{display:flex;align-items:center;justify-content:center;min-height:150px;
   max-height:430px;background:#e9e5dc;line-height:0;overflow:hidden;
   border-bottom:1px solid var(--line)}}
 .shot img{{max-width:100%;max-height:430px;width:auto;height:auto;display:block;
   box-shadow:0 0 0 1px rgba(0,0,0,.07)}}
 .meta{{padding:12px 14px;font-size:13px}}
 ul.flags{{margin:4px 0 12px;padding-left:20px}} p.flags{{margin:0}}
 table{{width:100%;border-collapse:collapse;font-size:12.5px;
   font-variant-numeric:tabular-nums}}
 td{{padding:3px 6px 3px 0;border-bottom:1px solid #eee}}
 td:first-child{{opacity:.7}} em{{color:var(--acc);font-style:normal;font-size:11px}}
 details{{margin-top:10px;font-size:12.5px}} summary{{cursor:pointer;opacity:.75}}
 details ul{{margin:8px 0 0;padding-left:20px;line-height:1.45}}
 .dl{{margin:10px 0 0;font-size:11.5px;opacity:.6}}
 a{{color:inherit}}
 {NAVCSS}
</style>
<div class="wrap">
{NAVBAR}
<h1>Spring Style Is Here</h1>
<p class="sub">Meridian Quarter &middot; {label} &middot; {len(cards)} formatos desde un master, en una pasada</p>
<p class="lede"><strong>{n_att} de {len(cards)} formatos necesitan tu atencion.</strong>
 The rest cleared the brand constraints unaided. It is a rough first pass: what is
 flagged is what needs review, not the whole batch.</p>
<div class="infer"><strong>What the system inferred from the master</strong> (without reading layer names):
<ul>{inf}</ul></div>
<div class="grid">{''.join(rows)}</div>
</div>
"""
    with open(os.path.join(d, "index.html"), "w") as fh:
        fh.write(doc)
    print(f"index.html escrito: {len(cards)} tarjetas, {n_att} marcadas para revision")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "out/spring-campaign/meridian-quarter")
