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
import trace as TR
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


def _trace_decision(sp, key, fmt, r, src_w):
    """Vuelca la decision del solver al span, en la forma en que se audita.

    No es el manifest volcado tal cual: se ordena por PREGUNTA. Que region de la
    fotografia sobrevive, cuanto se amplio, donde aterrizo el texto y por que, que
    se retiro. Quien abre esto quiere responder "por que salio asi", no leer un
    volcado de estructuras.
    """
    if r.get("failed"):
        sp.update(level="WARNING", status_message="no valid layout",
                  output={"failed": True, "reasons": r.get("reasons") or []})
        return

    cx, cy, cw, ch = r["crop_px"]
    zoom = (fmt.w / cw) if cw else 0.0
    out = {
        "hypothesis": r["hypothesis"],
        "crop": {"rect_px": [round(v) for v in r["crop_px"]],
                 "share_of_source_width": round(cw / max(src_w, 1), 3),
                 "scale_to_canvas": round(zoom, 3),
                 "effective_ppi": round(r["ppi"], 1)},
        "text": {"placement_cost_0_1": round(r["cost"], 4),
                 "blocks": [{"role": b["role"], "size_px": b["size"],
                             "weight": b["weight"], "lines": b["lines"],
                             "fill": b["fill"],
                             "contrast": round(b["achieved"], 2),
                             "required": b["required"],
                             "scrimmed": b["scrimmed"]} for b in r["blocks"]],
                 "scrims": [{"behind": s["for"], "alpha": round(s["alpha"], 3)}
                            for s in r["scrims"]]},
        "degradation": {"ladder": r.get("ladder") or [],
                        "dropped": r.get("dropped") or []},
        "panel": [round(v) for v in r["panel"]] if r.get("panel") else None,
        "logo": ({"width_px": round(r["lockup"]["rect"][2], 1),
                  "scale": round(r["lockup"]["scale"], 3),
                  "mark_only": r["lockup"]["mark_only"]} if r.get("lockup") else None),
        "why": r["reasons"],
    }
    if r.get("violations") is not None:
        out["violations"] = r["violations"]
        out["template"] = r.get("template")
    sp.update(output=out, metadata={
        "hypothesis": r["hypothesis"],
        "degraded": bool(r.get("ladder")),
        "dropped_any": bool(r.get("dropped")),
        "under_72_ppi": r["ppi"] < 72.0,
        "n_reasons": len(r["reasons"])})
    # El coste del emplazamiento es la unica cifra del solver que se puede seguir en
    # el tiempo: dice cuanto tuvo que pelear el texto para encontrar sitio.
    sp.score("placement_cost", round(r["cost"], 4), r["hypothesis"])


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

        # UN SPAN POR FORMATO, CON LA DECISION ENTERA.
        #
        # Hasta aqui la observabilidad cubria las llamadas al modelo y nada mas, que
        # es justo la parte mas barata de explicar: el modelo contesta que no se puede
        # recortar, y TODO lo demas -que region se recorta, cuanto zoom, donde cae el
        # texto, que se retira- lo decide codigo determinista. Esas decisiones viajaban
        # solo en el manifest.
        #
        # El argumento del sistema es que cada decision lleva su razon medida. Si esas
        # razones no estan en la herramienta donde se audita, el argumento existe pero
        # no se puede comprobar. Asi que el span lleva el recorte, la hipotesis, el
        # coste, el emplazamiento, los scrims, la escalera y las razones en prosa.
        with TR.Span(f"layout:{key}", input={
                "format": {"key": key, "label": fmt.label,
                           "canvas": f"{fmt.w}x{fmt.h}",
                           "aspect": round(fmt.aspect, 3)},
                "source": {"pixels": f"{prep['px_w']}x{prep['px_h']}",
                           "aspect": round(prep["px_w"] / max(prep["px_h"], 1), 3)},
                "focal_region": ({"rect": [round(v) for v in prep["face"]],
                                  "resolved_by": prep.get("focal_via", "cascades"),
                                  "hard_constraint": bool(prep.get("face_hard", True))}
                                 if prep.get("face") else None),
                "backend": name}) as _sp:
            r = solver(scene, fmt, prep)
            _trace_decision(_sp, key, fmt, r, prep["px_w"])

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
                    help="'all', 'video', or comma-separated keys")
    ap.add_argument("--out", default="out/spring-campaign/meridian-quarter")
    ap.add_argument("--sizes", default=None,
                    help="external size set, 'AxB,CxD,...' or the path to a file "
                         "with one per line. Replaces --formats: it runs somebody "
                         "else's spec sheet without touching the format table")
    ap.add_argument("--photo", default=None,
                    help="swap the master's photograph, keeping its structure. It is "
                         "the proof that the layout is DERIVED from the art: same "
                         "master, another photograph, another layout")
    ap.add_argument("--copy-from-photo", action="store_true",
                    help="with --photo: the model writes the copy from the image. "
                         "Roles, body sizes and geometry stay the master's")
    ap.add_argument("--focal-json", default=None,
                    help="region focal YA resuelta, en JSON. Quien llama -el demo- "
                         "puede haberla pedido para otra cosa; volver a preguntarla "
                         "es pagar dos veces la misma respuesta")
    ap.add_argument("--no-model-focal", action="store_true",
                    help="do not ask a model for the focal region even if the "
                         "cascades disagree; fall back to saliency")
    ap.add_argument("--backend", default="art", choices=["art", "constraints", "both"],
                    help="'art' decides from the pixels; 'constraints' is the rival "
                         "mechanism; 'both' emits the pair for the head to head")
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
                        "copy written by the model from the photograph: "
                        + "; ".join(cambiados))
                    if cd.get("why"):
                        scene.notes.append("why that line: " + cd["why"])
                    scene.notes.append(
                        "the legal line is not generated: it is fixed brand text. The "
                        "roles, the body sizes and the geometry are the master's")
                    print(f"  · copy desde la foto: "
                          f"{cd['copy'].get('headline','')!r}")
                else:
                    scene.notes.append(
                        "no usable copy could be written from the photograph: the "
                        "reference master's copy is kept")
            except Exception as e:
                scene.notes.append(
                    f"copy from the photograph unavailable ({type(e).__name__}): the "
                    f"master's copy is kept")

    prep = cropmod.prepare(scene.photo.src_path)

    # LA TRAZA DE LA CAMPANA, ETIQUETADA ARRIBA DEL TODO.
    #
    # Las llamadas al modelo cuelgan de aqui, y tambien las decisiones de layout de
    # cada formato. Sin esto la traza se llama como la ultima cosa que se instrumento
    # y no se sabe de que corrida viene.
    try:
        TR.trace_meta(
            name=f"campaign:{os.path.splitext(os.path.basename(a.master))[0]}",
            tags=["campaign", a.backend],
            input={"master": os.path.basename(a.master),
                   "photo": os.path.basename(scene.photo.src_path),
                   "source_pixels": f"{prep['px_w']}x{prep['px_h']}",
                   "formats": keys,
                   "text_blocks": [b.role for b in scene.texts]})
    except Exception:
        pass

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

    # LA REGION FOCAL YA RESUELTA POR QUIEN LLAMA.
    #
    # El demo pregunta al modelo una vez para decidir por que puerta entra el archivo
    # -si lleva copy sobrepuesto o es una fotografia-, y esa MISMA respuesta trae la
    # region focal. Volver a preguntarla aqui era pagar dos veces por lo mismo: nueve
    # segundos medidos, sobre un total de setenta y dos.
    hint_pre = None
    if a.focal_json and os.path.exists(a.focal_json):
        try:
            with open(a.focal_json) as fh:
                hint_pre = json.load(fh)
            if not (isinstance(hint_pre, dict) and hint_pre.get("rect")):
                hint_pre = None
        except Exception:
            hint_pre = None

    if prep.get("face") is None and hint_pre:
        import semantic
        prep["face"] = semantic.focal_proxy(
            hint_pre["rect"], hint_pre["subject"], float(prep["px_w"]),
            float(prep["px_h"]))
        prep["focal_via"] = "model"
        prep["face_hard"] = not semantic.es_extenso(hint_pre["subject"])
        scene.notes.append(
            f"region focal reutilizada de la llamada que decidio la ruta: "
            f"{hint_pre['subject']} — {hint_pre.get('what_it_is','')}, confianza "
            f"{float(hint_pre.get('confidence',0)):.2f}. No se vuelve a preguntar")
        if not prep["face_hard"]:
            scene.notes.append(
                f"the subject is a wide EXTENT ({hint_pre['subject']}), not a face: "
                f"the region is maximised instead of required")
        print(f"  · region focal reutilizada: {hint_pre['subject']} (sin 2a llamada)")
    elif prep.get("face") is None and not a.no_model_focal:
        try:
            import semantic
            porque = ("no face agreed on by the two cascades"
                      if not caras else
                      f"{len(caras)} agreed faces: which one carries the composition, "
                      f"or whether the subject is the group itself, geometry cannot say")
            scene.notes.append("focal region: " + porque + ". The model is asked")
            hint, flog = semantic.focal_from_model(scene.photo.src_path)
            for l in flog:
                scene.notes.append("region focal · " + l)
            if hint:
                prep["face"] = semantic.focal_proxy(
                    hint["rect"], hint["subject"], float(prep["px_w"]),
                    float(prep["px_h"]))
                prep["focal_via"] = "model"
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
                prep["face_hard"] = not semantic.es_extenso(hint["subject"])
                scene.notes.append(
                    f"the two cascades did not agree: the region that must not be "
                    f"cropped was decided by a model. {hint['subject']} — "
                    f"{hint['what_it_is']}, confidence {hint['confidence']:.2f}. "
                    f"{hint['why']}")
                if not prep["face_hard"]:
                    scene.notes.append(
                        f"the subject is a wide EXTENT ({hint['subject']}), not a face: "
                        f"the region is maximised instead of required, and the "
                        f"photograph only degrades to a panel if the best crop keeps "
                        f"less than {cropmod.SOFT_MIN_COVER:.0%} of it")
                print(f"  · region focal por modelo: {hint['subject']} "
                      f"({hint['confidence']:.2f})"
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
                prep["focal_via"] = "envelope-of-agreed-faces"
                # La envolvente de varias caras es, por construccion, una extension
                # ancha. Exigirla entera manda a panel por la misma razon geometrica
                # que el grupo del modelo, y aqui sabemos aun menos, asi que exigir
                # mas seria al reves.
                prep["face_hard"] = len(caras) <= 1
                scene.notes.append(
                    f"the model did not answer: the envelope of the {len(caras)} detected "
                    f"faces is used instead. It keeps everybody, but it does not know "
                    f"who carries the piece"
                    + ("" if prep["face_hard"] else
                       "; it enters as a soft region, not as a hard constraint"))
            else:
                prep["focal_via"] = "saliency"
                scene.notes.append("neither the cascades nor the model produced a "
                                   "usable focal region: saliency decides")
        except Exception as e:
            prep["focal_via"] = "saliency"
            scene.notes.append(f"focal region by saliency: {type(e).__name__}")
    else:
        prep["focal_via"] = "agreed-cascades" if prep.get("face") else "saliency"
        if prep.get("face"):
            scene.notes.append("exactly one face, and the two cascades agree: the "
                               "focal region is settled without calling any model")

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
