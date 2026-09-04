#!/usr/bin/env python3
"""Zero-spend regression coverage for bounded Stage 5 semantic repair."""

import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import foresight as F
import semantic_repair as SR


def scenario(name):
    return {
        "name": name,
        "narrative": f"{name} develops from a bounded uncertainty.",
        "drivers": [f"{name} driver"],
        "what_would_make_it_happen": f"Conditions for {name}.",
        "implication_for_the_sector": f"Implication of {name}.",
    }


def milestone(**overrides):
    value = {
        "statement": "Raise the service maturity level.",
        "indicator_id": "2.1",
        "target_level": 4,
        "target_year": F.ASSESSMENT_YEAR + 5,
        "why_this_step": "It advances a measured capability.",
        "candidate_indicator": None,
    }
    value.update(overrides)
    return value


class SequenceLLM:
    def __init__(self, *responses):
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
        if not self.responses:
            raise AssertionError("unexpected model transport")
        return copy.deepcopy(self.responses.pop(0))

    def enable_durable_outcomes(self):
        return self


class ForesightSemanticRepairTest(unittest.TestCase):
    def state(self, **overrides):
        value = {
            "scenarios": None,
            "preferred_future": None,
            "milestones": None,
            "refused": [],
            "context_sources": [],
            "semantic_repairs": {},
        }
        value.update(overrides)
        return value

    def test_legacy_truthy_scenario_checkpoint_is_revalidated_and_repaired_once(self):
        duplicate = [scenario("Same"), scenario(" same "), scenario("Other")]
        repaired = [scenario("Baseline"), scenario("Fragmented"), scenario("Accelerated")]
        state = self.state(scenarios=duplicate)
        llm = SequenceLLM({"scenarios": repaired})
        saves = []

        value = F.resolve_semantic_step(
            llm,
            state,
            lambda: saves.append(copy.deepcopy(state)),
            step_id="scenarios",
            state_key="scenarios",
            response_key="scenarios",
            system=F.SYSTEM,
            user="original scenario prompt",
            schema=F.SCENARIO_SCHEMA,
            max_tokens=6000,
            detail="scenarios",
            prepare=F.prepare_scenarios,
        )

        self.assertEqual(value, repaired)
        self.assertEqual(state["scenarios"], repaired)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(llm.calls[0]["detail"], "scenarios [semantic repair 1/1]")
        self.assertEqual(state["semantic_repairs"]["scenarios"]["status"], "complete")
        self.assertGreaterEqual(len(saves), 2)

    def test_distinct_names_with_duplicate_scenario_substance_are_repaired(self):
        duplicate = []
        for name in ("Baseline", "Fragmented", "Accelerated"):
            value = scenario(name)
            value.update({
                "narrative": "The same future is repeated.",
                "drivers": ["The same driver"],
                "what_would_make_it_happen": "The same condition.",
                "implication_for_the_sector": "The same implication.",
            })
            duplicate.append(value)
        repaired = [scenario("Baseline"), scenario("Fragmented"), scenario("Accelerated")]
        state = self.state()
        llm = SequenceLLM({"scenarios": duplicate}, {"scenarios": repaired})

        value = F.resolve_semantic_step(
            llm,
            state,
            lambda: None,
            step_id="scenarios",
            state_key="scenarios",
            response_key="scenarios",
            system=F.SYSTEM,
            user="original scenario prompt",
            schema=F.SCENARIO_SCHEMA,
            max_tokens=6000,
            detail="scenarios",
            prepare=F.prepare_scenarios,
        )

        self.assertEqual(value, repaired)
        self.assertEqual([call["detail"] for call in llm.calls], [
            "scenarios", "scenarios [semantic repair 1/1]",
        ])

    def test_malformed_legacy_scenario_drivers_fail_validation_without_crashing(self):
        malformed = [scenario("Baseline"), scenario("Fragmented"), scenario("Accelerated")]
        malformed[1]["drivers"] = 42

        errors = F.scenario_completion_errors(malformed)

        self.assertTrue(any("nonblank driver" in error for error in errors))

    def test_all_refused_milestones_get_one_distinct_repair_and_keep_audit_reasons(self):
        invalid = milestone(target_level=2)
        valid = milestone(target_level=4)
        state = self.state()
        llm = SequenceLLM({"milestones": [invalid]}, {"milestones": [valid]})

        value = F.resolve_semantic_step(
            llm,
            state,
            lambda: None,
            step_id="backcasting",
            state_key="milestones",
            response_key="milestones",
            system=F.SYSTEM,
            user="original backcasting prompt",
            schema=F.MILESTONE_SCHEMA,
            max_tokens=8000,
            detail="backcasting",
            prepare=lambda raw: F.prepare_milestones(raw, {"2.1": 2}),
            refusal_state_key="refused",
        )

        self.assertEqual(len(value), 1)
        self.assertEqual([call["detail"] for call in llm.calls], [
            "backcasting", "backcasting [semantic repair 1/1]",
        ])
        first_hash = F.V.json_call_request_sha256(
            F.SYSTEM, llm.calls[0]["user"], F.MILESTONE_SCHEMA,
            F.PASS, 8000, llm.calls[0]["detail"])
        repair_hash = F.V.json_call_request_sha256(
            F.SYSTEM, llm.calls[1]["user"], F.MILESTONE_SCHEMA,
            F.PASS, 8000, llm.calls[1]["detail"])
        self.assertNotEqual(first_hash, repair_hash)
        self.assertEqual(len(state["refused"]), 1)
        self.assertIn("already at level 2", state["refused"][0]["why"])
        audit = state["semantic_repairs"]["backcasting"]
        self.assertEqual(audit["status"], "complete")
        self.assertEqual(audit["initial_refusals"], state["refused"])

        # A later resume revalidates the clean value and must neither call nor append.
        resumed = SequenceLLM()
        again = F.resolve_semantic_step(
            resumed,
            state,
            lambda: None,
            step_id="backcasting",
            state_key="milestones",
            response_key="milestones",
            system=F.SYSTEM,
            user="original backcasting prompt",
            schema=F.MILESTONE_SCHEMA,
            max_tokens=8000,
            detail="backcasting",
            prepare=lambda raw: F.prepare_milestones(raw, {"2.1": 2}),
            refusal_state_key="refused",
        )
        self.assertEqual(again, value)
        self.assertEqual(resumed.calls, [])
        self.assertEqual(len(state["refused"]), 1)

    def test_exhausted_repair_is_nonretryable_and_never_marks_step_complete(self):
        duplicate = [scenario("Same"), scenario(" same "), scenario("Other")]
        state = self.state()
        llm = SequenceLLM({"scenarios": duplicate}, {"scenarios": duplicate})

        with self.assertRaises(SR.SemanticRepairExhausted) as caught:
            F.resolve_semantic_step(
                llm,
                state,
                lambda: None,
                step_id="scenarios",
                state_key="scenarios",
                response_key="scenarios",
                system=F.SYSTEM,
                user="original scenario prompt",
                schema=F.SCENARIO_SCHEMA,
                max_tokens=6000,
                detail="scenarios",
                prepare=F.prepare_scenarios,
            )

        self.assertEqual(SR.stage_failure_exit(caught.exception), F.V.NONRETRYABLE_STAGE_EXIT)
        self.assertIsNone(state["scenarios"])
        self.assertEqual(state["semantic_repairs"]["scenarios"]["status"], "exhausted")
        self.assertEqual(len(llm.calls), 2)

        # Even an explicit resume stops from the checkpoint without another call.
        resumed = SequenceLLM()
        with self.assertRaises(SR.SemanticRepairExhausted):
            F.resolve_semantic_step(
                resumed,
                state,
                lambda: None,
                step_id="scenarios",
                state_key="scenarios",
                response_key="scenarios",
                system=F.SYSTEM,
                user="original scenario prompt",
                schema=F.SCENARIO_SCHEMA,
                max_tokens=6000,
                detail="scenarios",
                prepare=F.prepare_scenarios,
            )
        self.assertEqual(resumed.calls, [])

    def test_resume_after_repair_journal_replays_without_transport(self):
        duplicate = [scenario("Same"), scenario(" same "), scenario("Other")]
        repaired = [scenario("Baseline"), scenario("Fragmented"), scenario("Accelerated")]
        state = self.state()

        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "foresight-spend.json")
            first_ledger = F.V.Ledger(ceiling=500, label="foresight-first")
            first_ledger.attach(spend_path)
            first = F.V.LLM(
                "anthropic", first_ledger, model="claude-opus-5",
            ).enable_durable_outcomes()
            first._call_anthropic = mock.Mock(side_effect=[
                ({"scenarios": duplicate}, 100, 20),
                ({"scenarios": repaired}, 100, 20),
            ])

            durable_state = {}
            save_count = 0

            def crash_after_repair_journal():
                nonlocal save_count, durable_state
                save_count += 1
                if save_count == 1:
                    durable_state = copy.deepcopy(state)
                    return
                raise RuntimeError("simulated crash before repaired state checkpoint")

            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                F.resolve_semantic_step(
                    first,
                    state,
                    crash_after_repair_journal,
                    step_id="scenarios",
                    state_key="scenarios",
                    response_key="scenarios",
                    system=F.SYSTEM,
                    user="original scenario prompt",
                    schema=F.SCENARIO_SCHEMA,
                    max_tokens=6000,
                    detail="scenarios",
                    prepare=F.prepare_scenarios,
                )
            self.assertEqual(len(first_ledger.calls), 2)
            self.assertEqual(
                durable_state["semantic_repairs"]["scenarios"]["status"],
                "required",
            )

            resumed_ledger = F.V.Ledger(ceiling=500, label="foresight-resumed")
            resumed_ledger.attach(spend_path)
            resumed_ledger.load(spend_path)
            resumed_llm = F.V.LLM(
                "anthropic", resumed_ledger, model="claude-opus-5",
            ).enable_durable_outcomes()
            transport = mock.Mock(side_effect=AssertionError("paid repair replay"))
            resumed_llm._call_anthropic = transport

            value = F.resolve_semantic_step(
                resumed_llm,
                durable_state,
                lambda: None,
                step_id="scenarios",
                state_key="scenarios",
                response_key="scenarios",
                system=F.SYSTEM,
                user="original scenario prompt",
                schema=F.SCENARIO_SCHEMA,
                max_tokens=6000,
                detail="scenarios",
                prepare=F.prepare_scenarios,
            )

            self.assertEqual(value, repaired)
            transport.assert_not_called()
            self.assertEqual(len(resumed_ledger.calls), 2)

    def test_stage5_main_maps_exhausted_semantic_repair_to_exit_78(self):
        duplicate = [scenario("Same"), scenario(" same "), scenario("Other")]
        llm = SequenceLLM({"scenarios": duplicate}, {"scenarios": duplicate})
        source = {
            "id": "WEB-1", "title": "Synthetic outlook",
            "url": "https://example.test/outlook", "tier": "T1",
            "source_kind": "published_source", "sha256": "", "text": "evidence",
        }

        with tempfile.TemporaryDirectory() as directory:
            engine_input = Path(directory) / "engine-input.json"
            engine_input.write_text("{}", encoding="utf-8")
            argv = [
                "foresight.py", "--country", "Fixtureland", "--iso", "FIX",
                "--out", "FIX_semantic", "--vendor", "anthropic/claude-opus-5",
            ]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(F, "LOOP1", directory), \
                    mock.patch.object(
                        F.V, "engine_input_for", return_value=(str(engine_input), True)), \
                    mock.patch.object(F.V, "load_env"), \
                    mock.patch.object(F.V, "LLM", return_value=llm), \
                    mock.patch.object(F.WI, "load_upload_documents", return_value=[]), \
                    mock.patch.object(
                        F, "foresight_context_sources", return_value=[source]), \
                    mock.patch.object(
                        F, "engine_run", return_value={"pillars": {}, "prerequisites": {}}):
                self.assertEqual(F.main(), F.V.NONRETRYABLE_STAGE_EXIT)

            checkpoint = F.V.strict_json_load(
                Path(directory) / "FIX_semantic_foresight_state.json")
            self.assertIsNone(checkpoint["scenarios"])
            self.assertEqual(
                checkpoint["semantic_repairs"]["scenarios"]["status"],
                "exhausted",
            )


if __name__ == "__main__":
    unittest.main()
