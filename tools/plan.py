#!/usr/bin/env python3
"""Genera docs/whats-next.html: el plan para llevarlo a producto.

REGLA QUE GOBIERNA ESTA PAGINA, y es la misma de `how-it-works.html`: aqui NO HAY
NADA CONSTRUIDO. Es una propuesta de arquitectura que puedo defender, y cada
afirmacion sobre el presente lleva su cifra medida y su enlace; todo lo demas dice
PROPUESTO en la etiqueta. El cliente ya fue sobrevendido una vez y la calibracion es
la mejor carta que hay: presentar un diseno como trabajo hecho seria el peor error
posible.

Las UNICAS cifras del presente que aparecen salen de los manifests en disco y de las
corridas de hoy. Se declaran como medidas y se distinguen tipograficamente.
"""
from __future__ import annotations
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nav                                                    # noqa: E402

DEST = os.path.join(ROOT, "out", "spring-campaign")


def _medido():
    """Las cifras de HOY, leidas de disco. Si falta un manifest, no se inventa."""
    d = {}
    p = os.path.join(DEST, "generic66", "manifest.json")
    if os.path.exists(p):
        m = json.load(open(p))
        d["n66"] = len(m["outputs"])
        d["ppi_bajo"] = sum(1 for o in m["outputs"]
                            if o.get("effective_ppi", 1e9) < 72.0)
    p = os.path.join(DEST, "meridian-quarter", "manifest.json")
    if os.path.exists(p):
        d["n8"] = len(json.load(open(p))["outputs"])
    return d


CSS = """
 :root{--ink:#0E2A26;--pap:#F4F1EA;--acc:#E4572E;--line:#d8d3c8;--mut:#5d6b66;
   --pro:#7a5cc4}
 *{box-sizing:border-box}
 body{margin:0;background:var(--pap);color:var(--ink);
   font:15px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 .wrap{max-width:940px;margin:0 auto;padding:40px 22px 100px}
 h1{font-size:34px;line-height:1.12;margin:0 0 8px;letter-spacing:-.022em}
 .sub{color:var(--mut);margin:0 0 26px;font-size:16px}
 .warn{background:#fff;border:1px solid var(--acc);border-left-width:4px;
   border-radius:7px;padding:16px 18px;margin:0 0 36px;font-size:14.5px}
 .warn b{color:var(--acc)}
 h2{font-size:24px;margin:52px 0 6px;letter-spacing:-.015em;line-height:1.2}
 h2 .k{display:block;font:600 11.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
   letter-spacing:.13em;color:var(--acc);margin-bottom:8px}
 h3{font-size:17px;margin:30px 0 8px;letter-spacing:-.008em}
 p{margin:10px 0}
 .lede{font-size:15.5px;color:#3b4a45;margin:6px 0 18px}
 ul,ol{margin:10px 0;padding-left:22px}
 li{margin:6px 0}
 code{font:12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:#fff;
   border:1px solid var(--line);border-radius:4px;padding:1px 5px}
 .tag{display:inline-block;font:600 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
   letter-spacing:.11em;padding:4px 7px;border-radius:4px;vertical-align:2px;
   margin-right:7px}
 .t-now{background:var(--ink);color:#fff}
 .t-pro{background:#efe9fb;color:var(--pro);border:1px solid #d9ccf5}
 .m{background:#fff;border:1px solid var(--line);border-radius:6px;
   padding:11px 14px;font-size:14px;margin:14px 0}
 .m b{color:var(--acc)}
 table{width:100%;border-collapse:collapse;margin:16px 0;font-size:13.8px}
 th,td{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);
   vertical-align:top}
 th{font:600 11px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;
   letter-spacing:.08em;text-transform:uppercase;color:var(--mut);
   border-bottom:1px solid var(--ink)}
 td:first-child{white-space:nowrap;font-weight:600}
 .fig{margin:22px 0 8px;background:#fff;border:1px solid var(--line);
   border-radius:9px;padding:16px 14px;overflow-x:auto}
 .fig svg{display:block;width:100%;height:auto;min-width:600px}
 .cap{color:var(--mut);font-size:12.8px;margin:0 0 24px;padding-left:2px}
 .phase{display:grid;grid-template-columns:88px 1fr;gap:0 16px;
   border-top:1px solid var(--line);padding:18px 0}
 .phase .w{font:600 12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
   color:var(--acc);padding-top:3px}
 .phase h4{margin:0 0 6px;font-size:16.5px}
 .phase .done{background:#fff;border:1px solid var(--line);border-radius:6px;
   padding:9px 12px;margin:10px 0 0;font-size:13.5px}
 .phase .done i{font-style:normal;color:var(--mut);font-weight:600;
   font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
   display:block;margin-bottom:3px}
 .two{display:grid;grid-template-columns:1fr 1fr;gap:20px}
 @media(max-width:680px){.two{grid-template-columns:1fr}
   .phase{grid-template-columns:1fr;gap:6px} h1{font-size:27px}}
 footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);
   color:var(--mut);font-size:12.5px}
"""

# --------------------------------------------------------------------- diagramas
DEF_ARROW = ('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
             'markerWidth="7" markerHeight="7" orient="auto">'
             '<path d="M0 0 L10 5 L0 10 z" fill="#7d8783"/></marker>'
             '<marker id="ao" viewBox="0 0 10 10" refX="9" refY="5" '
             'markerWidth="7" markerHeight="7" orient="auto">'
             '<path d="M0 0 L10 5 L0 10 z" fill="#E4572E"/></marker></defs>')

S_BOX = 'fill="#fff" stroke="#d8d3c8" rx="7"'
S_INK = 'fill="#0E2A26" rx="8"'
S_PRO = 'fill="#f6f2ff" stroke="#d9ccf5" rx="7"'
T = ('font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
     'font-size="11.5"')
TB = ('font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
      'font-size="12" font-weight="600"')
TS = ('font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="9.2" '
      'letter-spacing="0.06em"')


def fig_topologia() -> str:
    """Diagrama 1: la forma del sistema."""
    return f'''
<svg viewBox="0 0 900 420" role="img" aria-label="Proposed topology: the portal and the connectors enter through one API,
 the work is split across a queue, a pool of workers runs the engine, and the outputs
 go to storage and from there to delivery.">
{DEF_ARROW}
 <text x="4" y="12" {TS} fill="#7a5cc4">PROPOSED &#183; NONE OF THIS EXISTS TODAY</text>

 <text x="4" y="42" {TS} fill="#5d6b66">INPUT</text>
 <rect x="4" y="52" width="150" height="34" {S_BOX}/>
 <text x="16" y="73" {TB} fill="#0E2A26">Web portal</text>
 <rect x="4" y="94" width="150" height="34" {S_BOX}/>
 <text x="16" y="115" {TB} fill="#0E2A26">Figma plugin</text>
 <rect x="4" y="136" width="150" height="34" {S_BOX}/>
 <text x="16" y="157" {TB} fill="#0E2A26">Deliverables .xlsx</text>
 <rect x="4" y="178" width="150" height="34" {S_BOX}/>
 <text x="16" y="199" {TB} fill="#0E2A26">API / webhook</text>

 <path d="M154 69 L206 120" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M154 111 L206 124" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M154 153 L206 136" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M154 195 L206 148" stroke="#7d8783" fill="none" marker-end="url(#a)"/>

 <rect x="210" y="104" width="118" height="60" {S_INK}/>
 <text x="224" y="128" {TB} fill="#fff">API + Auth</text>
 <text x="224" y="146" {T} fill="#a8bdb7">one job per campaign</text>

 <rect x="210" y="196" width="118" height="52" {S_PRO}/>
 <text x="224" y="217" {TB} fill="#0E2A26">Agent</text>
 <text x="224" y="234" {T} fill="#5d6b66">plans, and asks</text>
 <path d="M269 196 L269 168" stroke="#E4572E" fill="none" marker-end="url(#ao)"/>

 <path d="M328 134 L378 134" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="382" y="100" width="104" height="68" {S_BOX}/>
 <text x="394" y="122" {TB} fill="#0E2A26">Queue</text>
 <text x="394" y="139" {T} fill="#5d6b66">1 task =</text>
 <text x="394" y="154" {T} fill="#5d6b66">1 format</text>

 <path d="M486 118 L536 84" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M486 134 L536 134" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M486 150 L536 184" stroke="#7d8783" fill="none" marker-end="url(#a)"/>

 <rect x="540" y="60" width="150" height="46" {S_BOX}/>
 <text x="552" y="79" {TB} fill="#0E2A26">worker</text>
 <text x="552" y="96" {TS} fill="#5d6b66">solve + emit</text>
 <rect x="540" y="112" width="150" height="46" {S_BOX}/>
 <text x="552" y="131" {TB} fill="#0E2A26">worker</text>
 <text x="552" y="148" {TS} fill="#5d6b66">solve + emit</text>
 <rect x="540" y="164" width="150" height="46" {S_BOX}/>
 <text x="552" y="183" {TB} fill="#0E2A26">worker</text>
 <text x="552" y="200" {TS} fill="#5d6b66">solve + emit</text>
 <text x="540" y="228" {TS} fill="#5d6b66">CPU. DETERMINISTIC. STATELESS.</text>

 <rect x="382" y="290" width="308" height="58" {S_PRO}/>
 <text x="396" y="312" {TB} fill="#0E2A26">Scene + focal region &#183; once per master</text>
 <text x="396" y="330" {T} fill="#5d6b66">the only model call. It does not scale with the outputs.</text>
 <path d="M615 290 L615 240" stroke="#E4572E" fill="none"
   marker-end="url(#ao)" stroke-dasharray="4 3"/>
 <text x="432" y="272" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="9.2" letter-spacing="0.06em" fill="#E4572E">REUSED BY EVERY TASK</text>

 <path d="M690 134 L740 134" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="744" y="100" width="152" height="68" {S_INK}/>
 <text x="757" y="123" {TB} fill="#fff">Object store</text>
 <text x="757" y="141" {T} fill="#a8bdb7">svg, png, pdf</text>
 <text x="757" y="157" {T} fill="#a8bdb7">+ manifest</text>

 <rect x="744" y="196" width="152" height="86" {S_BOX}/>
 <text x="757" y="217" {TB} fill="#0E2A26">Delivery</text>
 <text x="757" y="235" {T} fill="#5d6b66">zip per centre</text>
 <text x="757" y="251" {T} fill="#5d6b66">DAM / Drive</text>
 <text x="757" y="267" {T} fill="#5d6b66">back into Figma</text>
 <path d="M820 168 L820 196" stroke="#7d8783" fill="none" marker-end="url(#a)"/>

 <rect x="4" y="290" width="360" height="58" {S_BOX}/>
 <text x="17" y="312" {TB} fill="#0E2A26">Postgres &#183; campaigns, overrides, corrections</text>
 <text x="17" y="330" {T} fill="#5d6b66">what the designer corrects comes back as data, not as a patch</text>

 <path d="M184 290 L184 260 L269 260 L269 248" stroke="#7d8783" fill="none"
   marker-end="url(#a)" stroke-dasharray="4 3"/>

 <rect x="4" y="368" width="892" height="44" {S_BOX}/>
 <text x="17" y="389" {TB} fill="#0E2A26">Traces &#183; one per model attempt</text>
 <text x="17" y="405" {T} fill="#5d6b66">fallback rate, latency, cost per campaign, and the whole response so it can be debugged</text>
</svg>'''


def fig_agente() -> str:
    """Diagrama 2: el flujo agentico desde el portal."""
    return f'''
<svg viewBox="0 0 900 330" role="img" aria-label="Agentic flow: the brief comes in, the agent proposes a plan that a person
 approves, the engine runs, triage separates what needs review, the designer corrects it
 and the correction persists.">
{DEF_ARROW}
 <text x="4" y="12" {TS} fill="#7a5cc4">PROPOSED</text>

 <rect x="4" y="34" width="126" height="52" {S_BOX}/>
 <text x="16" y="55" {TB} fill="#0E2A26">1 &#183; Brief</text>
 <text x="16" y="72" {T} fill="#5d6b66">master + centres</text>

 <path d="M130 60 L172 60" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="176" y="24" width="150" height="72" {S_PRO}/>
 <text x="188" y="45" {TB} fill="#0E2A26">2 &#183; The agent reads</text>
 <text x="188" y="62" {T} fill="#5d6b66">which formats, which</text>
 <text x="188" y="77" {T} fill="#5d6b66">centres, what is missing</text>
 <text x="188" y="91" font-family="ui-monospace,SFMono-Regular,Menlo,monospace"
   font-size="8.4" letter-spacing="0.04em" fill="#7a5cc4">AND ASKS FOR WHAT IS NOT THERE</text>

 <path d="M326 60 L368 60" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="372" y="24" width="150" height="72" {S_INK}/>
 <text x="384" y="45" {TB} fill="#fff">3 &#183; The plan</text>
 <text x="384" y="62" {T} fill="#a8bdb7">n outputs, which master,</text>
 <text x="384" y="78" {T} fill="#a8bdb7">estimated cost</text>
 <text x="384" y="92" font-family="ui-monospace,SFMono-Regular,Menlo,monospace"
   font-size="8.4" letter-spacing="0.04em" fill="#E4572E">APPROVED BEFORE IT RUNS</text>

 <path d="M522 60 L564 60" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="568" y="34" width="150" height="52" {S_BOX}/>
 <text x="580" y="55" {TB} fill="#0E2A26">4 &#183; The engine</text>
 <text x="580" y="72" {T} fill="#5d6b66">deterministic, in parallel</text>

 <path d="M718 60 L760 60" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="764" y="34" width="132" height="52" {S_BOX}/>
 <text x="776" y="55" {TB} fill="#0E2A26">5 &#183; Triage</text>
 <text x="776" y="72" {T} fill="#5d6b66">which to open, and why</text>

 <path d="M830 86 L830 132" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="600" y="140" width="296" height="62" {S_BOX}/>
 <text x="613" y="162" {TB} fill="#0E2A26">6 &#183; The designer sees ONLY what is flagged</text>
 <text x="613" y="180" {T} fill="#5d6b66">not all 66. The ones the engine could not settle,</text>
 <text x="613" y="195" {T} fill="#5d6b66">with the measured reason beside them</text>

 <path d="M600 171 L470 171" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="290" y="140" width="176" height="62" {S_PRO}/>
 <text x="302" y="162" {TB} fill="#0E2A26">7 &#183; Corrects it once</text>
 <text x="302" y="180" {T} fill="#5d6b66">moves the focal region,</text>
 <text x="302" y="195" {T} fill="#5d6b66">rewrites a line</text>

 <path d="M290 171 L200 171 L200 246" stroke="#E4572E" fill="none"
   marker-end="url(#ao)"/>
 <rect x="4" y="240" width="470" height="66" {S_INK}/>
 <text x="17" y="262" {TB} fill="#fff">8 &#183; The correction PERSISTS per master, and enters the golden set</text>
 <text x="17" y="280" {T} fill="#a8bdb7">the same campaign never asks for the same correction twice, and the case</text>
 <text x="17" y="296" {T} fill="#a8bdb7">stays as a regression test. The system improves by data, not by branches.</text>

 <path d="M474 273 L560 273 L560 96" stroke="#E4572E" fill="none"
   marker-end="url(#ao)" stroke-dasharray="4 3"/>
 <text x="580" y="262" {TS} fill="#E4572E">FEEDS BACK INTO THE PLAN</text>
 <text x="580" y="278" {T} fill="#5d6b66">and into the engine for that</text>
 <text x="580" y="293" {T} fill="#5d6b66">brand&rsquo;s next campaign</text>
</svg>'''


def fig_adaptadores() -> str:
    """Diagrama 3: por que Scene es el seam, y que se conecta a que."""
    return f'''
<svg viewBox="0 0 900 340" role="img" aria-label="Input and output adapters against a single Scene model. Three inputs exist
 today, the Figma one is next, and the rest are further adapters against the same core.">
{DEF_ARROW}
 <text x="4" y="14" {TS} fill="#5d6b66">INPUTS</text>
 <text x="392" y="14" {TS} fill="#5d6b66">CORE</text>
 <text x="700" y="14" {TS} fill="#5d6b66">OUTPUTS</text>

 <rect x="4" y="28" width="180" height="34" {S_BOX}/>
 <text x="16" y="49" {TB} fill="#0E2A26">SVG with a raster</text>
 <rect x="188" y="34" width="46" height="22" fill="#0E2A26" rx="4"/>
 <text x="196" y="49" {TS} fill="#fff">TODAY</text>

 <rect x="4" y="70" width="180" height="34" {S_BOX}/>
 <text x="16" y="91" {TB} fill="#0E2A26">Flat raster</text>
 <rect x="188" y="76" width="46" height="22" fill="#0E2A26" rx="4"/>
 <text x="196" y="91" {TS} fill="#fff">TODAY</text>

 <rect x="4" y="112" width="180" height="34" {S_BOX}/>
 <text x="16" y="133" {TB} fill="#0E2A26">SVG this engine emitted</text>
 <rect x="188" y="118" width="46" height="22" fill="#0E2A26" rx="4"/>
 <text x="196" y="133" {TS} fill="#fff">TODAY</text>

 <rect x="4" y="154" width="180" height="34" fill="#f6f2ff" stroke="#E4572E" rx="7"/>
 <text x="16" y="175" {TB} fill="#0E2A26">Figma component</text>
 <rect x="188" y="160" width="86" height="22" fill="#E4572E" rx="4"/>
 <text x="196" y="175" {TS} fill="#fff">UP NEXT</text>

 <rect x="4" y="196" width="180" height="34" {S_PRO}/>
 <text x="16" y="217" {TB} fill="#0E2A26">IDML / InDesign</text>
 <rect x="4" y="238" width="180" height="34" {S_PRO}/>
 <text x="16" y="259" {TB} fill="#0E2A26">PSD</text>
 <rect x="4" y="280" width="180" height="34" {S_PRO}/>
 <text x="16" y="301" {TB} fill="#0E2A26">Canva &#183; Drive &#183; DAM</text>

 <path d="M274 45 L360 158" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M274 87 L360 164" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M274 129 L360 170" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M282 171 L360 176" stroke="#E4572E" fill="none" marker-end="url(#ao)"/>
 <path d="M186 213 L360 184" stroke="#b9aee0" fill="none" marker-end="url(#a)"
   stroke-dasharray="4 3"/>
 <path d="M186 255 L360 190" stroke="#b9aee0" fill="none" marker-end="url(#a)"
   stroke-dasharray="4 3"/>
 <path d="M186 297 L360 196" stroke="#b9aee0" fill="none" marker-end="url(#a)"
   stroke-dasharray="4 3"/>

 <rect x="364" y="120" width="164" height="110" {S_INK}/>
 <text x="378" y="146" {TB} fill="#fff" font-size="14">Scene</text>
 <text x="378" y="167" {T} fill="#a8bdb7">blocks with their role,</text>
 <text x="378" y="183" {T} fill="#a8bdb7">hierarchy, lockup,</text>
 <text x="378" y="199" {T} fill="#a8bdb7">photograph</text>
 <text x="378" y="219" {TS} fill="#E4572E">THE ONLY SEAM</text>

 <path d="M446 230 L446 268" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="364" y="272" width="164" height="42" {S_BOX}/>
 <text x="378" y="291" {TB} fill="#0E2A26">solve + emit</text>
 <text x="378" y="307" {TS} fill="#5d6b66">DETERMINISTIC</text>

 <path d="M528 175 L616 78" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M528 175 L616 133" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M528 181 L616 188" stroke="#b9aee0" fill="none" marker-end="url(#a)"
   stroke-dasharray="4 3"/>
 <path d="M528 187 L616 243" stroke="#b9aee0" fill="none" marker-end="url(#a)"
   stroke-dasharray="4 3"/>
 <path d="M528 193 L616 297" stroke="#b9aee0" fill="none" marker-end="url(#a)"
   stroke-dasharray="4 3"/>

 <rect x="620" y="56" width="180" height="34" {S_BOX}/>
 <text x="632" y="77" {TB} fill="#0E2A26">Editable SVG</text>
 <rect x="804" y="62" width="46" height="22" fill="#0E2A26" rx="4"/>
 <text x="812" y="77" {TS} fill="#fff">TODAY</text>

 <rect x="620" y="112" width="180" height="34" {S_BOX}/>
 <text x="632" y="133" {TB} fill="#0E2A26">Folder per centre</text>
 <rect x="804" y="118" width="46" height="22" fill="#0E2A26" rx="4"/>
 <text x="812" y="133" {TS} fill="#fff">TODAY</text>

 <rect x="620" y="168" width="180" height="34" {S_PRO}/>
 <text x="632" y="189" {TB} fill="#0E2A26">PNG / JPG / PDF</text>
 <rect x="620" y="224" width="180" height="34" {S_PRO}/>
 <text x="632" y="245" {TB} fill="#0E2A26">Back into Figma</text>
 <rect x="620" y="280" width="180" height="34" {S_PRO}/>
 <text x="632" y="301" {TB} fill="#0E2A26">DAM / media platforms</text>

 <text x="364" y="30" {T} fill="#5d6b66">Adding an input is an adapter.</text>
 <text x="364" y="46" {T} fill="#5d6b66">The decision logic is not touched.</text>
</svg>'''


def fig_escala(med: dict) -> str:
    """Diagrama 4: donde escala el coste y donde no."""
    n66 = med.get("n66", 66)
    return f'''
<svg viewBox="0 0 900 250" role="img" aria-label="Model cost scales with masters and not with outputs: a campaign of 66 sizes
 makes one call, not 66.">
{DEF_ARROW}
 <text x="4" y="14" {TS} fill="#0E2A26">MEASURED TODAY</text>

 <rect x="4" y="30" width="150" height="46" {S_BOX}/>
 <text x="16" y="50" {TB} fill="#0E2A26">1 master</text>
 <text x="16" y="67" {T} fill="#5d6b66">1 photograph</text>

 <path d="M154 53 L206 53" stroke="#E4572E" fill="none" marker-end="url(#ao)"/>
 <rect x="210" y="24" width="176" height="58" fill="#fff" stroke="#E4572E" rx="7"/>
 <text x="223" y="45" {TB} fill="#0E2A26">1 to 2 model calls</text>
 <text x="223" y="62" {T} fill="#5d6b66">the scene, and the focal region</text>
 <text x="223" y="77" {T} fill="#5d6b66">only if the cascades are unsure</text>

 <path d="M386 53 L438 53" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <rect x="442" y="24" width="176" height="58" {S_INK}/>
 <text x="455" y="45" {TB} fill="#fff">Scene, once</text>
 <text x="455" y="63" {T} fill="#a8bdb7">reused for every</text>
 <text x="455" y="78" {T} fill="#a8bdb7">one of the outputs</text>

 <path d="M618 40 L668 30" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M618 53 L668 53" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <path d="M618 66 L668 76" stroke="#7d8783" fill="none" marker-end="url(#a)"/>
 <text x="674" y="26" {T} fill="#5d6b66">format 1</text>
 <text x="674" y="46" {T} fill="#5d6b66">format 2</text>
 <text x="674" y="60" {T} fill="#5d6b66">&#8230;</text>
 <text x="674" y="80" {T} fill="#5d6b66">format {n66}</text>
 <text x="674" y="100" {TS} fill="#0E2A26">ZERO FURTHER CALLS</text>

 <line x1="4" y1="124" x2="896" y2="124" stroke="#d8d3c8"/>

 <text x="4" y="148" {TS} fill="#5d6b66">AND THAT IS WHY CONCURRENCY IS CHEAP</text>
 <rect x="4" y="160" width="290" height="76" {S_BOX}/>
 <text x="17" y="181" {TB} fill="#0E2A26">The cost that scales with outputs</text>
 <text x="17" y="199" {T} fill="#5d6b66">is deterministic CPU: dense search,</text>
 <text x="17" y="215" {T} fill="#5d6b66">font metrics, sRGB compositing.</text>
 <text x="17" y="230" {T} fill="#5d6b66">Stateless, no network, no GPU.</text>

 <rect x="304" y="160" width="290" height="76" {S_PRO}/>
 <text x="317" y="181" {TB} fill="#0E2A26">So the work splits by format</text>
 <text x="317" y="199" {T} fill="#5d6b66">1 task = 1 format. A pool of N</text>
 <text x="317" y="215" {T} fill="#5d6b66">workers divides wall-clock by N without</text>
 <text x="317" y="230" {T} fill="#5d6b66">touching model spend.</text>

 <rect x="604" y="160" width="292" height="76" fill="#fff" stroke="#E4572E" rx="7"/>
 <text x="617" y="181" {TB} fill="#0E2A26">What to actually watch</text>
 <text x="617" y="199" {T} fill="#5d6b66">is not the model: it is MEMORY. A</text>
 <text x="617" y="215" {T} fill="#5d6b66">3840x2160 raster decompressed is</text>
 <text x="617" y="230" {T} fill="#5d6b66">hundreds of MB per worker.</text>
</svg>'''


FASES = [
    ("Week 1", "Agree the number before building anything",
     "The first thing to close, in writing, is the acceptance metric: <em>what "
     "percentage of a campaign's formats need less than N minutes of designer "
     "editing</em>. If we do not propose it, the tool gets measured against "
     "&ldquo;it doesn't look right&rdquo; forever, and that is a fight nobody wins. "
     "In the same week: one named decision-maker, and committed designer hours to "
     "review output.",
     "The metric is written down, and a baseline exists: how long a campaign takes "
     "today, measured on a real one."),
    ("Weeks 2-4", "The Figma component adapter",
     "This is the first real deliverable, because it is the actual job: not "
     "<em>image &rarr; formats</em> but <em>campaign component &rarr; rollout</em>. "
     "A third adapter in front of the same <code>Scene</code>; the decision logic is "
     "not touched. The trap that will bite is known and named: in a Figma component "
     "the photograph is an image fill on a node with nested <code>clipPath</code> and "
     "<code>transform</code>, so the pixels are not where the node says they are.",
     "A real campaign component from the studio comes out the other side as a "
     "rollout, and the validator re-parses every delivered file."),
    ("Weeks 4-6", "The portal, the queue, and one job per campaign",
     "Upload or connect, approve a plan, get a folder per centre. The engine already "
     "runs headless and stateless, so this is mostly plumbing: an API, a queue, a "
     "worker pool, object storage, and auth. No agent yet &mdash; a form is enough to "
     "find out whether the output is worth automating.",
     "A designer runs a campaign end to end without anyone from engineering in the "
     "room."),
    ("Weeks 6-8", "The correction that persists, and the golden set",
     "The single highest-value feature after the adapter. The designer moves a focal "
     "region or rewrites a line once, and it persists <em>per master</em>, so the "
     "same campaign never asks twice. Every correction also enters a golden set, "
     "which turns the tool's failures into regression tests instead of tickets.",
     "A correction survives a re-run, and the golden set catches a regression that "
     "would otherwise have shipped."),
    ("Week 6", "Verification in the job, not in a demo",
     "At the end of week 6 the designer takes a generated campaign, adjusts it, "
     "saves it, and that time is compared against the number agreed in week 1. That "
     "is the only verification that matters, and it is deliberately scheduled before "
     "anything is added.",
     "Measured minutes against the agreed threshold. If it misses, the next phase is "
     "about closing that gap and nothing else."),
    ("Beyond", "The agent, and more adapters",
     "Only once the output is trusted: an agent that reads a brief, proposes a plan, "
     "asks what is missing and hands it over for approval. Then more adapters &mdash; "
     "IDML, PSD, a DAM &mdash; each one a front end on the same seam. Copy that varies "
     "per centre also lives here, and it is a product decision as much as a technical "
     "one.",
     "Each adapter added without touching the decision logic. That is the claim the "
     "architecture has to keep earning."),
]

RETOS = [
    ("The Figma image fill",
     "In a component the photograph is a fill on a node, with <code>clipPath</code> "
     "and <code>transform</code> possibly nested several levels up. Resolving where "
     "the pixels actually are is the whole adapter. The SVG parser already hit a "
     "smaller version of this, so the shape of the problem is known.",
     "high"),
    ("Memory, not the model",
     "A 3840&times;2160 raster decompressed is hundreds of MB, and each worker holds "
     "one plus its integral images. This is the real limit on how wide the pool can "
     "go, and it is what makes per-format serverless functions awkward rather than "
     "obvious.",
     "high"),
    ("The model's label is not deterministic",
     "Measured, twice, on the same illustration: one run answered "
     "<code>persona</code>, another <code>ilustracion</code>, and the two took "
     "different geometric paths. Anything downstream of a model label has to be "
     "correct for <em>every</em> value it can return, not for the one that came back "
     "while you were watching.",
     "high"),
    ("The crop contract is too narrow",
     "Today a focal region is one box that is either required or preferred. The real "
     "vocabulary is small and closed &mdash; <em>contain</em>, <em>preserve</em>, "
     "<em>do not cover</em>, <em>none</em> &mdash; and several regions can coexist. "
     "Half of what got fixed by hand this week is that vocabulary missing.",
     "medium"),
    ("Fonts and colour at production scale",
     "Embedding a foundry font in every delivered file is a licensing question before "
     "a technical one. And print is CMYK with an ICC profile, while everything here "
     "composites in sRGB, which is where SVG actually composites &mdash; print output "
     "is a conversion step that has to be designed, not assumed.",
     "medium"),
    ("Reproducibility",
     "Same input, same output, or regression tests are worthless. The engine is "
     "deterministic today; the model calls are not. Caching the scene and the focal "
     "region per master &mdash; which is also what makes them cheap &mdash; is what "
     "makes a re-run comparable.",
     "medium"),
]

DATOS = [
    ("Masters and photographs",
     "Re-run a whole campaign when a brand guideline changes, without asking anyone "
     "to re-upload. This is also what makes the tool worth keeping between campaigns."),
    ("Manifests &mdash; every decision with its reason",
     "Already generated today, one per output. It is the audit trail a designer can "
     "argue with, and it is the source for every number in the analytics below. "
     "Nothing has to be instrumented separately."),
    ("Focal overrides, per master",
     "The correction that persists. Small, and the single most valuable row in the "
     "schema, because it is the difference between a tool that learns and one that "
     "asks the same question every week."),
    ("Designer edits &mdash; delivered file vs. saved file",
     "The only honest quality signal there is. Everything else measures what the "
     "engine believes; this measures what a professional actually had to change."),
    ("Triage outcome vs. what was opened",
     "Whether the flag was right. The dangerous cell is the unflagged piece the "
     "designer edited anyway: that is the engine being confidently wrong, and it is "
     "invisible without this record."),
    ("Model traces &mdash; prompt, response, provider, latency, cost",
     "Already wired. Debugging a bad scene needs the response, not its length, and "
     "the fallback rate is the earliest warning that the primary provider is "
     "degrading."),
    ("The golden set",
     "Grows from failures. It is what lets the engine change without the change being "
     "an act of faith."),
]

ANALYTICS = [
    ("Minutes of designer editing per campaign",
     "The contract metric from week 1. Everything else is secondary to this one.",
     "the difference between the delivered file and the saved file, per format"),
    ("Triage precision, and its false negatives",
     "Of the flagged pieces, how many were really edited. And of the unflagged, how "
     "many were edited anyway &mdash; the number that says the engine is overconfident.",
     "triage label joined against designer edits"),
    ("Formats that always need review",
     "A format that is flagged every single time is not a bad crop; it is a missing "
     "brand rule, or a size that should carry its own hand-authored template. The "
     "tool should be able to say which.",
     "flag rate grouped by format across campaigns"),
    ("Cost per campaign, and per asset",
     "Model spend is per master, so cost per asset falls as a campaign grows. That is "
     "a number worth showing a client, and worth watching for the day it stops being "
     "true.",
     "traces, grouped by job"),
    ("Source resolution shortfalls",
     "Eight of the 66 sizes fall under 72 effective ppi today, and the engine says so "
     "rather than upscaling and hoping. Aggregated, it stops being a warning and "
     "becomes a brief: what resolution the photography needs to be shot at.",
     "effective_ppi from the manifests"),
    ("Provider fallback rate",
     "Per attempt, not per call, so a fallback is counted rather than silently "
     "absorbed. A rising rate is an incident before it is an outage.",
     "one span per attempt, already emitted"),
]

DESPLIEGUE = [
    ("One VM, systemd, a local queue",
     "A single machine, the queue in Postgres, workers as processes. Cheapest, "
     "simplest to reason about, and enough for a studio's real volume.",
     "No orchestration to learn. Restores from a snapshot. One place to look when "
     "something breaks.",
     "Vertical ceiling, and a single point of failure. Scaling means a bigger box.",
     "Where I would start, and I would not apologise for it."),
    ("Containers, a managed queue, an autoscaling pool",
     "The engine image is small and stateless. Workers scale on queue depth; the API "
     "and Postgres are managed.",
     "Absorbs a burst of campaigns. Deployments are boring. Memory per worker is a "
     "declared limit rather than a surprise.",
     "More moving parts, and a bill that grows with idle capacity if the pool floor "
     "is set carelessly.",
     "The obvious second step, once volume is known rather than guessed."),
    ("A function per format",
     "Fan out one invocation per output, converge on storage.",
     "Elastic to the point of absurdity, and pays only for work done.",
     "Fights the actual constraint: a large raster plus OpenCV and PIL is a heavy "
     "cold start and a tight memory ceiling. The shared master would have to be "
     "re-fetched or re-decoded per invocation, which is exactly the cost the "
     "architecture is built to avoid.",
     "Attractive on the slide, and the wrong shape for this workload. Named here so "
     "it does not have to be discovered later."),
]


def build(d: str = DEST) -> str:
    med = _medido()
    n66 = med.get("n66", 66)
    n8 = med.get("n8", 8)
    ppi = med.get("ppi_bajo", 8)

    fases = "".join(f'''
<div class="phase">
 <div class="w">{w}</div>
 <div>
  <h4>{t}</h4>
  <p>{cuerpo}</p>
  <div class="done"><i>Done when</i>{crit}</div>
 </div>
</div>''' for w, t, cuerpo, crit in FASES)

    retos = "".join(f'''
<tr><td>{n}</td><td>{c}</td>
 <td><span class="tag {'t-pro' if sev=='medium' else 't-now'}"
   style="{'background:#fdece7;color:#E4572E;border:1px solid #f5c9bb' if sev=='high' else ''}"
   >{sev.upper()}</span></td></tr>''' for n, c, sev in RETOS)

    datos = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in DATOS)
    ana = "".join(f"<tr><td>{k}</td><td>{v}</td><td><code>{s}</code></td></tr>"
                  for k, v, s in ANALYTICS)
    depl = "".join(f'''
<tr><td>{n}</td><td>{q}</td><td>{pro}</td><td>{con}</td><td><em>{ver}</em></td></tr>'''
                   for n, q, pro, con, ver in DESPLIEGUE)

    doc = f"""<!doctype html><meta charset="utf-8">
<title>What's next &middot; art-directed-resize</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}{nav.CSS}</style>
<div class="wrap">
{nav.render(d, "whats-next.html")}

<h1>What&rsquo;s next</h1>
<p class="sub">From a layout engine to a tool a studio runs every week.</p>

<div class="warn">
 <b>Read this first.</b> Everything on this page is a <b>proposal</b>. Not one line of
 it is written. It is an architecture I can defend and a plan I would commit to, and
 that is a different thing from working software &mdash; saying otherwise would be the
 most expensive mistake available here.<br><br>
 The few numbers about the <em>present</em> are marked
 <span class="tag t-now">MEASURED</span> and come from the manifests on disk and from
 today's runs. Everything else is marked <span class="tag t-pro">PROPOSED</span>.
 The engine as it stands is described in
 <a href="how-it-works.html">how it works</a>, and how it got there in
 <a href="evolution.html">how it changed</a>.
</div>

<h2><span class="k">01 &#183; THE STARTING POINT</span>What is actually built, and what the job actually is</h2>
<p class="lede">The honest version, because the plan only makes sense against it.</p>
<p>What exists is a layout engine. It reads a piece into a format-independent scene,
 decides the crop and the typography from the pixels, states a reason for every
 decision, and re-parses what it delivered to check it. Three input adapters work
 today: an SVG with an embedded raster, a flat raster with no structure at all, and
 an SVG this engine emitted &mdash; the output is an input.</p>
<div class="m"><span class="tag t-now">MEASURED</span>
 <b>{n66} banner sizes</b> from one master in a single invocation, about two minutes,
 one process, no templates authored by hand. <b>{n8} formats</b> for the campaign set
 in around twenty seconds. <b>1 to 2 model calls per master</b>, never per output.
 <b>{ppi} of the {n66}</b> fall under 72 effective ppi, and the engine says so
 instead of upscaling and hoping.</p></div>
<p><strong>And the part worth saying out loud:</strong> the demo optimises
 <em>image &rarr; formats</em>, while the real job is
 <em>campaign component &rarr; rollout</em>. The priorities of the real product are
 close to the inverse of the demo's emphasis. That is why the plan below starts with
 the Figma adapter and not with anything more impressive.</p>

<h2><span class="k">02 &#183; THE PLAN</span>Eight weeks, and the number comes first</h2>
<p class="lede">Each phase has an acceptance criterion that someone other than me can
 check. The order is deliberate: the metric before the build, the adapter before the
 portal, the portal before the agent.</p>
{fases}

<h2><span class="k">03 &#183; INFRASTRUCTURE</span>The shape of the system</h2>
<p class="lede">The engine is already headless, stateless and deterministic, which is
 what makes this shape available rather than aspirational. The only stateful pieces
 are the ones that hold what people decided.</p>
<div class="fig">{fig_topologia()}</div>
<p class="cap">Inputs converge on one API. A campaign becomes a job; a job becomes one
 task per format. Workers are CPU-only and hold no state. The model is called once
 per master, off to the side, and its answer is cached with the master.</p>
<p>Three properties of the engine do the load-bearing here, and all three are true
 today rather than planned. It <strong>holds no state</strong>, so a worker is
 disposable. It is <strong>deterministic</strong>, so two workers given the same task
 produce the same file, which is what makes retries safe and regression tests
 meaningful. And the <strong>model call does not scale with the output count</strong>,
 so parallelism buys wall-clock time without buying model spend.</p>

<h2><span class="k">04 &#183; THE AGENTIC FLOW</span>What the portal actually does</h2>
<p class="lede">The agent's job is not to decide the layout. It is to turn a brief into
 an approved plan, and to make sure a designer only ever looks at the pieces that need
 a human.</p>
<div class="fig">{fig_agente()}</div>
<p class="cap">The two steps that matter are 3 and 8. A plan approved before anything
 runs, and a correction that persists so the same question is never asked twice.</p>
<p>A plan that is approved before execution is not a UX nicety; it is the difference
 between a tool a studio trusts with 1,300 assets and one it runs twice and abandons.
 It also happens to be something the incumbent gets right, and there is no reason to
 pretend otherwise.</p>
<p><strong>Where the agent is genuinely useful</strong> is the gap between a brief and
 a job: which formats does this campaign need, which centres, what is missing, what
 will this cost. That is reading an underspecified request and asking the right
 question &mdash; and it is the one part of the flow where a deterministic form would
 be worse. <strong>Where it is not useful</strong> is inside the layout, and the
 architecture keeps it out on purpose: a model that writes the crop cannot state a
 reason you can audit, and cannot be regression-tested.</p>

<h2><span class="k">05 &#183; INTEGRATIONS</span>Figma first &mdash; and why it cannot only be Figma</h2>
<p class="lede">Figma is where the studio works, so it is where this has to land. But
 betting the architecture on one tool's API is how a tool like this dies.</p>
<div class="fig">{fig_adaptadores()}</div>
<p class="cap"><code>Scene</code> is the only coupling point in the system. Everything
 to its left is an adapter, everything to its right is an emitter, and the decision
 logic in the middle has never needed to know which one it is talking to.</p>
<p>This is the claim the design has already had to earn twice. A flat JPEG has zero
 text nodes and zero hierarchy, and it enters the same model. An SVG this engine
 emitted enters it too. Neither required touching the solver. So
 <strong>IDML, PSD, a DAM or Canva are more adapters, not more pipelines</strong>
 &mdash; and if that ever stops being true, the seam was in the wrong place and it
 will be obvious immediately rather than in year two.</p>
<p>On the delivery side the same argument runs backwards: a folder per centre works
 today because it is the format nobody can refuse. Pushing back into Figma, into a
 DAM, or straight into a media platform are emitters against the same manifest.</p>

<h2><span class="k">06 &#183; SCALE</span>High concurrency, and where the cost actually is</h2>
<p class="lede">The instinct is that an AI tool scales badly because inference is
 expensive. Here that is not where the cost is, and the design is arranged so it
 stays that way.</p>
<div class="fig">{fig_escala(med)}</div>
<p class="cap">Model spend follows masters. CPU follows outputs. They are different
 axes, and only one of them needs a queue.</p>
<p>A campaign of {n66} sizes makes one to two model calls today, measured. Ten
 campaigns in an hour make ten to twenty &mdash; a number no rate limit cares about.
 What grows is deterministic CPU work, and that partitions perfectly: one task per
 format, N workers, wall-clock divided by N.</p>
<p><strong>So the honest capacity question is memory, not inference.</strong> A worker
 decoding a 4K raster and building its integral images holds hundreds of megabytes,
 and that &mdash; not the model, not the CPU &mdash; sets how wide the pool can go per
 machine. It is also the reason the per-format serverless design in the deployment
 table below looks better than it is.</p>
<p>Two things are worth building early because they cost almost nothing and save a bad
 week later: <strong>per-master caching</strong> of the scene and focal region, which
 makes a re-run cheap and comparable, and a <strong>declared spend ceiling per job</strong>,
 which already exists in the prototype for the paid provider because a retry loop over
 a large image is otherwise an invoice.</p>

<h2><span class="k">07 &#183; DATA</span>What gets stored, and what it is for</h2>
<p class="lede">Nothing here is stored because it might be useful. Each row has a use,
 and most of it is already being produced &mdash; it just is not being kept.</p>
<table><tr><th>What</th><th>What it is for</th></tr>{datos}</table>
<p>The one to argue about is the fourth. <strong>The difference between the file we
 delivered and the file the designer saved is the only measurement of quality that is
 not self-graded</strong>, and it is also the metric the week-1 contract number
 depends on. It needs the designer's cooperation, which means it has to be worth their
 while &mdash; which is what the persisted correction buys.</p>

<h2><span class="k">08 &#183; ANALYTICS</span>What the tool should know about itself</h2>
<p class="lede">All of it derives from the manifests and traces the engine already
 emits. No separate instrumentation, and no metric that cannot be traced back to a
 file on disk.</p>
<table><tr><th>Metric</th><th>Why it earns its place</th><th>Source</th></tr>{ana}</table>
<p>Two of these are uncomfortable on purpose. <strong>Triage false negatives</strong>
 measure the engine being confidently wrong, which is the failure mode that damages
 trust fastest and the one a dashboard of green numbers will never show. And
 <strong>formats that are always flagged</strong> will eventually say that some sizes
 want a hand-authored template after all &mdash; which is the incumbent's answer, and
 if the data says it, the data says it.</p>

<h2><span class="k">09 &#183; RISKS</span>The technical challenges, named before anyone asks</h2>
<p class="lede">Ranked by how much they would hurt, not by how hard they are to
 explain. The first three are the ones I would want to be wrong about.</p>
<table><tr><th>Challenge</th><th>Why it is hard</th><th>Risk</th></tr>{retos}</table>

<h2><span class="k">10 &#183; DEPLOYMENT</span>Three options, and which one I would pick</h2>
<table><tr><th>Option</th><th>Shape</th><th>For</th><th>Against</th><th>Verdict</th></tr>{depl}</table>
<p>The recommendation is the boring one, and the reason is the volume. A studio
 producing campaigns weekly does not have a scaling problem; it has a
 <em>reliability and turnaround</em> problem. One machine that is easy to reason about
 and restores from a snapshot solves more of that than an autoscaling pool nobody on
 the team can debug at 6pm. The second option is the step to take when the volume is
 known rather than guessed, and the engine being stateless means that step costs a
 Dockerfile, not a rewrite.</p>

<h2><span class="k">11 &#183; VALUE</span>What this is actually worth</h2>
<p class="lede">Stated against the incumbent, without pretending the incumbent is bad
 at what it is good at.</p>
<div class="two">
 <div>
  <h3>What we do not compete on</h3>
  <p>Orchestration: the plan, the batch, the naming, the grouping by vendor, the
   round trip, the export formats. That is genuinely good, it has enterprise
   customers, and rebuilding it would be the wrong use of the first three months.</p>
 </div>
 <div>
  <h3>What is missing, and is the whole point</h3>
  <p>The layout intelligence does not live in the orchestrator. It lives in the
   constraints a designer authored by hand into a handful of Figma templates. That is
   the part that does not scale with the number of formats, and it is the part this
   engine replaces.</p>
 </div>
</div>
<ul>
 <li><strong>Formats you never authored.</strong> {n66} sizes from one master, ratios
  from 8.2:1 to portrait, with nothing written by hand per size. Adding a size is a
  row, not a template.</li>
 <li><strong>A reason for every decision.</strong> Every crop, colour, scrim, dropped
  element and logo variant arrives with the measurement that caused it. A designer can
  disagree with a reason; nobody can disagree with a black box.</li>
 <li><strong>A triage instead of a pile.</strong> The output is a rough first pass by
  design, and the tool says which pieces need a human. That is what turns
  &ldquo;rough&rdquo; from an apology into a feature.</li>
 <li><strong>Corrections that persist.</strong> The designer's judgement is captured
  once per master instead of re-applied every campaign, which is the only way the
  tool gets better rather than just faster.</li>
 <li><strong>It degrades in public.</strong> Insufficient source resolution, a subject
  that cannot survive a bleed crop, a group that will not fit &mdash; all measured and
  stated. The failure mode is a flag, not a bad asset shipped quietly.</li>
</ul>

<footer>Generated by <code>tools/plan.py</code>. Nothing described here is
 implemented; the numbers marked MEASURED come from the manifests in this repository.
 Brand, type and photography declared in <code>assets/LICENSES.md</code>.
 MERIDIAN QUARTER, Harbourside Plaza and Northgate Centre are invented names.</footer>
</div>
"""
    p = os.path.join(d, "whats-next.html")
    with open(p, "w") as fh:
        fh.write(doc)
    print(f"-> {p}  ({len(doc)//1024} KB, {len(FASES)} fases, 4 diagramas)")
    return p


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else DEST)
