#!/usr/bin/env python3
"""Focused tests for the fail-closed offline workflow simulation seam."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

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

    def test_nigeria_stage6_scenario_reproduces_exact_failure_without_spend(self):
        output = self.root / "stage6"
        report = S.simulate_workflow("nigeria-stage6-overlength-v1", output)

        self.assertEqual(report["schema_version"], "damm.simulation-report/v1")
        self.assertEqual(report["label"], "SIMULATED — NOT ACCEPTANCE EVIDENCE")
        self.assertEqual(report["execution_kind"], "simulation")
        self.assertIs(report["acceptance_eligible"], False)
        self.assertTrue(report["run_id"].startswith("sim-"))
        self.assertEqual(report["harness_verdict"], "pass")
        self.assertEqual(report["observed"]["workflow_status"], "failed")
        self.assertEqual(report["observed"]["failed_stage"], "investment_options")
        self.assertEqual(report["observed"]["error_code"], "appraisal_output_invalid")
        self.assertRegex(report["observed"]["error_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(report["external_spend_usd"], 0.0)
        self.assertEqual(report["external_io"], {
            "network_calls": 0,
            "database_writes": 0,
            "capabilities_minted": 0,
            "subprocess_calls": 0,
        })
        self.assertIs(type(report["external_spend_usd"]), int)
        self.assertEqual(report["fixture_call_count"], 3)
        self.assertEqual(
            set(report["code_identity"]["files"]),
            set(S.PRODUCTION_CODE_FILES),
        )
        self.assertTrue(all(assertion["ok"] for assertion in report["assertions"]))
        lengths = json.loads(
            (output / "artifacts/stage6-reproduction.json").read_text(encoding="utf-8")
        )["observed_repair_lengths"]
        self.assertEqual(lengths, [501, 504, 536, 516, 543, 505, 490])
        self.assertEqual(self.report_hash(report)[0], self.report_hash(report)[1])
        self.assertEqual(
            json.loads((output / S.REPORT_NAME).read_text(encoding="utf-8")),
            report,
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
                with zipfile.ZipFile(output / "workflow" / workbook["path"]) as archive:
                    workbook_strings = "".join(
                        archive.read(name).decode("utf-8", errors="ignore")
                        for name in archive.namelist()
                        if name.endswith(".xml")
                    )
                self.assertIn("SIMULATED", workbook_strings)

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
