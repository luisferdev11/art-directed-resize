#!/usr/bin/env python3
"""Adapta un master a los formatos de una campana.

Un script, cuatro flags. Sin subcomandos.

Cada formato es funcion pura del Scene, asi que el problema es embarazosamente
paralelo por construccion. No se uso un pool de procesos: ocho formatos en serie
son instantaneos y depurar multiprocessing con objetos cv2 cuesta mas de lo que
ahorra. La afirmacion "una campana en una pasada" la cumple una sola invocacion.

DOS BACKENDS DE LAYOUT contra el mismo Scene:
  art          la decision se busca sobre los pixeles           (src/solve.py)
  constraints  template mas constraints, el mecanismo rival     (src/constraints.py)

Que los dos entren por la misma puerta y salgan por el mismo emisor no es comodidad:
es la demostracion de que `scene.py` es un seam real y de que el motor de decision
es intercambiable. Un tercer adaptador de entrada (IDML, PSD, Figma) entra ahi mismo.
"""
from __future__ import annotations
import argparse, json, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import constraints as constraintsmod
import crop as cropmod
import emit
import solve as solvemod
from formats import BY_KEY, FORMATS, VIDEO_ORDER, from_sizes
from parse_svg import parse

BACKENDS = {"art": solvemod.solve, "constraints": constraintsmod.solve}


def _has_light(scene) -> bool:
    return bool(scene.lockup and scene.lockup.light_nodes)


def _lockup_nodes(scene, r):
    """Los nodos del lockup para este formato: marca sola o completo, oscuro o claro.

    Si el adaptador de entrada dejo hecha la variante clara -lo hace cuando el logo
    viene de pixeles y no se puede recolorear en el emisor-, se usa esa. Si no, van
    los nodos vectoriales y el emisor los recolorea.
    """
    lk = scene.lockup
    if not (lk and r.get("lockup")):
        return None
    mark = r["lockup"].get("mark_only")
    if r["lockup"].get("invert") and lk.light_nodes:
        return lk.light_mark_nodes if mark else lk.light_nodes
    return lk.mark_nodes if mark else lk.nodes


def run_backend(name, scene, keys, prep, out_dir, master):
    """Resuelve y emite un lote completo con un backend. Devuelve el manifest."""
    solver = BACKENDS[name]
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"master": master, "backend": name,
                "canvas": [scene.width, scene.height],
                "inference": scene.notes, "outputs": []}
    results = []
    for key in keys:
        fmt = BY_KEY[key]
        r = solver(scene, fmt, prep)
        if r.get("failed"):
            print(f"  {key:15} FALLO")
            for x in r["reasons"]:
                print(f"      - {x}")
            manifest["outputs"].append({"key": key, "failed": True,
                                        "reasons": r["reasons"]})
            continue
        results.append(r)
        target = r.get("panel") or (0.0, 0.0, float(fmt.w), float(fmt.h))
        uri, box = emit.photo_placement(scene.photo.src_path, r["crop_px"], target)
        path = os.path.join(out_dir, f"{key}.svg")
        emit.write(path, fmt.w, fmt.h,
                   {"blocks": r["blocks"], "scrims": r["scrims"], "panel": r["panel"]},
                   uri, box,
                   _lockup_nodes(scene, r), r["lockup"]["xform"] if r["lockup"] else None,
                   bool(r["lockup"] and r["lockup"].get("invert")
                        and not _has_light(scene)))
        kb = os.path.getsize(path) / 1024
        worst = min((b["achieved"] / b["required"] for b in r["blocks"]), default=9.9)
        dr = ",".join(r.get("dropped") or []) or "-"
        ld = ">".join(r.get("ladder") or []) or "-"
        nv = len(r.get("violations") or [])
        print(f"  {key:15} {fmt.w:5d}x{fmt.h:<5d} {kb:6.0f}KB  "
              f"hip={r['hypothesis']:17} coste={r['cost']:.3f} "
              f"ppi={r['ppi']:5.1f} scrims={len(r['scrims'])} "
              f"margen={worst:.2f}x retirado={dr} escalera={ld}"
              + (f" VIOLACIONES={nv}" if nv else ""))
        entry = {
            "key": key, "label": fmt.label, "w": fmt.w, "h": fmt.h,
            "file": f"{key}.svg", "hypothesis": r["hypothesis"],
            "crop_px": [round(v, 1) for v in r["crop_px"]],
            "effective_ppi": round(r["ppi"], 1), "field_cost": round(r["cost"], 4),
            "reasons": r["reasons"],
            "dropped": r.get("dropped") or [],
            "ladder": r.get("ladder") or [],
            "panel": [round(v, 1) for v in r["panel"]] if r.get("panel") else None,
            "logo": ({"width": round(r["lockup"]["rect"][2], 1),
                      "scale": round(r["lockup"]["scale"], 3),
                      "mark_only": r["lockup"]["mark_only"]} if r.get("lockup") else None),
            "blocks": [{"role": b["role"], "size": b["size"], "weight": b["weight"],
                        "lines": b["lines"],
                        "fill": b["fill"], "contrast": round(b["contrast"], 2),
                        "achieved": round(b["achieved"], 2),
                        "scrimmed": b["scrimmed"],
                        "required": b["required"]} for b in r["blocks"]],
            "scrims": [{"for": s["for"], "alpha": round(s["alpha"], 3)} for s in r["scrims"]],
        }
        # Solo el backend de constraints: el template elegido, los constraints tal
        # como se aplicaron y las violaciones medidas. La regla de justicia 2 pide
        # que salgan impresos en el artefacto para que cualquiera los audite.
        if r.get("template"):
            entry["template"] = r["template"]
            entry["constraints"] = r["constraints"]
            entry["violations"] = r["violations"]
            entry["inherited"] = r["inherited"]
        manifest["outputs"].append(entry)

    # Los pesos de fuente se derivan de lo RESUELTO, no de una lista fija. Con la
    # lista fija, un master con un peso fuera de ella emitia un @font-face hacia un
    # TTF que nunca se copiaba: el navegador caia a la fuente de sistema en silencio.
    weights = sorted({b["weight"] for r in results for b in r["blocks"]}
                     | ({900} if scene.lockup else set()))
    emit.copy_fonts(out_dir, weights)

    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", default="assets/master.svg")
    ap.add_argument("--formats", default="all",
                    help="'all', 'video', o claves separadas por coma")
    ap.add_argument("--out", default="out/spring-campaign/meridian-quarter")
    ap.add_argument("--sizes", default=None,
                    help="set de tamanos externo, 'AxB,CxD,...' o la ruta de un "
                         "archivo con uno por linea. Sustituye a --formats: sirve "
                         "para correr una hoja de especificaciones ajena sin tocar "
                         "la tabla de formatos")
    ap.add_argument("--photo", default=None,
                    help="sustituye la fotografia del master conservando su estructura. "
                         "Es la prueba de que el layout se DERIVA del arte: mismo "
                         "master, otra foto, otro layout")
    ap.add_argument("--copy-from-photo", action="store_true",
                    help="con --photo: el modelo escribe la copy desde la imagen. "
                         "Los roles, cuerpos y geometria siguen siendo del master")
    ap.add_argument("--no-model-focal", action="store_true",
                    help="no preguntar a un modelo por la region focal aunque las "
                         "cascadas no coincidan; se cae a saliencia")
    ap.add_argument("--backend", default="art", choices=["art", "constraints", "both"],
                    help="'art' decide desde los pixeles; 'constraints' es el "
                         "mecanismo rival; 'both' emite los dos para el cara a cara")
    a = ap.parse_args()

    if a.sizes:
        spec = a.sizes
        if os.path.exists(spec):
            spec = ",".join(l.strip() for l in open(spec) if l.strip()
                            and not l.startswith("#"))
        extra = from_sizes(spec)
        BY_KEY.update({f.key: f for f in extra})
        keys = [f.key for f in extra]
        print(f"set externo: {len(keys)} tamanos, insets simetricos del "
              f"{__import__('formats').GENERIC_INSET:.0%} del lado menor")
    elif a.formats == "all":
        keys = [f.key for f in FORMATS]
    elif a.formats == "video":
        keys = list(VIDEO_ORDER)
    else:
        keys = [k.strip() for k in a.formats.split(",") if k.strip()]
    bad = [k for k in keys if k not in BY_KEY]
    if bad:
        print(f"formatos desconocidos: {bad}", file=sys.stderr)
        return 2

    t0 = time.time()
    scene = parse(a.master)
    print(f"master: {os.path.basename(a.master)}  "
          f"{scene.width:.0f}x{scene.height:.0f}  {len(scene.texts)} bloques de texto"
          f"{', lockup' if scene.lockup else ''}")
    for n in scene.notes:
        print(f"  · {n}")

    if a.photo:
        # Solo se cambia el pixel. Los bloques, sus roles, la jerarquia y el lockup
        # siguen siendo los del master: si el layout se mueve, se mueve por la foto.
        from PIL import Image as _I
        scene.photo.src_path = a.photo
        scene.photo.px_w, scene.photo.px_h = _I.open(a.photo).size
        print(f"  · fotografia sustituida: {os.path.basename(a.photo)} "
              f"{scene.photo.px_w}x{scene.photo.px_h}px")

        # LA COPY DESDE LA FOTOGRAFIA.
        #
        # Solo con --photo, es decir solo cuando la entrada es una foto suelta y no
        # hay copy de nadie que pisar. Con un master -SVG o pieza compuesta- la copy
        # ya existe y no se toca.
        #
        # Se sustituyen las PALABRAS y nada mas: rol, cuerpo del master, peso, caja y
        # jerarquia siguen siendo los del master de referencia. Asi el layout que
        # salga se mueve por la fotografia y por el largo del texto, que es lo que se
        # quiere ensenar, y no porque se haya reordenado la pieza por detras.
        #
        # El aviso legal NO se genera: es texto fijo de marca y no es del modelo
        # escribirlo.
        if a.copy_from_photo:
            try:
                import semantic as _sem
                cd, clog = _sem.copy_from_model(a.photo)
                for l in clog:
                    scene.notes.append("copy · " + l)
                if cd:
                    cambiados = []
                    for b in scene.texts:
                        nuevo = cd["copy"].get(b.role)
                        if nuevo:
                            b.words = nuevo.split()
                            cambiados.append(f"{b.role}=\u201c{nuevo}\u201d")
                    scene.notes.append(
                        "copy escrita por el modelo desde la fotografia: "
                        + "; ".join(cambiados))
                    if cd.get("por_que"):
                        scene.notes.append("por que esa linea: " + cd["por_que"])
                    scene.notes.append(
                        "el aviso legal no se genera: es texto fijo de marca. Los "
                        "roles, los cuerpos y la geometria son los del master")
                    print(f"  · copy desde la foto: "
                          f"{cd['copy'].get('headline','')!r}")
                else:
                    scene.notes.append(
                        "no se pudo escribir copy utilizable desde la fotografia: se "
                        "conserva la del master de referencia")
            except Exception as e:
                scene.notes.append(
                    f"copy desde la fotografia no disponible ({type(e).__name__}): se "
                    f"conserva la del master")

    prep = cropmod.prepare(scene.photo.src_path)

    # LA VIA BARATA PRIMERO, EL MODELO CUANDO NO SABE.
    #
    # Dos cascadas de Haar puestas de acuerdo resuelven una fotografia con una cara
    # de frente en milisegundos y gratis. Cuando no coinciden -gorra y gafas, perfil,
    # o simplemente no hay ninguna cara porque la pieza es una ilustracion, un
    # producto o tipografia sobre un fondo- no hay geometria que consultar: la
    # pregunta "que no se puede recortar" pasa a ser semantica, y ahi si vale pagar
    # una llamada.
    #
    # Es el mismo router que decide todo lo demas en este sistema, y por eso el coste
    # sigue siendo por master y no por formato.
    caras = prep.get("faces") or []
    if prep.get("face") is None and not a.no_model_focal:
        try:
            import semantic
            porque = ("ninguna cara con acuerdo entre las dos cascadas"
                      if not caras else
                      f"{len(caras)} caras con acuerdo: cual sostiene la composicion, "
                      f"o si el sujeto es el grupo entero, no lo dice la geometria")
            scene.notes.append("region focal: " + porque + ". Se pregunta al modelo")
            hint, flog = semantic.focal_from_model(scene.photo.src_path)
            for l in flog:
                scene.notes.append("region focal · " + l)
            if hint:
                prep["face"] = semantic.focal_proxy(
                    hint["rect"], hint["sujeto"], float(prep["px_w"]),
                    float(prep["px_h"]))
                prep["focal_via"] = "modelo"
                # DURA O BLANDA, y lo decide QUE es el sujeto.
                #
                # Las guardas de `crop.choose` acotan el ALTO de la region y estan
                # calibradas sobre una cara. La region de un grupo conserva todo el
                # ancho -es su extension; encogerla deja fuera a la gente de los
                # extremos- asi que ninguna ventana mas estrecha que la fuente la
                # contiene, y la foto degradaba a panel en casi todos los formatos.
                # Medido sobre tres fotos de grupo: panel en 5 de 5, 4 de 5 y 2 de 5.
                #
                # Para un grupo la restriccion correcta no es "contener" sino
                # "conservar la mayor parte", asi que la region entra blanda y la
                # cobertura pasa del filtro al score. El panel sigue apareciendo
                # cuando ni el mejor encuadre conserva lo suficiente, que a 8:1 es
                # justo lo que debe pasar.
                prep["face_hard"] = not semantic.es_extenso(hint["sujeto"])
                scene.notes.append(
                    f"las dos cascadas no coincidieron: la region que no se puede "
                    f"recortar la decidio un modelo. {hint['sujeto']} — "
                    f"{hint['que_es']}, confianza {hint['confianza']:.2f}. "
                    f"{hint['por_que']}")
                if not prep["face_hard"]:
                    scene.notes.append(
                        f"el sujeto es una EXTENSION ancha ({hint['sujeto']}), no una "
                        f"cara: la region se maximiza en lugar de exigirse, y la foto "
                        f"solo degrada a panel si el mejor encuadre conserva menos del "
                        f"{cropmod.SOFT_MIN_COVER:.0%}")
                print(f"  · region focal por modelo: {hint['sujeto']} "
                      f"({hint['confianza']:.2f})"
                      f"{'' if prep['face_hard'] else ' [region blanda]'}")
            elif caras:
                # DEGRADACION, no rendicion. Si el modelo no esta disponible, el
                # conjunto de caras sigue siendo mejor que nada: se conserva su
                # envolvente, que es la lectura literal de "no cortar a nadie".
                # Es peor que preguntar -no sabe quien importa- y mejor que ignorar
                # que hay gente. Y se dice cual de las dos cosas ocurrio.
                x0 = min(f[0] for f in caras); y0 = min(f[1] for f in caras)
                x1 = max(f[0] + f[2] for f in caras)
                y1 = max(f[1] + f[3] for f in caras)
                prep["face"] = (x0, y0, x1 - x0, y1 - y0)
                prep["focal_via"] = "envolvente"
                # La envolvente de varias caras es, por construccion, una extension
                # ancha. Exigirla entera manda a panel por la misma razon geometrica
                # que el grupo del modelo, y aqui sabemos aun menos, asi que exigir
                # mas seria al reves.
                prep["face_hard"] = len(caras) <= 1
                scene.notes.append(
                    f"el modelo no respondio: se usa la envolvente de las {len(caras)} "
                    f"caras detectadas. Conserva a todo el mundo, pero no sabe quien "
                    f"sostiene la pieza"
                    + ("" if prep["face_hard"] else
                       "; entra como region blanda, no como restriccion dura"))
            else:
                prep["focal_via"] = "saliencia"
                scene.notes.append("ni las cascadas ni el modelo dieron una region "
                                   "focal utilizable: manda la saliencia")
        except Exception as e:
            prep["focal_via"] = "saliencia"
            scene.notes.append(f"region focal por saliencia: {type(e).__name__}")
    else:
        prep["focal_via"] = "cascadas" if prep.get("face") else "saliencia"
        if prep.get("face"):
            scene.notes.append("una sola cara, y las dos cascadas coinciden: region "
                               "focal resuelta sin llamar a ningun modelo")

    names = ["art", "constraints"] if a.backend == "both" else [a.backend]
    total = 0
    for name in names:
        # El backend rival va a un subdirectorio: la hoja de contactos los enfrenta
        # por clave de formato, y check.py puede correrse sobre cada uno por separado.
        d = a.out if name == "art" else os.path.join(a.out, "constraints")
        print(f"\n[{name}]  -> {d}")
        man = run_backend(name, scene, keys, prep, d, a.master)
        total += len(man["outputs"])

    # El SDK enviá en segundo plano; sin esto un proceso corto se muere antes.
    try:
        import trace as _tr
        _tr.flush()
    except Exception:
        pass
    print(f"\n{total} formatos en {time.time()-t0:.1f}s -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
