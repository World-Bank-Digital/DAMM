#!/usr/bin/env python3

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import diagnostic_stage as D
import diagnostic as R
import automated_challenge as A


class DiagnosticStageTest(unittest.TestCase):
    def test_challenger_is_from_an_independent_vendor_family(self):
        for primary in ("anthropic/model", "openai/model", "gemini/model"):
            challenger = D.independent_challenger(primary)
            self.assertNotEqual(D.vendor_family(primary), D.vendor_family(challenger))

    def test_family_reads_the_vendor_prefix(self):
        self.assertEqual(D.vendor_family("openai/gpt-test"), "openai")
        self.assertEqual(D.vendor_family(None), "")

    def test_canonical_stage_invokes_the_automated_challenge_not_gate2(self):
        self.assertEqual(
            os.path.basename(D.AUTOMATED_CHALLENGE_SCRIPT),
            "automated_challenge.py",
        )
        self.assertTrue(os.path.isfile(D.AUTOMATED_CHALLENGE_SCRIPT))

    def test_machine_execution_never_satisfies_human_g1_or_g2(self):
        status = R.review_status(automated_challenge_complete=True)
        self.assertEqual(
            status["human_gates"],
            {
                "G1": "pending — named human assessor review required",
                "G2": "pending — independent human review required after G1",
                "G3": "pending — named and dated TTL/country-owner sign-off required",
            },
        )
        self.assertEqual(
            status["automated_challenge"],
            "complete — machine QC only; does not satisfy G1 or G2",
        )

    def test_canonical_outputs_do_not_use_human_g2_names(self):
        paths = A.output_paths("EGY_test")
        self.assertEqual(
            os.path.basename(paths["input"]),
            "EGY_test_automated_challenge_input.json",
        )
        self.assertEqual(
            os.path.basename(paths["report"]),
            "AUTOMATED-CHALLENGE-REPORT-EGY_test.md",
        )
        self.assertTrue(all("_g2_" not in path for path in paths.values()))

    def test_legacy_resume_is_supported_but_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(A, "LOOP1", directory):
                legacy = A.output_paths("EGY_test", legacy_g2_names=True)
                canonical = A.output_paths("EGY_test")
                Path(legacy["state"]).write_bytes(b"legacy")
                self.assertTrue(
                    A._select_legacy_resume_mode(
                        "EGY_test", resume=True, explicit_legacy=False
                    )
                )
                Path(canonical["state"]).write_bytes(b"canonical")
                with self.assertRaisesRegex(ValueError, "conflicting canonical"):
                    A._select_legacy_resume_mode(
                        "EGY_test", resume=True, explicit_legacy=False
                    )
                with self.assertRaisesRegex(ValueError, "conflicting canonical"):
                    A._select_legacy_resume_mode(
                        "EGY_test", resume=True, explicit_legacy=True
                    )

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(A, "LOOP1", directory):
                legacy = A.output_paths("EGY_test", legacy_g2_names=True)
                canonical = A.output_paths("EGY_test")
                Path(legacy["report"]).write_bytes(b"legacy report")
                Path(canonical["report"]).write_bytes(b"canonical report")
                with self.assertRaisesRegex(ValueError, "report checkpoints"):
                    A._select_legacy_resume_mode(
                        "EGY_test", resume=True, explicit_legacy=False
                    )

    def test_legacy_promotion_never_replaces_a_canonical_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(A, "LOOP1", directory):
                legacy = A.output_paths("EGY_test", legacy_g2_names=True)
                canonical = A.output_paths("EGY_test")
                for key, path in legacy.items():
                    Path(path).write_bytes(f"legacy {key}".encode("utf-8"))
                A._publish_canonical_outputs(legacy, "EGY_test")
                for key in legacy:
                    self.assertEqual(
                        Path(canonical[key]).read_bytes(),
                        Path(legacy[key]).read_bytes(),
                    )

                Path(canonical["report"]).write_bytes(b"another artifact identity")
                with self.assertRaisesRegex(ValueError, "conflicting canonical"):
                    A._publish_canonical_outputs(legacy, "EGY_test")
                self.assertEqual(
                    Path(canonical["report"]).read_bytes(),
                    b"another artifact identity",
                )

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(A, "LOOP1", directory):
                legacy = A.output_paths("EGY_test", legacy_g2_names=True)
                canonical = A.output_paths("EGY_test")
                for key, path in legacy.items():
                    Path(path).write_bytes(f"legacy {key}".encode("utf-8"))
                Path(canonical["report"]).write_bytes(b"another artifact identity")
                with self.assertRaisesRegex(ValueError, "conflicting canonical"):
                    A._publish_canonical_outputs(legacy, "EGY_test")
                for key in ("state", "spend", "findings", "input"):
                    self.assertFalse(Path(canonical[key]).exists())

    def test_legacy_challenge_spend_is_counted_once_and_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(D, "LOOP1", directory):
                primary = Path(directory) / "EGY_test_spend.json"
                legacy = Path(directory) / "EGY_test_g2_spend.json"
                canonical = (
                    Path(directory) / "EGY_test_automated_challenge_spend.json"
                )
                primary.write_text(
                    json.dumps({"summary": {"total": 2.5}}), encoding="utf-8"
                )
                legacy.write_text(
                    json.dumps({"summary": {"total": 3.5}}), encoding="utf-8"
                )
                combined_path = Path(D.checkpoint_combined_spend("EGY_test"))
                combined = json.loads(combined_path.read_text(encoding="utf-8"))
                self.assertEqual(combined["summary"]["total"], 6.0)
                self.assertEqual(
                    combined["source_ledgers"],
                    ["EGY_test_spend.json", "EGY_test_g2_spend.json"],
                )

                canonical.write_text(
                    json.dumps({"summary": {"total": 4.5}}), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "conflicting canonical"):
                    D.checkpoint_combined_spend("EGY_test")

    def test_spend_checkpoint_rejects_a_singleton_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(D, "LOOP1", directory):
                target = Path(directory) / "outside-ledger.json"
                target.write_text(
                    json.dumps({"summary": {"total": 3.5}}), encoding="utf-8"
                )
                alias = Path(directory) / "EGY_test_automated_challenge_spend.json"
                alias.symlink_to(target)
                with self.assertRaisesRegex(ValueError, "not a regular file"):
                    D.checkpoint_combined_spend("EGY_test")

    def test_renderer_cannot_treat_legacy_free_text_as_human_approval(self):
        loop1 = Path(HERE).parent
        source_config = json.loads(
            (loop1 / "config_egy.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "diagnostic.html"
            source_config["data_path"] = str(loop1 / "EGY_v17.json")
            source_config["register_path"] = str(loop1 / "research/EGY_register.json")
            source_config["out_path"] = str(output)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="config_lifecycle_",
                suffix=".json",
                dir=loop1,
                delete=False,
            ) as handle:
                json.dump(source_config, handle)
                config_path = Path(handle.name)
            self.addCleanup(config_path.unlink, missing_ok=True)
            key = config_path.stem.removeprefix("config_")
            completed = subprocess.run(
                [sys.executable, str(loop1 / "render_v17.py"), key],
                cwd=loop1,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            rendered = output.read_text(encoding="utf-8")
            self.assertNotIn("derivations adjusted with recorded reasons", rendered)
            self.assertNotIn("prerequisite rows re-verified and confirmed", rendered)
            self.assertIn("named human assessor review required", rendered)
            self.assertIn("independent human review required after G1", rendered)


if __name__ == "__main__":
    unittest.main()
