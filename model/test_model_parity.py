#!/usr/bin/env python3
"""The model file must be enough to score from.

Runs `reference_scorer` — which reads only DAMM-v1.7-model.json — against Egypt and Nigeria,
and compares every derived figure to what the engine produced. Any divergence means a rule
still lives in engine code instead of in the model, and the export is not yet canonical.

Run: python3 model/test_model_parity.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from reference_scorer import Scorer

L1 = os.path.join(ROOT, "gauntlet", "loop-1")
model = json.load(open(os.path.join(HERE, "DAMM-v1.7-model.json")))
sc = Scorer(model)

fails, checks = [], 0
def eq(label, a, b):
    global checks
    checks += 1
    same = (abs(a - b) < 1e-9) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else a == b
    if not same:
        fails.append(f"{label}: model={a!r} engine={b!r}")

for iso, name in (("EGY", "Egypt"), ("NGA", "Nigeria")):
    obs = {k: v for k, v in json.load(open(f"{L1}/{iso}_v17_input.json")).items()
           if not k.startswith("A1-CAND-")}
    eng = json.load(open(f"{L1}/{iso}_v17.json"))
    got = sc.run(obs)

    for c in ("Measured", "Documented", "Judged", "Gap"):
        eq(f"{name} counts.{c}", got["counts"][c], eng["counts"][c])
    eq(f"{name} rated", got["rated"], eng["rated"])
    eq(f"{name} held", got["held"], eng["held"])

    for p, e in eng["pillars"].items():
        g = got["pillars"][p]
        for k in ("n", "rated", "held", "mean", "band", "weak", "stale"):
            eq(f"{name} pillar {p}.{k}", g[k], e[k])
        for c in ("Measured", "Documented", "Judged", "Gap"):
            eq(f"{name} pillar {p}.comp.{c}", g["comp"][c], e["comp"][c])

    for L, v in eng["layers"].items():
        eq(f"{name} layer {L}", got["layers"][L], v)
    eq(f"{name} leapfrog", got["leapfrog"]["gap"], eng["leapfrog"]["gap"])

    for i, e in eng["prereq"].items():
        eq(f"{name} prereq {i}", got["prereq"][i]["status"], e["status"])

    for uc, e in eng["matrix"].items():
        g = got["matrix"][uc]
        for k in ("status", "why", "mean", "mean_enabler", "n_bearing"):
            eq(f"{name} matrix {uc}.{k}", g[k], e[k])

# --- structural invariants the schema declares, asserted directly (no schema engine here:
# consumers validate against DAMM-v1.7-model.schema.json with zod/ajv) -------------------
def inv(label, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        fails.append(f"{label}{': ' + detail if detail else ''}")

ids = [i["id"] for i in model["indicators"]]
inv("indicator ids unique", len(ids) == len(set(ids)))
inv("57 indicators", len(ids) == 57, str(len(ids)))
inv("every pillar referenced is declared",
    {i["pillar"] for i in model["indicators"]} <= set(model["pillars"]))
inv("every layer referenced is declared",
    {i["layer"] for i in model["indicators"]} <= set(model["layers"]))
inv("every use case referenced is declared",
    {u for i in model["indicators"] for u in i["use_cases"]} <= set(model["use_cases"]))
inv("threshold rows carry 4 cut-points and a direction",
    all(i["thresholds"] and len(i["thresholds"]) == 4 and i["direction"]
        for i in model["indicators"] if i["method"] == "threshold"))
inv("ladder rows carry no cut-points",
    all(not i["thresholds"] for i in model["indicators"] if i["method"] == "ladder"))
inv("bands are contiguous and half-open",
    all(model["bands"][k]["hi"] == model["bands"][k + 1]["lo"] for k in range(len(model["bands"]) - 1)))
inv("prerequisite kinds are closed",
    all(i["prerequisite"] in (None, "UNIVERSAL", "DELIVERY") or i["prerequisite"].startswith("UC:")
        for i in model["indicators"]))
inv("every UC: prerequisite names declared use cases",
    all(set(i["prerequisite"][3:].split(",")) <= set(model["use_cases"]) | {"AI"}
        for i in model["indicators"] if (i["prerequisite"] or "").startswith("UC:")))
inv("model is flagged unratified while decisions are open",
    model["ratified"] is False and len(model["open_decisions"]) > 0)
inv("no binding rule claims ratification while 13.4 is open",
    not any(r["ratified"] for r in model["binding_rules"]))
inv("A1 thresholds are marked unratified (13.6)",
    all(i.get("thresholds_ratified") is False
        for i in model["indicators"] if i["pillar"] == "A1" and i["thresholds"]))
inv("open definitional questions carried on 44 rows (13.5)",
    sum(1 for i in model["indicators"] if "ratification" in i) == 44)
inv("every open decision names what it governs",
    all(d["id"] and d["title"] and isinstance(d["governs"], list) for d in model["open_decisions"]))
inv("the four prohibitions travel with the model", len(model["prohibitions"]) == 4)

print(f"model-only parity: {checks - len(fails)}/{checks} checks match")
if fails:
    print("\nThe model file is NOT yet sufficient to score from:")
    for f in fails[:25]:
        print("  -", f)
    sys.exit(1)
print("DAMM-v1.7-model.json is canonical: every derived figure reproduces from the model alone.")
