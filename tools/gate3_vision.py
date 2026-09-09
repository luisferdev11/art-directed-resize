"""Compuerta 3: la vision encuentra el sujeto en la foto hero, al tamano del master.

Si falla, se reencuadra el master. NUNCA se anade data-focal al archivo:
eso recrearia la queja del cliente ("requires a base Master example to be created first").
"""
from __future__ import annotations
import sys
import cv2
import numpy as np
from PIL import Image

HERO = "/home/pillofon/Downloads/PXL_20260330_105145119.jpg"

def faces(gray):
    out = []
    for name, sf, mn in (("default", 1.08, 5), ("alt2", 1.08, 5)):
        c = cv2.CascadeClassifier(cv2.data.haarcascades + f"haarcascade_frontalface_{name}.xml")
        for f in c.detectMultiScale(gray, sf, mn, minSize=(30, 30)):
            out.append((name, tuple(int(v) for v in f)))
    return out

def saliency_box(gray, pct=88):
    sal = cv2.saliency.StaticSaliencyFineGrained_create()
    ok, S = sal.computeSaliency(gray)
    if not ok:
        return None, None
    S = (S * 255).astype(np.uint8)
    thr = np.percentile(S, pct)
    ys, xs = np.where(S >= thr)
    return S, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

im = Image.open(HERO)
W0, H0 = im.size
rgb = np.array(im.convert("RGB"))
print(f"fuente: {W0}x{H0}  ({W0*H0/1e6:.1f} MPx)  aspecto {W0/H0:.3f}")

# --- 1. cara a resolucion de trabajo alta -------------------------------------
work_w = 1400
g = cv2.cvtColor(cv2.resize(rgb, (work_w, int(H0 * work_w / W0))), cv2.COLOR_RGB2GRAY)
fs = faces(g)
print(f"\n[a resolucion de trabajo {g.shape[1]}x{g.shape[0]}]")
if not fs:
    print("  sin cara")
for name, (x, y, w, h) in fs:
    sx = W0 / g.shape[1]
    print(f"  {name}: caja={x},{y},{w},{h}  -> en fuente: "
          f"{int(x*sx)},{int(y*sx)},{int(w*sx)},{int(h*sx)}  "
          f"centro rel=({(x+w/2)/g.shape[1]:.3f},{(y+h/2)/g.shape[0]:.3f})  alto={h}px")

# --- 2. region saliente -------------------------------------------------------
S, sb = saliency_box(g)
if sb:
    x0, y0, x1, y1 = sb
    print(f"\nregion saliente (p88): rel x[{x0/g.shape[1]:.3f},{x1/g.shape[1]:.3f}] "
          f"y[{y0/g.shape[0]:.3f},{y1/g.shape[0]:.3f}]")

# --- 3. LA PRUEBA REAL: a escala del master ------------------------------------
print("\n=== la cara a escala del master (el requisito real) ===")
for mw in (1080, 1350, 1600):
    mh = int(mw * 1.25)                      # master 4:5
    # ventana 4:5 mas ancha posible desde la fuente 3:4
    cw = W0; ch = int(cw * 1.25)
    if ch > H0:
        ch = H0; cw = int(ch / 1.25)
    crop = rgb[0:ch, (W0 - cw) // 2:(W0 - cw) // 2 + cw]
    small = cv2.cvtColor(cv2.resize(crop, (mw, mh)), cv2.COLOR_RGB2GRAY)
    f2 = faces(small)
    tag = "OK" if f2 else "FALLA"
    hs = ",".join(str(b[3]) for _, b in f2) or "-"
    print(f"  master {mw}x{mh}: ventana {cw}x{ch} -> caras={len(f2)} [{tag}] altos={hs}px")
