#!/usr/bin/env python3
"""Reconcile every figure quoted in the review package against its source artifact.

Asked for by the reviewer before the rulings are recorded, and the ask was well placed:
the package carried a first-pass cost of $0.26 in one appendix and "about $15.50" in the
main paper, and two legacy automated-challenge figures that a re-run had superseded.

Prose drifts from data whenever an artifact is regenerated and a sentence is not. This
check makes that mechanical. It computes the canonical value of every figure the package
quotes, then requires that the documents state the current value and do NOT state a
superseded one.

    python3 reconcile_figures.py [--fix-list]
"""

import json, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(LOOP1, "..", ".."))
PKG = os.path.join(REPO, "Katreyna-Pipeline-Evidence-2026-08-24")


def J(p):
    return json.load(open(p)) if os.path.exists(p) else None


def canonical():
    """Every figure the package quotes, computed from the artifacts."""
    f = {}
    a = J(os.path.join(HERE, "audition_results.json"))
    if a:
        f["audition spend"] = f"${a['meta']['spend']['total']:.2f}"
        f["audition pages"] = str(a["meta"]["pages_fetched"])
        rates = {e["name"]: e["rates"]["fabrication_rate"] for e in a["entrants"]}
        f["entrants at zero fabrication"] = str(sum(1 for v in rates.values() if v == 0.0))
        f["highest fabrication rate"] = f"{max(rates.values()):.1f}%"
    for iso, co in (("EGY", "Egypt"), ("NGA", "Nigeria")):
        c2 = J(os.path.join(LOOP1, f"{iso}_shadow_g2_comparison.json"))
        if not c2:
            continue
        h = c2["headline"]
        rows = c2["rows"]
        f[f"{co} levels at verified"] = str(h["level_same"])
        f[f"{co} prerequisites matching"] = str(h["prereq_match"])
        f[f"{co} gaps"] = str(len(h["shadow_gaps"]))
        f[f"{co} rows above verified"] = str(
            sum(1 for r in rows if r["both_levelled"] and r["s_level"] > r["o_level"]))
        f[f"{co} levels withheld"] = str(
            sum(1 for r in rows if r["o_level"] is not None and r["s_level"] is None))
        challenge_findings = (
            J(os.path.join(LOOP1, f"{iso}_shadow_g2_findings.json")) or []
        )
        oc = {}
        for x in challenge_findings:
            oc[x["outcome"]] = oc.get(x["outcome"], 0) + 1
        f[f"{co} automated-challenge rows"] = str(len(challenge_findings))
        f[f"{co} automated-challenge levels changed"] = str(
            sum(oc.get(k, 0) for k in ("filled", "withdrawn", "relevelled")))
        sp = J(os.path.join(LOOP1, f"{iso}_shadow_g2_spend.json"))
        if sp:
            f[f"{co} automated-challenge cost"] = f"${sp['summary']['total']:.2f}"
        sh = J(os.path.join(LOOP1, f"{iso}_shadow_g2.json"))
        v = J(os.path.join(LOOP1, f"{iso}_v17.json"))
        if sh and v:
            f[f"{co} matrix automated"] = ", ".join(
                sorted({d["status"] for d in sh["matrix"].values()}))
            f[f"{co} matrix verified"] = ", ".join(
                sorted({d["status"] for d in v["matrix"].values()}))
    tot = sum(1 for r in (J(os.path.join(LOOP1, "EGY_shadow_g2_comparison.json")) or
                          {"rows": []})["rows"]
              if r["both_levelled"] and r["s_level"] > r["o_level"])
    tot += sum(1 for r in (J(os.path.join(LOOP1, "NGA_shadow_g2_comparison.json")) or
                           {"rows": []})["rows"]
               if r["both_levelled"] and r["s_level"] > r["o_level"])
    f["rows above verified, both countries"] = str(tot)
    return f


# Figures that were true of an earlier run and must not survive anywhere in the package.
# Each is paired with what replaced it, so a failure names the correction rather than
# only the problem.
SUPERSEDED = [
    (r"\$6\.39", "Egypt automated-challenge cost, superseded by the re-run"),
    (r"\$6\.14", "Nigeria automated-challenge cost, superseded by the re-run"),
    (r"\$21\.88", "Egypt two-pass total, from ledgers the resume bug truncated"),
    (r"\$21\.47", "Nigeria two-pass total, from ledgers the resume bug truncated"),
    (r"\bsix rows where\b", "there are eight rows above the verified assessments"),
    (r"changed three levels in each country",
     "the automated challenge changed four levels in Egypt and five in Nigeria"),
    (r"\b24 of 57\b", "Egypt now records 29 of 57"),
    (r"\b30 of 57\b", "Nigeria now records 33 of 57"),
    (r"\b5 of 12\b", "both countries now match 8 of 12 prerequisites"),
]


def main():
    facts = canonical()
    docs = sorted(glob.glob(os.path.join(PKG, "*.md"))
                  + glob.glob(os.path.join(PKG, "*", "*.md")))
    if not docs:
        sys.exit(f"no package documents found under {PKG}")
    blob = {os.path.relpath(d, PKG): open(d).read() for d in docs}

    if "--fix-list" in sys.argv:
        print("Canonical figures, for use when editing the prose:\n")
        for k, v in facts.items():
            print(f"  {k:44} {v}")
        return 0

    print("Canonical figures, computed from the artifacts:\n")
    for k, v in facts.items():
        print(f"  {k:44} {v}")

    print("\n\nSuperseded figures still present in the package:\n")
    bad = []
    for pat, why in SUPERSEDED:
        hits = [name for name, text in blob.items() if re.search(pat, text, re.I)]
        if hits:
            bad.append((pat, why, hits))
            print(f"  FOUND {pat:42} {why}")
            for h in hits:
                print(f"        in {h}")
    if not bad:
        print("  none")

    # The two authored documents are prose and must carry the current headline figures.
    print("\n\nHeadline figures the authored documents must state:\n")
    must = ["Egypt levels at verified", "Nigeria levels at verified",
            "Egypt prerequisites matching", "Nigeria prerequisites matching",
            "rows above verified, both countries", "audition spend"]
    authored = "\n".join(t for n, t in blob.items() if os.sep not in n)
    missing = []
    for k in must:
        v = facts.get(k)
        if v and not re.search(re.escape(v.lstrip("$")), authored):
            missing.append((k, v))
            print(f"  MISSING {k:40} expected to see {v}")
    if not missing:
        print("  all present")

    print()
    if bad or missing:
        print("RECONCILIATION FAILED — the package states figures its artifacts do not.")
        return 1
    print("Reconciliation passed: no superseded figure survives, "
          "and every headline is present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
