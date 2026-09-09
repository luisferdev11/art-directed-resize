# art-directed-resize

A layout engine that adapts one master artwork to many formats by **reading the
photograph**, not by moving boxes according to rules written in advance.

Give it a master (an SVG with an embedded raster, or a flat JPEG with no structure
at all) and it produces every format in one pass: each one cropped, typeset,
colour-corrected and degraded on its own terms, with a stated reason for every
decision.

> Inline documentation and code comments are in Spanish. This README and the
> generated report pages carry the argument in full.

**[See the generated output →](https://luisferdev11.github.io/art-directed-resize/)**

---

## The idea in one line

Template-and-constraints resize moves elements by geometric rules. A constraint
cannot look at the photograph: it does not know where the face is, whether the
text is still legible over what ended up behind it, or that at 8:1 the photograph
should stop bleeding altogether.

This engine searches densely over a **cost field derived from the pixels** of the
photograph, so the layout is decided from the art.

## What it actually does

| | |
|---|---|
| **Infers roles without reading layer names** | headline, subhead, support and legal are deduced from type size, area and relative hierarchy. Rename every layer to `Layer 1` and nothing changes. |
| **Crops with the subject as a hard constraint** | dense search over 7 scales x 13 x 13 positions, with a minimum and a maximum subject scale. |
| **Places text by search, not by anchors** | the cost field combines saliency, local luminance variance and gradient. The face region is excluded outright. |
| **Measures contrast, per line** | WCAG luminance by percentiles. Where a line falls short, the minimum scrim alpha is found by compositing in sRGB, which is where SVG actually composites. |
| **Degrades in a stated ladder** | tighten leading, re-express hierarchy in weight, drop the legal, drop the support. When no bleed crop can hold the subject, the photograph becomes a side panel and the brand field is promoted. |
| **Emits editable SVG** | one `<text>` per line with absolute baselines, fonts alongside the artwork. It opens in a design tool with its layers and its text intact. |
| **Verifies what it delivered** | `check.py` re-parses the emitted SVG and re-measures everything from the file, not from what the solver believed it wrote. |

## Two input adapters, one model

`Scene` is the only seam in the system. SVG is an adapter at both ends, and a flat
raster is a second adapter in front of the same model:

```
master.svg   ->  parse_svg.py   -\
                                  >-- Scene -->  solve.py  -->  emit.py  -->  *.svg
master.jpg   ->  semantic.py    -/                   ^
                                                     |
                              constraints.py --------+   (the rival mechanism,
                                                          same Scene, same emitter)
```

For a flat JPEG there is nothing to parse: zero text nodes, zero roles, zero
hierarchy. A multimodal model reads the piece and returns the semantic scene; the
**pixels and the font metrics** then measure where everything is and how big it is.
The model classifies by communicative function, which is the one thing only a model
can do here. The burned-in text is removed with classical inpainting so the
photograph can be re-composed underneath.

## Results, measured

Every number below is produced by a script in `tools/` and appears in the
generated pages.

**Role assignment** — 3 masters, 12 assignments, **N=3, declared**:
ranking by font size gets **9/12**; reading the piece gets **12/12**. The gap is
one constructed case: a legal notice set in large type, which happens constantly in
regulated promotions. Ranking by size gets 1 of 4 there.

**Changing the photograph** — same master, three photographs. By the constraints
route the only thing that changes is which pixels get cropped: type sizes, colours,
scrims, dropped elements and logo variant are identical across all five formats. By
the art route, the crop changes in 5 of 5, the scrims in 4 of 5, the colours in 3 of
5 and the type sizes in 3 of 5.

**Head to head** — the same independent validator over both backends: this engine
passes 8 of 8; a faithful template-and-constraints resize fails 7 of 8, with zero
violations on exactly the three formats whose size matches a template. That is the
honest claim: it works while the target resembles a template.

## Running it

```bash
pip install -r requirements.txt        # opencv-CONTRIB, not opencv-python

./run.py --backend both                # 8 formats, both layout backends
./check.py                             # re-parse and validate what was written
python3 tools/face_off.py  out/spring-campaign/meridian-quarter
python3 tools/swap_test.py             # same master, three photographs
python3 tools/rollout.py               # one self-contained folder per centre
python3 tools/golden.py                # role assignment, size ranking vs model

./run.py --master assets/master-flat.jpg --formats video \
         --out out/spring-campaign/meridian-flat     # from a flat JPEG
```

The AI path needs a key in `.env` (see `.env.example`). Everything else is local
and deterministic.

## What this is not

It is a layout engine, not a product. It does not orchestrate campaigns, group or
name assets in bulk, export video, or round-trip through a design tool's plugin
API. Copy does not vary per centre. There is no UI: the report pages are generated
static files.

Adding a format is adding a row in `src/formats.py`. The degradation ladder is a
list in `src/brand.py`, shown as-is in the output.

## Provenance

Photography and brand are declared in [`assets/LICENSES.md`](assets/LICENSES.md).
MERIDIAN QUARTER, Harbourside Plaza and Northgate Centre are invented names.
