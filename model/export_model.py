#!/usr/bin/env python3
"""Emit the canonical, machine-readable DAMM v1.7 model.

Until now the model lived in three places — the Python engine, the workbook formulas and
the indicator census — with no single machine-readable form. Anything consuming DAMM (DAR
Studio first) had to re-implement it, which is how a model drifts. This module makes the
engine the one source and exports everything else from it.

The file it writes is MODEL ONLY: indicator metadata and the rules. No country observations,
no assessments, no outputs — those are separate payloads with their own shapes.

Every value the twelve open decisions in specification 13 can change is DATA in this file,
never code in a consumer. Ratification edits the model file and bumps `revision`; consumers
are written once. Each such value is listed under `open_decisions` with the fields it
governs, so an application can render a provisional reading honestly instead of presenting
an unratified cut-point as settled.

Usage: python3 model/export_model.py [outdir]
"""
import json, os, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "gauntlet", "loop-1"))

from engine_v17 import MODEL, ABSORB, BANDS  # the source of truth

PILLARS = {
    "A1": {"name": "Agriculture & need", "reading": "need",
           "note": "Scored as need, not digital maturity: a low reading is a large opportunity."},
    "C1": {"name": "Connectivity & access", "reading": "capability"},
    "C2": {"name": "Data & DPI", "reading": "capability"},
    "C3": {"name": "Policy & safeguards", "reading": "capability"},
    "C4": {"name": "People & institutions", "reading": "capability"},
    "E1": {"name": "Innovation, solutions & emerging tech", "reading": "capability"},
    "O1": {"name": "Outcomes & inclusion", "reading": "outcome"},
}
LAYERS = ["Foundation", "Enablers", "Transformation", "Outcomes"]
USE_CASES = {
    "ADV": "Advisory & extension", "SMF": "Smart farming", "MKT": "Market linkage & pricing",
    "SCM": "Supply chain", "FIN": "Financial services", "AGI": "Agricultural intelligence",
}
NON_UC_TAGS = {
    "NEED": "Bears on the agricultural-need profile, not on a use-case column.",
    "EQ": "Equity/inclusion reading.",
    "ALL": "Bears on every use-case column.",
    "AI": "Binds AI-enabled services; loop-1 ruling binds it to AGI pending a definition (13.4).",
}
EVIDENCE_CLASSES = [
    {"id": "Measured",   "derived_from": "a numeric value was recorded",
     "levels": "threshold-derived from the recorded value"},
    {"id": "Documented", "derived_from": "a non-numeric value with a source at an admissible tier (not T5)",
     "levels": "assessor level against the shared qualitative ladder"},
    {"id": "Judged",     "derived_from": "a non-numeric value with no source, or a T5-only citation",
     "levels": "assessor level; carries no artifact"},
    {"id": "Gap",        "derived_from": "the value records a search trail beginning 'DATA GAP'",
     "levels": "none — a gap is never levelled"},
]
SOURCE_TIERS = {
    "T1": "Official statistics and international databases",
    "T2": "Peer-reviewed and international-organisation flagship reports",
    "T3": "Government legal and policy artifacts",
    "T4": "Reputable grey literature",
    "T5": "News and vendor material — existence facts only; never yields Documented",
}
PREREQUISITE_KINDS = {
    "UNIVERSAL": "Absence blocks every use-case column.",
    "UC:<list>": "Absence blocks the named columns only.",
    "DELIVERY":  "Delivery-risk flag. Reported on the cover; blocks nothing.",
}
PREREQUISITE_STATUS = {
    "Present":          "level >= 3",
    "Present (narrow)": "level == 2",
    "Absent":           "level == 1",
    "Unverified":       "no level recorded — an unrated row asserts nothing, and is never Absent",
}
BINDING_RULES = [
    {"id": "universal-absent",     "rule": "Any universal prerequisite Absent -> every column Blocked.",
     "ratified": False, "decision": "13.4"},
    {"id": "universal-unverified", "rule": "Any universal prerequisite Unverified -> every column Unverified. A known blocker outranks an unknown one.",
     "ratified": False, "decision": "13.4"},
    {"id": "universal-narrow",     "rule": "Any universal prerequisite at Present (narrow) -> every column capped at Partial.",
     "ratified": False, "decision": "13.4"},
    {"id": "uc-prerequisite",      "rule": "A per-use-case prerequisite Absent -> that column Blocked; Unverified -> that column Unverified.",
     "ratified": False, "decision": "13.3"},
    {"id": "ai-binds-agi",         "rule": "7.12 (consent and rights) binds the AGI column.",
     "ratified": False, "decision": "13.4",
     "note": "The external review argues this should condition every use case touching personal or farm-level data rather than block one column."},
    {"id": "thin-enablers",        "rule": "Mean of bearing indicators below the readiness threshold -> Partial.",
     "ratified": False, "decision": "13.12",
     "note": "The bearing set mixes need, outcome and enabling indicators. See open decision 13.12."},
]
PROHIBITIONS = [
    "No cross-country ranking.",
    "No band used as a project development objective, disbursement-linked indicator or disbursement condition.",
    "No automatic financing decisions.",
    "No public claim before human review.",
]
OPEN_DECISIONS = [
    {"id": "13.1",  "title": "Band edges", "governs": ["bands"]},
    {"id": "13.2",  "title": "A1 additions (cereal import dependency, irrigation)", "governs": ["candidates"]},
    {"id": "13.3",  "title": "Per-use-case prerequisite mapping", "governs": ["indicators[].prerequisite", "binding_rules"]},
    {"id": "13.4",  "title": "The three binding rules in force", "governs": ["binding_rules"]},
    {"id": "13.5",  "title": "Indicator definitions — the largest item",
     "governs": ["indicators[].ratification"], "scope": "44 of 57 rows"},
    {"id": "13.6",  "title": "A1 thresholds (still test values)",
     "governs": ["indicators[].thresholds where pillar == A1"]},
    {"id": "13.7",  "title": "Sub-readings display", "governs": ["presentation only"]},
    {"id": "13.8",  "title": "Source-tier lookup and register field set", "governs": ["source_tiers"]},
    {"id": "13.9",  "title": "QC gate scope", "governs": ["process, not model"]},
    {"id": "13.10", "title": "Practice Library schema", "governs": ["companion schema"]},
    {"id": "13.11", "title": "Bhutan out of scope (statement)", "governs": []},
    {"id": "13.12", "title": "Whether need and outcome indicators belong in a readiness mean",
     "governs": ["indicators[].use_cases", "config.readiness_threshold", "binding_rules.thin-enablers"]},
]


def build(defnotes):
    inds = []
    for i, m in MODEL.items():
        uc  = [u for u in m["uc"] if u in USE_CASES]
        tag = [u for u in m["uc"] if u not in USE_CASES]
        row = {
            "id": i,
            "name": m["name"],
            "pillar": m["pillar"],
            "layer": m["layer"],
            "use_cases": uc,
            "tags": tag,
            "prerequisite": m["prereq"] or None,
            "method": "threshold" if m["kind"] == "t" else "ladder",
            "direction": {"H": "higher-is-better", "L": "lower-is-better", "": None}[m["dir"]],
            "thresholds": m["th"] or None,
            "absorbs": ABSORB.get(i, []),
        }
        if i in defnotes:
            row["ratification"] = {
                "open_question": defnotes[i]["q"],
                "severity": defnotes[i].get("sev"),
                "decision": "13.5",
            }
        if m["pillar"] == "A1" and m["th"]:
            row["thresholds_ratified"] = False       # 13.6: A1 cut-points are still test values
        inds.append(row)
    inds.sort(key=lambda r: [int(x) for x in r["id"].split(".")])

    return {
        "$schema": "./DAMM-v1.7-model.schema.json",
        "model": "DAMM",
        "title": "Digital Agriculture Maturity Model",
        "version": "1.7",
        "revision": 1,
        "status": "draft for review",
        "ratified": False,
        "ratification_note": (
            "Twelve design decisions are open in specification section 13. Every value they can "
            "change is data in this file. A consumer must not present an unratified value as settled: "
            "see `open_decisions` for which fields each ruling governs."
        ),
        "generated_from": "gauntlet/loop-1/engine_v17.py",
        "generated_on": datetime.date.today().isoformat(),
        "prohibitions": PROHIBITIONS,
        "config": {
            "assessment_year": 2026,
            "staleness_years": 3,
            "readiness_threshold": 2.6,
            "leapfrog_threshold": 1.5,
            "rounding": "half-up",
            "rounding_note": "Half-up to 2dp, matching the workbook. Banker's rounding disagrees at exact .xx5 and would band a mean differently.",
        },
        "pillars": PILLARS,
        "layers": LAYERS,
        "use_cases": USE_CASES,
        "non_use_case_tags": NON_UC_TAGS,
        "evidence_classes": EVIDENCE_CLASSES,
        "source_tiers": SOURCE_TIERS,
        "tier_note": "Tiers are reported, never weighted. Weighting them would rebuild the confidence weights v1.6 removed.",
        "bands": [{"name": n, "lo": lo, "hi": hi} for lo, hi, n in BANDS],
        "prerequisite_kinds": PREREQUISITE_KINDS,
        "prerequisite_status": PREREQUISITE_STATUS,
        "binding_rules": BINDING_RULES,
        "invariants": [
            "No level without a recorded value; the evidence class is derived from what was recorded, never chosen.",
            "A withheld level is not an absence. A prerequisite so recorded reads Unverified, never Absent.",
            "A mean averages rated rows only, and never travels without its own denominator (rated of n).",
            "No narrative claim ever sets a level.",
            "Tiers are reported, never weighted.",
        ],
        "indicators": inds,
        "open_decisions": OPEN_DECISIONS,
    }


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else HERE
    notes = json.load(open(os.path.join(ROOT, "gauntlet", "loop-1", "definition_notes.json")))
    notes = {k: v for k, v in notes.items() if not k.startswith("A1-CAND-")}
    m = build(notes)
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "DAMM-v1.7-model.json")
    json.dump(m, open(p, "w"), indent=2, ensure_ascii=False)
    open(p, "a").write("\n")
    rat = sum(1 for i in m["indicators"] if "ratification" in i)
    print(f"wrote {p}")
    print(f"  {len(m['indicators'])} indicators · {rat} carrying an open definition question "
          f"· {len(m['open_decisions'])} open decisions")
    return m


if __name__ == "__main__":
    main()
