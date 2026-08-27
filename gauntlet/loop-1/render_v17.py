#!/usr/bin/env python3
"""DAMM v1.7 report renderer — country-generic (gauntlet loop 1).
Usage: python3 render_v17.py <ISO3>  — loads config_<iso>.json, <ISO>_v17.json,
research/<ISO>_register.json. All country content comes from data or config;
strategic questions and the impact crosswalk are derived mechanically (spec 9).
"""
import json, html, sys, os, re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ISO = sys.argv[1] if len(sys.argv) > 1 else "NGA"
CFG = json.load(open(os.path.join(HERE, f"config_{ISO.lower()}.json")))
DATA = CFG.get("data_path") or os.path.join(HERE, f"{ISO}_v17.json")
REG  = CFG.get("register_path") or os.path.join(HERE, "research", f"{ISO}_register.json")
# `out_path` lets a pipeline run render its own diagnostic without colliding with a
# hand-built one for the same country. It mirrors data_path and register_path above; the
# default is unchanged, so every existing invocation writes exactly where it always did.
OUT  = CFG.get("out_path") or os.path.join(HERE, f"{CFG['country']}-DAR-Diagnostic.html")

d   = json.load(open(DATA))
reg = json.load(open(REG))
esc = lambda s: html.escape(str(s), quote=True)


# Legacy configs contain only unverified free text. It cannot establish a named,
# authenticated post-completion approval, even when it says "executed". The renderer
# therefore fails closed until a future structured approval record can be validated.
HUMAN_GATES = {
    "G1": "pending — named human assessor review required",
    "G2": "pending — independent human review required after G1",
    "G3": "pending — named and dated TTL/country-owner sign-off required",
}

# The report is a standalone document: no process history, no internal cross-references.
# Agent-authored text (register entries, notes) is sanitized before it reaches the page.
_CLEAN = [
    (r"[-—,;]?\s*gauntlet(?:\s+loop\s*\d+)?", ""),
    (r"[-—,;]?\s*\bloop[-\s]?\d+\b", ""),
    (r"\bclean[-\s]slate pass\b", "assessment"),
    (r"\bclean[-\s]slate\b", ""),
    (r"[;,]?\s*prior (?:desk )?pass[^;.]*", ""),
    (r"\bthis run\b", "at capture"),
    (r"flagged for §[\d.]+ judgment", "flagged for methodology review"),
    (r"\s*\(§[\d.]+\)", ""),
    (r"per §[\d.]+", "per the methodology"),
    (r"§[\d.]+", "the methodology"),
]
# Proper names and quoted titles keep their own spelling: an institution or a publication title is
# a quotation, not prose. Capitalized "Programme" is protected for the same reason (Anchor Borrowers'
# Programme); the lowercase generic word is not, and americanizes to "program".
_PROTECT_NAMES = ["Role-modelling", "Microdata Catalog", "Programme",
                  "International Labour Organization", "International Labour Organisation",
                  "SME Digitalisation", "Digitalisation of African Agriculture",
                  "National Council on Privatisation"]
_US_RULES = [("artefacts","artifacts"),("artefact","artifact"),("judgements","judgments"),("judgement","judgment"),
             ("behaviour","behavior"),("organisations","organizations"),("organisation","organization"),
             ("summarised","summarized"),("recognised","recognized"),("prioritise","prioritize"),
             ("modelling","modeling"),("catalogues","catalogs"),("catalogue","catalog"),
             ("centres","centers"),("centre","center"),("licence","license"),("defence","defense"),
             ("towards","toward"),("amongst","among"),("whilst","while"),("utilised","utilized"),
             ("subsidised","subsidized"),("subsidise","subsidize"),("subsidises","subsidizes"),
             ("digitised","digitized"),("digitisation","digitization"),
             ("digitalisation","digitalization"),("digitalised","digitalized"),
             ("modernisation","modernization"),("modernised","modernized"),
             ("mechanisation","mechanization"),("mechanised","mechanized"),
             ("privatisation","privatization"),("privatised","privatized"),
             ("harmonisation","harmonization"),("harmonised","harmonized"),("harmonise","harmonize"),
             ("standardisation","standardization"),("standardised","standardized"),
             ("mobilisation","mobilization"),("mobilised","mobilized"),
             ("specialised","specialized"),("capitalised","capitalized"),
             ("mischaracterised","mischaracterized"),("characterised","characterized"),
             ("fertiliser","fertilizer"),("fertilisers","fertilizers"),
             ("enrolment","enrollment"),("enrolments","enrollments"),
             ("programmes","programs"),("programme","program")]

_URL_RE = re.compile(r"(?:https?://|www\.)\S+")
def _shield(t, pat, mark):
    """Lift matches out of reach of the text rules, returning the text and the pieces removed."""
    held = []
    def take(m):
        held.append(m.group(0)); return f"\x00{mark}{len(held)-1}\x00"
    return pat.sub(take, t), held
def _unshield(t, held, mark):
    for i, v in enumerate(held): t = t.replace(f"\x00{mark}{i}\x00", v)
    return t

def americanize(t):
    """American spelling for assessor prose; quoted labels, proper names and URLs are left alone.
    URLs must be shielded before any rule runs: live links in the register contain the very strings
    the rules rewrite ('...summer-fertiliser-season...', '...silo-modernisation-efforts...'), and
    rewriting one silently breaks the citation it points at."""
    if not isinstance(t, str): return t
    t, urls = _shield(t, _URL_RE, "U")
    for i, nm in enumerate(_PROTECT_NAMES): t = t.replace(nm, f"\x00N{i}\x00")
    for a, b in _US_RULES:
        t = re.sub(r"\b" + re.escape(a) + r"\b", b, t)
        t = re.sub(r"\b" + re.escape(a.capitalize()) + r"\b", b.capitalize(), t)
    for i, nm in enumerate(_PROTECT_NAMES): t = t.replace(f"\x00N{i}\x00", nm)
    return _unshield(t, urls, "U")

def clean(t):
    if not isinstance(t, str): return t
    t, urls = _shield(t, _URL_RE, "C")          # the sanitizer rewrites prose, never a link
    for pat, rep in _CLEAN:
        t = re.sub(pat, rep, t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t)
    t = _unshield(t, urls, "C")
    return americanize(re.sub(r"^[\s—,;-]+", "", t).strip())

# Addresses are never rewritten — only the prose around them.
_RAW_KEYS = {"url", "src_url", "link", "href"}
def clean_deep(o, key=None):
    """Sanitize every string that can reach the page, at whatever depth it sits. The register's
    use-case tags are lists, the narrative blocks are lists, and indicator values are free prose:
    cleaning only top-level string fields left all three unsanitized."""
    if key in _RAW_KEYS: return o
    if isinstance(o, str):  return clean(o)
    if isinstance(o, list): return [clean_deep(x) for x in o]
    if isinstance(o, dict): return {k: clean_deep(v, k) for k, v in o.items()}
    return o

def clean_reg(reg):
    reg["entries"] = clean_deep(reg.get("entries", []))
    for k in ("overlap_finding", "status_note", "issues"):
        if isinstance(reg.get(k), str): reg[k] = clean(reg[k])
    return reg
reg = clean_reg(reg)
d["indicators"] = clean_deep(d["indicators"])
for _nk in ("narrative_problem", "narrative_register", "narrative_constraints", "narrative_questions"):
    if isinstance(CFG.get(_nk), list): CFG[_nk] = clean_deep(CFG[_nk])

PILLAR_NAMES = {
  "A1": "Agriculture & need", "C1": "Connectivity & access", "C2": "Data & DPI",
  "C3": "Policy & safeguards", "C4": "People & institutions",
  "E1": "Innovation, solutions & emerging tech", "O1": "Outcomes & inclusion"}
PILLAR_ORDER = ["A1","C1","C2","C3","C4","E1","O1"]
UC_NAMES = {"ADV":"Advisory & extension","SMF":"Smart farming","MKT":"Market linkage & pricing",
            "SCM":"Supply chain","FIN":"Financial services","AGI":"Agricultural intelligence"}
UC_ORDER = ["ADV","SMF","MKT","SCM","FIN","AGI"]
LAYERS = ["Foundation","Enablers","Transformation","Outcomes"]
# The chart axis bands. Derived from the engine rather than restated, because this was
# a second copy of the edges and it silently kept the pre-recut values.
from engine_v17 import BANDS as _EB
BANDS = [(lo, n) for lo, hi, n in _EB]
# The caption used to restate the cut-offs as literal text. When the bands were re-cut the
# chart moved with the model and the sentence did not, so every report drew its lines in
# one place and told the reader they were somewhere else. Derived now, from the same list
# the chart uses.
BAND_CUTS = " / ".join(f"{lo:g}" for lo, _ in BANDS[1:])

def tier_of(src):
    s = src.lower()
    if "machine pass" in s: return ""
    for k in ("wdi","world bank wdi","faostat","aquastat","itu","findex","ilo"):
        if k in s: return "T1"
    for k in ("openknowledge","icr","peer-reviewed","journal"):
        if k in s: return "T2"
    for k in ("ncc","nimc","nitda","cbn","nimet","fmafs","fmard","gazette","ndpc","law","act "):
        if k in s: return "T3"
    for k in ("gsma","giz","usaid","agra","afdb"):
        if k in s: return "T4"
    return "T3" if ".gov" in s else "T4"

def chip(cls):
    return f'<span class="chip chip-{cls.lower()}" title="{cls}">{cls[0]}</span>'

def srclink(v):
    t = esc(v["src"])
    u = v.get("url", "")
    return f'<a href="{esc(u)}" rel="noopener">{t}</a>' if u else t

def tierbadge(t):
    names = {"T1":"Tier 1 — official statistics / IO databases","T2":"Tier 2 — peer-reviewed / IO flagship",
             "T3":"Tier 3 — government legal & policy artifacts","T4":"Tier 4 — reputable grey literature",
             "T5":"Tier 5 — news / vendor (existence facts only)"}
    return f'<span class="tier" title="{names.get(t,"")}">{t}</span>' if t else ""

def statuschip(s):
    m = {"Ready":("ok","✓"), "Partial":("warn","◐"), "Blocked":("crit","✕"), "Unverified":("neut","?"),
         "Present":("ok","✓"), "Present (narrow)":("warn","◐"), "Absent":("crit","✕"),
         "Operating":("ok","●"), "Adopted":("warn","●"), "Announced":("neut","○"), "Closed":("neut","■")}
    k, ic = m.get(s, ("neut","·"))
    return f'<span class="st st-{k}"><span class="st-ic">{ic}</span>{esc(s)}</span>'

def band_of(mean):
    b = "Nascent"
    for edge, name in BANDS:
        if mean >= edge: b = name
    return b

# ---------- charts (inline SVG, colors via CSS vars) ----------

def pillar_chart():
    W, ROW, PAD_L, PAD_R, TOP = 980, 46, 250, 56, 34
    H = TOP + ROW*len(PILLAR_ORDER) + 30
    x0, x1 = PAD_L, W - PAD_R
    def X(v): return x0 + (v-1)/4.0*(x1-x0)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Pillar profile: mean level per pillar on the 1 to 5 scale" class="viz">']
    for edge,name in BANDS[1:]:
        s.append(f'<line x1="{X(edge):.1f}" y1="{TOP-14}" x2="{X(edge):.1f}" y2="{H-26}" class="cut"/>')
        s.append(f'<text x="{X(edge):.1f}" y="{TOP-20}" class="cutlab" text-anchor="middle">{edge}</text>')
    for i,(edge,name) in enumerate(BANDS):
        nxt = BANDS[i+1][0] if i+1 < len(BANDS) else 5.0
        s.append(f'<text x="{(X(edge)+X(nxt))/2:.1f}" y="{H-8}" class="bandlab" text-anchor="middle">{name}</text>')
    short = dict(PILLAR_NAMES); short["E1"] = "Innovation & emerging tech"
    for i,p in enumerate(PILLAR_ORDER):
        pd = d["pillars"][p]; y = TOP + i*ROW
        lbl = f'{p} · {short[p]}'
        s.append(f'<text x="{x0-12}" y="{y+17}" class="rowlab" text-anchor="end">{esc(lbl)}</text>')
        s.append(f'<line x1="{x0}" y1="{y+24.5}" x2="{x1}" y2="{y+24.5}" class="track"/>')
        if pd["mean"] is None:
            # A pillar with nothing rated has no mean. Drawing a bar of zero length would
            # read as a measured floor — the lowest possible maturity — when what happened
            # is that no row in the pillar carries a level. The row keeps its track and
            # says so, which is the same rule the tiles below already follow.
            s.append(f'<text x="{x0+8}" y="{y+17}" class="vallab">Not rated'
                     f'&#8202;<tspan class="dimlab">&#183; 0 of {pd["n"]} rated</tspan></text>')
            continue
        bw = max(X(pd["mean"])-x0, 2)
        weak = pd["weak"]
        cls = "bar weakbar" if weak else "bar"
        s.append(f'<rect x="{x0}" y="{y+4}" width="{bw:.1f}" height="17" rx="3" class="{cls}">'
                 f'<title>{esc(PILLAR_NAMES[p])}: mean {pd["mean"]:.2f} — {pd["band"]}{f" {pd["margin"]:+.2f}" if pd.get("margin") is not None else ""}{" (weak evidence)" if weak else ""}; '
                 f'averaged over {pd["rated"]} of {pd["n"]} indicators'
                 f'{(", " + str(pd["held"]) + " level(s) withheld pending ratification") if pd["held"] else ""}; '
                 f'{pd["comp"].get("Measured",0)}M/{pd["comp"].get("Documented",0)}D/{pd["comp"].get("Judged",0)}J/{pd["comp"].get("Gap",0)}G</title></rect>')
        _mg = pd.get("margin")
        _mgtxt = f' {_mg:+.2f}' if _mg is not None else ''
        bandtxt = (f'({pd["band"]}{_mgtxt})' if weak else f'{pd["band"]}{_mgtxt}')
        # The denominator travels with the mean: a band averaged over 3 of 7 rows must never be
        # readable as one averaged over 7 (defect 39).
        denom = (f'&#8202;<tspan class="dimlab">&#183; {pd["rated"]} of {pd["n"]} rated</tspan>'
                 if pd["rated"] < pd["n"] else "")
        s.append(f'<text x="{X(pd["mean"])+8:.1f}" y="{y+17}" class="vallab">{pd["mean"]:.2f}&#8194;{bandtxt}{denom}</text>')
    s.append('</svg>')
    return "".join(s)

def evidence_chart():
    W, ROW, PAD_L, PAD_R, TOP = 980, 40, 250, 40, 30
    H = TOP + ROW*len(PILLAR_ORDER) + 14
    x0, x1 = PAD_L, W-PAD_R
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Evidence composition per pillar: Measured, Documented, Judged, Gap" class="viz">']
    for i,p in enumerate(PILLAR_ORDER):
        pd = d["pillars"][p]; comp = pd["comp"]; n = pd["n"]; y = TOP+i*ROW
        _rl = f'n={n}' + (f' &#183; {pd["rated"]} rated' if pd["rated"] < n else "")
        s.append(f'<text x="{x0-12}" y="{y+16}" class="rowlab" text-anchor="end">{p} <tspan class="dimlab">{_rl}</tspan></text>')
        x = x0
        for key in ("Measured","Documented","Judged","Gap"):
            c = comp.get(key,0)
            if not c: continue
            w = c/n*(x1-x0) - 2
            s.append(f'<rect x="{x:.1f}" y="{y+3}" width="{max(w,2):.1f}" height="18" rx="2" class="seg seg-{key.lower()}">'
                     f'<title>{esc(PILLAR_NAMES[p])}: {c} {key}'
                     f'{(" \u2014 " + str(pd["held"]) + " of this pillar\u2019s rows have the level withheld") if (pd["held"] and key in ("Measured","Documented")) else ""}'
                     f'</title></rect>')
            if w > 16:
                tcls = "seglab-m" if key == "Measured" else ("seglab" if key == "Documented" else "seglab-dark")
                s.append(f'<text x="{x+max(w,2)/2:.1f}" y="{y+16.5}" class="{tcls}" text-anchor="middle">{c}</text>')
            x += c/n*(x1-x0)
    s.append('</svg>')
    return "".join(s)

def layer_chart():
    W, ROW, PAD_L, PAD_R, TOP = 980, 44, 250, 56, 12
    H = TOP + ROW*4 + 8
    x0, x1 = PAD_L, W-PAD_R
    def X(v): return x0 + (v-1)/4.0*(x1-x0)
    counts = Counter(v["layer"] for v in d["indicators"].values())
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Layer profile: mean level per layer" class="viz">']
    for edge,_ in BANDS[1:]:
        s.append(f'<line x1="{X(edge):.1f}" y1="{TOP-4}" x2="{X(edge):.1f}" y2="{H-6}" class="cut"/>')
    for i,L in enumerate(LAYERS):
        v = d["layers"][L]; y = TOP+i*ROW
        s.append(f'<text x="{x0-12}" y="{y+16}" class="rowlab" text-anchor="end">{L} <tspan class="dimlab">n={counts.get(L,0)}</tspan></text>')
        s.append(f'<line x1="{x0}" y1="{y+22.5}" x2="{x1}" y2="{y+22.5}" class="track"/>')
        if v is None:
            # Same rule as the pillar chart: a layer with nothing rated has no mean, and a
            # zero-length bar would read as the lowest maturity rather than as silence.
            s.append(f'<text x="{x0+8}" y="{y+16}" class="vallab">Not rated</text>')
            continue
        s.append(f'<rect x="{x0}" y="{y+4}" width="{max(X(v)-x0,2):.1f}" height="15" rx="3" class="bar">'
                 f'<title>{L}: mean {v:.2f}</title></rect>')
        s.append(f'<text x="{X(v)+8:.1f}" y="{y+16}" class="vallab">{v:.2f}</text>')
    s.append('</svg>')
    return "".join(s)

def vintage_chart():
    # Stale = older than 3 years at the 2026 assessment: year <= 2022 (matches engine).
    years = Counter(v["year"] for v in d["indicators"].values() if v["cls"] != "Gap")
    if not years: return ""
    stale_n = sum(c for y,c in years.items() if y <= 2022)
    buckets = [("&#8804;2022", stale_n, True)] + [(str(y), years.get(y,0), False) for y in (2023,2024,2025,2026)]
    W, H, BOT, TOP = 440, 168, 30, 26
    cw = (W-20)/len(buckets)
    mx = max(c for _,c,_ in buckets) or 1
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Data vintage: indicator count by observation year" class="viz">']
    for i,(lab,c,stale) in enumerate(buckets):
        x = 10 + i*cw + cw*0.18
        bh = 0 if not c else max(c/mx*(H-TOP-BOT), 3)
        y = H-BOT-bh
        cls = "bar stale" if stale else "bar"
        if c:
            s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw*0.64:.1f}" height="{bh:.1f}" rx="3" class="{cls}">'
                     f'<title>{lab.replace("&#8804;","<=")}: {c} indicator{"s" if c!=1 else ""}{" — stale" if stale else ""}</title></rect>')
            s.append(f'<text x="{x+cw*0.32:.1f}" y="{y-6:.1f}" class="vallab" text-anchor="middle">{c}</text>')
        s.append(f'<text x="{x+cw*0.32:.1f}" y="{H-10}" class="rowlab" text-anchor="middle">{lab}</text>')
    s.append(f'<text x="{10+cw*0.5:.1f}" y="{TOP-10}" class="cutlab" text-anchor="middle">stale</text>')
    s.append('</svg>')
    return "".join(s)

def spine():
    cells = []
    for k in d["indicators"]:
        v = d["indicators"][k]
        cells.append(f'<span class="cell cell-{v["cls"].lower()}" title="{esc(k)} {esc(v["name"])} — {v["cls"]}"></span>')
    return f'<div class="spine" aria-label="Evidence spine: one cell per indicator, coloured by evidence class">{"".join(cells)}</div>'


# ---------- reference values (context, never scored; spec \u00a79 context rules) ----------
REFS = CFG.get("refs", {})

# ---------- automated QC (Layer 2, DAMM-v1.7-QC-Protocol.md; emit-blocking) ----------
def qc_checks(d, reg):
    inds = d["indicators"]; checks = []
    def add(name, ok): checks.append((name, bool(ok)))
    add("A1 level implies value+source+year; no level on Gap",
        all((v["level"] is None) or (v["value"] not in (None, "") and v["src"] and v["year"]) for v in inds.values())
        and all(v["level"] is None for v in inds.values() if v["cls"] == "Gap"))
    ok2 = all(isinstance(v["value"], (int, float)) for v in inds.values() if v["cls"] == "Measured") \
        and all("DATA GAP" in str(v["value"]).upper() for v in inds.values() if v["cls"] == "Gap")
    add("A2 class derives from value", ok2)
    add("A3 Gap rows carry a search trail",
        all(("searched" in str(v["value"]).lower()) or v["note"] for v in inds.values() if v["cls"] == "Gap"))
    add("A4 staleness matches the 3-year rule",
        all(v["stale"] == (v["year"] <= 2022) for v in inds.values() if v["cls"] != "Gap"))
    _cc = Counter(v["cls"] for v in inds.values())
    add("A5 counts reconcile to 57; matrix has 6 columns",
        all(_cc.get(c, 0) == d["counts"].get(c, 0) for c in ("Measured", "Documented", "Judged", "Gap"))
        and sum(d["counts"].values()) == 57
        and sum(pl["n"] for pl in d["pillars"].values()) == 57
        and len(d["matrix"]) == 6)
    add("A6 status vocabularies closed",
        all(m["status"] in {"Ready", "Partial", "Blocked", "Unverified"} for m in d["matrix"].values())
        and all(pr["status"] in {"Present", "Present (narrow)", "Absent", "Unverified"} for pr in d["prereq"].values()))
    add("A7 register tiers valid; T5 carries no results tier",
        all(e["tier"] in {"T1", "T2", "T3", "T4", "T5"} for e in reg["entries"])
        and all(not e.get("results_tier","") for e in reg["entries"] if e["tier"] == "T5"))
    add("A8 KPI baseline rows all Measured A1/O1",
        all(inds[k["id"]]["cls"] == "Measured" and inds[k["id"]]["pillar"] in ("A1", "O1") for k in d["kpi"]))
    return checks

QC = qc_checks(d, reg)
_failed = [n for n, ok in QC if not ok]
if _failed:
    raise SystemExit("QC FAIL \u2014 report not emitted: " + "; ".join(_failed))

# ---------- narrative + derived content ----------

counts = d["counts"]; N = sum(counts.values())
valuebacked = counts["Measured"] + counts["Documented"]
weak_pillars = [p for p in PILLAR_ORDER if d["pillars"][p]["weak"]]
# (executive sentence is built mechanically in build_brief)

matrix_counts = Counter(m["status"] for m in d["matrix"].values())

# Strategic questions — derived per spec §9 rules
UC_LONG = {"ADV":"advisory & extension","SMF":"smart farming","MKT":"market linkage & pricing",
           "SCM":"supply chain","FIN":"financial services","AGI":"agricultural intelligence"}

def derive_questions(d, cfg):
    qs = []
    seen_blockers = set()
    for uc in ["ADV","SMF","MKT","SCM","FIN","AGI"]:
        m = d["matrix"][uc]
        if m["status"] != "Blocked": continue
        for bid in [x.strip() for x in m["why"].replace("Universal:","").split(",") if x.strip() and x.strip() in d["prereq"]]:
            if bid in seen_blockers: continue
            seen_blockers.add(bid)
            nm = d["prereq"][bid]["name"]
            lv = d["indicators"][bid]["level"]
            qs.append((f"Blocked cell {uc} \u00b7 {bid}",
                       f"{nm} is Absent ({bid}{', L'+str(lv) if lv else ''}). Which institution gets the mandate to move it to Adopted, on what timeline \u2014 and what does the {UC_LONG[uc]} agenda do until then?", bid))
    for pid, pr in d["prereq"].items():
        if pr["status"] == "Unverified":
            tailk = "both delivery-risk flags hang on it" if pr["kind"] == "DELIVERY" else "a readiness column cannot resolve until it is settled"
            qs.append((f"Unverified prerequisite {pid}",
                       f"The desk pass could not verify {pr['name']} ({pid}) \u2014 a first-mission verification question, because {tailk}.", pid))
    for pid, pr in d["prereq"].items():
        if pr["status"] == "Present (narrow)" and pr["kind"].startswith(("UNIVERSAL","UC")):
            qs.append((f"Prerequisite {pid} \u00b7 narrow",
                       f"{pr['name']} is Present but narrow ({pid}). What moves it from pilot or partial coverage to a national rail the dependent use cases can stand on?", pid))
    if d["leapfrog"]["flag"]:
        qs.append(("Layer profile \u00b7 structural flag", d["leapfrog"]["reading"] + " \u2014 what sequencing answer does the roadmap give?", "leapfrog"))
    thin = [uc for uc, m in d["matrix"].items() if m["status"] == "Partial" and m["why"] == "thin enablers"]
    if len(thin) >= 2:
        qs.append(("Matrix \u00b7 thin enablers",
                   f"{len(thin)} columns ({', '.join(thin)}) are Partial for the same reason \u2014 thin enablers (layer mean {d['layers']['Enablers']:.2f} vs Foundation {d['layers']['Foundation']:.2f}). Which two or three enabler investments unlock the most columns at once?", "matrix"))
    if d["counts"]["Gap"] >= 8:
        gap_names = [d["indicators"][v["id"]]["name"] for v in d["verify"] if v["cls"] == "Gap"][:5]
        qs.append(("Evidence ledger",
                   f"{d['counts']['Gap']} of 57 indicators are recorded gaps (including {', '.join(n.split('(')[0].strip().lower() for n in gap_names)}). What primary data collection must the mission commission first?", "ledger"))
    qs = qs[:12]
    prec = cfg.get("precedents", {})
    out = []
    for tag, q, key in qs:
        out.append((tag, q, tuple(prec[key]) if key in prec else None))
    for extra in cfg.get("authored_questions", []):
        out.append((extra["tag"] + " \u00b7 authored", extra["q"], None))
    return out[:12]

SQ = derive_questions(d, CFG)

CROSSWALK = {  # standard v1.7 impact crosswalk: A1 constraint -> use-case areas that address it
 "1.1": ["SMF","FIN"], "1.2": ["ADV","SMF","AGI"], "1.3": ["SMF","FIN"], "1.4": ["ADV","SMF"],
 "1.5": ["SCM","MKT"], "1.6": ["MKT"], "1.7": ["FIN"], "1.8": ["ADV","AGI"],
 "8.1": ["ADV","FIN","MKT"], "8.5": ["ADV","SMF","MKT","SCM","FIN","AGI"],
}
def build_impact(d):
    rows = []
    for iid, ucs in CROSSWALK.items():
        v = d["indicators"].get(iid)
        if not v: continue
        if v["cls"] == "Gap":
            txt = f"{v['name']} \u2014 recorded gap"
        elif isinstance(v["value"], (int, float)):
            txt = f"{v['name']}: {v['value']:,g} ({v['year']})"
        else:
            txt = f"{v['name']}: {str(v['value'])[:80]}"
        rows.append((iid, txt, ucs))
    return rows
IMPACT = build_impact(d)

# ---------- HTML assembly ----------

_a1 = d["pillars"]["A1"]
_a1v = _a1["comp"]["Measured"] + _a1["comp"]["Documented"]
A1_NOTE = (f'A1 is scored as need, not digital maturity \u2014 a low reading is a large opportunity. '
           + (f'Pillar mean {_a1["mean"]:.2f}, {("(" + _a1["band"] + ")") if _a1["weak"] else _a1["band"]}, '
              if _a1["mean"] is not None else 'No row in the pillar carries a level, so there is no mean; ')
           + f'averaged over the {_a1["rated"]} of {_a1["n"]} rows that carry a level'
           + (f' ({_a1["held"]} withheld pending ratification, {_a1["comp"]["Gap"]} recorded as gaps)'
              if (_a1["held"] or _a1["comp"]["Gap"]) else '')
           + f'; {_a1v} of {_a1["n"]} are value-backed.')

_weak = [p for p in PILLAR_ORDER if d["pillars"][p]["weak"]]
_partial = [p for p in PILLAR_ORDER if d["pillars"][p]["rated"] < d["pillars"][p]["n"]]
EVID_NOTE = ("Evidence composition per pillar; the bar shows what class of evidence each row rests on, "
             "which is not the same as how many rows produced a level. "
             + (f'A pillar mean averages only its rated rows, so {", ".join(_partial)} publish that count beside the mean. '
                if _partial else "")
             + (f'{", ".join(_weak)} carry the weak-evidence rendering: judged rows, recorded gaps and withheld levels outnumber the levelled measured and documented rows, so those bands print in parentheses.'
                if _weak else "No pillar carries the weak-evidence rendering: in every pillar, the levelled measured and documented rows outnumber judged rows, recorded gaps and withheld levels."))

_mdriven = [(u, m) for u, m in d["matrix"].items() if m.get("mean_driven")]
_roles = [m for m in d["matrix"].values() if m["basis"]["need"] or m["basis"]["outcome"]]
# Ruling 13.12: the three roles are separated and only the readiness mean decides a
# column. This note used to carry the open question; it now states the rule.
MATRIX_NOTE = ("Cells: Ready / Partial / Blocked (named blocker) / Unverified. Prerequisites bind on presence "
               "only \u2014 a fact, never an opinion. Delivery-risk flags sit on the cover and block nothing. "
               "A column reads on its ENABLING indicators alone. Indicators of agricultural need measure the "
               "severity of the problem and outcome indicators measure what has already been achieved; both "
               "are reported beside the column and neither is averaged into it, because a country with a worse "
               "agricultural problem must not thereby read as less digitally ready."
               + ("".join(f' {UC_NAMES[u]} is the one column whose reading turns on the mean rather than on a '
                          f'prerequisite, at {m["mean_readiness"]:.2f} against the '
                          f'{CFG.get("readiness_threshold", 2.5)} line.'
                          for u, m in _mdriven))
               + (f' Across the six columns, need and outcome rows sit among the bearing set '
                  f'{len(_roles)} time{"" if len(_roles)==1 else "s"}; they are shown as separate '
                  f'means and never folded in.' if _roles else ""))

def sec(no, title, feeds, body, note=""):
    n = f'<p class="secnote">{note}</p>' if note else ""
    return (f'<section id="s{no}"><header class="sechead"><h2><span class="secno">{no}</span>{esc(title)}</h2>'
            f'<span class="feeds">feeds {esc(feeds)}</span></header>{n}{body}</section>')

def cand_strip(d):
    c = d.get("candidates", {})
    if not c: return ""
    bits = []
    for k, v in c.items():
        nm = "Cereal import dependency ratio" if "IMP" in k else "Irrigation coverage"
        if v.get("cls") == "Gap" or v.get("status") in ("no_data",):
            bits.append(f"<b>{nm}:</b> not retrieved this pass")
        else:
            val = v.get("value"); yr = v.get("year","")
            bits.append(f"<b>{nm}:</b> {val:,.1f}% ({yr}, {esc(str(v.get('src','') or v.get('source_title','')))})" if isinstance(val,(int,float)) else f"<b>{nm}:</b> {esc(str(val))[:120]}")
    return ('<p class="caption">Proposed additions to the need profile \u2014 recorded for context, not scored: ' + " \u00b7 ".join(bits) + '</p>')
def a1_tiles():
    A1 = [(i, v) for i, v in d["indicators"].items() if v["pillar"] == "A1"]
    tiles = []
    for k, v in A1:
        if not isinstance(v["value"], (int, float)): continue
        val = v["value"]
        if not isinstance(val, float):
            disp = f'{val:,}'
        elif abs(val) >= 10:
            disp = f'{val:,.1f}'.rstrip('0').rstrip('.')
        else:
            disp = f'{val:,.2f}'.rstrip('0').rstrip('.')
        stale = ' <span class="stale-tag">stale</span>' if v["stale"] else ""
        lvl = f'L{v["level"]}' if v["level"] else "unrated"
        tiles.append(f'<div class="tile"><div class="tile-k">{esc(v["name"])}{stale}</div>'
                     f'<div class="tile-v">{disp}</div>'
                     + (f'<div class="tile-ref">ref: {REFS[k]}</div>' if k in REFS else '')
                     + f'<div class="tile-m">{chip(v["cls"])} {lvl} · {esc(v["src"].split(";")[0])} · {v["year"]}</div></div>')
    docs = [(k, v) for k, v in A1 if v["cls"] == "Documented" and v["level"]]
    if docs:
        dl = "".join(f'<li>{esc(v["name"])} <span class="dim">({k} · L{v["level"]})</span></li>' for k, v in docs)
        tiles.append(f'<div class="tile"><div class="tile-k">Recorded from documents — {len(docs)} of {len(A1)} need metrics</div>'
                     f'<ul class="gaplist">{dl}</ul>'
                     f'<div class="tile-m">{chip("Documented")} levelled from cited evidence, not a national statistic</div></div>')
    unrated = [(k, v) for k, v in A1 if v["level"] is None and v["cls"] != "Gap"]
    gaps = [(k, v) for k, v in A1 if v["cls"] == "Gap"]
    if unrated or gaps:
        parts = []
        if unrated:
            ul = "".join(f'<li>{esc(v["name"])} <span class="dim">({k})</span></li>' for k, v in unrated)
            parts.append(f'<div class="tile-k">Recorded but unrated — {len(unrated)} of {len(A1)}</div><ul class="gaplist">{ul}</ul>'
                         f'<div class="tile-m">{chip("Documented")} evidence exists; it measures a different construct, so no level is set</div>')
        if gaps:
            gl = "".join(f'<li>{esc(v["name"])} <span class="dim">({k})</span></li>' for k, v in gaps)
            parts.append(f'<div class="tile-k">Recorded gaps — {len(gaps)} of {len(A1)} need metrics</div><ul class="gaplist">{gl}</ul>'
                         f'<div class="tile-m">{chip("Gap")} searched, named, and routed to the evidence ledger</div>')
        tiles.append('<div class="tile tile-gap">' + "".join(parts) + '</div>')
    return (f'<div class="tiles">{"".join(tiles)}</div>'
            + cand_strip(d) + '<p class="caption">Reference values compare the country reading with the world figure for the same series \u2014 context only, never scored.</p>')

def register_table():
    rows = []
    for e in reg["entries"]:
        ucs = " ".join(f'<span class="uc">{u}</span>' for u in e["uc"])
        ov = ", ".join(e.get("overlap",[])) if e.get("overlap",[]) else "—"
        res = esc(e["results"]) + (f' {tierbadge(e.get("results_tier",""))}' if e.get("results_tier","") else "")
        rows.append(f'<tr><td class="rn">{esc(e["name"])}<div class="dim">{esc(e["lead"])}</div></td>'
                    f'<td>{ucs}</td><td>{statuschip(e["status"])}</td>'
                    f'<td>{esc(e["scale"])}</td><td>{res}</td><td>{esc(ov)}</td>'
                    f'<td>{tierbadge(e["tier"])}<div class="dim srcline">{(f'<a href="{esc(e["src_url"])}" rel="noopener">{esc(e["src"])}</a>' if e.get("src_url") else esc(e["src"]))}</div>'
                    f'{('<div class="dim srcline">'+esc(e["verification_note"])+'</div>') if e.get("verification_note") else ''}</td></tr>')
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>Initiative · lead</th><th>Use cases</th>'
            '<th>Status</th><th>Scale (as reported)</th><th>Results evidence</th><th>Overlaps</th><th>Source</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')

def prereq_strip():
    groups = {"UNIVERSAL":[], "UC":[], "DELIVERY":[]}
    for pid, pr in d["prereq"].items():
        g = pr["kind"] if pr["kind"] in ("UNIVERSAL","DELIVERY") else "UC"
        groups[g].append((pid,pr))
    def block(title, items, cls=""):
        lis = "".join(f'<div class="pr"><span class="prid">{pid}</span>{esc(pr["name"])}'
                      f'{"<span class=prkind>"+esc(pr["kind"][3:])+"</span>" if pr["kind"].startswith("UC:") else ""}'
                      f'{statuschip(pr["status"])}</div>' for pid,pr in items)
        return f'<div class="prgroup {cls}"><h4>{title}</h4>{lis}</div>'
    return ('<div class="prwrap">' + block("Universal — absence blocks every column", groups["UNIVERSAL"])
            + block("Per use case — absence blocks named columns", groups["UC"])
            + block("Delivery-risk flags — on the cover, blocking nothing", groups["DELIVERY"], "prdelivery") + "</div>")

def matrix_table():
    head = "".join(f'<th><div class="uchead">{u}</div><div class="ucname">{esc(UC_NAMES[u])}</div></th>' for u in UC_ORDER)
    st  = "".join(f'<td>{statuschip(d["matrix"][u]["status"])}</td>' for u in UC_ORDER)
    why = []
    for u in UC_ORDER:
        m = d["matrix"][u]; w = m["why"]
        if w and w not in ("thin enablers",):
            names = ", ".join(f'{b} {esc(d["prereq"].get(b,{}).get("name",""))}' for b in [x.strip() for x in w.split(",")])
            why.append(f'<td class="why">{names}</td>')
        else:
            why.append(f'<td class="why dim">{esc(w) if w else "—"}</td>')
    # Ruling 13.12: readiness is the enabling mean and is the only one that decides a
    # column. Need and outcome are published beside it as separate rows so the reader can
    # see the whole picture without either being averaged into the reading.
    def _mrow(key):
        return "".join(
            f'<td class="num">'
            + (f'{d["matrix"][u][key]:.2f}' if d["matrix"][u].get(key) is not None else "\u2014")
            + '</td>' for u in UC_ORDER)
    mean, need, outc = _mrow("mean_readiness"), _mrow("mean_need"), _mrow("mean_outcome")
    return ('<div class="tablewrap"><table class="tbl matrix"><thead><tr><th></th>'+head+'</tr></thead><tbody>'
            f'<tr><td class="rowhd">Readiness</td>{st}</tr>'
            f'<tr><td class="rowhd">Named blocker / reason</td>{"".join(why)}</tr>'
            f'<tr><td class="rowhd">Readiness &#8212; enabling indicators</td>{mean}</tr>'
            f'<tr><td class="rowhd">Need &#8212; severity of the problem</td>{need}</tr>'
            f'<tr><td class="rowhd">Outcomes already achieved</td>{outc}</tr>'
            '</tbody></table></div>')

def constraints_table():
    rows = []
    for c in d["constraints"]:
        flag = ' <span class="preflag" title="prerequisite">&#10033;</span>' if c["prereq"] else ""
        rows.append(f'<tr><td class="num">{esc(c["id"])}</td><td>{esc(c["name"])}{flag}</td>'
                    f'<td>{esc(c["pillar"])}</td><td class="num">L{c["level"]}</td></tr>')
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>ID</th><th>Indicator (&#10033; = prerequisite)</th>'
            f'<th>Pillar</th><th>Level</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

def impact_table():
    rows = []
    for iid, txt, ucs in IMPACT:
        v = d["indicators"][iid]
        u = " ".join(f'<span class="uc">{x}</span>' for x in ucs)
        rows.append(f'<tr><td class="num">{iid}</td><td>{esc(txt)} {chip(v["cls"])}</td><td>{u}</td></tr>')
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>ID</th><th>Constraint (A1 need profile)</th>'
            f'<th>Use-case areas that address it</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

def questions_list():
    parts = []
    for t, q, prec in SQ:
        pr = ""
        if prec:
            txt, tier = prec
            pr = f'<p class="qprec"><span class="plab">Precedent</span> {esc(txt)} {tierbadge(tier)}</p>'
        parts.append(f'<li><span class="qtag">{esc(t)}</span><p>{esc(q)}</p>{pr}</li>')
    return f'<ol class="qs">{"".join(parts)}</ol>'

def ledger():
    ver = d["verify"]; ref = d["refresh"]
    bypillar = {}
    for v in ver:
        p = d["indicators"][v["id"]]["pillar"]
        bypillar.setdefault(p, []).append(v)
    vb = ""
    for p in PILLAR_ORDER:
        if p not in bypillar: continue
        items = "".join(f'<li><span class="num">{esc(x["id"])}</span> {esc(x["name"])} {chip(x["cls"])}</li>' for x in bypillar[p])
        vb += f'<div class="ledgroup"><h4>{p} · {esc(PILLAR_NAMES[p])}</h4><ul>{items}</ul></div>'
    rf = "".join(f'<li><span class="num">{esc(x["id"])}</span> {esc(x["name"])} <span class="dim">({x["year"]})</span></li>' for x in ref)
    return (f'<div class="ledger"><div class="ledcol"><h3>Verify first <span class="count">{len(ver)}</span></h3>'
            f'<p class="lednote">Judged rows and recorded gaps — the mission&#8217;s evidence agenda.</p>{vb}</div>'
            f'<div class="ledcol"><h3>Refresh <span class="count">{len(ref)}</span></h3>'
            f'<p class="lednote">Measured, but older than the 3-year staleness rule.</p><ul>{rf}</ul>'
            f'<div class="vintbox"><h4>Data vintage</h4>{vintage_chart()}</div></div></div>')

def kpi_table():
    rows = "".join(f'<tr><td class="num">{esc(k["id"])}</td><td>{esc(k["name"])}</td>'
                   f'<td class="num">{k["value"]:,g}</td><td class="num">{k["year"]}</td><td>{srclink(d["indicators"][k["id"]])} {tierbadge(d["indicators"][k["id"]].get("tier") or tier_of(k["src"]))}</td>'
                   f'<td class="dim">{REFS.get(k["id"], "\u2014")}</td></tr>'
                   for k in d["kpi"])
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>ID</th><th>Indicator</th><th>Baseline value</th>'
            f'<th>Year</th><th>Source</th><th>Reference (context)</th></tr></thead><tbody>{rows}</tbody></table></div>')

def appendix():
    rows = []
    for k, v in d["indicators"].items():
        val = v["value"]
        disp = f'{val:,g}' if isinstance(val,(int,float)) else esc(str(val))
        lvl = f'L{v["level"]}' if v["level"] else "—"
        t = v.get("tier") or tier_of(v["src"])
        rows.append(f'<tr class="cls-{v["cls"].lower()}"><td class="num">{esc(k)}</td><td>{esc(v["name"])}</td>'
                    f'<td>{esc(v["pillar"])}</td><td>{chip(v["cls"])}</td><td class="num">{lvl}</td>'
                    f'<td class="valcell">{disp}</td><td class="num">{v["year"]}</td>'
                    f'<td>{srclink(v)} {tierbadge(t)}</td></tr>')
    btns = "".join(f'<button class="fbtn" data-f="{c.lower()}">{c} <span class="count">{counts[c]}</span></button>'
                   for c in ("Measured","Documented","Judged","Gap"))
    return (f'<div class="fbar" role="group" aria-label="Filter by evidence class"><button class="fbtn active" data-f="all">All 57</button>{btns}</div>'
            '<div class="tablewrap"><table class="tbl appx"><thead><tr><th>ID</th><th>Indicator</th><th>Pillar</th>'
            '<th>Class</th><th>Level</th><th>Recorded value</th><th>Year</th><th>Source · tier (auto-derived)</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')

GLOSS = """<div class="gloss"><h3>Abbreviations in recorded values and sources</h3>
<p>Source and value strings in the tables are quoted verbatim as recorded; alphanumeric series codes (e.g. NV.AGR.EMPL.KD) are World Bank WDI series identifiers. <b>A4AI</b> Alliance for Affordable Internet &#183; <b>AfDB</b> African Development Bank &#183; <b>B-READY</b> World Bank Business Ready assessment &#183; <b>BoA</b> Bank of Agriculture &#183; <b>CBA</b> community-based advisor &#183; <b>CBN</b> Central Bank of Nigeria &#183; <b>CSA</b> climate-smart agriculture &#183; <b>DCAS</b> Digital Climate Advisory Services &#183; <b>DPI</b> digital public infrastructure &#183; <b>EO</b> earth observation &#183; <b>FAO</b> Food and Agriculture Organization of the United Nations &#183; <b>Findex</b> World Bank Global Findex database &#183; <b>FMAFS</b> Federal Ministry of Agriculture and Food Security &#183; <b>FMARD</b> Federal Ministry of Agriculture and Rural Development (predecessor ministry) &#183; <b>G2P</b> government-to-person payments &#183; <b>GAID</b> General Application and Implementation Directive (NDPC, 2025) &#183; <b>GII</b> Global Innovation Index &#183; <b>GNI pc</b> gross national income per capita &#183; <b>GSMA</b> the mobile-industry association &#183; <b>ICR</b> Implementation Completion and Results Report (World Bank) &#183; <b>IDA</b> International Development Association (World Bank) &#183; <b>ILO</b> International Labour Organization &#183; <b>ITU</b> International Telecommunication Union &#183; <b>ITU GCI</b> ITU Global Cybersecurity Index &#183; <b>KPI</b> key performance indicator &#183; <b>LIFE-ND</b> Livelihood Improvement Family Enterprises in the Niger Delta (IFAD) &#183; <b>MoAg</b> Ministry of Agriculture &#183; <b>NAERLS</b> National Agricultural Extension and Research Liaison Services &#183; <b>NAIS</b> National Artificial Intelligence Strategy (2024) &#183; <b>NASRDA</b> National Space Research and Development Agency &#183; <b>NBS</b> National Bureau of Statistics &#183; <b>NCC</b> Nigerian Communications Commission &#183; <b>NDAS</b> National Digital Agriculture Strategy (2020&#8211;2030 draft) &#183; <b>NDPA</b> Nigeria Data Protection Act (2023) &#183; <b>NDPC</b> Nigeria Data Protection Commission &#183; <b>NiMet</b> Nigerian Meteorological Agency &#183; <b>NIMC</b> National Identity Management Commission &#183; <b>NIN</b> National Identification Number &#183; <b>NITDA</b> National Information Technology Development Agency &#183; <b>OECD.AI</b> OECD AI Policy Observatory &#183; <b>SCP</b> Seasonal Climate Prediction (NiMet) &#183; <b>SME</b> small and medium-sized enterprise &#183; <b>STEM</b> science, technology, engineering and mathematics &#183; <b>TTL</b> task team leader &#183; <b>USSD</b> Unstructured Supplementary Service Data (feature-phone menus) &#183; <b>WDI</b> World Development Indicators (World Bank) &#183; <b>WIPO</b> World Intellectual Property Organization.{CFG.get('gloss_extra','')}</p></div>"""

CSS = """
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --panel:#f3f2ee;
  --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --hair:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
  --accent:#1c5cab; --accent-ink:#164a8a;
  --m:#0d366b; --dc:#1c5cab; --j:#5598e7; --g:#b6b4ac; --mchip-ink:#ffffff;
  --bar:#1c5cab; --barstale:#b6b4ac;
  --ok:#0ca30c; --okbg:rgba(12,163,12,.11);
  --warn:#fab219; --warnbg:rgba(250,178,25,.15); --warnink:#6b4a00;
  --crit:#d03b3b; --critbg:rgba(208,59,59,.10);
  --neut:#898781; --neutbg:rgba(137,135,129,.13);
  --banner:#fdf6e6; --bannerbord:#e8d9ae;
  --narr:#f6f4ef;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --page:#0d0d0d; --surface:#1a1a19; --panel:#222220;
    --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --hair:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
    --accent:#86b6ef; --accent-ink:#9ec5f4;
    --m:#9ec5f4; --dc:#3987e5; --j:#184f95; --g:#6e6c66; --mchip-ink:#0d0d0d;
    --bar:#3987e5; --barstale:#6e6c66;
    --ok:#0ca30c; --okbg:rgba(12,163,12,.16);
    --warn:#fab219; --warnbg:rgba(250,178,25,.14); --warnink:#fab219;
    --crit:#e66767; --critbg:rgba(230,103,103,.14);
    --neut:#898781; --neutbg:rgba(137,135,129,.18);
    --banner:#26200f; --bannerbord:#4d3f18;
    --narr:#20201d;
  }
}
:root[data-theme="dark"]{
  --page:#0d0d0d; --surface:#1a1a19; --panel:#222220;
  --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
  --hair:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
  --accent:#86b6ef; --accent-ink:#9ec5f4;
  --m:#9ec5f4; --dc:#3987e5; --j:#184f95; --g:#6e6c66; --mchip-ink:#0d0d0d;
  --bar:#3987e5; --barstale:#6e6c66;
  --ok:#0ca30c; --okbg:rgba(12,163,12,.16);
  --warn:#fab219; --warnbg:rgba(250,178,25,.14); --warnink:#fab219;
  --crit:#e66767; --critbg:rgba(230,103,103,.14);
  --neut:#898781; --neutbg:rgba(137,135,129,.18);
  --banner:#26200f; --bannerbord:#4d3f18;
  --narr:#20201d;
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font:16px/1.55 "Archivo",system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:0 28px 90px}
a{color:var(--accent-ink)}
h1,h2,h3,h4{font-family:"Archivo",system-ui,sans-serif;text-wrap:balance;margin:0}
p{margin:.5em 0}

/* masthead */
.mast{padding:54px 0 0}
.kicker{font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--ink2)}
.kicker b{color:var(--accent-ink)}
h1{font-size:clamp(40px,6vw,58px);font-weight:700;letter-spacing:-.015em;line-height:1.04;margin:10px 0 4px}
.subtitle{font-family:"Source Serif 4",Georgia,serif;font-size:20px;color:var(--ink2);max-width:56ch;margin:6px 0 18px}
.metarow{display:flex;flex-wrap:wrap;gap:24px;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);
  padding:12px 0;font-size:13px;color:var(--ink2)}
.metarow b{color:var(--ink);font-weight:600}
.spine{display:flex;gap:2px;margin:18px 0 6px;height:14px}
.spine .cell{flex:1;border-radius:2px;min-width:6px}
.cell-measured{background:var(--m)}.cell-documented{background:var(--dc)}
.cell-judged{background:var(--j)}.cell-gap{background:var(--g)}
.spinecap{font-size:12px;color:var(--muted);margin:0 0 8px}
.banner{display:flex;gap:12px;align-items:flex-start;background:var(--banner);border:1px solid var(--bannerbord);
  border-radius:8px;padding:14px 18px;margin:22px 0 8px;font-size:14.5px}
.banner .bicon{font-size:16px;line-height:1.4}
.banner b{font-weight:650}

/* how to read */
.howto{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 20px 8px;margin:20px 0 0}
.howto h3{font-size:11.5px;font-weight:650;letter-spacing:.12em;text-transform:uppercase;color:var(--accent-ink);margin:0 0 10px}
.howgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:4px 26px}
.how h4{font-size:12px;font-weight:650;color:var(--ink);margin:0 0 2px}
.how p{font-size:12.5px;line-height:1.55;color:var(--ink2);margin:0 0 12px}
.gloss{margin-top:26px;border-top:1px solid var(--hair);padding-top:14px}
.gloss h3{font-size:14px;color:var(--ink);margin-bottom:8px}
.gloss p{font-size:12px;line-height:1.7;color:var(--ink2);column-count:2;column-gap:34px;margin:0}
@media (max-width:760px){.gloss p{column-count:1}}
.gloss b{color:var(--ink);font-weight:600}

/* in brief */
.brief{margin:34px 0 8px}
.brief .sentence{font-family:"Source Serif 4",Georgia,serif;font-size:21px;line-height:1.5;max-width:62ch;margin:0 0 22px}
.brieftiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.btile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.btile .k{font-size:11.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.btile .v{font-size:26px;font-weight:650;letter-spacing:-.01em;margin-top:4px}
.btile .m{font-size:13px;color:var(--ink2);margin-top:2px}

/* sections */
section{margin:56px 0 0}
.sechead{display:flex;align-items:baseline;justify-content:space-between;gap:16px;
  border-bottom:2px solid var(--ink);padding-bottom:8px;margin-bottom:6px}
.sechead h2{font-size:23px;font-weight:700;letter-spacing:-.01em}
.secno{display:inline-block;min-width:34px;color:var(--accent-ink);font-variant-numeric:tabular-nums}
.feeds{font-size:11.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);white-space:nowrap}
.secnote{font-size:14px;color:var(--ink2);max-width:76ch;margin:8px 0 14px}
.prose{font-family:"Source Serif 4",Georgia,serif;font-size:17px;line-height:1.65;max-width:70ch}

/* narrative register */
.narrative{background:var(--narr);border:1px solid var(--border);border-left:3px solid var(--accent);
  border-radius:0 10px 10px 0;padding:18px 24px;margin:18px 0;max-width:900px}
.narrlab{font-size:11px;font-weight:650;letter-spacing:.12em;text-transform:uppercase;color:var(--accent-ink);margin:0 0 6px}
.narrative p{font-family:"Source Serif 4",Georgia,serif;font-size:16.5px;line-height:1.66;color:var(--ink);margin:.5em 0}

/* chips & badges */
.chip{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:5px;
  font-size:11.5px;font-weight:700;color:#fff;vertical-align:middle}
.chip-measured{background:var(--m);color:var(--mchip-ink)}.chip-documented{background:var(--dc)}
.chip-judged{background:var(--j)}.chip-gap{background:var(--g);color:var(--page)}
.tier{display:inline-block;border:1px solid var(--baseline);border-radius:4px;padding:0 5px;
  font-size:11px;font-weight:650;letter-spacing:.04em;color:var(--ink2);vertical-align:middle;cursor:help}
.st{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 10px 2px 7px;
  font-size:12.5px;font-weight:650;white-space:nowrap}
.st-ic{font-size:11px}
.st-ok{background:var(--okbg);color:var(--ok)}
.st-warn{background:var(--warnbg);color:var(--warnink)}
.st-crit{background:var(--critbg);color:var(--crit)}
.st-neut{background:var(--neutbg);color:var(--ink2)}
.uc{display:inline-block;background:var(--panel);border:1px solid var(--border);border-radius:4px;
  padding:0 5px;font-size:11px;font-weight:650;letter-spacing:.04em;color:var(--ink2);margin:1px 1px}
.stale-tag{display:inline-block;background:var(--warnbg);color:var(--warnink);border-radius:4px;
  padding:0 5px;font-size:10.5px;font-weight:650;letter-spacing:.05em;text-transform:uppercase;vertical-align:middle}
.preflag{color:var(--crit);font-weight:700}
.dim{color:var(--muted);font-size:12.5px}.dimlab{fill:var(--muted);font-size:11px}

/* tiles */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:16px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.tile-k{font-size:12.5px;font-weight:600;color:var(--ink2)}
.tile-v{font-size:30px;font-weight:650;letter-spacing:-.01em;margin:6px 0 4px;font-variant-numeric:tabular-nums}
.tile-m{font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.tile-gap{border-style:dashed}
.gaplist{margin:8px 0;padding-left:18px;font-size:13.5px;color:var(--ink2)}
.gaplist li{margin:2px 0}

/* charts */
.viz{width:100%;height:auto;display:block;margin:12px 0 4px}
.viz text{font-family:"Archivo",system-ui,sans-serif}
.rowlab{fill:var(--ink);font-size:13px}
.vallab{fill:var(--ink);font-size:12.5px;font-weight:650}
.cut{stroke:var(--hair);stroke-width:1;stroke-dasharray:3 3}
.cutlab{fill:var(--muted);font-size:11px}
.bandlab{fill:var(--muted);font-size:11.5px;letter-spacing:.06em;text-transform:uppercase}
.track{stroke:var(--hair);stroke-width:1}
.bar{fill:var(--bar)}.bar.stale{fill:var(--barstale)}
.weakbar{fill-opacity:.55;stroke:var(--bar);stroke-width:1.4;stroke-dasharray:4 3}
.seg-measured{fill:var(--m)}.seg-documented{fill:var(--dc)}.seg-judged{fill:var(--j)}.seg-gap{fill:var(--g)}
.seglab{fill:#fff;font-size:11.5px;font-weight:650}
.seglab-m{fill:var(--mchip-ink);font-size:11.5px;font-weight:650}
.seglab-dark{fill:var(--ink);font-size:11.5px;font-weight:650}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12.5px;color:var(--ink2);margin:2px 0 0}
.legend .sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.caption{font-size:12.5px;color:var(--muted);max-width:80ch;margin:6px 0 0}

/* tables */
.tablewrap{overflow-x:auto;margin:14px 0}
.tbl{border-collapse:collapse;width:100%;font-size:13.5px;background:var(--surface);
  border:1px solid var(--border);border-radius:10px;overflow:hidden}
.tbl th{font-size:11px;font-weight:650;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
  text-align:left;padding:10px 12px;border-bottom:1px solid var(--hair);background:var(--panel)}
.tbl td{padding:9px 12px;border-bottom:1px solid var(--hair);vertical-align:top}
.tbl tbody tr:last-child td{border-bottom:none}
.tbl tbody tr:hover td{background:var(--panel)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.rn{font-weight:600;min-width:210px}
.srcline{margin-top:2px}
.valcell{max-width:260px}
.matrix th{text-align:center}
.matrix td{text-align:center}
.matrix .rowhd{text-align:left;font-weight:600;white-space:nowrap}
.matrix .why{font-size:12.5px;max-width:150px}
.uchead{font-size:15px;font-weight:700;letter-spacing:0;color:var(--ink);text-transform:none}
.ucname{font-size:10.5px;font-weight:600;color:var(--muted);text-transform:none;letter-spacing:.02em}

/* prerequisites */
.prwrap{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:14px 0}
.prgroup{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.prgroup h4{font-size:11.5px;font-weight:650;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
.pr{display:flex;align-items:center;gap:8px;padding:5px 0;font-size:13.5px;flex-wrap:wrap}
.pr .st{margin-left:auto}
.prid{font-variant-numeric:tabular-nums;color:var(--muted);font-size:12px;min-width:30px}
.prkind{font-size:10.5px;font-weight:650;color:var(--accent-ink);letter-spacing:.05em}

/* questions */
.qs{list-style:none;counter-reset:q;margin:16px 0;padding:0;max-width:900px}
.qs li{counter-increment:q;display:grid;grid-template-columns:44px 1fr;gap:0 14px;
  padding:14px 0;border-bottom:1px solid var(--hair)}
.qs li::before{content:"Q" counter(q);font-weight:700;color:var(--accent-ink);font-size:15px;grid-row:1/4}
.qtag{font-size:11px;font-weight:650;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.qs p{font-family:"Source Serif 4",Georgia,serif;font-size:16.5px;line-height:1.55;margin:3px 0 0}
.qprec{font-size:13px;color:var(--ink2);margin:6px 0 0;grid-column:2}
.qprec .plab{font-weight:650;color:var(--accent-ink);letter-spacing:.08em;font-size:10.5px;text-transform:uppercase;margin-right:6px}
.tile-ref{font-size:12px;color:var(--accent-ink);margin:0 0 4px}
.qcline{font-size:12.5px;color:var(--ink2);margin-top:14px;border-top:1px solid var(--hair);padding-top:10px}

/* ledger */
.ledger{display:grid;grid-template-columns:1.15fr .85fr;gap:22px;margin:16px 0}
@media (max-width:820px){.ledger{grid-template-columns:1fr}}
.ledcol{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 20px}
.ledcol h3{font-size:16px;font-weight:700}
.ledcol .count{display:inline-block;background:var(--panel);border-radius:999px;padding:0 9px;
  font-size:12.5px;color:var(--ink2);vertical-align:2px}
.lednote{font-size:13px;color:var(--muted);margin:4px 0 10px}
.ledgroup h4{font-size:12px;font-weight:650;color:var(--ink2);margin:12px 0 4px}
.ledcol ul{margin:4px 0;padding-left:2px;list-style:none}
.ledcol li{font-size:13.5px;padding:3px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.vintbox{margin-top:18px;border-top:1px solid var(--hair);padding-top:10px}
.vintbox h4{font-size:12px;font-weight:650;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}

/* appendix filter */
.fbar{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 4px}
.fbtn{font:600 13px "Archivo",system-ui,sans-serif;color:var(--ink2);background:var(--surface);
  border:1px solid var(--border);border-radius:999px;padding:6px 14px;cursor:pointer}
.fbtn:hover{background:var(--panel)}
.fbtn.active{background:var(--ink);color:var(--page);border-color:var(--ink)}
.fbtn:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.fbtn .count{opacity:.65;font-weight:500}

/* footer */
.method{margin-top:70px;border-top:2px solid var(--ink);padding-top:18px;font-size:13.5px;color:var(--ink2)}
.method h3{font-size:14px;color:var(--ink);margin-bottom:8px}
.method ol{margin:6px 0;padding-left:20px}
.method li{margin:3px 0}
.prohib{margin-top:14px;font-size:12.5px;color:var(--muted);max-width:90ch}

@page{size:A4;margin:12mm 10mm}
@media print{
  body{background:#fff}
  .fbar{display:none}
  section{break-inside:auto;margin-top:30px}
  .banner{break-inside:avoid}
  .wrap{max-width:none;padding:0}
  /* A table wider than the page used to be CLIPPED here: .tablewrap scrolls on screen, but in
     print overflow has nothing to scroll into, so the rightmost columns were simply cut off the
     page. The register lost Overlaps and Source — its whole provenance — while the caption
     underneath still promised a deep link per entry (defect 40). Print lays every table out to
     the page width instead, and wraps rather than overflows. */
  .tablewrap{overflow:visible!important;margin:10px 0}
  .tbl{table-layout:fixed;width:100%;font-size:9.5px;border-radius:0;break-inside:auto}
  .tbl th{font-size:8px;letter-spacing:.05em;padding:5px 6px}
  .tbl td{padding:5px 6px;overflow-wrap:anywhere;word-break:normal;hyphens:auto}
  .tbl thead{display:table-header-group}
  .tbl tbody tr{break-inside:avoid}
  .rn{min-width:0}
  .valcell{max-width:none}
  .matrix .why{max-width:none}
  .srcline{font-size:8.5px}
  .tbl a{overflow-wrap:anywhere}
  .viz{max-width:100%;height:auto}
  .appx{font-size:8.5px}
}
@media (prefers-reduced-motion: reduce){*{scroll-behavior:auto}}
"""

JS = """
document.querySelectorAll('.fbtn').forEach(function(b){
  b.addEventListener('click', function(){
    document.querySelectorAll('.fbtn').forEach(function(x){x.classList.remove('active')});
    b.classList.add('active');
    var f = b.getAttribute('data-f');
    document.querySelectorAll('.appx tbody tr').forEach(function(tr){
      tr.style.display = (f==='all' || tr.classList.contains('cls-'+f)) ? '' : 'none';
    });
  });
});
"""

HOWTO = """<div class="howto"><h3>How to read this report</h3><div class="howgrid">
<div class="how"><h4>Evidence classes</h4><p><span class="chip chip-measured">M</span> Measured &#8212; a number was recorded &nbsp;<span class="chip chip-documented">D</span> Documented &#8212; a citable artifact &nbsp;<span class="chip chip-judged">J</span> Judged &#8212; assessor statement without artifact &nbsp;<span class="chip chip-gap">G</span> Gap &#8212; searched for and not found. The class is derived from the recorded value, never chosen.</p></div>
<div class="how"><h4>Levels &amp; bands</h4><p>Every indicator carries a level, L1&#8211;L5. A pillar band is the level the plain mean of its recorded levels rounds to: Nascent &lt;1.5 &#8226; Emerging &lt;2.5 &#8226; Established &lt;3.5 &#8226; Advanced &lt;4.5 &#8226; Transformative &#8805;4.5. Beside the band is a signed margin, the distance from the level the band is named for: +0.00 means the pillar sits squarely at that level, and a margin near &#177;0.5 means it is on the edge of the next one. Recorded gaps and levels withheld pending ratification are not averaged in, so where a pillar has any, the count of rated rows is printed beside the mean. A band in (parentheses) rests more on judgment, gaps and withheld levels than on levelled evidence.</p></div>
<div class="how"><h4>Pillars</h4><p>A1 Agriculture &amp; need &#8226; C1 Connectivity &amp; access &#8226; C2 Data &amp; digital public infrastructure (DPI) &#8226; C3 Policy &amp; safeguards &#8226; C4 People &amp; institutions &#8226; E1 Innovation, solutions &amp; emerging tech &#8226; O1 Outcomes &amp; inclusion.</p></div>
<div class="how"><h4>Use-case areas</h4><p>ADV advisory &amp; extension &#8226; SMF smart farming &#8226; MKT market linkage &amp; pricing &#8226; SCM supply chain &#8226; FIN financial services &#8226; AGI agricultural intelligence (AI-enabled analytics and decision systems).</p></div>
<div class="how"><h4>Source tiers</h4><p>T1 official statistics &amp; international databases &#8226; T2 peer-reviewed &amp; flagship reports &#8226; T3 government legal and policy artifacts &#8226; T4 reputable grey literature &#8226; T5 news/vendor material (admitted only in the register, for existence facts). Tiers are reported, never weighted.</p></div>
<div class="how"><h4>Playbook tags &amp; IDs</h4><p>&#8220;Feeds Playbook 1A&#8230;3C&#8221; ties each section to the step of the DAR Playbook (World Bank&#8211;Gates Foundation&#8211;BCG, 2025) it serves: 1A problem statement &#8226; 1B landscape &#8226; 1C ecosystem maturity &#8226; 2B use-case prioritization &#8226; 3C results baseline &#8226; 4A roadmap sequencing. Indicator IDs (e.g. 3.11) are the model&#8217;s census identifiers &#8212; all 57 resolve in the appendix; &#10033; marks a prerequisite.</p></div>
</div></div>"""

legend_html = ('<div class="legend">'
  '<span><span class="sw" style="background:var(--m)"></span>Measured</span>'
  '<span><span class="sw" style="background:var(--dc)"></span>Documented</span>'
  '<span><span class="sw" style="background:var(--j)"></span>Judged</span>'
  '<span><span class="sw" style="background:var(--g)"></span>Gap</span></div>')

def narr_block(text):
    if not text: return ""
    return ('<div class="narrative"><p class="narrlab">Researched narrative \u00b7 desk draft \u2014 cites scored rows; sets no level</p>'
            + "".join(f"<p>{t}</p>" for t in text) + "</div>")
narr_problem = narr_block(CFG.get("narrative_problem", []))
narr_register = narr_block(CFG.get("narrative_register", []) + ([esc(reg["overlap_finding"])] if reg.get("overlap_finding") else []))

def build_brief(d):
    P = d["pillars"]
    rated = {p: v for p, v in P.items() if v["mean"] is not None}
    hi = max(rated, key=lambda p: rated[p]["mean"]); lo = min(rated, key=lambda p: rated[p]["mean"])
    weak = [p for p in PILLAR_ORDER if P[p].get("weak")]
    mc = Counter(m["status"] for m in d["matrix"].values())
    blocked = [(uc, m["why"]) for uc, m in d["matrix"].items() if m["status"] == "Blocked"]
    bands = {}
    for p in PILLAR_ORDER:
        if P[p]["mean"] is None: continue
        bands.setdefault(P[p]["band"], []).append(p)
    parts = []
    for bandname in ["Transformative", "Advanced", "Established", "Emerging", "Nascent"]:
        if bandname in bands:
            parts.append(f"{', '.join(bands[bandname])} read <em>{bandname}</em>")
    sent = "; ".join(parts) + "."
    if weak:
        sent += f" In {', '.join(weak)} the band renders parenthesized \u2014 on current evidence, a finding about the assessment as much as the country."
    vb = d["counts"]["Measured"] + d["counts"]["Documented"]
    sent += f" The assessment recorded values for {vb} of {N} indicators and named {d['counts']['Gap']} gaps; nothing here rests on an unrecorded claim."
    if d.get("held"):
        sent += (f" A further {d['held']} carry a recorded value but no level: what was found measures a different "
                 f"construct from what the indicator names, so the level is withheld rather than guessed, and those "
                 f"rows are outside every mean.")
    unver = [(uc, m["why"]) for uc, m in d["matrix"].items() if m["status"] == "Unverified"]
    bits = [f"{uc} blocked by {why}" for uc, why in blocked]
    if unver:
        reason = unver[0][1].replace("universal unverified: ", "")
        bits.append(f"{len(unver)} column{'s' if len(unver) > 1 else ''} unresolved on prerequisite {reason}")
    btxt = " \u00b7 ".join(bits) if bits else "no blocked or unresolved columns"
    stale_n = sum(P[p]["stale"] for p in PILLAR_ORDER)
    return f"""<div class="brief"><p class="sentence">{sent}</p>
<div class="brieftiles">
 <div class="btile"><div class="k">Strongest pillar</div><div class="v">{hi} \u00b7 {rated[hi]['mean']:.2f}</div><div class="m">{esc(PILLAR_NAMES[hi])} \u2014 {('('+rated[hi]['band']+')') if P[hi]['weak'] else rated[hi]['band']}</div></div>
 <div class="btile"><div class="k">Weakest pillar</div><div class="v">{lo} \u00b7 {rated[lo]['mean']:.2f}</div><div class="m">{esc(PILLAR_NAMES[lo])} \u2014 {('('+rated[lo]['band']+')') if P[lo]['weak'] else rated[lo]['band']}</div></div>
<div class="btile"><div class="k">Use-case readiness</div><div class="v">{mc.get('Ready',0)}\u2009R \u00b7 {mc.get('Partial',0)}\u2009P \u00b7 {mc.get('Blocked',0)}\u2009B \u00b7 {mc.get('Unverified',0)}\u2009U</div><div class="m">Ready \u00b7 Partial \u00b7 Blocked \u00b7 Unverified \u2014 {esc(btxt)}</div></div>
 <div class="btile"><div class="k">Evidence base</div><div class="v">{vb}/{N}</div><div class="m">value-backed (M+D) \u00b7 {d['rated']} levelled \u00b7 {d['counts']['Gap']} recorded gaps \u00b7 {d['held']} levels withheld \u00b7 {stale_n} stale</div></div>
</div></div>"""
brief = build_brief(d)

html_out = f"""<meta charset="utf-8">
<title>{CFG['country']} Digital Agriculture Diagnostic</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">
<style>{CSS}</style>
<div class="wrap">

<header class="mast">
  <div class="kicker">Digital Agriculture Maturity Model · <b>DAMM v1.7 draft</b> · Diagnostic Package</div>
  <h1>{CFG['country']}</h1>
  <p class="subtitle">Digital agriculture diagnostic — the starting document for the National Digital Agriculture Roadmap {CFG['period']}.</p>
  <div class="metarow">
    <span>Assessment: <b>{CFG['assessment']}</b></span>
    <span>Model: <b>DAMM v1.7</b></span>
    <span>Evidence compiled: <b>22 Aug 2026</b></span>
    <span>Rendered: <b>22 Aug 2026</b></span>
    <span>Indicators: <b>57</b> · 7 pillars × 4 layers</span>
  </div>
  {spine()}
  <p class="spinecap">The evidence spine — one cell per indicator in census order: {counts["Measured"]} Measured · {counts["Documented"]} Documented · {counts["Judged"]} Judged · {counts["Gap"]} recorded gaps.</p>
  <div class="banner"><span class="bicon">&#9888;</span><div><b>Desk assessment, pending mission validation.</b>
  {esc(CFG["assessment"].capitalize())}; {counts["Gap"]} of {N} indicators are recorded gaps and {counts["Judged"]} rest on judgment. No level exists without a recorded value;
  bands with weak evidence render parenthesized. Not for circulation, cross-country ranking, or financing decisions.</div></div>
{HOWTO}
</header>

{brief}

{sec(1, "Country problem statement", "Playbook 1A",
     a1_tiles() + narr_problem,
     A1_NOTE)}

{sec(2, "Initiative & solutions register", "Playbook 1B",
     register_table()
     + f'<p class="caption">{esc(reg.get('status_note', CFG.get('register_note','Register verified to the Source-Tier Protocol, gauntlet loop 1 (22 Aug 2026).')))} Status uses the presence ladder (Announced / Adopted / Operating / Closed). T5 rows evidence existence only; scale figures marked &#8220;vendor-reported&#8221; are claims, not findings. Register rows may serve as Documented evidence for E1/C4 indicators — cited by row.</p>'
     + narr_register,
     "One row per initiative, tier-badged. The register is the presence ladder applied to the landscape.")}

{sec(3, "Pillar profile", "Playbook 1C",
     pillar_chart()
     + f'<p class="caption">Band cut-offs at {BAND_CUTS} (half-open).{" Hatched bars render parenthesized: judged and gap rows outnumber measured and documented ones, so the band is a finding about the assessment as much as about the country." if _weak else ""}</p>'
     + evidence_chart() + legend_html
     + f'<p class="caption">{EVID_NOTE}</p>')}

{sec(4, "Layer profile", "Playbook 1C",
     layer_chart()
     + (f'<p class="caption">Leapfrog gap = mean(Foundation) − mean(Transformation) = <b>{d["leapfrog"]["gap"]:+.2f}</b> — {esc(d["leapfrog"]["reading"]).lower()} (flag at |gap| &gt; 1.5). The national gap is calm; the use-case grain below is where fragility shows.</p>'
        if d["leapfrog"]["gap"] is not None else
        '<p class="caption">Leapfrog gap = mean(Foundation) − mean(Transformation): not computable, because one of the two layers carries no rated row. An absent gap is not a calm one.</p>'))}

{sec(5, "Use-case readiness matrix", "Playbook 2B — Digital Readiness",
     matrix_table() + prereq_strip(),
     MATRIX_NOTE)}

{sec(6, "Impact side", "Playbook 2B — Impact",
     impact_table()
     + '<p class="caption">Mapping: standard v1.7 crosswalk, curated by the task team leader (TTL). Constraints recorded as gaps still map — an unmeasured constraint is a task for the evidence ledger, not a reason to drop the use case.</p>')}

{sec(7, "Binding constraints", "Playbook 2B · 4A",
     constraints_table(),
     "Every indicator at L1–L2, ascending. &#10033; marks prerequisites — constraints that also gate a readiness column.")}

{sec(8, "Strategic questions", "Step 2 agenda",
     questions_list()
     + '<p class="caption">Derived mechanically from the readiness matrix and the binding-constraints list; task team leader curation pending. Precedent pointers are existence proofs drawn from the DAMM Global Practice Library \u2014 relevance is selected by the readiness matrix; never endorsements, never country comparisons. Authored additions are marked as such.</p>')}

{sec(9, "Evidence ledger", "Mission planning",
     ledger(),
     "The assessment&#8217;s honest edge: what to verify, what to refresh, before any of this is called a baseline.")}

{sec(10, "KPI baseline", "Playbook 3C",
     kpi_table()
     + '<p class="caption">Every Measured A1/O1 row, with value, source, year — the roadmap&#8217;s results framework starts from these six, and grows as the ledger converts gaps to measurements.</p>')}

<section id="appx"><header class="sechead"><h2><span class="secno">A</span>All 57 indicators</h2><span class="feeds">full record</span></header>
{appendix()}
</section>

<div class="method">
<h3>Method — DAMM v1.7 in five lines</h3>
<ol>
<li>Every indicator gets a value, a source, and a year — or a recorded gap. No level without a recorded value.</li>
<li>The value sets the evidence class: number → Measured · citable artifact → Documented · neither → Judged · looked-for-and-not-found → Gap. Derived, never chosen.</li>
<li>Pillars report a band and their evidence composition. No weights, no overall score, no stage.</li>
<li>Prerequisites bind on presence only; a failed prerequisite blocks its use-case column, not a global stage.</li>
<li>Source tiers (T1–T5) are reported, never weighted. Researched narrative cites scored rows; <b>no narrative claim sets a level.</b></li>
</ol>
<p class="qcline"><b>Automated quality control:</b> {len(QC)}/{len(QC)} renderer checks passed (consistency, provenance, reconciliation and presentation \u2014 a failed check blocks the render). <b>Stage 1 automated challenge:</b> {CFG.get("automated_challenge") or "not recorded \u2014 machine QC only; does not satisfy G1 or G2"}. <b>Human gates:</b> G1, assessor confirmation of every machine-filled row \u2014 {HUMAN_GATES["G1"]}; G2, independent peer review of all prerequisite and Judged rows plus a 15% sample of the remainder \u2014 {HUMAN_GATES["G2"]}; G3, task team leader/country-owner sign-off against all seven QC affirmations \u2014 {HUMAN_GATES["G3"]}.</p>\n<p class="prohib">Prohibitions: no cross-country ranking · no band as a project development objective (PDO), disbursement-linked indicator (DLI), or disbursement condition · no automatic financing decisions ·
no public claim before human review. Rendered by the DAMM v1.7 engine and report pipeline from the scored indicator set and the initiative register for {CFG["country"]}; the same pipeline renders any country&#8217;s assessment. Source tiers are assigned by the DAMM Source-Tier Protocol lookup.</p>
{GLOSS.replace("{CFG.get('gloss_extra','')}", CFG.get('gloss_extra',''))}
</div>

</div>
<script>{JS}</script>
"""

open(OUT, "w").write(html_out)
print(f"wrote {OUT} ({len(html_out):,} bytes)")
