#!/usr/bin/env python3
"""A scorer that reads ONLY the exported model file plus observations.

This exists to prove the model export is COMPLETE. It imports nothing from the engine: if a
rule still lives in engine code rather than in the model file, this scorer produces a
different answer and `test_model_parity.py` fails. That is the whole point — it is the guard
that keeps `DAMM-v1.7-model.json` canonical rather than merely descriptive, and it is the
reference any consumer (DAR Studio) implements against.

Observations payload: {indicator_id: {value, cls, level, year, src, tier, url}} — the same
shape the engine consumes, kept separate from the model as the release gate requires.
"""
import hashlib, json, math
from decimal import Decimal, ROUND_HALF_UP


def r2(x):
    """Half-up to 2dp — the workbook is the source of truth and Python's banker's rounding
    disagrees with it at exact .xx5, which would band a mean differently."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


_PREREQUISITE_STATUSES = ("Absent", "Unverified", "Present (narrow)", "Present")
_READINESS_STATUSES = ("Blocked", "Unverified", "Partial", "Ready")
_GATE_OUTCOMES = {
    "Absent": "Blocked", "Unverified": "Unverified",
    "Present (narrow)": "Partial", "Present": "no_change",
}
_DELIVERY_RISK_OUTCOMES = {
    "Absent": "flag", "Unverified": "verify",
    "Present (narrow)": "flag_narrow", "Present": "no_change",
}
_INTERVENTION_PROFILE_FIELDS = frozenset({
    "targeted_farmer_level_delivery",
    "cross_organization_agricultural_data_sharing",
    "cross_ministerial_delivery", "moag_led_or_owned",
    "uses_personal_data", "uses_farm_level_data", "ai_enabled",
})


def _definition_contract_error(indicator_id, row, model):
    catalog = model.get("indicator_definitions")
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    if entries is None:
        return "missing ratified definition catalog"
    definition = entries.get(indicator_id) if isinstance(entries, dict) else None
    metadata = row.get("definition_metadata") if isinstance(row, dict) else None
    if not isinstance(definition, dict) or not isinstance(metadata, dict):
        return "missing ratified definition metadata"
    encoded = json.dumps(
        definition, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")
    measure = definition.get("measure")
    policy = definition.get("source_policy")
    scoring = definition.get("scoring")
    model_indicators = model.get("indicators")
    indicator = next((item for item in (
                          model_indicators if isinstance(model_indicators, list) else [])
                      if isinstance(item, dict)
                      and item.get("id") == indicator_id), None)
    expected = {
        "definition_version": definition.get("definition_version"),
        "definition_sha256": hashlib.sha256(encoded).hexdigest(),
        "unit": measure.get("unit") if isinstance(measure, dict) else None,
        "population_scope": (measure.get("population_scope")
                             if isinstance(measure, dict) else None),
        "reference_period_rule": (measure.get("reference_period")
                                  if isinstance(measure, dict) else None),
        "transform": measure.get("transform") if isinstance(measure, dict) else None,
    }
    if any(metadata.get(field) != value for field, value in expected.items()):
        return "definition metadata differs from the ratified catalog"
    if metadata.get("definition_match") is not True:
        return "definition match was not affirmed"
    if (not isinstance(policy, dict)
            or not isinstance(policy.get("allowed_tiers"), list)
            or not policy["allowed_tiers"]
            or policy.get("minimum_confirmation")
            != "One load-bearing source plus construct review"
            or not isinstance(scoring, dict)
            or scoring.get("missing_rule") != "DATA GAP"
            or scoring.get("mismatch_rule") != "HOLD"):
        return "ratified definition policy is not executable"
    if row.get("cls") != "Gap" and row.get("tier") not in policy["allowed_tiers"]:
        return "source tier is not allowed by the ratified definition"
    expected_method = (indicator.get("method")
                       if isinstance(indicator, dict) else None)
    expected_direction = (indicator.get("direction")
                          if isinstance(indicator, dict) else None)
    expected_thresholds = (indicator.get("thresholds")
                           if isinstance(indicator, dict) else None)
    if (not isinstance(scoring, dict)
            or scoring.get("method") != expected_method
            or scoring.get("direction") != expected_direction
            or (expected_method == "threshold"
                and scoring.get("cuts") != expected_thresholds)
            or (expected_method == "ladder" and "cuts" in scoring)):
        return "definition scoring does not match the runtime model"
    if (expected_method == "threshold" and row.get("level") is not None
            and row.get("cls") not in ("Measured", "Gap")):
        return "threshold score requires a Measured observation"
    if expected_method == "ladder" and row.get("cls") == "Measured":
        return "ladder observation cannot be Measured"
    if any(not isinstance(metadata.get(field), str)
           or not metadata[field].strip()
           for field in ("geography", "observation_period", "edition")):
        return "definition metadata lacks observation identity"
    if type(metadata.get("proxy")) is not bool:
        return "definition metadata proxy flag is not boolean"
    proxy_reason = metadata.get("proxy_justification")
    if (metadata["proxy"]
            and (not isinstance(proxy_reason, str)
                 or len(" ".join(proxy_reason.split()).strip(" .")) < 8)):
        return "proxy observation lacks a specific justification"
    source_digest = metadata.get("source_record_sha256")
    if (not isinstance(source_digest, str) or len(source_digest) != 64
            or any(character not in "0123456789abcdef"
                   for character in source_digest)):
        return "definition metadata source record digest is invalid"
    review_digest = metadata.get("construct_review_sha256")
    if (not isinstance(review_digest, str) or len(review_digest) != 64
            or any(character not in "0123456789abcdef"
                   for character in review_digest)):
        return "definition metadata construct review digest is invalid"
    for field in ("numerator", "denominator"):
        contract_value = measure.get(field) if isinstance(measure, dict) else None
        actual_value = metadata.get(field)
        if contract_value == "not_applicable":
            if actual_value != "not_applicable":
                return f"definition metadata {field} must be not_applicable"
        elif not ((isinstance(actual_value, str) and actual_value.strip())
                  or (type(actual_value) in (int, float)
                      and actual_value == actual_value
                      and actual_value not in (float("inf"), float("-inf")))):
            return f"definition metadata lacks an actual {field}"
    preferred = policy.get("preferred_series") if isinstance(policy, dict) else []
    source_series = metadata.get("source_series")
    if not isinstance(source_series, str) or not source_series.strip():
        return "definition metadata lacks a source series"
    fallback = metadata.get("fallback_justification")
    if (preferred and source_series not in preferred
            and (not isinstance(fallback, str)
                 or len(" ".join(fallback.split()).strip(" .")) < 8)):
        return "non-preferred source has no fallback justification"
    calibration_refs = model.get("indicator_calibration_refs")
    expected_calibration = (calibration_refs.get(indicator_id)
                            if isinstance(calibration_refs, dict) else None)
    if expected_method == "threshold" and expected_calibration is None:
        return "threshold row has no ratified calibration reference"
    if expected_calibration is not None:
        if metadata.get("calibration_ref") != expected_calibration:
            return "calibration reference differs from the ratified model"
    elif "calibration_ref" in metadata:
        return "ladder row names a threshold calibration"
    if row.get("cls") == "Measured":
        value = row.get("value")
        inputs = metadata.get("transform_inputs")
        transform = measure.get("transform") if isinstance(measure, dict) else None
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not isinstance(inputs, dict)):
            return "Measured observation lacks numeric transform inputs"
        try:
            if transform == "identity" and set(inputs) == {"source_value"}:
                expected_value = inputs["source_value"]
            elif transform == "raw / 100" and set(inputs) == {"source_value"}:
                expected_value = inputs["source_value"] / 100
            elif (transform == "monthly_price / (annual_GNI_per_capita / 12) * 100"
                  and set(inputs) == {"monthly_price", "annual_gni_per_capita"}
                  and inputs["annual_gni_per_capita"] != 0):
                expected_value = (inputs["monthly_price"]
                                  / (inputs["annual_gni_per_capita"] / 12) * 100)
            elif (transform == "max(male_rate - female_rate, 0)"
                  and set(inputs) == {"male_rate", "female_rate"}):
                expected_value = max(
                    inputs["male_rate"] - inputs["female_rate"], 0)
            else:
                return "Measured observation uses an unsupported transform input contract"
        except (TypeError, ZeroDivisionError):
            return "Measured observation transform inputs are not numeric"
        if (type(expected_value) not in (int, float)
                or not math.isfinite(expected_value)
                or not math.isclose(
                    value, expected_value, rel_tol=1e-9, abs_tol=1e-9)):
            return "Measured value does not equal the ratified transform result"
    return None


def _mapping_error(message):
    raise ValueError("invalid ratified prerequisite_mapping: " + message)


def _valid_predicate(predicate):
    if not isinstance(predicate, dict):
        return False
    if set(predicate) == {"field", "equals"}:
        return (predicate["field"] in _INTERVENTION_PROFILE_FIELDS
                and type(predicate["equals"]) is bool)
    for operator in ("any", "all"):
        if set(predicate) == {operator}:
            children = predicate[operator]
            return (isinstance(children, list) and bool(children)
                    and all(_valid_predicate(child) for child in children))
    return False


def _predicate_result(predicate, profile):
    """Evaluate a boolean intervention predicate with an explicit unknown state."""
    if "field" in predicate:
        field = predicate["field"]
        if field not in profile:
            return None
        if type(profile[field]) is not bool:
            raise ValueError(
                f"intervention profile field {field!r} must be boolean")
        return profile[field] == predicate["equals"]
    operator = "any" if "any" in predicate else "all"
    results = [_predicate_result(child, profile) for child in predicate[operator]]
    if operator == "any":
        if any(result is True for result in results):
            return True
        return None if any(result is None for result in results) else False
    if any(result is False for result in results):
        return False
    return None if any(result is None for result in results) else True


def _ratified_prerequisite_mapping(model, use_case_ids, prerequisite_ids):
    """Return a complete active mapping, or None while the model remains legacy."""
    if not isinstance(model, dict):
        return None
    mapping = model.get("prerequisite_mapping")
    if model.get("ratified") is not True:
        return None
    if model.get("status") != "ratified":
        _mapping_error("ratified model root must have status ratified")
    if not isinstance(mapping, dict) or mapping.get("ratified") is not True:
        _mapping_error("ratified model root requires a ratified mapping")

    if mapping.get("decision_id") != "13.3" or mapping.get("status") != "ratified":
        _mapping_error("decision/status is not ratified 13.3")
    if (type(mapping.get("revision")) is not int or mapping["revision"] < 1
            or not isinstance(model.get("version"), str) or not model["version"].strip()
            or type(model.get("revision")) is not int or model["revision"] < 1):
        _mapping_error("model and mapping revisions must be pinned")
    config = model.get("config")
    readiness_threshold = (config.get("readiness_threshold")
                           if isinstance(config, dict) else None)
    if (type(readiness_threshold) not in (int, float)
            or not 0 < readiness_threshold <= 5):
        _mapping_error("model readiness threshold is missing or invalid")
    if (not isinstance(mapping.get("use_case_ids"), list)
            or len(mapping["use_case_ids"]) != len(use_case_ids)
            or any(not isinstance(item, str)
                   for item in mapping["use_case_ids"])
            or set(mapping["use_case_ids"]) != set(use_case_ids)
            or not isinstance(mapping.get("prerequisite_ids"), list)
            or len(mapping["prerequisite_ids"]) != len(prerequisite_ids)
            or any(not isinstance(item, str)
                   for item in mapping["prerequisite_ids"])
            or set(mapping["prerequisite_ids"]) != set(prerequisite_ids)):
        _mapping_error("declared use-case/prerequisite inventories do not match")

    precedence = mapping.get("status_precedence")
    if precedence != list(_READINESS_STATUSES):
        _mapping_error("status_precedence does not match the ratified schema")
    if mapping.get("conditional_policy") != {
            "missing_profile": "report_condition_without_mutating_base_status",
            "true": "activate_edge",
            "false": "ignore_edge"}:
        _mapping_error("conditional_policy is missing or unsupported")

    edges = mapping.get("edges")
    expected_pairs = {(prerequisite_id, use_case_id)
                      for prerequisite_id in prerequisite_ids
                      for use_case_id in use_case_ids}
    if not isinstance(edges, list) or len(edges) != 72 or len(expected_pairs) != 72:
        _mapping_error("edges must be the complete 12 x 6 graph")

    actual_pairs = []
    for edge in edges:
        if (not isinstance(edge, dict)
                or not isinstance(edge.get("prerequisite_id"), str)
                or not isinstance(edge.get("use_case_id"), str)):
            _mapping_error("every edge must name string prerequisite/use-case ids")
        actual_pairs.append((edge["prerequisite_id"], edge["use_case_id"]))
        if (not isinstance(edge.get("rationale"), str) or not edge["rationale"].strip()
                or not isinstance(edge.get("basis"), list) or not edge["basis"]
                or any(not isinstance(item, str) or not item.strip()
                       for item in edge["basis"])
                or edge.get("decision_status") != "ratified"):
            _mapping_error("every edge needs ratified rationale and basis metadata")

        effect = edge.get("effect")
        applicability = edge.get("applicability")
        mode = applicability.get("mode") if isinstance(applicability, dict) else None
        if effect not in ("gate", "delivery_risk", "none"):
            _mapping_error("edge effect is outside gate/delivery_risk/none")
        if effect == "none":
            if applicability != {"mode": "never"}:
                _mapping_error("none edges must use exact never applicability")
            if "on_prerequisite_status" in edge:
                _mapping_error("none edges cannot declare prerequisite outcomes")
            continue
        if mode not in ("always", "conditional"):
            _mapping_error("positive edges must be always or conditional")
        if mode == "always":
            if applicability != {"mode": "always"}:
                _mapping_error("always edges must use exact always applicability")
        elif (set(applicability) != {"mode", "predicate"}
              or not _valid_predicate(applicability.get("predicate"))):
            _mapping_error("conditional edge predicate is malformed")

        outcomes = edge.get("on_prerequisite_status")
        if not isinstance(outcomes, dict) or set(outcomes) != set(_PREREQUISITE_STATUSES):
            _mapping_error("positive edges must declare all prerequisite outcomes")
        if effect == "gate" and outcomes != _GATE_OUTCOMES:
            _mapping_error("gate outcomes do not match the ratified schema")
        if effect == "delivery_risk" and outcomes != _DELIVERY_RISK_OUTCOMES:
            _mapping_error("delivery-risk outcomes do not match the ratified schema")

    if len(set(actual_pairs)) != 72 or set(actual_pairs) != expected_pairs:
        _mapping_error("edge pairs are duplicated or incomplete")
    effects = {edge["effect"] for edge in edges}
    if not {"gate", "delivery_risk", "none"} <= effects:
        _mapping_error("mapping must exercise gate, delivery_risk, and none effects")
    if not any(edge["effect"] == "gate"
               and edge["applicability"] == {"mode": "always"}
               for edge in edges):
        _mapping_error("mapping must include an always gate")
    return mapping


def _mapped_readiness(mapping, edges, prerequisite_statuses, mean_readiness,
                      readiness_threshold, intervention_profile):
    """Evaluate one use-case edge column without letting risks mutate readiness."""
    active_gates, conditional_constraints, delivery_risks = [], [], []
    candidates = []
    for edge in edges:
        if edge["effect"] == "none":
            continue
        prerequisite_id = edge["prerequisite_id"]
        prerequisite_status = prerequisite_statuses[prerequisite_id]["status"]
        action = edge["on_prerequisite_status"][prerequisite_status]
        mode = edge["applicability"]["mode"]
        evaluation = True
        if mode == "conditional":
            evaluation = _predicate_result(
                edge["applicability"]["predicate"], intervention_profile)
            conditional_constraints.append({
                "prerequisite_id": edge["prerequisite_id"],
                "effect": edge["effect"],
                "predicate": edge["applicability"]["predicate"],
                "prerequisite_status": prerequisite_status,
                "outcome_if_active": action,
                "evaluation": ("active" if evaluation is True else
                               "inactive" if evaluation is False else "unresolved"),
            })
        if evaluation is not True:
            continue

        if edge["effect"] == "gate":
            gate = {
                "prerequisite_id": prerequisite_id,
                "prerequisite_status": prerequisite_status,
                "outcome": action,
                "applicability": mode,
            }
            active_gates.append(gate)
            if action != "no_change":
                candidates.append((action, {
                    "type": "gate", "prerequisite_id": prerequisite_id,
                    "prerequisite_status": prerequisite_status,
                }))
        elif edge["effect"] == "delivery_risk" and action != "no_change":
            delivery_risks.append({
                "prerequisite_id": prerequisite_id,
                "prerequisite_status": prerequisite_status,
                "action": action,
                "applicability": mode,
            })

    if mean_readiness is not None and mean_readiness < readiness_threshold:
        candidates.append(("Partial", {
            "type": "readiness_mean", "mean_readiness": mean_readiness,
            "threshold": readiness_threshold,
        }))
    rank = {status: index for index, status in enumerate(mapping["status_precedence"])}
    status = min(candidates, key=lambda item: rank[item[0]])[0] if candidates else "Ready"
    drivers = [driver for outcome, driver in candidates if outcome == status]
    drivers.sort(key=lambda item: (
        0 if item["type"] == "gate" else 1,
        item.get("prerequisite_id", ""),
    ))

    active_gates.sort(key=lambda item: item["prerequisite_id"])
    conditional_constraints.sort(
        key=lambda item: (item["prerequisite_id"], item["effect"]))
    delivery_risks.sort(key=lambda item: item["prerequisite_id"])
    gate_drivers = [driver["prerequisite_id"] for driver in drivers
                    if driver["type"] == "gate"]
    why = (", ".join(gate_drivers) if gate_drivers else
           "thin enablers" if any(driver["type"] == "readiness_mean"
                                  for driver in drivers) else "")
    return {
        "status": status,
        "why": why,
        "active_gates": active_gates,
        "conditional_constraints": conditional_constraints,
        "delivery_risks": delivery_risks,
        "status_reason": {
            "status": status,
            "status_precedence": list(mapping["status_precedence"]),
            "drivers": drivers,
        },
    }


class Scorer:
    def __init__(self, model):
        self.m = model
        self.ind = {i["id"]: i for i in model["indicators"]}
        self.cfg = model["config"]
        self.uc_ids = list(model["use_cases"].keys())
        self.band_level = {
            band["name"]: index + 1 for index, band in enumerate(model["bands"])
        }

    # --- per-row -----------------------------------------------------------------
    def evidence_class(self, r):
        v = r.get("value")
        if v is None or v == "":                      return ""
        if isinstance(v, (int, float)):               return "Measured"
        if "DATA GAP" in str(v).upper():              return "Gap"
        if r.get("src") and r.get("tier") != "T5":    return "Documented"
        return "Judged"

    def level(self, iid, r, cls):
        if cls in ("", "Gap"):                        return None
        d = self.ind[iid]
        # A non-null Measured level is a reviewable cache, not an independent input.
        # Recompute it so a threshold revision cannot leave old levels in force.  Null is
        # an explicit construct/ratification hold and must not be reactivated here.
        if (cls == "Measured" and d["thresholds"]
                and ("level" not in r or r.get("level") is not None)):
            v, th = r["value"], d["thresholds"]
            hi = d["direction"] == "higher-is-better"
            lv = 1
            for k, t in enumerate(th):
                if (hi and v >= t) or (not hi and v <= t):
                    lv = k + 2
            return lv
        return r.get("level")

    def stale(self, r, cls):
        y = r.get("year")
        return bool(y and cls != "Gap" and y < self.cfg["assessment_year"] - self.cfg["staleness_years"])

    # Ruling 13.1. The band names a level, and the margin is measured from that level
    # rather than from the interval midpoint, because the two end bands are half-width.
    def margin(self, x):
        b = self.band(x)
        return r2(x - self.band_level[b]) if b in self.band_level else None

    def band(self, x):
        for b in self.m["bands"]:
            if b["lo"] <= x < b["hi"]:
                return b["name"]
        return "—"

    # --- assessment --------------------------------------------------------------
    def run(self, obs, intervention_profiles=None):
        mapping = _ratified_prerequisite_mapping(
            self.m, self.uc_ids,
            [iid for iid, definition in self.ind.items()
             if definition["prerequisite"]])
        rows = {}
        for iid, d in self.ind.items():
            r = obs[iid]
            cls = r.get("cls") or self.evidence_class(r)
            if self.m.get("ratified") is True:
                contract_row = dict(r, cls=cls)
                contract_error = _definition_contract_error(
                    iid, contract_row, self.m)
                if contract_error:
                    raise ValueError(
                        f"invalid ratified observation {iid}: {contract_error}")
            lvl = self.level(iid, r, cls)
            rows[iid] = {
                **dict(r), "cls": cls, "level": lvl,
                "stale": self.stale(r, cls), "name": d["name"],
                "pillar": d["pillar"], "layer": d["layer"],
                "uc": list(d["use_cases"]) + list(d["tags"]),
                "prereq": d["prerequisite"] or "",
                "kind": "t" if d["thresholds"] else "l",
            }

        out = {
            "indicators": rows, "pillars": {}, "layers": {},
            "prereq": {}, "matrix": {},
        }

        for p in self.m["pillars"]:
            rs = [v for v in rows.values() if v["pillar"] == p]
            lv = [v["level"] for v in rs if v["level"] is not None]
            comp = {c: sum(1 for v in rs if v["cls"] == c) for c in ("Measured", "Documented", "Judged", "Gap")}
            rated = len(lv)
            held = sum(1 for v in rs if v["level"] is None and v["cls"] != "Gap")
            jr = sum(1 for v in rs if v["cls"] == "Judged" and v["level"] is not None)
            mean = r2(sum(lv) / len(lv)) if lv else None
            out["pillars"][p] = {
                "n": len(rs), "rated": rated, "held": held, "mean": mean,
                "band": self.band(mean) if mean else "Not rated",
                "margin": self.margin(mean) if mean else None,
                "weak": (jr + comp["Gap"] + held) > (rated - jr),
                "comp": comp, "stale": sum(1 for v in rs if v["stale"]),
            }

        for L in self.m["layers"]:
            lv = [v["level"] for v in rows.values() if v["layer"] == L and v["level"] is not None]
            out["layers"][L] = r2(sum(lv) / len(lv)) if lv else None

        F, T = out["layers"]["Foundation"], out["layers"]["Transformation"]
        out["leapfrog"] = {
            "gap": r2(F - T) if F and T else None,
            "flag": (F and T and abs(F - T) > self.cfg["leapfrog_threshold"]),
            "reading": (
                "Transformation running ahead of foundations — leapfrog fragility"
                if F and T and T - F > self.cfg["leapfrog_threshold"]
                else "Foundations ahead of transformation — execution gap"
                if F and T and F - T > self.cfg["leapfrog_threshold"]
                else "No structural flag"),
        }

        for iid, d in self.ind.items():
            if not d["prerequisite"]:
                continue
            v = rows[iid]
            if v["cls"] == "Gap" or v["level"] is None: st = "Unverified"
            elif v["level"] >= 3:                       st = "Present"
            elif v["level"] == 2:                       st = "Present (narrow)"
            else:                                       st = "Absent"
            out["prereq"][iid] = {
                "name": d["name"], "kind": d["prerequisite"], "status": st,
            }

        P = out["prereq"]
        if mapping is not None:
            if intervention_profiles is None:
                intervention_profiles = {}
            if not isinstance(intervention_profiles, dict):
                raise ValueError("intervention_profiles must be a use-case keyed object")
            if any(use_case_id not in self.uc_ids
                   for use_case_id in intervention_profiles):
                raise ValueError("intervention_profiles names an unknown use case")
            for use_case_id, profile in intervention_profiles.items():
                if not isinstance(profile, dict):
                    raise ValueError(
                        f"intervention profile for {use_case_id} must be an object")
                if (set(profile) - _INTERVENTION_PROFILE_FIELDS
                        or any(type(value) is not bool for value in profile.values())):
                    raise ValueError(
                        f"intervention profile for {use_case_id} has invalid facts")
            edges_by_use_case = {
                uc: [edge for edge in mapping["edges"] if edge["use_case_id"] == uc]
                for uc in self.uc_ids
            }
        uni = lambda s: [i for i, v in P.items() if v["kind"] == "UNIVERSAL" and v["status"] == s]
        blk, unv, nrw = uni("Absent"), uni("Unverified"), uni("Present (narrow)")

        for uc in self.uc_ids:
            pres = [(i, v["status"]) for i, v in P.items()
                    if v["kind"].startswith("UC:")
                    and uc in v["kind"].split(":", 1)[1].split(",")]
            bear = [i for i, d in self.ind.items()
                    if (uc in d["use_cases"] or "ALL" in d["tags"]) and rows[i]["level"] is not None]
            # Ruling 13.12: need, readiness and outcome are separated, and only the
            # readiness mean decides the column.
            def _rm(want):
                v = [rows[i]["level"] for i in bear
                     if {"A1": "need", "O1": "outcome"}.get(self.ind[i]["pillar"],
                                                            "enabler") == want]
                return r2(sum(v) / len(v)) if v else None
            mean_readiness, mean_need, mean_outcome = _rm("enabler"), _rm("need"), _rm("outcome")
            basis = {"need": 0, "outcome": 0, "enabler": 0}
            for indicator_id in bear:
                indicator_role = {
                    "A1": "need", "O1": "outcome",
                }.get(self.ind[indicator_id]["pillar"], "enabler")
                basis[indicator_role] += 1

            if mapping is None:
                if blk:                                        st, why = "Blocked", "Universal: " + ", ".join(blk)
                elif any(s == "Absent" for _, s in pres):      st, why = "Blocked", ", ".join(i for i, s in pres if s == "Absent")
                elif unv:                                      st, why = "Unverified", "universal unverified: " + ", ".join(unv)
                elif any(s == "Unverified" for _, s in pres):  st, why = "Unverified", ", ".join(i for i, s in pres if s == "Unverified")
                elif any("narrow" in s for _, s in pres) or (mean_readiness and mean_readiness < self.cfg["readiness_threshold"]):
                    st = "Partial"; why = ", ".join(i for i, s in pres if "narrow" in s) or "thin enablers"
                elif nrw:                                      st, why = "Partial", "universal narrow: " + ", ".join(nrw)
                else:                                          st, why = "Ready", ""
                out["matrix"][uc] = {
                    "status": st, "why": why,
                    "prereqs": pres, "basis": basis,
                    "mean_readiness": mean_readiness,
                    "mean_need": mean_need, "mean_outcome": mean_outcome,
                    "n_bearing": len(bear),
                    "mean_driven": st == "Partial" and why == "thin enablers",
                }
            else:
                profile = intervention_profiles.get(uc, {})
                mapped = _mapped_readiness(
                    mapping, edges_by_use_case[uc], P, mean_readiness,
                    self.cfg["readiness_threshold"], profile)
                mapped_prereqs = [
                    (gate["prerequisite_id"], gate["prerequisite_status"])
                    for gate in mapped["active_gates"]
                ]
                out["matrix"][uc] = {
                    "mean_readiness": mean_readiness,
                    "mean_need": mean_need, "mean_outcome": mean_outcome,
                    "n_bearing": len(bear),
                    "basis": basis, "prereqs": mapped_prereqs,
                    "mean_driven": any(
                        driver["type"] == "readiness_mean"
                        for driver in mapped["status_reason"]["drivers"]),
                    **mapped,
                }
        rated_rows = [
            (indicator_id, row) for indicator_id, row in rows.items()
            if row["level"] is not None
        ]
        out["constraints"] = [
            {
                "id": indicator_id, "name": row["name"],
                "level": row["level"], "pillar": row["pillar"],
                "prereq": bool(row["prereq"]),
            }
            for indicator_id, row in sorted(
                rated_rows, key=lambda item: (item[1]["level"], item[0]))[:12]
        ]
        out["kpi"] = [
            {
                "id": indicator_id, "name": row["name"],
                "value": row["value"], "year": row["year"], "src": row["src"],
            }
            for indicator_id, row in rows.items()
            if row["cls"] == "Measured" and row["pillar"] in ("A1", "O1")
        ]
        out["verify"] = [
            {"id": indicator_id, "name": row["name"], "cls": row["cls"]}
            for indicator_id, row in rows.items()
            if row["cls"] in ("Gap", "Judged")
        ]
        out["refresh"] = [
            {"id": indicator_id, "name": row["name"], "year": row["year"]}
            for indicator_id, row in rows.items() if row["stale"]
        ]
        out["counts"] = {c: sum(1 for v in rows.values() if v["cls"] == c)
                         for c in ("Measured", "Documented", "Judged", "Gap")}
        out["rated"] = sum(1 for v in rows.values() if v["level"] is not None)
        out["held"] = sum(1 for v in rows.values() if v["level"] is None and v["cls"] != "Gap")
        if mapping is not None:
            out["model_version"] = self.m["version"]
            out["model_revision"] = self.m["revision"]
            out["prerequisite_mapping_revision"] = mapping["revision"]
        return out
