#!/usr/bin/env python3
"""Checks for the roadmap generator. No keys, no network.

Three rules decide whether a document may be written: a chapter may cite only what its
binding allows, every figure must trace to the engine, and the gate blocks the emit.

    python3 test_generate_dar.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_dar as D

FAILED, COUNT = [], 0


def check(label, got, want):
    global COUNT
    COUNT += 1
    ok = (got == want) if isinstance(want, (list, bool, int, float)) else (want in str(got))
    if not ok:
        FAILED.append(f"{label}\n    got:  {got}\n    want: {want}")


def section(t):
    print(f"\n## {t}")


BINDING = {"pillars": ["A1", "C1"], "indicators": ["1.1"], "use_cases": ["ADV"],
           "prerequisites": ["2.1"], "derived": ["matrix"]}


section("A chapter may cite only what its binding allows (E4)")

check("citing inside the binding is clean",
      D.binding_gate({"pillars": ["A1"], "indicators": ["1.1"], "use_cases": [],
                      "prerequisites": []}, BINDING), [])

check("a pillar outside the binding is caught",
      # A financing chapter reaching for connectivity indicators reads perfectly fluently
      # and is wrong. This is the only mechanism that catches it before a reader does.
      D.binding_gate({"pillars": ["E1"], "indicators": [], "use_cases": [],
                      "prerequisites": []}, BINDING), ["pillar E1"])

check("an indicator outside the binding is caught",
      D.binding_gate({"pillars": [], "indicators": ["7.12"], "use_cases": [],
                      "prerequisites": []}, BINDING), ["indicator 7.12"])

check("several violations are all reported",
      len(D.binding_gate({"pillars": ["E1"], "indicators": ["9.9"], "use_cases": ["FIN"],
                          "prerequisites": []}, BINDING)), 3)


section("Every figure must trace to the engine (E3)")

ALLOWED = {2.71, 109.1, 57.0, 4.0}

check("a figure the engine produced is supported",
      D.fidelity_check("The mean is 2.71.", [{"value": "2.71", "what_it_is": "A1 mean"}],
                       ALLOWED)[0][0]["value"], "2.71")

check("a figure the engine never produced is unsupported",
      D.fidelity_check("The mean is 3.44.", [{"value": "3.44", "what_it_is": "A1 mean"}],
                       ALLOWED)[1][0]["value"], "3.44")

check("a number in the prose that was never declared is a stray",
      # The shape this check most has to catch: a fabricated figure the writer did not
      # even list among its figures.
      D.fidelity_check("Coverage reached 63.2% last year.", [], ALLOWED)[2], ["63.2"])

check("a small count is ordinary prose, not a stray",
      D.fidelity_check("The seven pillars divide into four layers.", [], ALLOWED)[2], [])

check("a calendar year is ordinary prose",
      D.fidelity_check("The strategy was published in 2023.", [], ALLOWED)[2], [])

check("a percentage is never ordinary",
      D.fidelity_check("Adoption stands at 41.8%.", [], ALLOWED)[2], ["41.8"])

check("a declared figure is not also counted as a stray",
      D.fidelity_check("The value is 109.1.", [{"value": "109.1", "what_it_is": "1.4"}],
                       ALLOWED)[2], [])

check("ordinary covers counts up to twelve only", D._ordinary(12), True)
check("thirteen is not an ordinary count", D._ordinary(13), False)
check("a decimal is never ordinary", D._ordinary(4.5), False)


section("What the engine is allowed to have produced")

ASSESS = {
    "pillars": {"A1": {"n": 8, "rated": 7, "held": 1, "mean": 2.71, "band": "Established",
                       "margin": 0.21, "comp": 0.9, "stale": 2}},
    "layers": {}, "matrix": {"ADV": {"n_bearing": 5, "mean_readiness": 3.2,
                                     "mean_need": 2.0, "mean_outcome": 1.5, "mean_driven": 2.5}},
    "counts": {"Measured": 30, "Documented": 15, "Judged": 7, "Gap": 5},
    "rated": 47, "held": 5,
    "indicators": {"1.4": {"level": 3, "value": 109.1, "year": 2022}},
}

check("pillar means are allowed", 2.71 in D.allowed_figures(ASSESS), True)
check("indicator values are allowed", 109.1 in D.allowed_figures(ASSESS), True)
check("matrix means are allowed", 3.2 in D.allowed_figures(ASSESS), True)
check("a figure nobody produced is not allowed", 3.44 in D.allowed_figures(ASSESS), False)
check("milestone targets are allowed once foresight has run",
      2033.0 in D.allowed_figures(ASSESS, {"milestones": [{"target_level": 4,
                                                           "target_year": 2033}]}), True)


section("The gate blocks the emit (E5)")


def doc(**over):
    ch = dict(n="3", title="Vision", kind="prescriptive",
              status="proposed, not evidenced", provenance="Chapter 3 draws on ...",
              cited_outside_binding=[], stray_numbers=[])
    base = {"chapters": [dict(ch, **over.pop("chapter", {}))],
            "fidelity": {"rate": 1.0, "claimed": 4, "supported": 4, "unsupported": 0}}
    base.update(over)
    return base


def failing(d):
    return [n for n, ok, _ in D.qc_checks(d) if not ok]


check("a clean single-chapter document fails only the completeness check",
      failing(doc()), ["B6 every chapter of the outline is present"])

check("a chapter with no provenance banner blocks the emit",
      "B1 every chapter carries a provenance banner" in failing(doc(chapter={"provenance": ""})),
      True)

check("citing outside the binding blocks the emit",
      "B2 no chapter cites outside its binding"
      in failing(doc(chapter={"cited_outside_binding": ["pillar E1"]})), True)

check("a prescriptive chapter presented as evidenced blocks the emit",
      # The one a reader must not miss, so it is stated three times: on the page, in the
      # record, and here.
      "B3 no prescriptive chapter renders as evidenced"
      in failing(doc(chapter={"status": "evidenced by the assessment"})), True)

check("fidelity below the floor blocks the emit",
      "B4 figure fidelity at or above 95%"
      in failing(doc(fidelity={"rate": 0.8, "claimed": 10, "supported": 8, "unsupported": 2})),
      True)

check("undeclared numbers block the emit",
      "B5 no undeclared numbers in the prose"
      in failing(doc(chapter={"stray_numbers": ["63.2"]})), True)


section("The outline is read from the model")

check("all eleven chapters are declared", len(D.OUTLINE), 11)
check("chapters 3 to 10 are prescriptive",
      sum(1 for c in D.OUTLINE if c["kind"] == "prescriptive"), 8)
check("the fidelity floor is high enough to mean something", D.FIDELITY_FLOOR >= 0.95, True)


print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT} checks FAILED\n")
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print(f"all {COUNT} checks pass")
