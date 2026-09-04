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
from engine_v17 import run as engine_run


class RecordingLlm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def json_call(self, system, user, schema, pass_name, max_tokens=8000, detail=""):
        self.calls.append({
            "system": system,
            "user": user,
            "schema": schema,
            "pass_name": pass_name,
            "max_tokens": max_tokens,
            "detail": detail,
        })
        return copy.deepcopy(self.responses.pop(0))


class GenerateDarWorkflowTest(unittest.TestCase):
    def clean_required_products(self):
        prefix = os.path.join(os.path.dirname(HERE), "EGY_202608260342_clean")
        with open(f"{prefix}_scans.json") as handle:
            scans = json.load(handle)
        with open(f"{prefix}_foresight.json") as handle:
            foresight = json.load(handle)
        return scans, foresight

    def chapter_context(self):
        prefix = os.path.join(os.path.dirname(HERE), "EGY_202608260342_clean")
        with open(f"{prefix}_g2_input.json") as handle:
            rows = json.load(handle)
        scans, foresight = self.clean_required_products()
        assessment = engine_run(
            "Egypt", rows, refyear=D.ASSESSMENT_YEAR, model_spec=D.SPEC,
            intervention_profiles={})
        return assessment, scans, foresight

    def test_schema_valid_chapter_gets_one_bounded_semantic_repair(self):
        assessment, scans, foresight = self.chapter_context()
        chapter = next(item for item in D.OUTLINE if str(item["n"]) == "2")
        invalid = {
            "prose": "The chapter makes an unrelated connectivity claim.",
            "cites": {
                "pillars": [], "indicators": ["2.4"],
                "use_cases": [], "prerequisites": [],
            },
            "claims": [],
            "figures": [],
        }
        repaired = {
            "prose": "The A1 pillar mean is 3.6.",
            "cites": {
                "pillars": ["A1"], "indicators": [],
                "use_cases": [], "prerequisites": [],
            },
            "claims": [{
                "text": "The A1 pillar mean is 3.6.",
                "basis": "evidence",
                "source_refs": ["pillar:A1:mean"],
            }],
            "figures": [{
                "value": "3.6",
                "what_it_is": "A1 pillar mean",
                "basis": "evidence",
                "operation": "none",
                "source_refs": ["pillar:A1:mean"],
                "inputs": [],
                "rationale": "Quoted from the A1 pillar record.",
            }],
        }
        llm = RecordingLlm([invalid, repaired])

        record = D.write_chapter(
            chapter, assessment, scans, foresight, "Egypt", llm)

        self.assertEqual(record["cited_outside_binding"], [])
        self.assertEqual(record["unsupported_figures"], [])
        self.assertEqual(record["stray_numbers"], [])
        self.assertEqual(
            [call["detail"] for call in llm.calls],
            ["chapter 2", "chapter 2 [semantic repair 1/1]"],
        )
        self.assertIn("failed local publication gates", llm.calls[1]["user"])

    def test_chapter_semantic_repair_exhaustion_is_bounded(self):
        assessment, scans, foresight = self.chapter_context()
        chapter = next(item for item in D.OUTLINE if str(item["n"]) == "2")
        invalid = {
            "prose": "The chapter makes an unrelated connectivity claim.",
            "cites": {
                "pillars": [], "indicators": ["2.4"],
                "use_cases": [], "prerequisites": [],
            },
            "claims": [],
            "figures": [],
        }
        llm = RecordingLlm([invalid, invalid])

        with self.assertRaises(D.ChapterSemanticRepairExhausted) as raised:
            D.write_chapter(
                chapter, assessment, scans, foresight, "Egypt", llm)

        self.assertEqual(raised.exception.chapter_id, "2")
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(
            llm.calls[1]["detail"], "chapter 2 [semantic repair 1/1]")

    def test_blank_schema_valid_chapter_is_repaired_before_checkpointing(self):
        assessment, scans, foresight = self.chapter_context()
        chapter = next(item for item in D.OUTLINE if str(item["n"]) == "2")
        blank = {
            "prose": "",
            "cites": {
                "pillars": [], "indicators": [],
                "use_cases": [], "prerequisites": [],
            },
            "claims": [],
            "figures": [],
        }
        repaired = {
            "prose": "The A1 pillar mean is 3.6.",
            "cites": {
                "pillars": ["A1"], "indicators": [],
                "use_cases": [], "prerequisites": [],
            },
            "claims": [{
                "text": "The A1 pillar mean is 3.6.",
                "basis": "evidence",
                "source_refs": ["pillar:A1:mean"],
            }],
            "figures": [{
                "value": "3.6", "what_it_is": "A1 pillar mean",
                "basis": "evidence", "operation": "none",
                "source_refs": ["pillar:A1:mean"], "inputs": [],
                "rationale": "Quoted from the A1 pillar record.",
            }],
        }
        llm = RecordingLlm([blank, repaired])

        record = D.write_chapter(
            chapter, assessment, scans, foresight, "Egypt", llm)

        self.assertEqual(record["prose"], repaired["prose"])
        self.assertEqual(len(llm.calls), 2)

    def test_blank_figure_fields_trigger_repair_before_later_chapter_spend(self):
        assessment, scans, foresight = self.chapter_context()
        chapter = next(item for item in D.OUTLINE if str(item["n"]) == "2")
        initial = {
            "prose": "The assessment contains a reviewed readiness record.",
            "cites": {
                "pillars": ["A1"], "indicators": [],
                "use_cases": [], "prerequisites": [],
            },
            "claims": [{
                "text": "The assessment contains a reviewed readiness record.",
                "basis": "evidence",
                "source_refs": ["pillar:A1:mean"],
            }],
            "figures": [{
                "value": "   ",
                "what_it_is": "\t",
                "basis": "evidence",
                "operation": "none",
                "source_refs": ["pillar:A1:mean"],
                "inputs": [],
                "rationale": "",
            }],
        }
        repaired = copy.deepcopy(initial)
        repaired["figures"] = []
        llm = RecordingLlm([initial, repaired])

        record = D.write_chapter(
            chapter, assessment, scans, foresight, "Egypt", llm)

        self.assertEqual(record["unsupported_figures"], [])
        self.assertEqual(
            [call["detail"] for call in llm.calls],
            ["chapter 2", "chapter 2 [semantic repair 1/1]"],
        )

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
