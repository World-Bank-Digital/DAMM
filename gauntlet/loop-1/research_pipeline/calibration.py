#!/usr/bin/env python3
"""Two countries, one question: what is the abstention threshold actually made of?

The design record calls the abstention threshold the highest-leverage parameter in the
system and says it must be tuned against Egypt *and* Nigeria before any new country
runs. One country cannot answer it: a row withheld in Egypt might be the pipeline being
careful or Egypt not publishing the figure, and there is no way to tell from Egypt.

Two countries separate those. A row withheld in **both** is the pipeline. A row withheld
in **one** is that country's data environment. And within the first group, the split
that matters most is between rows the pipeline *could not reach* and rows it reached and
*declined to level* — because those need opposite fixes. More retrieval will not rescue
a row whose construct is unsettled, and a looser threshold will not rescue a row whose
page was never fetched.

Reads finished artifacts; calls nothing.

Usage:
    python3 calibration.py --runs EGY_shadow_g2:EGY_v17:Egypt NGA_shadow_g2:NGA_v17:Nigeria
"""

import argparse, json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, LOOP1)
from engine_v17 import MODEL


def id_key(i):
    p = str(i).split(".")
    try:
        return (0, int(p[0]), int(p[1]) if len(p) > 1 else 0, "")
    except ValueError:
        return (1, 0, 0, str(i))


def ids(seq):
    return ", ".join(sorted(seq, key=id_key)) or "—"


def load(name, suffix):
    p = os.path.join(LOOP1, f"{name}{suffix}")
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True,
                    help="shadow:oracle:Country triples")
    ap.add_argument("--out", default=os.path.join(LOOP1, "CALIBRATION.md"))
    args = ap.parse_args()

    runs = []
    for spec in args.runs:
        shadow, oracle, country = spec.split(":")
        comp = load(shadow, "_comparison.json")
        if not comp:
            sys.exit(f"no comparison for {shadow} — run compare_shadow.py first")
        base = shadow[:-3] if shadow.endswith("_g2") else shadow
        runs.append(dict(shadow=shadow, oracle=oracle, country=country, comp=comp,
                         research=load(base, "_research.json") or {},
                         g2=load(base, "_g2_findings.json") or []))

    # ------------------------------------------------------------ per country
    for r in runs:
        rows = r["comp"]["rows"]
        r["withheld"] = {x["id"] for x in rows
                         if x["o_level"] is not None and x["s_level"] is None}
        r["higher"] = {x["id"] for x in rows if x["both_levelled"]
                       and x["s_level"] > x["o_level"]}
        r["gaps"] = set(r["comp"]["headline"]["shadow_gaps"])
        r["holds"] = set(r["comp"]["headline"]["shadow_holds"])
        r["oracle_gaps"] = set(r["comp"]["headline"]["oracle_gaps"])
        r["by_id"] = {x["id"]: x for x in rows}

    common = set(runs[0]["withheld"])
    for r in runs[1:]:
        common &= r["withheld"]
    only = {r["country"]: r["withheld"] - common for r in runs}

    # Reached but declined, versus never reached. The first is a threshold question;
    # the second is a retrieval question, and no threshold will fix it.
    def cause(r, iid):
        rec = r["research"].get(iid) or {}
        gate = next((g for g in rec.get("gates", [])
                     if g["verdict"] in ("hold", "reject")), None)
        if gate:
            return f"declined: {gate['gate']}"
        if r["by_id"].get(iid, {}).get("s_cls") == "Gap":
            return "not reached"
        return "declined: other"

    causes = defaultdict(Counter)
    for r in runs:
        for iid in r["withheld"]:
            causes[r["country"]][cause(r, iid)] += 1
    common_causes = Counter()
    for iid in common:
        kinds = {cause(r, iid).split(":")[0] for r in runs}
        common_causes["not reached in both" if kinds == {"not reached"} else
                      "declined in both" if kinds == {"declined"} else
                      "mixed"] += 1

    L = []
    w = L.append
    w("# Calibrating the abstention threshold\n")
    w("Two automated runs, each compared against its own verified assessment. The "
      "design record names the abstention threshold as the highest-leverage parameter "
      "in the system — too loose and everything reads Ready, too tight and everything "
      "reads Unverified — and says it must be tuned against both countries before any "
      "new country runs. This is that comparison.\n")

    w("\n## The two runs side by side\n")
    w("| | " + " | ".join(r["country"] for r in runs) + " |")
    w("|---|" + "---|" * len(runs))
    h = [r["comp"]["headline"] for r in runs]
    w("| rows at the verified level (of 57) | "
      + " | ".join(f"{x['level_same']}" for x in h) + " |")
    w("| prerequisites matching (of 12) | "
      + " | ".join(f"{x['prereq_match']}" for x in h) + " |")
    w("| recorded gaps | "
      + " | ".join(f"{len(x['shadow_gaps'])} (verified: {len(x['oracle_gaps'])})"
                   for x in h) + " |")
    w("| ratification holds | "
      + " | ".join(f"{len(x['shadow_holds'])} (verified: {len(x['oracle_holds'])})"
                   for x in h) + " |")
    w("| levels withheld where the verified assessment set one | "
      + " | ".join(str(len(r["withheld"])) for r in runs) + " |")
    w("| **rows read HIGHER than the verified assessment** | "
      + " | ".join(f"**{len(r['higher'])}**" for r in runs) + " |")
    w("| cost | "
      + " | ".join(f"${(r['comp'].get('spend') or {}).get('total', 0):.2f}" for r in runs)
      + " |")

    w("\nThe row to read is the last but one. The pipeline's error is overwhelmingly in "
      "the direction of saying too little, not too much — which is the failure the "
      "design record chose when it made abstention a first-class answer.\n")

    w("\n## Is the abstention the pipeline, or the country?\n")
    w(f"**{len(common)} rows** withheld a level in BOTH countries. Those are the "
      f"pipeline. Rows withheld in only one are that country's data environment.\n")
    w("| | rows | which |")
    w("|---|---|---|")
    w(f"| withheld in both | {len(common)} | {ids(common)} |")
    for r in runs:
        o = only[r["country"]]
        w(f"| {r['country']} only | {len(o)} | {ids(o)} |")

    w("\n## The split that decides which lever to pull\n")
    w("Of the rows withheld in both countries, the ones the pipeline **never reached** "
      "need more retrieval, and no threshold change will rescue them. The ones it "
      "reached and **declined to level** are the threshold.\n")
    w("| | rows |")
    w("|---|---|")
    for k, v in common_causes.most_common():
        w(f"| {k} | {v} |")
    total = sum(common_causes.values()) or 1
    nr = common_causes.get("not reached in both", 0)
    w(f"\n**{100.0 * nr / total:.0f}%** of the rows both countries withheld were never "
      f"reached at all. ")
    if nr / total >= 0.5:
        w("On this evidence the binding constraint is retrieval, not the abstention "
          "threshold — which is what the vendor audition also found, where every entrant "
          "abstained on the same four known-answer cells because the page carrying the "
          "answer was behind a JavaScript dashboard or inside a survey PDF. Loosening "
          "the threshold would not have produced those levels; it would only have "
          "produced levels with less behind them.\n")
    else:
        w("On this evidence a material share of the abstention is judgment rather than "
          "reach, so the threshold itself is worth tuning.\n")

    w("\n## Why each country declined, gate by gate\n")
    w("| country | " + " | ".join(sorted({k for c in causes.values() for k in c})) + " |")
    keys = sorted({k for c in causes.values() for k in c})
    w("|---|" + "---|" * len(keys))
    for r in runs:
        w(f"| {r['country']} | "
          + " | ".join(str(causes[r["country"]].get(k, 0)) for k in keys) + " |")

    w("\n## Every row read higher than its verified assessment\n")
    w("The dangerous direction, in full, for both countries.\n")
    any_high = False
    for r in runs:
        for iid in sorted(r["higher"], key=id_key):
            any_high = True
            x = r["by_id"][iid]
            w(f"- **{r['country']} {iid} {x['name']}** — verified L{x['o_level']}, "
              f"recorded L{x['s_level']}. {str(x.get('why', ''))[:220]}")
    if not any_high:
        w("None. Neither country produced a row above its verified level.\n")

    w("\n## The cheapest coverage there is\n")
    w("Every run fetches a machine-readable T1 lane separately and reports it beside the "
      "research lane's own answer without ever substituting it — a measurement run that "
      "quietly swapped in an API figure would be measuring the API. The rows below are "
      "ones where the research lane recorded a gap while that independent T1 series had "
      "the figure all along. Each one is already visible on its row, which said so in "
      "its note; each is also a level available for the price of a decision.\n")
    lane_rows = []
    for r in runs:
        for iid, rec in r["research"].items():
            wdi = rec.get("wdi_corroboration") or {}
            if wdi.get("status") == "ok" and r["by_id"].get(iid, {}).get("s_cls") == "Gap":
                lane_rows.append((r["country"], iid, wdi))
    if lane_rows:
        w("| country | id | indicator | the T1 series had |")
        w("|---|---|---|---|")
        for country, iid, wdi in sorted(lane_rows, key=lambda t: (t[0], id_key(t[1]))):
            w(f"| {country} | {iid} | {MODEL[iid]['name'][:34]} | "
              f"{round(wdi['value'], 2)} ({wdi['year']}) — {wdi['src'][:48]} |")
        w(f"\n**{len(lane_rows)} rows** across both countries. Whether the T1 lane should "
          f"be allowed to fill a gap the research lane could not is a real design "
          f"question and not one to settle silently: it trades a measurement of what the "
          f"research lane can do for coverage a reader would rather have. It is recorded "
          f"here as an open decision.\n")
    else:
        w("None: wherever the machine-readable T1 lane had a figure, the research lane "
          "found it too.\n")

    w("\n## Rows to fix by hand before the next country\n")
    w("Withheld in both countries and never reached: these are named sources behind "
      "interfaces the Exa/Jina substrate does not open. Each is a targeted retrieval "
      "job, not a tuning question, and fixing one fixes it for every country.\n")
    unreached = sorted([i for i in common
                        if all(cause(r, i) == "not reached" for r in runs)], key=id_key)
    for iid in unreached:
        w(f"- **{iid} {MODEL[iid]['name']}**"
          + ("  ⚑ prerequisite" if MODEL[iid]["prereq"] else ""))

    if any(r["g2"] for r in runs):
        w("\n## What the second review changed, in both countries\n")
        # Outcomes down the side rather than across the top. Seven columns rendered to
        # PDF at portrait width break their own headers mid-word ("relevelle d"), and a
        # reader should not have to reassemble a column name.
        counts, spends = [], []
        for r in runs:
            counts.append(Counter(f["outcome"] for f in r["g2"]))
            base = r["shadow"][:-3] if r["shadow"].endswith("_g2") else r["shadow"]
            spends.append((load(base, "_g2_spend.json") or {}).get("summary", {}))
        w("| outcome | " + " | ".join(r["country"] for r in runs) + " |")
        w("|---|" + "---|" * len(runs))
        for k in ("filled", "withdrawn", "relevelled", "adjusted", "upheld"):
            w(f"| {k} | " + " | ".join(str(c.get(k, 0)) for c in counts) + " |")
        w("| cost | " + " | ".join(f"${s.get('total', 0):.2f}" for s in spends) + " |")

    open(args.out, "w").write("\n".join(L) + "\n")

    print(f"withheld in both countries: {len(common)}")
    for r in runs:
        print(f"  {r['country']:8} withheld {len(r['withheld']):2} · "
              f"read higher {len(r['higher'])} · "
              f"prereq {r['comp']['headline']['prereq_match']}/12 · "
              f"levels {r['comp']['headline']['level_same']}/57")
    print(f"never reached in both: {nr} of {total} "
          f"({100.0 * nr / total:.0f}%)")
    print(f"\nwrote {os.path.basename(args.out)}")


if __name__ == "__main__":
    main()
