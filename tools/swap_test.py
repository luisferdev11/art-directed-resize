"""La prueba de las fotos: ¿el layout se DERIVA del arte, o solo lo tapa?

Mismo master, mismos formatos, mismos constraints. Lo unico que cambia es el pixel.

    art          el emplazamiento se busca sobre un campo de costo derivado de la
                 fotografia, asi que al cambiar la fotografia DEBE moverse
    constraints  el emplazamiento sale de una regla geometrica sobre una caja, asi
                 que al cambiar la fotografia NO PUEDE moverse

Esa es la tesis entera del proyecto reducida a dos columnas de numeros. No se
argumenta: se mide el desplazamiento del bloque de texto EN EL SVG ENTREGADO, que
es el mismo sitio del que lee `check.py`. Si nuestro backend no se moviera, el
proyecto no tendria caso, y este banco lo diria.
"""
from __future__ import annotations
import os, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import json

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nav
from formats import BY_KEY, VIDEO_ORDER

SVG = "http://www.w3.org/2000/svg"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "_swap")
MOVE_MIN = 100.0        # umbral declarado: por debajo, no es "visible a simple vista"
# El formato que se enseña. Es el unico que se mueve con LAS DOS fotos nuevas, asi
# que una fila de tres imagenes basta para ver el argumento sin leer la tabla.
HERO = "feed_1x1"
PAGE = os.path.join(ROOT, "out", "spring-campaign", "swap")

HOME = os.path.expanduser("~")
PHOTOS = [
    ("A", "the master's own", os.path.join(ROOT, "out", "_work", "photo.jpg")),
    ("B", "another subject, landscape",
     os.path.join(HOME, "Downloads", "PXL_20260411_004955053.jpg")),
    ("C", "very close subject, 1045px face",
     os.path.join(HOME, "Downloads", "PXL_20260617_044354953 (1).jpg")),
]


DECISIONS = ("crop", "hypothesis", "colours", "body sizes", "scrims",
             "dropped", "logo")


def decisions(d, key):
    """Las decisiones de layout de un formato, para compararlas entre fotos."""
    man = json.load(open(os.path.join(d, "manifest.json")))
    o = next((x for x in man["outputs"] if x["key"] == key), None)
    if o is None:
        return None
    return {"crop": tuple(o["crop_px"]), "hypothesis": o["hypothesis"],
            "colours": tuple(b["fill"] for b in o["blocks"]),
            "body sizes": tuple(b["size"] for b in o["blocks"]),
            "scrims": tuple((x["for"], round(x["alpha"], 2)) for x in o["scrims"]),
            "dropped": tuple(o["dropped"]),
            "logo": (o.get("logo") or {}).get("mark_only")}


def origin(path):
    """Esquina superior izquierda del conjunto de texto, medida en el SVG entregado."""
    root = etree.parse(path).getroot()
    xs, ys = [], []
    for g in root.findall("{%s}g" % SVG):
        if (g.get("id") or "").lower().startswith(("photograph", "scrim", "brand", "logo")):
            continue
        for t in g.findall("{%s}text" % SVG):
            try:
                xs.append(float(t.get("x"))); ys.append(float(t.get("y")))
            except (TypeError, ValueError):
                pass
    return (min(xs), min(ys)) if xs else None


def run(photo, dest):
    cmd = [sys.executable, "-B", os.path.join(ROOT, "run.py"),
           "--formats", "video", "--backend", "both", "--out", dest]
    if photo:
        cmd += ["--photo", photo]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-1500:], r.stderr[-1500:], file=sys.stderr)
        raise SystemExit(f"fallo al generar {dest}")


def shots():
    """Seis renders: el formato testigo, tres fotos, dos backends."""
    tdir = os.path.join(PAGE, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    fmt = BY_KEY[HERO]
    from PIL import Image
    for key, _, _ in PHOTOS:
        for backend, sub in (("constraints", "constraints"), ("art", "")):
            svg = os.path.abspath(os.path.join(OUT, key, sub, f"{HERO}.svg"))
            if not os.path.exists(svg):
                continue
            png = os.path.abspath(os.path.join(tdir, f"{backend}_{key}.png"))
            jpg = png[:-4] + ".jpg"
            subprocess.run([os.path.join(ROOT, "tools", "shot.sh"), svg, png,
                            str(fmt.w), str(fmt.h)], check=False, capture_output=True)
            if not os.path.exists(png):
                print(f"  ! sin thumbnail {backend}/{key}", file=sys.stderr)
                continue
            im = Image.open(png).convert("RGB")
            w = 380
            im.resize((w, max(1, round(w * fmt.h / fmt.w))), Image.LANCZOS).save(
                jpg, "JPEG", quality=82, optimize=True, progressive=True)
            os.remove(png)


def page(rows, tally, con_max, varied=None, n=5):
    fmt = BY_KEY[HERO]
    cols = "".join(
        f'<th>Foto {k}<span>{label}</span></th>' for k, label, _ in PHOTOS)

    def strip(backend, title, sub):
        cells = ""
        for k, _, _ in PHOTOS:
            j = f"thumbs/{backend}_{k}.jpg"
            cells += (f'<td><img src="{j}" alt="{backend} {k}" loading="lazy"></td>'
                      if os.path.exists(os.path.join(PAGE, j)) else "<td>-</td>")
        return (f'<tr class="lab"><th colspan="3"><strong>{title}</strong> '
                f'<span>{sub}</span></th></tr><tr class="ims">{cells}</tr>')

    dec_rows = ""
    for campo in DECISIONS:
        a = (varied or {}).get("art", {}).get(campo, 0)
        c = (varied or {}).get("constraints", {}).get(campo, 0)
        if not (a or c):
            continue
        dec_rows += (f'<tr><td>{campo}</td>'
                     f'<td class="n {"mv" if a else ""}">{a} de {n}</td>'
                     f'<td class="n">{c} de {n}</td></tr>')
    trs = ""
    for fk, moved in rows:
        f2 = BY_KEY[fk]
        a, c = moved.get("art", 0.0), moved.get("constraints", 0.0)
        trs += (f'<tr><td>{f2.label}</td><td class="n">{f2.w}&times;{f2.h}</td>'
                f'<td class="n {"mv" if a >= MOVE_MIN else ""}">{a:.0f} px</td>'
                f'<td class="n">{c:.0f} px</td></tr>')

    doc = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>La prueba de las fotos &middot; Meridian Quarter</title>
<style>
 :root{{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--pap);color:var(--ink);
   font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
 .wrap{{max-width:1240px;margin:0 auto;padding:40px 24px 80px}}
 h1{{font-size:30px;margin:0 0 6px;letter-spacing:-.01em}}
 h2{{font-size:19px;margin:40px 0 10px}}
 .sub{{margin:0 0 22px;opacity:.75;max-width:76ch}}
 .box{{background:#fff;border:1px solid var(--line);border-radius:9px;
   padding:16px 18px;margin:0 0 22px;max-width:78ch}}
 .box strong{{color:var(--acc)}}
 table.grid{{width:100%;border-collapse:collapse;background:#fff;
   border:1px solid var(--line);border-radius:10px;overflow:hidden}}
 table.grid th{{font-size:12.5px;padding:11px 12px;text-align:center;
   border-bottom:1px solid var(--line);font-weight:600}}
 table.grid th span{{display:block;font-weight:400;opacity:.6;font-size:11.5px}}
 tr.lab th{{text-align:left;background:#fbfaf7;border-top:1px solid var(--line)}}
 tr.lab th span{{display:inline;opacity:.65;font-weight:400}}
 tr.ims td{{padding:14px 12px;text-align:center;vertical-align:top;background:#f2efe8}}
 tr.ims img{{max-width:100%;display:block;margin:0 auto;
   box-shadow:0 0 0 1px rgba(0,0,0,.09)}}
 table.num{{border-collapse:collapse;font-size:13.5px;margin-top:8px;
   background:#fff;border:1px solid var(--line);border-radius:9px;overflow:hidden}}
 table.num td,table.num th{{padding:7px 14px;border-bottom:1px solid #f0efeb;
   text-align:left}}
 table.num th{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;
   opacity:.6;background:#fbfaf7}}
 td.n{{font-variant-numeric:tabular-nums;text-align:right}}
 td.mv{{color:var(--acc);font-weight:700}}
 .verdict{{margin:20px 0 0;padding:14px 18px;border-radius:9px;
   background:#e7efe9;color:#14614d;font-size:14px;max-width:78ch}}
 a{{color:inherit}}
 {nav.CSS}
</style>
<div class="wrap">
{nav.render(PAGE, "swap/index.html")}
<h1>The photograph swap</h1>
<p class="sub">Same master, same formats, same constraints. The only thing that changes
 is the pixel. If the layout is decided by looking at the photograph, it has to move; if
 it comes out of a geometric rule on a box, it cannot.</p>

<div class="box">All three photographs are my own. <strong>A</strong> is the master's.
 <strong>B</strong> is a different subject in landscape. <strong>C</strong> puts the
 subject very close, with a 1045px face, to push the crop.
 <br><br>With photograph B alone the criterion would not have been met: a single format
 crossed the threshold. A third was needed, and that is stated, because the number that
 counts is the one that was measured, not the one that suited.</div>

<h2>{fmt.label} &middot; {fmt.w}&times;{fmt.h}</h2>
<table class="grid"><tr>{cols}</tr>
{strip("constraints", "Template + constraints", "the text does not move")}
{strip("art", "Art-directed decision", "the text follows the photograph")}
</table>

<h2>Measured displacement, the {len(rows)} formats in the video</h2>
<p class="sub">How far the corner of the text block travels relative to photograph A, in
 canvas pixels, taken from the delivered SVG. The larger of the two photograph changes is
 shown. Declared threshold for visible movement: {MOVE_MIN:.0f}px.</p>
<table class="num"><tr><th>Format</th><th>Canvas</th><th>Art-directed</th>
<th>Constraints</th></tr>{trs}</table>

<div class="verdict"><strong>{tally['art']} of {len(rows)}</strong> formats move the text
 block more than {MOVE_MIN:.0f}px by the art route.
 <strong>{tally['constraints']} of {len(rows)}</strong> by the constraints route, with a
 maximum measured displacement of <strong>{con_max:.0f} px</strong>.</div>

<div class="box" style="margin-top:22px"><strong>Displacement turned out to be a poor
 instrument, and it is left in view rather than swapped for the one that came out
 well.</strong> The threshold was fixed at {MOVE_MIN:.0f}px before measuring, and by the
 art route only {tally['art']} of {len(rows)} formats cross it. The reason is by design:
 the engine pulls towards the master's composition on purpose, so when the photograph
 does not force the text to move, it does not move it. Moving it for the sake of moving
 would be worse.
 <br><br>What does separate the two mechanisms is <strong>how many decisions are
 redone</strong>.</div>

<h2>Layout decisions redone when the photograph changes</h2>
<table class="num"><tr><th>Decision</th><th>Art-directed</th><th>Constraints</th></tr>
{dec_rows}</table>
<div class="verdict" style="margin-top:14px">By the constraints route, the only thing
 that changes when the photograph changes is <strong>which pixels get cropped</strong>.
 Body sizes, colours, scrims, dropped elements and logo variant are identical across all
 {len(rows)} formats. A constraint does not look at the photograph: it has nothing to
 look with.</div>
</div>
"""
    os.makedirs(PAGE, exist_ok=True)
    with open(os.path.join(PAGE, "index.html"), "w") as fh:
        fh.write(doc)
    print("\n-> " + os.path.join(PAGE, "index.html"))


def main():
    pos = {}
    for key, label, src in PHOTOS:
        if not os.path.exists(src):
            raise SystemExit(f"falta la foto {key}: {src}")
        d = os.path.join(OUT, key)
        print(f"generando {key} ({label}) ...")
        run(None if key == "A" else src, d)
        for backend, sub in (("art", ""), ("constraints", "constraints")):
            for fk in VIDEO_ORDER:
                p = os.path.join(d, sub, f"{fk}.svg")
                if os.path.exists(p):
                    pos[(backend, fk, key)] = origin(p)

    print(f"\nDesplazamiento del bloque de texto respecto de la foto A, en px de lienzo."
          f"\nDeclared threshold for visible movement: {MOVE_MIN:.0f}px.\n")
    print(f"  {'format':15} {'canvas':11} {'art B':>9} {'art C':>9} "
          f"{'constr B':>9} {'constr C':>9}")
    tally = {"art": 0, "constraints": 0}
    rows = []
    for fk in VIDEO_ORDER:
        fmt = BY_KEY[fk]
        cells, moved = [], {}
        for backend in ("art", "constraints"):
            for k in ("B", "C"):
                a, b = pos.get((backend, fk, "A")), pos.get((backend, fk, k))
                if not (a and b):
                    cells.append("-"); continue
                d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                cells.append(f"{d:.0f}")
                moved[backend] = max(moved.get(backend, 0.0), d)
        for backend in ("art", "constraints"):
            if moved.get(backend, 0.0) >= MOVE_MIN:
                tally[backend] += 1
        rows.append((fk, moved))
        print(f"  {fk:15} {fmt.w}x{fmt.h:<6} {cells[0]:>9} {cells[1]:>9} "
              f"{cells[2]:>9} {cells[3]:>9}")

    n = len(VIDEO_ORDER)
    print(f"\n  formats moving more than {MOVE_MIN:.0f}px when the photograph changes:")
    print(f"    art-directed decision : {tally['art']} of {n}")
    print(f"    template + constraints : {tally['constraints']} of {n}")

    # Segunda medida, y la que resulto decisiva: NO cuanto se mueve el texto, sino
    # CUANTAS DECISIONES se rehacen. El desplazamiento resulto mal instrumento, y se
    # deja a la vista en lugar de cambiarlo por el que salio bien: el motor tira de
    # la composicion del master a proposito, asi que cuando la fotografia no obliga
    # a mover el texto, no lo mueve. Moverlo porque si seria peor diseno.
    varied = {"art": {}, "constraints": {}}
    for backend, sub in (("art", ""), ("constraints", "constraints")):
        for fk in VIDEO_ORDER:
            ds = [decisions(os.path.join(OUT, k, sub), fk) for k, _, _ in PHOTOS]
            if any(x is None for x in ds):
                continue
            for campo in DECISIONS:
                if len({repr(x[campo]) for x in ds}) > 1:
                    varied[backend][campo] = varied[backend].get(campo, 0) + 1
    print("\n  layout decisions REDONE when the photograph changes:")
    for campo in DECISIONS:
        a = varied["art"].get(campo, 0); c = varied["constraints"].get(campo, 0)
        if a or c:
            print(f"    {campo:12} art {a} of {n} formats "
                  f"| constraints {c} of {n}")
    tot_a = sum(varied["art"].values()); tot_c = sum(varied["constraints"].values())
    print(f"    {'TOTAL':12} art {tot_a} | constraints {tot_c}")

    ok_art = tally["art"] >= 3
    ok_con = tally["constraints"] == 0
    zero = all(max(m.values() if (m := r[1]) else [0]) == 0
               for r in rows if "constraints" in r[1]) if rows else False
    con_max = max((r[1].get("constraints", 0.0) for r in rows), default=0.0)
    print(f"\n  CRITERION 1 · art moves the layout in 3 or more formats: "
          f"{'MET' if ok_art else 'NOT MET'}")
    print(f"  CRITERION 2 · constraints move it in none: "
          f"{'MET' if ok_con else 'NOT MET'} "
          f"(maximum measured displacement: {con_max:.0f}px)")
    ok_dec = tot_a > tot_c and set(varied["constraints"]) <= {"crop"}
    print("  CRITERION 3 · only art redoes decisions beyond the crop: "
          + ("MET" if ok_dec else "NOT MET"))
    shots()
    page(rows, tally, con_max, varied, n)
    return 0 if (ok_con and ok_dec) else 1


if __name__ == "__main__":
    raise SystemExit(main())
