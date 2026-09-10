#!/usr/bin/env python3
"""Genera docs/evolution.html: como cambio el motor entre versiones.

POR QUE ESTA PAGINA EXISTE. El resto del sitio ensena lo que el motor hace HOY. Lo
que no se ve en ninguna parte es que cada decision del diseno salio de una falla
concreta y medida, y que varias veces la primera version estuvo mal. Eso es lo que
distingue "lo pense" de "lo probe", y es lo unico que no se puede improvisar en una
entrevista.

REGLA DE HONESTIDAD DE ESTE ARCHIVO: cada etapa lleva el SHA del commit que la
introdujo, y el script COMPRUEBA que existe en el historial. Si un commit se
reescribe o desaparece, la pagina no se genera. No hay una sola cifra escrita aqui
que no venga de un commit, de un manifest o de una medicion que dejo su rastro.

Y lo que NO se hace: contar el arco mas bonito. El multimodal no llego "despues del
detector de caras" -estaba en el primer commit, leyendo la escena de un JPEG plano-.
Lo que evoluciono fue DONDE MAS se usa. Ordenarlo al reves seria mas limpio y seria
falso.
"""
from __future__ import annotations
import html
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nav                                                    # noqa: E402

DEST = os.path.join(ROOT, "out", "spring-campaign")

# (sha, fecha, titulo, que habia antes, que lo rompio, que se hizo, lo medido)
ETAPAS = [
    ("d0ec4b7", "day 1",
     "The deterministic engine, and the largest box wins",
     "Nothing. This is the floor: dense search over a cost field derived from the "
     "pixels, type fitted in closed form, contrast measured per line, and an "
     "editable SVG out. The multimodal path for a flat JPEG is already here, "
     "reading the scene by communicative function.",
     "The focal region was <em>the largest detection</em> from either of two Haar "
     "cascades, taken as a union. The code's own docstring already admitted a false "
     "positive on the reflecting pool.",
     "Shipped as the baseline. Everything below is a failure found afterwards.",
     "Role assignment: ranking by font size 9/12, reading the piece 12/12, N=3 "
     "declared."),
    ("ac88b8a", "day 2 · 10:20",
     "Two cascades have to agree, and the model answers when they do not",
     "One box, the biggest, treated as certainty.",
     "A subject in a cap and sunglasses in front of a building: the two cascades "
     "returned <strong>eight detections and not one was a face</strong> — a "
     "wristwatch, windows in the facade, poles on grass. The largest sat at 94% of "
     "the width, and because the focal region is a <em>hard</em> crop constraint, "
     "every format cut the subject in half.",
     "A face counts only when both cascades agree — an ensemble of two "
     "independently trained detectors, not a threshold fitted to the cases at hand. "
     "When they do not agree the question goes to a model, asked as <em>what must "
     "not be cropped, and what is it</em> rather than <em>where is the face</em>.",
     "Over four photographs, the three with a real subject agree at IoU 0.79 to "
     "0.93; the failing one produces no agreement at all."),
    ("f206a8b", "day 2 · 11:08",
     "Doubt escalates: zero agreements, or several, is not an answer",
     "Agreement fixed the false positive. Several agreements did not.",
     "A group photograph produced <strong>eleven corroborated faces spanning 31% to "
     "69% of the width</strong>. Taking the largest pins the crop to one person and "
     "cuts the rest of the team out of frame. Which face carries the composition, "
     "or whether the subject is the group itself, is a compositional judgement.",
     "The cheap path answers only when there is no doubt: exactly one agreed face. "
     "Zero, or several, is a declaration that this detector cannot say, and the "
     "question escalates. The temptation was a clusterer with its own thresholds — "
     "that would have been my judgement dressed as measurement.",
     "The schema was too narrow and the model said so: it answered "
     "<code>sujeto=\"grupo\"</code>, the value was not on the list, and the chain "
     "spent fourteen seconds falling through to the next provider. The answer was "
     "correct."),
    ("bc3a0f1", "day 2 · 12:57",
     "A group's region is preserved, not required",
     "Escalation worked. What came back was then fed to a guard calibrated on a "
     "single face.",
     "A group's region keeps the subject's full width — shrinking it drops the "
     "people at the edges — and the crop guard demands containment at 99.5%. No "
     "window narrower than the source can satisfy that, so the constraint was "
     "unsatisfiable <em>by geometry</em> and the photograph degraded to a side "
     "panel almost everywhere.",
     "For a wide extent the right constraint is not <em>contain</em> but "
     "<em>keep most of</em>: coverage leaves the filter and enters the score with a "
     "weight above saliency mass. The panel still appears when even the best crop "
     "keeps too little, which at 8:1 is exactly what should happen.",
     "Measured on three group photographs before: panel in <strong>5 of 5, 4 of 5 "
     "and 2 of 5</strong> formats. After: <strong>4 of 5, 1 of 5 and 2 of 5</strong>."),
    ("aa128ec", "day 2 · 13:54",
     "The list was wrong, and for the worst reason",
     "Which subjects get the soft treatment was a hand-written list: group, "
     "building, landscape, typography.",
     "It left out <code>ilustracion</code>, which falls in the same full-width "
     "branch — and it left it out because the run in front of me had come out fine. "
     "It came out fine for another reason: the model had labelled that illustration "
     "<code>persona</code>. Same image, another run, answered "
     "<code>ilustracion</code> and it degraded to a panel in 3 of 5 formats. "
     "<strong>Picking the label is not deterministic and the code cannot depend on "
     "it landing on the good side.</strong>",
     "The rule is now derived from the mechanism, not from the cases I had seen: of "
     "the three branches that reshape the model's box, only <code>persona</code> "
     "returns something compact. Hard containment applies to that and nothing else.",
     "With the label that broke it: 4:5 goes from panel to bleed at 73% coverage, "
     "1:1 at 91%, and 9:16 and 8:1 stay on the panel. With "
     "<code>persona</code> the result is byte-identical either way — which is why "
     "the 8 formats and the 66 sizes did not move."),
    ("aa128ec", "day 2 · 13:54",
     "Text painted inside the photograph is not campaign copy",
     "A composed piece is routed by asking the model whether copy is overlaid.",
     "An advertisement with <em>DRINK Coca-Cola / Delicious and Refreshing</em> "
     "<strong>painted on the side of a truck</strong>: the model read it as the "
     "headline, the inpainting left blurred smears across the vehicle in all five "
     "formats, and then wrote it back as live text on top — so the MPU read it "
     "twice.",
     "The prompt already states the rule, so sharpening it with this photograph "
     "would be fitting it to the case in front of me. Instead the claim is "
     "corroborated against the other answer the model gives in the same call: where "
     "the subject is. Overlaid copy sits <em>outside</em> the subject — that is what "
     "makes it legible. Photographed text sits <em>inside</em>. It matters that this "
     "is a guard and not a better prompt, because the failure is destructive: "
     "inpainting does not undo.",
     "On the truck the headline falls <strong>100% inside</strong> the subject "
     "region, so the piece enters as a photograph and survives intact. The "
     "regression that had to pass: the legitimate flat master, where copy really is "
     "overlaid, still reads its four roles and inpaints as before."),
    ("1652e7a", "day 2 · 14:30",
     "A bare photograph carries no copy, so the model writes it",
     "A loose photograph got the reference master's headline pasted onto it.",
     "It was the only thing in the demo that did not come from the input. On the "
     "truck advertisement <em>SPRING STYLE IS HERE</em> landed on top of the "
     "vehicle's own lettering: two messages competing.",
     "With <code>--photo</code> only — where there is no one's copy to overwrite — "
     "the model writes headline, subhead and support from the image. Words and "
     "nothing else: role, master body size, weight, case and hierarchy stay the "
     "master's, so the layout moves because of the photograph and the length of the "
     "text, not because the piece was quietly rearranged. The legal line is not "
     "generated: it is fixed brand text. Word limits per role are a "
     "<em>layout</em> constraint, not a style one, and the validator enforces them.",
     "On the truck the 4:5 cost drops from <strong>0.85 to 0.40</strong> — a "
     "headline that fits finds somewhere to go. On the Taj Mahal photograph it "
     "wrote <em>“Your escape begins here”</em>, with costs from 0.007 to 0.11."),
    ("1652e7a", "day 2 · 14:30",
     "The output is an input: the real use case",
     "Two entry points: an SVG master, or a flat raster.",
     "The real job is not <em>image → formats</em>. It is <em>campaign component → "
     "rollout</em>, and the demo had drifted away from it.",
     "An SVG carries its own structure — text nodes, a raster, a vector lockup — "
     "which is exactly what the parser consumes, so it enters as a master with no "
     "question asked of any model. The SVGs this engine emits work as input: the "
     "pipeline pointed at its own output. The Figma component becomes a third "
     "adapter in front of the same <code>Scene</code>, not a new pipeline.",
     "Verified end to end through the browser demo: 5 formats, validator green, and "
     "the focal region resolved by the cascades with no model call. One honest cost: "
     "each round trip re-crops and re-embeds the raster, so resolution decays per "
     "generation — on a 640×360 illustration it falls to 14 effective ppi, and the "
     "engine says so."),
]


def _shas_validos() -> set:
    out = subprocess.run(["git", "log", "--format=%h"], cwd=ROOT,
                         capture_output=True, text=True)
    return set(out.stdout.split())


def build(d: str = DEST) -> str:
    vivos = _shas_validos()
    faltan = sorted({s for s, *_ in ETAPAS} - vivos)
    if faltan:
        raise SystemExit(
            "evolution.py: estos commits ya no estan en el historial y la pagina no "
            "se genera hasta que se corrijan: " + ", ".join(faltan))

    filas = []
    for i, (sha, fecha, titulo, antes, rompio, hizo, medido) in enumerate(ETAPAS, 1):
        filas.append(f"""
<section class="stage">
 <div class="stage-h">
  <span class="n">{i:02d}</span>
  <div>
   <h2>{titulo}</h2>
   <p class="meta"><code>{sha}</code> &middot; {html.escape(fecha)}</p>
  </div>
 </div>
 <dl>
  <dt>Before</dt><dd>{antes}</dd>
  <dt>What broke it</dt><dd>{rompio}</dd>
  <dt>What changed</dt><dd>{hizo}</dd>
  <dt class="m">Measured</dt><dd class="m">{medido}</dd>
 </dl>
</section>""")

    doc = f"""<!doctype html><meta charset="utf-8">
<title>How it changed &middot; art-directed-resize</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 :root{{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8;--mut:#5d6b66}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--pap);color:var(--ink);
   font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
 .wrap{{max-width:860px;margin:0 auto;padding:40px 22px 90px}}
 h1{{font-size:32px;line-height:1.15;margin:0 0 6px;letter-spacing:-.02em}}
 .sub{{color:var(--mut);margin:0 0 30px;font-size:15.5px}}
 .lede{{border-left:3px solid var(--acc);padding:2px 0 2px 16px;margin:0 0 34px;
   font-size:15px;color:#3b4a45}}
 .stage{{border-top:1px solid var(--line);padding:26px 0 4px}}
 .stage-h{{display:flex;gap:14px;align-items:baseline}}
 .n{{font:600 13px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--acc);
   padding-top:6px}}
 h2{{font-size:20.5px;line-height:1.25;margin:0;letter-spacing:-.01em}}
 .meta{{margin:4px 0 0;color:var(--mut);font-size:12.5px}}
 dl{{margin:16px 0 0;padding:0 0 0 34px}}
 dt{{font-size:11.5px;letter-spacing:.09em;text-transform:uppercase;
   color:var(--mut);margin:14px 0 4px}}
 dt:first-child{{margin-top:0}}
 dd{{margin:0;font-size:14.5px}}
 dt.m{{color:var(--acc)}}
 dd.m{{background:#fff;border:1px solid var(--line);border-radius:6px;
   padding:10px 13px;font-size:14px}}
 code{{font:12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
   background:#fff;border:1px solid var(--line);border-radius:4px;padding:1px 5px}}
 footer{{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
   color:var(--mut);font-size:12.5px}}
 @media(max-width:560px){{dl{{padding-left:0}} h1{{font-size:26px}}}}
{nav.CSS}</style>
<div class="wrap">
{nav.render(d, "evolution.html")}
<h1>How it changed</h1>
<p class="sub">Eight steps, each one a failure that was measured first.</p>

<p class="lede">Every other page here shows what the engine does now. This one shows
 that each decision came out of a concrete failure, and that more than once the first
 version was wrong &mdash; twice for the same reason, which is that I generalised from
 the cases in front of me. Every stage carries the SHA of the commit that introduced
 it, and the generator refuses to build this page if a commit is missing from the
 history.<br><br>
 One thing is deliberately not tidied up: <strong>the multimodal did not arrive after
 the face detector.</strong> It was in the first commit, reading the scene of a flat
 JPEG by communicative function. What evolved is where <em>else</em> it is used.
 Telling it the other way round would read better and would be false.</p>
{''.join(filas)}
<footer>Generated by <code>tools/evolution.py</code> from the repository history.
 Brand, type and photography declared in <code>assets/LICENSES.md</code>.
 MERIDIAN QUARTER is an invented name.</footer>
</div>
"""
    p = os.path.join(d, "evolution.html")
    with open(p, "w") as fh:
        fh.write(doc)
    print(f"-> {p}  ({len(ETAPAS)} etapas, {len(doc)//1024} KB)")
    return p


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else DEST)
