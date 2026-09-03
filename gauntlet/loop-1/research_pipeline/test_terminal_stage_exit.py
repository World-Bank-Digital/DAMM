#!/usr/bin/env python3
"""Regression coverage for terminal paid outcomes crossing stage CLI boundaries."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ai_assessment as A
import diagnostic_stage as D
import foresight as F
import investment_options as I
import scan_stage as S
import vendors as V


NONRETRYABLE_EXIT = 78


def terminal_outcome(pass_name):
    return V.VendorTransportAmbiguous(
        vendor="synthetic",
        model="fixture-model",
        pass_name=pass_name,
        detail="safe synthetic terminal outcome",
        max_tokens=1,
        input_tokens=1,
        output_tokens=1,
    )


class FakeLLM:
    model = "fixture-model"

    def enable_durable_outcomes(self):
        return self


class TerminalStageExitTest(unittest.TestCase):
    def test_uncaught_terminal_outcome_maps_to_nonretryable_exit(self):
        def stage():
            raise terminal_outcome("research")

        self.assertEqual(V.run_stage_main(stage), NONRETRYABLE_EXIT)

    def test_ordinary_budget_stop_keeps_the_callers_existing_exit(self):
        error = V.BudgetExhausted("research", 1.0, 1.0)
        self.assertEqual(V.stage_failure_exit(error, 0), 0)

    def test_concurrent_budget_stop_cannot_hide_a_terminal_paid_outcome(self):
        budget = V.BudgetExhausted("research", 1.0, 1.0)
        terminal = terminal_outcome("research")
        self.assertIs(
            V.prefer_terminal_stage_failure(budget, terminal), terminal
        )
        self.assertIs(
            V.prefer_terminal_stage_failure(terminal, budget), terminal
        )

    def test_stage1_wrapper_preserves_terminal_child_exit(self):
        argv = [
            "diagnostic_stage.py",
            "--country", "Fixtureland",
            "--iso", "FIX",
            "--out", "FIX_terminal",
            "--vendor", "anthropic/claude-opus-5",
            "--challenge-vendor", "openai/gpt-5.6-terra",
        ]
        completed = SimpleNamespace(returncode=NONRETRYABLE_EXIT)
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(D.subprocess, "run", return_value=completed):
                with mock.patch.object(D, "checkpoint_combined_spend"):
                    self.assertEqual(D.main(), NONRETRYABLE_EXIT)

    def test_stage3_terminal_outcome_returns_nonretryable_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [
                "ai_assessment.py",
                "--country", "Fixtureland",
                "--iso", "FIX",
                "--out", "FIX_terminal",
                "--vendor", "anthropic/claude-opus-5",
            ]
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(A, "LOOP1", directory):
                    with mock.patch.object(A.V, "load_env"):
                        with mock.patch.object(A.V, "LLM", return_value=FakeLLM()):
                            with mock.patch.object(A, "_uploads", return_value=[]):
                                with mock.patch.object(
                                    A,
                                    "_search_sources",
                                    side_effect=terminal_outcome("ai"),
                                ):
                                    self.assertEqual(
                                        A.main(), NONRETRYABLE_EXIT
                                    )

    def test_scan_wrapper_preserves_terminal_child_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [
                "scan_stage.py",
                "--country", "Fixtureland",
                "--iso", "FIX",
                "--out", "FIX_terminal",
                "--lane", "country",
                "--vendor", "anthropic/claude-opus-5",
            ]
            completed = SimpleNamespace(returncode=NONRETRYABLE_EXIT)
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(S, "LOOP1", directory):
                    with mock.patch.object(S, "checkpoint_lane_spend"):
                        with mock.patch.object(
                            S.subprocess, "run", return_value=completed
                        ):
                            self.assertEqual(S.main(), NONRETRYABLE_EXIT)

    def test_stage5_context_terminal_outcome_returns_nonretryable_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            engine_input = Path(directory) / "input.json"
            engine_input.write_text("{}", encoding="utf-8")
            argv = [
                "foresight.py",
                "--country", "Fixtureland",
                "--iso", "FIX",
                "--out", "FIX_terminal",
                "--vendor", "anthropic/claude-opus-5",
            ]
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(F, "LOOP1", directory):
                    with mock.patch.object(
                        F.V, "engine_input_for", return_value=(str(engine_input), True)
                    ):
                        with mock.patch.object(F.V, "load_env"):
                            with mock.patch.object(F.V, "LLM", return_value=FakeLLM()):
                                with mock.patch.object(
                                    F.WI,
                                    "load_upload_documents",
                                    side_effect=terminal_outcome("foresight"),
                                ):
                                    self.assertEqual(
                                        F.main(), NONRETRYABLE_EXIT
                                    )

    def test_stage6_terminal_outcome_returns_nonretryable_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            out = "FIX_terminal"
            for suffix in ("scans", "foresight", "ai_assessment"):
                (Path(directory) / f"{out}_{suffix}.json").write_text(
                    "{}", encoding="utf-8"
                )
            argv = [
                "investment_options.py",
                "--country", "Fixtureland",
                "--iso", "FIX",
                "--out", out,
                "--vendor", "anthropic/claude-opus-5",
            ]
            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(I, "LOOP1", directory):
                    with mock.patch.object(I, "_uploads", return_value=[]):
                        with mock.patch.object(I, "_read", return_value={}):
                            with mock.patch.object(
                                I, "evidence_context", return_value=[{"id": "fixture"}]
                            ):
                                with mock.patch.object(I.V, "load_env"):
                                    with mock.patch.object(
                                        I.V, "LLM", return_value=FakeLLM()
                                    ):
                                        with mock.patch.object(
                                            I, "appraisal_state", return_value={}
                                        ):
                                            with mock.patch.object(
                                                I,
                                                "synthesize_appraisal",
                                                side_effect=terminal_outcome("investment"),
                                            ):
                                                self.assertEqual(
                                                    I.main(), NONRETRYABLE_EXIT
                                                )


if __name__ == "__main__":
    unittest.main()
