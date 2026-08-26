#!/usr/bin/env python3
"""Checks for the roadmap generator. No keys, no network.

Three rules decide whether a document may be written: a chapter may cite only what its
binding allows, every figure must trace to the engine, and the gate blocks the emit.

    python3 test_generate_dar.py
"""
import copy, hashlib, io, json, os, re, shutil, sys, tempfile, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_dar as D

FAILED, COUNT = [], 0


def check(label, got, want):
    global COUNT
    COUNT += 1
    ok = (got == want) if isinstance(want, (list, bool, int, float)) else (want in str(got))
    if not ok:
        FAILED.append(f"{label}\n    got:  {got}\n    want: {want}")


def section(t):
    print(f"\n## {t}")


BINDING = {"pillars": ["A1", "C1"], "indicators": ["1.1"], "use_cases": ["ADV"],
           "prerequisites": ["2.1"], "derived": ["matrix"]}


section("A chapter may cite only what its binding allows (E4)")

check("citing inside the binding is clean",
      D.binding_gate({"pillars": ["A1"], "indicators": ["1.1"], "use_cases": [],
                      "prerequisites": []}, BINDING), [])

check("a pillar outside the binding is caught",
      # A financing chapter reaching for connectivity indicators reads perfectly fluently
      # and is wrong. This is the only mechanism that catches it before a reader does.
      D.binding_gate({"pillars": ["E1"], "indicators": [], "use_cases": [],
                      "prerequisites": []}, BINDING), ["pillar E1"])

check("an indicator outside the binding is caught",
      D.binding_gate({"pillars": [], "indicators": ["7.12"], "use_cases": [],
                      "prerequisites": []}, BINDING), ["indicator 7.12"])

check("several violations are all reported",
      len(D.binding_gate({"pillars": ["E1"], "indicators": ["9.9"], "use_cases": ["FIN"],
                          "prerequisites": []}, BINDING)), 3)

check("every diagnostic sentence can bind to an exact pack origin",
      D.claim_provenance_gate(
          "The A1 pillar is advanced. Its evidence is incomplete.",
          [{"text": "The A1 pillar is advanced.",
            "basis": "evidence",
            "source_refs": ["pillar:A1:mean"]},
           {"text": "Its evidence is incomplete.",
            "basis": "evidence",
            "source_refs": ["pillar:A1:n"]}],
          {"pillar:A1:mean", "pillar:A1:n"}, require_all=True), [])

check("an unbound qualitative diagnostic sentence is caught",
      D.claim_provenance_gate(
          "Egypt has universal rural broadband coverage.", [],
          {"pillar:A1:mean"}, require_all=True),
      "unbound diagnostic sentence")

check("a diagnostic claim cannot cite an origin outside its pack",
      D.claim_provenance_gate(
          "The A1 pillar is advanced.",
          [{"text": "The A1 pillar is advanced.",
            "basis": "evidence",
            "source_refs": ["indicator:outside:value"]}],
          {"pillar:A1:mean"}, require_all=True),
      "origins outside pack")


section("Review and method ratification are separate publication gates")

check("the current reviewed replay cannot be final while the model is unratified",
      D.final_publication_blockers(True),
      "model ratified is not true")

_ratified_model = dict(D.SPEC)
_ratified_model.update({
    "revision": 3,
    "status": "ratified",
    "ratified": True,
    "open_decisions": [],
    "binding_rules": [dict(rule, ratified=True)
                      for rule in D.SPEC["binding_rules"]],
    "indicators": [
        dict({key: value for key, value in row.items()
              if key != "ratification"},
             **({"thresholds_ratified": True}
                if row.get("thresholds") else {}))
        for row in D.SPEC["indicators"]
    ],
    "foresight": dict(D.SPEC["foresight"], ratified=True),
})

_evidence_dir = tempfile.TemporaryDirectory()


def _archive_bytes(reference, raw):
    path = os.path.join(_evidence_dir.name, reference)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _archive(reference, payload):
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    return _archive_bytes(reference, raw)


def _approval(reviewer, slug):
    source_payload = dict(
        _model_binding, reviewer=reviewer, approved_on="2026-08-26",
        approved=True, decision_scope="DAMM Issue 2 ratification",
        source_record_id=f"approval-{slug}-2026-08-26",
        evidence_manifest_sha256=_manifest_sha256,
        provenance={
            "system": "google_drive",
            "immutable_record_id": f"drive-record-{slug}",
            "revision_id": "revision-1",
            "captured_on": "2026-08-26",
            "verification": {
                "method": "provider_revision",
                "verified_by": "Independent archive custodian",
                "verified_on": "2026-08-26",
            },
        })
    reference = f"reviews/approval-{slug}.json"
    return {
        "reviewer": reviewer,
        "approved_on": "2026-08-26",
        "source_record": {
            "record_ref": reference,
            "sha256": _archive(reference, source_payload),
        },
    }


def _mapping_records():
    prerequisite_ids = sorted(
        indicator_id for indicator_id, row in D.MODEL.items() if row["prereq"])
    edges = []
    for index, (prerequisite_id, use_case_id) in enumerate(
            (pair for prerequisite_id in prerequisite_ids
             for pair in ((prerequisite_id, use_case_id)
                          for use_case_id in sorted(D.SPEC["use_cases"])))):
        edge = {
            "id": f"{prerequisite_id}:{use_case_id}",
            "prerequisite_id": prerequisite_id,
            "use_case_id": use_case_id,
            "effect": "none",
            "applicability": {"mode": "never"},
            "rationale": "Ratified edge decision for this prerequisite/use-case cell.",
            "basis": ["joint-ratification-record"],
            "decision_status": "ratified",
        }
        if index == 0:
            edge.update(
                effect="gate", applicability={"mode": "always"},
                on_prerequisite_status=dict(D._MAPPING_GATE_OUTCOMES))
        elif index == 1:
            edge.update(
                effect="gate",
                applicability={
                    "mode": "conditional",
                    "predicate": {"field": "uses_personal_data", "equals": True},
                },
                on_prerequisite_status=dict(D._MAPPING_GATE_OUTCOMES))
        elif index == 2:
            edge.update(
                effect="delivery_risk", applicability={"mode": "always"},
                on_prerequisite_status=dict(D._MAPPING_RISK_OUTCOMES))
        edges.append(edge)
    return edges


def _definition_entry(indicator_id):
    model_row = D.MODEL[indicator_id]
    metadata_series = {
        "1.1": "WDI:NV.AGR.EMPL.KD",
        "1.3": "WDI:SL.AGR.EMPL.ZS",
        "2.5": "ITU:DATA_ONLY_MOBILE_BROADBAND_5GB:2025",
        "4.2": "ITU:GCI:OVERALL_SCORE:2024",
        "4.3": "OXFORD_INSIGHTS:GOVERNMENT_AI_READINESS:TOTAL_SCORE:2025",
    }
    index_ids = {"1.4", "4.2", "4.3", "6.1", "6.3"}
    is_threshold = bool(model_row["th"])
    scoring = {
        "method": "threshold" if is_threshold else "ladder",
        "direction": ({"H": "higher-is-better", "L": "lower-is-better", "": None}
                      [model_row["dir"]]),
        "missing_rule": "DATA GAP",
        "mismatch_rule": "HOLD",
    }
    if is_threshold:
        scoring["cuts"] = model_row["th"]
    else:
        scoring.update({
            "anchors": {f"L{level}": f"Ratified level {level} anchor"
                        for level in range(1, 6)},
            "qualifying_object_test": "Named qualifying object is verified.",
            "operating_test": "Operation is evidenced in the reference period.",
            "scale_test": "Scale is independently verifiable.",
        })
    return {
            "definition_version": "v1",
            "status": "ratified",
            "question_class": ("construct-drift"
                               if indicator_id in D._ISSUE_2_DEFINITION_IDS
                               else "not_applicable"),
            "resolution_basis": ("metadata-binding"
                                 if indicator_id in metadata_series
                                 else "reviewer-choice"
                                 if indicator_id in D._ISSUE_2_DEFINITION_IDS
                                 else "prior-ratification"),
            "construct": f"Nationally comparable DAMM construct for indicator {indicator_id}",
            "display_name": model_row["name"],
            "measure": {
                "operational_definition": (
                    f"Apply the jointly ratified operational rule for indicator {indicator_id}."),
                "unit": ("dimensionless published index score"
                         if indicator_id in index_ids
                         else "indicator-specific percentage or rate"
                         if is_threshold else "ordinal maturity rung from one to five"),
                "population_scope": "National population defined for this indicator",
                "reference_period": "Latest complete annual reference period",
                "numerator": ("not_applicable" if not is_threshold
                              or indicator_id in index_ids
                              else "Count or value meeting the ratified construct"),
                "denominator": ("not_applicable" if not is_threshold
                                or indicator_id in index_ids
                                else "Eligible population or comparison base"),
                "transform": (
                    "raw / 100" if indicator_id == "4.2"
                    else "monthly_price / (annual_GNI_per_capita / 12) * 100"
                    if indicator_id == "2.5"
                    else "max(male_rate - female_rate, 0)"
                    if indicator_id == "8.6" else "identity"),
            },
            "source_policy": {
                "preferred_series": ([metadata_series[indicator_id]]
                                     if indicator_id in metadata_series else []),
                "allowed_tiers": ["T1", "T2", "T3"],
                "fallback_rule": "Definitionally matched evidence only.",
                "minimum_confirmation": "One load-bearing source plus construct review",
            },
            "scoring": scoring,
            "inclusions": ["Evidence matching the ratified construct and population"],
            "exclusions": ["Proxy evidence with a mismatched unit or population"],
            "ambiguity_rule": "Unmatched evidence is held rather than scored.",
            "comparability_breaks": (["Version or basket change requires migration review"]
                                     if indicator_id in {"2.5", "4.3"} else []),
            "decision": {
                "decision_id": ("13.5" if indicator_id in D._ISSUE_2_DEFINITION_IDS
                                else "prior-ratification"),
                "ratified_by": "Katreyna + Randeep",
                "ratified_on": "2026-08-26",
                "rationale": "Jointly accepted operational definition.",
                "open_question": ("Original Issue 13.5 construct question"
                                  if indicator_id in D._ISSUE_2_DEFINITION_IDS
                                  else "No Issue 13.5 question; prior definition reviewed"),
                "resolution": "The stated construct and admissibility rule were accepted.",
            },
            "citations": ["joint-ratification-record"],
        }


def _definition_catalog(ids):
    return {indicator_id: _definition_entry(indicator_id)
            for indicator_id in sorted(ids)}


def _calibration_records(ids):
    calibrations, refs = {}, {}
    for indicator_id in sorted(ids):
        calibration_id = f"DAMM-{indicator_id}-v1"
        refs[indicator_id] = calibration_id
        calibrations[calibration_id] = {
            "indicator_id": indicator_id,
            "construct_id": f"DAMM-CONSTRUCT-{indicator_id}",
            "definition_decision": "13.5",
            "calibration_decision": "13.6",
            "status": "ratified",
            "unit": "ratified indicator unit",
            "reading_role": "readiness input",
            "score_polarity": "higher level means greater maturity",
            "direction": ({"H": "higher-is-better", "L": "lower-is-better"}
                          [D.MODEL[indicator_id]["dir"]]),
            "intervals": D._expected_threshold_intervals(D.MODEL[indicator_id]),
            "basis": {
                "kind": "expert_judgment",
                "source_ids": ["EXPERT-PANEL-MINUTES-2026-08-26"],
                "method": "Structured joint expert calibration review.",
                "rationale": "Jointly approved basis, cuts, and boundary closures.",
                "panel": ["Randeep Method Owner", "Katreyna Domain Reviewer"],
                "reviewed_on": "2026-08-26",
                "conflicts_considered": [
                    "Inherited round-number cuts versus construct-specific evidence",
                ],
                "cut_rationales": [
                    {"cut": cut,
                     "rationale": f"Panel rationale for cut {cut} on {indicator_id}.",
                     "source_ids": ["EXPERT-PANEL-MINUTES-2026-08-26"]}
                    for cut in D.MODEL[indicator_id]["th"]
                ],
            },
            "supersedes": {
                "calibration_id": None,
                "legacy_thresholds": D.MODEL[indicator_id]["th"],
            },
            "validation_fixture_ids": ["synthetic-schema-fixture"],
            "approval": {
                "method_owner": "Randeep Method Owner",
                "status": "ratified",
                "approved_on": "2026-08-26",
                "record_ref": "reviews/joint-ratification.json",
            },
            "created_on": "2026-08-26",
        }
    return calibrations, refs


_a1_threshold_ids = {
    indicator_id for indicator_id, row in D.MODEL.items()
    if row["pillar"] == "A1" and row["th"]
}
_mapping_edges = _mapping_records()
_prerequisite_mapping = {
    "decision_id": "13.3",
    "revision": 1,
    "status": "ratified",
    "ratified": True,
    "use_case_ids": list(D.SPEC["use_cases"]),
    "prerequisite_ids": sorted(
        indicator_id for indicator_id, row in D.MODEL.items() if row["prereq"]),
    "status_precedence": ["Blocked", "Unverified", "Partial", "Ready"],
    "conditional_policy": {
        "missing_profile": "report_condition_without_mutating_base_status",
        "true": "activate_edge",
        "false": "ignore_edge",
    },
    "edges": _mapping_edges,
}
_a1_calibrations, _a1_calibration_refs = _calibration_records(_a1_threshold_ids)
_threshold_ids = sorted(
    indicator_id for indicator_id, row in D.MODEL.items() if row["th"])
_threshold_calibrations, _threshold_calibration_refs = _calibration_records(
    _threshold_ids)
_definition_entries = _definition_catalog(D.KNOWN_IDS)


def _ratified_definition_metadata(
        indicator_id, *, source_sha256="a" * 64, geography="national",
        observation_period="2025", edition="2025 release",
        measured_value=None):
    """A complete observation-to-definition binding for ratified fixtures."""
    definition = _definition_entries[indicator_id]
    measure = definition["measure"]
    preferred = definition["source_policy"]["preferred_series"]
    metadata = {
        "definition_version": definition["definition_version"],
        "definition_sha256": D._canonical_sha256(definition),
        "definition_match": True,
        "unit": measure["unit"],
        "population_scope": measure["population_scope"],
        "reference_period_rule": measure["reference_period"],
        "transform": measure["transform"],
        "geography": geography,
        "observation_period": observation_period,
        "edition": edition,
        "proxy": False,
        "source_record_sha256": source_sha256,
        "construct_review_sha256": hashlib.sha256(
            f"construct-review:{indicator_id}".encode()).hexdigest(),
        "numerator": (
            "not_applicable" if measure["numerator"] == "not_applicable"
            else 50.0),
        "denominator": (
            "not_applicable" if measure["denominator"] == "not_applicable"
            else 100.0),
        "source_series": (preferred[0] if preferred
                          else "reviewer-approved fallback series"),
        "fallback_justification": (
            "The reviewed source satisfies every ratified construct field."),
    }
    if indicator_id in _threshold_calibration_refs:
        metadata["calibration_ref"] = _threshold_calibration_refs[indicator_id]
    if measured_value is not None:
        transform = measure["transform"]
        if transform == "identity":
            metadata["transform_inputs"] = {"source_value": measured_value}
        elif transform == "raw / 100":
            metadata["transform_inputs"] = {"source_value": measured_value * 100}
        elif transform == "monthly_price / (annual_GNI_per_capita / 12) * 100":
            metadata["transform_inputs"] = {
                "monthly_price": measured_value,
                "annual_gni_per_capita": 1200,
            }
        elif transform == "max(male_rate - female_rate, 0)":
            metadata["transform_inputs"] = {
                "male_rate": measured_value, "female_rate": 0,
            }
    return metadata

_ratified_model["prerequisite_mapping"] = _prerequisite_mapping
_ratified_model["definition_catalog_version"] = "release-ratified.1"
_ratified_model["indicator_definitions"] = {
    "catalog_version": "release-ratified.1",
    "catalog_status": "ratified",
    "entries": _definition_entries,
}
_ratified_model["indicator_calibration_refs"] = _threshold_calibration_refs
_ratified_model["indicators"] = [
    dict(
        row,
        definition_version=_definition_entries[row["id"]]["definition_version"],
        definition_status="ratified",
        **({"calibration_ref": _threshold_calibration_refs[row["id"]]}
           if row.get("thresholds") else {}),
    )
    for row in _ratified_model["indicators"]
]
_model_binding = {
    "model_version": _ratified_model["version"],
    "model_revision": _ratified_model["revision"],
    "model_sha256": D._model_ratification_sha256(_ratified_model),
}
_implementation_sha256 = D._release_implementation_sha256(_ratified_model)
_calibration_source_payload = dict(
    _model_binding,
    kind="expert_panel_record",
    title="Joint threshold calibration panel minutes and cut-by-cut rationale",
    panel=["Randeep Method Owner", "Katreyna Domain Reviewer"],
    reviewed_on="2026-08-26")
_calibration_sources = {
    "EXPERT-PANEL-MINUTES-2026-08-26": {
        "source_type": "expert_panel_record",
        "publisher": "DAMM joint methodology review panel",
        "title": "Threshold calibration panel minutes and cut-by-cut rationale",
        "accessed_on": "2026-08-26",
        "record_ref": "reviews/calibration-panel-minutes.json",
        "sha256": _archive(
            "reviews/calibration-panel-minutes.json", _calibration_source_payload),
    },
}
_decision_payloads = {
    "13.3": dict(
        _model_binding, ratified_on="2026-08-26", record_count=72,
        prerequisite_mapping=_prerequisite_mapping),
    "13.5": dict(_model_binding,
                 ratified_on="2026-08-26",
                 catalog_version="13.5-ratified.1", catalog_status="ratified",
                 record_count=len(D._ISSUE_2_DEFINITION_IDS),
                 entries=_definition_catalog(D._ISSUE_2_DEFINITION_IDS)),
    "13.6": dict(_model_binding,
                 ratified_on="2026-08-26", record_count=10,
                 calibration_sources=_calibration_sources,
                 threshold_calibrations=_a1_calibrations,
                 indicator_calibration_refs=_a1_calibration_refs),
}
_definition_payload = dict(
    _model_binding, ratified_on="2026-08-26",
    catalog_version="release-ratified.1", catalog_status="ratified",
    record_count=len(D.KNOWN_IDS), entries=_definition_entries)
_threshold_payload = dict(
    _model_binding, ratified_on="2026-08-26", record_count=len(_threshold_ids),
    calibration_sources=_calibration_sources,
    threshold_calibrations=_threshold_calibrations,
    indicator_calibration_refs=_threshold_calibration_refs)

_baseline_model = copy.deepcopy(D.SPEC)
_baseline_implementation_sha256 = D._release_implementation_sha256(
    _baseline_model)
_baseline_model_reference = "reviews/DAMM-v1.7-revision-2-model.json"
_baseline_model_record = {
    "record_ref": _baseline_model_reference,
    "sha256": _archive(_baseline_model_reference, _baseline_model),
    "model_sha256": D._model_ratification_sha256(_baseline_model),
    "implementation_sha256": _baseline_implementation_sha256,
    "source_commit": "b" * 40,
    "source_tag": "damm-v1.7-r2",
    "tag_object_oid": "a" * 40,
    "signature_target": "tag",
    "signature_evidence_sha256": "7" * 64,
    "authorized_signer_fingerprint": "A" * 40,
    "provenance": {
        "system": "git_signed_commit",
        "immutable_record_id": "damm-revision-2-baseline-commit",
        "revision_id": "revision-2",
        "captured_on": "2026-08-26",
        "verification": {
            "method": "verified_commit_signature",
            "verified_by": "Independent archive custodian",
            "verified_on": "2026-08-26",
        },
    },
}


def _captured_source_artifact(reference, payload):
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    return {
        "artifact_ref": reference,
        "content_sha256": _archive_bytes(reference, raw),
        "media_type": "application/json",
        "byte_length": len(raw),
    }


def _migration_diff(country):
    row_specs = {}
    for indicator_id in D.KNOWN_IDS:
        model_row = D.MODEL[indicator_id]
        if model_row["th"]:
            value = model_row["th"][0]
            cls = "Measured"
            level = D.tlevel(value, model_row["dir"], model_row["th"])
            tier = "T1"
        else:
            value = f"Reviewed {country} migration observation for {indicator_id}."
            cls, level, tier = "Documented", 3, "T3"
        row_specs[indicator_id] = {
            "value": value, "cls": cls, "level": level, "tier": tier,
        }
    source_records = {}
    for indicator_id, spec in row_specs.items():
        source_metadata = _ratified_definition_metadata(
            indicator_id, geography=country, observation_period="2025",
            edition="2025 migration snapshot",
            measured_value=(spec["value"] if spec["cls"] == "Measured"
                            else None))
        captured_source = {
            "indicator_id": indicator_id,
            "raw_value": spec["value"],
            "unit": source_metadata["unit"],
            "reference_period": source_metadata["observation_period"],
            "tier": spec["tier"],
            "url": "https://example.org/migration-source",
            "source_series": source_metadata["source_series"],
            "edition": source_metadata["edition"],
            "geography": source_metadata["geography"],
            "transform_inputs": source_metadata.get(
                "transform_inputs", "not_applicable"),
        }
        source_record = {
            key: value for key, value in captured_source.items()
            if key != "indicator_id"
        }
        source_record.update({
            "evidence_excerpt": (
                f"Archived {country} migration evidence for {indicator_id}."),
            "captured_source": _captured_source_artifact(
                f"captures/{country.lower()}-migration-source-"
                f"{indicator_id}.json", captured_source),
        })
        source_record["record_sha256"] = D._canonical_sha256(source_record)
        source_records[indicator_id] = source_record
    source_payload = dict(
        _model_binding, kind="migration_source_snapshot", country=country,
        title=f"{country} revision-3 migration source packet",
        publisher="Independent migration evidence review team",
        captured_on="2026-08-26",
        provenance={
            "system": "git_signed_commit",
            "immutable_record_id": f"{country}-migration-source-packet",
            "revision_id": f"{country.lower()}-migration-source-capture-1",
            "captured_on": "2026-08-26",
            "verification": {
                "method": "verified_commit_signature",
                "verified_by": "Independent migration source custodian",
                "verified_on": "2026-08-26",
            },
        },
        records=source_records)
    source_id = f"{country}-MIGRATION-SOURCE-PACKET"
    source_reference = f"reviews/{country.lower()}-migration-source-packet.json"
    source_registry = {
        source_id: {
            "title": source_payload["title"],
            "publisher": source_payload["publisher"],
            "accessed_on": "2026-08-26",
            "record_ref": source_reference,
            "sha256": _archive(source_reference, source_payload),
        },
    }
    engine_input = {}
    for indicator_id, spec in row_specs.items():
        value, cls, level, tier = (
            spec["value"], spec["cls"], spec["level"], spec["tier"])
        engine_input[indicator_id] = {
            "value": value, "cls": cls, "level": level, "year": 2025,
            "src": f"Archived {country} migration source",
            "note": "Reviewed migration input.",
            "tier": source_records[indicator_id]["tier"],
            "url": source_records[indicator_id]["url"],
            "definition_metadata": _ratified_definition_metadata(
                indicator_id,
                source_sha256=source_registry[source_id]["sha256"],
                geography=country,
                observation_period="2025",
                edition="2025 migration snapshot",
                measured_value=(value if cls == "Measured" else None)),
        }
    construct_review_registry = {}
    for indicator_id, row in engine_input.items():
        review_payload = dict(
            _model_binding, kind="construct_review", country=country,
            indicator_id=indicator_id,
            reviewer="Independent migration reviewer",
            reviewed_at="2026-08-26T00:40:00Z", disposition="accepted",
            definition_sha256=D._canonical_sha256(
                _definition_entries[indicator_id]),
            source_record_sha256=source_registry[source_id]["sha256"],
            source_indicator_record_sha256=source_records[
                indicator_id]["record_sha256"],
            observation_sha256=D._canonical_sha256(
                D._construct_review_observation_projection(row)),
            review_note=(
                f"Independent migration construct review accepted {indicator_id} "
                "against the ratified definition and archived source."),
            provenance={
                "system": "git_signed_commit",
                "immutable_record_id": (
                    f"{country}-migration-construct-review-{indicator_id}"),
                "revision_id": f"{country.lower()}-migration-review-1",
                "captured_on": "2026-08-26",
                "verification": {
                    "method": "verified_commit_signature",
                    "verified_by": "Independent migration archive custodian",
                    "verified_on": "2026-08-26",
                },
            })
        review_reference = (
            f"reviews/{country.lower()}-migration-construct-{indicator_id}.json")
        review_record = {
            "record_ref": review_reference,
            "sha256": _archive(review_reference, review_payload),
        }
        construct_review_registry[indicator_id] = review_record
        row["definition_metadata"]["construct_review_sha256"] = (
            review_record["sha256"])
    baseline_input = copy.deepcopy(engine_input)
    for row in baseline_input.values():
        row.pop("definition_metadata")
    intervention_profiles = {}
    baseline_output = D.engine_run(
        country, baseline_input,
        refyear=_baseline_model["config"]["assessment_year"],
        model_spec=_baseline_model,
        intervention_profiles=intervention_profiles,
        project_unratified_model=True)
    baseline_reference_output = D.ReferenceScorer(_baseline_model).run(
        baseline_input, intervention_profiles=intervention_profiles)
    engine_output = D.engine_run(
        country, engine_input,
        refyear=_ratified_model["config"]["assessment_year"],
        model_spec=_ratified_model,
        intervention_profiles=intervention_profiles)
    reference_output = D.ReferenceScorer(_ratified_model).run(
        engine_input, intervention_profiles=intervention_profiles)

    def snapshot(
            active_model, active_input, output, oracle_output,
            implementation_sha256, *, release_sources=None,
            construct_reviews=None):
        indicators = {}
        for indicator_id in D.KNOWN_IDS:
            metadata = active_input[indicator_id].get("definition_metadata")
            indicators[indicator_id] = {
                "level": output["indicators"][indicator_id]["level"],
                "cls": output["indicators"][indicator_id]["cls"],
                "value": active_input[indicator_id]["value"],
                "src": active_input[indicator_id]["src"],
                "unit": (metadata["unit"] if metadata else "legacy recorded unit"),
                "population_scope": (
                    metadata["population_scope"] if metadata
                    else "legacy national population"),
                "reference_period": (
                    metadata["observation_period"] if metadata else "2025"),
                "source_series": (
                    metadata["source_series"] if metadata
                    else "archived baseline source series"),
                "transform": (
                    metadata["transform"] if metadata else "legacy scoring rule"),
            }
            if metadata:
                indicators[indicator_id]["definition_metadata"] = metadata
        pillars = {
            pillar_id: {
                field: output["pillars"][pillar_id][field]
                for field in ("mean", "band", "rated")
            }
            for pillar_id in D.SPEC["pillars"]
        }
        matrix = {
            use_case_id: {
                "status": output["matrix"][use_case_id]["status"],
                "status_reason": output["matrix"][use_case_id].get(
                    "status_reason", output["matrix"][use_case_id].get("why")),
            }
            for use_case_id in D.SPEC["use_cases"]
        }
        result = {
            "country": country,
            "model_version": active_model["version"],
            "model_revision": active_model["revision"],
            "model_sha256": D._model_ratification_sha256(active_model),
            "implementation_sha256": implementation_sha256,
            "indicator_levels": {
                indicator_id: row["level"]
                for indicator_id, row in indicators.items()
            },
            "indicators": indicators,
            "pillars": pillars,
            "matrix": matrix,
            "engine_input": active_input,
            "engine_output": output,
            "reference_output": oracle_output,
            "reference_output_sha256": D._canonical_sha256(oracle_output),
            "intervention_profiles": intervention_profiles,
        }
        if release_sources is not None:
            result["source_registry"] = release_sources
            result["construct_review_registry"] = construct_reviews
        return result

    old_snapshot = snapshot(
        _baseline_model, baseline_input, baseline_output,
        baseline_reference_output, _baseline_implementation_sha256)
    new_snapshot = snapshot(
        _ratified_model, engine_input, engine_output,
        reference_output, _implementation_sha256,
        release_sources=source_registry,
        construct_reviews=construct_review_registry)

    old_reference = f"reviews/{country.lower()}-revision-2.json"
    new_reference = f"reviews/{country.lower()}-revision-3.json"
    old_record = {
        "record_ref": old_reference,
        "sha256": _archive(old_reference, old_snapshot),
    }
    new_record = {
        "record_ref": new_reference,
        "sha256": _archive(new_reference, new_snapshot),
    }
    changes = D._migration_expected_changes(old_snapshot, new_snapshot)
    change_domains = {
        domain: sum(change["domain"] == domain for change in changes)
        for domain in ("levels", "pillars", "bands", "matrix")
    }
    diff_payload = dict(
        _model_binding, country=country, reviewed=True, changes=changes,
        reviewer="Independent migration reviewer", reviewed_on="2026-08-26",
        comparison_summary=(
            "All 57 levels, seven pillar means and bands, and six matrix cells "
            f"were replayed and compared; {len(changes)} typed changes were derived."),
        change_domains=change_domains,
        old_artifact=old_record, new_artifact=new_record)
    reference = f"reviews/{country.lower()}-migration-diff.json"
    return {
        "id": country,
        "from_revision": 2,
        "to_revision": 3,
        "accepted": True,
        "change_count": len(changes),
        "diff_ref": reference,
        "sha256": _archive(reference, diff_payload),
    }


def _freeze_approval(reviewer, slug, approved_at):
    source_payload = dict(
        _model_binding, reviewer=reviewer, approved_at=approved_at,
        approved=True, decision_scope="DAMM Issue 2 method freeze",
        source_record_id=f"freeze-approval-{slug}-2026-08-26",
        provenance={
            "system": "google_drive",
            "immutable_record_id": f"freeze-drive-record-{slug}",
            "revision_id": "revision-1",
            "captured_on": "2026-08-26",
            "verification": {
                "method": "provider_revision",
                "verified_by": "Independent archive custodian",
                "verified_on": "2026-08-26",
            },
        })
    reference = f"reviews/freeze-approval-{slug}.json"
    return {
        "reviewer": reviewer,
        "approved_at": approved_at,
        "source_record": {
            "record_ref": reference,
            "sha256": _archive(reference, source_payload),
        },
    }


_method_freeze_payload = dict(
    _model_binding, kind="method_freeze", status="frozen",
    frozen_at="2026-08-26T00:10:00Z",
    approvals=[
        _freeze_approval("Katreyna", "katreyna", "2026-08-26T00:05:00Z"),
        _freeze_approval("Randeep", "randeep", "2026-08-26T00:06:00Z"),
    ])
_method_freeze_record = {
    "record_ref": "reviews/method-freeze.json",
    "sha256": _archive("reviews/method-freeze.json", _method_freeze_payload),
}
_migration_payload = dict(
    _model_binding, accepted=True, accepted_on="2026-08-26",
    baseline_model=_baseline_model_record,
    method_freeze=_method_freeze_record,
    started_at="2026-08-26T00:20:00Z",
    completed_at="2026-08-26T01:20:00Z",
    countries=["EGY", "NGA"],
    diffs=[_migration_diff("EGY"), _migration_diff("NGA")])


_unseen_source_records = {}
for _indicator_id in D.KNOWN_IDS:
    _source_value = (D.MODEL[_indicator_id]["th"][0]
                     if D.MODEL[_indicator_id]["th"]
                     else f"Reviewed Kenya observation for {_indicator_id}")
    _source_tier = "T1" if D.MODEL[_indicator_id]["th"] else "T3"
    _source_url = "https://example.org/kenya-source-packet"
    _source_metadata = _ratified_definition_metadata(
        _indicator_id, geography="Kenya", observation_period="2025",
        edition="2025 shadow-validation edition",
        measured_value=(_source_value if D.MODEL[_indicator_id]["th"] else None))
    _captured_source = {
        "indicator_id": _indicator_id,
        "raw_value": _source_value,
        "unit": _source_metadata["unit"],
        "reference_period": _source_metadata["observation_period"],
        "tier": _source_tier,
        "url": _source_url,
        "source_series": _source_metadata["source_series"],
        "edition": _source_metadata["edition"],
        "geography": _source_metadata["geography"],
        "transform_inputs": _source_metadata.get(
            "transform_inputs", "not_applicable"),
    }
    _source_record = {
        key: value for key, value in _captured_source.items()
        if key != "indicator_id"
    }
    _source_record.update({
        "evidence_excerpt": (
            f"Archived construct-matched source evidence for {_indicator_id}."),
        "captured_source": _captured_source_artifact(
            f"captures/ken-source-{_indicator_id}.json", _captured_source),
    })
    _source_record["record_sha256"] = D._canonical_sha256(_source_record)
    _unseen_source_records[_indicator_id] = _source_record
_unseen_source_payload = dict(
    _model_binding, kind="unseen_country_source_snapshot",
    iso3="KEN",
    title="Kenya shadow-validation source packet",
    publisher="Independent Kenya evidence review team",
    captured_on="2026-08-26",
    provenance={
        "system": "git_signed_commit",
        "immutable_record_id": "KEN-source-packet-2026-08-26",
        "revision_id": "kenya-source-capture-1",
        "captured_on": "2026-08-26",
        "verification": {
            "method": "verified_commit_signature",
            "verified_by": "Independent source archive custodian",
            "verified_on": "2026-08-26",
        },
    },
    records=_unseen_source_records)
_unseen_source_registry = {
    "KEN-SOURCE-PACKET-01": {
        "title": "Kenya shadow-validation source packet",
        "publisher": "Independent Kenya evidence review team",
        "accessed_on": "2026-08-26",
        "record_ref": "reviews/ken-source-packet.json",
        "sha256": _archive(
            "reviews/ken-source-packet.json", _unseen_source_payload),
    },
}
_unseen_intervention_profiles = {}
_unseen_engine_input = {}
for _indicator_id in D.KNOWN_IDS:
    _model_row = D.MODEL[_indicator_id]
    if _model_row["th"]:
        _value = _model_row["th"][0]
        _class = "Measured"
        _level = D.tlevel(_value, _model_row["dir"], _model_row["th"])
        _tier = "T1"
    else:
        _value = f"Reviewed Kenya observation for {_indicator_id}"
        _class, _level, _tier = "Documented", 3, "T3"
    _unseen_engine_input[_indicator_id] = {
        "value": _value,
        "cls": _class, "level": _level, "year": 2025,
        "src": "Kenya shadow-validation source packet",
        "note": "Independent source and construct review completed.",
        "tier": _unseen_source_records[_indicator_id]["tier"],
        "url": _unseen_source_records[_indicator_id]["url"],
        "definition_metadata": _ratified_definition_metadata(
            _indicator_id,
            source_sha256=_unseen_source_registry[
                "KEN-SOURCE-PACKET-01"]["sha256"],
            geography="Kenya", observation_period="2025",
            edition="2025 shadow-validation edition",
            measured_value=(_value if _class == "Measured" else None)),
    }
_unseen_assessment_rows = {
    indicator_id: {
        "raw_value": _unseen_engine_input[indicator_id]["value"],
        "unit": _unseen_engine_input[indicator_id][
            "definition_metadata"]["unit"],
        "reference_period": _unseen_engine_input[indicator_id][
            "definition_metadata"]["observation_period"],
        "source_ids": ["KEN-SOURCE-PACKET-01"],
        "primary_source_id": "KEN-SOURCE-PACKET-01",
        "human_level": _unseen_engine_input[indicator_id]["level"],
        "admissibility": "accepted",
        "review_note": "Independent source and construct review completed.",
    }
    for indicator_id in D.KNOWN_IDS
}
_unseen_construct_review_registry = {}
for _indicator_id in D.KNOWN_IDS:
    _review_payload = dict(
        _model_binding,
        kind="construct_review", iso3="KEN", indicator_id=_indicator_id,
        reviewer="Amina Example", reviewed_at="2026-08-26T02:30:00Z",
        disposition="accepted",
        definition_sha256=D._canonical_sha256(
            _definition_entries[_indicator_id]),
        source_record_sha256=_unseen_source_registry[
            "KEN-SOURCE-PACKET-01"]["sha256"],
        source_indicator_record_sha256=_unseen_source_records[
            _indicator_id]["record_sha256"],
        observation_sha256=D._canonical_sha256(
            D._construct_review_observation_projection(
                _unseen_engine_input[_indicator_id])),
        assessment_row_sha256=D._canonical_sha256(
            _unseen_assessment_rows[_indicator_id]),
        review_note=(
            f"Independent construct review accepted indicator {_indicator_id} "
            "against the ratified definition and archived source record."),
        provenance={
            "system": "git_signed_commit",
            "immutable_record_id": f"KEN-construct-review-{_indicator_id}",
            "revision_id": "kenya-shadow-review-1",
            "captured_on": "2026-08-26",
            "verification": {
                "method": "verified_commit_signature",
                "verified_by": "Independent review archive custodian",
                "verified_on": "2026-08-26",
            },
        })
    _review_reference = f"reviews/ken-construct-review-{_indicator_id}.json"
    _review_record = {
        "record_ref": _review_reference,
        "sha256": _archive(_review_reference, _review_payload),
    }
    _unseen_construct_review_registry[_indicator_id] = _review_record
    _unseen_engine_input[_indicator_id]["definition_metadata"][
        "construct_review_sha256"] = _review_record["sha256"]
_unseen_engine_output = D.engine_run(
    "Kenya", _unseen_engine_input,
    refyear=_ratified_model["config"]["assessment_year"],
    model_spec=_ratified_model,
    intervention_profiles=_unseen_intervention_profiles)
_unseen_automation_rows = {
    indicator_id: {
        "automation_level": _unseen_engine_output[
            "indicators"][indicator_id]["level"],
        "status": (
            "data_gap" if _unseen_engine_output[
                "indicators"][indicator_id]["cls"] == "Gap"
            else "held" if _unseen_engine_output[
                "indicators"][indicator_id]["level"] is None
            else "scored"),
        "input_sha256": D._canonical_sha256(
            _unseen_engine_input[indicator_id]),
        "trace_id": f"KEN-unseen-validation:{indicator_id}",
    }
    for indicator_id in D.KNOWN_IDS
}
_unseen_comparison_rows = {
    indicator_id: {
        "human_level": _unseen_assessment_rows[indicator_id]["human_level"],
        "automation_level": _unseen_automation_rows[indicator_id][
            "automation_level"],
        "outcome": "match",
        "human_row_sha256": D._canonical_sha256(
            _unseen_assessment_rows[indicator_id]),
        "automation_row_sha256": D._canonical_sha256(
            _unseen_automation_rows[indicator_id]),
        "review_note": "Human and automation readings agree.",
    }
    for indicator_id in D.KNOWN_IDS
}


def _unseen_artifact(kind):
    details = {
        "assessment": {
            "row_count": len(D.KNOWN_IDS), "source_reviewed": True,
            "started_at": "2026-08-26T02:00:00Z",
            "completed_at": "2026-08-26T03:00:00Z",
            "source_registry": _unseen_source_registry,
            "construct_review_registry": _unseen_construct_review_registry,
            "rows": _unseen_assessment_rows,
        },
        "automation_run": {
            "row_count": len(D.KNOWN_IDS), "completed": True,
            "run_id": "KEN-unseen-validation",
            "started_at": "2026-08-26T03:10:00Z",
            "completed_at": "2026-08-26T03:20:00Z",
            "refyear": _ratified_model["config"]["assessment_year"],
            "implementation_sha256": _implementation_sha256,
            "engine_input": _unseen_engine_input,
            "engine_output": _unseen_engine_output,
            "engine_output_sha256": D._canonical_sha256(
                _unseen_engine_output),
            "intervention_profiles": _unseen_intervention_profiles,
            "rows": _unseen_automation_rows,
        },
        "comparison": {
            "compared_rows": len(D.KNOWN_IDS), "accepted": True,
            "completed_at": "2026-08-26T04:00:00Z",
            "reviewer": "Amina Example", "discrepancies": [],
            "provenance": {
                "system": "git_signed_commit",
                "immutable_record_id": "KEN-human-automation-comparison",
                "revision_id": "kenya-comparison-1",
                "captured_on": "2026-08-26",
                "verification": {
                    "method": "verified_commit_signature",
                    "verified_by": "Independent comparison archive custodian",
                    "verified_on": "2026-08-26",
                },
            },
            "rows": _unseen_comparison_rows,
        },
    }[kind]
    artifact_payload = dict(
        _model_binding, iso3="KEN", kind=kind, reviewed=True, **details)
    reference = f"reviews/ken-{kind}.json"
    return {
        "record_ref": reference,
        "sha256": _archive(reference, artifact_payload),
    }


_unseen_payload = dict(
    _model_binding, iso3="KEN", country_name="Kenya", human_shadowed=True,
    method_freeze_sha256=_method_freeze_record["sha256"],
    migration_payload_sha256=D._canonical_sha256(_migration_payload),
    started_at="2026-08-26T02:00:00Z",
    completed_at="2026-08-26T04:00:00Z",
    independent_reviewer="Amina Example",
    reviewer_organization="Independent QA Ltd",
    independence_statement="No role in DAMM design, scoring, or ratification.",
    reviewed_on="2026-08-26",
    artifacts={kind: _unseen_artifact(kind) for kind in (
        "assessment", "automation_run", "comparison")})
_foresight_payload = dict(
    _model_binding, ratified=True, ratified_on="2026-08-26",
    rationale="Joint approval of the complete foresight method.",
    method=_ratified_model["foresight"])


def _xml_escape(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _excel_column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _fixture_workbook_runtime_inputs():
    """Return the exact scorer inputs copied into the parity workbook literals."""
    observations = {}
    indicator_rows = {
        row["id"]: row for row in _ratified_model["indicators"]
    }
    assessment_year = _ratified_model["config"]["assessment_year"]
    stale_year = (
        assessment_year - _ratified_model["config"]["staleness_years"] - 1)
    gap_assigned = False
    judged_assigned = False
    hold_assigned = False
    documented_index = 0
    for offset, indicator_id in enumerate(sorted(D.KNOWN_IDS)):
        indicator = indicator_rows[indicator_id]
        row = copy.deepcopy(_unseen_engine_input[indicator_id])
        if indicator["method"] == "threshold":
            value = indicator["thresholds"][(offset + 1) % 4]
            row["definition_metadata"] = _ratified_definition_metadata(
                indicator_id, geography="Workbook parity fixture",
                observation_period=str(assessment_year),
                edition="Runtime parity fixture", measured_value=value)
            row.update({
                "value": value, "cls": "Measured",
                "level": D.tlevel(
                    value, D.MODEL[indicator_id]["dir"],
                    indicator["thresholds"]),
                "src": f"Official parity source {indicator_id}",
                "url": f"https://example.test/{indicator_id}",
                "tier": "T1",
                "year": stale_year if offset == 0 else assessment_year,
                "note": "Runtime parity threshold observation.",
            })
        else:
            row["definition_metadata"] = _ratified_definition_metadata(
                indicator_id, geography="Workbook parity fixture",
                observation_period=str(assessment_year),
                edition="Runtime parity fixture")
            allowed_tiers = _definition_entries[
                indicator_id]["source_policy"]["allowed_tiers"]
            documented_tier = next(
                (tier for tier in allowed_tiers if tier != "T5"), None)
            if not gap_assigned:
                row.update({
                    "value": "DATA GAP — parity sources searched",
                    "cls": "Gap", "level": None, "src": "", "url": "",
                    "tier": "", "year": assessment_year,
                    "note": "Runtime parity gap observation.",
                })
                gap_assigned = True
            elif not judged_assigned and allowed_tiers:
                row.update({
                    "value": "Expert assessment evidence", "cls": "Judged",
                    "level": 2, "src": "", "url": "",
                    "tier": allowed_tiers[0],
                    "year": assessment_year,
                    "note": "Runtime parity judgment observation.",
                })
                judged_assigned = True
            elif not hold_assigned and documented_tier is not None:
                row.update({
                    "value": "Reviewed implementation evidence",
                    "cls": "Documented", "level": None,
                    "workbook_assessor_level": 4,
                    "workbook_definition_match": False,
                    "src": "Programme record",
                    "url": f"https://example.test/{indicator_id}",
                    "tier": documented_tier, "year": assessment_year,
                    "note": "Runtime parity held observation.",
                })
                hold_assigned = True
            elif documented_tier is not None:
                row.update({
                    "value": "Published policy evidence", "cls": "Documented",
                    "level": 3 + documented_index % 2,
                    "src": "Government gazette",
                    "url": f"https://example.test/{indicator_id}",
                    "tier": documented_tier, "year": assessment_year,
                    "note": "Runtime parity documentary observation.",
                })
                documented_index += 1
            elif allowed_tiers:
                row.update({
                    "value": "Expert assessment evidence", "cls": "Judged",
                    "level": 2, "src": "", "url": "",
                    "tier": allowed_tiers[0],
                    "year": assessment_year,
                    "note": "Runtime parity judgment observation.",
                })
            else:
                row.update({
                    "value": "DATA GAP — parity sources searched",
                    "cls": "Gap", "level": None, "src": "", "url": "",
                    "tier": "", "year": assessment_year,
                    "note": "Runtime parity gap observation.",
                })
        observations[indicator_id] = row
    assert gap_assigned and judged_assigned and hold_assigned, (
        gap_assigned, judged_assigned, hold_assigned,
        [(indicator_id, _definition_entries[indicator_id]["source_policy"][
            "allowed_tiers"])
         for indicator_id in sorted(D.KNOWN_IDS)
         if indicator_rows[indicator_id]["method"] == "ladder"])

    profiles = {}
    profile_states = (True, False, None)
    for use_case_index, use_case in enumerate(
            D._WORKBOOK_USE_CASES, start=2):
        profile = {}
        for field_index, field in enumerate(D._WORKBOOK_PROFILE_FIELDS):
            state = profile_states[(use_case_index + field_index) % 3]
            if state is not None:
                profile[field] = state
        profiles[use_case] = profile
    return observations, profiles


def _fixture_workbook_bytes():
    """A formula-complete, non-degenerate ratified workbook parity fixture."""
    sheet_names = [
        "Read Me", "Config", "Ladder", "Tiers", "Issues", "Scoring",
        "Definitions", "Visuals",
    ]
    manifests = {
        "Config": D._workbook_config_manifest(_ratified_model),
        "Scoring": D._workbook_scoring_manifest(_ratified_model),
        "Definitions": D._workbook_definitions_manifest(_ratified_model),
        "Visuals": D._workbook_visuals_manifest(_ratified_model),
    }
    assert all(manifest is not None for manifest in manifests.values())
    sheet_cells = {
        "Read Me": {
            "A1": "DAMM release parity workbook", "A2": "status: ratified",
            "A3": f"model_version:{_ratified_model['version']}",
            "A4": f"model_revision:{_ratified_model['revision']}",
            "A5": f"model_sha256:{_model_binding['model_sha256']}",
        },
        "Ladder": {"A1": "Level", "B1": "Ratified anchor",
                   "A2": 1, "B2": "Nascent anchor",
                   "A6": 5, "B6": "Transformative anchor"},
        "Tiers": {"A1": "Tier", "B1": "Admissible use",
                  "A2": "T1", "B2": "Official statistics",
                  "A4": "T3", "B4": "Government evidence",
                  "A6": "T5", "B6": "Judgment only"},
        "Issues": {"A1": "Issue", "B1": "Disposition",
                   "A2": "Issue 2", "B2": "Ratified parity surface installed"},
    }
    for sheet_name, (literals, formulas) in manifests.items():
        cells = dict(literals)
        cells.update({reference: ("formula", formula)
                      for reference, formula in formulas.items()})
        sheet_cells[sheet_name] = cells

    # The workbook is a parity case, not a blank shell: it exercises all four evidence
    # classes, both threshold directions, ladder scoring, a HOLD, and both sides of the
    # staleness boundary. Numeric values are emitted as numeric OOXML cells so ISNUMBER
    # follows the same branch that Excel/LibreOffice will use.
    runtime_observations, runtime_profiles = _fixture_workbook_runtime_inputs()
    indicator_rows = {
        row["id"]: row for row in _ratified_model["indicators"]
    }
    for offset, indicator_id in enumerate(sorted(D.KNOWN_IDS)):
        row_number = D._WORKBOOK_FIRST_INDICATOR_ROW + offset
        indicator = indicator_rows[indicator_id]
        observation = runtime_observations[indicator_id]
        values = {
            "M": observation["value"], "N": observation["src"],
            "O": observation["url"], "P": observation["tier"],
            "Q": observation["year"],
            "R": (observation.get(
                "workbook_assessor_level", observation["level"])
                  if indicator["method"] == "ladder" else ""),
            "AB": ("match" if observation.get(
                "workbook_definition_match",
                observation["definition_metadata"].get(
                    "definition_match")) is True else "mismatch"),
        }
        sheet_cells["Scoring"].update({
            f"{column}{row_number}": value for column, value in values.items()
        })

    for use_case_index, use_case in enumerate(D._WORKBOOK_USE_CASES, start=2):
        profile = runtime_profiles[use_case]
        for field, column in D._WORKBOOK_PROFILE_COLUMNS.items():
            value = profile.get(field)
            sheet_cells["Config"][f"{column}{use_case_index}"] = (
                "" if value is None else str(value).lower())

    def cell_sort(reference):
        match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", reference)
        if match is None:
            raise ValueError(f"invalid fixture cell reference: {reference}")
        column_number = 0
        for character in match.group(1):
            column_number = column_number * 26 + ord(character) - 64
        return int(match.group(2)), column_number

    def worksheet(cells):
        rows = {}
        for reference, value in cells.items():
            row_number, _ = cell_sort(reference)
            rows.setdefault(row_number, []).append((reference, value))
        rendered_rows = []
        for row_number in sorted(rows):
            rendered_cells = []
            for reference, value in sorted(rows[row_number], key=lambda item: cell_sort(item[0])):
                if isinstance(value, tuple) and value[0] == "formula":
                    rendered_cells.append(
                        f'<c r="{reference}"><f>{_xml_escape(value[1])}</f><v></v></c>')
                elif type(value) in (int, float):
                    rendered_cells.append(
                        f'<c r="{reference}"><v>{value}</v></c>')
                else:
                    rendered_cells.append(
                        f'<c r="{reference}" t="inlineStr"><is><t>'
                        f'{_xml_escape("" if value is None else value)}</t></is></c>')
            rendered_rows.append(
                f'<row r="{row_number}">{"".join(rendered_cells)}</row>')
        return (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                + ('<worksheet xmlns="http://schemas.openxmlformats.org/'
                   'spreadsheetml/2006/main"><sheetData>'
                   + "".join(rendered_rows)
                   + '</sheetData></worksheet>').encode())

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        + "".join(
            f'<sheet name="{_xml_escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
            for index, name in enumerate(sheet_names, start=1))
        + '</sheets></workbook>')
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            '<Relationship '
            f'Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, len(sheet_names) + 1))
        + '</Relationships>')
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for index in range(1, len(sheet_names) + 1))
        + '</Types>')
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>')
    workbook = io.BytesIO()
    with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr(
            "xl/styles.xml",
            '<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><numFmts count="0"/>'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/>'
            '</border></borders><cellStyleXfs count="1"><xf numFmtId="0" '
            'fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" '
            'borderId="0" xfId="0"/></cellXfs><cellStyles count="1">'
            '<cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            '</styleSheet>')
        for index, name in enumerate(sheet_names, start=1):
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml", worksheet(sheet_cells[name]))
    return workbook.getvalue()


def _application_case(case_id, scenario, observations, profiles):
    case_input = {
        "country": "Application fixture",
        "refyear": _ratified_model["config"]["assessment_year"],
        "observations": observations,
        "intervention_profiles": profiles,
    }
    try:
        engine_result = D.engine_run(
            case_input["country"], observations,
            refyear=case_input["refyear"], model_spec=_ratified_model,
            intervention_profiles=profiles)
    except (KeyError, TypeError, ValueError) as exc:
        engine_result = {"error_type": type(exc).__name__, "error": str(exc)}
    try:
        reference_result = D.ReferenceScorer(_ratified_model).run(
            observations, intervention_profiles=profiles)
    except (KeyError, TypeError, ValueError) as exc:
        reference_result = {"error_type": type(exc).__name__, "error": str(exc)}
    if ("error_type" in engine_result or "error_type" in reference_result):
        result = {
            "engine_error": engine_result,
            "reference_error": reference_result,
        }
    else:
        result = {
            "engine_output": engine_result,
            "reference_output": reference_result,
        }
    return {
        "id": case_id, "scenario": scenario, "passed": True,
        "input": case_input, "input_sha256": D._canonical_sha256(case_input),
        "expected": result, "expected_sha256": D._canonical_sha256(result),
        "actual": result, "actual_sha256": D._canonical_sha256(result),
        "assertions": [f"Replay exercises the {scenario} scoring contract."],
    }


def _application_fixture_payload():
    edges = _ratified_model["prerequisite_mapping"]["edges"]
    unconditional = next(edge for edge in edges
                         if edge["effect"] == "gate"
                         and edge["applicability"] == {"mode": "always"})
    conditional = next(edge for edge in edges
                       if edge["effect"] == "gate"
                       and edge["applicability"]["mode"] == "conditional")
    delivery = next(edge for edge in edges
                    if edge["effect"] == "delivery_risk"
                    and edge["applicability"] == {"mode": "always"})

    def rows_with_low(prerequisite_id):
        rows = copy.deepcopy(_unseen_engine_input)
        model_row = D.MODEL[prerequisite_id]
        if model_row["th"]:
            value = (model_row["th"][0] - 1
                     if model_row["dir"] == "H"
                     else model_row["th"][0] + 1)
            rows[prerequisite_id]["value"] = value
            transform = rows[prerequisite_id]["definition_metadata"]["transform"]
            if transform == "identity":
                inputs = {"source_value": value}
            elif transform == "raw / 100":
                inputs = {"source_value": value * 100}
            elif transform == "monthly_price / (annual_GNI_per_capita / 12) * 100":
                inputs = {"monthly_price": value, "annual_gni_per_capita": 1200}
            else:
                inputs = {"male_rate": value, "female_rate": 0}
            rows[prerequisite_id]["definition_metadata"][
                "transform_inputs"] = inputs
        rows[prerequisite_id]["level"] = 1
        return rows

    predicate = conditional["applicability"]["predicate"]
    conditional_field = predicate["field"]
    threshold_rows = copy.deepcopy(_unseen_engine_input)
    threshold_id = next(indicator_id for indicator_id, row in D.MODEL.items()
                        if row["th"] and not row["prereq"])
    threshold_rows[threshold_id].update({
        "value": D.MODEL[threshold_id]["th"][0],
        "cls": "Measured", "level": 1, "tier": "T1",
        "note": "Deliberately stale cached level for threshold replay.",
    })
    mismatch_rows = copy.deepcopy(_unseen_engine_input)
    mismatch_rows[threshold_id]["definition_metadata"][
        "definition_sha256"] = "0" * 64
    cases = [
        _application_case(
            "always-gate", "unconditional_gate",
            rows_with_low(unconditional["prerequisite_id"]), {}),
        _application_case(
            "conditional-inactive", "conditional_false",
            rows_with_low(conditional["prerequisite_id"]),
            {conditional["use_case_id"]: {conditional_field: False}}),
        _application_case(
            "conditional-active", "conditional_true",
            rows_with_low(conditional["prerequisite_id"]),
            {conditional["use_case_id"]: {conditional_field: True}}),
        _application_case(
            "delivery-risk", "delivery_risk",
            rows_with_low(delivery["prerequisite_id"]), {}),
        _application_case(
            "threshold-cache", "threshold_recompute", threshold_rows, {}),
        _application_case(
            "definition-hold", "definition_mismatch", mismatch_rows, {}),
    ]
    return dict(
        _model_binding, implementation_sha256=_implementation_sha256,
        cases=cases)


_application_fixtures = _application_fixture_payload()


def _release_artifact(artifact):
    version = f"1.7-r3-{artifact}"
    manifest = dict(
        _model_binding, artifact=artifact, version=version, produced=True)
    reference = f"release/{artifact}.json"
    content_reference = f"release/artifacts/{artifact}.bin"
    code_paths = {
        "engine": D.ENGINE_FILE,
        "reference_scorer": D.REFERENCE_SCORER_FILE,
        "renderer": D.RENDERER_FILE,
    }
    if artifact == "canonical_model":
        content = json.dumps(
            D._ratifiable_model_projection(_ratified_model),
            sort_keys=True).encode()
    elif artifact in code_paths:
        with open(code_paths[artifact], "rb") as handle:
            content = handle.read()
    elif artifact == "workbook":
        content = _fixture_workbook_bytes()
    else:
        content = json.dumps(_application_fixtures, sort_keys=True).encode()
    return {
        "version": version,
        "artifact_ref": reference,
        "sha256": _archive(reference, manifest),
        "content_ref": content_reference,
        "content_sha256": _archive_bytes(content_reference, content),
    }


def _release_check(check_id):
    binding_fields = {}
    passed_checks = 1
    if check_id == "application_tests":
        binding_fields = {
            "fixture_sha256": _release_artifact_versions[
                "application_fixtures"]["content_sha256"],
            "case_ids": sorted(case["id"] for case in _application_fixtures["cases"]),
            "case_count": len(_application_fixtures["cases"]),
        }
        passed_checks = binding_fields["case_count"]
    elif check_id == "single_source_parity":
        binding_fields = {
            "workbook_sha256": _release_artifact_versions[
                "workbook"]["content_sha256"],
            "canonical_model_sha256": _release_artifact_versions[
                "canonical_model"]["content_sha256"],
            "runtime_country": D._WORKBOOK_RUNTIME_COUNTRY,
            "runtime_evidence_ref": D._WORKBOOK_RUNTIME_EVIDENCE_REF,
            "runtime_evidence_sha256": _runtime_evidence_sha256,
            "observations_ref": D._WORKBOOK_RUNTIME_OBSERVATIONS_REF,
            "observations_sha256": _runtime_observations_sha256,
            "profiles_ref": D._WORKBOOK_RUNTIME_PROFILES_REF,
            "profiles_sha256": _runtime_profiles_sha256,
            **D._workbook_formula_manifest_summary(_ratified_model),
        }
        passed_checks = binding_fields["semantic_formula_count"]
    run_id = f"release-check-{check_id}-20260826"
    attestation_id = f"ci-attestation-{check_id}-20260826"
    started_at = "2026-08-26T05:00:00Z"
    completed_at = "2026-08-26T05:01:00Z"
    payload = dict(
        _model_binding, check=check_id, passed=True,
        command=D._RELEASE_CHECK_COMMANDS[check_id],
        result_summary=f"{check_id} passed",
        exit_code=0, passed_checks=passed_checks, failed_checks=0,
        run_id=run_id, attestation_id=attestation_id,
        started_at=started_at, completed_at=completed_at,
        provenance={
            "system": "git_signed_commit",
            "immutable_record_id": attestation_id,
            "revision_id": "ci-run-1",
            "captured_on": "2026-08-26",
            "verification": {
                "method": "verified_commit_signature",
                "verified_by": "Independent release custodian",
                "verified_on": "2026-08-26",
            },
        },
        **binding_fields)
    reference = f"release/check-{check_id}.json"
    log_reference = f"release/log-{check_id}.json"
    log = json.dumps({
        "check": check_id, "exit_code": 0,
        "passed_checks": passed_checks, "failed_checks": 0,
        "implementation_sha256": _implementation_sha256,
        "run_id": run_id, "attestation_id": attestation_id,
        "started_at": started_at, "completed_at": completed_at,
        **binding_fields,
    }, sort_keys=True).encode()
    return {
        "record_ref": reference,
        "sha256": _archive(reference, payload),
        "log_ref": log_reference,
        "log_sha256": _archive_bytes(log_reference, log),
    }


_release_artifact_versions = {
    key: _release_artifact(key) for key in D._RELEASE_ARTIFACT_KEYS
}
_runtime_observations, _runtime_profiles = _fixture_workbook_runtime_inputs()
_runtime_observations_raw = (
    json.dumps(_runtime_observations, sort_keys=True, indent=2) + "\n").encode()
_runtime_profiles_raw = (
    json.dumps(_runtime_profiles, sort_keys=True, indent=2) + "\n").encode()
_runtime_observations_sha256 = _archive_bytes(
    D._WORKBOOK_RUNTIME_OBSERVATIONS_REF, _runtime_observations_raw)
_runtime_profiles_sha256 = _archive_bytes(
    D._WORKBOOK_RUNTIME_PROFILES_REF, _runtime_profiles_raw)
_runtime_formula_summary = D._workbook_formula_manifest_summary(_ratified_model)
from verify_workbook_parity import projection_from_score as _projection_from_score
_runtime_engine_projection = _projection_from_score(
    D.engine_run(
        D._WORKBOOK_RUNTIME_COUNTRY, _runtime_observations,
        model_spec=_ratified_model, intervention_profiles=_runtime_profiles),
    _ratified_model)
_runtime_reference_projection = _projection_from_score(
    D.ReferenceScorer(_ratified_model).run(
        _runtime_observations, intervention_profiles=_runtime_profiles),
    _ratified_model)
assert _runtime_engine_projection == _runtime_reference_projection
_runtime_projection_sha256 = D._canonical_sha256(_runtime_engine_projection)
_runtime_evidence = {
    "schema": "damm.workbook-runtime-parity/v1",
    "status": "passed",
    "country": D._WORKBOOK_RUNTIME_COUNTRY,
    "workbook_sha256": _release_artifact_versions[
        "workbook"]["content_sha256"],
    "recalculated_workbook_sha256": hashlib.sha256(
        b"recalculated workbook fixture").hexdigest(),
    "model_file_sha256": _release_artifact_versions[
        "canonical_model"]["content_sha256"],
    "model_payload_sha256": D._canonical_sha256(
        D._ratifiable_model_projection(_ratified_model)),
    "observations_file_sha256": _runtime_observations_sha256,
    "observations_payload_sha256": D._canonical_sha256(
        _runtime_observations),
    "profiles_file_sha256": _runtime_profiles_sha256,
    "profiles_payload_sha256": D._canonical_sha256(_runtime_profiles),
    "formula_manifest_sha256": _runtime_formula_summary[
        "formula_manifest_sha256"],
    "semantic_formula_count": _runtime_formula_summary[
        "semantic_formula_count"],
    "static_verification_mode": _runtime_formula_summary[
        "verification_mode"],
    "runtime_recalculation_boundary": _runtime_formula_summary[
        "runtime_recalculation"],
    "engine_projection_sha256": _runtime_projection_sha256,
    "reference_projection_sha256": _runtime_projection_sha256,
    "workbook_projection_sha256": _runtime_projection_sha256,
    "comparison_count": 1682,
    "mismatch_count": 0,
    "mismatches": [],
    "mismatches_truncated": False,
    "input_binding_comparison_count": 504,
    "input_binding_mismatch_count": 0,
    "input_binding_mismatches": [],
    "formula_error_count": 0,
    "source_workbook_unchanged": True,
    "scope": {
        "indicators": 57,
        "indicator_outputs": ["class", "level", "stale"],
        "pillars": 7,
        "pillar_outputs": [
            "n", "rated", "held", "mean", "band", "margin", "weak",
            "evidence.Measured", "evidence.Documented", "evidence.Judged",
            "evidence.Gap", "stale",
        ],
        "layers": 4,
        "leapfrog_outputs": ["gap", "flag", "reading"],
        "prerequisites": 12,
        "mapped_readiness_outputs": 6,
        "mapping_edges": 72,
    },
    "recalculator": {
        "implementation": "LibreOffice",
        "executable": "/opt/libreoffice/program/soffice",
        "exit_code": 0,
        "stdout_sha256": hashlib.sha256(b"fixture stdout").hexdigest(),
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
    },
}
_runtime_evidence_sha256 = _archive(
    D._WORKBOOK_RUNTIME_EVIDENCE_REF, _runtime_evidence)
_release_checks = {
    key: _release_check(key) for key in D._RELEASE_CHECK_KEYS
}
_release_payload = dict(
    _model_binding,
    single_source_verified=True,
    verified_on="2026-08-26",
    artifact_versions=_release_artifact_versions,
    checks=_release_checks,
    release_tag="damm-v1.7-r3",
    signature_target="tag",
    authorized_signer_fingerprint="B" * 40,
    implementation_sha256=_implementation_sha256,
)

_non_joint_evidence = {
    "decisions": {
        decision_id: {
            "ratified": True,
            "record_count": payload["record_count"],
            "artifact_ref": f"model/decision-{decision_id}.json",
            "sha256": _archive(f"model/decision-{decision_id}.json", payload),
        }
        for decision_id, payload in _decision_payloads.items()
    },
    "definition_catalog": {
        "ratified": True,
        "record_count": len(D.KNOWN_IDS),
        "artifact_ref": "model/indicator-definitions.json",
        "sha256": _archive("model/indicator-definitions.json", _definition_payload),
    },
    "threshold_calibrations": {
        "ratified": True,
        "record_count": len(_threshold_ids),
        "method_owner": "Randeep Method Owner",
        "artifact_ref": "model/threshold-calibrations.json",
        "sha256": _archive("model/threshold-calibrations.json", _threshold_payload),
    },
    "country_migration": {
        "accepted": True,
        "countries": ["EGY", "NGA"],
        "record_ref": "reviews/country-migration.json",
        "sha256": _archive("reviews/country-migration.json", _migration_payload),
    },
    "unseen_country_validation": {
        "iso3": "KEN",
        "human_shadowed": True,
        "independent_reviewer": "Amina Example",
        "record_ref": "reviews/unseen-country.json",
        "sha256": _archive("reviews/unseen-country.json", _unseen_payload),
    },
    "foresight_method": {
        "artifact_ref": "model/foresight-method.json",
        "sha256": _archive("model/foresight-method.json", _foresight_payload),
    },
    "release_verification": {
        "record_ref": "reviews/release-verification.json",
        "sha256": _archive("reviews/release-verification.json", _release_payload),
    },
}
_manifest_sha256 = D._ratification_manifest_sha256(_non_joint_evidence)
_ratified_model["ratification_manifest_sha256"] = _manifest_sha256
_joint_payload = dict(
    _model_binding, evidence_manifest_sha256=_manifest_sha256,
    approvals=[_approval("Katreyna", "katreyna"),
               _approval("Randeep", "randeep")])
_ratified_model["ratification_evidence"] = dict(
    _non_joint_evidence,
    joint_review={
        "record_ref": "reviews/joint-ratification.json",
        "sha256": _archive("reviews/joint-ratification.json", _joint_payload),
    })

_baseline_artifact_sha256s = {}
for _migration_item in _migration_payload["diffs"]:
    _migration_diff_payload = D._verified_json_record(
        _migration_item, _evidence_dir.name, ref_field="diff_ref")
    _old_migration_record = _migration_diff_payload["old_artifact"]
    _baseline_artifact_sha256s[
        _old_migration_record["record_ref"]] = _old_migration_record["sha256"]

_release_tag_state = {
    "damm-v1.7-r2": {
        "commit": "b" * 40, "is_head": False,
        "tag_object_oid": "a" * 40,
        "signature_verified": True, "signature_target": "tag",
        "signer_fingerprint": "A" * 40,
        "signature_evidence_sha256": "7" * 64,
        "model_sha256": D._model_ratification_sha256(_baseline_model),
        "implementation_sha256": _baseline_implementation_sha256,
        "artifact_sha256s": _baseline_artifact_sha256s,
    },
    "damm-v1.7-r3": {
        "commit": "c" * 40, "tag_object_oid": "d" * 40,
        "is_head": True,
        "signature_verified": True, "signature_target": "tag",
        "signer_fingerprint": "B" * 40,
        "signature_evidence_sha256": "8" * 64,
        "model_sha256": _model_binding["model_sha256"],
        "implementation_sha256": _implementation_sha256,
        "ratification_manifest_sha256": _manifest_sha256,
        "ratification_evidence_sha256": D._canonical_sha256(
            _ratified_model["ratification_evidence"]),
        "evidence_tree_sha256": D._worktree_evidence_tree_sha256(
            _ratified_model, _evidence_dir.name),
    },
}


def _release_blockers(model, reviewed=True, tags=None):
    return D.final_publication_blockers(
        reviewed, model, evidence_root=_evidence_dir.name,
        available_release_tags=(_release_tag_state if tags is None else tags))


def _copied_release_evidence():
    temporary = tempfile.TemporaryDirectory()
    shutil.copytree(_evidence_dir.name, temporary.name, dirs_exist_ok=True)
    return temporary, copy.deepcopy(_release_payload)


def _write_release_archive(root, reference, payload, *, encoded=False):
    raw = payload if encoded else (
        json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    path = os.path.join(root, reference)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _rehashed_parity_wrapper(root, release_payload, check_payload, log_payload):
    original = release_payload["checks"]["single_source_parity"]
    release_payload["checks"]["single_source_parity"] = {
        "record_ref": original["record_ref"],
        "sha256": _write_release_archive(
            root, original["record_ref"], check_payload),
        "log_ref": original["log_ref"],
        "log_sha256": _write_release_archive(
            root, original["log_ref"],
            json.dumps(log_payload, sort_keys=True).encode(), encoded=True),
    }
    return release_payload


def _parity_check_and_log(root, release_payload):
    record = release_payload["checks"]["single_source_parity"]
    with open(os.path.join(root, record["record_ref"]), encoding="utf-8") as source:
        check_payload = json.load(source)
    with open(os.path.join(root, record["log_ref"]), encoding="utf-8") as source:
        log_payload = json.load(source)
    return check_payload, log_payload


def _release_with_runtime_mutation(mutate):
    temporary, release_payload = _copied_release_evidence()
    check_payload, log_payload = _parity_check_and_log(
        temporary.name, release_payload)
    with open(os.path.join(
            temporary.name,
            D._WORKBOOK_RUNTIME_EVIDENCE_REF), encoding="utf-8") as source:
        runtime_payload = json.load(source)
    mutate(runtime_payload)
    runtime_sha256 = _write_release_archive(
        temporary.name, D._WORKBOOK_RUNTIME_EVIDENCE_REF, runtime_payload)
    check_payload["runtime_evidence_sha256"] = runtime_sha256
    log_payload["runtime_evidence_sha256"] = runtime_sha256
    _rehashed_parity_wrapper(
        temporary.name, release_payload, check_payload, log_payload)
    return temporary, release_payload


check("reviewed inputs and prose may be final only after every method gate closes",
      _release_blockers(_ratified_model), [])

check("the substantive release workbook carries every ratified contract",
      D._workbook_content_is_semantic(
          _fixture_workbook_bytes(), _ratified_model), True)
_formula_manifest_summary = D._workbook_formula_manifest_summary(_ratified_model)
check("the release record binds the complete executable workbook surface",
      (_formula_manifest_summary["semantic_formula_count"] >= 1000
       and _formula_manifest_summary["verification_mode"]
       == "static_exact_formula_manifest"
       and _formula_manifest_summary["runtime_recalculation"]
       == "external_release_boundary"), True)
_scoring_formula_manifest = D._workbook_scoring_manifest(_ratified_model)[1]
_matrix_driver_formulas = [
    _scoring_formula_manifest[f"J{D._WORKBOOK_MATRIX_ROW + index}"]
    for index in range(len(D._WORKBOOK_USE_CASES))
]
check("matrix driver reasons use portable comma-separated concatenation",
      all("SUBSTITUTE(" in formula and "TEXTJOIN(" not in formula
          for formula in _matrix_driver_formulas), True)
check("archived runtime parity and its independent inputs complete the release record",
      D._release_records_are_complete(
          _release_payload, _ratified_model, _evidence_dir.name), True)

_missing_runtime_root, _missing_runtime_release = _copied_release_evidence()
try:
    os.remove(os.path.join(
        _missing_runtime_root.name, D._WORKBOOK_RUNTIME_EVIDENCE_REF))
    check("a missing archived runtime record fails closed",
          D._release_records_are_complete(
              _missing_runtime_release, _ratified_model,
              _missing_runtime_root.name), False)
    check("the signed evidence tree rejects a missing nested runtime record",
          D._worktree_evidence_tree_sha256(
              _ratified_model, _missing_runtime_root.name) is None, True)
    check("a tag cannot publish with a missing nested runtime record",
          bool(D.final_publication_blockers(
              True, _ratified_model, evidence_root=_missing_runtime_root.name,
              available_release_tags=_release_tag_state)), True)
finally:
    _missing_runtime_root.cleanup()

_forged_runtime_root, _forged_runtime_release = _copied_release_evidence()
try:
    _forged_runtime_check, _forged_runtime_log = _parity_check_and_log(
        _forged_runtime_root.name, _forged_runtime_release)
    with open(os.path.join(
            _forged_runtime_root.name,
            D._WORKBOOK_RUNTIME_EVIDENCE_REF), encoding="utf-8") as _source:
        _forged_runtime_payload = json.load(_source)
    _forged_runtime_payload["mismatch_count"] = 1
    _forged_runtime_payload["mismatches"] = [{
        "pair": "engine-workbook", "path": "readiness.ADV.status",
        "expected": "Partial", "actual": "Ready",
    }]
    _forged_runtime_sha256 = _write_release_archive(
        _forged_runtime_root.name, D._WORKBOOK_RUNTIME_EVIDENCE_REF,
        _forged_runtime_payload)
    _forged_runtime_check["runtime_evidence_sha256"] = (
        _forged_runtime_sha256)
    _forged_runtime_log["runtime_evidence_sha256"] = _forged_runtime_sha256
    _rehashed_parity_wrapper(
        _forged_runtime_root.name, _forged_runtime_release,
        _forged_runtime_check, _forged_runtime_log)
    check("rehashing every wrapper cannot forge a failed runtime comparison",
          D._release_records_are_complete(
              _forged_runtime_release, _ratified_model,
              _forged_runtime_root.name), False)
finally:
    _forged_runtime_root.cleanup()

_forged_projection_root, _forged_projection_release = (
    _release_with_runtime_mutation(lambda payload: payload.update({
        "engine_projection_sha256": "f" * 64,
        "reference_projection_sha256": "f" * 64,
        "workbook_projection_sha256": "f" * 64,
    })))
try:
    check("self-consistent scorer hashes cannot replace authoritative replay",
          D._release_records_are_complete(
              _forged_projection_release, _ratified_model,
              _forged_projection_root.name), False)
finally:
    _forged_projection_root.cleanup()

_copy_recalculator_root, _copy_recalculator_release = (
    _release_with_runtime_mutation(
        lambda payload: payload["recalculator"].update({
            "implementation": "test-copy",
        })))
try:
    check("a copied no-op workbook cannot attest runtime recalculation",
          D._release_records_are_complete(
              _copy_recalculator_release, _ratified_model,
              _copy_recalculator_root.name), False)
finally:
    _copy_recalculator_root.cleanup()

_narrow_scope_root, _narrow_scope_release = _release_with_runtime_mutation(
    lambda payload: payload["scope"].update({
        "pillar_outputs": payload["scope"]["pillar_outputs"][:-1],
    }))
try:
    check("runtime evidence cannot omit a declared pillar output",
          D._release_records_are_complete(
              _narrow_scope_release, _ratified_model,
              _narrow_scope_root.name), False)
finally:
    _narrow_scope_root.cleanup()

_mismatched_input_root, _mismatched_input_release = _copied_release_evidence()
try:
    _mismatched_input_check, _mismatched_input_log = _parity_check_and_log(
        _mismatched_input_root.name, _mismatched_input_release)
    with open(os.path.join(
            _mismatched_input_root.name,
            D._WORKBOOK_RUNTIME_OBSERVATIONS_REF), encoding="utf-8") as _source:
        _mismatched_observations = json.load(_source)
    _mismatched_observations[sorted(D.KNOWN_IDS)[0]]["src"] = (
        "Different independently archived source")
    _mismatched_observations_sha256 = _write_release_archive(
        _mismatched_input_root.name, D._WORKBOOK_RUNTIME_OBSERVATIONS_REF,
        _mismatched_observations)
    _mismatched_input_check["observations_sha256"] = (
        _mismatched_observations_sha256)
    _mismatched_input_log["observations_sha256"] = (
        _mismatched_observations_sha256)
    _rehashed_parity_wrapper(
        _mismatched_input_root.name, _mismatched_input_release,
        _mismatched_input_check, _mismatched_input_log)
    check("a rehashed input cannot mismatch the archived runtime binding",
          D._release_records_are_complete(
              _mismatched_input_release, _ratified_model,
              _mismatched_input_root.name), False)
    check("the signed evidence tree rejects mutated nested input bytes",
          D._worktree_evidence_tree_sha256(
              _ratified_model, _mismatched_input_root.name) is None, True)
finally:
    _mismatched_input_root.cleanup()

_forged_parity_check_record = _release_payload["checks"]["single_source_parity"]
_forged_parity_check = D._verified_json_record(
    _forged_parity_check_record, _evidence_dir.name)
with open(os.path.join(
        _evidence_dir.name, _forged_parity_check_record["log_ref"]), "rb") as _source:
    _forged_parity_log = json.loads(_source.read().decode())
_forged_parity_check["formula_manifest_sha256"] = "0" * 64
_forged_parity_log["formula_manifest_sha256"] = "0" * 64
_forged_parity_record = {
    "record_ref": "release/check-forged-workbook-manifest.json",
    "sha256": _archive(
        "release/check-forged-workbook-manifest.json", _forged_parity_check),
    "log_ref": "release/log-forged-workbook-manifest.json",
    "log_sha256": _archive_bytes(
        "release/log-forged-workbook-manifest.json",
        json.dumps(_forged_parity_log, sort_keys=True).encode()),
}
_forged_parity_release = copy.deepcopy(_release_payload)
_forged_parity_release["checks"]["single_source_parity"] = _forged_parity_record
check("matching check and log hashes cannot forge the formula manifest",
      D._release_records_are_complete(
          _forged_parity_release, _ratified_model, _evidence_dir.name), False)
_shell_workbook = io.BytesIO()
with zipfile.ZipFile(_shell_workbook, "w") as _archive_shell:
    _archive_shell.writestr("[Content_Types].xml", "<Types/>")
    _archive_shell.writestr("xl/workbook.xml", "<workbook/>")
check("a two-entry XLSX shell is not release evidence",
      D._workbook_content_is_semantic(
          _shell_workbook.getvalue(), _ratified_model), False)


def _rewrite_workbook(raw, transform):
    source = zipfile.ZipFile(io.BytesIO(raw))
    target_bytes = io.BytesIO()
    with source, zipfile.ZipFile(target_bytes, "w") as target:
        for name in source.namelist():
            replacement = transform(name, source.read(name))
            if replacement is not None:
                target.writestr(name, replacement)
    return target_bytes.getvalue()


_workbook_without_definitions = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: None if name == "xl/worksheets/sheet7.xml" else raw)
check("a workbook missing the Definitions sheet bytes is not release evidence",
      D._workbook_content_is_semantic(
          _workbook_without_definitions, _ratified_model), False)
_workbook_with_wrong_digest = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(_model_binding["model_sha256"].encode(), b"0" * 64)
        if name == "xl/worksheets/sheet2.xml" else raw))
check("a workbook bound to the wrong model digest is rejected",
      D._workbook_content_is_semantic(
          _workbook_with_wrong_digest, _ratified_model), False)
_workbook_without_formulas = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(b"<f>", b"<x>").replace(b"</f>", b"</x>")
        if name == "xl/worksheets/sheet6.xml" else raw))
check("scoring rows without executable formulas are not a release workbook",
      D._workbook_content_is_semantic(
          _workbook_without_formulas, _ratified_model), False)
_workbook_with_reversed_comparators = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(b"&gt;=", b"&lt;=")
        if name == "xl/worksheets/sheet6.xml" else raw))
check("a token-complete formula with reversed comparators is rejected",
      D._workbook_content_is_semantic(
          _workbook_with_reversed_comparators, _ratified_model), False)
_workbook_with_changed_cut = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            b'<c r="I2"><v>1000</v></c>',
            b'<c r="I2"><v>1001</v></c>', 1)
        if name == "xl/worksheets/sheet6.xml" else raw))
check("a stale contract marker cannot bless a changed workbook cut",
      D._workbook_content_is_semantic(
          _workbook_with_changed_cut, _ratified_model), False)
_workbook_with_changed_direction = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            b"<t>higher-is-better</t>", b"<t>lower-is-better</t>", 1)
        if name == "xl/worksheets/sheet6.xml" else raw))
check("a workbook direction must equal the canonical model",
      D._workbook_content_is_semantic(
          _workbook_with_changed_direction, _ratified_model), False)
_workbook_with_changed_class_rule = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(b'&quot;T5&quot;', b'&quot;T4&quot;', 1)
        if name == "xl/worksheets/sheet6.xml" else raw))
check("a workbook cannot reclassify a T5 observation as Documented",
      D._workbook_content_is_semantic(
          _workbook_with_changed_class_rule, _ratified_model), False)
_workbook_with_changed_stale_boundary = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            b'&lt;Config!$B$7-Config!$B$8',
            b'&lt;=Config!$B$7-Config!$B$8', 1)
        if name == "xl/worksheets/sheet6.xml" else raw))
check("the exact staleness boundary is executable workbook semantics",
      D._workbook_content_is_semantic(
          _workbook_with_changed_stale_boundary, _ratified_model), False)
_workbook_with_changed_bearing_flag = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            b'SEARCH(&quot;ADV&quot;', b'SEARCH(&quot;SMF&quot;', 1)
        if name == "xl/worksheets/sheet6.xml" else raw))
check("a use-case bearing flag cannot silently target another column",
      D._workbook_content_is_semantic(
          _workbook_with_changed_bearing_flag, _ratified_model), False)
_workbook_with_changed_pillar_mean = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(b'AVERAGEIF(', b'SUMIF(', 1)
        if name == "xl/worksheets/sheet6.xml" else raw))
check("pillar output formulas are part of the workbook parity surface",
      D._workbook_content_is_semantic(
          _workbook_with_changed_pillar_mean, _ratified_model), False)
_workbook_with_changed_readiness_constant = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            b'<c r="B9"><v>2.5</v></c>',
            b'<c r="B9"><v>2.6</v></c>', 1)
        if name == "xl/worksheets/sheet2.xml" else raw))
check("a workbook readiness constant must equal the canonical model",
      D._workbook_content_is_semantic(
          _workbook_with_changed_readiness_constant, _ratified_model), False)
_workbook_with_changed_mapping_effect = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            b'<c r="D21" t="inlineStr"><is><t>gate</t></is></c>',
            b'<c r="D21" t="inlineStr"><is><t>none</t></is></c>', 1)
        if name == "xl/worksheets/sheet2.xml" else raw))
check("a copied edge digest cannot bless a changed executable mapping",
      D._workbook_content_is_semantic(
          _workbook_with_changed_mapping_effect, _ratified_model), False)
_workbook_with_changed_matrix_precedence = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(b'&quot;Blocked&quot;', b'&quot;Ready&quot;', 1)
        if name == "xl/worksheets/sheet6.xml" else raw))
check("matrix status precedence is exact workbook semantics",
      D._workbook_content_is_semantic(
          _workbook_with_changed_matrix_precedence, _ratified_model), False)
_workbook_with_changed_definition_position = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(b'<t>1.1</t>', b'<t>ZZZ</t>', 1)
        if name == "xl/worksheets/sheet7.xml" else raw))
check("definition contracts must occupy their canonical workbook rows",
      D._workbook_content_is_semantic(
          _workbook_with_changed_definition_position, _ratified_model), False)
_workbook_with_changed_visual_link = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(b'Scoring!$E$62', b'Scoring!$E$63', 1)
        if name == "xl/worksheets/sheet8.xml" else raw))
check("Visuals must remain formula-backed by the canonical outputs",
      D._workbook_content_is_semantic(
          _workbook_with_changed_visual_link, _ratified_model), False)
_workbook_with_passive_formula = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            (b'<c r="B2" t="inlineStr"><is><t>'
             b'Ratified parity surface installed</t></is></c>'),
            b'<c r="B2"><f>1+1</f><v>2</v></c>', 1)
        if name == "xl/worksheets/sheet5.xml" else raw))
check("passive workbook sheets cannot hide executable formulas",
      D._workbook_content_is_semantic(
          _workbook_with_passive_formula, _ratified_model), False)
_workbook_with_external_relationship = _rewrite_workbook(
    _fixture_workbook_bytes(),
    lambda name, raw: (
        raw.replace(
            b'</Relationships>',
            (b'<Relationship Id="externalPayload" TargetMode="External" '
             b'Type="http://example.test/external" '
             b'Target="https://example.test/payload"/></Relationships>'), 1)
        if name == "_rels/.rels" else raw))
check("release workbooks cannot execute external relationships during recalc",
      D._workbook_content_is_semantic(
          _workbook_with_external_relationship, _ratified_model), False)

_application_fixture_raw = json.dumps(
    _application_fixtures, sort_keys=True).encode()
check("application evidence replays all six required scenarios",
      D._application_fixtures_are_semantic(
          _application_fixture_raw, _ratified_model), True)
_partial_application_reference = copy.deepcopy(
    _application_fixtures["cases"][0]["actual"])
_partial_application_reference["reference_output"]["indicators"]["1.1"][
    "level"] = 5
check("application parity includes every indicator result",
      D._engine_reference_outputs_match(
          _partial_application_reference["engine_output"],
          _partial_application_reference["reference_output"]), False)
_self_attested_app = dict(
    _model_binding, implementation_sha256=_implementation_sha256,
    cases=[{"id": "not-a-test", "passed": True}])
check("passed true without replayable application inputs proves nothing",
      D._application_fixtures_are_semantic(
          json.dumps(_self_attested_app).encode(), _ratified_model), False)
_forged_app = copy.deepcopy(_application_fixtures)
_forged_case = _forged_app["cases"][0]
_forged_case["expected"]["engine_output"]["country"] = "Forged output"
_forged_case["actual"] = copy.deepcopy(_forged_case["expected"])
_forged_case["expected_sha256"] = D._canonical_sha256(
    _forged_case["expected"])
_forged_case["actual_sha256"] = D._canonical_sha256(_forged_case["actual"])
check("rehashing a forged expected result cannot replace engine replay",
      D._application_fixtures_are_semantic(
          json.dumps(_forged_app, sort_keys=True).encode(), _ratified_model), False)

_wrong_definition_scenario = copy.deepcopy(_application_fixtures)
_wrong_definition_case = next(
    case for case in _wrong_definition_scenario["cases"]
    if case["scenario"] == "definition_mismatch")
_wrong_definition_input = _wrong_definition_case["input"]
_wrong_definition_id = next(
    indicator_id for indicator_id, row in _wrong_definition_input[
        "observations"].items()
    if row["definition_metadata"]["definition_sha256"] == "0" * 64)
_wrong_definition_row = _wrong_definition_input["observations"][
    _wrong_definition_id]
_wrong_definition_row["definition_metadata"]["definition_sha256"] = (
    D._canonical_sha256(_definition_entries[_wrong_definition_id]))
_wrong_definition_row["tier"] = "T4"
try:
    D.engine_run(
        _wrong_definition_input["country"],
        _wrong_definition_input["observations"],
        refyear=_wrong_definition_input["refyear"], model_spec=_ratified_model,
        intervention_profiles=_wrong_definition_input["intervention_profiles"])
except ValueError as _wrong_definition_engine_error:
    _wrong_definition_engine = {
        "error_type": "ValueError", "error": str(_wrong_definition_engine_error),
    }
try:
    D.ReferenceScorer(_ratified_model).run(
        _wrong_definition_input["observations"],
        intervention_profiles=_wrong_definition_input["intervention_profiles"])
except ValueError as _wrong_definition_reference_error:
    _wrong_definition_reference = {
        "error_type": "ValueError",
        "error": str(_wrong_definition_reference_error),
    }
_wrong_definition_result = {
    "engine_error": _wrong_definition_engine,
    "reference_error": _wrong_definition_reference,
}
_wrong_definition_case.update(
    input_sha256=D._canonical_sha256(_wrong_definition_input),
    expected=_wrong_definition_result,
    expected_sha256=D._canonical_sha256(_wrong_definition_result),
    actual=copy.deepcopy(_wrong_definition_result),
    actual_sha256=D._canonical_sha256(_wrong_definition_result),
)
check("definition-mismatch coverage cannot be replaced by another rejection",
      D._application_fixtures_are_semantic(
          json.dumps(_wrong_definition_scenario, sort_keys=True).encode(),
          _ratified_model), False)

check("both migration baselines resolve from the authenticated historical tag",
      D._migration_diffs_are_complete(
          _migration_payload, _ratified_model, _evidence_dir.name,
          _release_tag_state), True)
_unsigned_baseline_tags = copy.deepcopy(_release_tag_state)
_unsigned_baseline_tags["damm-v1.7-r2"]["signature_verified"] = False
check("an unsigned historical tag cannot establish the migration baseline",
      D._migration_diffs_are_complete(
          _migration_payload, _ratified_model, _evidence_dir.name,
          _unsigned_baseline_tags), False)
_wrong_baseline_signer = copy.deepcopy(_release_tag_state)
_wrong_baseline_signer["damm-v1.7-r2"]["signer_fingerprint"] = "D" * 40
check("the historical baseline must use its authorized signing key",
      D._migration_diffs_are_complete(
          _migration_payload, _ratified_model, _evidence_dir.name,
          _wrong_baseline_signer), False)
_unbound_baseline_tags = copy.deepcopy(_release_tag_state)
_unbound_baseline_tags["damm-v1.7-r2"]["artifact_sha256s"].pop(
    next(iter(_baseline_artifact_sha256s)))
check("a locally rehashed old snapshot is not a historical migration baseline",
      D._migration_diffs_are_complete(
          _migration_payload, _ratified_model, _evidence_dir.name,
          _unbound_baseline_tags), False)
_historical_diff = D._verified_json_record(
    _migration_payload["diffs"][0], _evidence_dir.name,
    ref_field="diff_ref")
_historical_snapshot = D._verified_json_record(
    _historical_diff["old_artifact"], _evidence_dir.name)
_recut_baseline_model = copy.deepcopy(_baseline_model)
next(row for row in _recut_baseline_model["indicators"]
     if row["id"] == "1.1")["thresholds"][0] += 1
_recut_baseline_output = D.engine_run(
    _historical_snapshot["country"], _historical_snapshot["engine_input"],
    refyear=_recut_baseline_model["config"]["assessment_year"],
    model_spec=_recut_baseline_model,
    intervention_profiles=_historical_snapshot["intervention_profiles"],
    project_unratified_model=True)
check("historical replay is driven by the archived draft model cuts",
      _recut_baseline_output["indicators"]["1.1"]["level"]
      != _historical_snapshot["engine_output"]["indicators"]["1.1"]["level"],
      True)


def _rebind_migration_source_packet(snapshot, source_payload, suffix):
    source_id = next(iter(snapshot["source_registry"]))
    prior_source_record = snapshot["source_registry"][source_id]
    packet_reference = f"reviews/egy-{suffix}-migration-source-packet.json"
    source_record = {
        **prior_source_record,
        "record_ref": packet_reference,
        "sha256": _archive(packet_reference, source_payload),
    }
    snapshot["source_registry"][source_id] = source_record
    for indicator_id in D.KNOWN_IDS:
        engine_row = snapshot["engine_input"][indicator_id]
        engine_row["definition_metadata"]["source_record_sha256"] = (
            source_record["sha256"])
        review_payload = D._verified_json_record(
            snapshot["construct_review_registry"][indicator_id],
            _evidence_dir.name)
        review_payload.update({
            "source_record_sha256": source_record["sha256"],
            "source_indicator_record_sha256": source_payload[
                "records"][indicator_id]["record_sha256"],
            "observation_sha256": D._canonical_sha256(
                D._construct_review_observation_projection(engine_row)),
        })
        review_reference = (
            f"reviews/egy-{suffix}-migration-construct-{indicator_id}.json")
        review_record = {
            "record_ref": review_reference,
            "sha256": _archive(review_reference, review_payload),
        }
        snapshot["construct_review_registry"][indicator_id] = review_record
        engine_row["definition_metadata"]["construct_review_sha256"] = (
            review_record["sha256"])
    return snapshot


_current_migration_diff = D._verified_json_record(
    _migration_payload["diffs"][0], _evidence_dir.name, ref_field="diff_ref")
_series_migration_snapshot = D._verified_json_record(
    _current_migration_diff["new_artifact"], _evidence_dir.name)
_series_migration_source_id = next(iter(
    _series_migration_snapshot["source_registry"]))
_series_migration_source_payload = D._verified_json_record(
    _series_migration_snapshot["source_registry"][_series_migration_source_id],
    _evidence_dir.name)
_series_migration_indicator = _series_migration_source_payload[
    "records"]["1.1"]
_series_migration_indicator["source_series"] = (
    "Rehashed migration series that differs from the reviewed engine input")
_series_migration_capture = {
    "indicator_id": "1.1",
    **{key: _series_migration_indicator[key] for key in (
        "raw_value", "unit", "reference_period", "tier", "url",
        "source_series", "edition", "geography", "transform_inputs")},
}
_series_migration_indicator["captured_source"] = _captured_source_artifact(
    "captures/egy-migration-series-tamper-1.1.json",
    _series_migration_capture)
_series_migration_indicator["record_sha256"] = D._canonical_sha256({
    key: value for key, value in _series_migration_indicator.items()
    if key != "record_sha256"
})
_series_migration_snapshot = _rebind_migration_source_packet(
    _series_migration_snapshot, _series_migration_source_payload,
    "series-tamper")
check("a fully rehashed migration source series must match engine metadata",
      D._migration_release_observations_are_complete(
          _series_migration_snapshot, _ratified_model, "EGY",
          _evidence_dir.name), False)

_capture_migration_snapshot = D._verified_json_record(
    _current_migration_diff["new_artifact"], _evidence_dir.name)
_capture_migration_source_id = next(iter(
    _capture_migration_snapshot["source_registry"]))
_capture_migration_source_payload = D._verified_json_record(
    _capture_migration_snapshot["source_registry"][_capture_migration_source_id],
    _evidence_dir.name)
_capture_migration_indicator = _capture_migration_source_payload[
    "records"]["1.1"]
_capture_migration_raw = {
    "indicator_id": "1.1",
    **{key: _capture_migration_indicator[key] for key in (
        "raw_value", "unit", "reference_period", "tier", "url",
        "source_series", "edition", "geography", "transform_inputs")},
}
_capture_migration_raw["raw_value"] = "tampered migration API response"
_capture_migration_indicator["captured_source"] = _captured_source_artifact(
    "captures/egy-migration-raw-tamper-1.1.json", _capture_migration_raw)
_capture_migration_indicator["record_sha256"] = D._canonical_sha256({
    key: value for key, value in _capture_migration_indicator.items()
    if key != "record_sha256"
})
_capture_migration_snapshot = _rebind_migration_source_packet(
    _capture_migration_snapshot, _capture_migration_source_payload,
    "raw-capture-tamper")
check("fully rehashed migration evidence cannot conceal changed capture bytes",
      D._migration_release_observations_are_complete(
          _capture_migration_snapshot, _ratified_model, "EGY",
          _evidence_dir.name), False)

_changed_migration = copy.deepcopy(_migration_payload)
_changed_item = _changed_migration["diffs"][0]
_changed_diff = D._verified_json_record(
    _changed_item, _evidence_dir.name, ref_field="diff_ref")
_changed_old = D._verified_json_record(
    _changed_diff["old_artifact"], _evidence_dir.name)
_changed_indicator = next(
    indicator_id for indicator_id in sorted(D.KNOWN_IDS)
    if not D.MODEL[indicator_id]["th"])
_changed_old["engine_input"][_changed_indicator]["level"] = 4
_changed_output = D.engine_run(
    "EGY", _changed_old["engine_input"],
    refyear=_baseline_model["config"]["assessment_year"],
    model_spec=_baseline_model,
    intervention_profiles=_changed_old["intervention_profiles"],
    project_unratified_model=True)
_changed_reference_output = D.ReferenceScorer(_baseline_model).run(
    _changed_old["engine_input"],
    intervention_profiles=_changed_old["intervention_profiles"])
_changed_old["engine_output"] = _changed_output
_changed_old["reference_output"] = _changed_reference_output
_changed_old["reference_output_sha256"] = D._canonical_sha256(
    _changed_reference_output)
for _indicator_id in D.KNOWN_IDS:
    _changed_level = _changed_output["indicators"][_indicator_id]["level"]
    _changed_old["indicator_levels"][_indicator_id] = _changed_level
    _changed_old["indicators"][_indicator_id]["level"] = _changed_level
for _pillar_id in D.SPEC["pillars"]:
    for _field in ("mean", "band", "rated"):
        _changed_old["pillars"][_pillar_id][_field] = _changed_output[
            "pillars"][_pillar_id][_field]
for _use_case_id in D.SPEC["use_cases"]:
    _changed_cell = _changed_output["matrix"][_use_case_id]
    _changed_old["matrix"][_use_case_id] = {
        "status": _changed_cell["status"],
        "status_reason": _changed_cell.get(
            "status_reason", _changed_cell.get("why")),
    }
_changed_old_record = {
    "record_ref": "reviews/changed-old-migration.json",
    "sha256": _archive("reviews/changed-old-migration.json", _changed_old),
}
_changed_diff["old_artifact"] = _changed_old_record
_changed_item.update(
    diff_ref="reviews/changed-but-empty-diff.json",
    sha256=_archive("reviews/changed-but-empty-diff.json", _changed_diff))
_changed_release_tag_state = copy.deepcopy(_release_tag_state)
_changed_release_tag_state["damm-v1.7-r2"]["artifact_sha256s"][
    _changed_old_record["record_ref"]] = _changed_old_record["sha256"]
check("an empty migration diff cannot conceal a changed snapshot",
      D._migration_diffs_are_complete(
          _changed_migration, _ratified_model, _evidence_dir.name,
          _changed_release_tag_state), False)

_fabricated_automation = D._verified_json_record(
    _unseen_payload["artifacts"]["automation_run"], _evidence_dir.name)
_fabricated_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
for _indicator_id in D.KNOWN_IDS:
    _fabricated_automation["rows"][_indicator_id]["automation_level"] = 4
    _fabricated_automation["engine_output"]["indicators"][_indicator_id][
        "level"] = 4
    _fabricated_comparison["rows"][_indicator_id].update({
        "automation_level": 4,
        "outcome": "accepted_difference",
        "resolution": (
            "Independent reviewer accepted this documented difference after "
            "examining the archived automation trace and source observation."),
        "automation_row_sha256": D._canonical_sha256(
            _fabricated_automation["rows"][_indicator_id]),
    })
_fabricated_automation["engine_output_sha256"] = D._canonical_sha256(
    _fabricated_automation["engine_output"])
_fabricated_comparison["discrepancies"] = sorted(D.KNOWN_IDS)
_fabricated_artifacts = dict(_unseen_payload["artifacts"])
_fabricated_artifacts["automation_run"] = {
    "record_ref": "reviews/ken-fabricated-automation.json",
    "sha256": _archive(
        "reviews/ken-fabricated-automation.json", _fabricated_automation),
}
_fabricated_artifacts["comparison"] = {
    "record_ref": "reviews/ken-fabricated-comparison.json",
    "sha256": _archive(
        "reviews/ken-fabricated-comparison.json", _fabricated_comparison),
}
_fabricated_unseen = dict(_unseen_payload, artifacts=_fabricated_artifacts)
check("rehashing fabricated automation levels cannot replace engine replay",
      D._unseen_artifacts_are_complete(
          _fabricated_unseen, _ratified_model, _evidence_dir.name), False)

_rehashed_human_assessment = D._verified_json_record(
    _unseen_payload["artifacts"]["assessment"], _evidence_dir.name)
_rehashed_human_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
for _indicator_id in D.KNOWN_IDS:
    _automation_level = _unseen_automation_rows[_indicator_id][
        "automation_level"]
    _altered_human_level = 1 if _automation_level != 1 else 2
    _rehashed_human_assessment["rows"][_indicator_id]["human_level"] = (
        _altered_human_level)
    _rehashed_human_comparison["rows"][_indicator_id].update({
        "human_level": _altered_human_level,
        "outcome": "accepted_difference",
        "resolution": (
            "Independent reviewer recorded a resolved construct difference "
            "after inspecting the archived source and automation trace."),
        "human_row_sha256": D._canonical_sha256(
            _rehashed_human_assessment["rows"][_indicator_id]),
    })
_rehashed_human_comparison["discrepancies"] = sorted(D.KNOWN_IDS)
_rehashed_human_artifacts = dict(_unseen_payload["artifacts"])
_rehashed_human_artifacts["assessment"] = {
    "record_ref": "reviews/ken-rehashed-human-assessment.json",
    "sha256": _archive(
        "reviews/ken-rehashed-human-assessment.json",
        _rehashed_human_assessment),
}
_rehashed_human_artifacts["comparison"] = {
    "record_ref": "reviews/ken-rehashed-human-comparison.json",
    "sha256": _archive(
        "reviews/ken-rehashed-human-comparison.json",
        _rehashed_human_comparison),
}
check("fully rehashed human levels cannot bypass signed assessment-row reviews",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_rehashed_human_artifacts),
          _ratified_model, _evidence_dir.name), False)

_unsigned_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
_unsigned_comparison.pop("provenance")
_unsigned_comparison_artifacts = dict(_unseen_payload["artifacts"])
_unsigned_comparison_artifacts["comparison"] = {
    "record_ref": "reviews/ken-unsigned-comparison.json",
    "sha256": _archive(
        "reviews/ken-unsigned-comparison.json", _unsigned_comparison),
}
check("unseen comparison acceptance requires independently verified provenance",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_unsigned_comparison_artifacts),
          _ratified_model, _evidence_dir.name), False)

_unresolved_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
_unresolved_comparison["rows"]["1.1"]["outcome"] = "rejected_automation"
_unresolved_comparison_artifacts = dict(_unseen_payload["artifacts"])
_unresolved_comparison_artifacts["comparison"] = {
    "record_ref": "reviews/ken-unresolved-comparison.json",
    "sha256": _archive(
        "reviews/ken-unresolved-comparison.json", _unresolved_comparison),
}
check("an unresolved rejected-automation outcome blocks unseen acceptance",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_unresolved_comparison_artifacts),
          _ratified_model, _evidence_dir.name), False)

_unexplained_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
_original_human_level = _unexplained_comparison["rows"]["1.1"][
    "human_level"]
_unexplained_comparison["rows"]["1.1"].update({
    "human_level": 1 if _original_human_level != 1 else 2,
    "outcome": "accepted_difference",
})
_unexplained_comparison["discrepancies"] = ["1.1"]
_unexplained_comparison_artifacts = dict(_unseen_payload["artifacts"])
_unexplained_comparison_artifacts["comparison"] = {
    "record_ref": "reviews/ken-unexplained-comparison.json",
    "sha256": _archive(
        "reviews/ken-unexplained-comparison.json", _unexplained_comparison),
}
check("an accepted human-automation difference needs a specific resolution",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_unexplained_comparison_artifacts),
          _ratified_model, _evidence_dir.name), False)

_unsigned_source_assessment = D._verified_json_record(
    _unseen_payload["artifacts"]["assessment"], _evidence_dir.name)
_unsigned_source_record = _unsigned_source_assessment["source_registry"][
    "KEN-SOURCE-PACKET-01"]
_unsigned_source_payload = D._verified_json_record(
    _unsigned_source_record, _evidence_dir.name)
_unsigned_source_payload.pop("provenance")
_unsigned_source_record = {
    **_unsigned_source_record,
    "record_ref": "reviews/ken-unsigned-source-packet.json",
    "sha256": _archive(
        "reviews/ken-unsigned-source-packet.json", _unsigned_source_payload),
}
_unsigned_source_assessment["source_registry"]["KEN-SOURCE-PACKET-01"] = (
    _unsigned_source_record)
_unsigned_source_artifacts = dict(_unseen_payload["artifacts"])
_unsigned_source_artifacts["assessment"] = {
    "record_ref": "reviews/ken-unsigned-source-assessment.json",
    "sha256": _archive(
        "reviews/ken-unsigned-source-assessment.json",
        _unsigned_source_assessment),
}
check("unseen source packets require independently verified provenance",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_unsigned_source_artifacts),
          _ratified_model, _evidence_dir.name), False)

_series_assessment = D._verified_json_record(
    _unseen_payload["artifacts"]["assessment"], _evidence_dir.name)
_series_automation = D._verified_json_record(
    _unseen_payload["artifacts"]["automation_run"], _evidence_dir.name)
_series_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
_series_source_record = _series_assessment["source_registry"][
    "KEN-SOURCE-PACKET-01"]
_series_source_payload = D._verified_json_record(
    _series_source_record, _evidence_dir.name)
_series_source_indicator = _series_source_payload["records"]["1.1"]
_series_source_indicator["source_series"] = (
    "Tampered alternative series with a plausible descriptive title")
_series_capture_payload = {
    "indicator_id": "1.1",
    **{key: _series_source_indicator[key] for key in (
        "raw_value", "unit", "reference_period", "tier", "url",
        "source_series", "edition", "geography", "transform_inputs")},
}
_series_source_indicator["captured_source"] = _captured_source_artifact(
    "captures/ken-series-tamper-1.1.json", _series_capture_payload)
_series_source_indicator["record_sha256"] = D._canonical_sha256({
    key: value for key, value in _series_source_indicator.items()
    if key != "record_sha256"
})
_series_source_record = {
    **_series_source_record,
    "record_ref": "reviews/ken-series-tamper-source-packet.json",
    "sha256": _archive(
        "reviews/ken-series-tamper-source-packet.json",
        _series_source_payload),
}
_series_assessment["source_registry"]["KEN-SOURCE-PACKET-01"] = (
    _series_source_record)
_series_input = _series_automation["engine_input"]["1.1"]
_series_input["definition_metadata"]["source_record_sha256"] = (
    _series_source_record["sha256"])
_series_review_payload = D._verified_json_record(
    _series_assessment["construct_review_registry"]["1.1"],
    _evidence_dir.name)
_series_review_payload.update({
    "source_record_sha256": _series_source_record["sha256"],
    "source_indicator_record_sha256": _series_source_indicator[
        "record_sha256"],
    "observation_sha256": D._canonical_sha256(
        D._construct_review_observation_projection(_series_input)),
})
_series_review_record = {
    "record_ref": "reviews/ken-series-tamper-construct-review-1.1.json",
    "sha256": _archive(
        "reviews/ken-series-tamper-construct-review-1.1.json",
        _series_review_payload),
}
_series_assessment["construct_review_registry"]["1.1"] = (
    _series_review_record)
_series_input["definition_metadata"]["construct_review_sha256"] = (
    _series_review_record["sha256"])
_series_automation["engine_output"] = D.engine_run(
    "Kenya", _series_automation["engine_input"],
    refyear=_series_automation["refyear"], model_spec=_ratified_model,
    intervention_profiles=_series_automation["intervention_profiles"])
_series_automation["engine_output_sha256"] = D._canonical_sha256(
    _series_automation["engine_output"])
_series_automation["rows"]["1.1"]["input_sha256"] = D._canonical_sha256(
    _series_input)
_series_comparison["rows"]["1.1"]["automation_row_sha256"] = (
    D._canonical_sha256(_series_automation["rows"]["1.1"]))
_series_artifacts = {
    "assessment": {
        "record_ref": "reviews/ken-series-tamper-assessment.json",
        "sha256": _archive(
            "reviews/ken-series-tamper-assessment.json", _series_assessment),
    },
    "automation_run": {
        "record_ref": "reviews/ken-series-tamper-automation.json",
        "sha256": _archive(
            "reviews/ken-series-tamper-automation.json", _series_automation),
    },
    "comparison": {
        "record_ref": "reviews/ken-series-tamper-comparison.json",
        "sha256": _archive(
            "reviews/ken-series-tamper-comparison.json", _series_comparison),
    },
}
check("rehashing source-series metadata cannot diverge from engine metadata",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_series_artifacts),
          _ratified_model, _evidence_dir.name), False)

_capture_assessment = D._verified_json_record(
    _unseen_payload["artifacts"]["assessment"], _evidence_dir.name)
_capture_source_record = _capture_assessment["source_registry"][
    "KEN-SOURCE-PACKET-01"]
_capture_source_payload = D._verified_json_record(
    _capture_source_record, _evidence_dir.name)
_capture_source_indicator = _capture_source_payload["records"]["1.1"]
_mismatched_capture_payload = {
    "indicator_id": "1.1",
    **{key: _capture_source_indicator[key] for key in (
        "raw_value", "unit", "reference_period", "tier", "url",
        "source_series", "edition", "geography", "transform_inputs")},
}
_mismatched_capture_payload["raw_value"] = "tampered raw API response"
_capture_source_indicator["captured_source"] = _captured_source_artifact(
    "captures/ken-mismatched-raw-capture-1.1.json",
    _mismatched_capture_payload)
_capture_source_indicator["record_sha256"] = D._canonical_sha256({
    key: value for key, value in _capture_source_indicator.items()
    if key != "record_sha256"
})
_capture_source_record = {
    **_capture_source_record,
    "record_ref": "reviews/ken-mismatched-capture-source-packet.json",
    "sha256": _archive(
        "reviews/ken-mismatched-capture-source-packet.json",
        _capture_source_payload),
}
_capture_assessment["source_registry"]["KEN-SOURCE-PACKET-01"] = (
    _capture_source_record)
_capture_artifacts = dict(_unseen_payload["artifacts"])
_capture_artifacts["assessment"] = {
    "record_ref": "reviews/ken-mismatched-capture-assessment.json",
    "sha256": _archive(
        "reviews/ken-mismatched-capture-assessment.json",
        _capture_assessment),
}
check("a rehashed source record cannot conceal mismatched captured bytes",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_capture_artifacts),
          _ratified_model, _evidence_dir.name), False)

_unseen_threshold_ids = {
    row["id"] for row in _ratified_model["indicators"]
    if row["method"] == "threshold"
}
check("the unseen fixture exercises all 32 threshold calibrations as Measured",
      sorted(indicator_id for indicator_id, row in _unseen_engine_input.items()
             if row["cls"] == "Measured"), sorted(_unseen_threshold_ids))

_wrong_review_assessment = D._verified_json_record(
    _unseen_payload["artifacts"]["assessment"], _evidence_dir.name)
_wrong_review_automation = D._verified_json_record(
    _unseen_payload["artifacts"]["automation_run"], _evidence_dir.name)
_wrong_review_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
_wrong_review_payload = D._verified_json_record(
    _wrong_review_assessment["construct_review_registry"]["1.1"],
    _evidence_dir.name)
_wrong_review_payload["indicator_id"] = "9.9"
_wrong_review_record = {
    "record_ref": "reviews/ken-wrong-construct-review-1.1.json",
    "sha256": _archive(
        "reviews/ken-wrong-construct-review-1.1.json", _wrong_review_payload),
}
_wrong_review_assessment["construct_review_registry"][
    "1.1"] = _wrong_review_record
_wrong_review_automation["engine_input"]["1.1"]["definition_metadata"][
    "construct_review_sha256"] = _wrong_review_record["sha256"]
_wrong_review_automation["engine_output"] = D.engine_run(
    "Kenya", _wrong_review_automation["engine_input"],
    refyear=_wrong_review_automation["refyear"],
    model_spec=_ratified_model,
    intervention_profiles=_wrong_review_automation["intervention_profiles"])
_wrong_review_automation["engine_output_sha256"] = D._canonical_sha256(
    _wrong_review_automation["engine_output"])
_wrong_review_automation["rows"]["1.1"]["input_sha256"] = (
    D._canonical_sha256(_wrong_review_automation["engine_input"]["1.1"]))
_wrong_review_comparison["rows"]["1.1"]["automation_row_sha256"] = (
    D._canonical_sha256(_wrong_review_automation["rows"]["1.1"]))
_wrong_review_artifacts = {
    "assessment": {
        "record_ref": "reviews/ken-wrong-review-assessment.json",
        "sha256": _archive(
            "reviews/ken-wrong-review-assessment.json",
            _wrong_review_assessment),
    },
    "automation_run": {
        "record_ref": "reviews/ken-wrong-review-automation.json",
        "sha256": _archive(
            "reviews/ken-wrong-review-automation.json",
            _wrong_review_automation),
    },
    "comparison": {
        "record_ref": "reviews/ken-wrong-review-comparison.json",
        "sha256": _archive(
            "reviews/ken-wrong-review-comparison.json",
            _wrong_review_comparison),
    },
}
check("a rehashed construct review bound to the wrong indicator is rejected",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_wrong_review_artifacts),
          _ratified_model, _evidence_dir.name), False)

_held_assessment = D._verified_json_record(
    _unseen_payload["artifacts"]["assessment"], _evidence_dir.name)
_held_automation = D._verified_json_record(
    _unseen_payload["artifacts"]["automation_run"], _evidence_dir.name)
_held_comparison = D._verified_json_record(
    _unseen_payload["artifacts"]["comparison"], _evidence_dir.name)
_held_source_record = _held_assessment["source_registry"][
    "KEN-SOURCE-PACKET-01"]
_held_source_payload = D._verified_json_record(
    _held_source_record, _evidence_dir.name)
_held_value = "Reviewed documented threshold mismatch for 1.1."
_held_source_indicator = _held_source_payload["records"]["1.1"]
_held_source_indicator.update({
    "raw_value": _held_value,
    "tier": "T3",
    "transform_inputs": "not_applicable",
})
_held_capture_payload = {
    "indicator_id": "1.1",
    **{key: _held_source_indicator[key] for key in (
        "raw_value", "unit", "reference_period", "tier", "url",
        "source_series", "edition", "geography", "transform_inputs")},
}
_held_source_indicator["captured_source"] = _captured_source_artifact(
    "captures/ken-held-source-1.1.json", _held_capture_payload)
_held_source_indicator["record_sha256"] = D._canonical_sha256({
    key: value for key, value in _held_source_indicator.items()
    if key != "record_sha256"
})
_held_source_record = dict(
    _held_source_record,
    record_ref="reviews/ken-held-source-packet.json",
    sha256=_archive(
        "reviews/ken-held-source-packet.json", _held_source_payload))
_held_assessment["source_registry"][
    "KEN-SOURCE-PACKET-01"] = _held_source_record
_held_assessment["rows"]["1.1"].update({
    "raw_value": _held_value, "human_level": None,
    "admissibility": "held",
})
_held_input = _held_automation["engine_input"]["1.1"]
_held_input.update({
    "value": _held_value, "cls": "Documented", "level": None,
    "tier": "T3",
})
_held_input["definition_metadata"]["source_record_sha256"] = (
    _held_source_record["sha256"])
_held_input["definition_metadata"].pop("transform_inputs")
_held_review_payload = D._verified_json_record(
    _held_assessment["construct_review_registry"]["1.1"],
    _evidence_dir.name)
_held_review_payload.update({
    "disposition": "held",
    "source_record_sha256": _held_source_record["sha256"],
    "source_indicator_record_sha256": _held_source_payload[
        "records"]["1.1"]["record_sha256"],
    "observation_sha256": D._canonical_sha256(
        D._construct_review_observation_projection(_held_input)),
    "assessment_row_sha256": D._canonical_sha256(
        _held_assessment["rows"]["1.1"]),
    "review_note": (
        "Independent construct review held the documented threshold mismatch "
        "instead of assigning a numeric score."),
})
_held_review_record = {
    "record_ref": "reviews/ken-held-construct-review-1.1.json",
    "sha256": _archive(
        "reviews/ken-held-construct-review-1.1.json", _held_review_payload),
}
_held_assessment["construct_review_registry"]["1.1"] = _held_review_record
_held_input["definition_metadata"]["construct_review_sha256"] = (
    _held_review_record["sha256"])
_held_automation["engine_output"] = D.engine_run(
    "Kenya", _held_automation["engine_input"],
    refyear=_held_automation["refyear"], model_spec=_ratified_model,
    intervention_profiles=_held_automation["intervention_profiles"])
_held_automation["engine_output_sha256"] = D._canonical_sha256(
    _held_automation["engine_output"])
_held_automation["rows"]["1.1"].update({
    "automation_level": None, "status": "held",
    "input_sha256": D._canonical_sha256(_held_input),
})
_held_comparison["rows"]["1.1"].update({
    "human_level": None, "automation_level": None, "outcome": "match",
    "human_row_sha256": D._canonical_sha256(
        _held_assessment["rows"]["1.1"]),
    "automation_row_sha256": D._canonical_sha256(
        _held_automation["rows"]["1.1"]),
})
_held_artifacts = {
    "assessment": {
        "record_ref": "reviews/ken-held-assessment.json",
        "sha256": _archive(
            "reviews/ken-held-assessment.json", _held_assessment),
    },
    "automation_run": {
        "record_ref": "reviews/ken-held-automation.json",
        "sha256": _archive(
            "reviews/ken-held-automation.json", _held_automation),
    },
    "comparison": {
        "record_ref": "reviews/ken-held-comparison.json",
        "sha256": _archive(
            "reviews/ken-held-comparison.json", _held_comparison),
    },
}
check("a fully rehashed held threshold cannot count as unseen calibration exercise",
      D._unseen_artifacts_are_complete(
          dict(_unseen_payload, artifacts=_held_artifacts),
          _ratified_model, _evidence_dir.name), False)
_migration_without_freeze = dict(_migration_payload)
_migration_without_freeze.pop("method_freeze")
check("country reruns require a jointly approved model-freeze record",
      D._migration_diffs_are_complete(
          _migration_without_freeze, _ratified_model, _evidence_dir.name), False)
_early_unseen = dict(
    _unseen_payload, started_at="2026-08-26T00:30:00Z")
check("the unseen-country run must begin after both migration reruns finish",
      D._unseen_follows_migration(
          _early_unseen, _migration_payload,
          _ratified_model, _evidence_dir.name), False)

_unbound_manifest = dict(
    _ratified_model, ratification_manifest_sha256="0" * 64)
check("joint approval must bind the exact non-joint evidence manifest",
      _release_blockers(_unbound_manifest),
      "ratification evidence manifest is incomplete or unbound")

for _field, _value in (
        ("prerequisite_mapping", None),
        ("definition_catalog_version", "different-catalog"),
        ("indicator_calibration_refs", {})):
    _unapplied_model = dict(_ratified_model, **{_field: _value})
    check(f"ratified artifact application is required for {_field}",
          _release_blockers(_unapplied_model),
          "ratified mapping, definitions, and calibrations are not applied")

_no_durable_evidence = dict(_ratified_model)
_no_durable_evidence.pop("ratification_evidence")
check("booleans cannot substitute for durable ratification evidence",
      _release_blockers(_no_durable_evidence),
      "durable ratification evidence is missing or malformed")

for _evidence_field, _evidence_message in (
        ("joint_review", "joint Katreyna and Randeep ratification record is incomplete"),
        ("decisions", "decision 13.3 ratification artifact is incomplete"),
        ("definition_catalog", "complete indicator-definition catalog is missing"),
        ("threshold_calibrations", "complete threshold-calibration attestation is missing"),
        ("country_migration", "Egypt and Nigeria migration acceptance is incomplete"),
        ("unseen_country_validation",
         "unseen-country independent human-shadow validation is incomplete"),
        ("foresight_method", "foresight ratification artifact is incomplete"),
        ("release_verification",
         "release verification and version evidence is incomplete")):
    _incomplete_evidence = dict(_ratified_model["ratification_evidence"])
    _incomplete_evidence.pop(_evidence_field)
    _incomplete_release = dict(
        _ratified_model, ratification_evidence=_incomplete_evidence)
    check(f"missing {_evidence_field} evidence cannot publish final",
          _release_blockers(_incomplete_release),
          _evidence_message)

for _bad_joint in (
        {
            "record_ref": "reviews/does-not-exist.json",
            "sha256": "a" * 64,
        },
        dict(_ratified_model["ratification_evidence"]["joint_review"],
             sha256="a" * 64),
        {
            "record_ref": "../outside-evidence.json",
            "sha256": "a" * 64,
        }):
    _bad_evidence = dict(
        _ratified_model["ratification_evidence"], joint_review=_bad_joint)
    _bad_release = dict(_ratified_model, ratification_evidence=_bad_evidence)
    check("evidence refs must resolve inside the archive with matching bytes",
          _release_blockers(_bad_release),
          "joint Katreyna and Randeep ratification record is incomplete")

_wrong_revision_payload = dict(_joint_payload, model_revision=2)
_wrong_revision_joint = {
    "record_ref": "reviews/wrong-revision-joint.json",
    "sha256": _archive(
        "reviews/wrong-revision-joint.json", _wrong_revision_payload),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    joint_review=_wrong_revision_joint)
_bad_release = dict(_ratified_model, ratification_evidence=_bad_evidence)
check("archived evidence must bind to the current model revision",
      _release_blockers(_bad_release),
      "joint Katreyna and Randeep ratification record is incomplete")

_float_count_payload = dict(_decision_payloads["13.3"], record_count=72.0)
_float_count_record = dict(
    _ratified_model["ratification_evidence"]["decisions"]["13.3"],
    record_count=72.0,
    artifact_ref="model/float-count-13.3.json",
    sha256=_archive("model/float-count-13.3.json", _float_count_payload))
_bad_decisions = dict(
    _ratified_model["ratification_evidence"]["decisions"],
    **{"13.3": _float_count_record})
_bad_evidence = dict(
    _ratified_model["ratification_evidence"], decisions=_bad_decisions)
_bad_release = dict(_ratified_model, ratification_evidence=_bad_evidence)
check("artifact counts must be integers derived from parsed records",
      _release_blockers(_bad_release),
      "decision 13.3 ratification artifact is incomplete")

_skeletal_joint_payload = dict(
    _joint_payload,
    approvals=[
        {key: value for key, value in approval.items() if key != "source_record"}
        for approval in _joint_payload["approvals"]
    ])
_skeletal_joint = {
    "record_ref": "reviews/skeletal-joint.json",
    "sha256": _archive("reviews/skeletal-joint.json", _skeletal_joint_payload),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"], joint_review=_skeletal_joint)
check("names and dates without archived source records cannot ratify",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "joint Katreyna and Randeep ratification record is incomplete")

_approval_without_provenance = D._verified_json_record(
    _joint_payload["approvals"][0]["source_record"], _evidence_dir.name)
_approval_without_provenance = {
    key: value for key, value in _approval_without_provenance.items()
    if key != "provenance"
}
_bad_approval_record = {
    "record_ref": "reviews/approval-without-provenance.json",
    "sha256": _archive(
        "reviews/approval-without-provenance.json", _approval_without_provenance),
}
_approvals_without_provenance = list(_joint_payload["approvals"])
_approvals_without_provenance[0] = dict(
    _approvals_without_provenance[0], source_record=_bad_approval_record)
_joint_without_provenance = dict(
    _joint_payload, approvals=_approvals_without_provenance)
_joint_without_provenance_record = {
    "record_ref": "reviews/joint-without-provenance.json",
    "sha256": _archive(
        "reviews/joint-without-provenance.json", _joint_without_provenance),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    joint_review=_joint_without_provenance_record)
check("approval source records require immutable external provenance",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "joint Katreyna and Randeep ratification record is incomplete")

_skeletal_mapping_payload = dict(
    _decision_payloads["13.3"],
    prerequisite_mapping=dict(
        _decision_payloads["13.3"]["prerequisite_mapping"],
        edges=[{
            "prerequisite_id": item["prerequisite_id"],
            "use_case_id": item["use_case_id"],
        } for item in _mapping_edges]))
_skeletal_mapping_record = dict(
    _ratified_model["ratification_evidence"]["decisions"]["13.3"],
    artifact_ref="model/skeletal-mapping.json",
    sha256=_archive("model/skeletal-mapping.json", _skeletal_mapping_payload))
_skeletal_decisions = dict(
    _ratified_model["ratification_evidence"]["decisions"],
    **{"13.3": _skeletal_mapping_record})
_bad_evidence = dict(
    _ratified_model["ratification_evidence"], decisions=_skeletal_decisions)
check("mapping ids cannot substitute for edge semantics",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "decision 13.3 ratification artifact is incomplete")

_skeletal_definition_payload = dict(
    _definition_payload,
    entries={indicator_id: {} for indicator_id in D.KNOWN_IDS})
_skeletal_definition_record = dict(
    _ratified_model["ratification_evidence"]["definition_catalog"],
    artifact_ref="model/skeletal-definitions.json",
    sha256=_archive("model/skeletal-definitions.json", _skeletal_definition_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    definition_catalog=_skeletal_definition_record)
check("definition ids cannot substitute for operational definitions",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "complete indicator-definition catalog is missing")

_generic_entries = dict(_definition_payload["entries"])
_generic_entries["1.1"] = dict(
    _generic_entries["1.1"],
    measure=dict(
        _generic_entries["1.1"]["measure"],
        unit="Published measurement unit",
        population_scope="National target population",
        numerator="not_applicable", denominator="not_applicable"),
    source_policy=dict(
        _generic_entries["1.1"]["source_policy"], preferred_series=[]),
    inclusions=[], exclusions=[])
_generic_definition_payload = dict(
    _definition_payload, entries=_generic_entries)
_generic_definition_record = dict(
    _ratified_model["ratification_evidence"]["definition_catalog"],
    artifact_ref="model/generic-definitions.json",
    sha256=_archive("model/generic-definitions.json", _generic_definition_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    definition_catalog=_generic_definition_record)
check("generic fields and empty named-series bindings cannot ratify definitions",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "complete indicator-definition catalog is missing")

_skeletal_threshold_payload = dict(
    _threshold_payload,
    threshold_calibrations={
        calibration_id: {"indicator_id": record["indicator_id"]}
        for calibration_id, record in _threshold_calibrations.items()
    })
_skeletal_threshold_record = dict(
    _ratified_model["ratification_evidence"]["threshold_calibrations"],
    artifact_ref="model/skeletal-thresholds.json",
    sha256=_archive("model/skeletal-thresholds.json", _skeletal_threshold_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    threshold_calibrations=_skeletal_threshold_record)
check("threshold ids cannot substitute for exact calibrated intervals",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "complete threshold-calibration attestation is missing")

_generic_calibrations = dict(_threshold_calibrations)
_generic_calibration_id = _threshold_calibration_refs["1.1"]
_generic_calibration = dict(_generic_calibrations[_generic_calibration_id])
_generic_calibration["basis"] = {
    "kind": "expert_judgment",
    "method": "Expert review",
    "rationale": "Approved cuts",
    "source_ids": [],
}
_generic_calibrations[_generic_calibration_id] = _generic_calibration
_generic_threshold_payload = dict(
    _threshold_payload, threshold_calibrations=_generic_calibrations)
_generic_threshold_record = dict(
    _ratified_model["ratification_evidence"]["threshold_calibrations"],
    artifact_ref="model/generic-threshold-basis.json",
    sha256=_archive(
        "model/generic-threshold-basis.json", _generic_threshold_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    threshold_calibrations=_generic_threshold_record)
check("expert calibration needs a named panel and rationale for every cut",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "complete threshold-calibration attestation is missing")

_skeletal_migration_payload = {
    key: value for key, value in _migration_payload.items() if key != "diffs"
}
_skeletal_migration_record = dict(
    _ratified_model["ratification_evidence"]["country_migration"],
    record_ref="reviews/skeletal-migration.json",
    sha256=_archive("reviews/skeletal-migration.json", _skeletal_migration_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    country_migration=_skeletal_migration_record)
check("migration acceptance requires both reviewed country diffs",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "Egypt and Nigeria migration acceptance is incomplete")

_bad_migration_payload = dict(_migration_payload)
_bad_migration_diffs = list(_bad_migration_payload["diffs"])
_bad_diff_payload = D._verified_json_record(
    _bad_migration_diffs[0], _evidence_dir.name, ref_field="diff_ref")
_bad_diff_payload = dict(
    _bad_diff_payload,
    old_artifact={"record_ref": "reviews/missing-old.json", "sha256": "a" * 64})
_bad_migration_diffs[0] = dict(
    _bad_migration_diffs[0], diff_ref="reviews/diff-without-snapshots.json",
    sha256=_archive("reviews/diff-without-snapshots.json", _bad_diff_payload))
_bad_migration_payload["diffs"] = _bad_migration_diffs
_bad_migration_record = dict(
    _ratified_model["ratification_evidence"]["country_migration"],
    record_ref="reviews/migration-without-snapshots.json",
    sha256=_archive(
        "reviews/migration-without-snapshots.json", _bad_migration_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    country_migration=_bad_migration_record)
check("migration diffs require content-addressed old and new 57-row snapshots",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "Egypt and Nigeria migration acceptance is incomplete")

_skeletal_unseen_payload = {
    key: value for key, value in _unseen_payload.items() if key != "artifacts"
}
_skeletal_unseen_record = dict(
    _ratified_model["ratification_evidence"]["unseen_country_validation"],
    record_ref="reviews/skeletal-unseen.json",
    sha256=_archive("reviews/skeletal-unseen.json", _skeletal_unseen_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    unseen_country_validation=_skeletal_unseen_record)
check("unseen validation requires assessment, run, and comparison artifacts",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "unseen-country independent human-shadow validation is incomplete")

_bad_assessment = D._verified_json_record(
    _unseen_payload["artifacts"]["assessment"], _evidence_dir.name)
_bad_assessment = dict(_bad_assessment, rows={})
_bad_unseen_artifacts = dict(_unseen_payload["artifacts"])
_bad_unseen_artifacts["assessment"] = {
    "record_ref": "reviews/ken-empty-assessment.json",
    "sha256": _archive("reviews/ken-empty-assessment.json", _bad_assessment),
}
_bad_unseen_payload = dict(_unseen_payload, artifacts=_bad_unseen_artifacts)
_bad_unseen_record = dict(
    _ratified_model["ratification_evidence"]["unseen_country_validation"],
    record_ref="reviews/unseen-empty-rows.json",
    sha256=_archive("reviews/unseen-empty-rows.json", _bad_unseen_payload))
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    unseen_country_validation=_bad_unseen_record)
check("unseen validation metadata cannot substitute for all 57 shadow rows",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "unseen-country independent human-shadow validation is incomplete")

_skeletal_release_payload = dict(
    _release_payload,
    artifact_versions={key: "v1" for key in D._RELEASE_ARTIFACT_KEYS},
    checks={key: True for key in D._RELEASE_CHECK_KEYS})
_skeletal_release_record = {
    "record_ref": "reviews/skeletal-release.json",
    "sha256": _archive("reviews/skeletal-release.json", _skeletal_release_payload),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    release_verification=_skeletal_release_record)
check("release booleans and version strings cannot replace hashed records",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "release verification and version evidence is incomplete")

for _bad_approvals in (
        "Katreyna and Randeep",
        [{"reviewer": "Katreyna and Randeep", "approved_on": "2026-08-26"}],
        [
            {"reviewer": "Katreyna and Randeep", "approved_on": "2026-08-26"},
            {"reviewer": "Katreyna and Randeep", "approved_on": "2026-08-26"},
        ],
        [
            {"reviewer": ["Katreyna"], "approved_on": "2026-08-26"},
            {"reviewer": "Randeep", "approved_on": "2026-08-26"},
        ],
        [
            {"reviewer": "Katreyna", "approved_on": "2026-99-99"},
            {"reviewer": "Randeep", "approved_on": "2026-08-26"},
        ],
        [
            {"reviewer": "Katreyna", "approved_on": "9999-12-31"},
            {"reviewer": "Randeep", "approved_on": "2026-08-26"},
        ]):
    _bad_joint_payload = dict(_joint_payload, approvals=_bad_approvals)
    _bad_joint = {
        "record_ref": "reviews/bad-joint-ratification.json",
        "sha256": _archive(
            "reviews/bad-joint-ratification.json", _bad_joint_payload),
    }
    _bad_evidence = dict(
        _ratified_model["ratification_evidence"], joint_review=_bad_joint)
    _bad_release = dict(_ratified_model, ratification_evidence=_bad_evidence)
    check("joint approval requires two distinct, validly dated records",
          _release_blockers(_bad_release),
          "joint Katreyna and Randeep ratification record is incomplete")

for _bad_countries in (1, [{}], ["EGY", "NGA", "EGY"]):
    _bad_migration_payload = dict(_migration_payload, countries=_bad_countries)
    _bad_migration = dict(
        _ratified_model["ratification_evidence"]["country_migration"],
        countries=_bad_countries,
        record_ref="reviews/bad-country-migration.json",
        sha256=_archive(
            "reviews/bad-country-migration.json", _bad_migration_payload))
    _bad_evidence = dict(
        _ratified_model["ratification_evidence"], country_migration=_bad_migration)
    _bad_release = dict(_ratified_model, ratification_evidence=_bad_evidence)
    check("malformed country migration evidence fails closed",
          _release_blockers(_bad_release),
          "Egypt and Nigeria migration acceptance is incomplete")

for _bad_unseen_payload in (
        dict(_unseen_payload, iso3="ZZZ"),
        dict(_unseen_payload, independent_reviewer="Randeep")):
    _bad_unseen = dict(
        _ratified_model["ratification_evidence"]["unseen_country_validation"],
        iso3=_bad_unseen_payload["iso3"],
        independent_reviewer=_bad_unseen_payload["independent_reviewer"],
        record_ref="reviews/bad-unseen-country.json",
        sha256=_archive(
            "reviews/bad-unseen-country.json", _bad_unseen_payload))
    _bad_evidence = dict(
        _ratified_model["ratification_evidence"],
        unseen_country_validation=_bad_unseen)
    _bad_release = dict(_ratified_model, ratification_evidence=_bad_evidence)
    check("unseen validation needs a real ISO code and independent reviewer",
          _release_blockers(_bad_release),
          "unseen-country independent human-shadow validation is incomplete")

_bad_release_payload = dict(
    _release_payload,
    checks=dict(_release_payload["checks"], full_build=False))
_bad_release_record = {
    "record_ref": "reviews/bad-release-verification.json",
    "sha256": _archive(
        "reviews/bad-release-verification.json", _bad_release_payload),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    release_verification=_bad_release_record)
_bad_release = dict(_ratified_model, ratification_evidence=_bad_evidence)
check("a failed release check blocks the Final label",
      _release_blockers(_bad_release),
      "release verification and version evidence is incomplete")

check("the declared release tag must exist",
      _release_blockers(_ratified_model, tags=set()),
      "release verification and version evidence is incomplete")

_unsigned_release_tag = copy.deepcopy(_release_tag_state)
_unsigned_release_tag["damm-v1.7-r3"]["signature_verified"] = False
check("an unsigned release tag cannot close publication",
      _release_blockers(_ratified_model, tags=_unsigned_release_tag),
      "release verification and version evidence is incomplete")

_wrong_release_signer = copy.deepcopy(_release_tag_state)
_wrong_release_signer["damm-v1.7-r3"]["signer_fingerprint"] = "C" * 40
check("a valid signature from an unauthorized release key cannot close publication",
      _release_blockers(_ratified_model, tags=_wrong_release_signer),
      "release verification and version evidence is incomplete")

_mispointed_tag = {
    "damm-v1.7-r3": {
        "commit": "older-commit", "is_head": False,
        "implementation_sha256": _implementation_sha256,
    },
}
check("the release tag must point at current HEAD and its implementation bytes",
      _release_blockers(_ratified_model, tags=_mispointed_tag),
      "release verification and version evidence is incomplete")

_tag_without_evidence = {
    "damm-v1.7-r3": {
        "commit": "fixture-commit", "is_head": True,
        "implementation_sha256": _implementation_sha256,
        "ratification_manifest_sha256": None,
        "ratification_evidence_sha256": None,
        "evidence_tree_sha256": None,
    },
}
check("the tag must contain the approved manifest and every evidence-tree byte",
      _release_blockers(_ratified_model, tags=_tag_without_evidence),
      "release verification and version evidence is incomplete")

_bad_artifact_versions = dict(_release_payload["artifact_versions"])
_bad_artifact_versions["workbook"] = dict(
    _bad_artifact_versions["workbook"], content_sha256="e" * 64)
_bad_release_payload = dict(
    _release_payload, artifact_versions=_bad_artifact_versions)
_bad_release_record = {
    "record_ref": "reviews/bad-artifact-content.json",
    "sha256": _archive(
        "reviews/bad-artifact-content.json", _bad_release_payload),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    release_verification=_bad_release_record)
check("release artifact manifests must resolve to matching content bytes",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "release verification and version evidence is incomplete")

_arbitrary_reference = "release/artifacts/arbitrary-workbook.bin"
_arbitrary_workbook = b"this is not an xlsx workbook"
_bad_artifact_versions = dict(_release_payload["artifact_versions"])
_bad_artifact_versions["workbook"] = dict(
    _bad_artifact_versions["workbook"],
    content_ref=_arbitrary_reference,
    content_sha256=_archive_bytes(_arbitrary_reference, _arbitrary_workbook))
_bad_release_payload = dict(
    _release_payload, artifact_versions=_bad_artifact_versions)
_bad_release_record = {
    "record_ref": "reviews/arbitrary-artifact-content.json",
    "sha256": _archive(
        "reviews/arbitrary-artifact-content.json", _bad_release_payload),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    release_verification=_bad_release_record)
check("a matching hash cannot make arbitrary bytes a release workbook",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "release verification and version evidence is incomplete")

_bad_implementation_payload = dict(
    _release_payload, implementation_sha256="f" * 64)
_bad_release_record = {
    "record_ref": "reviews/bad-implementation-digest.json",
    "sha256": _archive(
        "reviews/bad-implementation-digest.json", _bad_implementation_payload),
}
_bad_evidence = dict(
    _ratified_model["ratification_evidence"],
    release_verification=_bad_release_record)
check("the implementation digest must match the release code and model files",
      _release_blockers(dict(_ratified_model, ratification_evidence=_bad_evidence)),
      "release verification and version evidence is incomplete")

_old_revision = dict(_ratified_model, revision=2)
check("ratification must bump the baseline model revision",
      _release_blockers(_old_revision),
      "model revision was not bumped for ratification")

for _bad_foresight in (
        {"ratified": True},
        dict(_ratified_model["foresight"], method="arbitrary method")):
    _bad_release = dict(_ratified_model, foresight=_bad_foresight)
    check("foresight approval cannot be reduced to a boolean or changed in place",
          _release_blockers(_bad_release),
          "the foresight method is unratified")

for _missing_field, _missing_message in (
        ("status", "model status is not ratified"),
        ("open_decisions", "open-decisions attestation is missing or malformed"),
        ("binding_rules", "binding-rules attestation is missing or empty"),
        ("indicators", "indicator-ratification attestation is missing or malformed"),
        ("foresight", "the foresight method is unratified")):
    _incomplete_model = dict(_ratified_model)
    _incomplete_model.pop(_missing_field)
    check(f"a missing {_missing_field} attestation cannot publish final",
          _release_blockers(_incomplete_model),
          _missing_message)

for _empty_field, _empty_message in (
        ("binding_rules", "binding-rules attestation is missing or empty"),
        ("indicators", "indicator-ratification attestation is missing or malformed")):
    _empty_model = dict(_ratified_model, **{_empty_field: []})
    check(f"an empty {_empty_field} attestation cannot publish final",
          _release_blockers(_empty_model), _empty_message)

_incomplete_rules = dict(
    _ratified_model, binding_rules=_ratified_model["binding_rules"][:-1])
check("an incomplete binding-rule attestation cannot publish final",
      _release_blockers(_incomplete_rules),
      "binding-rules attestation is incomplete or malformed")
_malformed_rule_ids = dict(
    _ratified_model,
    binding_rules=[dict(row, id=[]) for row in _ratified_model["binding_rules"]],
)
check("malformed binding-rule ids fail closed",
      _release_blockers(_malformed_rule_ids),
      "binding-rules attestation is incomplete or malformed")
_skeletal_rules = dict(
    _ratified_model,
    binding_rules=[{"id": row["id"], "ratified": True}
                   for row in _ratified_model["binding_rules"]],
)
check("binding-rule ids and booleans cannot substitute for complete records",
      _release_blockers(_skeletal_rules),
      "binding-rules attestation is incomplete or malformed")
_padded_skeletal_rules = dict(
    _ratified_model,
    binding_rules=[{
        "id": row["id"], "rule": "", "decision": "", "ratified": True,
    } for row in _ratified_model["binding_rules"]],
)
check("blank binding-rule text cannot masquerade as a complete attestation",
      _release_blockers(_padded_skeletal_rules),
      "binding-rules attestation is incomplete or malformed")
_altered_rules = dict(
    _ratified_model,
    binding_rules=[dict(row, rule="Different rule text")
                   for row in _ratified_model["binding_rules"]],
)
check("binding-rule text must match the loaded canonical model",
      _release_blockers(_altered_rules),
      "binding-rules attestation is incomplete or malformed")
_incomplete_indicators = dict(
    _ratified_model, indicators=_ratified_model["indicators"][:-1])
check("an incomplete indicator attestation cannot publish final",
      _release_blockers(_incomplete_indicators),
      "indicator-ratification attestation is incomplete or malformed")
_malformed_indicator_ids = dict(
    _ratified_model,
    indicators=[dict(row, id=[]) for row in _ratified_model["indicators"]],
)
check("malformed indicator ids fail closed",
      _release_blockers(_malformed_indicator_ids),
      "indicator-ratification attestation is incomplete or malformed")
_skeletal_indicators = dict(
    _ratified_model,
    indicators=[{"id": row["id"]} for row in _ratified_model["indicators"]],
)
check("indicator ids cannot substitute for complete scoring records",
      _release_blockers(_skeletal_indicators),
      "indicator-ratification attestation is incomplete or malformed")

_missing_threshold_attestation = dict(
    _ratified_model,
    indicators=[
        {key: value for key, value in row.items()
         if key != "thresholds_ratified"}
        for row in _ratified_model["indicators"]
    ],
)
check("removing threshold holds is not a substitute for affirmative ratification",
      _release_blockers(_missing_threshold_attestation),
      "one or more indicator thresholds are unratified")
check("ratifying the model cannot make an unreviewed narrative final",
      _release_blockers(_ratified_model, reviewed=False),
      ["inputs and narrative have not both been reviewed"])

_render_doc = {
    "country": "Testland",
    "status": "Draft DAR",
    "model_version": "1.7 rev2",
    "assessment_year": 2026,
    "final": False,
    "publication_blockers": ["model <ratification> is incomplete"],
    "fidelity": {"rate": 1.0, "supported": 0, "claimed": 0},
    "chapters": [],
}
_draft_html = D.render_html(_render_doc)
check("a draft renders its escaped publication blockers visibly",
      _draft_html, "model &lt;ratification&gt; is incomplete")
check("a final document renders no publication-hold banner",
      "Publication hold" in D.render_html(dict(
          _render_doc, final=True, status="Final DAR", publication_blockers=[])), False)
try:
    D.render_html(dict(_render_doc, final=True, status="Draft DAR"))
    _contradictory_render = "rendered"
except ValueError as _error:
    _contradictory_render = str(_error)
check("contradictory Final/Draft state is rejected",
      _contradictory_render, "contradicts final=True")


section("Every figure must trace to the engine (E3)")

ALLOWED = {2.71, 109.1, 57.0, 4.0}

check("a figure the engine produced is supported",
      D.fidelity_check("The mean is 2.71.", [{"value": "2.71", "what_it_is": "A1 mean"}],
                       ALLOWED)[0][0]["value"], "2.71")

check("a figure the engine never produced is unsupported",
      D.fidelity_check("The mean is 3.44.", [{"value": "3.44", "what_it_is": "A1 mean"}],
                       ALLOWED)[1][0]["value"], "3.44")

check("a number in the prose that was never declared is a stray",
      # The shape this check most has to catch: a fabricated figure the writer did not
      # even list among its figures.
      D.fidelity_check("Coverage reached 63.2% last year.", [], ALLOWED)[2], ["63.2"])

check("a number hidden in the free-text description does not become declared",
      D.fidelity_check(
          "The programme serves 999 million farmers.",
          [{"value": "109.1", "what_it_is": "a programme serving 999 million farmers"}],
          ALLOWED)[2], ["999"])

check("a declared scale does not authorize a different scale in prose",
      D.fidelity_check(
          "The facility carries US$109.1 billion.",
          [{"value": "US$109.1 million", "what_it_is": "facility size"}],
          ALLOWED)[2], ["109.1"])

check("a small count is ordinary prose, not a stray",
      D.fidelity_check("The seven pillars divide into four layers.", [], ALLOWED)[2], [])

check("an arbitrary written-out count is not ordinary prose",
      D.fidelity_check("Nine schools joined the programme.", [], ALLOWED)[2],
      ["Nine schools"])

check("the fixed DAR structure remains ordinary prose",
      D.fidelity_check(
          "The eleven chapters cover three pillars across four layers.", [], ALLOWED)[2],
      [])

check("a numeric district count is substantive and must be declared",
      D.fidelity_check("The programme targets 10 districts.", [], ALLOWED)[2], ["10"])

check("a calendar year is ordinary prose",
      D.fidelity_check("The strategy was published in 2023.", [], ALLOWED)[2], [])

check("a calendar year may be followed by an ordinary clause",
      D.fidelity_check("In 2023 the ministry published the strategy.", [], ALLOWED)[2], [])

check("a year-shaped quantity is not mistaken for a calendar reference",
      D.fidelity_check("The shipment weighed 2020 tonnes.", [], ALLOWED)[2], ["2020"])

check("a year-shaped beneficiary count is substantive",
      D.fidelity_check("The programme reached 2025 farmers.", [], ALLOWED)[2], ["2025"])

check("a future target year must be declared",
      D.fidelity_check("The target year is 2030.", [], ALLOWED)[2], ["2030"])

check("a named national vision is a reference rather than a new target",
      D.fidelity_check("The mandate sits within Egypt Vision 2030.", [], ALLOWED)[2], [])

check("an undeclared L-prefixed maturity level is substantive",
      D.fidelity_check("The indicator is at L5.", [], ALLOWED)[2], ["5"])

check("a year written as a currency amount is not ordinary prose",
      D.fidelity_check("The budget is US$2020.", [], ALLOWED)[2], ["2020"])

check("a small integer with a scale is not an ordinary count",
      D.fidelity_check("The programme targets 12 million farmers.", [], ALLOWED)[2], ["12"])

check("a written-out scaled count is still a numeric claim",
      D.fidelity_check("The programme targets twelve million farmers.", [], ALLOWED)[2],
      ["twelve million farmers"])

check("a dozen is a numeric claim rather than an ordinary article",
      D.fidelity_check("The programme covers a dozen districts.", [], ALLOWED)[2],
      ["a dozen districts"])

check("a half-dozen is a numeric claim",
      D.fidelity_check("The pilot covers a half-dozen districts.", [], ALLOWED)[2],
      ["half-dozen districts"])

check("a written-out large currency claim is still a numeric claim",
      D.fidelity_check(
          "The programme costs nine hundred ninety-nine billion dollars.", [], ALLOWED)[2],
      ["nine hundred ninety-nine billion dollars"])

check("scientific notation is a numeric claim",
      D.fidelity_check("The programme claims 1e9 farmers.", [], ALLOWED)[2], ["1e9"])

check("scientific notation preserves mantissa precision",
      D._numeric_mentions("The programme claims 1.234e3 farmers.")[0]["number"], 1234.0)

check("a superscript exponent is a numeric claim",
      D.fidelity_check("The programme claims 10² farmers.", [], ALLOWED)[2], ["10²"])

check("a hyphenated numeric compound is a substantive claim",
      D.fidelity_check("The programme starts a 12-school rollout.", [], ALLOWED)[2],
      ["12"])

check("compact k notation carries the thousand scale",
      D.fidelity_check("The programme claims 250k farmers.", [], ALLOWED)[2], ["250"])

_hyphenated_decimal = D._numeric_mentions("Capacity is 3.6-gigawatt.")
check("a decimal before a hyphen is never truncated to its integer prefix",
      [_hyphenated_decimal[0]["raw"], _hyphenated_decimal[0]["number"]], ["3.6", 3.6])

check("a leading-decimal scaled claim is still a numeric claim",
      D.fidelity_check("The programme reaches .5 million farmers.", [], ALLOWED)[2],
      [".5"])

check("a fractional word is still a numeric claim",
      D.fidelity_check("Half of farmers use the service.", [], ALLOWED)[2], ["Half"])

check("an article fraction is a numeric claim",
      D.fidelity_check("A third of farmers use the service.", [], ALLOWED)[2],
      ["A third"])
check("an approximate article fraction cannot disappear",
      D.fidelity_check("Roughly a third of farmers use the service.", [], ALLOWED)[2],
      ["a third"])

_word_fractions = D._numeric_mentions(
    "One half of farmers and one quarter of households use it.")
check("one plus a fraction word composes as a fraction, not addition",
      [mention["number"] for mention in _word_fractions], [0.5, 0.25])
check("fraction words retain their semantic dimension",
      [(mention["unit"], mention["measure"]) for mention in _word_fractions],
      [("fraction", "farmers"), ("fraction", "households")])

_article_scales = D._numeric_mentions(
    "A million farmers, about a billion dollars, and a thousand households.")
check("article-scaled quantities preserve scale, measure, and currency",
      [(item["number"], item["scale"], item["measure"], item["currency"])
       for item in _article_scales],
      [(1.0, "million", "farmers", ""),
       (1.0, "billion", "", "USD"),
       (1.0, "thousand", "households", "")])

_mixed_scales = D._numeric_mentions(
    "Half a million farmers and one and a half million households.")
check("conventional fractional scales are each one atomic quantity",
      [(item["number"], item["scale"], item["measure"])
       for item in _mixed_scales],
      [(0.5, "million", "farmers"), (1.5, "million", "households")])

check("an ordinal structural phrase is not mistaken for a fractional claim",
      D._numeric_mentions("The third pillar records the result."), [])
check("ordinary hyphenated compounds are not mistaken for article fractions",
      D._numeric_mentions(
          "A third-party platform uses a fourth-generation network in a third-quarter report."),
      [])
check("ordinary whitespace ordinals are not mistaken for article fractions",
      D._numeric_mentions(
          "A third party audits a fourth generation network beside a third pillar."),
      [])
check("a hyphenated one-third share remains a numeric claim",
      D._numeric_mentions("One-third of farmers use it.")[0]["number"], 1 / 3)

_hyphenated_fraction_scales = D._numeric_mentions(
    "A third-million users, a half-million farmers, and a quarter-million households.")
check("hyphenated fractional scales remain atomic quantities",
      [(item["number"], item["scale"], item["measure"])
       for item in _hyphenated_fraction_scales],
      [(1 / 3, "million", "users"),
       (0.5, "million", "farmers"),
       (0.25, "million", "households")])

_signed_words = D._numeric_mentions("The changes are minus 3.6 and negative five.")
check("minus before digits carries a negative sign",
      [_signed_words[0]["number"], _signed_words[0]["sign"]], [-3.6, "-"])
check("negative before a number word carries a negative sign",
      [_signed_words[1]["number"], _signed_words[1]["sign"],
       _signed_words[1]["word"]], [-5.0, "-", True])

check("a word-sign reversal is not supported by a positive legacy value",
      len(D.fidelity_check(
          "The change is negative 3.6.",
          [{"value": "negative 3.6", "what_it_is": "change"}], {3.6})[1]), 1)

check("a written ratio is not two ordinary enumerations",
      D.fidelity_check("One in two farmers uses the service.", [], ALLOWED)[2],
      ["One", "two farmers"])

check("a small percentage is not an ordinary count",
      D.fidelity_check("Adoption is 5%.", [], ALLOWED)[2], ["5"])

check("an ASCII percentage range exposes both undeclared endpoints",
      D.fidelity_check("Coverage is 25-70%.", [], ALLOWED)[2], ["25", "70"])

check("a percentage is never ordinary",
      D.fidelity_check("Adoption stands at 41.8%.", [], ALLOWED)[2], ["41.8"])

check("a declared figure is not also counted as a stray",
      D.fidelity_check("The value is 109.1.", [{"value": "109.1", "what_it_is": "1.4"}],
                       ALLOWED)[2], [])

check("a figure written to fewer decimals is still that figure",
     # A chapter writing the A1 mean of 2.71 as "2.7" has fabricated nothing, and
     # blocking the document for it would train everyone to loosen the gate.
      D.fidelity_check("The mean is 2.7.",
                       [{"value": "2.7", "what_it_is": "rounded A1 mean"}],
                       ALLOWED)[2], [])

check("rounding is only tolerated toward a real figure",
      D.fidelity_check("The mean is 2.9.", [], ALLOWED)[2], ["2.9"])

check("a bare integer does not silently stand for a decimal figure",
      # Even though 109.1 rounds to 109, B5 requires the prose figure to be declared.
      D.fidelity_check("Coverage of 109 was recorded.", [], ALLOWED)[2], ["109"])

check("a small numeric count is not automatically ordinary", D._ordinary(12), False)
check("thirteen is not an ordinary count", D._ordinary(13), False)
check("a decimal is never ordinary", D._ordinary(4.5), False)


section("Every substantive figure declares its basis and origin")

ORIGIN_QUANTITIES = {
    "source:test": [
        (109.1, "USD", "million", "", "+"),
        (7.0, "", "", "", "+"),
        (8.0, "", "", "", "+"),
    ],
    "pillar:A1:n": [(10.0, "", "", "", "+", "rows")],
    "pillar:A1:rated": [(5.0, "", "", "", "+", "rows")],
    "source:score-ten": [(10.0, "", "", "", "+", "score")],
    "pillar:A1:mean": [(3.6, "", "", "", "+", "score")],
    "pillar:C3:rated": [(7.0, "", "", "", "+", "rows")],
    "pillar:C3:n": [(8.0, "", "", "", "+", "rows")],
    "indicator:1.4:level": [(3.0, "", "", "", "+", "level")],
    "indicator:1.4:year": [(2022.0, "", "", "", "+", "year")],
    "indicator:1.3:value": [(18.0, "", "", "percent", "+", "")],
    "source:range-low": [(25.0, "", "", "percent", "+", "")],
    "source:range-high": [(70.0, "", "", "percent", "+", "")],
    "source:dozen": [(12.0, "", "", "", "+", "districts")],
    "source:scientific": [(1000000000.0, "", "", "", "+", "farmers")],
    "source:superscript": [(100.0, "", "", "", "+", "farmers")],
    "source:compact-thousand": [(250.0, "", "thousand", "", "+", "farmers")],
    "source:score-three": [(3.0, "", "", "", "+", "score")],
}

def typed_figure(value, basis="evidence", refs=None, inputs=None,
                 rationale="Traceable basis.", operation=None):
    return {
        "value": value, "what_it_is": "test figure", "basis": basis,
        "source_refs": ["source:test"] if refs is None else refs,
        "inputs": [] if inputs is None else inputs, "rationale": rationale,
        "operation": ("percentage" if basis == "calculation" else "none")
        if operation is None else operation,
    }


check("source-backed evidence with the same unit and scale is supported",
      len(D.fidelity_check(
          "The facility is US$109.1 million.",
          [typed_figure("US$109.1 million")], {109.1},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("an atomic score origin supports its natural bare rendering",
      len(D.fidelity_check(
          "The A1 mean is 3.6.",
          [typed_figure("3.6", refs=["pillar:A1:mean"])], {3.6},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("an unknown unit cannot relabel a score origin",
      len(D.fidelity_check(
          "The A1 capacity is 3.6 gigawatts.",
          [typed_figure("3.6 gigawatts", refs=["pillar:A1:mean"])], {3.6},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a word-sign reversal is not supported by a positive score origin",
      len(D.fidelity_check(
          "The A1 change is negative 3.6.",
          [typed_figure("negative 3.6", refs=["pillar:A1:mean"])], {3.6},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a bare score declaration does not cover an unknown prose unit",
      D.fidelity_check(
          "The A1 capacity is 3.6 gigawatts.",
          [typed_figure("3.6", refs=["pillar:A1:mean"])], {3.6},
          allowed_quantities=ORIGIN_QUANTITIES)[2], ["3.6"])

check("a singular unknown noun cannot relabel a score origin",
      len(D.fidelity_check(
          "The A1 capacity is 3.6 sheep.",
          [typed_figure("3.6 sheep", refs=["pillar:A1:mean"])], {3.6},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("an evidence range requires both atomic endpoints",
      len(D.fidelity_check(
          "Coverage is 25-70%.",
          [typed_figure("25-70%", refs=["source:range-low", "source:range-high"])],
          {25, 70}, allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("one origin cannot authorize an evidence range",
      len(D.fidelity_check(
          "Coverage is 25-70%.",
          [typed_figure("25-70%", refs=["source:range-low"])],
          {25, 70}, allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a dozen normalizes to its source-backed quantity",
      len(D.fidelity_check(
          "The programme covers a dozen districts.",
          [typed_figure("a dozen districts", refs=["source:dozen"])], {12},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("scientific notation normalizes to its source-backed quantity",
      len(D.fidelity_check(
          "The programme covers 1e9 farmers.",
          [typed_figure("1e9 farmers", refs=["source:scientific"])], {1000000000},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("a superscript exponent normalizes to its source-backed quantity",
      len(D.fidelity_check(
          "The programme covers 10² farmers.",
          [typed_figure("10² farmers", refs=["source:superscript"])], {100},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("compact k notation matches the thousand-scale origin",
      len(D.fidelity_check(
          "The programme covers 250k farmers.",
          [typed_figure("250k farmers", refs=["source:compact-thousand"])], {250},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("an integer score origin cannot authorize a hyphenated decimal claim",
      len(D.fidelity_check(
          "Capacity is 3.6-gigawatt.",
          [typed_figure("3.6-gigawatt", refs=["source:score-three"])], {3},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a proposed range remains a valid planning assumption",
      len(D.fidelity_check(
          "The proposal targets 25-70% coverage.",
          [typed_figure("25-70%", "planning_assumption", refs=[],
                        rationale="An explicitly proposed planning range.")],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[0]), 1)

check("a factual range cannot be laundered as a planning assumption",
      len(D.fidelity_check(
          "Coverage is 25-70%.",
          [typed_figure("25-70%", "planning_assumption", refs=[],
                        rationale="A range labelled as an assumption to evade B5.")],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[1]), 1)

check("a natural row-count pair requires both atomic origins",
      len(D.fidelity_check(
          "C3 has 7 of 8 rows rated.",
          [typed_figure("7 of 8 rows",
                        refs=["pillar:C3:rated", "pillar:C3:n"])], {7, 8},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("a bare pair cannot combine different inferred semantics",
      len(D.fidelity_check(
          "The ratio is 5 of 10.",
          [typed_figure("5 of 10",
                        refs=["pillar:A1:rated", "source:score-ten"])], {5, 10},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("the right number from the wrong scale is not source-backed",
      len(D.fidelity_check(
          "The facility is US$109.1 billion.",
          [typed_figure("US$109.1 billion")], {109.1},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a reasoned planning assumption is valid only in a prescriptive chapter",
      len(D.fidelity_check(
          "The proposed envelope is US$999 billion.",
          [typed_figure("US$999 billion", "planning_assumption", refs=[],
                        rationale="A deliberately declared planning assumption.")],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[0]), 1)

check("a planning assumption cannot enter a diagnostic chapter",
      len(D.fidelity_check(
          "The envelope is US$999 billion.",
          [typed_figure("US$999 billion", "planning_assumption", refs=[],
                        rationale="A deliberately declared planning assumption.")],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=False)[1]), 1)

check("a factual claim cannot be laundered as a planning assumption",
      len(D.fidelity_check(
          "Egypt currently has 999 million farmers.",
          [typed_figure("999 million farmers", "planning_assumption", refs=[],
                        rationale=("This is deliberately labelled an assumption only "
                                   "to try to pass the gate."))],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[1]), 1)

check("an unrelated modal cannot launder a factual planning assumption",
      len(D.fidelity_check(
          "The roadmap should note that Egypt currently has 999 million farmers.",
          [typed_figure("999 million farmers", "planning_assumption", refs=[],
                        rationale=("A modal elsewhere in the sentence does not make "
                                   "the asserted population a proposal."))],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[1]), 1)

check("a consequence modal cannot launder a factual planning assumption",
      len(D.fidelity_check(
          "Egypt currently has 999 million farmers, which would affect delivery.",
          [typed_figure("999 million farmers", "planning_assumption", refs=[],
                        rationale=("A hypothetical consequence does not make the "
                                   "asserted population a proposal."))],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[1]), 1)

check("a proposed report cannot launder the fact it would report",
      len(D.fidelity_check(
          "The roadmap proposes to report that Egypt currently has 999 million farmers.",
          [typed_figure("999 million farmers", "planning_assumption", refs=[],
                        rationale=("Proposing to repeat an assertion does not make "
                                   "the asserted population a proposal."))],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[1]), 1)

check("a targeted study cannot launder the fact it claims",
      len(D.fidelity_check(
          "The roadmap targets a study claiming Egypt currently has 999 million farmers.",
          [typed_figure("999 million farmers", "planning_assumption", refs=[],
                        rationale=("Targeting a study does not make the study's "
                                   "asserted population a proposal."))],
          set(), allowed_quantities=ORIGIN_QUANTITIES, prescriptive=True)[1]), 1)

check("a ratio calculation is traceable to its declared inputs",
      len(D.fidelity_check(
          "Coverage is more than 80 percent.",
          [typed_figure("more than 80 percent", "calculation",
                        inputs=["7", "8"],
                        rationale="Seven divided by eight is 87.5 percent.")],
          {7, 8}, allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("a percentage calculation preserves the shared input semantic",
      len(D.fidelity_check(
          "Coverage is 87.5 percent.",
          [typed_figure("87.5 percent", "calculation",
                        refs=["pillar:C3:rated", "pillar:C3:n"],
                        inputs=["7 rows", "8 rows"], operation="percentage",
                        rationale="Seven rows divided by eight rows is 87.5 percent.")],
          {7, 8}, allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("an ordinal level retains its field semantic",
      len(D.fidelity_check(
          "The indicator is at level 3.",
          [typed_figure("level 3", refs=["indicator:1.4:level"])], {3},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("a calculation cannot invent currency or scale",
      len(D.fidelity_check(
          "The total is US$15 billion.",
          [typed_figure("US$15 billion", "calculation", inputs=["7", "8"],
                        operation="sum",
                        rationale="Seven plus eight is fifteen.")],
          {7, 8}, allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a field-level row count cannot be relabelled as districts",
      len(D.fidelity_check(
          "The programme covers 10 districts.",
          [typed_figure("10 districts", refs=["pillar:A1:n"])], {10},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a field-level row count retains its actual semantic unit",
      len(D.fidelity_check(
          "The assessment covers 10 rows.",
          [typed_figure("10 rows", refs=["pillar:A1:n"])], {10},
          allowed_quantities=ORIGIN_QUANTITIES)[0]), 1)

check("a bare count does not omit its row semantic",
      len(D.fidelity_check(
          "The assessment reports 10.",
          [typed_figure("10", refs=["pillar:A1:n"])], {10},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a declared composite does not authorize the same component elsewhere",
      D.fidelity_check(
          "C3 has 7 of 8 rows rated. Another table reports 7 rows.",
          [typed_figure("7 of 8 rows",
                        refs=["pillar:C3:rated", "pillar:C3:n"])], {7, 8},
          allowed_quantities=ORIGIN_QUANTITIES)[2], ["7"])

check("a figure must appear in the prose in the declared form",
      len(D.fidelity_check(
          "The assessment covers ten rows.",
          [typed_figure("10 rows", refs=["pillar:A1:n"])], {10},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("an observation year cannot be relabelled as a beneficiary count",
      len(D.fidelity_check(
          "The programme reaches 2022 farmers.",
          [typed_figure("2022 farmers", refs=["indicator:1.4:year"])], {2022},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a percent value cannot be relabelled as hectares",
      len(D.fidelity_check(
          "Coverage is 18 hectares.",
          [typed_figure("18 hectares", refs=["indicator:1.3:value"])], {18},
          allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)

check("a calculation cannot invent an unmodelled physical unit",
      len(D.fidelity_check(
          "The product is 56 tonnes.",
          [typed_figure("56 tonnes", "calculation", inputs=["7", "8"],
                        operation="product",
                        rationale="Seven times eight is fifty-six.")],
          {7, 8}, allowed_quantities=ORIGIN_QUANTITIES)[1]), 1)


section("What the engine is allowed to have produced")

ASSESS = {
    "pillars": {"A1": {"n": 8, "rated": 7, "held": 1, "mean": 2.71, "band": "Established",
                       "margin": 0.21, "comp": 0.9, "stale": 2}},
    "layers": {}, "matrix": {"ADV": {"n_bearing": 5, "mean_readiness": 3.2,
                                     "mean_need": 2.0, "mean_outcome": 1.5, "mean_driven": 2.5}},
    "counts": {"Measured": 30, "Documented": 15, "Judged": 7, "Gap": 5},
    "rated": 47, "held": 5,
    "indicators": {"1.4": {"level": 3, "value": 109.1, "year": 2022}},
}

check("pillar means are allowed", 2.71 in D.allowed_figures(ASSESS), True)
check("indicator values are allowed", 109.1 in D.allowed_figures(ASSESS), True)
check("matrix means are allowed", 3.2 in D.allowed_figures(ASSESS), True)
check("a figure nobody produced is not allowed", 3.44 in D.allowed_figures(ASSESS), False)
check("milestone targets are allowed once foresight has run",
      2033.0 in D.allowed_figures(ASSESS, {"milestones": [{"target_level": 4,
                                                           "target_year": 2033}]}), True)


section("Reviewed assessment rows obey the engine input contract")


def valid_review_rows():
    return {
        iid: {
            "value": "Reviewed source records the indicator.",
            "cls": "Documented", "level": None, "year": 2025,
            "src": "Official reviewed source", "note": "Reviewed at G2.",
            "tier": "T3", "url": "https://example.org/source",
        }
        for iid in D.MODEL
    }


def review_errors(iid, **changes):
    rows = valid_review_rows()
    rows[iid].update(changes)
    return D.assessment_input_errors(rows)


check("a complete reviewed input with withheld levels is valid",
      D.assessment_input_errors(valid_review_rows()), [])


def ratified_review_rows():
    rows = valid_review_rows()
    for indicator_id, row in rows.items():
        row["definition_metadata"] = _ratified_definition_metadata(indicator_id)
    return rows


check("ratified inputs bind every row to its exact definition and calibration",
      D.assessment_input_errors(ratified_review_rows(), spec=_ratified_model), [])
_unbound_ratified_rows = ratified_review_rows()
_unbound_ratified_rows["1.1"].pop("definition_metadata")
check("a ratified model rejects a row with no definition metadata",
      D.assessment_input_errors(_unbound_ratified_rows, spec=_ratified_model),
      "row 1.1 missing ratified definition_metadata")
_downgraded_ratified_rows = ratified_review_rows()
_downgraded_ratified_rows["1.1"].update({
    "value": "Synthetic documented substitute.",
    "cls": "Documented", "level": 3, "tier": "T3",
})
check("a ratified threshold score requires a Measured observation",
      D.assessment_input_errors(
          _downgraded_ratified_rows, spec=_ratified_model),
      "row 1.1 threshold score requires a Measured observation")
_held_ratified_rows = copy.deepcopy(_downgraded_ratified_rows)
_held_ratified_rows["1.1"]["level"] = None
check("a documented threshold mismatch may remain explicitly held",
      D.assessment_input_errors(_held_ratified_rows, spec=_ratified_model), [])
_recut_validation_model = copy.deepcopy(_ratified_model)
_recut_indicator = next(
    row for row in _recut_validation_model["indicators"]
    if row["id"] == "1.1")
_legacy_first_cut = _recut_indicator["thresholds"][0]
_recut_indicator["thresholds"][0] = _legacy_first_cut + 1
_recut_definition = _recut_validation_model[
    "indicator_definitions"]["entries"]["1.1"]
_recut_definition["scoring"]["cuts"][0] = _legacy_first_cut + 1
_recut_validation_rows = ratified_review_rows()
_recut_validation_rows["1.1"].update({
    "value": _legacy_first_cut, "cls": "Measured", "level": 1,
    "tier": "T1",
})
_recut_validation_rows["1.1"]["definition_metadata"].update({
    "definition_sha256": D._canonical_sha256(_recut_definition),
    "transform_inputs": {"source_value": _legacy_first_cut},
})
check("ratified input validation derives levels from the supplied model cuts",
      D.assessment_input_errors(
          _recut_validation_rows, spec=_recut_validation_model), [])
check("the evidence class vocabulary is exact",
      review_errors("1.1", cls="BANANA"), "row 1.1 cls")

for bad_level in (True, 2.5, 0, 6):
    check(f"level {bad_level!r} is outside the exact level contract",
          review_errors("1.1", level=bad_level), "row 1.1 level")

check("a Gap can never carry a level",
      review_errors(
          "1.1", value="DATA GAP — searched the official series", cls="Gap", level=1,
          year=2026, src="Structured source search", note="Search trail recorded.",
          tier="", url=""),
      "Gap level must be null")
check("a numeric-looking string is not a Measured value",
      review_errors("1.1", value="12", cls="Measured", level=None,
                    tier="T1"),
      "Measured value must be a finite number")
check("NaN is not a Measured value",
      review_errors("1.1", value=float("nan"), cls="Measured", level=None,
                    tier="T1"),
      "Measured value must be a finite number")
check("a year encoded as text is invalid",
      review_errors("1.1", year="2025"), "row 1.1 year")
check("a future observation year is invalid",
      review_errors("1.1", year=2027), "row 1.1 year")
check("a pre-modern observation year is invalid",
      review_errors("1.1", year=1899), "row 1.1 year")

check("a threshold-derived Measured level cannot contradict its value",
      review_errors(
          "1.1", value=1000.0, cls="Measured", level=5, year=2025,
          src="Official statistical series", tier="T1",
          url="https://example.org/statistic"),
      "Measured level does not match its thresholds")

check("a numeric value cannot masquerade as Documented evidence",
      review_errors("1.1", value=12.0, cls="Documented"),
      "Documented value must be non-gap text")

check("T5 cannot produce Documented evidence",
      review_errors("1.1", tier="T5"),
      "Documented provenance requires source, URL, and a T1-T4 tier")

_unknown_rows = valid_review_rows()
_unknown_rows["NOT-A-MODEL-ROW"] = dict(_unknown_rows["1.1"])
check("an unknown non-candidate row is rejected",
      D.assessment_input_errors(_unknown_rows), "unknown non-model row")

_candidate_rows = valid_review_rows()
_candidate_rows["C2-CAND-SOIL-API"] = {
    "value": "A proposed interoperability observation.",
    "cls": "Documented", "level": None, "year": 2025,
    "src": "Official reviewed source", "note": "Candidate, never scored.",
    "tier": "T3", "url": "https://example.org/candidate",
}
check("a canonical candidate with no level is valid",
      D.assessment_input_errors(_candidate_rows), [])
check("the Annex selector carries candidates from every canonical pillar",
      list(D._candidate_input_rows(_candidate_rows)), ["C2-CAND-SOIL-API"])

_levelled_candidate_rows = {key: dict(value) for key, value in _candidate_rows.items()}
_levelled_candidate_rows["C2-CAND-SOIL-API"]["level"] = 2
check("a candidate can never carry a score",
      D.assessment_input_errors(_levelled_candidate_rows),
      "candidate level must be null")

_missing_source_rows = valid_review_rows()
del _missing_source_rows["1.1"]["src"]
check("source provenance fields are required",
      D.assessment_input_errors(_missing_source_rows), "row 1.1 missing required field src")


section("The gate blocks the emit (E5)")


def doc(**over):
    ch = dict(n="3", title="Vision", kind="prescriptive",
              status="proposed, not evidenced", provenance="Chapter 3 draws on ...",
              cited_outside_binding=[], stray_numbers=[])
    base = {"chapters": [dict(ch, **over.pop("chapter", {}))],
            "fidelity": {"rate": 1.0, "claimed": 4, "supported": 4, "unsupported": 0}}
    base.update(over)
    return base


def failing(d):
    return [n for n, ok, _ in D.qc_checks(d) if not ok]


check("a clean single-chapter document fails only the completeness check",
      failing(doc()), ["B6 every chapter of the outline is present"])

check("a chapter with no provenance banner blocks the emit",
      "B1 every chapter carries a provenance banner" in failing(doc(chapter={"provenance": ""})),
      True)

check("citing outside the binding blocks the emit",
      "B2 every citation and prose claim stays within its binding"
      in failing(doc(chapter={"cited_outside_binding": ["pillar E1"]})), True)

check("a prescriptive chapter presented as evidenced blocks the emit",
      # The one a reader must not miss, so it is stated three times: on the page, in the
      # record, and here.
      "B3 no prescriptive chapter renders as evidenced"
      in failing(doc(chapter={"status": "evidenced by the assessment"})), True)

# Fidelity binds on the chapters that make claims about the country. Chapters three to
# ten propose an investment programme — a budget line, a district count — and the engine
# could not have produced those figures. Holding a proposal to "every number traces to the
# assessment" asks it to be evidence, which is the one thing it is marked as not being.
# On the first Egypt roadmap the evidence chapters ran at 97% and the prescriptive ones at
# 52%, and the blended 53% was read as the document being unsupported.
_EVID = dict(n="2", title="Where the country stands", kind="diagnostic",
             status="evidenced by the assessment", provenance="Chapter 2 draws on ...",
             cited_outside_binding=[], stray_numbers=[],
             figures=[{"value": "1"}] * 10,
             unsupported_figures=[{"value": "9.9"}] * 2)

check("fidelity below the floor blocks the emit, on an evidence chapter",
      "B4 evidence-chapter figure fidelity at or above 95%"
      in failing({"chapters": [_EVID], "fidelity": {"rate": 0.8, "claimed": 10,
                                                    "supported": 8, "unsupported": 2}}),
      True)

check("an evidence chapter at the floor passes",
      "B4 evidence-chapter figure fidelity at or above 95%"
      in failing({"chapters": [dict(_EVID, figures=[{"value": "1"}] * 20,
                                    unsupported_figures=[{"value": "9.9"}])],
                  "fidelity": {"rate": 0.95, "claimed": 20, "supported": 19,
                               "unsupported": 1}}),
      False)

check("a prescriptive chapter's proposed figures never block the emit",
      "B4 evidence-chapter figure fidelity at or above 95%"
      in failing(doc(chapter={"figures": [{"value": "USD 269.64 million"}] * 10,
                              "unsupported_figures": [{"value": "USD 269.64 million"}] * 9})),
      False)

check("undeclared numbers block the emit",
      "B5 no undeclared numbers in the prose"
      in failing(doc(chapter={"stray_numbers": ["63.2"]})), True)

check("an untraceable declared proposal also blocks the emit",
      "B5 no undeclared numbers in the prose"
      in failing(doc(chapter={"figures": [{"value": "US$999 billion"}],
                              "unsupported_figures": ["US$999 billion"]})), True)


section("The outline is read from the model")

check("all eleven chapters are declared", len(D.OUTLINE), 11)
check("chapters 3 to 10 are prescriptive",
      sum(1 for c in D.OUTLINE if c["kind"] == "prescriptive"), 8)
check("the fidelity floor is high enough to mean something", D.FIDELITY_FLOOR >= 0.95, True)


section("A run id identifies content and the resolved adapter")

RUN_INPUTS_HERE = {
    "engine_input": {"file": "/first/run/g2_input.json", "sha256": "a" * 64},
    "replay": {"file": "/first/tapes/replay.json", "sha256": "b" * 64},
}
RUN_INPUTS_THERE = {
    "engine_input": {"file": "/second/run/g2_input.json", "sha256": "a" * 64},
    "replay": {"file": "/second/tapes/replay.json", "sha256": "b" * 64},
}
RUN_IMPLEMENTATION = {
    "generator": {"file": "/source/generate_dar.py", "sha256": "c" * 64},
}

check(
    "relocating identical replay content keeps the same run id",
    D.content_run_id(
        "Egypt", "EGY", D.ASSESSMENT_YEAR, RUN_INPUTS_HERE, RUN_IMPLEMENTATION,
        {"mode": "replay", "resolved": "replay/frozen-v2"}),
    D.content_run_id(
        "Egypt", "EGY", D.ASSESSMENT_YEAR, RUN_INPUTS_THERE, RUN_IMPLEMENTATION,
        {"mode": "replay", "resolved": "replay/frozen-v2"}))

check(
    "different resolved live models have different run ids",
    D.content_run_id(
        "Egypt", "EGY", D.ASSESSMENT_YEAR, RUN_INPUTS_HERE, RUN_IMPLEMENTATION,
        {"mode": "live", "resolved": "anthropic/model-a"})
    != D.content_run_id(
        "Egypt", "EGY", D.ASSESSMENT_YEAR, RUN_INPUTS_HERE, RUN_IMPLEMENTATION,
        {"mode": "live", "resolved": "openai/model-b"}),
    True)


def outline_records():
    records = []
    for chapter in D.OUTLINE:
        record = dict(
            n=str(chapter["n"]), title=chapter["title"], kind=chapter["kind"],
            status=("proposed, not evidenced" if chapter["kind"] == "prescriptive"
                    else "evidenced by the assessment"),
            prose="Complete chapter prose.", provenance="Traceable provenance.",
            cited_outside_binding=[], figures=[], unsupported_figures=[],
            stray_numbers=[],
        )
        if str(chapter["n"]) == "A":
            record["annex"] = {"schema_version": "damm.dar.annex/v1"}
        records.append(record)
    return records


_complete_doc = {"chapters": outline_records(),
                 "fidelity": {"rate": 1.0, "claimed": 0,
                              "supported": 0, "unsupported": 0}}
check("the exact ordered outline passes B6",
      "B6 every chapter of the outline is present" in failing(_complete_doc), False)

_duplicates = outline_records()
_duplicates[-1] = dict(_duplicates[0])
check("eleven records with a duplicate chapter id fail B6",
      "B6 every chapter of the outline is present"
      in failing({"chapters": _duplicates, "fidelity": _complete_doc["fidelity"]}), True)

_wrong_order = outline_records()
_wrong_order[0], _wrong_order[1] = _wrong_order[1], _wrong_order[0]
check("the right chapter ids in the wrong order fail B6",
      "B6 every chapter of the outline is present"
      in failing({"chapters": _wrong_order, "fidelity": _complete_doc["fidelity"]}), True)

_empty_annex = outline_records()
_empty_annex[-1]["annex"] = {}
check("Annex A without its deterministic payload fails B6",
      "B6 every chapter of the outline is present"
      in failing({"chapters": _empty_annex, "fidelity": _complete_doc["fidelity"]}), True)



section("A binding that says every one of these means every one of these")

_A = {"pillars": {"A1": {}, "C1": {}}, "indicators": {"1.1": {}, "2.4": {}},
      "matrix": {"ADV": {}, "FIN": {}}, "prereq": {"2.1": {}, "7.12": {}}}

_b = D.expand_binding({"prerequisites": ["*"], "pillars": ["A1"]}, _A)
check("the wildcard expands to every id of its kind", sorted(_b["prerequisites"]), ["2.1", "7.12"])
check("an explicit list is left alone", _b["pillars"], ["A1"])

# The pack looked up an id called "*", found nothing, and handed chapters bound to every
# prerequisite no prerequisite evidence at all. The gate then compared each cited id
# against the literal set {"*"} and failed every one. The chapters most entitled to the
# evidence were starved of it and then failed for going to look elsewhere.
check("a cited prerequisite inside a wildcard binding is allowed",
      D.binding_gate({"prerequisites": ["2.1"]}, {"prerequisites": ["*"]}, _A), [])
check("without the assessment the wildcard cannot be expanded, and nothing is claimed clean",
      D.binding_gate({"prerequisites": ["2.1"]}, {"prerequisites": ["*"]}), ["prerequisite 2.1"])
check("a genuine violation is still caught",
      D.binding_gate({"indicators": ["9.9"]}, {"indicators": ["1.1"]}, _A), ["indicator 9.9"])


section("A figure stated as a pair or a rung is still a figure")

_ALLOWED = {5.0, 10.0, 3.0, 3.6, 2.5}

# "5 of 10" is a coverage denominator and "level 3" is a rung; both come straight out of
# the pack. Unparseable before, so the writer quoting the evidence exactly was recorded as
# claiming something the engine never produced — 74 of the 95 figures the first Egypt
# roadmap was blocked over were this shape.
check("a coverage pair is supported when both halves are",
      D._composite_supported("5 of 10", _ALLOWED), True)
check("a pair with an invented half is not",
      D._composite_supported("5 of 99", _ALLOWED), False)
check("a rung is supported when the level is",
      D._composite_supported("level 3", _ALLOWED), True)
check("a plain number is not a composite",
      D._composite_supported("3.6", _ALLOWED) is None, True)

_sup, _uns, _ = D.fidelity_check("", [{"value": "5 of 10"}, {"value": "level 3"}], _ALLOWED)
check("composites reach the supported list", len(_sup), 2)
check("and none is called unsupported", len(_uns), 0)


section("An id in the prose is a reference, not a claim about the country")

_IDS = {"3.11", "1.3", "4.4"}

check("a parenthesised id is a reference",
      sorted(D.reference_ids("interoperability standards (3.11) are absent", _IDS)), ["3.11"])
check("a named row is a reference",
      sorted(D.reference_ids("row 3.11 and indicator 1.3", _IDS)), ["1.3", "3.11"])
# The roadmap writes "— 3.11" and "; 3.3" as often as it writes "(3.11)", and no reading
# of the surrounding words separates those from a quantity. The chapter's own declared
# citations do.
check("a bare id the chapter cited is a reference",
      sorted(D.reference_ids("what blocks it — 3.11", _IDS, cited_ids=["3.11"])), ["3.11"])
check("a bare id the chapter did not cite is left to be checked",
      sorted(D.reference_ids("a mean of 3.11", _IDS)), [])
check("a figure that happens to equal an id is still checked",
      sorted(D.reference_ids("the pillar mean 3.11 is Established", _IDS)), [])

_, _, _stray = D.fidelity_check("standards (3.11) are absent", [], {2.0}, _IDS)
check("a referenced id is not a stray number", _stray, [])
_, _, _stray2 = D.fidelity_check("a mean of 7.77 appears", [], {2.0}, _IDS)
check("an undeclared quantity still is", _stray2, ["7.77"])

print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT} checks FAILED\n")
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print(f"all {COUNT} checks pass")
