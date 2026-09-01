#!/usr/bin/env python3
"""Behavioral tests for the canonical one-launch DAR coordinator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import run_workflow as W
import vendors as V


HERE = Path(__file__).resolve().parent
CONTRACT = HERE.parents[2] / "workflow" / "dar-workflow-v1.json"


class WorkflowCoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workflow"
        self.contract = W.load_contract(CONTRACT)
        self.calls: list[str] = []

    def complete_handler(self, *, omit: str | None = None, spent: float = 1.25):
        def handler(context: W.StageContext):
            self.calls.append(context.stage_id)
            artifacts: dict[str, Path] = {}
            for artifact_id in context.required_artifacts:
                if artifact_id in {"stage_manifest", omit}:
                    continue
                path = context.stage_dir / f"{artifact_id}.json"
                path.write_text(
                    json.dumps({"stage": context.stage_id, "artifact": artifact_id}),
                    encoding="utf-8",
                )
                artifacts[artifact_id] = path
            return W.StageResult(artifacts=artifacts, spent_usd=spent)

        return handler

    def all_handlers(self):
        return {
            stage_id: self.complete_handler()
            for stage_id in W.EXPECTED_STAGE_IDS
        }

    def coordinator(self, handlers, **overrides):
        options = {
            "contract": self.contract,
            "workspace": self.workspace,
            "handlers": handlers,
            "commands": {},
            "max_attempts": 2,
            "retry_delay_seconds": 0,
            "sleep": lambda _seconds: None,
        }
        options.update(overrides)
        return W.WorkflowCoordinator(**options)

    def test_one_launch_completes_all_eight_stages_and_freezes_uploads(self):
        uploads = Path(self.temp.name) / "uploads.json"
        uploads_bytes = (
            b'{"schema_version":"damm.uploads-manifest/v1","documents":[]}\n'
        )
        uploads.write_bytes(uploads_bytes)

        handlers = self.all_handlers()
        draft_handler = handlers["draft_dar"]
        stage_seven_checkpoint = {}

        def inspect_stage_seven(context):
            stage_seven_checkpoint.update(
                json.loads(context.manifest_path.read_text(encoding="utf-8"))
            )
            return draft_handler(context)

        handlers["draft_dar"] = inspect_stage_seven
        manifest = self.coordinator(handlers).run(
            country="Egypt",
            iso3="EGY",
            uploads_manifest=uploads,
            run_id="workflow-test-run",
            ceiling_usd=500,
            vendor="test/replay",
        )

        self.assertEqual(self.calls, list(W.EXPECTED_STAGE_IDS))
        self.assertEqual(manifest["schema_version"], "damm.workflow-run/v1")
        self.assertEqual(
            manifest["contract_sha256"],
            hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
        )
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["current_stage"], None)
        self.assertEqual(
            set(manifest["input_snapshot"]), {"path", "sha256"}
        )
        self.assertTrue(manifest["human_review"]["available"])
        self.assertEqual(manifest["human_review"]["status"], "pending")
        self.assertEqual(
            manifest["uploads_manifest"]["sha256"],
            hashlib.sha256(uploads_bytes).hexdigest(),
        )
        frozen = self.workspace / manifest["uploads_manifest"]["path"]
        self.assertEqual(frozen.read_bytes(), uploads_bytes)
        self.assertEqual(
            [stage["id"] for stage in manifest["stages"]],
            list(W.EXPECTED_STAGE_IDS),
        )
        self.assertTrue(all(s["status"] == "complete" for s in manifest["stages"]))
        self.assertEqual(
            set(manifest["stages"][0]),
            {
                "ordinal",
                "id",
                "status",
                "attempts",
                "started_at",
                "completed_at",
                "execution_mode",
                "artifacts",
                "spent_usd",
            },
        )
        stage_artifact_keys = {
            stage["id"]: {artifact["key"] for artifact in stage["artifacts"]}
            for stage in manifest["stages"]
        }
        self.assertIn("engine_input", stage_artifact_keys["damm_diagnostic"])
        self.assertIn("ai_assessment", stage_artifact_keys["ai_digital_agriculture"])
        self.assertIn("scans", stage_artifact_keys["international_lessons"])
        self.assertIn("foresight", stage_artifact_keys["strategic_foresight"])
        self.assertIn("investment_options", stage_artifact_keys["investment_options"])
        required_stage_manifest_fields = set(
            self.contract["stage_manifest_required_fields"]
        )
        for stage in manifest["stages"]:
            binding = next(
                artifact
                for artifact in stage["artifacts"]
                if artifact["key"] == "stage_manifest"
            )
            value = json.loads(
                (self.workspace / binding["path"]).read_text(encoding="utf-8")
            )
            self.assertTrue(required_stage_manifest_fields <= set(value))
            self.assertIsInstance(value["spend_usd"], (int, float))
            self.assertIsInstance(value["input_hashes"], dict)
            self.assertIsInstance(value["output_hashes"], dict)
            self.assertTrue(all(check["ok"] for check in value["quality_checks"]))
            for artifact in stage["artifacts"]:
                if artifact["key"] == "stage_manifest":
                    continue
                bound = value["output_hashes"][artifact["key"]]
                hashes = bound if isinstance(bound, list) else [bound]
                expected = sorted(
                    candidate["sha256"]
                    for candidate in stage["artifacts"]
                    if candidate["key"] == artifact["key"]
                )
                self.assertEqual(sorted(hashes), expected)
        self.assertAlmostEqual(manifest["spent_usd"], 10.0)
        self.assertEqual(stage_seven_checkpoint["status"], "running")
        self.assertEqual(stage_seven_checkpoint["current_stage"], "draft_dar")
        self.assertTrue(
            all(
                stage["status"] == "complete"
                for stage in stage_seven_checkpoint["stages"][:6]
            )
        )
        self.assertEqual(stage_seven_checkpoint["stages"][6]["status"], "running")

        events = [
            json.loads(line)
            for line in (self.workspace / "workflow-events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(
            [event["event"] for event in events],
            ["start"]
            + [name for _ in W.EXPECTED_STAGE_IDS for name in ("stage_start", "stage_complete")]
            + ["workflow_complete"],
        )
        self.assertEqual([event["sequence"] for event in events], list(range(1, 19)))
        self.assertTrue(
            all(event["schema_version"] == "damm.workflow-event/v1" for event in events)
        )
        last_stage = next(
            event
            for event in events
            if event["event"] == "stage_complete"
            and event["stage_id"] == "export_package"
        )
        self.assertEqual(last_stage["spent_usd"], 1.25)
        self.assertEqual(last_stage["cumulative_spent_usd"], 10.0)
        self.assertIn("elapsed_seconds", last_stage)
        bundle = next(
            artifact
            for artifact in last_stage["artifacts"]
            if artifact["key"] == "complete_bundle"
        )
        self.assertEqual(
            set(bundle), {"key", "path", "sha256", "media_type"}
        )

    def test_original_and_extracted_upload_bytes_are_verified_again_on_resume(self):
        content = self.workspace / "inputs/upload-content/ttl-country.txt"
        original = self.workspace / "inputs/upload-originals/ttl-country.pdf"
        content.parent.mkdir(parents=True, exist_ok=True)
        original.parent.mkdir(parents=True, exist_ok=True)
        extracted_text = "Country upload evidence with café.\n"
        content.write_text(extracted_text, encoding="utf-8")
        original.write_bytes(b"%PDF-1.4\noriginal\n")
        uploads = Path(self.temp.name) / "uploads-with-original.json"
        document = {
            "id": "ttl-country",
            "kind": "country_context_documents",
            "original_filename": "country.pdf",
            "content_path": content.relative_to(self.workspace).as_posix(),
            "content_sha256": hashlib.sha256(content.read_bytes()).hexdigest(),
            "content_media_type": "text/plain",
            "original_path": original.relative_to(self.workspace).as_posix(),
            "original_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
            "original_size_bytes": original.stat().st_size,
            "metadata": {
                "extracted_characters": len(extracted_text),
                "app_upload_kind": "country_context_documents",
                "source_mime_type": "application/pdf",
                "uploaded_at": "2026-08-26T10:00:00Z",
                "uploaded_by": "fixture-ttl",
                "extraction_status": "extracted",
            },
        }
        uploads.write_text(
            json.dumps(
                {
                    "schema_version": "damm.uploads-manifest/v1",
                    "documents": [document],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        handlers = self.all_handlers()

        def interrupt(_context):
            raise KeyboardInterrupt()

        handlers["damm_diagnostic"] = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.coordinator(handlers).run(
                country="Egypt",
                iso3="EGY",
                uploads_manifest=uploads,
                run_id="upload-resume-run",
            )
        checkpoint = json.loads(
            (self.workspace / "workflow-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(checkpoint["uploads_manifest"]["document_count"], 1)

        original.write_bytes(original.read_bytes() + b"tamper")
        with self.assertRaisesRegex(W.WorkflowConfigurationError, "original hash mismatch"):
            self.coordinator(handlers).run(
                country="Egypt",
                iso3="EGY",
                uploads_manifest=uploads,
                run_id="upload-resume-run",
                resume=True,
            )

    def test_missing_required_artifact_fails_terminally_without_human_state(self):
        handlers = self.all_handlers()
        handlers["ai_digital_agriculture"] = self.complete_handler(
            omit="source_inventory"
        )

        with self.assertRaises(W.WorkflowRunFailed) as caught:
            self.coordinator(handlers).run(
                country="Egypt", iso3="EGY", run_id="missing-artifact"
            )

        manifest = caught.exception.manifest
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["current_stage"], "ai_digital_agriculture")
        self.assertFalse(manifest["human_review"]["available"])
        self.assertEqual(
            self.calls,
            list(W.EXPECTED_STAGE_IDS[:3]) + ["ai_digital_agriculture"],
        )
        failed_stage = next(
            stage
            for stage in manifest["stages"]
            if stage["id"] == "ai_digital_agriculture"
        )
        self.assertEqual(failed_stage["attempts"], 2)
        self.assertEqual(
            manifest["failure"]["type"], "MissingRequiredArtifacts"
        )
        self.assertIn("source_inventory", manifest["failure"]["message"])

        serialized = json.dumps(manifest).lower()
        self.assertNotIn("awaiting_human", serialized)
        self.assertNotIn('"paused"', serialized)
        events = [
            json.loads(line)
            for line in (self.workspace / "workflow-events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(events[-1]["event"], "failure")
        self.assertEqual(events[-1]["stage_id"], "ai_digital_agriculture")
        retries = [event for event in events if event["event"] == "retry"]
        self.assertEqual(len(retries), 1)
        self.assertEqual(retries[0]["stage_id"], "ai_digital_agriculture")
        self.assertNotIn("workflow_complete", [event["event"] for event in events])

    def test_retryable_handler_emits_retry_then_completes(self):
        handlers = self.all_handlers()
        attempts = {"country_research": 0}
        successful = self.complete_handler()

        def flaky(context):
            attempts["country_research"] += 1
            if attempts["country_research"] == 1:
                raise W.RetryableStageError("temporary vendor throttle")
            return successful(context)

        handlers["country_research"] = flaky
        manifest = self.coordinator(handlers).run(
            country="Egypt", iso3="EGY", run_id="retry-run"
        )

        self.assertEqual(manifest["status"], "complete")
        country_stage = next(
            stage for stage in manifest["stages"] if stage["id"] == "country_research"
        )
        self.assertEqual(country_stage["attempts"], 2)
        events = [
            json.loads(line)
            for line in (self.workspace / "workflow-events.jsonl").read_text().splitlines()
        ]
        retries = [event for event in events if event["event"] == "retry"]
        self.assertEqual(len(retries), 1)
        self.assertEqual(retries[0]["stage_id"], "country_research")
        self.assertEqual(retries[0]["attempt"], 1)
        self.assertEqual(retries[0]["next_attempt"], 2)

    def test_contract_and_execution_plan_are_enforced_before_launch(self):
        invalid = json.loads(json.dumps(self.contract))
        invalid["stages"] = invalid["stages"][:-1]
        with self.assertRaisesRegex(W.WorkflowContractError, "exactly eight"):
            W.validate_contract(invalid)

        invalid_budget = json.loads(json.dumps(self.contract))
        invalid_budget["execution_policy"]["fixed_stage_budget_allocations"][
            "country_research"
        ] = 0.15
        with self.assertRaisesRegex(
            W.WorkflowContractError, "fixed stage budget allocations are not canonical"
        ):
            W.validate_contract(invalid_budget)
        allocations = self.contract["execution_policy"][
            "fixed_stage_budget_allocations"
        ]
        self.assertEqual(allocations, W.EXPECTED_STAGE_BUDGET_ALLOCATIONS)
        self.assertEqual(sum(allocations.values()), 1.0)
        self.assertEqual(allocations["export_package"], 0.0)
        runtime_allocations = {
            "damm_diagnostic": (
                round(
                    V.Ledger.ALLOCATION["research"]
                    + V.Ledger.ALLOCATION["automated_challenge"],
                    6,
                )
            ),
            "country_research": V.Ledger.ALLOCATION["country_research"],
            "ai_digital_agriculture": V.Ledger.ALLOCATION["ai"],
            "international_lessons": V.Ledger.ALLOCATION[
                "international_lessons"
            ],
            "strategic_foresight": V.Ledger.ALLOCATION["foresight"],
            "investment_options": V.Ledger.ALLOCATION["investment"],
            "draft_dar": V.Ledger.ALLOCATION["generation"],
            "export_package": V.Ledger.ALLOCATION["export"],
        }
        self.assertEqual(runtime_allocations, allocations)

        defaults = W.build_existing_stage_commands(
            country="Egypt",
            iso3="EGY",
            legacy_out="EGY_test",
            ceiling_usd=500,
            vendor="test/replay",
            workflow_version=str(self.contract["workflow_version"]),
        )
        self.assertEqual(set(defaults), set(W.EXPECTED_STAGE_IDS))
        self.assertIn("--workflow-manifest", defaults["draft_dar"].argv)
        coordinator = W.WorkflowCoordinator(
            contract=self.contract,
            workspace=self.workspace,
            commands=defaults,
        )
        coordinator.validate_execution_plan()
        self.assertIn("ai_assessment.py", defaults["ai_digital_agriculture"].argv[1])
        self.assertIn("investment_options.py", defaults["investment_options"].argv[1])
        self.assertIn("export_package.py", defaults["export_package"].argv[1])
        self.assertEqual(
            tuple(path.suffix for path in defaults["ai_digital_agriculture"].artifacts[
                "ai_assessment_report"
            ]),
            (".md", ".html"),
        )
        self.assertEqual(
            tuple(path.suffix for path in defaults["investment_options"].artifacts[
                "investment_options_report"
            ]),
            (".md", ".html"),
        )
        self.assertIn("--resume", defaults["export_package"].argv)
        self.assertEqual(
            defaults["country_research"].spend_path.name,
            "EGY_test_country_research_spend.json",
        )
        self.assertEqual(
            defaults["international_lessons"].spend_path.name,
            "EGY_test_international_lessons_spend.json",
        )
        self.assertEqual(
            defaults["damm_diagnostic"].artifacts["engine_input"].name,
            "EGY_test_automated_challenge_input.json",
        )
        self.assertEqual(
            defaults["damm_diagnostic"].artifacts["automated_challenge"].name,
            "EGY_test_automated_challenge_findings.json",
        )
        self.assertTrue(all(
            spec.checkpoint_namespace == "EGY_test"
            for spec in defaults.values()
        ))

    def test_unbound_or_foreign_legacy_namespace_is_rejected_before_command(self):
        legacy = Path(self.temp.name) / "legacy"
        legacy.mkdir()
        (legacy / "shared_state.json").write_text("{}", encoding="utf-8")
        called = []
        command = W.CommandSpec(
            argv=("fake-command",),
            artifacts={},
            cwd=legacy,
            checkpoint_namespace="shared",
        )
        handlers = self.all_handlers()
        handlers.pop("damm_diagnostic")
        coordinator = self.coordinator(
            handlers,
            commands={"damm_diagnostic": command},
            command_runner=lambda *_args: called.append(True),
        )
        with self.assertRaisesRegex(
                W.WorkflowConfigurationError, "unbound legacy state"):
            coordinator.run(
                country="Egypt", iso3="EGY", run_id="namespace-run",
                ceiling_usd=500, vendor="test/replay",
            )
        self.assertEqual(called, [])

        (legacy / "shared_state.json").unlink()

        def interrupt_after_claim(*_args):
            called.append(True)
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            self.coordinator(
                handlers,
                commands={"damm_diagnostic": command},
                command_runner=interrupt_after_claim,
            ).run(
                country="Egypt", iso3="EGY", run_id="namespace-run",
                ceiling_usd=500, vendor="test/replay",
            )
        binding = json.loads(
            (self.workspace / "inputs/checkpoint-binding.json").read_text()
        )
        self.assertEqual(binding["run_id"], "namespace-run")
        self.assertEqual(binding["country"], "Egypt")

        calls_before_resume = len(called)
        with self.assertRaises(KeyboardInterrupt):
            self.coordinator(
                handlers,
                commands={"damm_diagnostic": command},
                command_runner=interrupt_after_claim,
            ).run(
                country="Egypt", iso3="EGY", run_id="namespace-run",
                ceiling_usd=500, vendor="test/replay", resume=True,
            )
        self.assertEqual(len(called), calls_before_resume + 1)

        other_workspace = Path(self.temp.name) / "other-workflow"
        with self.assertRaisesRegex(
                W.WorkflowConfigurationError, "claimed by another run or input"):
            W.WorkflowCoordinator(
                contract=self.contract,
                workspace=other_workspace,
                handlers=handlers,
                commands={"damm_diagnostic": command},
                command_runner=interrupt_after_claim,
                retry_delay_seconds=0,
            ).run(
                country="Kenya", iso3="KEN", run_id="foreign-run",
                ceiling_usd=500, vendor="test/replay",
            )

    def test_failed_command_attempt_spend_is_in_retry_and_terminal_totals(self):
        handlers = self.all_handlers()
        handlers.pop("country_research")
        spend_path = Path(self.temp.name) / "country-spend.json"
        command = W.CommandSpec(
            argv=("fake-command",),
            artifacts={},
            spend_path=spend_path,
        )
        attempt_totals = iter((2.0, 3.5))

        def fail_after_spending(_spec, _context):
            total = next(attempt_totals)
            spend_path.write_text(
                json.dumps({"summary": {"total": total}}), encoding="utf-8"
            )
            return SimpleNamespace(
                returncode=1, stdout="", stderr="transient vendor failure"
            )

        with self.assertRaises(W.WorkflowRunFailed) as caught:
            self.coordinator(
                handlers,
                commands={"country_research": command},
                command_runner=fail_after_spending,
            ).run(country="Egypt", iso3="EGY", run_id="failed-spend")

        manifest = caught.exception.manifest
        failed = next(
            stage for stage in manifest["stages"]
            if stage["id"] == "country_research"
        )
        self.assertEqual(failed["spent_usd"], 3.5)
        self.assertEqual(manifest["spent_usd"], 4.75)
        events = [
            json.loads(line)
            for line in (self.workspace / "workflow-events.jsonl").read_text().splitlines()
        ]
        retry = next(event for event in events if event["event"] == "retry")
        failure = events[-1]
        self.assertEqual(retry["cumulative_spent_usd"], 3.25)
        self.assertEqual(failure["cumulative_spent_usd"], 4.75)
        self.assertEqual(failure["failed_stage_spent_usd"], 3.5)

    def test_nonretryable_command_exit_stops_without_replaying_paid_work(self):
        handlers = self.all_handlers()
        handlers.pop("investment_options")
        spend_path = Path(self.temp.name) / "investment-spend.json"
        spend_path.write_text(
            json.dumps({"summary": {"total": 2.5}}), encoding="utf-8"
        )
        command = W.CommandSpec(
            argv=("fake-command",), artifacts={}, spend_path=spend_path
        )
        calls = []

        def terminal_failure(_spec, _context):
            calls.append(True)
            return SimpleNamespace(
                returncode=W.NONRETRYABLE_COMMAND_EXIT,
                stdout="",
                stderr="structured output exhausted its bounded retry",
            )

        with self.assertRaises(W.WorkflowRunFailed) as caught:
            self.coordinator(
                handlers,
                commands={"investment_options": command},
                command_runner=terminal_failure,
            ).run(country="Egypt", iso3="EGY", run_id="terminal-command")

        self.assertEqual(calls, [True])
        failed = next(
            stage for stage in caught.exception.manifest["stages"]
            if stage["id"] == "investment_options"
        )
        self.assertEqual(failed["attempts"], 1)
        self.assertEqual(
            caught.exception.manifest["failure"]["type"],
            "NonRetryableStageError",
        )
        events = [
            json.loads(line)
            for line in (self.workspace / "workflow-events.jsonl").read_text().splitlines()
        ]
        self.assertNotIn("retry", [event["event"] for event in events])

    def test_command_cannot_spend_another_stages_protected_allocation(self):
        handlers = self.all_handlers()
        handlers.pop("country_research")
        spend_path = Path(self.temp.name) / "over-budget-country-spend.json"
        command = W.CommandSpec(
            argv=("fake-command",), artifacts={}, spend_path=spend_path
        )

        def report_overspend(_spec, _context):
            spend_path.write_text(
                json.dumps({"summary": {"total": 8.0}}), encoding="utf-8"
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with self.assertRaises(W.WorkflowRunFailed) as caught:
            self.coordinator(
                handlers,
                commands={"country_research": command},
                command_runner=report_overspend,
            ).run(
                country="Egypt",
                iso3="EGY",
                run_id="protected-budget-run",
                ceiling_usd=100,
            )
        manifest = caught.exception.manifest
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["current_stage"], "country_research")
        self.assertEqual(manifest["stages"][1]["spent_usd"], 8.0)
        self.assertIn("exceeds its protected allocation $7.500000", manifest["failure"]["message"])

    def test_resume_skips_hash_verified_completed_stages(self):
        handlers = self.all_handlers()
        successful_ai = handlers["ai_digital_agriculture"]
        interrupted = {"done": False}

        def interrupt_once(context):
            self.calls.append(context.stage_id)
            if not interrupted["done"]:
                interrupted["done"] = True
                raise KeyboardInterrupt()
            return successful_ai(context)

        handlers["ai_digital_agriculture"] = interrupt_once
        coordinator = self.coordinator(handlers)
        with self.assertRaises(KeyboardInterrupt):
            coordinator.run(
                country="Egypt",
                iso3="EGY",
                run_id="resume-run",
                ceiling_usd=500,
                vendor="test/replay",
            )

        calls_before_resume = list(self.calls)
        resumed = self.coordinator(handlers).run(
            country="Egypt",
            iso3="EGY",
            run_id="resume-run",
            ceiling_usd=500,
            vendor="test/replay",
            resume=True,
        )

        self.assertEqual(resumed["status"], "complete")
        self.assertEqual(calls_before_resume[:2], list(W.EXPECTED_STAGE_IDS[:2]))
        self.assertEqual(self.calls.count("damm_diagnostic"), 1)
        self.assertEqual(self.calls.count("country_research"), 1)
        ai = next(
            stage
            for stage in resumed["stages"]
            if stage["id"] == "ai_digital_agriculture"
        )
        self.assertEqual(ai["attempts"], 2)
        events = [
            json.loads(line)
            for line in (self.workspace / "workflow-events.jsonl").read_text().splitlines()
        ]
        self.assertIn("resume", [event["event"] for event in events])
        self.assertNotIn("awaiting_human", json.dumps(events).lower())

    def test_resume_finalizes_when_all_stage_records_are_complete(self):
        handlers = self.all_handlers()
        first = self.coordinator(handlers).run(
            country="Egypt",
            iso3="EGY",
            run_id="finalization-crash",
            ceiling_usd=500,
            vendor="test/replay",
        )
        calls_before_resume = list(self.calls)

        # Recreate the crash boundary after Stage 8 checkpointing but before the
        # coordinator's root completion checkpoint/event.
        checkpoint = json.loads(
            (self.workspace / "workflow-manifest.json").read_text(encoding="utf-8")
        )
        checkpoint["status"] = "running"
        checkpoint["current_stage"] = "export_package"
        checkpoint["completed_at"] = None
        checkpoint["human_review"] = {
            "available": False,
            "status": "not_available",
        }
        (self.workspace / "workflow-manifest.json").write_text(
            json.dumps(checkpoint, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        events_path = self.workspace / "workflow-events.jsonl"
        events = events_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(events[-1])["event"], "workflow_complete")
        events_path.write_text("\n".join(events[:-1]) + "\n", encoding="utf-8")

        resumed = self.coordinator(handlers).run(
            country="Egypt",
            iso3="EGY",
            run_id="finalization-crash",
            ceiling_usd=500,
            vendor="test/replay",
            resume=True,
        )

        self.assertEqual(resumed["status"], "complete")
        self.assertIsNone(resumed["current_stage"])
        self.assertEqual(self.calls, calls_before_resume)
        self.assertEqual(resumed["stages"], first["stages"])
        final_events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            [event["event"] for event in final_events[-2:]],
            ["resume", "workflow_complete"],
        )


if __name__ == "__main__":
    unittest.main()
