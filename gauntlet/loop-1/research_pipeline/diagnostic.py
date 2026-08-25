#!/usr/bin/env python3
"""Pass six: the diagnostic report (design decision E1).

The renderer already exists and is not rewritten here. `render_v17.py` produced the
Egypt and Nigeria diagnostics, survived a gauntlet and an external review, and carries an
emit-blocking QC gate that is much of why it survived. E1 is explicit that a rewrite
would re-earn its defects, so this pass assembles the three things the renderer wants and
then calls it.

It makes no vendor call. The assessment has already been paid for by the research pass;
this scores it with the engine, points a per-run config at the run's own files, and
renders. Its share of the ceiling is zero, and that zero is stated in the allocation
rather than left as an absence.

What it will not do is invent the report's inputs. A diagnostic needs an initiative
register, and where the scans pass has not produced one this pass says so and renders
without it rather than shipping a report whose register section is quietly empty.

    python3 diagnostic.py --country Egypt --iso EGY --out EGY_shadow
"""

import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP1 = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(LOOP1, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, LOOP1)

import vendors as V
import engine_v17

PASS = "diagnostic"
MODEL_FILE = os.path.join(REPO, "model", "DAMM-v1.7-model.json")
SPEC = json.load(open(MODEL_FILE))
ASSESSMENT_YEAR = SPEC["config"]["assessment_year"]


def gates_text(basename, reviewed):
    """What the report says about its own gates. Stated from what actually ran."""
    return {
        "G1": ("machine derivation, executed by the research pass with every level "
               "derived from a recorded value and its own argument"),
        "G2": ("automated independent peer review of every gap, hold and prerequisite row"
               if reviewed else
               "NOT RUN for this pass — no independent second review has been applied"),
        "G3": "pending",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--out", required=True, help="basename of the research pass")
    ap.add_argument("--ceiling", type=float, default=500.0)
    ap.add_argument("--vendor", default="")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    print(f"{a.country} ({a.iso}) · 3 rows · vendor none (no vendor call is made)")
    print("budget $0, diagnostic allocation $0 — the assessment is already paid for")
    print()
    sys.stdout.flush()

    def step(n, name, outcome, detail, t0):
        print(f"  [{n}/3] {name:<14} {outcome:<8} {detail[:44]:<46} "
              f"$  0.00 {int(time.time() - t0):3d}s")
        sys.stdout.flush()

    # A second review, where it has run, supersedes the first pass. Preferring it is the
    # whole point of having run it.
    inp, reviewed = V.engine_input_for(LOOP1, a.out)
    src = os.path.basename(inp)
    if not os.path.exists(inp):
        print(f"!! no engine input at {src}")
        print("   The diagnostic reports an assessment. Finish the research pass first.")
        return 1

    # ---- 1. score
    t0 = time.time()
    scored = os.path.join(LOOP1, f"{a.out}_v17.json")
    try:
        engine_v17.main(inp, scored, a.country)
    except SystemExit as e:
        print(f"!! the engine refused the input: {e}")
        return 1
    d = json.load(open(scored))
    step(1, "score", "done",
         f"{d['rated']} rated, {d['held']} withheld, from {src}", t0)

    # ---- 2. the register
    t0 = time.time()
    register_path = os.path.join(LOOP1, f"{a.out}_register.json")
    if os.path.exists(register_path):
        n = len(json.load(open(register_path)).get("entries", []))
        step(2, "register", "found", f"{n} initiatives from the scans pass", t0)
    else:
        # Written empty rather than omitted: render_v17 requires a register, and an empty
        # one with a stated reason reads as "nothing was gathered", where a fabricated one
        # would read as "nothing exists".
        json.dump({
            "country": a.iso,
            "register": "Initiative & solutions register — DAMM v1.7 diagnostic",
            "access_date": "",
            "protocol": "DAMM-v1.6-Source-Tier-Protocol",
            "entries": [],
            "overlap_finding": "",
            "issues": ("The scans pass has not run for this assessment, so no initiative "
                       "register was gathered. This section is empty because nothing was "
                       "looked for, not because nothing was found."),
        }, open(register_path, "w"), indent=1)
        step(2, "register", "empty", "the scans pass has not run", t0)

    # ---- 3. render
    t0 = time.time()
    key = a.out.lower()
    out_html = os.path.join(LOOP1, f"{a.out}_diagnostic.html")
    json.dump({
        "country": a.country,
        "period": str(ASSESSMENT_YEAR),
        "assessment": "machine-assisted desk assessment",
        "data_path": scored,
        "register_path": register_path,
        # Keeps this run's report off any hand-built one for the same country.
        "out_path": out_html,
        "gates": gates_text(a.out, reviewed),
    }, open(os.path.join(LOOP1, f"config_{key}.json"), "w"), indent=1)

    proc = subprocess.run([sys.executable, "render_v17.py", a.out],
                          cwd=LOOP1, capture_output=True, text=True)
    if proc.returncode != 0:
        # The renderer's QC gate is emit-blocking by design. A failure here is the report
        # refusing to be written, and the reason is the useful part.
        detail = (proc.stdout + proc.stderr).strip().splitlines()
        print(f"!! the diagnostic was NOT written: {detail[-1] if detail else 'render failed'}")
        return 1
    step(3, "render", "written", os.path.basename(out_html), t0)

    # Coverage is stated by the run, not only by the document. The report carries its
    # denominators on every figure, but an operator reading a run log should not have to
    # open the HTML to learn that four pillars came out unrated.
    blank_pillars = [p for p, v in d["pillars"].items() if v["mean"] is None]
    blank_layers = [l for l, v in d["layers"].items() if v is None]
    if blank_pillars or blank_layers:
        print()
        print("!! this assessment is too thin to profile in full:")
        if blank_pillars:
            print(f"   {len(blank_pillars)} pillars carry no rated row: "
                  f"{', '.join(sorted(blank_pillars))}")
        if blank_layers:
            print(f"   {len(blank_layers)} layers carry no rated row: "
                  f"{', '.join(sorted(blank_layers))}")
        print("   The report was written and says so on its face. It reports what the "
              "assessment found, which here is mostly that it found little.")

    print()
    print(f"wrote {os.path.basename(out_html)} — {d['rated']} rated rows, "
          f"{d['counts']['Gap']} gaps, {d['held']} levels withheld"
          + ("" if reviewed else ", second review NOT applied"))
    print("spend $0.00 of $0 allocated — this pass makes no vendor call")
    return 0


if __name__ == "__main__":
    sys.exit(main())
