#!/usr/bin/env python3
"""Pass four: foresight (design decisions F1-F4).

The method is declared in the model file, not here: scenarios -> preferred future ->
backcasting to milestones. An unnamed method would be the one part of the system nobody
could review, so this script reads its own steps from `model.foresight` and would change
if a ratification changed them.

Three things this pass is built to keep straight.

**A scenario is not a forecast.** Scenarios bound the uncertainty; they are plausible
futures, and the output says so on every record. Nothing here predicts.

**The preferred future is a claim about values, not evidence.** It is the one normative
act in the whole pipeline, and it is marked as such structurally — its own key, its own
status line — rather than left to the reader to infer from tone.

**A milestone that binds to nothing is not a milestone.** F3 requires every milestone to
attach to an indicator or prerequisite with a target level and a target year, so progress
is measurable against the same instrument that produced the diagnostic. A milestone that
fails to bind is refused rather than recorded as prose, because prose is exactly what the
binding rule exists to prevent. Where nothing in the model fits, the milestone proposes a
candidate indicator (F4) and binds to that — recorded, carried, and outside every
aggregate, which is the existing mechanism and not a new one.

Foresight stands on a completed assessment. Running it without one would produce
milestones aimed at levels nobody has measured.

    python3 foresight.py --country Egypt --iso EGY --out EGY_shadow [--ceiling 500] [--resume]
"""

import argparse, html, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(LOOP1, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, LOOP1)

import vendors as V
from engine_v17 import MODEL, run as engine_run

PASS = "foresight"
MODEL_FILE = os.path.join(REPO, "model", "DAMM-v1.7-model.json")
SPEC = json.load(open(MODEL_FILE))
ASSESSMENT_YEAR = SPEC["config"]["assessment_year"]
FORESIGHT = SPEC["foresight"]
CANDIDATE = SPEC["candidate_indicators"]
CANDIDATE_PATTERN = re.compile(CANDIDATE["id_pattern"])

N_SCENARIOS = 3
# Beyond about fifteen years a "milestone" is a wish with a date on it, and inside the
# assessment year it is a description of the present. Both ends are refusals, not clamps:
# silently moving a date would put a year on the page that nobody chose.
HORIZON_YEARS = 15

SYSTEM = ("You conduct structured foresight for a national digital agriculture roadmap. "
          "You distinguish what is measured from what is chosen, and you say which is "
          "which. JSON only.")


# ------------------------------------------------------------------ the gates
#
# Pure, so the binding rule can be tested without a key or a network.

def known_indicator(indicator_id):
    return indicator_id in MODEL


def well_formed_candidate(cand):
    """A proposed candidate indicator, or a reason it is not one.

    The pattern and the required fields come from the model. A candidate that does not
    match cannot be carried, because the id pattern is what keeps candidates out of the
    aggregates: every consumer recognises them by shape.
    """
    if not isinstance(cand, dict):
        return "no candidate indicator was supplied"
    cid = (cand.get("id") or "").strip()
    if not cid:
        return "the candidate has no id"
    if not CANDIDATE_PATTERN.match(cid):
        return f"the candidate id {cid} does not match the model's pattern"
    missing = [f for f in CANDIDATE["required_fields"] if not str(cand.get(f) or "").strip()]
    if missing:
        return f"the candidate is missing {', '.join(missing)}"
    return None


def milestone_gate(m, levels, assessment_year=ASSESSMENT_YEAR, horizon=HORIZON_YEARS):
    """Whether a milestone is measurable against the instrument. Refusal, or None.

    `levels` maps indicator id to the level the assessment recorded, or None where the
    row is a gap or its level is withheld.
    """
    iid = (m.get("indicator_id") or "").strip()
    if not iid:
        return "it binds to no indicator"

    if not known_indicator(iid):
        why = well_formed_candidate(m.get("candidate_indicator"))
        if why:
            return f"{iid} is not in the model and {why}"
        if m["candidate_indicator"]["id"] != iid:
            return "it binds to one id and proposes another"

    level = m.get("target_level")
    if not isinstance(level, int) or not 1 <= level <= 5:
        return f"the target level {level!r} is not a level on the scale"

    year = m.get("target_year")
    if not isinstance(year, int):
        return f"the target year {year!r} is not a year"
    if year <= assessment_year:
        return f"the target year {year} is not after the assessment year {assessment_year}"
    if year > assessment_year + horizon:
        return f"the target year {year} is more than {horizon} years out"

    # A target at or below where the country already stands is not a milestone. Recording
    # it would put an achievement on the roadmap as though it were an ambition.
    current = levels.get(iid)
    if current is not None and level <= current:
        return f"{iid} is already at level {current}, so level {level} is not an advance"

    return None


def provisionality_of(indicator_id):
    """The open decision governing this row, where one exists (F4, A3).

    A target level standing on an unratified threshold inherits that provisionality. The
    marking travels with the milestone rather than being looked up at render time.
    """
    for ind in SPEC["indicators"]:
        if ind["id"] == indicator_id and ind.get("ratification"):
            return ind["ratification"].get("open_question")
    if not known_indicator(indicator_id):
        return ("This milestone binds to a proposed candidate indicator, which is not "
                "part of the scored model and carries no ratified thresholds.")
    return None


# ------------------------------------------------------------------ schemas

SCENARIO_SCHEMA = {
    "type": "object",
    "properties": {
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "narrative": {"type": "string"},
                    "drivers": {"type": "array", "items": {"type": "string"}},
                    "what_would_make_it_happen": {"type": "string"},
                    "implication_for_the_sector": {"type": "string"},
                },
                "required": ["name", "narrative", "drivers",
                             "what_would_make_it_happen", "implication_for_the_sector"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scenarios"],
    "additionalProperties": False,
}

PREFERRED_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "narrative": {"type": "string"},
        "drawn_from_scenarios": {"type": "array", "items": {"type": "string"}},
        "what_is_being_chosen": {"type": "string"},
        "who_would_have_to_agree": {"type": "string"},
    },
    "required": ["name", "narrative", "drawn_from_scenarios",
                 "what_is_being_chosen", "who_would_have_to_agree"],
    "additionalProperties": False,
}

MILESTONE_SCHEMA = {
    "type": "object",
    "properties": {
        "milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "indicator_id": {"type": "string"},
                    "target_level": {"type": "integer"},
                    "target_year": {"type": "integer"},
                    "why_this_step": {"type": "string"},
                    "candidate_indicator": {
                        "type": ["object", "null"],
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "proposed_pillar": {"type": "string"},
                            "rationale": {"type": "string"},
                            "proposed_by": {"type": "string"},
                        },
                        "required": ["id", "name", "proposed_pillar", "rationale",
                                     "proposed_by"],
                        "additionalProperties": False,
                    },
                },
                "required": ["statement", "indicator_id", "target_level", "target_year",
                             "why_this_step", "candidate_indicator"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["milestones"],
    "additionalProperties": False,
}


# ------------------------------------------------------------------ grounding

def standing_text(assessment, levels):
    """Where the country stands, as the foresight steps are allowed to see it."""
    lines = []
    for pid, p in sorted(assessment["pillars"].items()):
        lines.append(f"  {pid}: mean {p['mean']} ({p['band']}), {p['rated']} of {p['n']} rated"
                     + (f", {p['held']} withheld" if p.get("held") else ""))
    prereq = assessment.get("prerequisites", {})
    absent = [k for k, v in prereq.items()
              if (v.get("status") if isinstance(v, dict) else v) == "Absent"]
    unver = [k for k, v in prereq.items()
             if (v.get("status") if isinstance(v, dict) else v) == "Unverified"]
    out = ["PILLARS:", *lines]
    if absent:
        out.append(f"PREREQUISITES ABSENT: {', '.join(sorted(absent))}")
    if unver:
        out.append(f"PREREQUISITES UNVERIFIED (nothing is asserted about these): "
                   f"{', '.join(sorted(unver))}")
    rated = [f"{i} L{l}" for i, l in sorted(levels.items()) if l is not None]
    out.append(f"RATED ROWS: {', '.join(rated)}")
    return "\n".join(out)


def scans_text(basename):
    """The country findings from the scans pass, where that pass has run."""
    p = os.path.join(LOOP1, f"{basename}_scans.json")
    if not os.path.exists(p):
        return ""
    data = json.load(open(p))
    rows = data.get("country_findings") or []
    if not rows:
        return ""
    # Country findings only. International pointers feed the DAR (E2) and have no place
    # in a country's own foresight exercise.
    return "\nWHAT THE COUNTRY HAS ALREADY PUBLISHED:\n" + "\n".join(
        f"  - {r['statement']} [{r['source_name']}, {r['tier']}]" for r in rows[:12])


# ------------------------------------------------------------------ the report

def render_html(payload):
    """The standalone foresight report (steps 7-8).

    Three things it states rather than implies. Scenarios are not forecasts. The preferred
    future is a choice about values and not a finding from evidence. A milestone binds to
    the instrument, and one that binds to a proposed candidate is standing on something
    the model has not ratified.
    """
    c = html.escape
    p = payload
    out = [
        "<meta charset='utf-8'>",
        f"<title>{c(p['country'])} — Strategic Foresight</title>",
        "<style>",
        "body{font:16px/1.65 Georgia,serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1a1a1a}",
        "h1{font-size:2rem;margin-bottom:.15em}h2{margin-top:2.4em;border-bottom:1px solid #ddd;padding-bottom:.2em}",
        "h3{margin-bottom:.2em}",
        ".note{background:#f4f2ec;border-left:3px solid #9aa;padding:.7em 1em;font:13px/1.6 system-ui;margin:1em 0}",
        ".normative{background:#fff7e6;border-left:3px solid #d9a441}",
        ".drivers{font:13px/1.6 system-ui;color:#555}",
        "table{border-collapse:collapse;width:100%;font:14px/1.5 system-ui;margin:1em 0}",
        "th,td{border-bottom:1px solid #e5e5e5;padding:.5em .4em;text-align:left;vertical-align:top}",
        "th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#666}",
        ".prov{color:#8a6d1f;font:12px/1.5 system-ui}",
        ".cand{background:#fff7e6}",
        ".refused{font:13px/1.6 system-ui;color:#666}",
        ".prohib{font:12px/1.6 system-ui;color:#666;border-top:1px solid #ddd;margin-top:3em;padding-top:1em}",
        "</style>",
        f"<h1>{c(p['country'])} — Strategic Foresight</h1>",
        f"<p><em>Pre-review draft. Method: {c(p['method'])}"
        + ("" if p.get("method_ratified") else " — the method is declared in the model file and is not yet ratified")
        + f". Assessment year {p['assessment_year']}.</em></p>",
    ]

    out.append("<h2>Scenarios</h2>")
    out.append(f"<div class='note'>{c(p['scenario_status'])}</div>")
    for sc in p["scenarios"]:
        out.append(f"<h3>{c(sc['name'])}</h3>")
        out.append(f"<p>{c(sc['narrative'])}</p>")
        if sc.get("drivers"):
            out.append(f"<p class='drivers'><b>Driven by:</b> "
                       f"{c(', '.join(sc['drivers']))}</p>")
        if sc.get("what_would_make_it_happen"):
            out.append(f"<p class='drivers'><b>What would bring it about:</b> "
                       f"{c(sc['what_would_make_it_happen'])}</p>")
        if sc.get("implication_for_the_sector"):
            out.append(f"<p class='drivers'><b>Implication:</b> "
                       f"{c(sc['implication_for_the_sector'])}</p>")

    pf = p["preferred_future"]
    out.append("<h2>The preferred future</h2>")
    out.append(f"<div class='note normative'>{c(p['preferred_future_status'])}</div>")
    out.append(f"<h3>{c(pf['name'])}</h3><p>{c(pf['narrative'])}</p>")
    if pf.get("what_is_being_chosen"):
        out.append(f"<p><b>What is being chosen:</b> {c(pf['what_is_being_chosen'])}</p>")
    if pf.get("who_would_have_to_agree"):
        out.append(f"<p><b>Who would have to agree:</b> {c(pf['who_would_have_to_agree'])}</p>")

    out.append("<h2>Milestones</h2>")
    out.append(f"<div class='note'>{c(p['note'])}</div>")
    out.append("<table><thead><tr><th>Milestone</th><th>Binds to</th><th>Target</th>"
               "<th>By</th></tr></thead><tbody>")
    for m in p["milestones"]:
        cand = m.get("binds_to_candidate")
        out.append(
            f"<tr{' class=cand' if cand else ''}><td>{c(m['statement'])}"
            + (f"<div class='drivers'>{c(m.get('why_this_step',''))}</div>"
               if m.get("why_this_step") else "")
            + (f"<div class='prov'>{c(m['provisional_because'])}</div>"
               if m.get("provisional_because") else "")
            + f"</td><td>{c(m['indicator_id'])}"
            + ("<div class='prov'>proposed candidate — outside every aggregate</div>"
               if cand else "")
            + f"</td><td>Level {m['target_level']}</td><td>{m['target_year']}</td></tr>")
    out.append("</tbody></table>")

    if p.get("candidate_indicators"):
        out.append("<h2>Candidate indicators proposed</h2>")
        out.append(f"<div class='note normative'>{c(p['candidate_status'])}</div>")
        out.append("<table><thead><tr><th>Id</th><th>Name</th><th>Pillar</th>"
                   "<th>Why</th></tr></thead><tbody>")
        for cd in p["candidate_indicators"]:
            out.append(f"<tr><td>{c(cd['id'])}</td><td>{c(cd['name'])}</td>"
                       f"<td>{c(cd['proposed_pillar'])}</td>"
                       f"<td>{c(cd.get('rationale',''))}</td></tr>")
        out.append("</tbody></table>")

    if p.get("refused_milestones"):
        # Shown, not dropped. A milestone the exercise produced and the binding rule
        # refused is a fact about the exercise, and hiding it would make the kept ones
        # look like everything it had to say.
        out.append("<h2>Proposed and not recorded</h2>")
        out.append("<p class='refused'>These were produced by the backcasting step and "
                   "refused, because a milestone that cannot be measured against the "
                   "instrument is not a milestone.</p><ul class='refused'>")
        for r in p["refused_milestones"]:
            out.append(f"<li>{c(r.get('statement',''))} — <i>{c(r.get('why',''))}</i></li>")
        out.append("</ul>")

    out.append("<div class='prohib'><b>Standing prohibitions.</b> "
               + c(" ".join(str(x) for x in SPEC.get("prohibitions", []))) + "</div>")
    return "\n".join(out)


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
        print("   Foresight stands on a completed assessment. Without one it would aim "
              "milestones at levels nobody has measured. Finish the research pass first.")
        return 1

    V.load_env()
    vendor, _, mname = a.vendor.partition("/")
    ledger = V.Ledger(ceiling=a.ceiling, label=f"{a.out}_foresight")
    llm = V.LLM(vendor, ledger, model=mname or None)

    state_path = os.path.join(LOOP1, f"{a.out}_foresight_state.json")
    spend_path = os.path.join(LOOP1, f"{a.out}_foresight_spend.json")
    out_path = os.path.join(LOOP1, f"{a.out}_foresight.json")

    rows = json.load(open(inp))
    assessment = engine_run(
        a.country, rows, refyear=ASSESSMENT_YEAR, model_spec=SPEC,
        intervention_profiles={})
    levels = {i: r.get("level") for i, r in rows.items() if i in MODEL}
    standing = standing_text(assessment, levels) + scans_text(a.out)

    state = {"scenarios": None, "preferred_future": None, "milestones": None,
             "refused": []}
    if a.resume and os.path.exists(state_path):
        state = json.load(open(state_path))
        carried = ledger.load(spend_path)
        done = sum(1 for k in ("scenarios", "preferred_future", "milestones") if state.get(k))
        print(f"resuming — {done} of 3 steps already done, {carried} earlier vendor calls "
              f"carried (${ledger.spent():.2f} spent)")

    steps = FORESIGHT["steps"]
    print(f"{a.country} ({a.iso}) · {len(steps)} rows · vendor {a.vendor}")
    print(f"budget ${a.ceiling:.0f}, foresight allocation "
          f"${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} (decision G3)")
    print(f"method: {FORESIGHT['method']}")
    print()
    sys.stdout.flush()

    def save():
        json.dump(state, open(state_path, "w"), indent=1, default=str)
        ledger.save(spend_path)

    def report(n, step_id, outcome, detail, t0):
        print(f"  [{n}/{len(steps)}] {step_id:<17} {outcome:<8} {detail[:44]:<46} "
              f"$ {ledger.spent():5.2f} {int(time.time() - t0):3d}s")
        sys.stdout.flush()

    try:
        # ---- 1. scenarios
        t0 = time.time()
        if not state.get("scenarios"):
            ans = llm.json_call(
                SYSTEM,
                f"COUNTRY: {a.country}\nASSESSMENT YEAR: {ASSESSMENT_YEAR}\n\n"
                f"WHERE THE COUNTRY STANDS:\n{standing}\n\n"
                f"STEP: {steps[0]['name']} — {steps[0]['purpose']}\n\n"
                f"Write {N_SCENARIOS} scenarios for this country's digital agriculture "
                f"sector to {ASSESSMENT_YEAR + 10}. These bound the uncertainty; they are "
                "not forecasts and none of them is the recommendation. Make them "
                "genuinely different in what drives them, and ground each in the standing "
                "above.",
                SCENARIO_SCHEMA, PASS, max_tokens=6000, detail="scenarios")
            state["scenarios"] = ans["scenarios"]
            save()
        report(1, steps[0]["id"], "written", f"{len(state['scenarios'])} scenarios", t0)

        # ---- 2. preferred future
        t0 = time.time()
        if not state.get("preferred_future"):
            names = ", ".join(s["name"] for s in state["scenarios"])
            ans = llm.json_call(
                SYSTEM,
                f"COUNTRY: {a.country}\n\nSCENARIOS: {names}\n\n"
                + json.dumps(state["scenarios"])[:6000] + "\n\n"
                f"STEP: {steps[1]['name']} — {steps[1]['purpose']}\n\n"
                "Describe the future this country would choose to bring about. Say "
                "plainly in what_is_being_chosen that this is a normative selection — a "
                "claim about values rather than a finding from evidence — and say who "
                "would have to agree to it.",
                PREFERRED_SCHEMA, PASS, max_tokens=4000, detail="preferred future")
            state["preferred_future"] = ans
            save()
        report(2, steps[1]["id"], "written", state["preferred_future"]["name"], t0)

        # ---- 3. backcasting
        t0 = time.time()
        if not state.get("milestones"):
            ids = ", ".join(f"{i}({MODEL[i]['name']})" for i in sorted(MODEL))
            ans = llm.json_call(
                SYSTEM,
                f"COUNTRY: {a.country}\nASSESSMENT YEAR: {ASSESSMENT_YEAR}\n\n"
                f"WHERE THE COUNTRY STANDS:\n{standing}\n\n"
                f"PREFERRED FUTURE:\n{json.dumps(state['preferred_future'])[:3000]}\n\n"
                f"STEP: {steps[2]['name']} — {steps[2]['purpose']}\n\n"
                f"INDICATORS YOU MAY BIND TO:\n{ids}\n\n"
                "Work back from the preferred future to dated, measurable milestones. "
                "EVERY milestone must name one indicator_id from the list above, a "
                f"target_level between 1 and 5 that is HIGHER than the level recorded "
                f"above, and a target_year after {ASSESSMENT_YEAR} and no later than "
                f"{ASSESSMENT_YEAR + HORIZON_YEARS}.\n\n"
                "Where nothing in the list measures what a milestone needs, propose a "
                f"candidate indicator instead: set indicator_id to an id matching "
                f"{CANDIDATE['id_pattern']} and fill candidate_indicator with id, name, "
                "proposed_pillar, rationale and proposed_by. Otherwise leave "
                "candidate_indicator null.",
                MILESTONE_SCHEMA, PASS, max_tokens=8000, detail="backcasting")

            kept, refused = [], []
            for m in ans["milestones"]:
                why = milestone_gate(m, levels)
                if why:
                    refused.append({"statement": m.get("statement", ""), "why": why})
                    continue
                m["provisional_because"] = provisionality_of(m["indicator_id"])
                m["binds_to_candidate"] = not known_indicator(m["indicator_id"])
                kept.append(m)
            state["milestones"] = kept
            state["refused"] = refused
            save()
        n_ref = len(state.get("refused") or [])
        report(3, steps[2]["id"], "written",
               f"{len(state['milestones'])} bound, {n_ref} refused", t0)

    except V.BudgetExhausted as e:
        print(f"\n!! {e}")
        print("   The exercise stopped where the budget ran out. Steps never reached are "
              "absent from the output, NOT recorded as having produced nothing.")
        save()
        return 0

    candidates = [m["candidate_indicator"] for m in state["milestones"]
                  if m.get("candidate_indicator")]
    payload = {
        "country": a.country,
        "iso3": a.iso,
        "assessment_year": ASSESSMENT_YEAR,
        "method": FORESIGHT["method"],
        "method_ratified": FORESIGHT.get("ratified", False),
        "scenarios": state["scenarios"],
        "scenario_status": ("Scenarios bound the uncertainty. They are plausible futures, "
                            "not forecasts, and none of them is a recommendation."),
        "preferred_future": state["preferred_future"],
        # The one normative act in the pipeline, marked structurally rather than by tone.
        "preferred_future_status": ("A normative selection — a claim about values, not a "
                                    "finding from evidence. It is proposed for decision, "
                                    "not asserted."),
        "milestones": state["milestones"],
        "refused_milestones": state.get("refused") or [],
        "candidate_indicators": candidates,
        "candidate_status": CANDIDATE["disposition"],
        "note": ("Every milestone binds to an indicator or a proposed candidate with a "
                 "target level and year (F3), so progress is measurable against the same "
                 "instrument that produced the diagnostic. Candidates are carried outside "
                 "every aggregate."),
    }
    json.dump(payload, open(out_path, "w"), indent=1, default=str)
    html_path = os.path.join(LOOP1, f"{a.out}_foresight.html")
    open(html_path, "w").write(render_html(payload))
    ledger.save(spend_path)

    print()
    print(f"wrote {a.out}_foresight.html — the standalone report")
    print(f"wrote {a.out}_foresight.json — {len(state['scenarios'])} scenarios, "
          f"{len(state['milestones'])} milestones, {len(candidates)} candidate indicators, "
          f"{len(state.get('refused') or [])} refused")
    s = ledger.summary()
    print(f"spend ${s['total']:.2f} of ${a.ceiling * V.Ledger.ALLOCATION[PASS]:.0f} "
          f"allocated (${a.ceiling:.0f} country ceiling), {s['calls']} vendor calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
