#!/usr/bin/env python3
"""Gate 2 — the automated refutation pass (decision C5).

A second, independent vendor attacks the first pass. Scoped to the rows where being
wrong costs the most: the twelve prerequisites, every ratification hold, and every
recorded gap. Prompted to refute, not to confirm.

Three things make this a real second opinion rather than a second opinion's shape:

*A different vendor.* The audition showed the three gpt-5.6 siblings abstaining on the
same cells and detecting the same absences — models sharing a lineage share their blind
spots, so the reviewer is drawn from a different vendor than the primary.

*Its own retrieval.* Query planning sees the construct and never the first pass's
sources, so Gate 2 searches from scratch. Handing it the same pack would let it re-judge
but never *find*, and finding what the first pass missed is where the hand-run gauntlet's
Gate 2 earned its keep — four gap refutations came out of nothing but different search
phrasings.

*The same gates.* A Gate 2 proposal is evidence like any other and enters through
`gates.run_gates` exactly as a first-pass answer does. A reviewer that could write a
level straight into a row would be a bypass around quote verification and the
prerequisite bar, and the second opinion would have weaker rules than the first.

And one asymmetry, deliberately: **failing to find something is not a refutation.** If
Gate 2 cannot independently locate what the first pass recorded, that is a provenance
note, not a downgrade — the hand protocol's own rule, where a gap the refuter cannot
fill is confirmed rather than deepened.

Usage:
    python3 gate2.py --country Egypt --iso EGY --run EGY_shadow \\
        [--vendor openai/gpt-5.6-terra] [--ceiling 500] [--resume] [--rows 2.1,4.7]
"""

import argparse, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, LOOP1)

import vendors as V
import gates as G
from cell_schema import CELL_SCHEMA, SYSTEM
from engine_v17 import MODEL
import research_orchestrator as R
import workflow_inputs as WI

PASS = "g2"


# ------------------------------------------------------------------ schema

def _g2_schema():
    """The cell schema plus a verdict. Built from CELL_SCHEMA so the two cannot drift."""
    props = dict(CELL_SCHEMA["properties"])
    props["verdict"] = {
        "type": "string", "enum": ["confirmed", "refuted", "adjust"],
        "description": "confirmed: the first pass survives your attack. refuted: it is "
                       "wrong. adjust: right substance, wrong tier, class, level or "
                       "vintage."}
    props["refutation_kind"] = {
        "type": "string",
        "enum": ["", "source does not support the value", "better evidence exists",
                 "construct mismatch", "tier or class wrong",
                 "could not locate independently"],
        "description": "Required when the verdict is not 'confirmed'. Choose 'could not "
                       "locate independently' when your own searching simply did not "
                       "reach what the first pass cited — that is a note about "
                       "provenance, not a refutation of the row."}
    props["reason"] = {"type": "string",
                       "description": "What you attacked and what happened. Name the "
                                      "specific thing that failed or held."}
    props["severity"] = {
        "type": "string", "enum": ["high", "medium", "low"],
        "description": "high: would change a prerequisite status, a matrix cell or a "
                       "pillar band. medium: changes a level or a tier. low: provenance "
                       "polish."}
    return {"type": "object", "properties": props,
            "required": CELL_SCHEMA["required"] + ["verdict", "refutation_kind",
                                                   "reason", "severity"],
            "additionalProperties": False}


G2_SCHEMA = _g2_schema()

G2_SYSTEM = SYSTEM + """

YOU ARE NOW THE SECOND REVIEWER, NOT THE ASSESSOR.

Another researcher has already recorded this row. Your job is to REFUTE it. Default to
skepticism: assume the recorded row is wrong and try to show it. Every rule above still
binds you — you may not assert anything you cannot quote from a supplied page, and a
figure measuring a different construct is still not an answer.

Three things you are looking for, in order of how much they matter:

1. Does the cited source actually say what the row claims? A row whose source does not
   support its value is the worst failure in the set, and the only way to find it is to
   read the page rather than the row.

2. Is there evidence the first pass did not reach? Where the row is a gap or a
   withheld level, the useful question is not whether the search was reasonable but
   whether the data exists. Your searches were generated independently of theirs.

3. Is the tier, the class, or the construct judgment wrong in a way that changes the
   level?

One asymmetry you must respect. If your own searching simply did not reach what the
first pass cited, that is NOT a refutation — set verdict "confirmed" and
refutation_kind "could not locate independently". You cannot disprove a quote-verified
citation by failing to find it again. Only an affirmative finding refutes."""


# ------------------------------------------------------------------ scope

def in_scope(rows):
    """Prerequisites, holds and gaps — where being wrong costs the most (C5)."""
    core = {k: v for k, v in rows.items() if not k.startswith("A1-CAND-")}
    prereq = {i for i in MODEL if MODEL[i]["prereq"]}
    gaps = {i for i, r in core.items() if r["cls"] == "Gap"}
    holds = {i for i, r in core.items() if r["level"] is None and r["cls"] != "Gap"}
    return prereq | gaps | holds, prereq, gaps, holds


def role_of(iid, prereq, gaps, holds):
    if iid in prereq:
        return "prerequisite"
    if iid in gaps:
        return "gap"
    return "hold"


ROLE_BRIEF = {
    "prerequisite":
        "THIS ROW IS A PREREQUISITE. It gates whole columns of the readiness matrix, so "
        "it gets a full adversarial review whatever the first pass concluded. A "
        "one-level error here moves six columns. Re-establish its factual basis from "
        "your own sources, and hold it to T1-T3 quote-verified evidence.",
    "gap":
        "THE FIRST PASS FOUND NOTHING HERE. You are the gap refuter. The question is not "
        "whether their search was reasonable — it is whether the data exists at all. Try "
        "the phrasings they did not, the national statistical office rather than the "
        "international database, the sector survey rather than the headline series. A "
        "gap you cannot fill after a genuine tier-ordered attempt is confirmed, and "
        "saying so is a real result. T5 never fills a gap.",
    "hold":
        "THE FIRST PASS WITHHELD THE LEVEL HERE and gave a reason. Attack the reason. "
        "Either it was right — the evidence really does measure a different construct, "
        "or really is inadmissible — or there is evidence that does measure the named "
        "construct and they did not reach it. Both answers are useful; the useless one "
        "is repeating their reasoning back.",
}


def first_pass_brief(iid, row, record):
    """What the first pass concluded, and why. Shown for the verdict, never for the search."""
    ans = (record or {}).get("answer", {}) or {}
    gate = next((g for g in (record or {}).get("gates", [])
                 if g["verdict"] in ("hold", "reject")), None)
    L = [f"WHAT THE FIRST PASS RECORDED FOR {iid}:",
         f"  evidence class: {row['cls']}",
         f"  level: {'withheld' if row['level'] is None else row['level']}",
         f"  value: {str(row['value'])[:600]}",
         f"  source: {row.get('src', '') or '(none)'}",
         f"  source URL: {row.get('url', '') or '(none)'}",
         f"  tier: {row.get('tier', '') or '(none)'}"]
    if gate:
        L.append(f"  withheld by the '{gate['gate']}' rule: {gate['reason']}")
    if ans.get("search_trail"):
        L.append(f"  where they looked: {ans['search_trail'][:900]}")
    if ans.get("negative_finding"):
        L.append(f"  why they did not go higher: {ans['negative_finding'][:500]}")
    if ans.get("construct_note"):
        L.append(f"  on the construct: {ans['construct_note'][:500]}")
    return "\n".join(L)


# ------------------------------------------------------------------ one row

def review_row(spec, row, record, country, llm, ledger, prereq, gaps, holds, log):
    role = role_of(spec["id"], prereq, gaps, holds)

    # Retrieval is independent: R.retrieve plans its queries from the construct alone and
    # has no sight of the first pass's sources. That independence is the whole point.
    pack, plan, ppx, construct = R.retrieve(spec, country, llm, ledger, log,
                                            pass_name=PASS)

    extra = "\n\n".join([ROLE_BRIEF[role], first_pass_brief(spec["id"], row, record)])
    user = R.cell_prompt(country, spec["id"], spec["name"], construct,
                         R.scoring_text(spec), pack, extra)
    ans = llm.json_call(G2_SYSTEM, user, G2_SCHEMA, PASS, max_tokens=6000,
                        detail=f"g2 {spec['id']}")

    by_url = {p["url"]: p for p in pack}
    cited = (ans.get("source_url") or "").split("#")[0]
    page = by_url.get(cited)
    quote_ok = V.quote_verify(ans.get("quote", ""), page["text"]) if page else False
    is_ladder = spec["method"] == "ladder" and not spec["candidate"]
    ladder_derived = R.ladder_level(ans.get("presence_rung"), ans.get("quality_evidence"),
                                    ans.get("scale_evidence"))[0] if is_ladder else None
    gate_list = G.run_gates(ans, country=country, indicator_id=spec["id"],
                            is_prerequisite=bool(spec["prerequisite"]),
                            quote_ok=quote_ok,
                            quote_page_tier=(page or {}).get("tier", ""),
                            cited_url=cited, page_urls=set(by_url),
                            derived_level=ladder_derived, is_ladder=is_ladder,
                            assessment_year=R.ASSESSMENT_YEAR)
    verdict, gate = G.verdict_of(gate_list)
    asserted = bool(ans.get("found")) and ans.get("value_kind") in ("number", "statement") \
        and str(ans.get("value", "")).strip() != ""
    if verdict == "pass" and not asserted:
        verdict = "gap"

    finding = dict(id=spec["id"], name=spec["name"], role=role,
                   verdict=ans.get("verdict", "confirmed"),
                   refutation_kind=ans.get("refutation_kind", ""),
                   reason=ans.get("reason", ""), severity=ans.get("severity", "low"),
                   gate_verdict=verdict, gate_reason=(gate.reason if gate else ""),
                   gates=[g.as_dict() for g in gate_list],
                   quote_verified=quote_ok, answer=ans,
                   queries=plan.get("queries", []),
                   pack=[{k: v for k, v in p.items() if k != "text"} for p in pack])
    finding["proposed_row"] = R.row_from(spec, ans, verdict, gate, pack, "", country)
    finding["outcome"], finding["applied_row"] = decide(spec, row, finding)
    return finding


def decide(spec, row, f):
    """What Gate 2's finding does to the row. Returns (outcome, replacement or None).

    Four outcomes, and the conservative one is the default:

      upheld          the row stands. Either Gate 2 confirmed it, or its own attempt did
                      not clear the gates, or it simply could not find the evidence
                      again — none of which disproves a quote-verified row.
      filled          a gap or a withheld level is replaced by evidence that cleared
                      every gate. This is Gate 2 earning its keep.
      withdrawn       Gate 2 showed affirmatively that the cited source does not support
                      the recorded value, or measures a different construct. The level
                      goes; the evidence stays, with the reason recorded.
      adjusted        the substance stands but the provenance changes.
    """
    verdict = (f["verdict"] or "confirmed").lower()
    kind = f["refutation_kind"] or ""
    cleared = f["gate_verdict"] == "pass"
    row_has_level = row["level"] is not None

    # Failing to find it again is never a refutation.
    if kind == "could not locate independently":
        return "upheld", None

    if verdict == "confirmed":
        return "upheld", None

    # An affirmative refutation of the row's own basis withdraws the level. This is the
    # only path that can lower a row, so it carries the heaviest evidence requirement:
    # the reviewer must have quote-verified something it actually read.
    #
    # Without that, the asymmetry above is enforced by the reviewer's own labelling
    # rather than by evidence — and the reviewer is the thing being checked. Both
    # countries' 7.12 withdrawals came from a reviewer that asserted no value, produced
    # no quote and verified nothing: an absence, filed under "source does not support
    # the value" instead of "could not locate independently". An absence cannot refute a
    # quote-verified citation whatever it is called.
    #
    # The legitimate case survives. A reviewer that reads a page and finds it does not
    # say what the row claims can quote the text it read, and that quote verifies. What
    # is excluded is a withdrawal resting on nothing.
    if verdict == "refuted" and kind in ("source does not support the value",
                                         "construct mismatch") and row_has_level:
        if not f.get("quote_verified"):
            return "upheld", None
        out = dict(row, level=None)
        out["note"] = (f"RATIFICATION HOLD — withdrawn on second review: {f['reason']} "
                       f"The level is withheld and this row leaves every mean. "
                       + (row.get("note") or "")).strip()
        return "withdrawn", out

    # Anything that proposes new evidence must have cleared the gates to be written.
    if not cleared:
        return "upheld", None

    proposed = f["proposed_row"]
    if proposed["cls"] == "Gap":
        return "upheld", None
    if not row_has_level and proposed["level"] is not None:
        out = dict(proposed)
        out["note"] = (f"Recorded on second review, which located evidence the first "
                       f"pass did not reach. {f['reason']} " + (proposed.get("note") or "")).strip()
        for k in ("defnote", "defsev"):
            if k in row:
                out[k] = row[k]
        return "filled", out
    if verdict in ("adjust", "refuted"):
        # The schema defines 'adjust' as right substance with the wrong tier, class,
        # level or vintage — so an adjustment that changes the level has to change the
        # level. Copying only the provenance and silently keeping the old level, which
        # is what this did at first, made the verdict mean less than it says: on 5.5 the
        # reviewer argued the rung was understated and the row kept its old one anyway.
        #
        # The protection is that the proposal has already cleared every gate, including
        # quote verification, the construct rule, the T1-T3 prerequisite bar and the
        # requirement that a level below 5 carry its negative finding. A level that has
        # cleared all of those from an independent vendor is as well-founded as the one
        # it replaces. Levels Gate 2 raised are listed separately in the report, because
        # raising a level is the direction that needs a reader.
        if proposed.get("level") is not None and proposed["level"] != row["level"]:
            out = dict(proposed)
            out["note"] = (f"Level {row['level']} to {proposed['level']} on second "
                           f"review: {f['reason']} " + (proposed.get("note") or "")).strip()
            for k in ("defnote", "defsev"):
                if k in row:
                    out[k] = row[k]
            return "relevelled", out
        out = dict(row)
        for k in ("src", "url", "tier", "tier_detail", "year"):
            if proposed.get(k):
                out[k] = proposed[k]
        out["note"] = (f"Provenance adjusted on second review: {f['reason']} "
                       + (row.get("note") or "")).strip()
        return "adjusted", out
    return "upheld", None


# ------------------------------------------------------------------ report

def write_report(path, country, run, findings, counts, summ, scope_n, vendor):
    L = []
    w = L.append
    by = lambda o: [f for f in findings if f["outcome"] == o]
    w(f"# Gate 2 — second review of {run} ({country})\n")
    w(f"An independent vendor (`{vendor}`) attacked the first pass on the "
      f"**{scope_n} rows** where being wrong costs the most: the twelve prerequisites, "
      f"every ratification hold and every recorded gap. It planned its own searches from "
      f"the construct and never saw the first pass's sources while searching; it saw the "
      f"recorded row only when forming its verdict. Its proposals entered through the "
      f"same gates as any other evidence.\n")
    if summ:
        w(f"**${summ.get('total', 0):.2f}** across {summ.get('calls', 0)} vendor calls in "
          f"{summ.get('elapsed_s', 0) / 60:.0f} minutes.\n")

    w("\n## What it changed\n")
    w("| outcome | rows | |")
    w("|---|---|---|")
    w(f"| **filled** | {len(by('filled'))} | a gap or withheld level replaced by evidence that cleared every gate |")
    w(f"| **withdrawn** | {len(by('withdrawn'))} | a level removed: the cited source was shown not to support it |")
    w(f"| **relevelled** | {len(by('relevelled'))} | the level changed: a second reading of better evidence, cleared through every gate |")
    w(f"| **adjusted** | {len(by('adjusted'))} | substance and level stand, provenance corrected |")
    w(f"| **upheld** | {len(by('upheld'))} | the row survived the attack |")

    w("\n## Verdicts as the reviewer gave them\n")
    w("| verdict | rows |")
    w("|---|---|")
    for k, v in sorted(counts["verdict"].items(), key=lambda kv: -kv[1]):
        w(f"| {k} | {v} |")
    w("\nA reviewer verdict is not the same thing as a change to the row. A refutation "
      "that proposes evidence still has to clear quote verification, the tier rule, the "
      "construct rule and — on a prerequisite — the T1–T3 bar, exactly as the first pass "
      "did. Where the two columns disagree, the gates are why.\n")

    for outcome, heading, blurb in (
        ("filled", "Rows Gate 2 filled",
         "Evidence the first pass did not reach, which then cleared every gate. This is "
         "the measure of what a second independent search buys."),
        ("withdrawn", "Levels Gate 2 withdrew",
         "An affirmative finding that the cited source does not support the value, or "
         "measures a different construct. The evidence stays on the row; the level goes."),
        ("relevelled", "Levels Gate 2 changed",
         "The row kept its evidence and changed its level, on a proposal that cleared "
         "quote verification, the construct rule, the prerequisite bar and the "
         "requirement to carry a negative finding. Read the ones that went UP first — "
         "raising a level is the direction that claims readiness."),
        ("adjusted", "Provenance Gate 2 corrected",
         "The substance and the level survived; the source, tier or vintage did not.")):
        rows_ = by(outcome)
        if not rows_:
            continue
        w(f"\n## {heading}\n")
        w(blurb + "\n")
        for f in sorted(rows_, key=lambda f: R_id_key(f["id"])):
            a = f["applied_row"] or {}
            w(f"\n**{f['id']} {f['name']}** · {f['role']} · severity {f['severity']}\n")
            w(f"- {f['reason']}")
            if outcome in ("filled", "relevelled"):
                w(f"- now: {a.get('cls')} at level {a.get('level')}, "
                  f"{a.get('tier') or 'untiered'} — {(a.get('src') or '')[:140]}")
                w(f"- {(a.get('url') or '')[:160]}")

    w("\n## Every row reviewed\n")
    w("| id | role | reviewer verdict | outcome | what it found |")
    w("|---|---|---|---|---|")
    for f in sorted(findings, key=lambda f: R_id_key(f["id"])):
        mark = "" if f["outcome"] == "upheld" else "**"
        reason = (f["reason"] or "")[:110]
        w(f"| {f['id']} | {f['role']} | {f['verdict']}"
          f"{' · ' + f['refutation_kind'] if f['refutation_kind'] else ''} | "
          f"{mark}{f['outcome']}{mark} | {reason} |")

    w("\n## Reading this\n")
    w("Gate 2 is scoped to the rows the first pass was least sure of, so a high upheld "
      "count is not a null result — it is the first pass's abstentions being confirmed "
      "as real by an independent searcher, which is exactly what makes a recorded gap "
      "trustworthy. The figure that decides whether Gate 2 earns its share of the budget "
      "is **filled** plus **withdrawn**: rows where a second opinion changed what the "
      "assessment says.\n")
    open(path, "w").write("\n".join(L) + "\n")


def R_id_key(i):
    parts = str(i).split(".")
    try:
        return (0, int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, "")
    except ValueError:
        return (1, 0, 0, str(i))


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--run", required=True, help="basename of the first pass, e.g. EGY_shadow")
    ap.add_argument("--vendor", default="openai/gpt-5.6-terra")
    ap.add_argument("--ceiling", type=float, default=500.0)
    ap.add_argument("--rows", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--reapply", action="store_true",
                    help="recompute what each saved finding does to its row, and rewrite "
                         "the outputs, without making a single vendor call. The findings "
                         "carry the reviewer's answer, its gate results and its proposed "
                         "row, so a corrected decision rule applies to the review already "
                         "paid for rather than occasioning another one.")
    args = ap.parse_args()

    V.load_env()
    rows = json.load(open(os.path.join(LOOP1, f"{args.run}_input.json")))
    rec_path = os.path.join(LOOP1, f"{args.run}_research.json")
    records = json.load(open(rec_path)) if os.path.exists(rec_path) else {}

    scope, prereq, gaps, holds = in_scope(rows)
    specs = {s["id"]: s for s in R.build_specs(json.load(open(R.MODEL_FILE)))}
    todo_ids = sorted(scope, key=R_id_key)
    if args.rows:
        want = {r.strip() for r in args.rows.split(",")}
        todo_ids = [i for i in todo_ids if i in want]

    vendor, _, mname = args.vendor.partition("/")
    ledger = V.Ledger(ceiling=args.ceiling, label=f"{args.run}_g2")
    llm = V.LLM(vendor, ledger, model=mname or None)

    state_path = os.path.join(LOOP1, f"{args.run}_g2_state.json")
    spend_path = os.path.join(LOOP1, f"{args.run}_g2_spend.json")
    ledger.attach(spend_path)
    # A paid review can be journalled before its finding reaches the state file. Resume
    # the spend checkpoint even when no finding checkpoint survived that attempt.
    carried = ledger.load(spend_path) if args.resume else 0
    state = {"findings": {}}
    loaded_state = False
    if args.resume and os.path.exists(state_path):
        state = json.load(open(state_path))
        loaded_state = True
    WI.bind_checkpoint_state(state, loaded=loaded_state)
    if loaded_state:
        print(f"resuming — {len(state['findings'])} rows already reviewed, "
              f"{carried} earlier vendor calls carried (${ledger.spent():.2f} spent)")
    elif args.resume and carried:
        print(f"resuming — no completed finding checkpoint yet; {carried} earlier "
              f"vendor calls carried (${ledger.spent():.2f} spent)")

    if args.reapply:
        findings = json.load(open(os.path.join(LOOP1, f"{args.run}_g2_findings.json")))
        for f in findings:
            spec = specs[f["id"]]
            f["outcome"], f["applied_row"] = decide(spec, rows[f["id"]], f)
            state["findings"][f["id"]] = f
        V.atomic_write_json(state_path, state)
        print(f"reapplied the decision rule to {len(findings)} saved findings — "
              "no vendor calls")
        return finish(args, rows, findings, ledger, scope, f"{vendor}/{llm.model}",
                      prior_spend=json.load(open(
                          os.path.join(LOOP1, f"{args.run}_g2_spend.json"))).get("summary"))

    print(f"Gate 2 on {args.run} · reviewer {vendor}/{llm.model}")
    print(f"scope: {len(scope)} of 57 rows — {len(prereq)} prerequisites, "
          f"{len(gaps)} gaps, {len(holds)} holds ({len(prereq & (gaps | holds))} overlap)")
    print(f"budget ${args.ceiling:.0f}, Gate 2 allocation ${ledger.cap(PASS):.0f} "
          f"(decision G3)\n")

    lock = threading.Lock()
    stopped = None

    def log(m):
        print(m, flush=True)

    def work(iid):
        nonlocal stopped
        if stopped or iid in state["findings"]:
            return
        t0 = time.time()
        try:
            f = review_row(specs[iid], rows[iid], records.get(iid), args.country,
                           llm, ledger, prereq, gaps, holds, log)
        except V.BudgetExhausted as e:
            with lock:
                stopped = str(e)
            return
        except Exception as e:
            log(f"  ! {iid} failed: {type(e).__name__}: {str(e)[:160]}")
            return
        with lock:
            state["findings"][iid] = f
            V.atomic_write_json(state_path, state)
            ledger.save(os.path.join(LOOP1, f"{args.run}_g2_spend.json"))
            n = len(state["findings"])
        mark = {"upheld": "  ", "filled": "F ", "withdrawn": "W ", "adjusted": "A ",
            "relevelled": "L "}[f["outcome"]]
        log(f"{mark}[{n:2}/{len(todo_ids)}] {iid:12} {f['role']:12} {f['verdict']:9} "
            f"-> {f['outcome']:10} ${ledger.spent(PASS):6.2f} {time.time() - t0:4.0f}s")

    with ThreadPoolExecutor(max_workers=R.ROW_WORKERS) as ex:
        list(ex.map(work, todo_ids))

    if stopped:
        print(f"\n!! {stopped}")
        print("   Rows never reviewed are absent from the findings, NOT recorded as "
              "upheld — an unreviewed row must not read like one that survived review.")

    missing = sorted(set(todo_ids) - set(state["findings"]), key=R_id_key)
    if stopped or missing:
        # A partial challenge is valuable checkpoint data, but it is not a completed
        # automated challenge and must not produce a `_g2_input.json` whose filename
        # would authorize downstream stages. The canonical coordinator may retry; if it
        # still cannot finish, the workflow fails terminally rather than awaiting a
        # person or relabelling unreviewed rows as upheld.
        V.atomic_write_json(state_path, state)
        ledger.save(spend_path)
        if missing:
            print(f"!! automated challenge incomplete — {len(missing)} rows remain: "
                  f"{', '.join(missing[:12])}")
        return 1

    return finish(args, rows, list(state["findings"].values()), ledger, scope,
                  f"{vendor}/{llm.model}")


def finish(args, rows, findings, ledger, scope, vendor_label, prior_spend=None):
    """Write the corrected input, the findings and the report. Shared with --reapply."""
    counts = {"verdict": {}, "outcome": {}}
    for f in findings:
        counts["verdict"][f["verdict"]] = counts["verdict"].get(f["verdict"], 0) + 1
        counts["outcome"][f["outcome"]] = counts["outcome"].get(f["outcome"], 0) + 1

    corrected = {k: dict(v) for k, v in rows.items()}
    for f in findings:
        if f["applied_row"]:
            corrected[f["id"]] = f["applied_row"]

    out_input = os.path.join(LOOP1, f"{args.run}_g2_input.json")
    json.dump(corrected, open(out_input, "w"), indent=1, default=str)
    json.dump(findings, open(os.path.join(LOOP1, f"{args.run}_g2_findings.json"), "w"),
              indent=1, default=str)
    summ = prior_spend or ledger.summary()
    if not prior_spend:
        ledger.save(os.path.join(LOOP1, f"{args.run}_g2_spend.json"))
    write_report(os.path.join(LOOP1, f"G2-REPORT-{args.run}.md"), args.country, args.run,
                 findings, counts, summ, len(scope), vendor_label)

    print(f"\nreviewed {len(findings)} rows · "
          + " · ".join(f"{k} {v}" for k, v in sorted(counts["outcome"].items())))
    print(f"spend ${summ.get('total', 0):.2f} of ${ledger.cap(PASS):.0f} allocated "
          f"in {summ.get('elapsed_s', 0) / 60:.0f} minutes")
    print(f"wrote {os.path.basename(out_input)} and G2-REPORT-{args.run}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
