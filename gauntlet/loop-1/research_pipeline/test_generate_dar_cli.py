#!/usr/bin/env python3
"""CLI integration checks for the DAR generator.

These checks cross the same command-line seam a production caller uses.  The only
substitution is the true external dependency: recorded chapter responses stand in for
the live reasoning vendor so the run is deterministic and needs no keys or network.
"""

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOP1 = HERE.parent
SCRIPT = HERE / "generate_dar.py"
REFERENCE = "EGY_202608260342_clean"
FROZEN_REPLAY = HERE / "fixtures" / f"{REFERENCE}_replay_v2.json"

sys.path.insert(0, str(HERE))
import generate_dar as D
import vendors as V
from engine_v17 import run as engine_run


def copy_reference_inputs(run: Path) -> None:
    """Give an isolated CLI run the committed assessment, scans and foresight inputs."""
    for suffix in ("g2_input", "scans", "foresight", "run_package"):
        shutil.copyfile(LOOP1 / f"{REFERENCE}_{suffix}.json",
                        Path(f"{run}_{suffix}.json"))


def refresh_run_package(run: Path) -> None:
    path = Path(f"{run}_run_package.json")
    package = json.loads(path.read_text(encoding="utf-8"))
    for name, suffix in (("engine_input", "g2_input"),
                         ("scans", "scans"), ("foresight", "foresight")):
        package["files"][name]["sha256"] = hashlib.sha256(
            Path(f"{run}_{suffix}.json").read_bytes()).hexdigest()
    path.write_text(json.dumps(package), encoding="utf-8")


def bind_replay_to_run(tape: dict, run: Path) -> dict:
    """Bind every recorded answer to the exact public-CLI prompt it answers."""
    required = [Path(f"{run}_{suffix}.json")
                for suffix in ("g2_input", "scans", "foresight")]
    if not all(path.exists() for path in required):
        # Preflight-failure tests never reach the adapter; a legacy tape is sufficient.
        tape["format"] = "damm.llm-replay/v1"
        return tape
    rows, scans, foresight = [json.loads(path.read_text(encoding="utf-8"))
                              for path in required]
    country = scans["country"]
    assessment = engine_run(country, rows, refyear=D.ASSESSMENT_YEAR)
    outline = {str(chapter["n"]): chapter for chapter in D.OUTLINE}
    for entry in tape["responses"]:
        chapter_id = entry["detail"].split()[-1]
        chapter = outline[chapter_id]
        user = D.chapter_user_prompt(chapter, assessment, scans, foresight, country)
        entry["request_sha256"] = V.json_call_request_sha256(
            D.SYSTEM, user, D.CHAPTER_SCHEMA, D.PASS, 8000, entry["detail"])
        entry["response_sha256"] = V.stable_json_sha256(entry["response"])
    tape["format"] = "damm.llm-replay/v2"
    return tape


def write_success_replay(path: Path, fixture_id: str = "egypt-success-v1",
                         run: Path = None) -> None:
    responses = []
    for chapter in range(1, 11):
        response = {
            "prose": "This chapter records the assessment context."
                     if chapter < 3 else
                     "This chapter proposes actions for review.",
            "cites": {
                "pillars": [],
                "indicators": [],
                "use_cases": [],
                "prerequisites": [],
            },
            "claims": [],
            "figures": [],
        }
        if chapter >= 3:
            response["claims"] = [{
                "text": "This chapter proposes actions for review.",
                "basis": "proposal",
                "source_refs": [],
            }]
        if chapter in (1, 2):
            response.update({
                "prose": "The A1 pillar mean is 3.6.",
                "cites": {
                    "pillars": ["A1"],
                    "indicators": [],
                    "use_cases": [],
                    "prerequisites": [],
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
            })
        responses.append({
            "pass_name": "generation",
            "detail": f"chapter {chapter}",
            "response": response,
        })
    tape = {
        "format": "damm.llm-replay/v1",
        "fixture_id": fixture_id,
        "responses": responses,
    }
    path.write_text(json.dumps(bind_replay_to_run(
        tape, run or (path.parent / "fixture"))), encoding="utf-8")


def replace_replay_response(path: Path, chapter: str, response: dict) -> None:
    response.setdefault("claims", [])
    tape = json.loads(path.read_text(encoding="utf-8"))
    entry = next(item for item in tape["responses"]
                 if item["detail"] == f"chapter {chapter}")
    entry["response"] = response
    if tape.get("format") == "damm.llm-replay/v2":
        entry["response_sha256"] = V.stable_json_sha256(response)
    path.write_text(json.dumps(tape), encoding="utf-8")


class GenerateDarCliTest(unittest.TestCase):
    def test_missing_engine_input_is_nonzero_and_manifested(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            replay = Path(td) / "responses.json"
            write_success_replay(replay)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest_path = Path(f"{run}_dar_manifest.json")
            self.assertTrue(manifest_path.exists(), result.stdout + result.stderr)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["reason"]["code"], "required_input_missing")
            self.assertIsNone(manifest["artifacts"]["dar_json"])

    def test_failed_rerun_removes_stale_dar_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            command = [sys.executable, str(SCRIPT),
                       "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                       "--replay", str(replay)]

            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertTrue(Path(f"{run}_dar.json").exists())
            self.assertTrue(Path(f"{run}_dar.html").exists())

            Path(f"{run}_scans.json").unlink()
            second = subprocess.run(command, text=True, capture_output=True, check=False)

            self.assertNotEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["reason"]["code"], "required_input_missing")
            self.assertIsNone(manifest["artifacts"]["dar_json"])
            self.assertIsNone(manifest["artifacts"]["dar_html"])

    def test_parse_failed_rerun_invalidates_a_prior_complete_publication(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            command = [sys.executable, str(SCRIPT),
                       "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                       "--replay", str(replay)]

            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertTrue(Path(f"{run}_dar.json").exists())
            self.assertTrue(Path(f"{run}_dar.html").exists())
            first_manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(first_manifest["status"], "complete")

            failed = subprocess.run(
                command + ["--ceiling", "not-a-number"],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["reason"]["code"], "cli_parse_failed")
            self.assertIsNone(manifest["artifacts"]["dar_json"])
            self.assertIsNone(manifest["artifacts"]["dar_html"])

    def test_non_finite_budget_rerun_invalidates_a_prior_complete_publication(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            command = [sys.executable, str(SCRIPT),
                       "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                       "--replay", str(replay)]

            first = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

            failed = subprocess.run(
                command + ["--ceiling", "nan"],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["reason"]["code"], "invalid_argument")

    def test_non_finite_engine_input_is_rejected_before_generation(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, run=run)

            input_path = Path(f"{run}_g2_input.json")
            rows = json.loads(input_path.read_text(encoding="utf-8"))
            rows["1.1"]["value"] = float("nan")
            input_path.write_text(json.dumps(rows), encoding="utf-8")
            refresh_run_package(run)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reason"]["code"], "required_input_invalid")
            self.assertIn("non-finite JSON number", manifest["reason"]["detail"])
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())

    def test_self_hashed_review_package_cannot_authorize_an_invalid_row_class(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)

            input_path = Path(f"{run}_g2_input.json")
            rows = json.loads(input_path.read_text(encoding="utf-8"))
            rows["1.1"]["cls"] = "BANANA"
            input_path.write_text(json.dumps(rows), encoding="utf-8")
            refresh_run_package(run)

            replay = Path(td) / "responses.json"
            write_success_replay(replay, fixture_id="forged-review-v1", run=run)
            package_path = Path(f"{run}_run_package.json")
            package = json.loads(package_path.read_text(encoding="utf-8"))
            package["files"]["replay"] = {
                "sha256": hashlib.sha256(replay.read_bytes()).hexdigest(),
                "fixture_id": "forged-review-v1",
            }
            package_path.write_text(json.dumps(package), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reason"]["code"], "required_input_invalid")
            self.assertIn("row 1.1 cls", manifest["reason"]["detail"])
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())

    def test_country_identity_mismatch_blocks_before_generation(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Nigeria", "--iso", "NGA", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["reason"]["code"], "input_identity_mismatch")
            self.assertFalse(Path(f"{run}_dar.json").exists())

    def test_assessment_year_mismatch_blocks_before_generation(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            foresight_path = Path(f"{run}_foresight.json")
            foresight = json.loads(foresight_path.read_text(encoding="utf-8"))
            foresight["assessment_year"] = D.ASSESSMENT_YEAR - 1
            foresight_path.write_text(json.dumps(foresight), encoding="utf-8")
            replay = Path(td) / "responses.json"
            write_success_replay(replay)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reason"]["code"], "input_identity_mismatch")

    def test_engine_input_swap_is_rejected_by_the_reviewed_package(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            shutil.copyfile(LOOP1 / "NGA_shadow_g2_input.json",
                            Path(f"{run}_g2_input.json"))
            replay = Path(td) / "responses.json"
            write_success_replay(replay)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reason"]["code"], "input_package_mismatch")
            self.assertFalse(Path(f"{run}_dar.json").exists())

    def test_metadata_only_products_do_not_satisfy_the_public_seam(self):
        for suffix, product in (("scans", {
                "schema_version": "damm.scans/v1", "country": "Egypt", "iso3": "EGY",
                "assessment_year": D.ASSESSMENT_YEAR,
            }), ("foresight", {
                "schema_version": "damm.foresight/v1", "country": "Egypt", "iso3": "EGY",
                "assessment_year": D.ASSESSMENT_YEAR,
            })):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory(
                    prefix="damm-dar-cli-") as td:
                run = Path(td) / "fixture"
                copy_reference_inputs(run)
                Path(f"{run}_{suffix}.json").write_text(
                    json.dumps(product), encoding="utf-8")
                refresh_run_package(run)
                replay = Path(td) / "responses.json"
                write_success_replay(replay, run=run)

                result = subprocess.run(
                    [sys.executable, str(SCRIPT),
                     "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                     "--replay", str(replay)],
                    text=True, capture_output=True, check=False,
                )

                self.assertNotEqual(result.returncode, 0,
                                    result.stdout + result.stderr)
                manifest = json.loads(
                    Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["reason"]["code"],
                                 "required_product_incomplete")
                self.assertFalse(Path(f"{run}_dar.json").exists())

    def test_vacuous_product_records_do_not_satisfy_the_public_seam(self):
        def vacuous_scans(run):
            path = Path(f"{run}_scans.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            data["country_findings"] = [{}]
            data["international_pointers"] = []
            data["register_entries"] = []
            data["abstained"] = []
            path.write_text(json.dumps(data), encoding="utf-8")

        def vacuous_foresight(run):
            path = Path(f"{run}_foresight.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            data.update({
                "method": "x",
                "scenarios": [{}],
                "scenario_status": "x",
                "preferred_future": {"name": "x"},
                "preferred_future_status": "x",
                "milestones": [{}],
                "candidate_status": "x",
            })
            path.write_text(json.dumps(data), encoding="utf-8")

        for label, make_vacuous in (("scans", vacuous_scans),
                                    ("foresight", vacuous_foresight)):
            with self.subTest(product=label), tempfile.TemporaryDirectory(
                    prefix="damm-dar-cli-") as td:
                run = Path(td) / "fixture"
                copy_reference_inputs(run)
                replay = Path(td) / "responses.json"
                write_success_replay(replay, run=run)
                make_vacuous(run)
                refresh_run_package(run)

                result = subprocess.run(
                    [sys.executable, str(SCRIPT),
                     "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                     "--replay", str(replay)],
                    text=True, capture_output=True, check=False,
                )

                self.assertNotEqual(result.returncode, 0,
                                    result.stdout + result.stderr)
                manifest = json.loads(
                    Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["reason"]["code"],
                                 "required_product_incomplete")
                self.assertFalse(Path(f"{run}_dar.json").exists())

    def test_country_scan_record_cannot_belong_to_another_country(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, run=run)

            scans_path = Path(f"{run}_scans.json")
            scans = json.loads(scans_path.read_text(encoding="utf-8"))
            scans["country_findings"][0]["about_country"] = "Nigeria"
            scans["country_findings"][0]["statement"] = (
                "This record describes a Nigeria-specific programme.")
            scans_path.write_text(json.dumps(scans), encoding="utf-8")
            refresh_run_package(run)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reason"]["code"],
                             "required_product_incomplete")
            self.assertIn("about_country", manifest["reason"]["detail"])

    def test_legacy_unbound_replay_format_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            replay.write_text(json.dumps({
                "format": "damm.llm-replay/v1",
                "fixture_id": "unbound-legacy",
                "responses": [],
            }), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reason"]["code"],
                             "adapter_initialization_failed")
            self.assertIn("unsupported replay format", manifest["reason"]["detail"])

    def test_incomplete_replay_is_nonzero_and_manifested(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)

            replay = Path(td) / "responses.json"
            tape = {
                "format": "damm.llm-replay/v1",
                "fixture_id": "incomplete-after-one-chapter",
                "responses": [{
                    "pass_name": "generation",
                    "detail": "chapter 1",
                    "response": {
                        "prose": "The agricultural context is recorded in the assessment.",
                        "cites": {
                            "pillars": ["A1"],
                            "indicators": [],
                            "use_cases": [],
                            "prerequisites": [],
                        },
                        "claims": [{
                            "text": "The agricultural context is recorded in the assessment.",
                            "basis": "evidence",
                            "source_refs": ["pillar:A1:mean"],
                        }],
                        "figures": [],
                    },
                }],
            }
            replay.write_text(json.dumps(bind_replay_to_run(tape, run)),
                              encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())

            manifest_path = Path(f"{run}_dar_manifest.json")
            self.assertTrue(manifest_path.exists(), result.stdout + result.stderr)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "incomplete")
            self.assertEqual(manifest["reason"]["code"], "chapter_generation_failed")
            self.assertEqual(manifest["chapters"]["completed"], 1)
            self.assertEqual(manifest["chapters"]["expected"], 11)

    def test_replay_response_is_rejected_when_its_prompt_has_changed(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)

            scans_path = Path(f"{run}_scans.json")
            scans = json.loads(scans_path.read_text(encoding="utf-8"))
            target = next(item for item in scans["country_findings"]
                          if str(item["chapter"]) == "8")
            target["statement"] += " Updated after the replay was recorded."
            scans_path.write_text(json.dumps(scans), encoding="utf-8")
            refresh_run_package(run)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "incomplete")
            self.assertEqual(manifest["reason"]["code"], "chapter_generation_failed")
            self.assertIn("request hash mismatch", manifest["reason"]["detail"])
            self.assertFalse(Path(f"{run}_dar.json").exists())

    def test_ten_replayed_chapters_plus_deterministic_annex_emit_a_complete_dar(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            dar_path = Path(f"{run}_dar.json")
            html_path = Path(f"{run}_dar.html")
            manifest_path = Path(f"{run}_dar_manifest.json")
            self.assertTrue(dar_path.exists())
            self.assertTrue(html_path.exists())
            self.assertTrue(manifest_path.exists())

            dar = json.loads(dar_path.read_text(encoding="utf-8"))
            self.assertEqual([str(chapter["n"]) for chapter in dar["chapters"]],
                             ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "A"])
            annex = dar["chapters"][-1]
            self.assertEqual(annex["status"], "deterministic audit trail")
            row = next(item for item in annex["annex"]["indicator_evidence"]
                       if item["id"] == "1.1")
            self.assertEqual(row["value"], 8942.42)
            self.assertEqual(row["source"]["url"],
                             "https://data.worldbank.org/indicator/NV.AGR.EMPL.KD")

            rendered = html_path.read_text(encoding="utf-8")
            self.assertIn("Annexes", rendered)
            self.assertIn("NV.AGR.EMPL.KD", rendered)
            for heading in ("Candidate rows", "Country findings",
                            "International pointers", "Initiative register",
                            "Foresight record", "Method record"):
                self.assertIn(heading, rendered)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "complete")
            self.assertTrue(manifest["run_id"])
            self.assertTrue(manifest["started_at"])
            self.assertTrue(manifest["finished_at"])
            self.assertFalse(manifest["reviewed"])
            self.assertEqual(manifest["review"],
                             {"inputs": True, "narrative": False})
            self.assertFalse(dar["reviewed"])
            self.assertTrue(dar["status"].startswith("Draft DAR"))
            self.assertIn("Draft Digital Agriculture Roadmap", rendered)
            self.assertIn("Publication hold", rendered)
            self.assertEqual(manifest["execution"]["mode"], "replay")
            self.assertTrue(manifest["execution"]["resolved"].startswith("replay/"))
            self.assertEqual(set(manifest["inputs"]),
                             {"engine_input", "scans", "foresight", "run_package",
                              "replay"})
            self.assertEqual(set(manifest["implementation"]),
                             {"generator", "engine", "model", "adapter"})
            for record in list(manifest["inputs"].values()) + list(
                    manifest["implementation"].values()):
                self.assertEqual(len(record["sha256"]), 64)
            self.assertEqual([check["id"] for check in manifest["qc"]],
                             ["B1", "B2", "B3", "B4", "B5", "B6"])
            self.assertTrue(all(check["ok"] for check in manifest["qc"]))
            for key, path in (("dar_json", dar_path), ("dar_html", html_path)):
                artifact = manifest["artifacts"][key]
                content = path.read_bytes()
                self.assertEqual(artifact["file"], path.name)
                self.assertEqual(artifact["bytes"], len(content))
                self.assertEqual(artifact["sha256"], hashlib.sha256(content).hexdigest())

    def test_consistent_candidate_reuse_crosses_the_public_cli_seam(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)

            foresight_path = Path(f"{run}_foresight.json")
            foresight = json.loads(foresight_path.read_text(encoding="utf-8"))
            reused = copy.deepcopy(foresight["milestones"][2])
            reused["statement"] = "A later milestone reuses the same candidate metric."
            reused["target_year"] += 2
            foresight["milestones"].append(reused)
            foresight_path.write_text(json.dumps(foresight), encoding="utf-8")
            refresh_run_package(run)

            replay = Path(td) / "responses.json"
            write_success_replay(replay, run=run)
            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "complete")

    def test_run_id_is_content_based_when_a_package_is_relocated(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as left_td, \
                tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as right_td:
            run_ids = []
            for td in (left_td, right_td):
                run = Path(td) / "relocated"
                copy_reference_inputs(run)
                replay = Path(td) / "responses.json"
                write_success_replay(replay, run=run)
                result = subprocess.run(
                    [sys.executable, str(SCRIPT),
                     "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                     "--replay", str(replay)],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0,
                                 result.stdout + result.stderr)
                manifest = json.loads(
                    Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
                run_ids.append(manifest["run_id"])

            self.assertEqual(run_ids[0], run_ids[1])

    def test_chapter_may_cite_indicator_present_in_authorized_derived_pack(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "2", {
                "prose": "Agricultural data interoperability standards are absent.",
                "cites": {
                    "pillars": [],
                    "indicators": ["3.11"],
                    "use_cases": [],
                    "prerequisites": [],
                },
                "claims": [{
                    "text": "Agricultural data interoperability standards are absent.",
                    "basis": "evidence",
                    "source_refs": ["derived:constraints:3.11:level"],
                }],
                "figures": [],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"] if str(item["n"]) == "2")
            self.assertEqual(chapter["cited_outside_binding"], [])

    def test_unseen_citation_rejects_the_run_and_is_recorded(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "2", {
                "prose": "The chapter makes an unrelated connectivity claim.",
                "cites": {
                    "pillars": [],
                    "indicators": ["2.4"],
                    "use_cases": [],
                    "prerequisites": [],
                },
                "figures": [],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "rejected")
            self.assertEqual(manifest["reason"]["code"], "qc_failed")
            b2 = next(check for check in manifest["qc"] if check["id"] == "B2")
            self.assertFalse(b2["ok"])

    def test_unseen_prose_reference_cannot_bypass_empty_cites(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "1", {
                "prose": "Indicator 8.17 and use case FIN are national priorities.",
                "cites": {
                    "pillars": [], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "figures": [],
            })
            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b2 = next(check for check in manifest["qc"] if check["id"] == "B2")
            self.assertFalse(b2["ok"])
            self.assertIn("prose indicator 8.17", b2["detail"])
            self.assertIn("prose use_case FIN", b2["detail"])

    def test_unbound_qualitative_diagnostic_claim_rejects_the_run(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "1", {
                "prose": ("Egypt has universal rural broadband coverage and complete "
                          "farmer data interoperability."),
                "cites": {
                    "pillars": [], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "figures": [],
                "claims": [],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b2 = next(check for check in manifest["qc"] if check["id"] == "B2")
            self.assertFalse(b2["ok"])
            self.assertIn("unbound diagnostic sentence", b2["detail"])

    def test_factual_prose_in_a_prescriptive_chapter_still_requires_provenance(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "3", {
                "prose": ("Egypt has universal rural broadband coverage and complete "
                          "farmer data interoperability."),
                "cites": {
                    "pillars": [], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "claims": [],
                "figures": [],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b2 = next(check for check in manifest["qc"] if check["id"] == "B2")
            self.assertFalse(b2["ok"])
            self.assertIn("unbound prose sentence", b2["detail"])

    def test_number_elsewhere_in_assessment_but_outside_chapter_pack_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "1", {
                "prose": "Agricultural value added per worker is 8942.42.",
                "cites": {
                    "pillars": ["A1"], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "figures": [{
                    "value": "8942.42",
                    "what_it_is": "Agriculture value added per worker",
                    "basis": "evidence",
                    "operation": "none",
                    "source_refs": ["pillar:A1:mean"],
                    "inputs": [],
                    "rationale": "Claimed from A1 for the rejection test.",
                }],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b4 = next(check for check in manifest["qc"] if check["id"] == "B4")
            self.assertFalse(b4["ok"])

    def test_decorated_scan_figure_is_declared_and_traceable(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "8", {
                "prose": "The existing climate-resilient investment vehicle carries US$250 million.",
                "cites": {
                    "pillars": [],
                    "indicators": [],
                    "use_cases": [],
                    "prerequisites": [],
                },
                "claims": [{
                    "text": ("The existing climate-resilient investment vehicle carries "
                             "US$250 million."),
                    "basis": "evidence",
                    "source_refs": ["scan:country_findings:3:number:0"],
                }],
                "figures": [{
                    "value": "US$250 million",
                    "what_it_is": "Financing reported by the source",
                    "basis": "evidence",
                    "operation": "none",
                    "source_refs": ["scan:country_findings:3:number:0"],
                    "inputs": [],
                    "rationale": "Quoted from the country finding.",
                }],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"] if str(item["n"]) == "8")
            self.assertEqual(chapter["stray_numbers"], [])
            self.assertEqual(chapter["unsupported_figures"], [])
            self.assertEqual(chapter["supported_figures"], 1)

    def test_undeclared_scan_number_rejects_the_run(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "8", {
                "prose": "The existing climate-resilient investment vehicle carries US$250 million.",
                "cites": {
                    "pillars": [],
                    "indicators": [],
                    "use_cases": [],
                    "prerequisites": [],
                },
                "figures": [],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b5 = next(check for check in manifest["qc"] if check["id"] == "B5")
            self.assertFalse(b5["ok"])
            self.assertIn("250", b5["detail"])

    def test_arbitrary_declared_prescriptive_figure_without_valid_basis_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "3", {
                "prose": "The proposed envelope is US$999 billion.",
                "cites": {
                    "pillars": [], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "claims": [{
                    "text": "The proposed envelope is US$999 billion.",
                    "basis": "proposal",
                    "source_refs": [],
                }],
                "figures": [{
                    "value": "US$999 billion", "what_it_is": "proposed envelope",
                    "basis": "evidence", "operation": "none",
                    "source_refs": ["pillar:A1:mean"],
                    "inputs": [], "rationale": "Claimed as evidence without support.",
                }],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b5 = next(check for check in manifest["qc"] if check["id"] == "B5")
            self.assertFalse(b5["ok"])
            self.assertIn("US$999 billion", b5["detail"])

    def test_explicit_reasoned_planning_assumption_is_traceable(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "3", {
                "prose": "The roadmap proposes a planning envelope of US$999 billion.",
                "cites": {
                    "pillars": [], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "claims": [{
                    "text": ("The roadmap proposes a planning envelope of "
                             "US$999 billion."),
                    "basis": "proposal",
                    "source_refs": [],
                }],
                "figures": [{
                    "value": "US$999 billion", "what_it_is": "planning envelope",
                    "basis": "planning_assumption", "operation": "none",
                    "source_refs": [], "inputs": [],
                    "rationale": ("A deliberately explicit planning assumption for "
                                  "subsequent appraisal, not an evidence claim."),
                }],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"] if str(item["n"]) == "3")
            self.assertEqual(chapter["figures"][0]["basis"], "planning_assumption")
            self.assertEqual(chapter["stray_numbers"], [])

    def test_factual_claim_cannot_be_laundered_as_a_planning_assumption(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "3", {
                "prose": "Egypt currently has 999 million farmers.",
                "cites": {
                    "pillars": [], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "figures": [{
                    "value": "999 million farmers",
                    "what_it_is": "asserted current farmer population",
                    "basis": "planning_assumption", "operation": "none",
                    "source_refs": [], "inputs": [],
                    "rationale": ("A long rationale cannot turn a factual assertion "
                                  "into a proposal."),
                }],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b5 = next(check for check in manifest["qc"] if check["id"] == "B5")
            self.assertFalse(b5["ok"])
            self.assertIn("999 million farmers", b5["detail"])

    def test_calculation_cannot_relabel_row_inputs_as_districts(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "4", {
                "prose": "The rollout covers 15 districts.",
                "cites": {
                    "pillars": ["C3"], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "figures": [{
                    "value": "15 districts", "what_it_is": "rollout coverage",
                    "basis": "calculation", "operation": "sum",
                    "source_refs": ["pillar:C3:rated", "pillar:C3:n"],
                    "inputs": ["7 rows", "8 rows"],
                    "rationale": "Seven rows plus eight rows is fifteen districts.",
                }],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(Path(f"{run}_dar.json").exists())
            self.assertFalse(Path(f"{run}_dar.html").exists())
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b5 = next(check for check in manifest["qc"] if check["id"] == "B5")
            self.assertFalse(b5["ok"])
            self.assertIn("15 districts", b5["detail"])

    def test_project_and_fiscal_identifiers_are_not_numeric_claims(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay)
            replace_replay_response(replay, "8", {
                "prose": "The P180480 vehicle is reflected in the FY2025/26 planning cycle.",
                "cites": {
                    "pillars": [],
                    "indicators": [],
                    "use_cases": [],
                    "prerequisites": [],
                },
                "claims": [{
                    "text": ("The P180480 vehicle is reflected in the FY2025/26 "
                             "planning cycle."),
                    "basis": "evidence",
                    "source_refs": ["scan:country_findings:3:number:0"],
                }],
                "figures": [],
            })

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"] if str(item["n"]) == "8")
            self.assertEqual(chapter["stray_numbers"], [])

    def test_resume_reuses_a_chapter_when_its_request_is_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, fixture_id="resume-v1")
            tape = json.loads(replay.read_text(encoding="utf-8"))
            tape["responses"] = tape["responses"][:1]
            replay.write_text(json.dumps(tape), encoding="utf-8")

            first = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(first.returncode, 0, first.stdout + first.stderr)

            write_success_replay(replay, fixture_id="resume-v1")
            resumed = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay), "--resume"],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"] if str(item["n"]) == "1")
            self.assertEqual(chapter["prose"],
                             "The A1 pillar mean is 3.6.")
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["chapters"]["reused"], ["1"])
            self.assertEqual(manifest["chapters"]["regenerated"],
                             ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"])

    def test_resume_regenerates_when_the_recorded_response_changes(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, fixture_id="resume-response-v1")
            tape = json.loads(replay.read_text(encoding="utf-8"))
            tape["responses"] = tape["responses"][:1]
            replay.write_text(json.dumps(tape), encoding="utf-8")

            first = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(first.returncode, 0, first.stdout + first.stderr)

            write_success_replay(replay, fixture_id="resume-response-v1")
            replace_replay_response(replay, "1", {
                "prose": "The replacement response contains an unsupported 999.",
                "cites": {
                    "pillars": [], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "figures": [],
            })
            resumed = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay), "--resume"],
                text=True, capture_output=True, check=False,
            )

            self.assertNotEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("1", manifest["chapters"]["reused"])
            self.assertIn("1", manifest["chapters"]["regenerated"])
            b5 = next(check for check in manifest["qc"] if check["id"] == "B5")
            self.assertFalse(b5["ok"])
            self.assertIn("999", b5["detail"])

    def test_resume_regenerates_when_cached_raw_response_is_tampered(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, fixture_id="resume-qc-v1")
            tape = json.loads(replay.read_text(encoding="utf-8"))
            tape["responses"] = tape["responses"][:1]
            replay.write_text(json.dumps(tape), encoding="utf-8")

            first = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(first.returncode, 0, first.stdout + first.stderr)

            state_path = Path(f"{run}_generation_state.json")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["chapters"]["1"]["prose"] += " An unreviewed value is 999."
            state["chapters"]["1"]["stray_numbers"] = []
            state_path.write_text(json.dumps(state), encoding="utf-8")

            write_success_replay(replay, fixture_id="resume-qc-v1")
            resumed = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay), "--resume"],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"]
                           if str(item["n"]) == "1")
            self.assertEqual(chapter["prose"], "The A1 pillar mean is 3.6.")
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            b5 = next(check for check in manifest["qc"] if check["id"] == "B5")
            self.assertTrue(b5["ok"])
            self.assertNotIn("999", b5["detail"])
            self.assertNotIn("1", manifest["chapters"]["reused"])
            self.assertIn("1", manifest["chapters"]["regenerated"])

    def test_resume_rejects_a_tampered_response_with_a_matching_checkpoint_hash(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, fixture_id="resume-tamper-v1")

            first = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

            state_path = Path(f"{run}_generation_state.json")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["chapters"]["1"]["prose"] = "A tampered cache claims 999."
            raw_response = D.chapter_response(state["chapters"]["1"])
            state["response_sha256"]["1"] = D._sha256(raw_response)
            state_path.write_text(json.dumps(state), encoding="utf-8")

            resumed = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay), "--resume"],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"]
                           if str(item["n"]) == "1")
            self.assertEqual(chapter["prose"], "The A1 pillar mean is 3.6.")
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("1", manifest["chapters"]["reused"])
            self.assertIn("1", manifest["chapters"]["regenerated"])

    def test_legacy_unidentified_cache_is_ignored_and_regenerated(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, fixture_id="legacy-cache-v1")
            Path(f"{run}_generation_state.json").write_text(json.dumps({
                "chapters": {
                    "1": {
                        "prose": "A legacy cache claims 999.",
                        "cites": {"pillars": [], "indicators": [],
                                  "use_cases": [], "prerequisites": []},
                        "figures": [],
                    },
                },
            }), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay), "--resume"],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"] if str(item["n"]) == "1")
            self.assertEqual(chapter["prose"], "The A1 pillar mean is 3.6.")
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["chapters"]["reused"], [])
            self.assertEqual(manifest["chapters"]["regenerated"],
                             ["1", "2", "3", "4", "5", "6", "7", "8", "9",
                              "10", "A"])

    def test_resume_regenerates_a_chapter_when_its_evidence_changes(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)
            replay = Path(td) / "responses.json"
            write_success_replay(replay, fixture_id="changed-evidence-v1")
            tape = json.loads(replay.read_text(encoding="utf-8"))
            tape["responses"] = tape["responses"][:1]
            replay.write_text(json.dumps(tape), encoding="utf-8")

            first = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(first.returncode, 0, first.stdout + first.stderr)

            input_path = Path(f"{run}_g2_input.json")
            rows = json.loads(input_path.read_text(encoding="utf-8"))
            rows["1.1"]["value"] = 1.0
            rows["1.1"]["level"] = 1
            input_path.write_text(json.dumps(rows), encoding="utf-8")
            refresh_run_package(run)

            write_success_replay(replay, fixture_id="changed-evidence-v1")
            replace_replay_response(replay, "1", {
                "prose": "This chapter was regenerated from the changed assessment.",
                "cites": {
                    "pillars": ["A1"], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "claims": [{
                    "text": "This chapter was regenerated from the changed assessment.",
                    "basis": "evidence",
                    "source_refs": ["pillar:A1:mean"],
                }],
                "figures": [],
            })
            replace_replay_response(replay, "2", {
                "prose": "The A1 pillar is recorded in the changed assessment.",
                "cites": {
                    "pillars": ["A1"], "indicators": [],
                    "use_cases": [], "prerequisites": [],
                },
                "claims": [{
                    "text": "The A1 pillar is recorded in the changed assessment.",
                    "basis": "evidence",
                    "source_refs": ["pillar:A1:mean"],
                }],
                "figures": [],
            })
            resumed = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(replay), "--resume"],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            chapter = next(item for item in dar["chapters"] if str(item["n"]) == "1")
            self.assertEqual(
                chapter["prose"],
                "This chapter was regenerated from the changed assessment.")
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("1", manifest["chapters"]["reused"])
            self.assertIn("1", manifest["chapters"]["regenerated"])

    def test_committed_egypt_chapters_plus_deterministic_annex_pass_b1_to_b6(self):
        with tempfile.TemporaryDirectory(prefix="damm-dar-cli-") as td:
            run = Path(td) / "fixture"
            copy_reference_inputs(run)

            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--country", "Egypt", "--iso", "EGY", "--out", str(run),
                 "--replay", str(FROZEN_REPLAY)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(
                Path(f"{run}_dar_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "complete")
            self.assertTrue(manifest["reviewed"])
            self.assertFalse(manifest["model_ratified"])
            self.assertFalse(manifest["final"])
            self.assertIn("model ratified is not true",
                          manifest["publication_blockers"])
            self.assertEqual(manifest["review"],
                             {"inputs": True, "narrative": True})
            dar = json.loads(Path(f"{run}_dar.json").read_text(encoding="utf-8"))
            self.assertTrue(dar["reviewed"])
            self.assertFalse(dar["method_ratified"])
            self.assertFalse(dar["final"])
            self.assertTrue(dar["status"].startswith("Draft DAR"))
            rendered = Path(f"{run}_dar.html").read_text(encoding="utf-8")
            self.assertIn("Draft Digital Agriculture Roadmap", rendered)
            self.assertIn("Publication hold", rendered)
            self.assertIn("model ratified is not true", rendered)
            self.assertNotIn("Final Digital Agriculture Roadmap", rendered)
            self.assertEqual([check["id"] for check in manifest["qc"]],
                             ["B1", "B2", "B3", "B4", "B5", "B6"])
            self.assertTrue(all(check["ok"] for check in manifest["qc"]))


if __name__ == "__main__":
    unittest.main()
