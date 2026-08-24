#!/usr/bin/env python3
"""The acceptance test: an automated shadow run against the verified assessment.

Reads a shadow assessment and the verified one, and answers the five questions the
handoff sets, row by row. It never writes to either input — the verified Egypt and
Nigeria assessments are the test oracle, and an oracle a test can edit is not an
oracle.

Divergence is the expected result, not the failure condition. The verified assessments
came from sustained human-directed searching under the full tiered protocol, and this
pass runs without Gate 2. What the report is for is the *measured* delta, because that
is what calibrates the abstention threshold — the highest-leverage parameter in the
system, and the only thing standing between machine-set levels and a machine-set
readiness matrix.

Usage:
    python3 compare_shadow.py --shadow EGY_shadow --oracle EGY_v17 --country Egypt
"""

import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, LOOP1)
from engine_v17 import MODEL

PREREQ = [i for i in MODEL if MODEL[i]["prereq"]]


def load(name):
    return json.load(open(os.path.join(LOOP1, f"{name}.json")))


def lineage_spend(name):
    """Every pass that went into this assessment, summed.

    A Gate 2 assessment is the first pass plus the second review, and reporting only
    the second review's ledger would price the deliverable at a third of what it cost.
    The passes are separate files because decision G3 allocates them separately; the
    total is what a reader wants.
    """
    base = name[:-3] if name.endswith("_g2") else name
    parts, seen = [], []
    for stem in (f"{base}_spend.json", f"{base}_g2_spend.json"):
        p = os.path.join(LOOP1, stem)
        if not os.path.exists(p) or (name == base and stem.endswith("_g2_spend.json")):
            continue
        j = json.load(open(p)).get("summary", {})
        parts.append(j)
        seen.append(stem.replace("_spend.json", ""))
    if not parts:
        return {}
    out = dict(total=round(sum(p.get("total", 0) for p in parts), 4),
               calls=sum(p.get("calls", 0) for p in parts),
               elapsed_s=sum(p.get("elapsed_s", 0) for p in parts),
               ceiling=max((p.get("ceiling", 0) for p in parts), default=0),
               passes=seen)
    by = {}
    for p in parts:
        for k, v in (p.get("by_vendor") or {}).items():
            by[k] = round(by.get(k, 0) + v, 4)
    out["by_vendor"] = by
    return {"summary": out}


def fmt_level(v):
    return "no level" if v is None else f"L{v}"


def id_key(i):
    """Sort indicator ids the way a reader reads them: 6.3 before 6.13."""
    parts = str(i).split(".")
    try:
        return (0, int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, "")
    except ValueError:
        return (1, 0, 0, str(i))


def ids(seq):
    return ", ".join(sorted(seq, key=id_key)) or "—"


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def fmt_value(v, n=40):
    s = str(v)
    return (s[: n - 1] + "…") if len(s) > n else s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shadow", required=True)
    ap.add_argument("--oracle", required=True)
    ap.add_argument("--country", required=True)
    ap.add_argument("--prior", default="",
                    help="basename of an earlier independent run of the SAME country, "
                         "to measure run-to-run variance. Every figure in this report "
                         "carries that variance, and a reader who cannot see it will "
                         "read a one-row difference as a finding.")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    sh, orc = load(args.shadow), load(args.oracle)
    research = {}
    p = os.path.join(LOOP1, f"{args.shadow}_research.json")
    if os.path.exists(p):
        research.update(json.load(open(p)))
    if not research:  # a Gate 2 assessment carries the first pass's research records
        base = args.shadow[:-3] if args.shadow.endswith("_g2") else args.shadow
        p = os.path.join(LOOP1, f"{base}_research.json")
        if os.path.exists(p):
            research.update(json.load(open(p)))
    spend = lineage_spend(args.shadow)

    S, O = sh["indicators"], orc["indicators"]
    row_ids = list(MODEL.keys())

    # ---------------------------------------------------------------- rows
    rows = []
    for i in row_ids:
        s, o = S[i], O[i]
        rec = research.get(i, {})
        rows.append(dict(
            id=i, name=MODEL[i]["name"], prereq=MODEL[i]["prereq"],
            o_cls=o["cls"], o_level=o["level"], o_value=o["value"], o_tier=o.get("tier", ""),
            s_cls=s["cls"], s_level=s["level"], s_value=s["value"], s_tier=s.get("tier", ""),
            level_match=(s["level"] == o["level"]),
            both_levelled=(s["level"] is not None and o["level"] is not None),
            cls_match=(s["cls"] == o["cls"]),
            verdict=rec.get("verdict", ""),
            gate=next((g["reason"] for g in rec.get("gates", [])
                       if g["verdict"] in ("hold", "reject")), ""),
            quote_verified=rec.get("quote_verified"),
            # Why the shadow row is what it is, in one phrase. A gated row gives its
            # gate's reason; a gap gives its search trail; a row that simply landed
            # elsewhere gives what it recorded. Leaving the column blank on a
            # divergence — which the first draft did for every gap — tells the reader
            # that a difference exists and nothing whatever about it.
            why=(next((g["reason"] for g in rec.get("gates", [])
                       if g["verdict"] in ("hold", "reject")), "")
                 or (str(s["value"]).replace("DATA GAP — ", "")
                     if s["cls"] == "Gap" else str(s["value"]))),
        ))
    by_id = {r["id"]: r for r in rows}

    n = len(rows)
    level_same = sum(1 for r in rows if r["level_match"])
    both = [r for r in rows if r["both_levelled"]]
    both_same = sum(1 for r in both if r["level_match"])
    within_one = sum(1 for r in both if abs(r["s_level"] - r["o_level"]) <= 1)

    # ---------------------------------------------------------------- gaps and holds
    o_gaps = {r["id"] for r in rows if r["o_cls"] == "Gap"}
    s_gaps = {r["id"] for r in rows if r["s_cls"] == "Gap"}
    o_holds = {r["id"] for r in rows if r["o_level"] is None and r["o_cls"] != "Gap"}
    s_holds = {r["id"] for r in rows if r["s_level"] is None and r["s_cls"] != "Gap"}

    # ---------------------------------------------------------------- prerequisites
    pre = []
    for i in PREREQ:
        pre.append(dict(id=i, name=MODEL[i]["name"], kind=MODEL[i]["prereq"],
                        o=orc["prereq"][i]["status"], s=sh["prereq"][i]["status"],
                        match=orc["prereq"][i]["status"] == sh["prereq"][i]["status"],
                        o_level=O[i]["level"], s_level=S[i]["level"],
                        gate=by_id[i]["gate"], why=by_id[i]["why"],
                        verdict=by_id[i]["verdict"]))
    pre_match = sum(1 for p in pre if p["match"])

    # ---------------------------------------------------------------- verdict 2.1
    q4 = None
    if "2.1" in by_id:
        r = by_id["2.1"]
        rec = research.get("2.1", {})
        ans = rec.get("answer", {})
        text = " ".join(str(x) for x in (r["s_value"], ans.get("construct_note", ""),
                                         ans.get("abstain_reason", "")))
        national_present = any(k in text for k in ("99.8", "99,8", "national"))
        recorded_national = (r["s_cls"] == "Measured" and r["s_level"] is not None
                             and isinstance(r["s_value"], (int, float))
                             and float(r["s_value"]) > 90)
        q4 = dict(
            reproduced=(r["s_level"] is None and not recorded_national),
            repeated_defect=recorded_national,
            shadow_cls=r["s_cls"], shadow_level=r["s_level"], shadow_value=r["s_value"],
            verdict=r["verdict"], gate=r["gate"],
            names_national_as_context=national_present,
            construct_match=ans.get("construct_match", ""),
            construct_note=ans.get("construct_note", ""),
            abstain_reason=ans.get("abstain_reason", ""))

    # ---------------------------------------------------------------- aggregates
    pillars = []
    for p, od in orc["pillars"].items():
        sd = sh["pillars"][p]
        pillars.append(dict(pillar=p, o_mean=od["mean"], o_band=od["band"],
                            o_rated=od["rated"], o_held=od["held"],
                            s_mean=sd["mean"], s_band=sd["band"],
                            s_rated=sd["rated"], s_held=sd["held"],
                            band_match=od["band"] == sd["band"]))
    matrix = []
    for uc, od in orc["matrix"].items():
        sd = sh["matrix"][uc]
        matrix.append(dict(uc=uc, o=od["status"], s=sd["status"],
                           match=od["status"] == sd["status"],
                           o_why=od["why"], s_why=sd["why"]))

    # ---------------------------------------------------------------- gates fired
    gate_counts = {}
    for i, rec in research.items():
        for g in rec.get("gates", []):
            if g["verdict"] in ("hold", "reject"):
                k = f"{g['gate']} ({g['verdict']})"
                gate_counts[k] = gate_counts.get(k, 0) + 1

    corrob = [rec for rec in research.values() if rec.get("wdi_corroboration")]
    corrob_ok = sum(1 for rec in corrob
                    if "Corroborated" in (rec.get("row", {}).get("note") or ""))

    summ = spend.get("summary", {}) if isinstance(spend, dict) else {}
    passes = summ.get("passes") or []

    # ---------------------------------------------------------------- variance
    variance = None
    prior_path = os.path.join(LOOP1, f"{args.prior}_input.json") if args.prior else ""
    if prior_path and os.path.exists(prior_path):
        prior = json.load(open(prior_path))
        this_in = json.load(open(os.path.join(LOOP1, f"{args.shadow}_input.json")))
        shared = [i for i in row_ids if i in prior and i in this_in]
        moved = [dict(id=i,
                      a_cls=prior[i]["cls"], a_level=prior[i]["level"],
                      b_cls=this_in[i]["cls"], b_level=this_in[i]["level"])
                 for i in shared
                 if prior[i]["level"] != this_in[i]["level"]
                 or prior[i]["cls"] != this_in[i]["cls"]]
        variance = dict(prior=args.prior, n=len(shared), moved=moved,
                        same_level=sum(1 for i in shared
                                       if prior[i]["level"] == this_in[i]["level"]))

    # ---------------------------------------------------------------- report
    L = []
    w = L.append
    w(f"# Shadow run against the verified assessment — {args.country}\n")
    w(f"`{args.shadow}` compared row by row with `{args.oracle}`, the verified "
      f"assessment. The verified assessment was not read by the pipeline and has not "
      f"been modified by this comparison.\n")

    w("\n## The five questions\n")
    w(f"**1. How many of the 57 rows land on the same level?** "
      f"**{level_same} of {n}** ({100.0 * level_same / n:.0f}%). "
      f"Of the {len(both)} rows where both assessments set a level at all, "
      f"{both_same} agree exactly ({100.0 * both_same / max(len(both), 1):.0f}%) and "
      f"{within_one} are within one level "
      f"({100.0 * within_one / max(len(both), 1):.0f}%).\n")
    w(f"**2. Do all twelve prerequisites match?** "
      f"**{pre_match} of 12** carry the same status. "
      + ("All twelve match.\n" if pre_match == 12 else
         "The divergences are listed below; each one moves at least one column of the "
         "readiness matrix.\n"))
    w(f"**3. Gaps.** The verified assessment records **{len(o_gaps)}** "
      f"({ids(o_gaps)}). The shadow run records **{len(s_gaps)}**, "
      f"of which it found **{len(o_gaps & s_gaps)}** of the recorded ones and raised "
      f"**{len(s_gaps - o_gaps)}** the verified assessment does not carry. It also set "
      f"**{len(s_holds)}** ratification holds against the verified assessment's "
      f"{len(o_holds)}.\n")
    if q4:
        w(f"**4. The 2.1 finding.** "
          + ("**Reproduced.** " if q4["reproduced"] else
             "**NOT reproduced — the original defect was repeated.** "
             if q4["repeated_defect"] else "**Diverged.** ")
          + f"The shadow run recorded 2.1 as `{q4['shadow_cls']}` with "
            f"{fmt_level(q4['shadow_level'])}; gate verdict `{q4['verdict']}`. ")
        if q4["gate"]:
            w(f"  \n  Reason given: *{q4['gate']}*\n")
        if q4["construct_note"]:
            w(f"  \n  On the construct: *{fmt_value(q4['construct_note'], 400)}*\n")
        w(f"  \n  Recorded value: `{fmt_value(q4['shadow_value'], 300)}`\n")
    if summ:
        w(f"\n**5. Cost and time.** **${summ.get('total', 0):.2f}** across "
          f"{summ.get('calls', 0)} vendor calls in "
          f"{summ.get('elapsed_s', 0) / 60:.0f} minutes, against a "
          f"${summ.get('ceiling', 0):.0f} country ceiling — "
          f"{100.0 * summ.get('total', 0) / max(summ.get('ceiling', 1), 1):.1f}% of it"
          + (f", across {len(passes)} passes ({', '.join(passes)})" if len(passes) > 1 else "")
          + f". By vendor: "
          + ", ".join(f"{k} ${v:.2f}" for k, v in
                      sorted(summ.get("by_vendor", {}).items(), key=lambda kv: -kv[1]))
          + ".\n")

    w("\n## Prerequisites — the twelve rows that gate the matrix\n")
    w("| id | prerequisite | verified | shadow | levels | why the shadow run differs |")
    w("|---|---|---|---|---|---|")
    for p in pre:
        mark = "" if p["match"] else "**"
        w(f"| {p['id']} | {MODEL[p['id']]['name'][:34]} | {p['o']} | "
          f"{mark}{p['s']}{mark} | {fmt_level(p['o_level'])} → {fmt_level(p['s_level'])} | "
          f"{fmt_value(p['why'], 110) if not p['match'] else ''} |")

    w("\n## Readiness matrix\n")
    w("| use case | verified | shadow | |")
    w("|---|---|---|---|")
    for m in matrix:
        w(f"| {m['uc']} | {m['o']} | {m['s']} | {'match' if m['match'] else '**differs**'} |")

    w("\n## Pillars\n")
    w("| pillar | verified mean (band) | rated/held | shadow mean (band) | rated/held |")
    w("|---|---|---|---|---|")
    for p in pillars:
        w(f"| {p['pillar']} | {p['o_mean']} ({p['o_band']}) | {p['o_rated']}/{p['o_held']} "
          f"| {p['s_mean']} ({p['s_band']}) | {p['s_rated']}/{p['s_held']} |")

    w("\n## Which direction the divergences run\n")
    up = [r for r in rows if r["both_levelled"] and r["s_level"] > r["o_level"]]
    down = [r for r in rows if r["both_levelled"] and r["s_level"] < r["o_level"]]
    withheld = [r for r in rows if r["o_level"] is not None and r["s_level"] is None]
    added = [r for r in rows if r["s_level"] is not None and r["o_level"] is None]
    w("This is the part to read first. A shadow run that withholds a level where the "
      "verified assessment set one costs coverage; a shadow run that sets a level "
      "*higher* than the verified assessment is claiming readiness the evidence may not "
      "carry, and that is the failure that matters.\n")
    w(f"- **{plural(len(up), 'row')} read higher** than the verified assessment."
      + ("" if up else " None."))
    for r in up:
        w(f"  - **{r['id']} {r['name']}** — L{r['o_level']} to L{r['s_level']}. "
          f"{fmt_value(r['why'], 200)}")
    w(f"- **{plural(len(down), 'row')} read lower.**"
      + (" " + ", ".join(f"{r['id']} (L{r['o_level']}→L{r['s_level']})" for r in down)
         if down else ""))
    w(f"- **{plural(len(withheld), 'row')} withheld a level** the verified assessment set: "
      f"{ids(r['id'] for r in withheld)}.")
    w(f"- **{plural(len(added), 'row')} set a level** the verified assessment withheld: "
      f"{ids(r['id'] for r in added)}.\n")
    w("The asymmetry between the last two is the abstention threshold, stated as a "
      "number. It is the figure to tune, and tuning it in either direction moves the "
      "first bullet — which is the one that decides whether a machine-set readiness "
      "matrix can be trusted.\n")

    w("\n## Where the shadow run withheld a level\n")
    w("Each gate below is a design decision doing its job. A row that reaches a gate "
      "keeps its evidence; what it loses is the level, and with it its place in every "
      "mean.\n")
    if gate_counts:
        w("| gate | rows |")
        w("|---|---|")
        for k, v in sorted(gate_counts.items(), key=lambda kv: -kv[1]):
            w(f"| {k} | {v} |")
    else:
        w("No gate fired.\n")

    if corrob:
        w(f"\n## Independent corroboration\n")
        w(f"{len(corrob)} rows are also covered by a machine-fetchable T1 series, "
          f"fetched separately and never substituted for the research lane's own answer. "
          f"**{corrob_ok} of {len(corrob)}** research values agree with the independent "
          f"series within 2%.\n")

    if variance:
        v = variance
        w("\n## How much of this is repeatable\n")
        w(f"An earlier independent run of the same country on the same pipeline "
          f"(`{v['prior']}`) agrees with this one on **{v['same_level']} of {v['n']}** "
          f"rows by level "
          f"({100.0 * v['same_level'] / max(v['n'], 1):.0f}%). The vendor plans its own "
          f"searches, so two runs do not retrieve the same pages, and a row whose answer "
          f"sits just at the edge of what the search reaches can land differently. Every "
          f"figure above carries this variance: a difference of one or two rows against "
          f"the verified assessment is inside the noise, and only the larger patterns "
          f"should be read as findings.\n")
        if v["moved"]:
            w("| id | earlier run | this run |")
            w("|---|---|---|")
            for m in sorted(v["moved"], key=lambda m: id_key(m["id"])):
                w(f"| {m['id']} | {m['a_cls']} {fmt_level(m['a_level'])} | "
                  f"{m['b_cls']} {fmt_level(m['b_level'])} |")

    w("\n## Every row\n")
    w("| id | indicator | verified | shadow | | note |")
    w("|---|---|---|---|---|---|")
    for r in rows:
        mark = "match" if r["level_match"] else "**differs**"
        pre_mark = " ⚑" if r["prereq"] else ""
        note = ""
        if not r["level_match"]:
            note = fmt_value(r["why"] or r["verdict"], 100)
        w(f"| {r['id']}{pre_mark} | {r['name'][:36]} | {r['o_cls']} {fmt_level(r['o_level'])} "
          f"| {r['s_cls']} {fmt_level(r['s_level'])} | {mark} | {note} |")

    w("\n⚑ marks a prerequisite.\n")

    w("\n## Reading this\n")
    w("Divergence here is the expected result. The verified assessments came from "
      "sustained human-directed searching under the full tiered protocol — Nigeria went "
      "from 21 recorded gaps to 4 that way — and this pass runs once, on a budget, "
      "without the Gate 2 refutation round that found four of those gap refutations. "
      "More gaps and more holds are the honest output of a first automated pass, not a "
      "regression.\n")
    w("The number to act on is the **abstention rate**: "
      f"{len(s_holds)} holds and {len(s_gaps)} gaps against the verified "
      f"{len(o_holds)} and {len(o_gaps)}. Too loose and everything reads Ready; too "
      "tight and everything reads Unverified. These figures are what that threshold "
      "should be tuned against, and they should be kept — when automated Gate 2 arrives, "
      "re-running this comparison is what tells you whether it earns its 15% of the "
      "budget.\n")

    out = args.out or os.path.join(LOOP1, f"SHADOW-COMPARISON-{args.shadow}.md")
    open(out, "w").write("\n".join(L) + "\n")

    json.dump(dict(rows=rows, prerequisites=pre, pillars=pillars, matrix=matrix,
                   gate_counts=gate_counts, spend=summ,
                   headline=dict(level_same=level_same, n=n,
                                 both_levelled=len(both), both_same=both_same,
                                 within_one=within_one, prereq_match=pre_match,
                                 oracle_gaps=sorted(o_gaps, key=id_key),
                                 shadow_gaps=sorted(s_gaps, key=id_key),
                                 oracle_holds=sorted(o_holds, key=id_key),
                                 shadow_holds=sorted(s_holds, key=id_key)),
                   question_4=q4, variance=variance),
              open(os.path.join(LOOP1, f"{args.shadow}_comparison.json"), "w"),
              indent=1, default=str)

    print(f"levels identical      {level_same}/{n}")
    print(f"both levelled & equal {both_same}/{len(both)}  (within one: {within_one})")
    print(f"prerequisites         {pre_match}/12")
    print(f"gaps  verified {len(o_gaps)} · shadow {len(s_gaps)} "
          f"(found {len(o_gaps & s_gaps)}, new {len(s_gaps - o_gaps)})")
    print(f"holds verified {len(o_holds)} · shadow {len(s_holds)}")
    if q4:
        print(f"2.1 finding           "
              f"{'REPRODUCED' if q4['reproduced'] else 'DEFECT REPEATED' if q4['repeated_defect'] else 'diverged'}")
    if variance:
        print(f"repeatable            {variance['same_level']}/{variance['n']} rows vs {variance['prior']}")
    if summ:
        print(f"spend ${summ.get('total', 0):.2f} in {summ.get('elapsed_s', 0) / 60:.0f} min")
    print(f"\nwrote {os.path.basename(out)}")


if __name__ == "__main__":
    main()
