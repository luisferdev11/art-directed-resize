#!/usr/bin/env python3
"""Demo local: sueltas una imagen y salen los formatos. Para grabar el video.

NO ES PARA GITHUB PAGES y no debe acabar ahi. Corre en localhost, escribe en
`out/_demo/` y existe por dos razones: probar el pipeline con una imagen cualquiera
sin escribir un comando, y tener algo que se pueda enseñar en noventa segundos.

Un servidor de una sola pieza a proposito: `http.server` de la libreria estandar,
sin framework y sin dependencias nuevas. La pagina de arquitectura propone cola y
workers para produccion; esto no es eso, y no pretende serlo.

El trabajo va en un hilo y la pagina consulta el estado, porque leer un master con
un modelo tarda entre veinte y sesenta segundos y una peticion que se queda colgada
un minuto se ve rota aunque funcione.
"""
from __future__ import annotations
import html, io, json, os, shutil, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
OUT = os.path.join(ROOT, "out", "_demo")
PUERTO = 8799
FORMATOS = "portrait_4x5,story_9x16,leader_728,mpu_300,feed_1x1"
MAX_BYTES = 25 * 1024 * 1024

_trabajos: dict[str, dict] = {}
_lock = threading.Lock()


def _langfuse_url() -> str:
    import secrets_env as S
    return (S.get("LANGFUSE_BASE_URL") or "").rstrip("/")


# --------------------------------------------------------------------- el trabajo
def procesar(jid: str, ruta: str, nombre: str) -> None:
    d = os.path.join(OUT, jid)
    t0 = time.time()

    def paso(txt, **kw):
        with _lock:
            _trabajos[jid].update(paso=txt, t=round(time.time() - t0, 1), **kw)

    try:
        # TRES CAMINOS, y cual se toma lo decide el archivo, no un boton.
        #
        # Si lo que sueltas es una PIEZA ya compuesta -copy sobrepuesto, logo,
        # jerarquia- el modelo la lee y la escena sale de ahi. Si es una FOTOGRAFIA
        # no hay titular que leer, y rechazarla seria absurdo cuando es lo primero
        # que cualquiera va a probar: se usa la estructura del master de referencia
        # con esa foto, que es el camino de `--photo`.
        #
        # UNA sola llamada barata decide la ruta. Antes se intentaba leer la escena
        # y, si fallaba, se caia a la ruta de fotografia: sobre una foto sin copy eso
        # gastaba tres cuartos de minuto averiguando algo que se pregunta en diez
        # segundos. La misma llamada devuelve la region que no se puede recortar,
        # asi que no es una consulta extra: es la que ya haciamos, antes.
        sys.path.insert(0, os.path.join(ROOT, "src"))
        import semantic
        base = [sys.executable, "-B", os.path.join(ROOT, "run.py"),
                "--formats", FORMATOS, "--out", d]

        # TERCERA RUTA, y la del caso de uso real: un SVG DE CAMPANA.
        #
        # Aqui no hay nada que preguntarle a un modelo para decidir la ruta. Un SVG
        # trae su estructura -nodos de texto, raster, lockup- y eso es exactamente lo
        # que el parser consume, asi que entra como master y sale el rollout. Es el
        # pipeline apuntado a su propia salida: los SVG que este motor emite valen
        # como entrada, y por eso "componente de campana -> rollout" no es una
        # feature que falte sino la que ya esta. El componente de Figma sera un
        # adaptador mas delante del mismo `Scene`.
        es_svg = ruta.lower().endswith(".svg")
        if es_svg:
            paso("es un SVG de campana: leyendo su estructura")
            r = subprocess.run(base + ["--master", ruta],
                               cwd=ROOT, capture_output=True, text=True, timeout=900)
            via = ("SVG de campana: su estructura se lee del archivo -sin nombres de "
                   "capa- y se produce el rollout. Es el caso de uso real, y la "
                   "entrada puede ser una salida de este mismo motor")
            pieza = False
        else:
            paso("mirando que tipo de imagen es")
            pista, _log = semantic.focal_from_model(ruta)
            pieza = bool(pista and pista.get("lleva_copy"))
            if pieza:
                paso("es una pieza compuesta: leyendo su escena")
                r = subprocess.run(base + ["--master", ruta],
                                   cwd=ROOT, capture_output=True, text=True,
                                   timeout=900)
                via = "lleva copy sobrepuesto: la escena se leyo de la propia imagen"
            else:
                que = (f"{pista['sujeto']} — {pista['que_es']}" if pista
                       else "sin foco claro")
                paso(f"es una fotografia ({que}): se aplica la campana encima")
                r = subprocess.run(
                    base + ["--master", os.path.join(ROOT, "assets", "master.svg"),
                            "--photo", ruta],
                    cwd=ROOT, capture_output=True, text=True, timeout=900)
                via = (f"sin copy sobrepuesto, asi que se trato como FOTOGRAFIA: "
                       f"estructura del master de referencia, tu foto. El modelo "
                       f"identifico {que}")
        if r.returncode != 0 and pieza:
            paso("la escena no valido: se aplica la campana sobre la fotografia")
            r = subprocess.run(
                base + ["--master", os.path.join(ROOT, "assets", "master.svg"),
                        "--photo", ruta],
                cwd=ROOT, capture_output=True, text=True, timeout=900)
            via = "el esquema de la escena no valido: se uso la ruta de fotografia"
        if r.returncode != 0:
            paso("fallo", estado="error",
                 detalle=(r.stderr or r.stdout)[-700:])
            return
        with _lock:
            _trabajos[jid]["via"] = via

        # Las notas de inferencia son la mitad del argumento: se enseñan.
        notas = []
        man = os.path.join(d, "manifest.json")
        if os.path.exists(man):
            notas = json.load(open(man)).get("inference", [])

        paso("validando el archivo entregado", notas=notas)
        chk = subprocess.run(
            [sys.executable, "-B", os.path.join(ROOT, "check.py"), d],
            cwd=ROOT, capture_output=True, text=True, timeout=300)
        veredicto = [l for l in chk.stdout.strip().splitlines() if l.strip()][-1:]

        paso("renderizando las miniaturas")
        subprocess.run(
            [sys.executable, "-B", os.path.join(ROOT, "tools", "contact_sheet.py"), d],
            cwd=ROOT, capture_output=True, text=True, timeout=900)

        piezas = []
        if os.path.exists(man):
            for o in json.load(open(man))["outputs"]:
                if o.get("failed"):
                    continue
                piezas.append({"key": o["key"], "label": o["label"],
                               "w": o["w"], "h": o["h"],
                               "hyp": o["hypothesis"], "ppi": o["effective_ppi"],
                               "scrims": len(o["scrims"]),
                               "dropped": o.get("dropped") or [],
                               "ladder": o.get("ladder") or [],
                               "reasons": o["reasons"]})
        with _lock:
            _trabajos[jid].update(estado="listo", paso="hecho", piezas=piezas,
                                  notas=notas, nombre=nombre,
                                  via=_trabajos[jid].get("via", ""),
                                  veredicto=veredicto[0] if veredicto else "",
                                  t=round(time.time() - t0, 1))
    except subprocess.TimeoutExpired:
        paso("se agoto el tiempo", estado="error", detalle="mas de 15 minutos")
    except Exception as e:
        paso("fallo", estado="error", detalle=f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------------- la web
PAGINA = """<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drop an image</title>
<style>
 :root{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8;--mut:#61756f}
 *{box-sizing:border-box}
 body{margin:0;background:var(--pap);color:var(--ink);
   font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 .wrap{max-width:1080px;margin:0 auto;padding:44px 24px 80px}
 h1{font-size:32px;margin:0 0 8px;letter-spacing:-.02em}
 .sub{color:var(--mut);margin:0 0 26px;max-width:62ch}
 #drop{border:2px dashed var(--line);border-radius:14px;background:#fff;
   padding:52px 24px;text-align:center;cursor:pointer;transition:.15s}
 #drop.over{border-color:var(--acc);background:#fff8f5}
 #drop b{display:block;font-size:19px;margin-bottom:6px}
 #drop span{color:var(--mut);font-size:14px}
 .estado{background:#fff;border:1px solid var(--line);border-radius:12px;
   padding:18px 22px;margin:22px 0;display:none}
 .estado.on{display:block}
 .bar{height:5px;background:#eee;border-radius:99px;overflow:hidden;margin:12px 0 0}
 .bar i{display:block;height:100%;width:30%;background:var(--acc);
   animation:go 1.15s ease-in-out infinite}
 @keyframes go{0%{margin-left:-30%}100%{margin-left:100%}}
 .notas{margin:14px 0 0;font-size:13.5px;color:var(--mut)}
 .notas li{margin:4px 0}
 .verde{color:#14614d;font-weight:700}
 .rojo{color:#8f2c10;font-weight:700}
 .grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
   margin-top:26px}
 .card{background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}
 .card .shot{background:#e9e5dc;display:flex;align-items:center;justify-content:center;
   min-height:130px;max-height:330px;overflow:hidden}
 .card img{max-width:100%;max-height:330px;display:block}
 .card .m{padding:12px 15px;font-size:13.5px}
 .card h3{margin:0 0 3px;font-size:15px}
 .dim{color:var(--mut);font-size:12.5px;font-variant-numeric:tabular-nums}
 details{margin-top:9px;font-size:12.5px} summary{cursor:pointer;color:var(--mut)}
 details ul{margin:7px 0 0;padding-left:18px;line-height:1.45}
 .lf{margin-top:22px;font-size:13.5px;color:var(--mut)}
 .lf a{color:var(--acc)}
 a{color:inherit}
</style>
<div class="wrap">
<h1>Drop an image</h1>
<p class="sub">Any photograph or a flattened piece of artwork. A model reads it, the
 pixels and the font metrics measure it, and the engine resolves five formats. Nothing
 here is authored in advance.</p>

<div id="drop"><b>Drop an image or a campaign SVG here</b><span>or click to choose
 &middot; JPEG, PNG or SVG, up to 25 MB &middot; an SVG this engine emitted works as
 input too</span></div>
<input id="file" type="file" accept="image/*,.svg,image/svg+xml" hidden>

<div class="estado" id="estado">
  <div id="paso">…</div>
  <div class="bar" id="bar"><i></i></div>
  <ul class="notas" id="notas"></ul>
</div>

<div class="grid" id="grid"></div>
<p class="lf" id="lf"></p>
</div>
<script>
const drop=document.getElementById('drop'), file=document.getElementById('file');
const est=document.getElementById('estado'), paso=document.getElementById('paso');
const bar=document.getElementById('bar'), notas=document.getElementById('notas');
const grid=document.getElementById('grid'), lf=document.getElementById('lf');

drop.onclick=()=>file.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add('over')};
drop.ondragleave=()=>drop.classList.remove('over');
drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');
  if(e.dataTransfer.files[0]) subir(e.dataTransfer.files[0])};
file.onchange=()=>{if(file.files[0]) subir(file.files[0])};

async function subir(f){
  grid.innerHTML=''; lf.textContent=''; notas.innerHTML='';
  est.classList.add('on'); bar.style.display='block';
  paso.textContent='subiendo '+f.name+'…';
  const fd=new FormData(); fd.append('img',f,f.name);
  const r=await fetch('/upload',{method:'POST',body:fd});
  if(!r.ok){paso.innerHTML='<span class="rojo">'+await r.text()+'</span>';
            bar.style.display='none';return}
  seguir((await r.json()).id);
}

async function seguir(id){
  const r=await fetch('/estado?id='+id); const j=await r.json();
  paso.textContent=j.paso+(j.t?'  ·  '+j.t+'s':'');
  if(j.notas) notas.innerHTML=j.notas.map(n=>'<li>'+esc(n)+'</li>').join('');
  if(j.estado==='error'){
    paso.innerHTML='<span class="rojo">'+esc(j.paso)+'</span>';
    notas.innerHTML='<li>'+esc(j.detalle||'')+'</li>'; bar.style.display='none'; return;
  }
  if(j.estado==='listo'){ bar.style.display='none'; pintar(id,j); return; }
  setTimeout(()=>seguir(id), 900);
}

function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}

function pintar(id,j){
  const v=j.veredicto||'';
  paso.innerHTML='<span class="'+(v.startsWith('VERDE')?'verde':'rojo')+'">'+esc(v)+
                 '</span>  ·  '+j.t+'s en total'+
                 (j.via?'<div class="dim" style="margin-top:6px">'+esc(j.via)+'</div>':'');
  grid.innerHTML=j.piezas.map(p=>`
    <article class="card">
      <a class="shot" href="/f/${id}/${p.key}.svg">
        <img src="/f/${id}/thumbs/${p.key}.jpg" loading="lazy" alt="${esc(p.label)}"></a>
      <div class="m"><h3>${esc(p.label)}</h3>
        <div class="dim">${p.w}&times;${p.h} · ${esc(p.hyp)} · ${p.ppi.toFixed(0)} ppi
          · ${p.scrims} scrim(s)${p.dropped.length?' · dropped: '+p.dropped.join(','):''}</div>
        <details><summary>${p.reasons.length} decisions</summary>
          <ul>${p.reasons.map(r=>'<li>'+esc(r)+'</li>').join('')}</ul></details>
      </div></article>`).join('');
  if(j.langfuse) lf.innerHTML='Model call traced &rarr; <a href="'+j.langfuse+
    '" target="_blank">open it in Langfuse</a>';
}
</script>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _envia(self, code, tipo, cuerpo: bytes):
        self.send_response(code)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._envia(200, "text/html; charset=utf-8", PAGINA.encode())
        if u.path == "/estado":
            jid = dict(p.split("=", 1) for p in u.query.split("&") if "=" in p).get("id", "")
            with _lock:
                j = dict(_trabajos.get(jid, {"estado": "error", "paso": "no existe"}))
            if j.get("estado") == "listo":
                base = _langfuse_url()
                j["langfuse"] = base or ""
            return self._envia(200, "application/json", json.dumps(j).encode())
        if u.path.startswith("/f/"):
            rel = u.path[3:].lstrip("/")
            ruta = os.path.normpath(os.path.join(OUT, rel))
            if not ruta.startswith(os.path.abspath(OUT)) or not os.path.isfile(ruta):
                return self._envia(404, "text/plain", b"no")
            tipo = {"svg": "image/svg+xml", "jpg": "image/jpeg",
                    "png": "image/png", "json": "application/json",
                    "html": "text/html; charset=utf-8"}.get(ruta.rsplit(".", 1)[-1],
                                                            "application/octet-stream")
            with open(ruta, "rb") as fh:
                return self._envia(200, tipo, fh.read())
        return self._envia(404, "text/plain", b"no")

    def do_POST(self):
        if urlparse(self.path).path != "/upload":
            return self._envia(404, "text/plain", b"no")
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BYTES:
            return self._envia(413, "text/plain", b"la imagen pasa de 25 MB")
        crudo = self.rfile.read(n)

        # multipart a mano: una dependencia menos, y solo hay un campo
        ctype = self.headers.get("Content-Type", "")
        if "boundary=" not in ctype:
            return self._envia(400, "text/plain", b"peticion mal formada")
        bnd = ("--" + ctype.split("boundary=", 1)[1].strip()).encode()
        partes = [p for p in crudo.split(bnd) if b"filename=" in p]
        if not partes:
            return self._envia(400, "text/plain", b"no llego ningun archivo")
        cab, _, cuerpo = partes[0].partition(b"\r\n\r\n")
        datos = cuerpo.rstrip(b"\r\n--")
        # Por LINEAS, no partiendo la cabecera entera por ";": Content-Disposition y
        # Content-Type van seguidas, y partir por ";" se traga la segunda dentro del
        # nombre del archivo. La extension salia mal y todo se rechazaba.
        nombre = "subida"
        for linea in cab.decode("utf-8", "ignore").split("\r\n"):
            if "filename=" not in linea.lower():
                continue
            for t in linea.split(";"):
                if "filename=" in t.lower():
                    nombre = os.path.basename(
                        t.split("=", 1)[1].strip().strip('"')) or nombre
            break

        ext = os.path.splitext(nombre)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".svg"):
            return self._envia(400, "text/plain",
                               b"formato no admitido: JPEG, PNG o SVG")
        if len(datos) < 1024:
            return self._envia(400, "text/plain", b"el archivo llego vacio")

        jid = uuid.uuid4().hex[:10]
        d = os.path.join(OUT, jid)
        os.makedirs(d, exist_ok=True)
        ruta = os.path.join(d, "master" + (".jpg" if ext in (".jpg", ".jpeg") else ext))
        # Un SVG con raster embebido pesa megas: el minimo de 1KB no aplica igual,
        # pero tampoco molesta. Lo que importa es que la extension sobreviva, porque
        # es lo que enruta.
        with open(ruta, "wb") as fh:
            fh.write(datos)
        with _lock:
            _trabajos[jid] = {"estado": "trabajando", "paso": "en cola", "t": 0}
        threading.Thread(target=procesar, args=(jid, ruta, nombre), daemon=True).start()
        return self._envia(200, "application/json", json.dumps({"id": jid}).encode())


def main():
    os.makedirs(OUT, exist_ok=True)
    import trace as TR
    print(f"demo local  ->  http://localhost:{PUERTO}")
    print(f"observabilidad: {TR.estado()}")
    print("salida en out/_demo/  ·  NO se publica en Pages")
    ThreadingHTTPServer(("127.0.0.1", PUERTO), Handler).serve_forever()


if __name__ == "__main__":
    main()
