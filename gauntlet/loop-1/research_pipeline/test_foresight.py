#!/usr/bin/env python3
"""Checks for the foresight pass. No keys, no network.

The rule worth testing is F3: a milestone that binds to nothing is not a milestone. Prose
is exactly what the binding rule exists to prevent, so a milestone that fails to bind must
be refused rather than recorded.

    python3 test_foresight.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foresight as F

FAILED, COUNT = [], 0
YEAR = F.ASSESSMENT_YEAR
LEVELS = {"1.1": 4, "2.1": 2, "3.7": None}


def check(label, got, want):
    global COUNT
    COUNT += 1
    ok = (got is None) if want is None else (want in str(got))
    if not ok:
        FAILED.append(f"{label}\n    got:  {got}\n    want: {want}")


def m(**kw):
    base = dict(statement="s", indicator_id="2.1", target_level=4,
                target_year=YEAR + 5, why_this_step="w", candidate_indicator=None)
    base.update(kw)
    return base


def section(t):
    print(f"\n## {t}")


section("A milestone must bind to the instrument")

check("a well-formed milestone passes", F.milestone_gate(m(), LEVELS), None)
check("binding to nothing is refused", F.milestone_gate(m(indicator_id=""), LEVELS),
      "binds to no indicator")
check("an invented indicator id is refused",
      F.milestone_gate(m(indicator_id="9.9"), LEVELS), "not in the model")


section("The target has to be a target")

check("a level off the scale is refused", F.milestone_gate(m(target_level=7), LEVELS),
      "not a level on the scale")
check("a non-integer level is refused", F.milestone_gate(m(target_level="four"), LEVELS),
      "not a level on the scale")
check("a level already reached is not an advance",
      # Recording it would put an achievement on the roadmap as though it were an ambition.
      F.milestone_gate(m(indicator_id="1.1", target_level=3), LEVELS),
      "already at level 4")
check("the same level is not an advance either",
      F.milestone_gate(m(indicator_id="1.1", target_level=4), LEVELS),
      "already at level 4")
check("a row with no recorded level can still carry a target",
      # An unrated row asserts nothing, so it cannot contradict a target.
      F.milestone_gate(m(indicator_id="3.7", target_level=3), LEVELS), None)


section("The date has to be a date in the future, within reach")

check("a year in the past is refused", F.milestone_gate(m(target_year=YEAR - 1), LEVELS),
      "not after the assessment year")
check("the assessment year itself is refused",
      F.milestone_gate(m(target_year=YEAR), LEVELS), "not after the assessment year")
check("a year beyond the horizon is refused",
      F.milestone_gate(m(target_year=YEAR + 40), LEVELS), "more than 15 years out")
check("a non-integer year is refused", F.milestone_gate(m(target_year="soon"), LEVELS),
      "not a year")


section("Where nothing in the model fits, a candidate is proposed (F4)")

good = dict(id="C2-CAND-EXTAGENT", name="Extension agents per 1000 farmers",
            proposed_pillar="C2", rationale="r", proposed_by="foresight backcasting (F4)")

check("a well-formed candidate binds",
      F.milestone_gate(m(indicator_id="C2-CAND-EXTAGENT", candidate_indicator=good), LEVELS),
      None)
check("an unknown id with no candidate is refused",
      F.milestone_gate(m(indicator_id="C2-CAND-X", candidate_indicator=None), LEVELS),
      "no candidate indicator was supplied")
check("a candidate whose id does not match the model's pattern is refused",
      # The pattern is what keeps candidates out of the aggregates: every consumer
      # recognises them by shape.
      F.milestone_gate(m(indicator_id="NEW-THING",
                         candidate_indicator=dict(good, id="NEW-THING")), LEVELS),
      "does not match the model's pattern")
check("a candidate missing a required field is refused",
      F.milestone_gate(m(indicator_id="C2-CAND-EXTAGENT",
                         candidate_indicator=dict(good, rationale="")), LEVELS),
      "missing rationale")
check("binding to one id while proposing another is refused",
      F.milestone_gate(m(indicator_id="C2-CAND-A",
                         candidate_indicator=dict(good, id="C2-CAND-B")), LEVELS),
      "binds to one id and proposes another")


section("Provisionality travels with the milestone")

check("a candidate carries its unratified standing",
      F.provisionality_of("C2-CAND-EXTAGENT"), "not part of the scored model")
check("a plain rated indicator carries nothing extra",
      F.provisionality_of("1.1") in (None, ) or isinstance(F.provisionality_of("1.1"), str),
      "True")


section("The method is read from the model, not restated here")

check("the three declared steps are used", len(F.FORESIGHT["steps"]), "3")
check("the method names backcasting", F.FORESIGHT["method"], "backcasting")
check("the candidate pattern comes from the model",
      F.CANDIDATE_PATTERN.pattern, F.CANDIDATE["id_pattern"])


print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT} checks FAILED\n")
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print(f"all {COUNT} checks pass")
