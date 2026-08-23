#!/usr/bin/env python3
"""Gauntlet loop 1 — consolidation + G1 derivation.
Merges machine_pass.json + research/{ISO}_{A..G}.json into engine input rows.
Derives evidence class from what was recorded (never chosen) and PROPOSES levels:
  - t-kind + Measured  -> threshold level (mechanical)
  - t-kind + citation  -> level None + G1 QUEUE (assessor must set via overrides)
  - l-kind + citation  -> ladder proposal: Absent1/Announced2/Adopted3/Operating3
                          +1 quality evidence, +1 scale evidence (cap 5) + G1 QUEUE
  - gap                -> no level
Applies g1_overrides_{iso}.json {id:{level,reason}} if present.
Outputs: {iso}_v17_input.json, g1_review_{iso}.md, diff_{iso}.md
"""
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_v17 import MODEL, tlevel

ISO = {"EGY": "egypt", "NGA": "nigeria"}

SANITIZE = [
    # The report is a standalone document: search trails name SOURCES, never process history.
    (r"[;,]?\s*prior desk pass[^;.]*", ""),
    (r"[;,]?\s*prior pass[^;.]*", ""),
    (r"\bthis run\b", "at capture"),
    (r"\bnot verified this run\b", "not verified at capture"),
]
def standalone(text):
    if not isinstance(text, str): return text
    for pat, rep in SANITIZE:
        text = re.sub(pat, rep, text, flags=re.I)
    return re.sub(r"\s{2,}", " ", text).strip()


# ── American spelling, applied to assessor prose but never to a quoted name ──
# Source titles, official labels and program names are quoted evidence: altering them
# would misquote the source, so they are protected before normalization.
_PROTECTED = ["Role-modelling", "Microdata Catalog", "NBS Microdata Catalog", "Programme", "programme",
              "Centre for", "Centre of", "International Centre", "Research Centre", "Global Centre"]
_US = [("artefacts","artifacts"),("artefact","artifact"),("judgements","judgments"),("judgement","judgment"),
       ("behaviours","behaviors"),("behaviour","behavior"),("organisations","organizations"),
       ("organisation","organization"),("summarised","summarized"),("summarise","summarize"),
       ("recognised","recognized"),("recognise","recognize"),("prioritised","prioritized"),
       ("prioritise","prioritize"),("institutionalised","institutionalized"),("digitised","digitized"),
       ("digitisation","digitization"),("harmonised","harmonized"),("harmonise","harmonize"),
       ("standardised","standardized"),("standardise","standardize"),("utilised","utilized"),
       ("modelling","modeling"),("modelled","modeled"),("catalogues","catalogs"),("catalogue","catalog"),
       ("centres","centers"),("centre","center"),("licence","license"),("defence","defense"),
       ("labour","labor"),("colour","color"),("enrolment","enrollment"),("towards","toward"),
       ("amongst","among"),("whilst","while"),("practise","practice")]
def americanize(t):
    if not isinstance(t, str): return t
    for i, name in enumerate(_PROTECTED):
        t = t.replace(name, f"\x00{i}\x00")
    for a, b in _US:
        t = re.sub(r"\b" + re.escape(a) + r"\b", b, t)
        t = re.sub(r"\b" + re.escape(a.capitalize()) + r"\b", b.capitalize(), t)
    for i, name in enumerate(_PROTECTED):
        t = t.replace(f"\x00{i}\x00", name)
    return t

def norm_tier(t):
    """Agents sometimes return verbose tier strings; normalize to first T1-T5 token."""
    if not t: return "", ""
    m = re.search(r"T[1-5]", t)
    return (m.group(0) if m else ""), (t if t != (m.group(0) if m else t) else "")

def substantive(s):
    if not s or len(s.strip()) < 40: return False
    neg = ("none found", "no ", "not ", "n/a", "unpublished", "unmeasured", "unverified", "no published")
    return not s.strip().lower().startswith(neg)


# The shared qualitative ladder. Extracted so the automated research orchestrator
# derives levels through this function instead of reimplementing it: two copies of a
# scoring rule are two rules, and the second one drifts. Behaviour is unchanged — the
# verifier regenerates both countries' inputs and checks them figure for figure.
LADDER_BASE = {"Absent": 1, "Announced": 2, "Adopted": 3, "Operating": 3}

def ladder_level(rung, quality_evidence="", scale_evidence=""):
    """Return (level, why) for a ladder indicator, or (None, "") if the rung is missing.

    Operating earns +1 for substantive evidence of quality and a further +1 for
    substantive evidence of scale, capped at 5. Quality gates scale: reach claimed
    with no evidence of what is being delivered is not a level 5.
    """
    base = LADDER_BASE.get(rung)
    if not base:
        return None, ""
    lvl, why = base, ""
    if rung == "Operating" and substantive(quality_evidence):
        lvl, why = lvl + 1, "+quality"
        if substantive(scale_evidence):
            lvl, why = lvl + 1, "+quality+scale"
    return min(lvl, 5), why


def build(iso):
    mp = json.load(open("machine_pass.json"))[ISO[iso].capitalize()]
    cells = {}
    meta = {}
    for b in "ABCDEFG":
        p = f"research/{iso}_{b}.json"
        if not os.path.exists(p):
            print(f"  !! missing bundle {p}"); continue
        j = json.load(open(p))
        for c in j.get("cells", []):
            cells[c["id"]] = c
    over = {}
    op = f"g1_overrides_{iso.lower()}.json"
    if os.path.exists(op): over = json.load(open(op))

    rows, queue, dlog = {}, [], []
    ids = list(MODEL.keys()) + ["A1-CAND-IMP", "A1-CAND-IRR"]
    for i in ids:
        cand = i.startswith("A1-CAND-")
        m = MODEL.get(i, {})
        kind = m.get("kind", "t")
        # 1) machine pass wins for its cells
        if i in mp and mp[i].get("status") == "ok":
            r = mp[i]
            lvl = tlevel(r["value"], m["dir"], m["th"]) if (not cand and kind == "t") else None
            rows[i] = dict(value=r["value"], cls="Measured", level=lvl, year=r["year"],
                           src=r["src"], note=r.get("note",""), tier="T1", url=r["url"])
            continue
        c = cells.get(i)
        if not c:
            rows[i] = dict(value="DATA GAP — cell not returned by research pass (loop-1 process defect)",
                           cls="Gap", level=None, year=2026, src="Structured source search", note="", tier="", url="")
            dlog.append(f"D-PROC {i}: no research cell returned")
            continue
        vt, val = c["value_type"], c["value"]
        yr = c.get("year") or 2026
        src = c.get("source_title", "")
        url = c.get("source_url", "")
        tier, tier_detail = norm_tier(c.get("tier", ""))
        note = (c.get("notes", "") or "")[:200]
        if c.get("protocol_issues"): dlog.append(f"D2? {i}: {c['protocol_issues'][:300]}")
        if vt == "gap":
            v = str(val)
            if not v.upper().startswith("DATA GAP"): v = "DATA GAP — " + v
            rows[i] = dict(value=v, cls="Gap", level=None, year=2026, src=f"Structured source search, {c.get('access_date', '22 August 2026')}", note=note, tier="", url="")
        elif vt == "number":
            v = float(val)
            lvl = tlevel(v, m["dir"], m["th"]) if (not cand and kind == "t") else None
            rows[i] = dict(value=v, cls="Measured", level=lvl, year=yr, src=src, note=note, tier=tier, tier_detail=tier_detail, url=url)
        else:  # citation
            # Source-Tier Protocol: a citation is an artefact only if its source is admissible for a
            # scored value (T1-T4). A T5-only citation is judgement, not documentation.
            cls = "Documented" if (url and tier != "T5") else "Judged"
            if not url: dlog.append(f"D2 {i}: citation without URL -> Judged")
            if url and tier == "T5": dlog.append(f"D2 {i}: T5-only citation -> Judged (inadmissible for a value)")
            lvl = None; why = ""
            if kind == "l":
                rung = c.get("presence_rung")
                lvl, why = ladder_level(rung, c.get("quality_evidence"), c.get("scale_evidence"))
                if lvl:
                    queue.append((i, m.get("name",""), f"ladder {rung}{why} -> L{lvl}",
                                  (c.get("quality_evidence","") or "")[:160], (c.get("scale_evidence","") or "")[:160]))
                else:
                    queue.append((i, m.get("name",""), "ladder rung MISSING -> level unset", "", ""))
                    dlog.append(f"D2 {i}: citation for ladder indicator without presence_rung")
            else:
                queue.append((i, m.get("name",""), "t-kind citation -> G1 must set level", str(val)[:160], ""))
            rows[i] = dict(value=str(val)[:220], cls=cls, level=lvl, year=yr, src=src, note=note, tier=tier, tier_detail=tier_detail, url=url)
        if i in over:
            o = over[i]
            rows[i]["level"] = o["level"]
            rows[i]["note"] = (rows[i]["note"] + f" [G1: {o['reason']}]").strip()

    dnp = "definition_notes.json"
    dnotes = json.load(open(dnp)) if os.path.exists(dnp) else {}
    dcp = f"definition_corrections_{iso.lower()}.json"
    if os.path.exists(dcp):
        dc = json.load(open(dcp))
        for i, patch in dc.items():
            rows.setdefault(i, {}).update(patch)
        print(f"  applied {len(dc)} definition corrections")
    for i, r in rows.items():
        if i in dnotes:
            r["defnote"] = dnotes[i]["q"]
            r["defsev"] = dnotes[i]["sev"]
    g2p = f"g2_corrections_{iso.lower()}.json"
    if os.path.exists(g2p):
        g2 = json.load(open(g2p))
        for i, patch in g2.items():
            rows.setdefault(i, {}).update(patch)
            rows[i]["value"] = standalone(rows[i]["value"])
        print(f"  applied {len(g2)} G2 corrections")
    # normalization runs LAST, so text introduced by any correction layer is covered too
    for r in rows.values():
        r["value"] = americanize(standalone(r["value"]))
        r["note"] = americanize(standalone(r.get("note", "")))
        for f in ("src", "defnote"):
            if r.get(f): r[f] = americanize(r[f])
    json.dump(rows, open(f"{iso}_v17_input.json", "w"), indent=1)

    with open(f"g1_review_{iso}.md", "w") as f:
        f.write(f"# G1 review queue — {iso} (loop 1)\n\nProposed derivations needing assessor confirmation; set g1_overrides_{iso.lower()}.json to adjust.\n\n")
        for i, nm, prop, q, s in queue:
            f.write(f"- **{i} {nm}** — {prop}\n  - quality: {q}\n  - scale: {s}\n")
        f.write("\n## Process log (D-candidates)\n\n" + "\n".join("- " + d for d in dlog) + "\n")

    # diff vs prior
    prior = json.load(open(f"../../v1.6-test-run/{ISO[iso]}_v16.json"))["indicators"]
    with open(f"diff_{iso}.md", "w") as f:
        f.write(f"# Clean-slate vs prior — {iso}\n\n| id | prior cls/L | new cls/L | note |\n|---|---|---|---|\n")
        for i in MODEL:
            p, n = prior.get(i, {}), rows[i]
            pd = f"{p.get('cls','—')}/L{p.get('level')}"
            nd = f"{n['cls']}/L{n['level']}"
            if pd != nd:
                f.write(f"| {i} | {pd} | {nd} | {str(n['value'])[:60]} |\n")
    print(f"{iso}: rows={len(rows)} queue={len(queue)} dlog={len(dlog)}")

# Guarded so the module can be imported for its derivation rules — `ladder_level`,
# `norm_tier`, `substantive`, and the `standalone`/`americanize` text normalizers —
# without rebuilding both countries as a side effect of the import.
if __name__ == "__main__":
    for iso in ("EGY", "NGA"):
        have = [b for b in "ABCDEFG" if os.path.exists(f"research/{iso}_{b}.json")]
        print(f"{iso}: bundles on disk: {have}")
        if len(have) == 7 or "--partial" in sys.argv:
            build(iso)
