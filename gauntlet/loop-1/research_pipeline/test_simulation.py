#!/usr/bin/env python3
"""Focused tests for the fail-closed offline workflow simulation seam."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile
import xml.etree.ElementTree as ET

import investment_options as I
import run_workflow as W
import simulate_workflow as CLI
import simulation as S


class SimulationHarnessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    @staticmethod
    def report_hash(report):
        value = json.loads(json.dumps(report))
        digest = value.pop("report_sha256")
        return digest, hashlib.sha256(S._stable_bytes(value)).hexdigest()

    @staticmethod
    def archive_member(archive, suffix):
        matches = [name for name in archive.namelist() if name.endswith(suffix)]
        if len(matches) != 1:
            raise AssertionError(
                f"expected one archive member ending {suffix!r}, found {matches!r}"
            )
        return matches[0]

    def test_simulated_converters_are_deterministic_valid_and_source_traceable(self):
        source = self.root / "source.html"
        source.write_text(
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>NGA Stage 6 source title 7a13</title>"
            "<style>body{font-family:serif}</style></head>"
            "<body><h1>NGA Stage 6 source title 7a13</h1>"
            "<p>Offline source narrative.</p></body></html>\n",
            encoding="utf-8",
        )
        expected_marker = (
            "SIMULATION-SOURCE-"
            + hashlib.sha256(source.read_bytes()).hexdigest()[:16].upper()
        )
        markdown = self.root / "first.md"
        first_docx = self.root / "first.docx"
        second_docx = self.root / "second.docx"
        first_pdf = self.root / "first.pdf"
        second_pdf = self.root / "second.pdf"

        S._simulation_pandoc(source, markdown)
        S._simulation_pandoc(source, first_docx)
        S._simulation_pandoc(source, second_docx)
        S._simulation_pdf(first_docx, first_pdf)
        S._simulation_pdf(first_docx, second_pdf)

        markdown_text = markdown.read_text(encoding="utf-8")
        self.assertIn("NGA Stage 6 source title 7a13", markdown_text)
        self.assertIn(expected_marker, markdown_text)
        self.assertEqual(first_docx.read_bytes(), second_docx.read_bytes())
        with zipfile.ZipFile(first_docx) as archive:
            names = set(archive.namelist())
            self.assertTrue({
                "[Content_Types].xml",
                "_rels/.rels",
                "docProps/core.xml",
                "word/document.xml",
                "word/_rels/document.xml.rels",
            }.issubset(names))
            for name in names:
                if name.endswith((".xml", ".rels")):
                    ET.fromstring(archive.read(name))
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("NGA Stage 6 source title 7a13", document_xml)
        self.assertIn(expected_marker, document_xml)

        self.assertEqual(first_pdf.read_bytes(), second_pdf.read_bytes())
        pdf = first_pdf.read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"NGA Stage 6 source title 7a13", pdf)
        self.assertIn(expected_marker.encode("ascii"), pdf)
        startxref = int(pdf.rsplit(b"startxref\n", 1)[1].splitlines()[0])
        self.assertEqual(pdf[startxref:startxref + 5], b"xref\n")

    def test_nigeria_stage6_scenario_recovers_exact_overlength_vector_without_spend(self):
        output = self.root / "stage6"
        report = S.simulate_workflow("nigeria-stage6-overlength-v1", output)

        self.assertEqual(report["schema_version"], "damm.simulation-report/v1")
        self.assertEqual(report["label"], "SIMULATED — NOT ACCEPTANCE EVIDENCE")
        self.assertEqual(report["execution_kind"], "simulation")
        self.assertIs(report["acceptance_eligible"], False)
        self.assertTrue(report["run_id"].startswith("sim-"))
        self.assertEqual(report["harness_verdict"], "pass")
        self.assertEqual(report["observed"]["workflow_status"], "complete")
        self.assertIsNone(report["observed"]["failed_stage"])
        self.assertIsNone(report["observed"]["error_code"])
        self.assertIsNone(report["observed"]["error_sha256"])
        self.assertEqual(report["external_spend_usd"], 0.0)
        self.assertEqual(report["external_io"], {
            "network_calls": 0,
            "database_writes": 0,
            "capabilities_minted": 0,
            "subprocess_calls": 0,
        })
        self.assertIs(type(report["external_spend_usd"]), int)
        self.assertEqual(report["fixture_call_count"], 18)
        self.assertEqual(
            set(report["code_identity"]["files"]),
            set(S.PRODUCTION_CODE_FILES),
        )
        self.assertTrue(all(assertion["ok"] for assertion in report["assertions"]))
        recovery = json.loads(
            (output / "artifacts/stage6-recovery.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            recovery["observed_repair_lengths"],
            [501, 504, 536, 516, 543, 505, 490],
        )
        self.assertEqual(
            recovery["observed_recovery_lengths"],
            [450, 450, 450, 450, 450, 450],
        )
        self.assertEqual(recovery["observed_recovery_max_tokens"], 1156)
        self.assertEqual(
            recovery["observed_effective_lengths"],
            [450, 450, 450, 450, 450, 450, 490],
        )
        self.assertEqual(recovery["fixture_calls"], [
            "investment candidate map batch 1/3",
            "investment candidate map batch 2/3",
            "investment candidate map batch 2/3 [local-length repair 1/1 chunk 1/4]",
            "investment candidate map batch 2/3 [local-length repair 1/1 chunk 2/4]",
            "investment candidate map batch 2/3 [local-length repair 1/1 chunk 3/4]",
            "investment candidate map batch 2/3 [local-length repair 1/1 chunk 4/4]",
            "investment candidate map batch 2/3 [local-length repair 2/2 chunk 1/3]",
            "investment candidate map batch 2/3 [local-length repair 2/2 chunk 2/3]",
            "investment candidate map batch 2/3 [local-length repair 2/2 chunk 3/3]",
            "investment candidate map batch 3/3",
            "investment candidate final register",
            "investment appraisal INV-1 batch 1/1",
            "investment appraisal INV-2 batch 1/1",
            "investment appraisal INV-3 batch 1/1",
            "investment appraisal INV-4 batch 1/1",
            "investment appraisal INV-5 batch 1/1",
            "investment appraisal INV-6 batch 1/1",
            "investment portfolio sequencing",
        ])
        product = json.loads(
            (output / "artifacts/investment-options.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(product["options"]), 6)
        self.assertEqual(I.validate_product(product), [])
        stage6 = next(
            stage
            for stage in report["stages"]
            if stage["stage_id"] == "investment_options"
        )
        self.assertEqual(stage6["status"], "complete")
        self.assertEqual(self.report_hash(report)[0], self.report_hash(report)[1])
        self.assertEqual(
            json.loads((output / S.REPORT_NAME).read_text(encoding="utf-8")),
            report,
        )

    def test_nigeria_recovery_flows_through_draft_and_export_package(self):
        output = self.root / "nigeria-package"

        report = S.simulate_workflow(
            "nigeria-stage6-through-package-v1", output
        )

        self.assertEqual(report["harness_verdict"], "pass")
        self.assertEqual(report["observed"]["workflow_status"], "complete")
        self.assertEqual(report["fixture_call_count"], 18)
        self.assertEqual(report["external_spend_usd"], 0)
        self.assertEqual(report["external_io"], {
            "network_calls": 0,
            "database_writes": 0,
            "capabilities_minted": 0,
            "subprocess_calls": 0,
        })
        self.assertEqual(len(report["stages"]), 8)
        self.assertTrue(all(
            stage["status"] == "complete" for stage in report["stages"]
        ))
        self.assertEqual(report["scenario_scope"], {
            "claim": "Stage 6 recovery through Stage 8 packaging only",
            "focus_stage_ids": [
                "investment_options", "draft_dar", "export_package",
            ],
            "synthetic_predecessor_stage_ids": [
                "damm_diagnostic",
                "country_research",
                "ai_digital_agriculture",
                "international_lessons",
                "strategic_foresight",
            ],
            "production_modules_exercised": [
                "gauntlet/loop-1/research_pipeline/investment_options.py",
                "gauntlet/loop-1/research_pipeline/report_design.py",
                "gauntlet/loop-1/research_pipeline/generate_dar.py",
                "gauntlet/loop-1/research_pipeline/export_package.py",
                "gauntlet/loop-1/research_pipeline/run_workflow.py",
            ],
            "bound_transitive_modules": [
                "gauntlet/loop-1/research_pipeline/vendors.py",
                "gauntlet/loop-1/research_pipeline/workflow_inputs.py",
                "gauntlet/loop-1/research_pipeline/foresight_contract.py",
                "gauntlet/loop-1/engine_v17.py",
                "model/reference_scorer.py",
            ],
            "simulation_harness_module": (
                "gauntlet/loop-1/research_pipeline/simulation.py"
            ),
        })
        bound_modules = set(report["scenario_scope"]["production_modules_exercised"])
        bound_modules.update(report["scenario_scope"]["bound_transitive_modules"])
        bound_modules.add(report["scenario_scope"]["simulation_harness_module"])
        self.assertTrue(bound_modules.issubset(report["code_identity"]["files"]))

        workflow_manifest = json.loads(
            (output / "workflow/workflow-manifest.json").read_text(encoding="utf-8")
        )
        expected_narrative_suffixes = {
            "damm_diagnostic": {".html"},
            "country_research": {".md", ".html"},
            "ai_digital_agriculture": {".md", ".html"},
            "international_lessons": {".md", ".html"},
            "strategic_foresight": {".html"},
        }
        narrative_keys = {
            "damm_diagnostic": "diagnostic_report",
            "country_research": "country_research_report",
            "ai_digital_agriculture": "ai_assessment_report",
            "international_lessons": "international_lessons_report",
            "strategic_foresight": "foresight_report",
        }
        for stage_id, expected_suffixes in expected_narrative_suffixes.items():
            stage = next(
                item for item in workflow_manifest["stages"] if item["id"] == stage_id
            )
            records = [
                item for item in stage["artifacts"]
                if item["key"] == narrative_keys[stage_id]
            ]
            self.assertEqual(
                {Path(item["path"]).suffix for item in records},
                expected_suffixes,
            )
            for record in records:
                if Path(record["path"]).suffix == ".html":
                    html_text = (output / "workflow" / record["path"]).read_text(
                        encoding="utf-8"
                    )
                    self.assertIn("<!doctype html>", html_text.casefold())
                    self.assertIn("<html", html_text.casefold())
                    self.assertNotRegex(
                        html_text,
                        r"(?i)<(?:link|script|img|iframe)[^>]+(?:href|src)="
                        r"[\"']https?://",
                    )

        draft_record = next(
            artifact for artifact in report["artifacts"]
            if artifact["stage_id"] == "draft_dar"
            and artifact["key"] == "dar_source_data"
        )
        draft = json.loads(
            (output / draft_record["path"]).read_text(encoding="utf-8")
        )
        annex = draft["annexes"]["investment_options_and_cost_benefit"]
        self.assertEqual(len(annex["options"]), 6)
        self.assertEqual(
            annex["decision_status"], "no_financing_decision_made"
        )
        repaired_option = next(
            option for option in annex["options"]
            if option["title"] == "Synthetic investment option 2"
        )
        self.assertEqual(len(repaired_option["problem"]), 450)
        stage6_html_record = next(
            artifact for artifact in report["artifacts"]
            if artifact["stage_id"] == "investment_options"
            and artifact["key"] == "investment_options_report"
            and artifact["path"].endswith(".html")
        )
        stage6_html = (output / stage6_html_record["path"]).read_text(encoding="utf-8")
        self.assertIn("Preliminary investment cost ranges", stage6_html)
        self.assertIn("Currencies use separate scales", stage6_html)
        draft_html_record = next(
            artifact for artifact in report["artifacts"]
            if artifact["stage_id"] == "draft_dar"
            and artifact["key"] == "draft_dar_report"
        )
        draft_html = (output / draft_html_record["path"]).read_text(encoding="utf-8")
        self.assertIn('aria-label="Figure traceability"', draft_html)
        self.assertIn("Investment decision support", draft_html)

        bundle_record = next(
            artifact for artifact in report["artifacts"]
            if artifact["stage_id"] == "export_package"
            and artifact["key"] == "complete_bundle"
        )
        stage6_source = (output / stage6_html_record["path"]).read_text(
            encoding="utf-8"
        )
        stage6_marker_match = re.search(
            r"SIMULATION-SOURCE-[0-9A-F]{16}", stage6_source
        )
        self.assertIsNotNone(stage6_marker_match)
        stage6_marker = stage6_marker_match.group(0)
        with zipfile.ZipFile(output / bundle_record["path"]) as archive:
            members = set(archive.namelist())
            stage6_markdown = archive.read(self.archive_member(
                archive,
                "narratives/06_investment_options/investment_options_report.md",
            )).decode("utf-8")
            stage6_document = archive.read(self.archive_member(
                archive,
                "narratives/06_investment_options/investment_options_report.docx",
            ))
            stage6_pdf = archive.read(self.archive_member(
                archive,
                "narratives/06_investment_options/investment_options_report.pdf",
            ))
        with zipfile.ZipFile(io.BytesIO(stage6_document)) as archive:
            stage6_document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("Stage 6", stage6_markdown)
        self.assertIn(stage6_marker, stage6_markdown)
        self.assertIn(stage6_marker, stage6_document_xml)
        self.assertIn(stage6_marker.encode("ascii"), stage6_pdf)
        self.assertTrue(stage6_pdf.rstrip().endswith(b"%%EOF"))
        self.assertTrue(any(
            name.endswith("/package-manifest.json") for name in members
        ))
        self.assertTrue(any(
            name.endswith(
                "narratives/06_investment_options/"
                "investment_options_report.pdf"
            )
            for name in members
        ))
        self.assertTrue(any(
            name.endswith("narratives/07_draft_dar/draft_dar_report.pdf")
            for name in members
        ))
        self.assertTrue(any(
            name.endswith(
                "structured/06_investment_options/cost_benefit.xlsx"
            )
            for name in members
        ))

    def test_identical_nigeria_package_simulations_are_byte_reproducible(self):
        first_output = self.root / "first-nigeria-package"
        second_output = self.root / "second-nigeria-package"

        first = S.simulate_workflow(
            "nigeria-stage6-through-package-v1", first_output
        )
        second = S.simulate_workflow(
            "nigeria-stage6-through-package-v1", second_output
        )

        self.assertEqual(first, second)
        first_bundle = next(
            artifact for artifact in first["artifacts"]
            if artifact["stage_id"] == "export_package"
            and artifact["key"] == "complete_bundle"
        )
        second_bundle = next(
            artifact for artifact in second["artifacts"]
            if artifact["stage_id"] == "export_package"
            and artifact["key"] == "complete_bundle"
        )
        self.assertEqual(
            (first_output / first_bundle["path"]).read_bytes(),
            (second_output / second_bundle["path"]).read_bytes(),
        )

    def test_happy_scenario_runs_real_coordinator_and_stage6_for_each_profile(self):
        expected_source_counts = {"minimal": 1, "typical": 3, "dense": 9}
        for profile, source_count in expected_source_counts.items():
            with self.subTest(profile=profile):
                output = self.root / profile
                report = S.simulate_workflow(
                    "eight-stage-happy-v1", output, profile=profile
                )

                self.assertEqual(report["harness_verdict"], "pass")
                self.assertEqual(report["observed"]["workflow_status"], "complete")
                self.assertEqual(report["fixture_call_count"], 6)
                self.assertEqual(len(report["stages"]), 8)
                self.assertTrue(all(stage["status"] == "complete" for stage in report["stages"]))
                self.assertTrue(all(stage["spent_usd"] == 0.0 for stage in report["stages"]))
                self.assertTrue(all(type(stage["spent_usd"]) is int for stage in report["stages"]))
                manifest = json.loads(
                    (output / "workflow/workflow-manifest.json").read_text(encoding="utf-8")
                )
                provenance = manifest["simulation_provenance"]
                self.assertEqual(provenance["schema_version"], "damm.simulation-provenance/v1")
                self.assertIs(provenance["acceptance_eligible"], False)
                snapshot = json.loads(
                    (output / "workflow" / manifest["input_snapshot"]["path"]).read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(snapshot["simulation_provenance"], provenance)
                stage6 = next(stage for stage in manifest["stages"] if stage["id"] == "investment_options")
                appraisal = next(
                    artifact for artifact in stage6["artifacts"]
                    if artifact["key"] == "appraisal_data"
                )
                product = json.loads(
                    (output / "workflow" / appraisal["path"]).read_text(encoding="utf-8")
                )
                self.assertEqual(product["simulation_notice"], S.SIMULATION_LABEL)
                self.assertEqual(len(product["source_inventory"]), source_count)
                self.assertEqual(len(product["options"]), 3)
                workbook = next(
                    artifact for artifact in stage6["artifacts"]
                    if artifact["key"] == "cost_benefit_workbook"
                )
                workbook_path = output / "workflow" / workbook["path"]
                with zipfile.ZipFile(workbook_path) as archive:
                    workbook_strings = "".join(
                        archive.read(name).decode("utf-8", errors="ignore")
                        for name in archive.namelist()
                        if name.endswith(".xml")
                    )
                self.assertIn("SIMULATED", workbook_strings)
                from openpyxl import load_workbook

                opened = load_workbook(workbook_path, read_only=False, data_only=False)
                self.addCleanup(opened.close)
                notice = opened["SIMULATED"]
                self.assertIs(notice.sheet_view.showGridLines, False)
                self.assertEqual(notice.page_setup.orientation, "landscape")
                self.assertEqual(notice.page_setup.fitToWidth, 1)
                self.assertEqual(notice.page_setup.fitToHeight, 1)
                self.assertGreaterEqual(notice["A1"].font.sz, 18)
                self.assertTrue(notice["A1"].font.bold)
                self.assertEqual(notice["A1"].fill.fgColor.rgb[-6:], "17322A")

    def test_simulation_scrubs_credentials_and_restores_the_process_environment(self):
        output = self.root / "scrubbed"
        sentinel = "must-not-reach-a-fixture"
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": sentinel}):
            original = S._HappyFixtureLLM.json_call

            def inspect(fixture, *args, **kwargs):
                self.assertNotIn("ANTHROPIC_API_KEY", os.environ)
                return original(fixture, *args, **kwargs)

            with mock.patch.object(S._HappyFixtureLLM, "json_call", inspect):
                report = S.simulate_workflow("eight-stage-happy-v1", output)
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], sentinel)
        self.assertEqual(report["external_io"]["network_calls"], 0)

    def test_provenance_validator_rejects_acceptance_eligible_simulation(self):
        value = {
            "schema_version": W.SIMULATION_PROVENANCE_SCHEMA,
            "label": W.SIMULATION_LABEL,
            "execution_kind": "simulation",
            "acceptance_eligible": True,
            "scenario_id": "eight-stage-happy-v1",
            "scenario_sha256": "a" * 64,
            "code_sha256": "b" * 64,
            "profile": "typical",
        }
        with self.assertRaisesRegex(W.WorkflowConfigurationError, "must be false"):
            W.validate_simulation_provenance(value)

    def test_cli_supports_named_scenario_and_output(self):
        output = self.root / "cli"
        with mock.patch("builtins.print") as printer:
            code = CLI.main([
                "--scenario", "nigeria-stage6-overlength-v1",
                "--output", str(output),
            ])
        self.assertEqual(code, 0)
        self.assertTrue((output / S.REPORT_NAME).is_file())
        self.assertGreaterEqual(printer.call_count, 2)

    def test_boundary_denies_alternate_network_subprocess_and_database_paths(self):
        counters = {
            "network_attempts": 0,
            "subprocess_attempts": 0,
            "database_attempts": 0,
            "capabilities_minted": 0,
        }
        with S._simulation_boundary(counters):
            transport = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.addCleanup(transport.close)
            with self.assertRaises(S.SimulationBoundaryError):
                transport.connect_ex(("127.0.0.1", 9))
            with self.assertRaises(S.SimulationBoundaryError):
                transport.sendto(b"blocked", ("127.0.0.1", 9))
            with self.assertRaises(S.SimulationBoundaryError):
                transport.sendmsg([b"blocked"], [], 0, ("127.0.0.1", 9))
            with self.assertRaises(S.SimulationBoundaryError):
                subprocess.run(["true"], check=False)
            with self.assertRaises(S.SimulationBoundaryError):
                os.posix_spawn("/usr/bin/true", ["true"], dict(os.environ))
            with self.assertRaises(S.SimulationBoundaryError):
                sqlite3.connect(":memory:")
        self.assertEqual(counters["network_attempts"], 3)
        self.assertEqual(counters["subprocess_attempts"], 2)
        self.assertEqual(counters["database_attempts"], 1)

    def test_scenario_schema_rejects_unknown_fields_and_boolean_counts(self):
        source = json.loads(
            (S.SCENARIO_DIR / "eight-stage-happy-v1.json").read_text(encoding="utf-8")
        )
        scenario_dir = self.root / "scenarios"
        scenario_dir.mkdir()
        scenario_path = scenario_dir / "eight-stage-happy-v1.json"
        with mock.patch.object(S, "SCENARIO_DIR", scenario_dir):
            with_unknown = json.loads(json.dumps(source))
            with_unknown["unexpected"] = True
            scenario_path.write_text(json.dumps(with_unknown), encoding="utf-8")
            with self.assertRaisesRegex(S.SimulationError, "top-level"):
                S._load_scenario("eight-stage-happy-v1")

            boolean_count = json.loads(json.dumps(source))
            boolean_count["fixture"]["candidate_count"] = True
            scenario_path.write_text(json.dumps(boolean_count), encoding="utf-8")
            with self.assertRaisesRegex(S.SimulationError, "happy fixture"):
                S._load_scenario("eight-stage-happy-v1")

        recovery_source = json.loads(
            (S.SCENARIO_DIR / "nigeria-stage6-overlength-v1.json").read_text(
                encoding="utf-8"
            )
        )
        recovery_path = scenario_dir / "nigeria-stage6-overlength-v1.json"
        with mock.patch.object(S, "SCENARIO_DIR", scenario_dir):
            unsafe_recovery = json.loads(json.dumps(recovery_source))
            unsafe_recovery["fixture"]["recovery_lengths"][0] = 451
            recovery_path.write_text(json.dumps(unsafe_recovery), encoding="utf-8")
            with self.assertRaisesRegex(S.SimulationError, "recovery fixture"):
                S._load_scenario("nigeria-stage6-overlength-v1")

            no_overlength_trigger = json.loads(json.dumps(recovery_source))
            no_overlength_trigger["fixture"]["repair_lengths"] = [500] * 7
            no_overlength_trigger["fixture"]["recovery_lengths"] = []
            recovery_path.write_text(
                json.dumps(no_overlength_trigger), encoding="utf-8"
            )
            with self.assertRaisesRegex(S.SimulationError, "recovery fixture"):
                S._load_scenario("nigeria-stage6-overlength-v1")

    def test_report_hash_uses_the_node_canonical_integer_zero_vector(self):
        vector = {
            "acceptance_eligible": False,
            "external_spend_usd": 0,
            "external_io": {
                "network_calls": 0,
                "database_writes": 0,
                "capabilities_minted": 0,
                "subprocess_calls": 0,
            },
            "stages": [{"spent_usd": 0}],
        }
        self.assertEqual(
            hashlib.sha256(S._stable_bytes(vector)).hexdigest(),
            "775c840df8085f60998ac141e484d9e1dfadaf0394a525ae064b0777d0124adb",
        )


if __name__ == "__main__":
    unittest.main()
