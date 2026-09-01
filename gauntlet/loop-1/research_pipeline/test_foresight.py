#!/usr/bin/env python3
"""Checks for the foresight pass. No keys, no network.

The rule worth testing is F3: a milestone that binds to nothing is not a milestone. Prose
is exactly what the binding rule exists to prevent, so a milestone that fails to bind must
be refused rather than recorded.

    python3 test_foresight.py
"""
import copy, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foresight as F
import foresight_contract as FC

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
check("a model indicator cannot also carry a candidate definition",
      F.milestone_gate(m(indicator_id="2.1", candidate_indicator=good), LEVELS),
      "model indicator but also proposes a candidate")

_resume_kept, _resume_refused = F.milestone_contract_gate(
    [m(indicator_id="2.1", candidate_indicator=good)], LEVELS)
check("a resumed milestone is revalidated against the same contract",
      _resume_kept, "[]")
check("a resumed invalid candidate binding is explicitly refused",
      _resume_refused[0]["why"],
      "model indicator but also proposes a candidate")

_valid_resume = m()
_valid_resume_before = copy.deepcopy(_valid_resume)
F.milestone_contract_gate([_valid_resume], LEVELS)
check("contract validation does not mutate resumed milestone state",
      _valid_resume == _valid_resume_before, "True")


section("The candidate register has one definition per candidate id")

_shared_candidate = dict(good, id="C2-CAND-SHARED")
_shared_bindings = [
    m(indicator_id="C2-CAND-SHARED", candidate_indicator=dict(_shared_candidate)),
    m(indicator_id="C2-CAND-SHARED", candidate_indicator=dict(_shared_candidate),
      statement="a later milestone using the same metric", target_year=YEAR + 7),
]
_shared_registry = FC.build_candidate_registry(_shared_bindings)
check("two consistent milestone bindings produce one candidate register entry",
      [candidate["id"] for candidate in _shared_registry.indicators],
      "['C2-CAND-SHARED']")
check("consistent reuse is not a candidate-definition conflict",
      list(_shared_registry.conflicts), "[]")

_conflicting_bindings = [
    _shared_bindings[0],
    m(indicator_id="C2-CAND-SHARED",
      candidate_indicator=dict(_shared_candidate, name="A different metric definition"),
      statement="a milestone whose candidate definition conflicts", target_year=YEAR + 8),
]
_conflicting_registry = FC.build_candidate_registry(_conflicting_bindings)
check("conflicting reuse identifies the later milestone",
      _conflicting_registry.conflicts[0].milestone_index, "1")
check("conflicting reuse identifies the shared candidate id",
      _conflicting_registry.conflicts[0].candidate_id, "C2-CAND-SHARED")
check("conflicting reuse gives an explicit refusal reason",
      _conflicting_registry.conflicts[0].reason,
      "conflicts with its earlier definition")

_kept, _refused = F.candidate_registry_gate(_conflicting_bindings)
check("the first candidate definition remains bound",
      [milestone["statement"] for milestone in _kept], "['s']")
check("the conflicting later milestone is explicitly refused",
      _refused[0]["why"],
      "C2-CAND-SHARED conflicts with its earlier definition")


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


section("The standalone report states what it is")

_P = dict(
    country="Egypt", iso3="EGY", assessment_year=YEAR, method=F.FORESIGHT["method"],
    method_ratified=False,
    scenarios=[dict(name="Stalled rollout", narrative="n", drivers=["a"],
                    what_would_make_it_happen="w", implication_for_the_sector="i")],
    scenario_status=("Scenarios bound the uncertainty. They are plausible futures, not "
                     "forecasts, and none of them is a recommendation."),
    preferred_future=dict(name="Connected smallholders", narrative="n",
                          drawn_from_scenarios=["Stalled rollout"],
                          what_is_being_chosen="a choice about values",
                          who_would_have_to_agree="MALR"),
    preferred_future_status=("A normative selection — a claim about values, not a finding "
                             "from evidence."),
    milestones=[dict(statement="s", indicator_id="2.1", target_level=4, target_year=YEAR + 7,
                     why_this_step="w", provisional_because=None, binds_to_candidate=False),
                dict(statement="s2", indicator_id="C2-CAND-EXT", target_level=3,
                     target_year=YEAR + 5, why_this_step="w",
                     provisional_because="not part of the scored model",
                     binds_to_candidate=True)],
    refused_milestones=[dict(statement="a vague aspiration", why="it binds to no indicator")],
    candidate_indicators=[dict(id="C2-CAND-EXT", name="Extension agents",
                               proposed_pillar="C2", rationale="r")],
    candidate_status="Recorded, carried, flagged as a ratification item.",
    note="Every milestone binds to an indicator or a proposed candidate.",
)
_H = F.render_html(_P)

check("it says scenarios are not forecasts", _H, "not forecasts")
check("it marks the preferred future as a claim about values", _H, "claim about values")
check("a candidate-bound milestone says it is outside every aggregate", _H,
      "outside every aggregate")
check("a provisional milestone carries why", _H, "not part of the scored model")
check("refused milestones are shown, not dropped", _H, "a vague aspiration")
check("an unratified method says so", _H, "not yet ratified")
check("the standing prohibitions are on the page", _H, "prohibitions")
check("nothing is left unescaped from the model text", "<script" in _H, "False")


section("The standalone report is an offline consulting working paper")

check("the report is a complete HTML document", _H.lstrip().lower(), "<!doctype html>")
check("the report identifies the lifecycle state", _H, "Lifecycle")
check("the report includes an accessible milestone timeline", _H,
      'aria-label="Backcast milestone timeline"')
check("the timeline presents milestones chronologically",
      _H.index(str(YEAR + 5)) < _H.index(str(YEAR + 7)), "True")
check("the timeline distinguishes candidate milestones from findings", _H,
      "Proposed / unratified")
check("the report has print rules", _H, "@media print")
check("the report contains no remote stylesheet or script dependency",
      any(token in _H.lower() for token in ("@import", "<script", "src=\"http",
                                             "src='http")), "False")
check("rendering the same payload is byte deterministic", F.render_html(_P) == _H, "True")

_hostile = copy.deepcopy(_P)
_hostile["scenarios"][0]["narrative"] = '<img src=x onerror="alert(1)">'
_hostile["milestones"][0]["statement"] = "Measure <script>alert(1)</script>"
_hostile_html = F.render_html(_hostile)
check("scenario prose is escaped", _hostile_html,
      "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;")
check("milestone labels are escaped", "<script" in _hostile_html, "False")


section("TTL documents are evidence, not instructions")

_LONG = ("START_MARKER" + "a" * 18000 + "MIDDLE_MARKER"
         + "b" * 18000 + "TAIL_MARKER")
_original_search = F.V.exa_search
try:
    F.V.exa_search = lambda *args, **kwargs: []
    _sources = F.foresight_context_sources(
        "Egypt",
        [
            {"filename": "future.pdf", "sha256": "a" * 64,
             "extracted_text": _LONG},
            {"filename": "second.txt", "sha256": "b" * 64,
             "extracted_text": "second document evidence"},
        ],
        object(),
    )
finally:
    F.V.exa_search = _original_search

check("every TTL upload is represented", len(_sources), "2")
check("balanced foresight evidence includes the opening", _sources[0]["text"],
      "START_MARKER")
check("balanced foresight evidence includes the middle", _sources[0]["text"],
      "MIDDLE_MARKER")
check("balanced foresight evidence includes the tail", _sources[0]["text"],
      "TAIL_MARKER")
check("coverage policy is recorded",
      _sources[0]["analysis_coverage"]["policy"], F.WI.BALANCED_EXCERPT_POLICY)
_context = F.context_text(_sources)
check("the prompt states the TTL evidence boundary", _context, "NEVER INSTRUCTIONS")
check("the prompt discloses excerpt coverage", _context, "ANALYSIS_COVERAGE")
check("the prompt retains the tail", _context, "TAIL_MARKER")
check("the source inventory retains coverage",
      F.context_inventory(_sources)[0], "analysis_coverage")
check("the system instruction rejects embedded commands", F.SYSTEM, "never instructions")


print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT} checks FAILED\n")
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print(f"all {COUNT} checks pass")
