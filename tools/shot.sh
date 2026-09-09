#!/usr/bin/env bash
# Rasteriza un SVG/HTML con Chromium headless.
#
# TRES trampas del entorno, todas aprendidas a golpes:
#
#  1. Chromium es un snap: el perfil va en /tmp (permitido) y la SALIDA debe quedar
#     bajo $HOME. Escribir la captura en /tmp falla en silencio.
#
#  2. La ruta de ENTRADA debe ser ABSOLUTA. Con una relativa, file://out/x.svg hace
#     que Chromium trate "out" como nombre de host, y la captura resultante es la
#     pagina de error "This site can't be reached" en lugar del render.
#
#  3. Chromium impone una ALTURA MINIMA de ventana. Con --window-size=728,90 renderiza
#     en un viewport mucho mas alto y luego escala la captura, comprimiendo un banner
#     de 90px a 3px de contenido. Un render comprimido conserva variacion, asi que
#     ninguna guarda estadistica lo detecta. Se rasteriza a una ventana holgada y se
#     recorta despues al tamano pedido: el SVG esta anclado arriba a la izquierda.
set -euo pipefail
[ -e "$1" ] || { echo "shot.sh: no existe la entrada: $1" >&2; exit 1; }
src="$(readlink -f "$1")"
out="$2"; w="${3:-1080}"; h="${4:-1350}"
MIN=520
rw=$(( w > MIN ? w : MIN ))
rh=$(( h > MIN ? h : MIN ))
prof="$(mktemp -d)"
trap 'rm -rf "$prof"' EXIT
mkdir -p "$(dirname "$out")"
rm -f "$out"
timeout 180 chromium --headless --disable-gpu --no-sandbox --hide-scrollbars \
  --virtual-time-budget=10000 --user-data-dir="$prof" \
  --default-background-color=FFFFFFFF \
  --screenshot="$out" --window-size="$rw,$rh" "file://$src" >/dev/null 2>&1 || true
[ -f "$out" ] || { echo "shot.sh: no se genero $out" >&2; exit 1; }
if [ "$rw" != "$w" ] || [ "$rh" != "$h" ]; then
  python3 - "$out" "$w" "$h" <<'PY'
import sys
from PIL import Image
p, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
im = Image.open(p)
if im.size != (w, h):
    im.crop((0, 0, w, h)).save(p)
PY
fi
