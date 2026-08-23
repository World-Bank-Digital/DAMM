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
# ---------------------------------------------------------------------------
# The DAR outline, with each chapter's evidence binding (design decision E4).
#
# A chapter may cite ONLY what its binding names. This is what lifts the
# fidelity check from "did the prose invent a number" to "did it use the RIGHT
# number" — a financing chapter citing connectivity indicators reads perfectly
# fluently and is wrong, and no invented-figure check would catch it.
#
# `kind` separates chapters the model can evidence from chapters resting on
# judgment it does not hold. Prescriptive chapters render marked as proposed,
# not evidenced (decision E3).
# ---------------------------------------------------------------------------
DERIVED_SOURCES = {
    "pillar_profile":  "Per-pillar mean, band, rated/held denominators and evidence composition.",
    "layer_profile":   "Foundation / Enablers / Transformation / Outcomes means.",
    "leapfrog":        "Foundation minus Transformation, and the structural flag.",
    "matrix":          "The six use-case readiness columns with both means.",
    "prerequisites":   "Presence status of the twelve prerequisite rows.",
    "constraints":     "Lowest-level rated indicators, the binding-constraint list.",
    "kpi_baseline":    "Measured A1/O1 rows carried as baseline readings.",
    "register":        "The initiative and solutions register, tier-badged.",
    "evidence_ledger": "Every row with class, level, source, tier, year; gaps, holds and stale readings.",
    "foresight.scenarios":        "Scenario set produced by the foresight stage.",
    "foresight.preferred_future": "The selected preferred future.",
    "foresight.milestones":       "Backcast milestones and their indicator bindings.",
}

ALL_PILLARS = ["A1", "C1", "C2", "C3", "C4", "E1", "O1"]
ALL_UC = ["ADV", "SMF", "MKT", "SCM", "FIN", "AGI"]

DAR_OUTLINE = [
    {"n": "1", "title": "Country and sector context", "kind": "diagnostic",
     "content": "Agricultural structure, need and climate exposure; the national digital context "
                "the roadmap has to work inside.",
     "binding": {"pillars": ["A1", "C1", "O1"], "indicators": [], "use_cases": [],
                 "prerequisites": [], "derived": ["constraints", "register"]},
     "note": "A1 reads as NEED: a low reading is a large opportunity, never low maturity."},

    {"n": "2", "title": "Where the country stands", "kind": "diagnostic",
     "content": "Pillar and layer profiles with their rated denominators; the use-case readiness "
                "matrix; prerequisite status; the structural gap; what the evidence rests on.",
     "binding": {"pillars": ALL_PILLARS, "indicators": [], "use_cases": ALL_UC,
                 "prerequisites": ["*"],
                 "derived": ["pillar_profile", "layer_profile", "leapfrog", "matrix",
                             "prerequisites", "constraints", "evidence_ledger"]},
     "note": "This chapter is the diagnostic. Every figure must reconcile with the diagnostic "
             "report generated for the same assessment."},

    {"n": "3", "title": "Vision, targeting and beneficiaries", "kind": "prescriptive",
     "content": "Priority value chains, regions and farmer segments; which use cases are worth "
                "pursuing first, and for whom.",
     "binding": {"pillars": ["A1", "O1"], "indicators": ["5.12"], "use_cases": ALL_UC,
                 "prerequisites": [],
                 "derived": ["matrix", "foresight.preferred_future", "foresight.milestones"]},
     "note": "Targeting rests on the readiness matrix; beneficiary claims rest on A1 need and O1 "
             "equity rows. The vision itself comes from the foresight stage, not from the model."},

    {"n": "4", "title": "The investment program", "kind": "prescriptive",
     "content": "Sequenced candidates with dependencies and implementation owners; what has to be "
                "built before what.",
     "binding": {"pillars": ["C1", "C2", "C3", "C4", "E1"], "indicators": [], "use_cases": ALL_UC,
                 "prerequisites": ["*"],
                 "derived": ["matrix", "prerequisites", "constraints", "foresight.milestones"]},
     "note": "Sequencing follows the prerequisites: a Blocked column names what must be built. "
             "A blocked use case is an argument FOR investment, never against it."},

    {"n": "5", "title": "Costs and financing", "kind": "prescriptive",
     "content": "Costed program under envelope scenarios; instrument routing; financing sources.",
     "binding": {"pillars": [], "indicators": ["1.7", "6.14"], "use_cases": ["FIN"],
                 "prerequisites": ["6.14"], "derived": ["register"]},
     "note": "DAMM CARRIES NO COST, BUDGET OR FINANCING DATA OF ANY KIND. No figure in this "
             "chapter may be presented as derived from the model or the assessment. The only "
             "quantities available are scale figures as reported by initiatives in the register, "
             "which are the initiatives' own claims and are tier-badged as such."},

    {"n": "6", "title": "Policy and regulatory actions", "kind": "prescriptive",
     "content": "Reform actions arising from the policy and safeguards pillar; legal drafting needs.",
     "binding": {"pillars": ["C3"], "indicators": [], "use_cases": [],
                 "prerequisites": ["4.1", "4.5", "3.11", "7.12"], "derived": ["prerequisites"]},
     "note": "An Absent prerequisite here is a named legal or regulatory instrument that does not "
             "exist; say which, and cite the row."},

    {"n": "7", "title": "Delivery and governance", "kind": "prescriptive",
     "content": "Mandate and ownership; steering arrangements; the institutional home and its capacity.",
     "binding": {"pillars": ["C4"], "indicators": [], "use_cases": [],
                 "prerequisites": ["4.9", "5.7"], "derived": ["prerequisites", "register"]},
     "note": "4.9 and 5.7 are DELIVERY-risk flags: they are reported and they block nothing. "
             "Do not render them as gating anything."},

    {"n": "8", "title": "Climate alignment", "kind": "prescriptive",
     "content": "Climate-smart practice, advisory reach and the weather and climate data base the "
                "roadmap can build on.",
     "binding": {"pillars": [], "indicators": ["1.8", "3.6", "8.17"], "use_cases": ["ADV"],
                 "prerequisites": [], "derived": []},
     "note": "The model holds no NDC or CCDR crosswalk and no climate-finance taxonomy. Alignment "
             "claims against those instruments are external and must be marked as such."},

    {"n": "9", "title": "Results and learning", "kind": "prescriptive",
     "content": "Results chains with baselines; the measurement gap register; what will be watched "
                "and how often.",
     "binding": {"pillars": ["O1"], "indicators": [], "use_cases": [], "prerequisites": [],
                 "derived": ["kpi_baseline", "evidence_ledger", "foresight.milestones"]},
     "note": "Baselines come from Measured A1/O1 rows only. Recorded gaps, held levels and stale "
             "readings ARE the measurement gap register — carry them, do not summarise them away."},

    {"n": "10", "title": "Risks and safeguards", "kind": "prescriptive",
     "content": "Data rights, consent and redress; evidence-quality risk; political-economy risk "
                "and mitigations.",
     "binding": {"pillars": ["C3"], "indicators": [], "use_cases": [],
                 "prerequisites": ["4.1", "4.5", "7.12"], "derived": ["evidence_ledger"]},
     "note": "Evidence quality is itself a risk and belongs here: how much of the assessment rests "
             "on withheld levels, recorded gaps, stale readings and unratified definitions."},

    {"n": "A", "title": "Annexes", "kind": "diagnostic",
     "content": "The full indicator evidence base; the source and tier record; the open-decision "
                "register; the version and configuration record.",
     "binding": {"pillars": ALL_PILLARS, "indicators": ["*"], "use_cases": ALL_UC,
                 "prerequisites": ["*"], "derived": list(DERIVED_SOURCES.keys())},
     "note": "The annex is the audit trail. Nothing is summarised here; rows appear in full."},
]

# ---------------------------------------------------------------------------
# Strategic foresight (design decisions F1, F3, F4).
#
# Declared in the model so it is ratifiable like every other rule. An unnamed
# method would be the one part of the system nobody could review.
# ---------------------------------------------------------------------------
FORESIGHT = {
    "method": "scenarios -> preferred future -> backcasting to milestones",
    "ratified": False,
    "settled_by": "design interview, 24 August 2026",
    "steps": [
        {"id": "scenarios", "name": "Scenarios",
         "purpose": "Bound the uncertainty: plausible futures for the sector, not forecasts."},
        {"id": "preferred_future", "name": "Preferred future",
         "purpose": "The normative selection — what the country would choose to bring about. "
                    "A claim about values, not evidence, and marked as such."},
        {"id": "backcasting", "name": "Backcasting to milestones",
         "purpose": "Work back from the preferred future to dated, measurable milestones."},
    ],
    "milestone_binding": {
        "rule": "Each milestone binds to one or more indicators or prerequisites with a target "
                "level and a target year, so progress is measurable against the same instrument "
                "that produced the diagnostic.",
        "fields": ["indicator_id", "target_level", "target_year"],
        "fallback": "Where no indicator in the model fits, the milestone proposes a CANDIDATE "
                    "indicator (see candidate_indicators) and binds to that instead.",
        "provisionality": "A target level standing on an unratified threshold inherits that "
                          "provisionality and carries the marking of the open decision governing it.",
    },
    "note": "Where a foresight document is supplied it is ingested and this exercise is skipped. "
            "A machine-run preferred future is a facilitation input, never a finding.",
}

# ---------------------------------------------------------------------------
# Candidate indicators (design decision F4).
#
# The mechanism already exists — A1-CAND-IMP and A1-CAND-IRR are carried this
# way. Foresight may create more, so the rule is stated in the model rather
# than left as pipeline convention.
# ---------------------------------------------------------------------------
CANDIDATE_INDICATORS = {
    "purpose": "Let a metric be recorded and carried without silently expanding the scored model.",
    "id_pattern": "^(A1|C1|C2|C3|C4|E1|O1)-CAND-[A-Z0-9-]+$",
    "required_fields": ["id", "name", "proposed_pillar", "rationale", "proposed_by"],
    "may_be_proposed_by": ["foresight backcasting (F4)", "assessor proposal", "indicator audit"],
    "never": [
        "enters a pillar mean",
        "enters a layer mean",
        "enters a use-case mean",
        "carries or gates a prerequisite",
        "appears in the readiness matrix",
    ],
    "disposition": "Recorded, carried beside the assessment, flagged as a ratification item. "
                   "Promotion to a scored indicator is a versioned model change, never automatic.",
}

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
        "derived_sources": DERIVED_SOURCES,
        "dar_outline": DAR_OUTLINE,
        "foresight": FORESIGHT,
        "candidate_indicators": CANDIDATE_INDICATORS,
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
    presc = sum(1 for c in m["dar_outline"] if c["kind"] == "prescriptive")
    print(f"wrote {p}")
    print(f"  {len(m['indicators'])} indicators · {rat} carrying an open definition question "
          f"· {len(m['open_decisions'])} open decisions")
    print(f"  {len(m['dar_outline'])} DAR chapters ({presc} prescriptive) · "
          f"foresight: {m['foresight']['method']}")
    return m


if __name__ == "__main__":
    main()
