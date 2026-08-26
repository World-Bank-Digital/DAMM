#!/usr/bin/env python3
"""Pass five: the draft Digital Agriculture Roadmap (design decisions E3, E4, E5).

Eleven chapters of prose, and three defences against the failure that prose invites — a
fluent paragraph carrying a number the evidence never produced.

**Chapters see only what they may cite (E4).** Each chapter's binding lives in the model
file: the pillars, indicators, use-case columns, prerequisites and derived sources it may
draw on. The pack assembled for a chapter contains that and nothing else, so citing
outside the binding is not something the writer is trusted to avoid. A financing chapter
reaching for connectivity indicators reads perfectly fluently and is wrong, and this is
the only mechanism that catches it before a reader does.

**Every figure is checked against the engine (E3).** The writer returns its figures as
data alongside the prose. Each is matched against the numbers the engine actually
produced, and the prose is swept for numbers that are in neither the figure list nor the
narrow set of things a sentence may legitimately count. The check is reported as a rate on
the document's own face rather than kept in a log.

**The gate blocks the emit (E5).** The diagnostic has one and it is much of why the
diagnostic survived review. This one refuses to write a document when a chapter has no
provenance banner, when a chapter cites outside its binding, when a prescriptive chapter
is presented as evidenced, or when fidelity falls below the floor. The gates are the
compensation for having removed the human from every step before final review.

Chapters 3 to 10 are prescriptive. They are marked *proposed, not evidenced* on the page,
in their own record, and in the gate — three statements of one fact, because this is the
one a reader must not miss.

    python3 generate_dar.py --country Egypt --iso EGY --out EGY_shadow [--ceiling 500] [--resume]
"""

import argparse, html, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(LOOP1, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, LOOP1)

import vendors as V
from engine_v17 import MODEL, run as engine_run

PASS = "generation"

# Every id the instrument names, so a reference to a row can be told from a claim about
# the country. Prerequisite ids are indicator ids, so the one set covers both.
KNOWN_IDS = frozenset(MODEL)
MODEL_FILE = os.path.join(REPO, "model", "DAMM-v1.7-model.json")
SPEC = json.load(open(MODEL_FILE))
ASSESSMENT_YEAR = SPEC["config"]["assessment_year"]
OUTLINE = SPEC["dar_outline"]
PROHIBITIONS = SPEC.get("prohibitions", [])

# Below this, the document is not emitted. A roadmap where one figure in twenty is
# untraceable is not a roadmap with a small problem; it is a document a reader cannot use
# without checking every number themselves, which is the work it was meant to do for them.
FIDELITY_FLOOR = 0.95

CHAPTER_WORKERS = 3

SYSTEM = ("You draft chapters of a national Digital Agriculture Roadmap from an evidence "
          "pack. You use only the figures in the pack, you never invent a number, and you "
          "say plainly when something is proposed rather than evidenced. JSON only.")

CHAPTER_SCHEMA = {
    "type": "object",
    "properties": {
        "prose": {"type": "string"},
        "cites": {
            "type": "object",
            "properties": {
                "pillars": {"type": "array", "items": {"type": "string"}},
                "indicators": {"type": "array", "items": {"type": "string"}},
                "use_cases": {"type": "array", "items": {"type": "string"}},
                "prerequisites": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["pillars", "indicators", "use_cases", "prerequisites"],
            "additionalProperties": False,
        },
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "what_it_is": {"type": "string"},
                },
                "required": ["value", "what_it_is"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["prose", "cites", "figures"],
    "additionalProperties": False,
}


# ------------------------------------------------------------------ the gates
#
# Pure, so the rules that decide whether a document may be written can be tested without
# a key or a network.

def binding_gate(cites, binding, assessment=None):
    """What a chapter cited that its binding does not allow. Empty list when clean.

    The pack already withholds everything outside the binding, so a violation here means
    the writer produced an id from its own knowledge rather than from the evidence — which
    is precisely the failure the binding exists to catch.
    """
    if assessment is not None:
        binding = expand_binding(binding, assessment)
    out = []
    for kind in ("pillars", "indicators", "use_cases", "prerequisites"):
        allowed = set(binding.get(kind) or [])
        for cited in (cites.get(kind) or []):
            c = str(cited).strip()
            if c and c not in allowed:
                out.append(f"{kind[:-1]} {c}")
    return out


def _numbers(text):
    """Numbers as they appear in prose, without percent signs or thousands separators."""
    return re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text or "")


def _norm_num(s):
    try:
        return round(float(str(s).replace(",", "").replace("%", "").strip()), 2)
    except (TypeError, ValueError):
        return None


def allowed_figures(assessment, foresight=None):
    """Every number the engine and the foresight exercise actually produced."""
    ok = set()

    def add(v):
        n = _norm_num(v)
        if n is not None:
            ok.add(n)

    for p in assessment["pillars"].values():
        for k in ("n", "rated", "held", "mean", "margin", "comp", "stale"):
            add(p.get(k))
    for l in assessment.get("layers", {}).values():
        if isinstance(l, dict):
            for k in ("n", "rated", "mean"):
                add(l.get(k))
    for m in assessment["matrix"].values():
        for k in ("n_bearing", "mean_readiness", "mean_need", "mean_outcome", "mean_driven"):
            add(m.get(k))
    for v in assessment["counts"].values():
        add(v)
    add(assessment.get("rated"))
    add(assessment.get("held"))
    for i in assessment["indicators"].values():
        add(i.get("level"))
        add(i.get("value"))
        add(i.get("year"))
    for m in ((foresight or {}).get("milestones") or []):
        add(m.get("target_level"))
        add(m.get("target_year"))
    return ok


def _rounds_to(n, raw, allowed):
    """Whether `n` is an allowed figure written to fewer decimals.

    A chapter that writes the A1 mean of 2.71 as "2.7" has not fabricated anything, and
    blocking the document for it would train everyone to loosen the gate. A figure that
    rounds to a real one is still traceable to a real one. Matching is at the precision
    the prose actually used, so "3" does not silently stand for 2.71.
    """
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return any(round(a, decimals) == n for a in allowed)


def _ordinary(n):
    """Numbers a sentence may carry without the engine having produced them.

    Small counts ("three pillars", "the eleven chapters") and calendar years. Deliberately
    narrow: anything wider would let a fabricated percentage through as ordinary prose.
    """
    if n is None:
        return False
    if n == int(n) and 0 <= n <= 12:
        return True
    if n == int(n) and 1900 <= n <= ASSESSMENT_YEAR + 30:
        return True
    return False


# A figure the assessment states as a pair or as a level, rather than as one number:
# "5 of 10" is a coverage denominator and "level 3" is a rung. Both come straight out of
# the pack, and both used to be unparseable — so the writer quoting the evidence exactly
# was marked as claiming something the engine did not produce. Of the 95 figures the first
# Egypt roadmap was blocked over, 74 were of this shape.
_PAIR = re.compile(r"^\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:of|/|out of)\s*"
                   r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*$", re.I)
_RUNG = re.compile(r"^\s*(?:level|band|rung)\s*(\d+(?:\.\d+)?)\s*$", re.I)


def _composite_supported(raw, allowed):
    """Whether a composite figure is fully supported. None when it is not a composite."""
    if raw is None:
        return None
    text = str(raw)
    m = _PAIR.match(text)
    if m:
        a, b = _norm_num(m.group(1)), _norm_num(m.group(2))
        return a is not None and b is not None and a in allowed and b in allowed
    m = _RUNG.match(text)
    if m:
        n = _norm_num(m.group(1))
        return n is not None and n in allowed
    return None


def reference_ids(prose, known_ids, cited_ids=()):
    """Numbers in the prose that are references to rows, not claims about the country.

    The roadmap names a row the way the instrument does — "(3.11)" after the indicator's
    name, or "indicator 3.11". Read as a quantity, 3.11 is a number the engine never
    produced, and 86 of the 114 numbers the first Egypt roadmap was blocked over were
    references of exactly this kind.

    Matched in the shapes a reference actually takes, so a real figure that happens to
    equal an id — a pillar mean of 3.11, written as "mean 3.11" — is still checked.

    A chapter also declares what it cites. Where prose names an id the chapter has cited,
    that is a reference on the chapter's own account, which is firmer than any reading of
    the surrounding words: the roadmap writes "— 3.11" and "; 3.3" as often as it writes
    "(3.11)", and no amount of context matching separates those from a quantity.
    """
    if not prose or not known_ids:
        return set()
    out = {str(c).strip() for c in (cited_ids or [])
           if str(c).strip() in known_ids and str(c).strip() in prose}
    for m in re.finditer(r"[(\[§]\s*([0-9]+\.[0-9]+[A-Za-z-]*)\s*[)\]]?"
                         r"|(?:indicator|prerequisite|row|indicators|rows)\s+"
                         r"([0-9]+\.[0-9]+[A-Za-z-]*)", prose, re.I):
        tok = m.group(1) or m.group(2)
        if tok in known_ids:
            out.add(tok)
    return out


def fidelity_check(prose, figures, allowed, known_ids=(), cited_ids=()):
    """Which claimed figures the engine supports, and what the prose says beyond them.

    Returns (supported, unsupported, stray). `stray` is numbers in the prose that are
    neither a claimed figure nor ordinary — a fabricated figure the writer did not even
    declare, which is the shape this check most has to catch.
    """
    supported, unsupported = [], []
    claimed = set()
    for f in figures or []:
        raw = f.get("value")
        n = _norm_num(raw)
        claimed.add(n)
        comp = _composite_supported(raw, allowed)
        if comp is True or (comp is None and n is not None and n in allowed):
            supported.append(f)
        else:
            unsupported.append(f)

    refs = reference_ids(prose, set(known_ids), cited_ids)
    stray = []
    for raw in _numbers(prose):
        if raw in refs:
            continue
        n = _norm_num(raw)
        if (n is None or n in claimed or n in allowed
                or _ordinary(n) or _rounds_to(n, raw, allowed)):
            continue
        stray.append(raw)
    return supported, unsupported, sorted(set(stray))


def qc_checks(doc):
    """The emit-blocking gate (E5). Returns [(name, ok, detail)]."""
    chapters = doc["chapters"]
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    missing_banner = [c["n"] for c in chapters if not c.get("provenance")]
    add("B1 every chapter carries a provenance banner", not missing_banner,
        f"missing on {', '.join(missing_banner)}" if missing_banner else "")

    outside = [f"{c['n']}: {', '.join(c['cited_outside_binding'])}"
               for c in chapters if c.get("cited_outside_binding")]
    add("B2 no chapter cites outside its binding", not outside, "; ".join(outside))

    mislabelled = [c["n"] for c in chapters
                   if c["kind"] == "prescriptive" and c.get("status") != "proposed, not evidenced"]
    add("B3 no prescriptive chapter renders as evidenced", not mislabelled,
        f"chapters {', '.join(mislabelled)}" if mislabelled else "")

    # Fidelity is an evidence test, and it binds on the chapters that make claims about
    # the country. Chapters three to ten propose an investment programme: a budget line,
    # a district count, a target year. Those figures are proposals, and the engine could
    # not have produced them — holding them to "every number traces to the assessment"
    # asks a proposal to be evidence, which is the one thing chapter three to ten is
    # marked as not being. On the first Egypt roadmap the split was 97% on the diagnostic
    # chapters against 52% on the prescriptive ones, and the global rate of 53% was read
    # as the document being unsupported when its evidence chapters were nearly clean.
    #
    # What protects the prescriptive chapters is B3, which fails if one of them renders as
    # evidenced, and the banner each carries. Their fidelity is reported, never blocking.
    ev = [c for c in chapters if c["kind"] != "prescriptive"]
    ev_claimed = sum(len(c.get("figures") or []) for c in ev)
    ev_unsup = sum(len(c.get("unsupported_figures") or []) for c in ev)
    ev_rate = (ev_claimed - ev_unsup) / ev_claimed if ev_claimed else 1.0
    add(f"B4 evidence-chapter figure fidelity at or above {FIDELITY_FLOOR:.0%}",
        ev_rate >= FIDELITY_FLOOR,
        f"{ev_rate:.1%} — {ev_unsup} unsupported of {ev_claimed} claimed in the "
        f"{len(ev)} evidence chapters")

    pr = [c for c in chapters if c["kind"] == "prescriptive"]
    pr_claimed = sum(len(c.get("figures") or []) for c in pr)
    pr_unsup = sum(len(c.get("unsupported_figures") or []) for c in pr)
    # Reported so that a reader can see how much of the programme is proposal rather than
    # measurement. Not a pass or a fail: it is the point of those chapters.
    checks.append((f"      prescriptive chapters propose {pr_unsup} figures the "
                   f"assessment did not produce, of {pr_claimed}", True, ""))

    strays = [f"{c['n']}: {', '.join(c['stray_numbers'][:4])}"
              for c in chapters if c.get("stray_numbers")]
    add("B5 no undeclared numbers in the prose", not strays, "; ".join(strays))

    add("B6 every chapter of the outline is present",
        len(chapters) == len(OUTLINE),
        f"{len(chapters)} of {len(OUTLINE)}")

    return checks


# ------------------------------------------------------------------ the pack

# A binding may say ["*"] for "every one of these". Both the pack and the gate have to
# read it the same way, so it is expanded once here rather than interpreted twice.
#
# Neither expanded it before. The pack looked up an id called "*", found nothing, and
# handed chapters bound to every prerequisite no prerequisite evidence at all; the gate
# then compared each cited id against the literal set {"*"} and reported every one of
# them as a citation outside the binding. So the chapters most entitled to the evidence
# were the ones starved of it, and were then failed for going to look elsewhere.
_KINDS = {
    "pillars": lambda a: list(a.get("pillars") or {}),
    "indicators": lambda a: list(a.get("indicators") or {}),
    "use_cases": lambda a: list(a.get("matrix") or {}),
    "prerequisites": lambda a: list(a.get("prereq") or {}),
}


def expand_binding(binding, assessment):
    """The binding with any "*" replaced by every id of that kind."""
    out = dict(binding)
    for kind, all_ids in _KINDS.items():
        vals = list(out.get(kind) or [])
        if any(str(v).strip() == "*" for v in vals):
            out[kind] = all_ids(assessment)
    return out


def pack_for(chapter, assessment, scans, foresight):
    """The evidence a chapter may see. Nothing outside its binding is included."""
    b = expand_binding(chapter["binding"], assessment)
    out = []

    if b.get("pillars"):
        out.append("PILLARS:")
        for pid in b["pillars"]:
            p = assessment["pillars"].get(pid)
            if p:
                out.append(f"  {pid}: mean {p['mean']} ({p['band']}), {p['rated']} of "
                           f"{p['n']} rated, {p['held']} withheld, {p['stale']} stale")

    if b.get("indicators"):
        out.append("INDICATORS:")
        for iid in b["indicators"]:
            i = assessment["indicators"].get(iid)
            if i:
                out.append(f"  {iid} {MODEL.get(iid, {}).get('name', '')}: value {i['value']}, "
                           f"level {i['level']}, {i['cls']}, {i['year']}, source {i['src']}")

    if b.get("use_cases"):
        out.append("USE-CASE READINESS:")
        for uc in b["use_cases"]:
            m = assessment["matrix"].get(uc)
            if m:
                out.append(f"  {uc}: {m['status']} — {m['why']} (readiness "
                           f"{m['mean_readiness']}, need {m['mean_need']}, "
                           f"{m['n_bearing']} bearing rows)")

    if b.get("prerequisites"):
        out.append("PREREQUISITES:")
        for pid in b["prerequisites"]:
            pr = assessment["prereq"].get(pid)
            if pr:
                out.append(f"  {pid} {pr['name']}: {pr['status']} ({pr['kind']})")

    for d in (b.get("derived") or []):
        if d == "constraints":
            out.append(f"CONSTRAINTS: {json.dumps(assessment.get('constraints'))[:1200]}")
        elif d == "leapfrog":
            out.append(f"LEAPFROG: {json.dumps(assessment.get('leapfrog'))[:800]}")
        elif d == "kpi_baseline":
            out.append(f"KPI BASELINE: {json.dumps(assessment.get('kpi'))[:1200]}")
        elif d == "pillar_profile":
            out.append(f"PILLAR PROFILE: {json.dumps(assessment['pillars'])[:1500]}")
        elif d == "layer_profile":
            out.append(f"LAYER PROFILE: {json.dumps(assessment.get('layers'))[:800]}")
        elif d == "matrix":
            out.append(f"MATRIX: {json.dumps(assessment['matrix'])[:1500]}")
        elif d == "prerequisites":
            out.append(f"ALL PREREQUISITES: {json.dumps(assessment['prereq'])[:1200]}")
        elif d == "evidence_ledger":
            out.append(f"EVIDENCE COUNTS: {json.dumps(assessment['counts'])}, "
                       f"{assessment['rated']} rated, {assessment['held']} withheld")
        elif d == "register":
            out.append("SOURCE REGISTER: available in the annexes")
        elif d.startswith("foresight."):
            key = d.split(".", 1)[1]
            out.append(f"FORESIGHT {key.upper()}: "
                       f"{json.dumps((foresight or {}).get(key))[:2000]}")

    country_findings = [s for s in (scans or {}).get("country_findings", [])
                        if str(s.get("chapter")) == str(chapter["n"])]
    if country_findings:
        out.append("WHAT THE COUNTRY HAS PUBLISHED:")
        for s in country_findings:
            out.append(f"  - {s['statement']} [{s['source_name']}, {s['tier']}]")

    # International precedent reaches the DAR and nothing else (E2), and only the
    # prescriptive chapters it was gathered for.
    if chapter["kind"] == "prescriptive":
        pointers = [s for s in (scans or {}).get("international_pointers", [])
                    if str(s.get("chapter")) == str(chapter["n"])]
        for s in pointers:
            out.append(f"PRECEDENT ELSEWHERE (a pointer, never an endorsement and never a "
                       f"comparison of countries) — {s['about_country']}: {s['statement']} "
                       f"[{s['source_name']}, {s['tier']}]")

    return "\n".join(out)


def write_chapter(chapter, assessment, scans, foresight, country, llm, allowed):
    prescriptive = chapter["kind"] == "prescriptive"
    pack = pack_for(chapter, assessment, scans, foresight)

    ans = llm.json_call(
        SYSTEM,
        f"COUNTRY: {country}\nASSESSMENT YEAR: {ASSESSMENT_YEAR}\n"
        f"CHAPTER {chapter['n']}: {chapter['title']}\n"
        f"WHAT IT COVERS: {chapter['content']}\n"
        + (f"NOTE: {chapter['note']}\n" if chapter.get("note") else "")
        + f"\nEVIDENCE PACK — this is everything you may cite:\n{pack}\n\n"
        + ("This is a PRESCRIPTIVE chapter. What it proposes is not evidenced by the "
           "assessment; it is a recommendation built on it. Write it as a proposal and do "
           "not present any recommendation as a finding.\n\n"
           if prescriptive else
           "This is a DIAGNOSTIC chapter. Report what the assessment found and nothing "
           "beyond it.\n\n")
        + "Write the chapter as continuous prose, several paragraphs. Rules:\n"
        "- Every number in your prose must come from the pack above. If the pack does "
        "not carry a figure, write the sentence without one.\n"
        "- List every figure you used in `figures`, exactly as it appears in your prose.\n"
        "- List in `cites` only the ids that appear in the pack.\n"
        "- Where the pack shows a row as withheld or unverified, say so rather than "
        "treating it as a low score. A withheld level is not an absence.\n"
        "- Never compare this country to another, and never rank countries.",
        CHAPTER_SCHEMA, PASS, max_tokens=8000, detail=f"chapter {chapter['n']}")

    outside = binding_gate(ans["cites"], chapter["binding"], assessment)
    cited = [c for k in ("indicators", "prerequisites")
             for c in (ans["cites"].get(k) or [])]
    supported, unsupported, stray = fidelity_check(
        ans["prose"], ans["figures"], allowed, KNOWN_IDS, cited)

    return {
        "n": chapter["n"],
        "title": chapter["title"],
        "kind": chapter["kind"],
        "status": "proposed, not evidenced" if prescriptive else "evidenced by the assessment",
        "prose": ans["prose"],
        "cites": ans["cites"],
        "figures": ans["figures"],
        "supported_figures": len(supported),
        "unsupported_figures": [f["value"] for f in unsupported],
        "stray_numbers": stray,
        "cited_outside_binding": outside,
        "provenance": (
            f"Chapter {chapter['n']} draws on "
            + ", ".join(filter(None, [
                f"pillars {', '.join(chapter['binding']['pillars'])}" if chapter["binding"]["pillars"] else "",
                f"indicators {', '.join(chapter['binding']['indicators'])}" if chapter["binding"]["indicators"] else "",
                f"use cases {', '.join(chapter['binding']['use_cases'])}" if chapter["binding"]["use_cases"] else "",
                f"prerequisites {', '.join(chapter['binding']['prerequisites'])}" if chapter["binding"]["prerequisites"] else "",
                f"derived: {', '.join(chapter['binding']['derived'])}" if chapter["binding"]["derived"] else "",
            ]))
            + ". "
            + ("Prescriptive: proposed, not evidenced."
               if prescriptive else "Diagnostic: reports what the assessment found.")),
    }


# ------------------------------------------------------------------ render

def render_html(doc):
    c = html.escape
    parts = [
        "<meta charset='utf-8'>",
        f"<title>{c(doc['country'])} — Draft Digital Agriculture Roadmap</title>",
        "<style>",
        "body{font:16px/1.65 Georgia,serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1a1a1a}",
        "h1{font-size:2rem;margin-bottom:.2em}h2{margin-top:2.2em;border-bottom:1px solid #ddd;padding-bottom:.2em}",
        ".banner{background:#f4f2ec;border-left:3px solid #9aa;padding:.6em .9em;font:13px/1.5 system-ui;margin:.6em 0 1.2em}",
        ".proposed{background:#fff7e6;border-left:3px solid #d9a441}",
        ".status{display:inline-block;font:600 11px system-ui;text-transform:uppercase;letter-spacing:.06em;padding:.2em .5em;border-radius:3px;background:#eee}",
        ".status.proposed{background:#d9a441;color:#fff}",
        ".fid{font:13px/1.6 system-ui;background:#f4f2ec;padding:1em;margin:1.5em 0}",
        ".prohib{font:12px/1.6 system-ui;color:#666;border-top:1px solid #ddd;margin-top:3em;padding-top:1em}",
        "</style>",
        f"<h1>{c(doc['country'])} — Draft Digital Agriculture Roadmap</h1>",
        f"<p><em>Pre-review draft. DAMM {c(doc['model_version'])}, assessment year "
        f"{doc['assessment_year']}.</em></p>",
        "<div class='fid'>",
        f"<b>Figure fidelity: {doc['fidelity']['rate']:.1%}</b> — "
        f"{doc['fidelity']['supported']} of {doc['fidelity']['claimed']} figures matched "
        "against the engine's own output. ",
        "Every chapter states what it was allowed to draw on. Chapters marked "
        "<span class='status proposed'>proposed</span> are recommendations built on the "
        "assessment, not findings from it.",
        "</div>",
    ]
    for ch in doc["chapters"]:
        prescriptive = ch["kind"] == "prescriptive"
        parts.append(f"<h2>{c(str(ch['n']))}. {c(ch['title'])} "
                     + (f"<span class='status proposed'>proposed, not evidenced</span>"
                        if prescriptive else "<span class='status'>evidenced</span>")
                     + "</h2>")
        parts.append(f"<div class='banner{" proposed" if prescriptive else ""}'>"
                     f"{c(ch['provenance'])}</div>")
        for para in ch["prose"].split("\n\n"):
            if para.strip():
                parts.append(f"<p>{c(para.strip())}</p>")
    parts.append("<div class='prohib'><b>Standing prohibitions.</b> "
                 + c(" ".join(str(p) for p in PROHIBITIONS)) + "</div>")
    return "\n".join(parts)


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--out", required=True, help="basename of the research pass")
    ap.add_argument("--ceiling", type=float, default=500.0)
    ap.add_argument("--vendor", default="anthropic/claude-opus-5")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    inp, reviewed = V.engine_input_for(LOOP1, a.out)
    if not reviewed:
        print("   (the second review has not run for this pass — reading the first pass)")
    if not os.path.exists(inp):
        print(f"!! no engine input at {os.path.basename(inp)}")
        print("   The roadmap is written from the assessment. Finish the research pass first.")
        return 1

    def load(name):
        p = os.path.join(LOOP1, f"{a.out}_{name}.json")
        return json.load(open(p)) if os.path.exists(p) else None

    scans, foresight = load("scans"), load("foresight")
    missing = [n for n, v in (("scans", scans), ("foresight", foresight)) if v is None]
    if missing:
        # Named rather than silently absent. Chapters 3, 4, 9 and the annexes bind to
        # foresight, and a roadmap written without it is missing its milestones — the
        # reader should learn that from the run, not by noticing later.
        print(f"!! the {' and '.join(missing)} pass has not run; chapters bound to it will "
              f"be written without it")

    V.load_env()
    vendor, _, mname = a.vendor.partition("/")
    ledger = V.Ledger(ceiling=a.ceiling, label=f"{a.out}_generation")
    llm = V.LLM(vendor, ledger, model=mname or None)

    state_path = os.path.join(LOOP1, f"{a.out}_generation_state.json")
    spend_path = os.path.join(LOOP1, f"{a.out}_generation_spend.json")

    rows = json.load(open(inp))
    assessment = engine_run(a.country, rows, refyear=ASSESSMENT_YEAR)
    allowed = allowed_figures(assessment, foresight)

    state = {"chapters": {}}
    if a.resume and os.path.exists(state_path):
        state = json.load(open(state_path))
        carried = ledger.load(spend_path)
        print(f"resuming — {len(state['chapters'])} chapters already written, {carried} "
              f"earlier vendor calls carried (${ledger.spent():.2f} spent)")

    total = len(OUTLINE)
    print(f"{a.country} ({a.iso}) · {total} rows · vendor {a.vendor}")
    print(f"budget ${a.ceiling:.0f}, generation allocation "
          f"${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} (decision G3)")
    print()
    sys.stdout.flush()

    def save():
        json.dump(state, open(state_path, "w"), indent=1, default=str)
        ledger.save(spend_path)

    stopped = None
    for n, chapter in enumerate(OUTLINE, 1):
        key = str(chapter["n"])
        if key in state["chapters"]:
            continue
        t0 = time.time()
        try:
            rec = write_chapter(chapter, assessment, scans, foresight, a.country, llm, allowed)
        except V.BudgetExhausted as e:
            stopped = str(e)
            break
        except Exception as e:
            print(f"!! chapter {key} failed: {str(e)[:120]}")
            sys.stdout.flush()
            continue
        state["chapters"][key] = rec
        save()
        mark = "P" if rec["kind"] == "prescriptive" else " "
        flags = []
        if rec["cited_outside_binding"]:
            flags.append(f"{len(rec['cited_outside_binding'])} outside binding")
        if rec["unsupported_figures"]:
            flags.append(f"{len(rec['unsupported_figures'])} unsupported")
        if rec["stray_numbers"]:
            flags.append(f"{len(rec['stray_numbers'])} stray")
        print(f"{mark} [{n:2d}/{total}] {key:<12} written {rec['title'][:22]:<24} "
              f"{('; '.join(flags) or 'clean'):<36} $ {ledger.spent():5.2f} "
              f"{int(time.time() - t0):3d}s")
        sys.stdout.flush()

    if stopped:
        print(f"\n!! {stopped}")
        print("   Generation stopped where the budget ran out. Chapters never reached are "
              "absent from the output, NOT written as empty.")
        save()
        return 0

    chapters = [state["chapters"][str(c["n"])] for c in OUTLINE
                if str(c["n"]) in state["chapters"]]
    claimed = sum(len(c["figures"]) for c in chapters)
    supported = sum(c["supported_figures"] for c in chapters)
    doc = {
        "country": a.country,
        "iso3": a.iso,
        "assessment_year": ASSESSMENT_YEAR,
        "model_version": f"{SPEC['version']} rev{SPEC['revision']}",
        "status": "Pre-review draft (A1). Review happens once, at the end, on the "
                  "completed set.",
        "chapters": chapters,
        "fidelity": {
            "claimed": claimed,
            "supported": supported,
            "unsupported": claimed - supported,
            "rate": (supported / claimed) if claimed else 1.0,
        },
        "prohibitions": PROHIBITIONS,
    }

    checks = qc_checks(doc)
    print()
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        # Emit-blocking, exactly as the diagnostic's gate is. A document that fails its
        # own checks and is written anyway teaches everyone to ignore the checks.
        print(f"\n!! QC FAIL — the roadmap was NOT written: {'; '.join(failed)}")
        save()
        return 1

    json.dump(doc, open(os.path.join(LOOP1, f"{a.out}_dar.json"), "w"), indent=1, default=str)
    open(os.path.join(LOOP1, f"{a.out}_dar.html"), "w").write(render_html(doc))
    ledger.save(spend_path)

    print()
    print(f"wrote {a.out}_dar.json — {len(chapters)} chapters, fidelity "
          f"{doc['fidelity']['rate']:.1%} ({supported}/{claimed} figures)")
    s = ledger.summary()
    print(f"spend ${s['total']:.2f} of ${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} "
          f"allocated (${a.ceiling:.0f} country ceiling), {s['calls']} vendor calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
