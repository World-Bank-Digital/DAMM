#!/usr/bin/env python3
"""Did Gate 2 earn its 15%?

Decision G3 reserves roughly 15% of a country's budget for the second review, and the
design record says plainly that whether it deserves that share is unknown until the
shadow figures can be re-run with it. This is that arithmetic: the same comparison
against the same verified assessment, before and after, with Gate 2's own cost beside
it.

It reads finished artifacts and calls nothing — run it after both comparisons exist.

Usage:
    python3 g2_delta.py --before EGY_shadow --after EGY_shadow_g2 --country Egypt
"""

import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))


def load(name, suffix):
    p = os.path.join(LOOP1, f"{name}{suffix}")
    return json.load(open(p)) if os.path.exists(p) else None


def arrow(before, after, higher_is_better=True):
    if before == after:
        return "no change"
    better = (after > before) if higher_is_better else (after < before)
    return f"{'+' if after > before else ''}{after - before}" + (" ✓" if better else " ✗")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--country", required=True)
    args = ap.parse_args()

    b = load(args.before, "_comparison.json")
    a = load(args.after, "_comparison.json")
    if not b or not a:
        sys.exit("both comparisons must exist — run compare_shadow.py on each first")
    findings = load(args.before, "_g2_findings.json") or []
    spend = (load(args.before, "_g2_spend.json") or {}).get("summary", {})
    first = (load(args.before, "_spend.json") or {}).get("summary", {})

    bh, ah = b["headline"], a["headline"]
    outcomes = {}
    for f in findings:
        outcomes[f["outcome"]] = outcomes.get(f["outcome"], 0) + 1
    # Every outcome that moved a level. "adjusted" is provenance only and is not
    # a level change, so it is reported beside these rather than among them.
    changed = sum(outcomes.get(k, 0) for k in ("filled", "withdrawn", "relevelled"))

    L = []
    w = L.append
    w(f"# Did Gate 2 earn its share? — {args.country}\n")
    w(f"The same comparison against the same verified assessment, before and after the "
      f"second review. `{args.before}` is the first pass alone; `{args.after}` is the "
      f"first pass with Gate 2's surviving findings applied.\n")

    w("\n## What it cost\n")
    g2c, fpc = spend.get("total", 0), first.get("total", 0)
    # A first-pass ledger smaller than the second review's is not a cheap first pass. It
    # is a truncated ledger: resuming a run used to overwrite the counter rather than
    # carry it, so a run finished in two sittings kept only the second. Saying so beats
    # printing a share of a total that is wrong.
    truncated = fpc < g2c
    if truncated:
        w("**The first-pass ledger for this run is incomplete and the figures below "
          "understate it.** Resuming a run overwrote the spend counter instead of "
          "carrying it forward, so what survives is the cost of the final sitting only. "
          "The defect is fixed and the counter now accumulates across a resume, but this "
          "run's first-pass total cannot be recovered from the file. Clean measurements "
          "of a full first pass, taken before the resumes, were $15.49 for Egypt and "
          "$15.32 for Nigeria. The authoritative figure will come from the re-run on the "
          "frozen configuration.\n")
    w(f"| | first pass | Gate 2 | Gate 2 as a share |")
    w("|---|---|---|---|")
    w(f"| cost | ${fpc:.2f}{' (incomplete)' if truncated else ''} | ${g2c:.2f} | "
      + ("not derivable from an incomplete first-pass ledger"
         if truncated else
         f"{100.0 * g2c / max(fpc + g2c, 1e-9):.0f}% of the two passes together") + " |")
    w(f"| rows | 57 | {len(findings)} | "
      f"{100.0 * len(findings) / 57:.0f}% of the register |")
    w(f"| minutes | {first.get('elapsed_s', 0) / 60:.0f} | "
      f"{spend.get('elapsed_s', 0) / 60:.0f} | |")
    w(f"\nDecision G3 reserves 15% of the country budget for Gate 2 — $75 of $500. It "
      f"spent **${g2c:.2f}**, which is {100.0 * g2c / 75.0:.0f}% of that allocation.\n")

    w("\n## What it changed\n")
    w("| outcome | rows |")
    w("|---|---|")
    for k in ("filled", "withdrawn", "relevelled", "adjusted", "upheld"):
        if k in outcomes:
            w(f"| {k} | {outcomes[k]} |")
    w(f"\n**{changed} rows** had their level changed by the second review "
      f"({outcomes.get('filled', 0)} filled, {outcomes.get('withdrawn', 0)} withdrawn, "
      f"{outcomes.get('relevelled', 0)} relevelled). That figure, not the upheld count, "
      f"is what the 15% buys.\n")

    w("\n## Whether it moved the assessment toward the verified one\n")
    w("| measure | before Gate 2 | after | change |")
    w("|---|---|---|---|")
    w(f"| rows at the verified level (of {bh['n']}) | {bh['level_same']} | "
      f"{ah['level_same']} | {arrow(bh['level_same'], ah['level_same'])} |")
    w(f"| prerequisites matching (of 12) | {bh['prereq_match']} | {ah['prereq_match']} | "
      f"{arrow(bh['prereq_match'], ah['prereq_match'])} |")
    w(f"| recorded gaps | {len(bh['shadow_gaps'])} | {len(ah['shadow_gaps'])} | "
      f"{arrow(len(bh['shadow_gaps']), len(ah['shadow_gaps']), higher_is_better=False)} "
      f"(the verified assessment records {len(bh['oracle_gaps'])}) |")
    w(f"| ratification holds | {len(bh['shadow_holds'])} | {len(ah['shadow_holds'])} | "
      f"{arrow(len(bh['shadow_holds']), len(ah['shadow_holds']), higher_is_better=False)} "
      f"(the verified assessment records {len(bh['oracle_holds'])}) |")
    w(f"| rows both assessments levelled | {bh['both_levelled']} | {ah['both_levelled']} | "
      f"{arrow(bh['both_levelled'], ah['both_levelled'])} |")
    w(f"| of those, exactly equal | {bh['both_same']} | {ah['both_same']} | "
      f"{arrow(bh['both_same'], ah['both_same'])} |")

    filled = sorted(set(bh["shadow_gaps"]) - set(ah["shadow_gaps"]))
    newheld = sorted(set(ah["shadow_holds"]) - set(bh["shadow_holds"]))
    if filled:
        w(f"\nGaps Gate 2 closed: {', '.join(filled)}.")
    if newheld:
        w(f"\nLevels Gate 2 withdrew: {', '.join(newheld)}.")

    w("\n\n## Reading this\n")
    w("Two cautions before this table is used to decide anything.\n")
    w("**Moving toward the verified assessment is not the only good outcome.** The "
      "verified assessment is the best available answer, not the truth, and Gate 2 can "
      "be right where it disagrees with it — the hand-run gauntlet's own Gate 2 changed "
      "rows that had already passed Gate 1. A row moved away from the verified level is "
      "a row to read, not a row to count against Gate 2.\n")
    w("**Two independent runs of the first pass alone differ on about four rows.** A "
      "change of one or two in this table is inside that noise. Only a change larger "
      "than that is evidence about Gate 2 rather than about run-to-run variance.\n")

    out = os.path.join(LOOP1, f"G2-VALUE-{args.before}.md")
    open(out, "w").write("\n".join(L) + "\n")

    print(f"Gate 2 cost ${g2c:.2f} ({100.0 * g2c / 75.0:.0f}% of its $75 allocation) "
          f"on {len(findings)} rows")
    print(f"changed {changed} levels — "
          + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())))
    print(f"verified-level agreement {bh['level_same']} -> {ah['level_same']} of {bh['n']}")
    print(f"prerequisites            {bh['prereq_match']} -> {ah['prereq_match']} of 12")
    print(f"gaps                     {len(bh['shadow_gaps'])} -> {len(ah['shadow_gaps'])}")
    print(f"holds                    {len(bh['shadow_holds'])} -> {len(ah['shadow_holds'])}")
    print(f"\nwrote {os.path.basename(out)}")


if __name__ == "__main__":
    main()
