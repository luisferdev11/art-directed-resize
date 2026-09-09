"""Un archivo por centre. La cuarta queja del cliente, respondida literalmente.

    "It also cannot separate files into different 'centres' thus creating one
     overly large document"                                   -- el brief [pdf]

Lo verificado del competidor: 1340 assets aterrizan en UNA pagina de Figma,
`Rollout - 4:26 pm 21/07/2026`, agrupados por vendor dentro de ese unico documento
(`competencia.md` §2 `[ui]`). Agrupar no es separar.

Aqui cada centre es una CARPETA AUTOCONTENIDA: sus SVG, sus fuentes al lado, su
manifest y su hoja de contactos. Se abre, se comprime y se manda sola. Nadie tiene
que extraer nada de un documento grande.

LO QUE NO HACE, y se dice en la pagina en lugar de dejarlo sobreentendido: el copy
no varia por centre. Eso es la Fase 7b del plan y no esta construido. Cada centre
trae su propia fotografia, que es lo realista -cada centro fotografia lo suyo- y
es suficiente para lo que se afirma, que es la separacion de archivos.
"""
from __future__ import annotations
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import nav

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "out", "spring-campaign", "rollout")
HOME = os.path.expanduser("~")
MAX_MB = 3.0        # criterio declarado: ningun archivo por encima de esto
# El formato testigo que se ENSEÑA. Una vista sobre separacion de archivos que solo
# muestra una tabla de cifras no demuestra nada: hay que ver las tres piezas.
HERO = "portrait_4x5"

# Los tres centres son MARCAS INVENTADAS, declaradas en assets/LICENSES.md igual
# que Meridian Quarter. Cada uno con su hero propia.
CENTRES = [
    ("meridian-quarter", "Meridian Quarter",
     os.path.join(ROOT, "out", "_work", "photo.jpg")),
    ("harbourside-plaza", "Harbourside Plaza",
     os.path.join(HOME, "Downloads", "PXL_20260411_004955053.jpg")),
    ("northgate-centre", "Northgate Centre",
     os.path.join(HOME, "Downloads", "PXL_20260617_044354953 (1).jpg")),
]


def build():
    made = []
    for slug, name, photo in CENTRES:
        if not os.path.exists(photo):
            raise SystemExit(f"falta la fotografia de {name}: {photo}")
        d = os.path.join(DEST, slug)
        print(f"\n=== {name} ===")
        cmd = [sys.executable, "-B", os.path.join(ROOT, "run.py"),
               "--formats", "video", "--out", d]
        if slug != "meridian-quarter":
            cmd += ["--photo", photo]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:], file=sys.stderr)
            raise SystemExit(f"fallo generando {name}")
        print(r.stdout.strip().splitlines()[-1])

        chk = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "check.py"), d],
                             cwd=ROOT, capture_output=True, text=True)
        verde = chk.returncode == 0
        print("  validador:", chk.stdout.strip().splitlines()[-1])
        subprocess.run([sys.executable, "-B",
                        os.path.join(ROOT, "tools", "contact_sheet.py"), d],
                       cwd=ROOT, capture_output=True, text=True)

        files, total, biggest = 0, 0, 0.0
        for r_, _, fs in os.walk(d):
            for f in fs:
                sz = os.path.getsize(os.path.join(r_, f))
                files += 1; total += sz; biggest = max(biggest, sz / 1e6)
        made.append({"slug": slug, "name": name, "verde": verde, "files": files,
                     "mb": total / 1e6, "biggest": biggest,
                     "photo": os.path.basename(photo)})
        print(f"  {files} archivos, {total/1e6:.1f} MB, el mayor {biggest:.2f} MB")
    return made


def page(made):
    from formats import BY_KEY
    f = BY_KEY[HERO]
    BY_HERO = f"{f.label} &middot; {f.w}&times;{f.h}"
    ok_sep = len(made) == len(CENTRES)
    ok_verde = all(m["verde"] for m in made)
    ok_size = all(m["biggest"] <= MAX_MB for m in made)
    strip = "".join(
        f'<figure><img src="{m["slug"]}/thumbs/{HERO}.jpg" alt="{m["name"]}" '
        f'loading="lazy"><figcaption><strong>{m["name"]}</strong>'
        f'<span>{m["slug"]}/</span></figcaption></figure>'
        for m in made
        if os.path.exists(os.path.join(DEST, m["slug"], "thumbs", HERO + ".jpg")))
    rows = "".join(
        f'<tr><td><a href="{m["slug"]}/index.html"><strong>{m["name"]}</strong></a>'
        f'<span class="p">{m["photo"]}</span></td>'
        f'<td class="n">{m["files"]}</td><td class="n">{m["mb"]:.1f} MB</td>'
        f'<td class="n">{m["biggest"]:.2f} MB</td>'
        f'<td class="{"ok" if m["verde"] else "no"}">'
        f'{"verde" if m["verde"] else "FALLA"}</td></tr>' for m in made)
    tree = "\n".join(
        f"rollout/\n" if i == 0 else "" for i, _ in enumerate(made[:1])) + "\n".join(
        f"  {m['slug']}/\n"
        f"    portrait_4x5.svg  story_9x16.svg  leader_728.svg  mpu_300.svg  feed_1x1.svg\n"
        f"    fonts/            manifest.json   index.html" for m in made)
    doc = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Un archivo por centre &middot; Meridian Quarter</title>
<style>
 :root{{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--pap);color:var(--ink);
   font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
 .wrap{{max-width:1040px;margin:0 auto;padding:40px 24px 80px}}
 h1{{font-size:30px;margin:0 0 6px;letter-spacing:-.01em}}
 h2{{font-size:19px;margin:38px 0 10px}}
 .sub{{margin:0 0 22px;opacity:.75;max-width:76ch}}
 blockquote{{margin:0 0 22px;padding:12px 16px;background:#fff;
   border-left:3px solid var(--acc);border-radius:0 8px 8px 0;font-size:14px;
   max-width:76ch}}
 blockquote em{{opacity:.55;font-style:normal;font-size:11.5px}}
 table{{width:100%;border-collapse:collapse;background:#fff;
   border:1px solid var(--line);border-radius:10px;overflow:hidden}}
 th{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;opacity:.6;
   background:#fbfaf7;text-align:left;padding:9px 14px}}
 td{{padding:11px 14px;border-top:1px solid #f0efeb;vertical-align:top}}
 td.n{{font-variant-numeric:tabular-nums;text-align:right}}
 td.ok{{color:#14614d;font-weight:600}} td.no{{color:#8f2c10;font-weight:700}}
 span.p{{display:block;font-size:11.5px;opacity:.55;margin-top:2px}}
 pre{{background:#fff;border:1px solid var(--line);border-radius:9px;padding:14px 16px;
   font-size:12.5px;line-height:1.5;overflow-x:auto}}
 .crit{{margin:22px 0 0;padding:14px 18px;border-radius:9px;font-size:14px;
   max-width:78ch;background:#e7efe9;color:#14614d}}
 .gap{{margin:22px 0 0;padding:14px 18px;border-radius:9px;font-size:14px;
   max-width:78ch;background:#fdf0d5;color:#7a5200}}
 .strip{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:0 0 8px}}
 .strip figure{{margin:0;background:#fff;border:1px solid var(--line);
   border-radius:10px;overflow:hidden}}
 .strip img{{width:100%;display:block;border-bottom:1px solid var(--line)}}
 .strip figcaption{{padding:9px 12px;font-size:13px}}
 .strip figcaption span{{display:block;font-size:11.5px;opacity:.55;
   font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
 a{{color:inherit}}
 {nav.CSS}
</style>
<div class="wrap">
{nav.render(DEST, "rollout/index.html")}
<h1>Un archivo por centre</h1>
<blockquote>"It also cannot separate files into different 'centres' thus creating one
 overly large document" <em>&mdash; el brief del cliente [pdf]</em></blockquote>
<p class="sub">Lo verificado del competidor: 1340 assets aterrizan en una sola pagina
 de Figma, agrupados por vendor dentro de ese unico documento
 <em style="opacity:.55;font-size:12px">[ui, competencia.md §2]</em>. Agrupar no es
 separar. Aqui cada centre es una carpeta autocontenida: se abre, se comprime y se
 manda sola.</p>

<h2>Las tres piezas, mismo formato</h2>
<p class="sub">{BY_HERO} &mdash; una por centre, cada una en su carpeta. Misma
 estructura de master, misma copy, su propia fotografia y su propio layout resuelto.</p>
<div class="strip">{strip}</div>

<h2>Las carpetas</h2>
<table><tr><th>Centre</th><th>Archivos</th><th>Total</th><th>El mayor</th>
<th>Validador</th></tr>{rows}</table>

<h2>El arbol de salida</h2>
<pre>{tree}</pre>

<div class="crit">
 <strong>Criterios de aceptacion.</strong>
 {len(made)} centres &rarr; {len(made)} carpetas: <strong>{'cumple' if ok_sep else 'no cumple'}</strong>.
 <code>check.py</code> verde en todas: <strong>{'cumple' if ok_verde else 'no cumple'}</strong>.
 Ningun archivo por encima de {MAX_MB:.0f} MB: <strong>{'cumple' if ok_size else 'no cumple'}</strong>.
</div>

<div class="gap"><strong>Lo que esto NO hace.</strong> El copy no varia por centre:
 los tres llevan el mismo titular, la misma oferta y las mismas fechas. Esa es la
 Fase 7b del plan y no esta construida. Lo que cambia por centre es la fotografia,
 que es lo realista, y basta para lo que se afirma aqui, que es la separacion de
 archivos. Se nombra como hueco, no como ventaja.</div>
</div>
"""
    os.makedirs(DEST, exist_ok=True)
    with open(os.path.join(DEST, "index.html"), "w") as fh:
        fh.write(doc)
    print("\n  CRITERIO 1 · un directorio por centre : "
          + ("CUMPLE" if ok_sep else "NO CUMPLE"))
    print("  CRITERIO 2 · check.py verde en todos  : "
          + ("CUMPLE" if ok_verde else "NO CUMPLE"))
    print(f"  CRITERIO 3 · ningun archivo > {MAX_MB:.0f}MB     : "
          + ("CUMPLE" if ok_size else "NO CUMPLE"))
    print("\n-> " + os.path.join(DEST, "index.html"))
    return 0 if (ok_sep and ok_verde and ok_size) else 1


if __name__ == "__main__":
    raise SystemExit(page(build()))
