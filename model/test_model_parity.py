#!/usr/bin/env python3
"""The model file must be enough to score from.

Runs `reference_scorer` — which reads only DAMM-v1.7-model.json — against Egypt and Nigeria,
and compares every derived figure to what the engine produced. Any divergence means a rule
still lives in engine code instead of in the model, and the export is not yet canonical.

Run: python3 model/test_model_parity.py
"""
import copy, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from reference_scorer import Scorer

L1 = os.path.join(ROOT, "gauntlet", "loop-1")
sys.path.insert(0, L1)
from engine_v17 import run as engine_run

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
    legacy_engine = engine_run(name, obs)
    injected_unratified_engine = engine_run(name, obs, model_spec=model)

    eq(f"{name} unratified engine matrix remains exactly legacy",
       json.loads(json.dumps(legacy_engine["matrix"])), eng["matrix"])
    eq(f"{name} explicit unratified model_spec is an exact legacy no-op",
       injected_unratified_engine, legacy_engine)
    eq(f"{name} unratified engine emits no mapping version pins",
       set(("model_version", "model_revision", "prerequisite_mapping_revision"))
       & set(legacy_engine), set())

    for c in ("Measured", "Documented", "Judged", "Gap"):
        eq(f"{name} counts.{c}", got["counts"][c], eng["counts"][c])
    eq(f"{name} rated", got["rated"], eng["rated"])
    eq(f"{name} held", got["held"], eng["held"])

    for p, e in eng["pillars"].items():
        g = got["pillars"][p]
        for k in ("n", "rated", "held", "mean", "band", "margin", "weak", "stale"):
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
        for k in ("status", "why", "mean_readiness", "mean_need", "mean_outcome",
                  "n_bearing"):
            eq(f"{name} matrix {uc}.{k}", g[k], e[k])

# A stored non-null level is a cache: both scoring boundaries must rederive it from the
# current thresholds.  A null level is different — it is an explicit ratification hold.
# Using an otherwise all-gap payload makes the universal 2.9 prerequisite expose both
# semantics directly in the readiness matrix.
synthetic = {
    iid: {
        "value": "DATA GAP — synthetic scoring-boundary fixture",
        "cls": "Gap",
        "level": None,
        "year": 2026,
        "src": "synthetic fixture",
        "tier": "",
        "url": "",
    }
    for iid in sc.ind
}
synthetic["2.9"] = {
    "value": 0.0,
    "cls": "Measured",
    "level": 5,  # deliberately stale: current H thresholds derive level 1
    "year": 2026,
    "src": "synthetic fixture",
    "tier": "T1",
    "url": "https://example.test/fixture",
}
stale_ref = sc.run(synthetic)
stale_eng = engine_run("Synthetic", synthetic)
eq("reference scorer rederives a stale Measured level",
   stale_ref["prereq"]["2.9"]["status"], "Absent")
eq("engine rederives a stale Measured level",
   stale_eng["prereq"]["2.9"]["status"], "Absent")
eq("a rederived absent universal prerequisite blocks the reference matrix",
   {row["status"] for row in stale_ref["matrix"].values()}, {"Blocked"})
eq("a rederived absent universal prerequisite blocks the engine matrix",
   {row["status"] for row in stale_eng["matrix"].values()}, {"Blocked"})

held = {iid: dict(row) for iid, row in synthetic.items()}
held["2.9"]["level"] = None
held_ref = sc.run(held)
held_eng = engine_run("Synthetic", held)
eq("reference scorer preserves an explicit Measured hold",
   held_ref["prereq"]["2.9"]["status"], "Unverified")
eq("engine preserves an explicit Measured hold",
   held_eng["prereq"]["2.9"]["status"], "Unverified")
eq("a held universal prerequisite leaves the reference matrix unverified",
   {row["status"] for row in held_ref["matrix"].values()}, {"Unverified"})
eq("a held universal prerequisite leaves the engine matrix unverified",
   {row["status"] for row in held_eng["matrix"].values()}, {"Unverified"})

missing = {iid: dict(row) for iid, row in synthetic.items()}
missing["2.9"].pop("level")
missing_ref = sc.run(missing)
missing_eng = engine_run("Synthetic", missing)
eq("reference scorer derives a missing Measured level rather than inventing a hold",
   missing_ref["prereq"]["2.9"]["status"], "Absent")
eq("engine derives a missing Measured level rather than inventing a hold",
   missing_eng["prereq"]["2.9"]["status"], "Absent")

# A first-class mapping activates only when both it and the model root are ratified.  The
# fixture is the complete 12 x 6 Cartesian product but deliberately has only four positive
# edges, so each effect can be isolated without copying the still-unratified 13.3 proposal.
gate_outcomes = {
    "Absent": "Blocked", "Unverified": "Unverified",
    "Present (narrow)": "Partial", "Present": "no_change",
}
risk_outcomes = {
    "Absent": "flag", "Unverified": "verify",
    "Present (narrow)": "flag_narrow", "Present": "no_change",
}
mapping_prerequisites = [
    row["id"] for row in model["indicators"] if row["prerequisite"]]
mapping_use_cases = list(model["use_cases"])


def mapping_edge(prerequisite_id, use_case_id, effect="none",
                 applicability=None, outcomes=None):
    edge = {
        "prerequisite_id": prerequisite_id,
        "use_case_id": use_case_id,
        "effect": effect,
        "applicability": applicability or {"mode": "never"},
        "rationale": f"Synthetic {effect} edge for parity testing.",
        "basis": ["test.synthetic-ratified-mapping"],
        "decision_status": "ratified",
    }
    if outcomes is not None:
        edge["on_prerequisite_status"] = dict(outcomes)
    return edge


positive_edges = {
    ("2.9", "MKT"): mapping_edge(
        "2.9", "MKT", "gate", {"mode": "always"}, gate_outcomes),
    ("7.12", "ADV"): mapping_edge(
        "7.12", "ADV", "gate", {
            "mode": "conditional",
            "predicate": {"any": [
                {"field": "uses_personal_data", "equals": True},
                {"field": "uses_farm_level_data", "equals": True},
            ]},
        }, gate_outcomes),
    ("7.12", "MKT"): mapping_edge(
        "7.12", "MKT", "gate", {
            "mode": "conditional",
            "predicate": {"any": [
                {"field": "uses_personal_data", "equals": True},
                {"field": "uses_farm_level_data", "equals": True},
            ]},
        }, gate_outcomes),
    ("5.7", "AGI"): mapping_edge(
        "5.7", "AGI", "delivery_risk", {
            "mode": "conditional",
            "predicate": {"field": "moag_led_or_owned", "equals": True},
        }, risk_outcomes),
}
mapping_edges = [
    positive_edges.get(
        (prerequisite_id, use_case_id),
        mapping_edge(prerequisite_id, use_case_id))
    for prerequisite_id in mapping_prerequisites
    for use_case_id in mapping_use_cases
]
ratified_mapping_model = copy.deepcopy(model)
ratified_mapping_model.update({
    "status": "ratified",
    "ratified": True,
    "revision": model["revision"] + 1,
    "prerequisite_mapping": {
        "decision_id": "13.3",
        "revision": 1,
        "status": "ratified",
        "ratified": True,
        "use_case_ids": mapping_use_cases,
        "prerequisite_ids": mapping_prerequisites,
        "status_precedence": ["Blocked", "Unverified", "Partial", "Ready"],
        "conditional_policy": {
            "missing_profile": "report_condition_without_mutating_base_status",
            "true": "activate_edge",
            "false": "ignore_edge",
        },
        "edges": mapping_edges,
    },
})
mapping_definition_entries = {}
mapping_definition_refs = {}
for indicator in ratified_mapping_model["indicators"]:
    indicator_id = indicator["id"]
    mapping_definition_entries[indicator_id] = {
        "definition_version": "mapping-parity-v1",
        "measure": {
            "unit": "ratified parity unit",
            "population_scope": "national parity population",
            "reference_period": "latest complete annual period",
            "numerator": "not_applicable",
            "denominator": "not_applicable",
            "transform": "identity",
        },
        "source_policy": {
            "preferred_series": ["PARITY:SERIES"],
            "allowed_tiers": ["T1", "T2", "T3"],
            "minimum_confirmation": (
                "One load-bearing source plus construct review"),
        },
        "scoring": {
            "method": indicator["method"],
            "direction": indicator["direction"],
            "missing_rule": "DATA GAP", "mismatch_rule": "HOLD",
            **({"cuts": indicator["thresholds"]}
               if indicator["method"] == "threshold" else {}),
        },
    }
    if indicator.get("thresholds"):
        mapping_definition_refs[indicator_id] = f"PARITY-CAL-{indicator_id}"
ratified_mapping_model["indicator_definitions"] = {
    "catalog_version": "mapping-parity-v1",
    "catalog_status": "ratified",
    "entries": mapping_definition_entries,
}
ratified_mapping_model["indicator_calibration_refs"] = mapping_definition_refs
mapped_obs = {}
mapping_indicator_by_id = {
    indicator["id"]: indicator
    for indicator in ratified_mapping_model["indicators"]
}
for iid in sc.ind:
    indicator = mapping_indicator_by_id[iid]
    desired_level = 1 if iid in {"2.9", "5.7"} else 5
    if indicator["method"] == "threshold":
        cuts = indicator["thresholds"]
        value = (cuts[0] - 1
                 if desired_level == 1
                 and indicator["direction"] == "higher-is-better"
                 else cuts[0] + 1
                 if desired_level == 1 else cuts[-1])
        cls, tier = "Measured", "T1"
    else:
        value = "Synthetic documented evidence."
        cls, tier = "Documented", "T3"
    mapped_obs[iid] = {
        "value": value, "cls": cls, "level": desired_level, "year": 2026,
        "src": "synthetic fixture", "tier": tier,
        "url": "https://example.test/fixture",
    }
for indicator_id, row in mapped_obs.items():
    definition = mapping_definition_entries[indicator_id]
    encoded = json.dumps(
        definition, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")
    row["definition_metadata"] = {
        "definition_version": definition["definition_version"],
        "definition_sha256": hashlib.sha256(encoded).hexdigest(),
        "definition_match": True,
        "unit": definition["measure"]["unit"],
        "population_scope": definition["measure"]["population_scope"],
        "reference_period_rule": definition["measure"]["reference_period"],
        "transform": definition["measure"]["transform"],
        "geography": "synthetic national parity fixture",
        "observation_period": "2026",
        "edition": "2026 parity release",
        "proxy": False,
        "source_record_sha256": hashlib.sha256(
            f"source:{indicator_id}".encode()).hexdigest(),
        "construct_review_sha256": hashlib.sha256(
            f"review:{indicator_id}".encode()).hexdigest(),
        "numerator": "not_applicable",
        "denominator": "not_applicable",
        "source_series": "PARITY:SERIES",
    }
    if indicator_id in mapping_definition_refs:
        row["definition_metadata"]["calibration_ref"] = (
            mapping_definition_refs[indicator_id])
    if row["cls"] == "Measured":
        row["definition_metadata"]["transform_inputs"] = {
            "source_value": row["value"],
        }
mapped_obs["2.9"]["level"] = 1
mapped_obs["7.12"].update({
    "value": "DATA GAP — synthetic conditional hold",
    "cls": "Gap", "level": None,
})
mapped_obs["5.7"]["level"] = 1
intervention_profiles = {
    "ADV": {"uses_farm_level_data": True},
    "MKT": {"uses_personal_data": True},
    "AGI": {"moag_led_or_owned": True},
}

mapped_scorer = Scorer(ratified_mapping_model)
mapped_ref = mapped_scorer.run(mapped_obs, intervention_profiles)
mapped_eng = engine_run(
    "Synthetic mapped", mapped_obs, model_spec=ratified_mapping_model,
    intervention_profiles=intervention_profiles)

eq("ratified fixture contains all 72 explicit mapping edges", len(mapping_edges), 72)
eq("ratified fixture carries explicit none edges",
   sum(edge["effect"] == "none" for edge in mapping_edges), 68)
for field in ("model_version", "model_revision", "prerequisite_mapping_revision"):
    eq(f"mapped engine/reference pin the same {field}",
       mapped_ref[field], mapped_eng[field])
eq("mapped output pins the exact model and mapping revisions", {
    "model_version": mapped_ref["model_version"],
    "model_revision": mapped_ref["model_revision"],
    "prerequisite_mapping_revision": mapped_ref["prerequisite_mapping_revision"],
}, {
    "model_version": model["version"],
    "model_revision": model["revision"] + 1,
    "prerequisite_mapping_revision": 1,
})

for use_case_id in mapping_use_cases:
    for field in (
            "status", "why", "mean_readiness", "mean_need", "mean_outcome",
            "n_bearing", "active_gates", "conditional_constraints",
            "delivery_risks", "status_reason"):
        eq(f"mapped engine/reference parity {use_case_id}.{field}",
           mapped_ref["matrix"][use_case_id][field],
           mapped_eng["matrix"][use_case_id][field])
eq("mapped engine/reference cells expose one complete interface",
   mapped_ref["matrix"], mapped_eng["matrix"])

eq("a true any-predicate activates the ADV conditional gate",
   mapped_ref["matrix"]["ADV"]["status"], "Unverified")
eq("an explicit none edge keeps absent 2.9 out of ADV active gates",
   [gate["prerequisite_id"]
    for gate in mapped_ref["matrix"]["ADV"]["active_gates"]], ["7.12"])
eq("declared status precedence selects Blocked over Unverified",
   mapped_ref["matrix"]["MKT"]["status"], "Blocked")
eq("status_reason names only the winning MKT gate",
   mapped_ref["matrix"]["MKT"]["status_reason"]["drivers"], [{
       "type": "gate", "prerequisite_id": "2.9",
       "prerequisite_status": "Absent",
   }])
eq("an active delivery risk is exposed",
   mapped_ref["matrix"]["AGI"]["delivery_risks"], [{
       "prerequisite_id": "5.7", "prerequisite_status": "Absent",
       "action": "flag", "applicability": "conditional",
   }])

missing_profile_ref = mapped_scorer.run(mapped_obs)
missing_profile_eng = engine_run(
    "Synthetic mapped", mapped_obs, model_spec=ratified_mapping_model)
eq("missing profiles preserve mapped engine/reference parity",
   missing_profile_ref["matrix"], missing_profile_eng["matrix"])
eq("missing ADV profile reports rather than activates its condition",
   missing_profile_ref["matrix"]["ADV"]["conditional_constraints"][0]["evaluation"],
   "unresolved")
eq("missing ADV profile does not mutate the base status",
   missing_profile_ref["matrix"]["ADV"]["status"], "Ready")
eq("delivery risk never changes readiness status",
   missing_profile_ref["matrix"]["AGI"]["status"],
   mapped_ref["matrix"]["AGI"]["status"])

false_profile_ref = mapped_scorer.run(mapped_obs, {
    "ADV": {"uses_personal_data": False, "uses_farm_level_data": False},
})
eq("a false conditional predicate is explicitly inactive",
   false_profile_ref["matrix"]["ADV"]["conditional_constraints"][0]["evaluation"],
   "inactive")
eq("a false conditional predicate leaves no active gate",
   false_profile_ref["matrix"]["ADV"]["active_gates"], [])

reversed_mapping_model = copy.deepcopy(ratified_mapping_model)
reversed_mapping_model["prerequisite_mapping"]["edges"].reverse()
reversed_ref = Scorer(reversed_mapping_model).run(
    mapped_obs, intervention_profiles)
eq("edge order cannot change mapped readiness output",
   reversed_ref["matrix"], mapped_ref["matrix"])

reordered_inventory_model = copy.deepcopy(ratified_mapping_model)
reordered_inventory_model["prerequisite_mapping"]["use_case_ids"].reverse()
reordered_inventory_model["prerequisite_mapping"]["prerequisite_ids"].reverse()
reordered_ref = Scorer(reordered_inventory_model).run(
    mapped_obs, intervention_profiles)
reordered_eng = engine_run(
    "Synthetic reordered inventories", mapped_obs,
    model_spec=reordered_inventory_model,
    intervention_profiles=intervention_profiles)
eq("mapping inventories are duplicate-free sets, not ordered contracts",
   reordered_ref["matrix"], mapped_ref["matrix"])
eq("reordered mapping inventories preserve engine/reference parity",
   reordered_eng["matrix"], mapped_eng["matrix"])

# A model revision pin must identify every scoring rule, not just the edge mapping.  This
# mutation catches an engine that accepts model_spec but continues using embedded thresholds.
threshold_model = copy.deepcopy(ratified_mapping_model)
next(row for row in threshold_model["indicators"]
     if row["id"] == "2.9")["thresholds"] = [0, 0, 0, 0]
threshold_model["indicator_definitions"]["entries"]["2.9"][
    "scoring"]["cuts"] = [0, 0, 0, 0]
threshold_obs = copy.deepcopy(mapped_obs)
threshold_obs["2.9"].update({"value": 0, "cls": "Measured", "level": 1})
threshold_obs["2.9"]["definition_metadata"]["definition_sha256"] = (
    hashlib.sha256(json.dumps(
        threshold_model["indicator_definitions"]["entries"]["2.9"],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest())
threshold_obs["2.9"]["definition_metadata"]["transform_inputs"] = {
    "source_value": 0,
}
threshold_ref = Scorer(threshold_model).run(
    threshold_obs, intervention_profiles)
threshold_eng = engine_run(
    "Synthetic threshold mutation", threshold_obs,
    model_spec=threshold_model, intervention_profiles=intervention_profiles)
eq("ratified model_spec drives engine threshold derivation",
   threshold_eng["prereq"]["2.9"]["status"], "Present")
eq("mutated ratified scoring projection preserves complete matrix parity",
   threshold_eng["matrix"], threshold_ref["matrix"])

assessment_year_model = copy.deepcopy(ratified_mapping_model)
assessment_year_model["config"]["assessment_year"] = 2030
assessment_year_ref = Scorer(assessment_year_model).run(
    mapped_obs, intervention_profiles)
assessment_year_eng = engine_run(
    "Synthetic assessment-year mutation", mapped_obs,
    model_spec=assessment_year_model,
    intervention_profiles=intervention_profiles)
eq("ratified model_spec assessment year drives engine staleness",
   {pillar: row["stale"]
    for pillar, row in assessment_year_eng["pillars"].items()},
   {pillar: row["stale"]
    for pillar, row in assessment_year_ref["pillars"].items()})

tag_model = copy.deepcopy(ratified_mapping_model)
next(row for row in tag_model["indicators"]
     if row["id"] == "3.4")["tags"].append("ADV")
tag_ref = Scorer(tag_model).run(mapped_obs, intervention_profiles)
tag_eng = engine_run(
    "Synthetic tag mutation", mapped_obs, model_spec=tag_model,
    intervention_profiles=intervention_profiles)
eq("a UC-like free-form tag cannot expand the model use-case bearing set",
   tag_eng["matrix"], tag_ref["matrix"])

blank_class_obs = copy.deepcopy(mapped_obs)
blank_class_obs["2.9"].update({"value": 0, "cls": "", "level": 5})
blank_class_obs["2.9"]["definition_metadata"]["transform_inputs"] = {
    "source_value": 0,
}
blank_class_ref = mapped_scorer.run(blank_class_obs, intervention_profiles)
blank_class_eng = engine_run(
    "Synthetic blank evidence class", blank_class_obs,
    model_spec=ratified_mapping_model,
    intervention_profiles=intervention_profiles)
eq("ratified engine derives a blank evidence class before threshold scoring",
   blank_class_eng["matrix"], blank_class_ref["matrix"])

gap_with_level_obs = copy.deepcopy(mapped_obs)
gap_with_level_obs["2.9"].update({
    "value": "DATA GAP — explicit gap overrides a cached level",
    "cls": "Gap", "level": 1,
})
gap_with_level_ref = mapped_scorer.run(gap_with_level_obs, intervention_profiles)
gap_with_level_eng = engine_run(
    "Synthetic gap with cached level", gap_with_level_obs,
    model_spec=ratified_mapping_model,
    intervention_profiles=intervention_profiles)
eq("ratified engine nulls a cached level on an explicit gap",
   gap_with_level_eng["matrix"], gap_with_level_ref["matrix"])

# Winning reasons are serialized evidence and therefore cannot depend on edge-list order.
dual_block_obs = copy.deepcopy(mapped_obs)
dual_block_obs["7.12"].update({
    "value": "Synthetic documented blocker", "cls": "Documented", "level": 1,
})
dual_block_ref = mapped_scorer.run(dual_block_obs, intervention_profiles)
dual_block_reversed_ref = Scorer(reversed_mapping_model).run(
    dual_block_obs, intervention_profiles)
dual_block_eng = engine_run(
    "Synthetic dual blocker", dual_block_obs,
    model_spec=ratified_mapping_model, intervention_profiles=intervention_profiles)
eq("same-severity gate reasons are sorted canonically",
   dual_block_ref["matrix"]["MKT"]["why"], "2.9, 7.12")
eq("same-severity driver order is independent of edge order",
   dual_block_reversed_ref["matrix"], dual_block_ref["matrix"])
eq("canonical multi-driver output preserves engine/reference parity",
   dual_block_eng["matrix"], dual_block_ref["matrix"])


def value_error_text(call):
    try:
        call()
    except ValueError as error:
        return str(error)
    return ""


definition_model = copy.deepcopy(ratified_mapping_model)
definition_obs = copy.deepcopy(mapped_obs)
definition_ref = Scorer(definition_model).run(
    definition_obs, intervention_profiles)
definition_eng = engine_run(
    "Definition parity", definition_obs, model_spec=definition_model,
    intervention_profiles=intervention_profiles)
eq("ratified observation-definition application preserves matrix parity",
   definition_eng["matrix"], definition_ref["matrix"])

for metadata_field, invalid_value, expected_error in (
        ("geography", "", "definition metadata lacks observation identity"),
        ("source_record_sha256", "A" * 64,
         "definition metadata source record digest is invalid"),
        ("numerator", None,
         "definition metadata numerator must be not_applicable"),
        ("construct_review_sha256", "",
         "definition metadata construct review digest is invalid")):
    invalid_obs = copy.deepcopy(definition_obs)
    invalid_obs["1.1"]["definition_metadata"][metadata_field] = invalid_value
    reference_error = value_error_text(
        lambda rows=invalid_obs: Scorer(definition_model).run(rows))
    engine_error = value_error_text(
        lambda rows=invalid_obs: engine_run(
            "Invalid definition", rows, model_spec=definition_model))
    eq(f"reference rejects invalid ratified metadata {metadata_field}",
       expected_error in reference_error, True)
    eq(f"engine rejects invalid ratified metadata {metadata_field}",
       expected_error in engine_error, True)
    eq(f"definition rejection parity for {metadata_field}",
       engine_error, reference_error)

invalid_tier_obs = copy.deepcopy(definition_obs)
invalid_tier_obs["1.1"]["tier"] = "T5"
eq("ratified definitions enforce their allowed source tiers",
   "source tier is not allowed" in value_error_text(
       lambda: Scorer(definition_model).run(invalid_tier_obs)), True)
eq("engine enforces the same ratified source-tier rule",
   "source tier is not allowed" in value_error_text(
       lambda: engine_run(
           "Invalid tier", invalid_tier_obs, model_spec=definition_model)), True)

downgraded_threshold_obs = copy.deepcopy(definition_obs)
downgraded_threshold_obs["1.1"].update({
    "value": "Synthetic documented substitute.",
    "cls": "Documented", "level": 3, "tier": "T3",
})
downgraded_threshold_obs["1.1"]["definition_metadata"].pop(
    "transform_inputs")
downgraded_reference_error = value_error_text(
    lambda: Scorer(definition_model).run(downgraded_threshold_obs))
downgraded_engine_error = value_error_text(
    lambda: engine_run(
        "Downgraded threshold", downgraded_threshold_obs,
        model_spec=definition_model))
eq("a ratified threshold score cannot masquerade as Documented evidence",
   "threshold score requires a Measured observation"
   in downgraded_reference_error, True)
eq("the engine rejects the same threshold evidence-class downgrade",
   "threshold score requires a Measured observation"
   in downgraded_engine_error, True)
eq("threshold evidence-class rejection preserves scorer parity",
   downgraded_engine_error, downgraded_reference_error)

held_threshold_obs = copy.deepcopy(downgraded_threshold_obs)
held_threshold_obs["1.1"]["level"] = None
eq("a definition-mismatched threshold may remain Documented and held",
   value_error_text(lambda: Scorer(definition_model).run(held_threshold_obs)), "")
eq("the engine preserves the same explicit threshold HOLD",
   value_error_text(lambda: engine_run(
       "Held threshold", held_threshold_obs, model_spec=definition_model)), "")

wrong_scoring_model = copy.deepcopy(definition_model)
wrong_scoring_model["indicator_definitions"]["entries"]["1.1"][
    "scoring"]["direction"] = "lower-is-better"
wrong_scoring_obs = copy.deepcopy(definition_obs)
wrong_scoring_definition = wrong_scoring_model[
    "indicator_definitions"]["entries"]["1.1"]
wrong_scoring_obs["1.1"]["definition_metadata"]["definition_sha256"] = (
    hashlib.sha256(json.dumps(
        wrong_scoring_definition, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest())
eq("ratified definition scoring must match the runtime indicator rule",
   "definition scoring does not match the runtime model" in value_error_text(
       lambda: Scorer(wrong_scoring_model).run(wrong_scoring_obs)), True)
eq("engine rejects the same definition/runtime scoring drift",
   "definition scoring does not match the runtime model" in value_error_text(
       lambda: engine_run(
           "Scoring drift", wrong_scoring_obs,
           model_spec=wrong_scoring_model)), True)

invalid_transform_obs = copy.deepcopy(definition_obs)
invalid_transform_obs["1.1"].update({
    "value": 1000, "cls": "Measured", "level": 2, "tier": "T1",
})
invalid_transform_obs["1.1"]["definition_metadata"]["transform_inputs"] = {
    "source_value": 999,
}
transform_reference_error = value_error_text(
    lambda: Scorer(definition_model).run(invalid_transform_obs))
transform_engine_error = value_error_text(
    lambda: engine_run(
        "Invalid transform", invalid_transform_obs, model_spec=definition_model))
eq("reference scorer recomputes the declared observation transform",
   "does not equal the ratified transform result" in transform_reference_error, True)
eq("engine recomputes the declared observation transform",
   "does not equal the ratified transform result" in transform_engine_error, True)
eq("transform rejection preserves engine/reference parity",
   transform_engine_error, transform_reference_error)

catalogless_model = copy.deepcopy(ratified_mapping_model)
catalogless_model.pop("indicator_definitions")
eq("ratified reference scoring fails closed without a definition catalog",
   "missing ratified definition catalog" in value_error_text(
       lambda: Scorer(catalogless_model).run(mapped_obs)), True)
eq("ratified engine scoring fails closed without a definition catalog",
   "missing ratified definition catalog" in value_error_text(
       lambda: engine_run(
           "Missing catalog", mapped_obs, model_spec=catalogless_model)), True)


root_without_mapping = copy.deepcopy(model)
root_without_mapping.update({"status": "ratified", "ratified": True})
eq("a ratified root cannot silently fall back to legacy mapping in the reference scorer",
   value_error_text(lambda: Scorer(root_without_mapping).run(mapped_obs)),
   "invalid ratified prerequisite_mapping: ratified model root requires a ratified mapping")
eq("a ratified root cannot silently fall back to legacy mapping in the engine",
   value_error_text(lambda: engine_run(
       "Synthetic invalid", mapped_obs, model_spec=root_without_mapping)),
   "invalid ratified prerequisite_mapping: ratified model root requires a ratified mapping")

bad_predicate_model = copy.deepcopy(ratified_mapping_model)
next(edge for edge in bad_predicate_model["prerequisite_mapping"]["edges"]
     if edge["effect"] == "gate"
     and edge["applicability"]["mode"] == "conditional")["applicability"]["predicate"] = {
         "field": "undeclared_profile_fact", "equals": True,
     }
eq("a ratified mapping cannot introduce an undeclared predicate field",
   value_error_text(lambda: Scorer(bad_predicate_model).run(mapped_obs)),
   "invalid ratified prerequisite_mapping: conditional edge predicate is malformed")

bad_precedence_model = copy.deepcopy(ratified_mapping_model)
bad_precedence_model["prerequisite_mapping"]["status_precedence"] = [
    "Unverified", "Blocked", "Partial", "Ready",
]
eq("reference scorer rejects noncanonical status precedence",
   value_error_text(lambda: Scorer(bad_precedence_model).run(mapped_obs)),
   "invalid ratified prerequisite_mapping: status_precedence does not match the ratified schema")
eq("engine rejects noncanonical status precedence",
   value_error_text(lambda: engine_run(
       "Synthetic invalid", mapped_obs, model_spec=bad_precedence_model)),
   "invalid ratified prerequisite_mapping: status_precedence does not match the ratified schema")

bad_always_model = copy.deepcopy(ratified_mapping_model)
next(edge for edge in bad_always_model["prerequisite_mapping"]["edges"]
     if edge["effect"] == "gate"
     and edge["applicability"] == {"mode": "always"})["applicability"]["predicate"] = {
         "field": "uses_personal_data", "equals": True,
     }
eq("reference scorer rejects a predicate hidden on an always edge",
   value_error_text(lambda: Scorer(bad_always_model).run(mapped_obs)),
   "invalid ratified prerequisite_mapping: always edges must use exact always applicability")
eq("engine rejects a predicate hidden on an always edge",
   value_error_text(lambda: engine_run(
       "Synthetic invalid", mapped_obs, model_spec=bad_always_model)),
   "invalid ratified prerequisite_mapping: always edges must use exact always applicability")

bad_none_model = copy.deepcopy(ratified_mapping_model)
next(edge for edge in bad_none_model["prerequisite_mapping"]["edges"]
     if edge["effect"] == "none")["on_prerequisite_status"] = dict(gate_outcomes)
eq("reference scorer rejects outcomes hidden on a none edge",
   value_error_text(lambda: Scorer(bad_none_model).run(mapped_obs)),
   "invalid ratified prerequisite_mapping: none edges cannot declare prerequisite outcomes")
eq("engine rejects outcomes hidden on a none edge",
   value_error_text(lambda: engine_run(
       "Synthetic invalid", mapped_obs, model_spec=bad_none_model)),
   "invalid ratified prerequisite_mapping: none edges cannot declare prerequisite outcomes")

bad_gate_outcomes = copy.deepcopy(ratified_mapping_model)
next(edge for edge in bad_gate_outcomes["prerequisite_mapping"]["edges"]
     if edge["effect"] == "gate")["on_prerequisite_status"]["Absent"] = "Ready"
eq("reference scorer rejects noncanonical gate outcomes",
   value_error_text(lambda: Scorer(bad_gate_outcomes).run(mapped_obs)),
   "invalid ratified prerequisite_mapping: gate outcomes do not match the ratified schema")
eq("engine rejects noncanonical gate outcomes",
   value_error_text(lambda: engine_run(
       "Synthetic invalid", mapped_obs, model_spec=bad_gate_outcomes)),
   "invalid ratified prerequisite_mapping: gate outcomes do not match the ratified schema")

bad_risk_outcomes = copy.deepcopy(ratified_mapping_model)
next(edge for edge in bad_risk_outcomes["prerequisite_mapping"]["edges"]
     if edge["effect"] == "delivery_risk")["on_prerequisite_status"]["Absent"] = "Blocked"
eq("reference scorer rejects noncanonical delivery-risk outcomes",
   value_error_text(lambda: Scorer(bad_risk_outcomes).run(mapped_obs)),
   "invalid ratified prerequisite_mapping: delivery-risk outcomes do not match the ratified schema")
eq("engine rejects noncanonical delivery-risk outcomes",
   value_error_text(lambda: engine_run(
       "Synthetic invalid", mapped_obs, model_spec=bad_risk_outcomes)),
   "invalid ratified prerequisite_mapping: delivery-risk outcomes do not match the ratified schema")
eq("an intervention profile rejects unknown facts",
   value_error_text(lambda: mapped_scorer.run(
       mapped_obs, {"ADV": {"undeclared_profile_fact": True}})),
   "intervention profile for ADV has invalid facts")

eq("legacy reference output carries no mapping version pins",
   set(("model_version", "model_revision", "prerequisite_mapping_revision"))
   & set(stale_ref), set())
eq("legacy engine output carries no mapping version pins",
   set(("model_version", "model_revision", "prerequisite_mapping_revision"))
   & set(stale_eng), set())
eq("legacy matrix cells carry no mapping-only fields",
   set(("active_gates", "conditional_constraints", "delivery_risks",
        "status_reason")) & set(stale_ref["matrix"]["ADV"]), set())

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
# The readiness threshold duplicated a band edge as a separate constant, and when the
# bands were recut it stayed behind, leaving a column that could read "Partial, thin
# enablers" while its enablers were Established. Breaking this invariant is a decision.
_est = next(b for b in model["bands"] if b["name"] == "Established")
inv("readiness threshold is the Established band's lower edge",
    model["config"]["readiness_threshold"] == _est["lo"],
    f"threshold {model['config']['readiness_threshold']} vs Established lo {_est['lo']}")

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

# --- DAR outline bindings, foresight, candidate indicators (E4, F1, F3, F4) ---
out = model["dar_outline"]
ids = {i["id"] for i in model["indicators"]}
inv("11 DAR chapters, numbered 1-10 plus annex",
    [c["n"] for c in out] == [str(k) for k in range(1, 11)] + ["A"])
inv("every chapter declares kind, content, binding and note",
    all(c.get("kind") in ("diagnostic", "prescriptive") and c.get("content")
        and c.get("binding") and c.get("note") for c in out))
inv("bindings name only declared pillars",
    all(set(c["binding"]["pillars"]) <= set(model["pillars"]) for c in out))
inv("bindings name only declared use cases",
    all(set(c["binding"]["use_cases"]) <= set(model["use_cases"]) for c in out))
inv("bindings name only real indicators",
    all(set(c["binding"]["indicators"]) - {"*"} <= ids for c in out),
    str([i for c in out for i in c["binding"]["indicators"] if i != "*" and i not in ids]))
_pre = {i["id"] for i in model["indicators"] if i["prerequisite"]}
inv("bindings name only real prerequisites",
    all(set(c["binding"]["prerequisites"]) - {"*"} <= _pre for c in out),
    str([x for c in out for x in c["binding"]["prerequisites"] if x != "*" and x not in _pre]))
inv("bindings name only declared derived sources",
    all(set(c["binding"]["derived"]) <= set(model["derived_sources"]) for c in out))
inv("the costs chapter claims no evidentiary basis it does not have",
    "NO COST, BUDGET OR FINANCING DATA" in next(c for c in out if c["n"] == "5")["note"].upper()
    and not next(c for c in out if c["n"] == "5")["binding"]["pillars"])
inv("chapters 3-10 are prescriptive; 1, 2 and the annex are diagnostic",
    all(c["kind"] == "prescriptive" for c in out if c["n"] not in ("1", "2", "A"))
    and all(c["kind"] == "diagnostic" for c in out if c["n"] in ("1", "2", "A")))
inv("the annex may cite everything", 
    next(c for c in out if c["n"] == "A")["binding"]["derived"] == list(model["derived_sources"]))

fs = model["foresight"]
inv("foresight declares a named, unratified method with three steps",
    fs["ratified"] is False and fs["method"] and len(fs["steps"]) == 3)
inv("foresight steps are scenarios, preferred future, backcasting",
    [x["id"] for x in fs["steps"]] == ["scenarios", "preferred_future", "backcasting"])
inv("milestones bind to an indicator with a target level and year",
    fs["milestone_binding"]["fields"] == ["indicator_id", "target_level", "target_year"])
inv("milestones with no fitting indicator fall back to a candidate",
    "candidate_indicators" in fs["milestone_binding"]["fallback"].lower().replace(" ", "_")
    or "CANDIDATE" in fs["milestone_binding"]["fallback"])

ci = model["candidate_indicators"]
inv("candidate indicators are barred from every aggregate",
    all(any(k in n for n in ci["never"])
        for k in ("pillar mean", "layer mean", "use-case mean", "prerequisite", "readiness matrix")),
    str(ci["never"]))
inv("candidate ids follow the existing A1-CAND- shape",
    __import__("re").match(ci["id_pattern"], "A1-CAND-IRR") is not None)
inv("promotion to a scored indicator is never automatic",
    "never automatic" in ci["disposition"])

print(f"model-only parity: {checks - len(fails)}/{checks} checks match")
if fails:
    print("\nThe model file is NOT yet sufficient to score from:")
    for f in fails[:25]:
        print("  -", f)
    sys.exit(1)
print("DAMM-v1.7-model.json is canonical: every derived figure reproduces from the model alone.")
