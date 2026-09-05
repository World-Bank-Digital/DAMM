#!/usr/bin/env python3
"""End-to-end contract rehearsal from one launch through the Draft ZIP package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

import export_package as E
import run_workflow as W
from test_export_package import FakeConverters


HERE = Path(__file__).resolve().parent
CONTRACT = HERE.parents[2] / "workflow" / "dar-workflow-v1.json"


class WorkflowExportIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="damm-workflow-integration-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workflow"
        self.contract = W.load_contract(CONTRACT)
        self.converters = FakeConverters()

    @staticmethod
    def _write_workbook(path: Path) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Options"
        sheet.append(["Option", "Cost low", "Cost high", "Benefit low", "Benefit high"])
        sheet.append(["I-1", 10, 20, 15, 35])
        workbook.save(path)
        workbook.close()

    def analytical_handler(self, context: W.StageContext) -> W.StageResult:
        narrative_key = E.NARRATIVE_ARTIFACTS.get(context.stage_id)
        artifacts = {}
        for artifact_id in context.required_artifacts:
            if artifact_id == "stage_manifest":
                continue
            if artifact_id == narrative_key:
                path = context.stage_dir / f"{artifact_id}.md"
                path.write_text(
                    f"# {context.stage['title']}\n\n"
                    "Draft evidence generated without an in-run human action.\n",
                    encoding="utf-8",
                )
            elif artifact_id == "cost_benefit_workbook":
                path = context.stage_dir / "cost_benefit_workbook.xlsx"
                self._write_workbook(path)
            else:
                path = context.stage_dir / f"{artifact_id}.json"
                value = (
                    [
                        {
                            "title": f"Source for {context.stage_id}",
                            "url": f"https://example.test/{context.stage_id}",
                            "tier": "T1",
                        }
                    ]
                    if artifact_id == "source_inventory"
                    else {
                        "schema_version": f"damm.{artifact_id}/v1",
                        "country": context.country,
                        "iso3": context.iso3,
                        "stage_id": context.stage_id,
                    }
                )
                path.write_text(
                    json.dumps(value, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
            artifacts[artifact_id] = path
        return W.StageResult(artifacts=artifacts, spent_usd=1.0)

    def export_handler(self, context: W.StageContext) -> W.StageResult:
        output_prefix = context.workspace / "deliverables" / "EGY_2026"
        result = E.build_export_package(
            country=context.country,
            iso3=context.iso3,
            out=output_prefix,
            workflow_manifest=context.manifest_path,
            contract_path=CONTRACT,
            pandoc_converter=self.converters.pandoc,
            pdf_converter=self.converters.pdf,
            created_at="2026-08-26T12:00:00Z",
        )
        return W.StageResult(
            artifacts={
                "narrative_exports": result.package_dir / "narratives",
                "structured_exports": result.package_dir / "structured",
                "source_inventory_exports": result.package_dir / "source-inventory",
                "workflow_manifest": result.package_manifest,
                "complete_bundle": result.zip_path,
            },
            spent_usd=0.0,
        )

    def test_retry_diagnostics_do_not_escape_into_downloadable_events(self):
        sentinel = "SYNTHETIC_PRIVATE_VALUE https://provider.test/?key=private /var/worker/private"
        def retry_once(context):
            if context.attempt == 1:
                raise W.RetryableStageError(sentinel)
            return self.analytical_handler(context)
        handlers = {stage_id: self.analytical_handler for stage_id in W.EXPECTED_STAGE_IDS[:7]}
        handlers[W.EXPECTED_STAGE_IDS[0]] = retry_once
        handlers["export_package"] = self.export_handler
        result = W.WorkflowCoordinator(
            contract=self.contract, workspace=self.workspace,
            handlers=handlers, retry_delay_seconds=0,
        ).run(country="Egypt", iso3="EGY", run_id="safe-retry")
        self.assertEqual(result["status"], "complete")
        events = (self.workspace / "workflow-events.jsonl").read_text()
        self.assertNotIn("SYNTHETIC_PRIVATE_VALUE", events)
        self.assertNotIn("provider.test", events)
        self.assertNotIn("/var/worker", events)
        self.assertIn('"event":"retry"', events)

    def test_one_launch_produces_hash_bound_all_format_draft_package(self):
        handlers = {
            stage_id: self.analytical_handler
            for stage_id in W.EXPECTED_STAGE_IDS[:7]
        }
        handlers["export_package"] = self.export_handler
        manifest = W.WorkflowCoordinator(
            contract=self.contract,
            workspace=self.workspace,
            handlers=handlers,
            retry_delay_seconds=0,
        ).run(country="Egypt", iso3="EGY", run_id="integration-run")

        self.assertEqual(manifest["status"], "complete")
        self.assertTrue(all(stage["status"] == "complete" for stage in manifest["stages"]))
        self.assertEqual(manifest["required_human_actions_during_run"], [])
        self.assertEqual(manifest["human_review"], {"available": True, "status": "pending"})
        self.assertEqual(manifest["spent_usd"], 7.0)

        export_stage = manifest["stages"][-1]
        records = {record["key"]: record for record in export_stage["artifacts"]}
        bundle = self.workspace / records["complete_bundle"]["path"]
        package_manifest = self.workspace / records["workflow_manifest"]["path"]
        self.assertTrue(bundle.is_file())
        package = json.loads(package_manifest.read_text(encoding="utf-8"))
        self.assertEqual(package["schema_version"], "damm.dar-package/v1")
        self.assertEqual(package["lifecycle_state"], "draft")
        self.assertEqual(package["export_profiles"], self.contract["export_profiles"])
        suffixes = {Path(record["path"]).suffix for record in package["files"]}
        self.assertTrue({".md", ".html", ".docx", ".pdf", ".xlsx", ".csv", ".json"} <= suffixes)

        stage1 = manifest["stages"][0]
        source_record = next(
            record for record in stage1["artifacts"] if record["key"] == "engine_input"
        )
        package_record = next(
            record
            for record in package["files"]
            if record.get("stage_id") == "damm_diagnostic"
            and record.get("artifact_id") == "engine_input"
        )
        source_bytes = (self.workspace / source_record["path"]).read_bytes()
        package_bytes = (package_manifest.parent / package_record["path"]).read_bytes()
        self.assertEqual(package_bytes, source_bytes)
        self.assertEqual(
            package_record["sha256"], hashlib.sha256(source_bytes).hexdigest()
        )
        self.assertEqual(package_record["source_sha256"], source_record["sha256"])

        events = [
            json.loads(line)
            for line in (self.workspace / "workflow-events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(events[-1]["event"], "workflow_complete")
        self.assertNotIn("human", " ".join(event["event"] for event in events))


if __name__ == "__main__":
    unittest.main()
