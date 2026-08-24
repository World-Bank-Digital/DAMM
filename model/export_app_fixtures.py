#!/usr/bin/env python3
"""Sync the model and the parity fixtures into DAR Studio.

The app carries a TypeScript port of the scorer, and its test suite holds that port to
the pipeline's own Egypt and Nigeria figures. Three files have to move together for that
to mean anything: the model the app validates, and the two expectation fixtures.

The fixtures are DISTILLED, not copies of the assessment JSON. They carry only the
derived figures the port must reproduce, in a flat shape that reads as a contract and
diffs legibly when a ruling changes a number. Copying the raw assessment over them looks
right and silently changes the shape — prereq becomes an object, leapfrog nests, and half
the suite starts comparing a string against a record. That is how this script came to
exist.

    python3 model/export_app_fixtures.py [--app PATH]
"""

import argparse, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
LOOP1 = os.path.join(REPO, "gauntlet", "loop-1")
DEFAULT_APP = os.path.expanduser("~/Projects/dar-studio-v2")

# The figures the port must reproduce. Anything not listed here is the pipeline's own
# working detail and is deliberately outside the contract.
PILLAR_KEYS = ("n", "rated", "held", "mean", "band", "margin", "weak", "comp", "stale")
MATRIX_KEYS = ("status", "why", "mean_readiness", "mean_need", "mean_outcome", "n_bearing")


def distil(assessment):
    a = assessment
    return {
        "counts": a["counts"],
        "rated": a["rated"],
        "held": a["held"],
        "pillars": {p: {k: v[k] for k in PILLAR_KEYS} for p, v in a["pillars"].items()},
        "layers": a["layers"],
        # Flattened: the port asserts the gap, and the reading is prose the port does not
        # reproduce.
        "leapfrog_gap": a["leapfrog"]["gap"],
        # id -> status. The kind and the name are model facts the port reads from the
        # model file, so repeating them here would test the fixture against itself.
        "prereq": {i: v["status"] for i, v in a["prereq"].items()},
        "matrix": {u: {k: v[k] for k in MATRIX_KEYS} for u, v in a["matrix"].items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=DEFAULT_APP)
    args = ap.parse_args()

    fixtures = os.path.join(args.app, "src", "lib", "damm-v17", "fixtures")
    data = os.path.join(args.app, "src", "data")
    for d in (fixtures, data):
        if not os.path.isdir(d):
            sys.exit(f"not found: {d}\nIs {args.app} the DAR Studio repository?")

    src = os.path.join(REPO, "model", "DAMM-v1.7-model.json")
    shutil.copyfile(src, os.path.join(data, "model_v1_7.json"))
    rev = json.load(open(src))["revision"]
    print(f"model_v1_7.json  <- revision {rev}")

    for iso, name in (("EGY", "egypt"), ("NGA", "nigeria")):
        a = json.load(open(os.path.join(LOOP1, f"{iso}_v17.json")))
        out = os.path.join(fixtures, f"{name}-expected.json")
        json.dump(distil(a), open(out, "w"), indent=1)
        print(f"{name}-expected.json  <- {len(a['pillars'])} pillars, "
              f"{len(a['matrix'])} columns, {len(a['prereq'])} prerequisites")

        # The observation fixtures are the pipeline's input rows, reduced to what the
        # port actually reads. Two exclusions matter. The carried candidates are outside
        # the scored register by construction, so handing them to the scorer makes it
        # reject the fixture as naming an unknown indicator. And the ratification notes
        # (defnote, defsev, note) are commentary the port never consults; leaving them in
        # would let a fixture diff look like a scoring change.
        rows = json.load(open(os.path.join(LOOP1, f"{iso}_v17_input.json")))
        keep = ("value", "cls", "level", "year", "src", "tier", "url")
        obs_rows = {i: {k: r[k] for k in keep if k in r}
                    for i, r in rows.items() if not i.startswith("A1-CAND-")}
        obs = os.path.join(fixtures, f"{name}-observations.json")
        json.dump(obs_rows, open(obs, "w"), indent=1)
        print(f"{name}-observations.json  <- {len(obs_rows)} scored rows "
              f"({len(rows) - len(obs_rows)} carried candidates excluded)")

    # The per-pass budget allocation lives in vendors.Ledger and is enforced there. The
    # app only displays and predicts against it, so it is exported rather than restated:
    # two copies of an allocation would drift, and the app would show a ceiling the
    # pipeline does not enforce.
    sys.path.insert(0, os.path.join(LOOP1, "research_pipeline"))
    import vendors as V  # noqa: E402
    budget = {
        "_source": "vendors.Ledger.ALLOCATION — exported, never restated. Regenerate with "
                   "model/export_app_fixtures.py after changing it there.",
        "default_ceiling_usd": 500.0,
        "allocation": V.Ledger.ALLOCATION,
    }
    out = os.path.join(data, "run_budget.json")
    json.dump(budget, open(out, "w"), indent=1)
    passes = {k: v for k, v in V.Ledger.ALLOCATION.items() if k != "audition"}
    print(f"run_budget.json  <- {len(V.Ledger.ALLOCATION)} passes, "
          f"country passes sum to {sum(passes.values()):.2f} of the ceiling")

    # The reasoning vendors, and which one each pass uses when none is named.
    #
    # gate2.py's contract is that the reviewer comes from a DIFFERENT vendor than the
    # primary: the audition showed a vendor's siblings sharing blind spots, so a model
    # reviewing its own pass upholds it. Nothing in the pipeline enforces that, because
    # the two defaults happened to differ. Now that the app chooses the vendor it has to
    # enforce it, and to do that it needs the defaults — read from the scripts rather
    # than restated, so a change there cannot leave the app checking the wrong pair.
    # A pass is runnable when a script implements it. The budget allocation names five
    # passes because it reserves each one's share of the ceiling, but only these two are
    # built — and the app must not queue a run for the other three, because a pass with
    # no script of its own would be handed to the research orchestrator and spend a full
    # research budget under another pass's name.
    PASS_SCRIPTS = {"research": "research_orchestrator.py", "g2": "gate2.py",
                    "scans": "scans.py"}
    pass_defaults = {}
    for pass_name, script in PASS_SCRIPTS.items():
        src = open(os.path.join(LOOP1, "research_pipeline", script)).read()
        m = re.search(r'add_argument\(\s*"--vendor"\s*,\s*default\s*=\s*"([^"]+)"', src)
        if not m:
            sys.exit(f"{script}: could not read the --vendor default. Export refuses to "
                     f"guess it: a wrong default would let a model review its own pass.")
        pass_defaults[pass_name] = m.group(1)

    vendors_out = {
        "_source": "vendors._MODEL_PREFS and the --vendor defaults in "
                   "research_orchestrator.py / gate2.py — exported, never restated. "
                   "Regenerate with model/export_app_fixtures.py after changing either.",
        "families": V._MODEL_PREFS,
        "runnable_passes": sorted(PASS_SCRIPTS),
        "pass_defaults": pass_defaults,
    }
    out = os.path.join(data, "run_vendors.json")
    json.dump(vendors_out, open(out, "w"), indent=1)
    print(f"run_vendors.json <- {len(V._MODEL_PREFS)} families; defaults "
          + ", ".join(f"{k}={v}" for k, v in pass_defaults.items()))

    print("\nNow run the app's test suite. The port must reproduce every figure above.")


if __name__ == "__main__":
    main()
