#!/usr/bin/env python3

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import generate_dar as D


class GenerateDarWorkflowTest(unittest.TestCase):
    def clean_required_products(self):
        prefix = os.path.join(os.path.dirname(HERE), "EGY_202608260342_clean")
        with open(f"{prefix}_scans.json") as handle:
            scans = json.load(handle)
        with open(f"{prefix}_foresight.json") as handle:
            foresight = json.load(handle)
        return scans, foresight

    def manifest(self, input_records):
        bindings = {
            "damm_diagnostic": ("engine_input", "engine_input"),
            "country_research": ("country_research", None),
            "ai_digital_agriculture": ("ai_assessment", "ai_assessment"),
            "international_lessons": ("scans", "scans"),
            "strategic_foresight": ("foresight", "foresight"),
            "investment_options": ("investment_options", "investment_options"),
        }
        stages = []
        for ordinal, (stage_id, (artifact_key, input_name)) in enumerate(bindings.items(), 1):
            artifacts = []
            if input_name:
                artifacts.append({
                    "key": artifact_key,
                    "path": input_records[input_name]["file"],
                    "sha256": input_records[input_name]["sha256"],
                    "media_type": "application/json",
                })
            stages.append({
                "ordinal": ordinal,
                "id": stage_id,
                "status": "complete",
                "attempts": 1,
                "started_at": "2026-08-26T00:00:00Z",
                "completed_at": "2026-08-26T00:01:00Z",
                "execution_mode": "autonomous_research",
                "artifacts": artifacts,
            })
        with open(D.WORKFLOW_FILE) as handle:
            workflow_version = json.load(handle)["workflow_version"]
        with open(D.WORKFLOW_FILE, "rb") as handle:
            contract_sha256 = hashlib.sha256(handle.read()).hexdigest()
        return {
            "schema_version": "damm.workflow-run/v1",
            "workflow_id": "dar-canonical-v1",
            "workflow_version": workflow_version,
            "contract_sha256": contract_sha256,
            "country": "Exampleland",
            "iso3": "EXP",
            "status": "running",
            "input_snapshot": {"sha256": "a" * 64},
            "stages": stages,
        }

    def test_completed_machine_stages_authorize_draft_input(self):
        with tempfile.TemporaryDirectory() as directory:
            input_records = {}
            for name in ("engine_input", "scans", "ai_assessment", "foresight",
                         "investment_options"):
                path = os.path.join(directory, f"{name}.json")
                with open(path, "w") as handle:
                    handle.write("{}")
                input_records[name] = D.file_record(path)
            errors = D.workflow_generation_input_errors(
                self.manifest(input_records), "Exampleland", "EXP", input_records)
            self.assertEqual(errors, [])

    def test_stage_or_hash_mismatch_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            input_records = {}
            for name in ("engine_input", "scans", "ai_assessment", "foresight",
                         "investment_options"):
                path = os.path.join(directory, f"{name}.json")
                with open(path, "w") as handle:
                    handle.write("{}")
                input_records[name] = D.file_record(path)
            manifest = self.manifest(input_records)
            manifest["stages"][2]["status"] = "running"
            manifest["stages"][5]["artifacts"][0]["sha256"] = "0" * 64
            errors = D.workflow_generation_input_errors(
                manifest, "Exampleland", "EXP", input_records)
            self.assertTrue(any("ai_digital_agriculture is not complete" in e for e in errors))
            self.assertTrue(any("investment_options hash" in e for e in errors))

    def test_supplemental_products_keep_ai_and_financing_status_explicit(self):
        ai = {
            "schema_version": "damm.ai-digital-agriculture/v1",
            "country": "Exampleland", "iso3": "EXP",
            "as_is": {"findings": [{"id": "A"}]},
            "peer_experience": {"findings": [{"id": "P"}]},
            "recommended_agenda": {"status": "proposed_for_post_completion_validation"},
            "source_inventory": [],
        }
        investment = {
            "schema_version": "damm.investment-options/v1",
            "country": "Exampleland", "iso3": "EXP",
            "options": [{"option_id": "INV-1"}],
            "source_inventory": [],
            "decision_status": "no_financing_decision_made",
        }
        self.assertEqual(
            D.supplemental_product_errors(ai, investment, "Exampleland", "EXP"), [])
        investment["decision_status"] = "approved"
        self.assertTrue(any("financing decision" in error for error in
                            D.supplemental_product_errors(
                                ai, investment, "Exampleland", "EXP")))

    def test_candidate_register_allows_consistent_reuse_by_multiple_milestones(self):
        scans, foresight = self.clean_required_products()
        reused = copy.deepcopy(foresight["milestones"][2])
        reused["statement"] = "A later milestone reuses the same candidate metric."
        reused["target_year"] += 2
        foresight["milestones"].append(reused)

        self.assertEqual(D.required_product_errors(scans, foresight, "Egypt"), [])

    def test_candidate_register_rejects_conflicting_same_id_definitions(self):
        scans, foresight = self.clean_required_products()
        conflicting = copy.deepcopy(foresight["milestones"][2])
        conflicting["statement"] = "A later milestone changes the metric definition."
        conflicting["target_year"] += 2
        conflicting["candidate_indicator"]["name"] = "A conflicting metric definition"
        foresight["milestones"].append(conflicting)

        errors = D.required_product_errors(scans, foresight, "Egypt")
        self.assertTrue(any(
            "conflicts with its earlier definition" in error for error in errors), errors)

    def test_candidate_register_rejects_duplicate_missing_and_extra_rows(self):
        scans, clean_foresight = self.clean_required_products()
        variants = {}

        duplicate = copy.deepcopy(clean_foresight)
        duplicate["candidate_indicators"].append(copy.deepcopy(
            duplicate["candidate_indicators"][0]))
        variants["duplicate"] = duplicate

        missing = copy.deepcopy(clean_foresight)
        missing["candidate_indicators"].pop()
        variants["missing"] = missing

        extra = copy.deepcopy(clean_foresight)
        extra["candidate_indicators"].append({
            "id": "C2-CAND-UNBOUND",
            "name": "An unbound register entry",
            "proposed_pillar": "C2",
            "rationale": "Regression fixture",
            "proposed_by": "Regression test",
        })
        variants["extra"] = extra

        for label, foresight in variants.items():
            with self.subTest(label=label):
                errors = D.required_product_errors(scans, foresight, "Egypt")
                self.assertIn(
                    "foresight candidate register does not match milestone bindings",
                    errors,
                )

    def test_candidate_register_rejects_definition_drift_with_the_same_id(self):
        scans, foresight = self.clean_required_products()
        foresight["candidate_indicators"][0]["name"] = "A changed register definition"

        errors = D.required_product_errors(scans, foresight, "Egypt")
        self.assertIn(
            "foresight candidate register does not match milestone bindings",
            errors,
        )

    def test_malformed_candidate_id_is_reported_without_crashing_validation(self):
        scans, foresight = self.clean_required_products()
        foresight["milestones"][2]["candidate_indicator"]["id"] = ["not-a-string"]

        errors = D.required_product_errors(scans, foresight, "Egypt")
        self.assertTrue(any("candidate_indicator id does not match" in error
                            for error in errors), errors)

        scans, foresight = self.clean_required_products()
        foresight["candidate_indicators"][0]["id"] = ["not-a-string"]
        errors = D.required_product_errors(scans, foresight, "Egypt")
        self.assertTrue(any("outside the candidate namespace" in error
                            for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
