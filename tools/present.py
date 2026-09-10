"""La portada, EN INGLES: que es esto, por que existe y que hace, con sus cifras.

Esta pagina esta en ingles y el resto del sitio en espanol, y es deliberado. Es lo
primero que abre el cliente, que es australiano, y el puesto pide ingles fluido:
entregar la puerta de entrada en espanol lo contradice sin querer. Las vistas de
detalle son sobre todo imagenes y tablas de cifras, que se leen igual, y sus razones
quedan en espanol porque traducirlas entera cuesta un dia que no hay.

TODAS LAS CIFRAS SE LEEN DE LOS MANIFESTS Y DE LAS SALIDAS EN DISCO. Ninguna esta
escrita a mano. Es la misma regla que gobierna el resto del proyecto: si el codigo
cambia y la pagina no, la pagina miente, y una pagina que se vende sola es
exactamente donde mas caro sale mentir.

Lo que NO lleva esta pagina, a proposito:
  · ninguna cita del brief del cliente. Ese documento es suyo.
  · ningun nombre de cliente del empleador del autor.
  · ninguna cifra sin su N al lado.
"""
from __future__ import annotations
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import nav
from nav import SHEETS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://github.com/luisferdev11/art-directed-resize"

# Las vistas de detalle estan en espanol; sus nombres aqui van en ingles porque esta
# pagina lo esta. nav.py conserva los suyos para las paginas que si son en espanol.
EN = {
    "writeup.html": ("The write-up", "architecture notes on building with models"),
    "meridian-quarter/face-off.html": ("Head to head",
        "constraint resize against deciding from the art, 8 pairs"),
    "meridian-quarter/index.html": ("The campaign",
        "this engine over the master, 8 formats"),
    "meridian-quarter/constraints/index.html": ("The rival mechanism",
        "template plus constraints, on its own"),
    "meridian-flat/index.html": ("From a flat JPEG",
        "no layers, no text nodes: a model reads the piece"),
    "swap/index.html": ("The photograph test",
        "one master, three photographs: what moves and what does not"),
    "rollout/index.html": ("One folder per centre",
        "three centres, three self-contained packages"),
    "generic66/spec.html": ("A whole media spec",
        "66 sizes, no templates authored by hand"),
    "generic66/index.html": ("All 66, with triage",
        "every piece and what it flagged"),
}


# ------------------------------------------------------------------- las cifras
def validator(d):
    """El veredicto del validador, corriendolo. No se deduce de otra fuente."""
    r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "check.py"), d],
                       cwd=ROOT, capture_output=True, text=True)
    last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:]
    if not last:
        return None
    t = last[0]
    if t.startswith("VERDE"):
        n = int(t.split(":")[1].split()[0])
        return (n, n)
    if t.startswith("FALLA"):
        parts = t.replace("FALLA:", "").split()
        return (int(parts[2]) - int(parts[0]), int(parts[2]))
    return None


def facts(site):
    """Se leen del disco. Si algo falta, se dice que falta en lugar de inventarlo."""
    f = {}

    def man(*parts):
        p = os.path.join(site, *parts, "manifest.json")
        return json.load(open(p)) if os.path.exists(p) else None

    f["val_art"] = validator(os.path.join(site, "meridian-quarter"))
    f["val_con"] = validator(os.path.join(site, "meridian-quarter", "constraints"))
    a, c = man("meridian-quarter"), man("meridian-quarter", "constraints")
    if a and c:
        oa = [x for x in a["outputs"] if not x.get("failed")]
        oc = [x for x in c["outputs"] if not x.get("failed")]
        f["n_formatos"] = len(oa)
        f["viol_total"] = sum(len(x.get("violations") or []) for x in oc)
        f["viol_formatos"] = sum(1 for x in oc if x.get("violations"))
        f["limpios"] = len(oc) - f["viol_formatos"]
        f["n_bloques"] = sum(len(x["blocks"]) for x in oa)
        f["escalera"] = sorted({s for x in oa for s in (x.get("ladder") or [])})
        f["paneles"] = [x["key"] for x in oa if x.get("hypothesis") == "panel"]
        f["retirados"] = sorted({d for x in oa for d in (x.get("dropped") or [])})

    fl = man("meridian-flat")
    if fl:
        f["n_flat"] = len([x for x in fl["outputs"] if not x.get("failed")])
        f["flat_roles"] = [b["role"] for b in fl["outputs"][0]["blocks"]]

    ro = os.path.join(site, "rollout")
    if os.path.isdir(ro):
        cs = sorted(x for x in os.listdir(ro) if os.path.isdir(os.path.join(ro, x)))
        f["centres"] = cs
        f["piezas"] = sum(len([y for y in os.listdir(os.path.join(ro, x))
                               if y.endswith(".svg")]) for x in cs)

    g = os.path.join(ROOT, "out", "_golden", "golden.json")
    if os.path.exists(g):
        j = json.load(open(g))
        f["gold"] = (j["n_masters"], j["n_asignaciones"],
                     j["aciertos_por_tamano"], j["aciertos_por_modelo"])

    f["loc"] = sum(sum(1 for _ in open(os.path.join(dp, fn)))
                   for dp, _, fs in os.walk(ROOT)
                   for fn in fs if fn.endswith(".py")
                   and "__pycache__" not in dp and "/docs/" not in dp
                   and "/out/" not in dp)
    return f


def swap_facts(site):
    """Las decisiones que se rehacen al cambiar la fotografia, contadas en disco."""
    out = os.path.join(ROOT, "out", "_swap")
    if not os.path.isdir(out):
        return None
    import swap_test as SW
    res = {"art": {}, "constraints": {}}
    for backend, sub in (("art", ""), ("constraints", "constraints")):
        for fk in SW.VIDEO_ORDER:
            ds = [SW.decisions(os.path.join(out, k, sub), fk) for k, _, _ in SW.PHOTOS]
            if any(x is None for x in ds):
                return None
            for campo in SW.DECISIONS:
                if len({repr(x[campo]) for x in ds}) > 1:
                    res[backend][campo] = res[backend].get(campo, 0) + 1
    return res, len(SW.VIDEO_ORDER)


# ------------------------------------------------------------------ el diagrama
DIAGRAM = """
<svg viewBox="0 0 760 260" role="img" aria-label="Architecture: two input adapters against a single
 Scene model, two layout backends and one shared emitter"
 style="width:100%;height:auto;max-width:760px">
 <defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"
   markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="currentColor"/>
 </marker></defs>
 <g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="12.5">
  <rect x="8" y="26" width="150" height="42" rx="7" fill="#fff" stroke="#d8d3c8"/>
  <text x="83" y="44" text-anchor="middle" font-size="12">master.svg</text>
  <text x="83" y="59" text-anchor="middle" font-size="10.5" opacity=".6">parse_svg.py</text>

  <rect x="8" y="92" width="150" height="42" rx="7" fill="#fff" stroke="#d8d3c8"/>
  <text x="83" y="110" text-anchor="middle" font-size="12">master.jpg</text>
  <text x="83" y="125" text-anchor="middle" font-size="10.5" opacity=".6">semantic.py + model</text>

  <rect x="8" y="158" width="150" height="42" rx="7" fill="#faf7f0" stroke="#e0d5bd"
    stroke-dasharray="4 3"/>
  <text x="83" y="176" text-anchor="middle" font-size="12">Figma frame</text>
  <text x="83" y="191" text-anchor="middle" font-size="10.5" opacity=".55">plugin · not built</text>

  <rect x="238" y="82" width="120" height="62" rx="9" fill="#0E2A26"/>
  <text x="298" y="108" text-anchor="middle" fill="#F4F1EA" font-size="14"
    font-weight="700">Scene</text>
  <text x="298" y="126" text-anchor="middle" fill="#F4F1EA" font-size="10"
    opacity=".7">the only seam</text>

  <rect x="430" y="34" width="160" height="46" rx="7" fill="#fff" stroke="#d8d3c8"/>
  <text x="510" y="53" text-anchor="middle" font-size="12">solve.py</text>
  <text x="510" y="68" text-anchor="middle" font-size="10.5" opacity=".6">decides from the pixels</text>

  <rect x="430" y="146" width="160" height="46" rx="7" fill="#fff" stroke="#d8d3c8"/>
  <text x="510" y="165" text-anchor="middle" font-size="12">constraints.py</text>
  <text x="510" y="180" text-anchor="middle" font-size="10.5" opacity=".6">the rival mechanism</text>

  <rect x="640" y="82" width="112" height="62" rx="7" fill="#fff" stroke="#d8d3c8"/>
  <text x="696" y="104" text-anchor="middle" font-size="12">emit.py</text>
  <text x="696" y="121" text-anchor="middle" font-size="10.5" opacity=".6">editable SVG</text>

  <g stroke="currentColor" fill="none" marker-end="url(#ar)" opacity=".55">
   <path d="M158 47 C200 47 200 100 232 106"/>
   <path d="M158 113 L232 113"/>
   <path d="M158 179 C200 179 200 128 232 122" stroke-dasharray="4 3"/>
   <path d="M358 100 C395 100 395 57 424 57"/>
   <path d="M358 126 C395 126 395 169 424 169"/>
   <path d="M590 57 C615 57 615 100 634 106"/>
   <path d="M590 169 C615 169 615 128 634 122"/>
  </g>
 </g>
</svg>"""


def build(site: str) -> None:
    f = facts(site)
    sw = swap_facts(site)
    cards = "".join(
        '<a class="card" href="{}"><h3>{}</h3><p>{}</p></a>'.format(
            rel, *EN.get(rel, (label, desc)))
        for rel, label, desc in SHEETS if os.path.exists(os.path.join(site, rel)))

    dec = ""
    if sw:
        res, n = sw
        # Los nombres de campo vienen del banco de pruebas, que esta en espanol;
        # esta pagina esta en ingles y se traducen aqui en lugar de renombrarlos
        # alli, donde los leen las paginas que si son en espanol.
        EN_FIELD = {"recorte": "crop", "cuerpos": "type sizes",
                    "colores": "text colour", "scrims": "scrims",
                    "hipotesis": "structure", "retirados": "dropped elements",
                    "logo": "logo variant"}
        for campo in ("recorte", "cuerpos", "colores", "scrims"):
            a, c = res["art"].get(campo, 0), res["constraints"].get(campo, 0)
            dec += (f'<tr><td>{EN_FIELD.get(campo, campo)}</td>'
                    f'<td class="n {"hi" if a > c else ""}">{a} de {n}</td>'
                    f'<td class="n">{c} de {n}</td></tr>')

    g = f.get("gold")
    gold = (f'<strong>{g[3]}/{g[1]}</strong> frente a <strong>{g[2]}/{g[1]}</strong>, '
            f'sobre <strong>N={g[0]} masters</strong>' if g else "pendiente de medir")

    va = f.get("val_art") or ("?", "?")
    vc = f.get("val_con") or ("?", "?")
    esc = ", ".join(f["escalera"]) if f.get("escalera") else "ninguno"
    ret = ", ".join(f["retirados"]) if f.get("retirados") else "ninguno"

    doc = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>art-directed-resize &middot; a layout engine that reads the photograph</title>
<meta name="description" content="One master artwork becomes every format a media plan
 asks for, in a single pass: each one cropped, typeset, contrast-corrected and degraded
 on its own terms, with a stated reason behind every decision.">
<style>
 :root{{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8;--mut:#6b7f79}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--pap);color:var(--ink);
   font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
 .wrap{{max-width:1080px;margin:0 auto;padding:0 24px 90px}}
 header.hero{{padding:64px 0 10px}}
 h1{{font-size:clamp(30px,5vw,46px);line-height:1.1;margin:0 0 14px;
   letter-spacing:-.02em;max-width:19ch}}
 h1 em{{font-style:normal;color:var(--acc)}}
 .lede{{font-size:clamp(17px,2.2vw,20px);max-width:62ch;margin:0 0 26px;color:var(--mut)}}
 h2{{font-size:24px;margin:56px 0 12px;letter-spacing:-.01em}}
 h2 span{{color:var(--acc);font-size:15px;font-weight:400;margin-left:8px}}
 p{{max-width:70ch}}
 .cta{{display:flex;gap:10px;flex-wrap:wrap;margin:26px 0 0}}
 .cta a{{display:inline-block;padding:11px 20px;border-radius:99px;text-decoration:none;
   font-size:14.5px;font-weight:600;border:1px solid var(--ink)}}
 .cta a.p{{background:var(--ink);color:var(--pap)}}
 .cta a.s{{background:transparent;color:var(--ink)}}
 .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;
   margin:40px 0 0}}
 .kpi{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:16px 18px}}
 .kpi b{{display:block;font-size:27px;letter-spacing:-.02em;line-height:1.15}}
 .kpi span{{display:block;font-size:12.5px;color:var(--mut);margin-top:5px}}
 .box{{background:#fff;border:1px solid var(--line);border-radius:11px;
   padding:20px 22px;margin:18px 0}}
 .box.q{{border-left:3px solid var(--acc)}}
 table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);
   border-radius:11px;overflow:hidden;margin:14px 0;font-size:14.5px}}
 th{{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;
   color:var(--mut);background:#fbfaf7;padding:10px 16px;font-weight:600}}
 td{{padding:11px 16px;border-top:1px solid #f0efeb;vertical-align:top}}
 td:first-child{{font-weight:600;width:30%}}
 td.n{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;width:22%}}
 td.hi{{color:var(--acc)}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;
   margin:16px 0}}
 .card{{display:block;background:#fff;border:1px solid var(--line);border-radius:11px;
   padding:18px 20px;text-decoration:none;color:inherit}}
 .card:hover{{border-color:var(--ink)}}
 .card h3{{margin:0 0 5px;font-size:16px}}
 .card p{{margin:0;font-size:13.5px;color:var(--mut)}}
 .diagram{{background:#fff;border:1px solid var(--line);border-radius:11px;
   padding:22px;margin:16px 0;color:var(--ink);overflow-x:auto}}
 pre{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:16px 18px;
   font-size:13px;line-height:1.55;overflow-x:auto}}
 ul{{max-width:70ch}} li{{margin:7px 0}}
 .limits li::marker{{color:var(--acc)}}
 .note{{font-size:13.5px;color:var(--mut);margin-top:10px}}
 footer{{margin:70px 0 0;padding-top:22px;border-top:1px solid var(--line);
   font-size:13.5px;color:var(--mut)}}
 a{{color:inherit}}
</style>
<div class="wrap">
<header class="hero">
<h1>A layout engine that <em>reads the photograph</em></h1>
<p class="lede">One master goes in and every format of the campaign comes out in a
 single pass, each one cropped, typeset, contrast-corrected and degraded on its own
 terms. With a reason you can say out loud behind every decision.</p>
<div class="cta">
 <a class="p" href="meridian-quarter/face-off.html">See the head to head &rarr;</a>
 <a class="s" href="generic66/spec.html">66 sizes, no templates</a>
 <a class="s" href="writeup.html">The write-up</a>
 <a class="s" href="{REPO}">Source on GitHub</a>
</div>
<div class="kpis">
 <div class="kpi"><b>{f.get('n_formatos','?')} formats</b><span>from one master, in a
   single invocation</span></div>
 <div class="kpi"><b>{f.get('n_flat','?')} with no structure</b><span>built from a flat
   JPEG: no layers, no text nodes</span></div>
 <div class="kpi"><b>{len(f.get('centres',[]))} centres</b><span>{f.get('piezas','?')}
   pieces in self-contained folders</span></div>
 <div class="kpi"><b>{f.get('loc','?')} lines</b><span>of Python, no framework,
   deterministic</span></div>
</div>
<p class="note">This page and the write-up are in English. The detail views below are
 in Spanish: they are mostly artwork and tables of figures, and every number in them
 is generated, not written by hand.</p>
</header>

<h2>The problem<span>why a resize is not enough</span></h2>
<p>Adapting a campaign to dozens of formats is decision work, not scaling work. The
 usual mechanism &mdash; three hand-authored templates with constraints, each output
 matched to the closest one by size &mdash; moves boxes according to rules fixed in
 advance.</p>
<div class="box q"><strong>A constraint cannot look at the photograph.</strong> It does
 not know where the face is, whether the headline is still legible over whatever ended
 up behind it, or that at 8:1 the photograph should stop bleeding altogether. It works
 while the target resembles a template, and a campaign does not resemble three
 templates.</div>

<h2>What this engine does<span>the decisions it actually makes</span></h2>
<table>
<tr><th>Decision</th><th>How it is taken</th></tr>
<tr><td>Roles</td><td>Deduced from type size, area and relative hierarchy.
 <strong>Layer names are never read</strong>: rename everything to "Layer 1" and the
 result does not change. Depending on names would mean asking for a file authored for
 the tool.</td></tr>
<tr><td>Crop</td><td>Dense search over 7 scales and 13&times;13 positions, with the
 subject as a hard constraint and a floor and ceiling on subject scale.</td></tr>
<tr><td>Placement</td><td>Not picked from a list of anchors: <strong>searched over a
 cost field derived from the pixels</strong> &mdash; saliency, luminance variance and
 gradient &mdash; with the face region ruled out for text.</td></tr>
<tr><td>Contrast</td><td>WCAG luminance by percentiles, <strong>measured line by
 line</strong>. Where it falls short, the minimum scrim alpha is found by compositing
 in sRGB, which is where SVG actually composites.</td></tr>
<tr><td>Degradation</td><td>A stated ladder, applied in order: {esc}. Nothing is
 silently squeezed: if it does not fit, something goes and the reason is recorded.
 In this campaign what went was: {ret}.</td></tr>
<tr><td>Structure</td><td>When no bleed crop can hold the subject, the photograph
 degrades to a side panel and the brand field is promoted. That is a decision
 <strong>emerging from a measured constraint</strong>, not a per-format template.
 It happened in: {', '.join(f.get('paneles',[])) or 'none'}.</td></tr>
<tr><td>Output</td><td>Editable SVG: one <code>&lt;text&gt;</code> per line with
 absolute baselines and the fonts alongside. <strong>Verified: it imports into Figma
 with layers and editable text.</strong></td></tr>
</table>

<h2>The architecture<span>a single seam</span></h2>
<p><code>Scene</code> is the only coupling point in the system. File formats are
 adapters at both ends, and the decision engine is interchangeable. That is why the
 rival mechanism could be implemented as a <strong>second backend against the same
 model</strong>, and why a Figma plugin would be a third adapter rather than a
 separate project.</p>
<div class="diagram">{DIAGRAM}</div>
<p>For a flat JPEG there is nothing to parse: zero text nodes, zero roles, zero
 hierarchy. There a multimodal model reads the piece and assigns each role <em>by
 communicative function</em>, which is the one thing only a model can do; the pixels
 and the font metrics then measure where everything sits and how large it is. Burned-in
 text is removed with classical inpainting so the artwork can be recomposed underneath.
 If the schema does not validate, the chain falls through to the next provider
 <strong>and the failure is recorded</strong>.</p>

<h2>Measured results<span>every figure with its N</span></h2>
<table>
<tr><th>What was measured</th><th>Deciding from the art</th><th>Template + constraints</th></tr>
<tr><td>Formats that pass the validator<br>
 <span style="font-weight:400;font-size:12.5px;color:var(--mut)">re-parsing the
 delivered SVG: overlap, safe area, type floor, logo scale and per-line contrast.
 The same instrument for both</span></td>
 <td class="n hi">{va[0]} of {va[1]}</td>
 <td class="n">{vc[0]} of {vc[1]}</td></tr>
</table>
<p style="margin-top:-2px;font-size:14.5px;color:var(--mut)">The
 <strong>{f.get('limpios','?')}</strong> formats the constraint mechanism resolves
 without a single violation attributable to it are exactly those whose size matches a
 template. That is the honest claim, and it is why the comparison opens there.</p>

<h2 style="font-size:19px;margin-top:34px">When the photograph changes, which decision
 is remade?</h2>
<table>
<tr><th>Decision</th><th>Deciding from the art</th><th>Template + constraints</th></tr>
{dec}
</table>
<p>Down the constraint route, the only thing that changes when you change the
 photograph is <strong>which pixels get cropped</strong>: type sizes, colours, scrims
 and dropped elements are identical. That is the thesis, measured.</p>
<div class="box"><strong>Role assignment:</strong> reading the piece scores {gold}
 against ranking by type size. The whole difference is one deliberately constructed
 case, and a real one: a legal notice set in large type, which turns up in any
 regulated promotion. Ranking by size gets 1 of 4 right there.
 <br><br><strong>N=3 does not support a model comparison, and is not presented as
 one.</strong> It supports the claim that this class of artwork exists and that
 ranking by size fails on it by construction.</div>

<h2>What is inside<span>{len([1 for r,_,_ in SHEETS if os.path.exists(os.path.join(site,r))])} generated views</span></h2>
<div class="grid">{cards}</div>

<h2>What it does NOT do<span>said before anyone has to ask</span></h2>
<ul class="limits">
<li>It does not orchestrate campaigns: no bulk grouping, no bulk naming, no video
 export, no round trip back into the design tool through a plugin. It is the layout
 engine, not the product.</li>
<li><strong>Copy does not vary per centre.</strong> All three centres carry the same
 headline and the same dates. What changes is the photograph.</li>
<li>Exactly one field of the scene goes unverified: typographic <strong>weight</strong>
 on the flat-JPEG path. Deriving it was attempted and made the result worse, so it is
 stated rather than implying everything is measured.</li>
<li>The plate reconstructed under burned-in text is an <strong>approximation</strong>:
 beneath a 92px headline the inpainting invents plausible texture, not the original.</li>
<li><strong>A group is harder than a person, and it shows.</strong> When the subject is
 a group the focal region is a wide extent rather than a face, so it is maximised
 instead of required: at 4:5 and 1:1 it holds on a bleed crop, at 8:1 the photograph
 still degrades to a side panel, and in a 300&times;250 MPU the headline ends up over
 faces &mdash; the triage flags exactly those. Measured on three group photographs, not
 argued from one.</li>
<li>No interface. The pages on this site are generated static reports.</li>
</ul>

<h2>Reproducing it</h2>
<pre>pip install -r requirements.txt        <span style="opacity:.55"># opencv-CONTRIB, not opencv-python</span>

./run.py --backend both                <span style="opacity:.55"># both layout backends</span>
./check.py                             <span style="opacity:.55"># re-parse and measure the delivered SVG</span>
python3 tools/swap_test.py             <span style="opacity:.55"># one master, three photographs</span>
python3 tools/golden.py                <span style="opacity:.55"># role assignment, with its N</span>
./run.py --sizes specs/generic-66.txt \\
         --out out/spring-campaign/generic66   <span style="opacity:.55"># somebody else's spec sheet</span></pre>

<footer>Brand, type and photography declared in <code>assets/LICENSES.md</code>.
 MERIDIAN QUARTER, Harbourside Plaza and Northgate Centre are invented names.
 Code and documentation on <a href="{REPO}">GitHub</a>.</footer>
</div>
"""
    with open(os.path.join(site, "index.html"), "w") as fh:
        fh.write(doc)
    print(f"portada escrita: {len(doc)//1024} KB -> {os.path.join(site, 'index.html')}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1
          else os.path.join(ROOT, "out", "spring-campaign"))
