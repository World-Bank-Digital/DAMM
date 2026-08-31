#!/usr/bin/env python3
"""Cost-free, fail-closed simulation for the canonical DAMM workflow.

The public interface deliberately accepts a scenario identifier, not a graph of test
doubles.  A scenario selects versioned fixture behavior while the harness retains the
real Stage 6 assembler and, for the happy path, the real eight-stage coordinator.
Simulation output is permanently marked as ineligible for staging acceptance.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
from typing import Any, Mapping
from unittest import mock
import zipfile

import investment_options as I
import run_workflow as W


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SCENARIO_DIR = HERE / "fixtures" / "simulation"
REPORT_SCHEMA = "damm.simulation-report/v1"
SCENARIO_SCHEMA = "damm.simulation-scenario/v1"
PROVENANCE_SCHEMA = W.SIMULATION_PROVENANCE_SCHEMA
SIMULATION_LABEL = W.SIMULATION_LABEL
REPORT_NAME = "simulation-report.json"
CODE_IDENTITY_SCHEMA = "damm.simulation-code-identity/v1"
PRODUCTION_CODE_FILES = {
    "gauntlet/loop-1/research_pipeline/investment_options.py": HERE / "investment_options.py",
    "gauntlet/loop-1/research_pipeline/run_workflow.py": HERE / "run_workflow.py",
    "gauntlet/loop-1/research_pipeline/vendors.py": HERE / "vendors.py",
    "model/DAMM-v1.7-model.json": REPO_ROOT / "model" / "DAMM-v1.7-model.json",
    "workflow/dar-workflow-v1.json": REPO_ROOT / "workflow" / "dar-workflow-v1.json",
}

_SENSITIVE_ENV_MARKERS = (
    "API_KEY",
    "DATABASE_URL",
    "POSTGRES",
    "NEON",
    "RENDER",
    "NETLIFY",
    "ARTIFACT_DELIVERY_SECRET",
    "DAR_KEY_SECRET",
    "BETTER_AUTH_SECRET",
)


class SimulationError(RuntimeError):
    """The requested simulation is unsafe, unknown, or malformed."""


class SimulationBoundaryError(SimulationError):
    """Simulated code attempted a forbidden live external operation."""


def _stable_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _stable_sha256(value: Any) -> str:
    return hashlib.sha256(_stable_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _code_identity() -> dict[str, Any]:
    files = {name: _file_sha256(path) for name, path in PRODUCTION_CODE_FILES.items()}
    return {
        "schema_version": CODE_IDENTITY_SCHEMA,
        "files": files,
        "aggregate_sha256": _stable_sha256(files),
    }


def _scenario_path(scenario_id: str) -> Path:
    if not isinstance(scenario_id, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{2,80}", scenario_id
    ):
        raise SimulationError("scenario_id is not a safe built-in identifier")
    path = SCENARIO_DIR / f"{scenario_id}.json"
    if not path.is_file():
        known = ", ".join(sorted(candidate.stem for candidate in SCENARIO_DIR.glob("*.json")))
        raise SimulationError(f"unknown simulation scenario {scenario_id!r}; choose {known}")
    return path


def _load_scenario(scenario_id: str) -> tuple[dict[str, Any], Path, str]:
    path = _scenario_path(scenario_id)
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SimulationError(f"invalid built-in scenario {scenario_id}: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != SCENARIO_SCHEMA:
        raise SimulationError(f"scenario {scenario_id} must use {SCENARIO_SCHEMA}")
    expected_top_level = {
        "schema_version",
        "scenario_id",
        "description",
        "kind",
        "default_country",
        "default_iso3",
        "default_profile",
        "profiles",
        "expected",
        "fixture",
    }
    if set(value) != expected_top_level:
        raise SimulationError(
            f"scenario {scenario_id} has unexpected or missing top-level fields"
        )
    if value.get("scenario_id") != scenario_id:
        raise SimulationError(f"scenario file identity does not match {scenario_id}")
    if value.get("kind") not in {"stage6_failure_reproduction", "eight_stage_happy"}:
        raise SimulationError(f"scenario {scenario_id} has an unsupported kind")
    profiles = value.get("profiles")
    if not isinstance(profiles, list) or not profiles or any(
        not isinstance(profile, str) for profile in profiles
    ):
        raise SimulationError(f"scenario {scenario_id} has no valid profiles")
    expected = value.get("expected")
    if not isinstance(expected, dict):
        raise SimulationError(f"scenario {scenario_id} has no expected outcome")
    required_expected = {
        "workflow_status",
        "failed_stage",
        "error_code",
        "fixture_call_count",
        "code_sha256",
    }
    if value["kind"] == "stage6_failure_reproduction":
        required_expected.add("step_id")
    if set(expected) != required_expected:
        raise SimulationError(
            f"scenario {scenario_id} expected outcome has unexpected or missing fields"
        )
    if expected["workflow_status"] not in {"complete", "failed"}:
        raise SimulationError(f"scenario {scenario_id} workflow_status is invalid")
    if (
        not isinstance(expected["fixture_call_count"], int)
        or isinstance(expected["fixture_call_count"], bool)
        or expected["fixture_call_count"] < 1
    ):
        raise SimulationError(f"scenario {scenario_id} fixture_call_count is invalid")
    if not isinstance(expected["code_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected["code_sha256"]
    ):
        raise SimulationError(f"scenario {scenario_id} code_sha256 is invalid")
    fixture = value.get("fixture")
    if not isinstance(fixture, dict):
        raise SimulationError(f"scenario {scenario_id} has no fixture controls")
    if value["kind"] == "stage6_failure_reproduction":
        if set(fixture) != {"evidence_batches", "failed_batch", "repair_lengths"}:
            raise SimulationError(f"scenario {scenario_id} failure fixture is malformed")
        if (
            not isinstance(fixture["evidence_batches"], int)
            or isinstance(fixture["evidence_batches"], bool)
            or fixture["evidence_batches"] < 2
            or not isinstance(fixture["failed_batch"], int)
            or isinstance(fixture["failed_batch"], bool)
            or not 1 <= fixture["failed_batch"] <= fixture["evidence_batches"]
            or not isinstance(fixture["repair_lengths"], list)
            or not fixture["repair_lengths"]
            or any(
                not isinstance(length, int)
                or isinstance(length, bool)
                or length < 0
                for length in fixture["repair_lengths"]
            )
        ):
            raise SimulationError(f"scenario {scenario_id} failure fixture is invalid")
    else:
        if set(fixture) != {"source_count_by_profile", "candidate_count"}:
            raise SimulationError(f"scenario {scenario_id} happy fixture is malformed")
        source_counts = fixture["source_count_by_profile"]
        if (
            not isinstance(source_counts, dict)
            or set(source_counts) != set(profiles)
            or any(
                not isinstance(count, int) or isinstance(count, bool) or count < 1
                for count in source_counts.values()
            )
            or not isinstance(fixture["candidate_count"], int)
            or isinstance(fixture["candidate_count"], bool)
            or fixture["candidate_count"] < 1
        ):
            raise SimulationError(f"scenario {scenario_id} happy fixture is invalid")
    return value, path, hashlib.sha256(raw).hexdigest()


def _normalise_launch(
    scenario: Mapping[str, Any],
    *,
    country: str | None,
    iso3: str | None,
    profile: str | None,
) -> tuple[str, str, str]:
    selected_country = " ".join(str(country or scenario.get("default_country") or "").split())
    selected_iso3 = str(iso3 or scenario.get("default_iso3") or "").strip().upper()
    selected_profile = str(profile or scenario.get("default_profile") or "").strip()
    if not selected_country:
        raise SimulationError("country cannot be empty")
    if not re.fullmatch(r"[A-Z]{3}", selected_iso3):
        raise SimulationError("iso3 must be exactly three letters")
    if selected_profile not in scenario["profiles"]:
        raise SimulationError(
            f"profile must be one of {', '.join(scenario['profiles'])}"
        )
    return selected_country, selected_iso3, selected_profile


def _provenance(
    scenario_id: str,
    scenario_sha256: str,
    code_sha256: str,
    profile: str,
) -> dict[str, Any]:
    return W.validate_simulation_provenance({
        "schema_version": PROVENANCE_SCHEMA,
        "label": SIMULATION_LABEL,
        "execution_kind": "simulation",
        "acceptance_eligible": False,
        "scenario_id": scenario_id,
        "scenario_sha256": scenario_sha256,
        "code_sha256": code_sha256,
        "profile": profile,
    })


@contextmanager
def _simulation_boundary(counters: dict[str, int]):
    """Remove live credentials and deny sockets for the duration of one simulation."""

    before = dict(os.environ)
    for key in list(os.environ):
        upper = key.upper()
        if any(marker in upper for marker in _SENSITIVE_ENV_MARKERS):
            os.environ.pop(key, None)
    os.environ["DAMM_EXECUTION_KIND"] = "simulation"
    os.environ["DAMM_ACCEPTANCE_ELIGIBLE"] = "false"

    def deny_network(*_args: Any, **_kwargs: Any):
        counters["network_attempts"] += 1
        raise SimulationBoundaryError("simulation attempted a live network connection")

    def deny_subprocess(*_args: Any, **_kwargs: Any):
        counters["subprocess_attempts"] += 1
        raise SimulationBoundaryError("simulation attempted to start a subprocess")

    def deny_database(*_args: Any, **_kwargs: Any):
        counters["database_attempts"] += 1
        raise SimulationBoundaryError("simulation attempted to open a database")

    try:
        with (
            mock.patch.object(socket.socket, "connect", deny_network),
            mock.patch.object(socket.socket, "connect_ex", deny_network),
            mock.patch.object(socket.socket, "send", deny_network),
            mock.patch.object(socket.socket, "sendall", deny_network),
            mock.patch.object(socket.socket, "sendto", deny_network),
            mock.patch.object(socket.socket, "sendmsg", deny_network),
            mock.patch.object(socket, "create_connection", deny_network),
            mock.patch.object(subprocess, "Popen", deny_subprocess),
            mock.patch.object(os, "system", deny_subprocess),
            mock.patch.object(os, "popen", deny_subprocess),
            mock.patch.object(os, "posix_spawn", deny_subprocess),
            mock.patch.object(os, "posix_spawnp", deny_subprocess),
            mock.patch.object(sqlite3, "connect", deny_database),
        ):
            yield
    finally:
        os.environ.clear()
        os.environ.update(before)


def _source(ref: str, index: int, *, characters: int = 180) -> dict[str, Any]:
    stem = f"Synthetic evidence {index} for deterministic simulation. "
    text = (stem * ((characters // len(stem)) + 2))[:characters]
    return {
        "ref": ref,
        "kind": "synthetic_country_finding",
        "title": f"Synthetic source {index}",
        "text": text,
        "source": f"fixture://source/{index}",
    }


def _candidate(index: int, source_ref: str) -> dict[str, Any]:
    return {
        "title": f"Synthetic investment option {index}",
        "problem": f"Synthetic evidence identifies interoperability gap {index}.",
        "recommendation_rationale": (
            f"A bounded appraisal of option {index} is useful for simulation only."
        ),
        "source_refs": [source_ref],
    }


def _option_body(source_ref: str, index: int) -> dict[str, Any]:
    return {
        "baseline": f"Synthetic baseline {index}; validation is required.",
        "counterfactual": "Agencies continue using fragmented systems.",
        "costs": {
            "currency": "USD",
            "base_year": 2026,
            "low": 100000.0 * index,
            "high": 150000.0 * index,
            "basis": "Synthetic planning range; not an estimate.",
            "source_refs": [source_ref],
        },
        "benefits": {
            "quantified": [],
            "qualitative": ["Synthetic reduction in duplicated processing."],
        },
        "horizon_years": 5,
        "discount_rate": 0.06,
        "npv_low": None,
        "npv_high": None,
        "bcr_low": None,
        "bcr_high": None,
        "sensitivity": [{
            "scenario": "Synthetic high-cost case",
            "changes": "Costs increase by 30 percent.",
            "result": "Revalidate scope before appraisal.",
        }],
        "distributional_effects": ["Test inclusion assumptions."],
        "climate_effects": ["Test climate-service assumptions."],
        "ai_and_data_risks": ["Test consent and model-bias controls."],
        "implementation_risks": ["Test institutional coordination."],
        "data_gaps": ["Replace all synthetic values before review."],
        "evidence_status": "Synthetic fixture; not evidence.",
    }


class _HappyFixtureLLM:
    """Deterministic JSON adapter at the real Stage 6 vendor-call boundary."""

    vendor = "fixture"
    model = "eight-stage-happy-v1"

    def __init__(self, candidate_count: int):
        self.calls: list[str] = []
        self.candidate_count = candidate_count

    def json_call(
        self,
        _system: str,
        user: str,
        _schema: Mapping[str, Any],
        _pass_name: str,
        max_tokens: int = 8000,
        detail: str = "",
    ) -> dict[str, Any]:
        del max_tokens
        self.calls.append(detail)
        if detail.startswith("investment candidate map batch "):
            return {
                "candidates": [
                    _candidate(index, "SRC-001")
                    for index in range(1, self.candidate_count + 1)
                ]
            }
        if detail == "investment candidate final register":
            serialized = user.split("SUPPORTED CANDIDATE BRIEFS:\n", 1)[1].split(
                "\n\nReturn", 1
            )[0]
            return {"candidates": json.loads(serialized)}
        if detail.startswith("investment appraisal INV-"):
            candidate = json.loads(
                user.split("CANDIDATE:\n", 1)[1].split(
                    "\n\nCURRENT APPRAISAL", 1
                )[0]
            )
            option_index = int(detail.split("INV-", 1)[1].split(" ", 1)[0])
            return {
                "option": _option_body(candidate["source_refs"][0], option_index)
            }
        if detail == "investment portfolio sequencing":
            return {
                "portfolio_sequencing": (
                    "Synthetic sequencing exercises governance before procurement."
                ),
                "cross_cutting_data_gaps": [
                    "Replace fixture costs and benefits with reviewed evidence."
                ],
            }
        raise AssertionError(f"unexpected fixture call: {detail}")


class _OverlengthFixtureLLM:
    """Reproduce the exact repair-length class observed in Nigeria batch 2/3."""

    vendor = "fixture"
    model = "nigeria-stage6-overlength-v1"

    def __init__(
        self,
        repair_lengths: list[int],
        *,
        evidence_batches: int,
        failed_batch: int,
    ):
        self.calls: list[str] = []
        self.repair_lengths = list(repair_lengths)
        self.evidence_batches = evidence_batches
        self.failed_batch = failed_batch
        self.observed_repair_lengths: list[int] = []

    @staticmethod
    def _overlong_batch(source_ref: str) -> list[dict[str, Any]]:
        candidates = [_candidate(index, source_ref) for index in range(1, 5)]
        candidates[0]["problem"] = "p" * 560
        candidates[0]["recommendation_rationale"] = "r" * 560
        candidates[1]["problem"] = "p" * 560
        candidates[1]["recommendation_rationale"] = "r" * 560
        candidates[2]["problem"] = "p" * 560
        candidates[2]["recommendation_rationale"] = "r" * 560
        candidates[3]["problem"] = "p" * 560
        return candidates

    def json_call(
        self,
        _system: str,
        _user: str,
        _schema: Mapping[str, Any],
        _pass_name: str,
        max_tokens: int = 8000,
        detail: str = "",
    ) -> dict[str, Any]:
        del max_tokens
        self.calls.append(detail)
        map_match = re.fullmatch(r"investment candidate map batch (\d+)/(\d+)", detail)
        if map_match:
            batch = int(map_match.group(1))
            total = int(map_match.group(2))
            if total != self.evidence_batches or batch > self.failed_batch:
                raise AssertionError(f"unexpected fixture call: {detail}")
            if batch < self.failed_batch:
                return {"candidates": [_candidate(batch, f"SRC-{batch:03d}")]}
            return {
                "candidates": self._overlong_batch(f"SRC-{self.failed_batch:03d}")
            }
        repair_detail = (
            f"investment candidate map batch {self.failed_batch}/"
            f"{self.evidence_batches} [local-length repair 1/1]"
        )
        if detail == repair_detail:
            keys = (
                "candidate-0.problem",
                "candidate-0.recommendation_rationale",
                "candidate-1.problem",
                "candidate-1.recommendation_rationale",
                "candidate-2.problem",
                "candidate-2.recommendation_rationale",
                "candidate-3.problem",
            )
            repairs = {
                key: chr(97 + index) * length
                for index, (key, length) in enumerate(zip(keys, self.repair_lengths))
            }
            self.observed_repair_lengths = [len(repairs[key]) for key in keys]
            return {"repairs": repairs}
        raise AssertionError(f"unexpected fixture call: {detail}")


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_stable_bytes(value) + b"\n")
    return path


def _synthetic_stage_handler(provenance: Mapping[str, Any]):
    def handler(context: W.StageContext) -> W.StageResult:
        artifacts: dict[str, Any] = {}
        for key in context.required_artifacts:
            if key == "stage_manifest":
                continue
            suffix = ".md" if key.endswith("report") else ".json"
            path = context.stage_dir / f"{key}{suffix}"
            if suffix == ".md":
                path.write_text(
                    f"# {SIMULATION_LABEL}\n\nSynthetic {context.stage_id} output.\n",
                    encoding="utf-8",
                )
            else:
                _write_json(path, {
                    "schema_version": "damm.synthetic-stage-artifact/v1",
                    "label": SIMULATION_LABEL,
                    "acceptance_eligible": False,
                    "stage_id": context.stage_id,
                    "artifact_key": key,
                    "country": context.country,
                    "iso3": context.iso3,
                    "simulation_provenance": provenance,
                })
            artifacts[key] = path
        return W.StageResult(artifacts=artifacts, spent_usd=0.0)

    return handler


def _stage6_handler(
    provenance: Mapping[str, Any], sources: list[dict[str, Any]], llm: _HappyFixtureLLM
):
    def handler(context: W.StageContext) -> W.StageResult:
        response = I.synthesize_appraisal(context.country, sources, llm)
        product = I.build_product(context.country, context.iso3, response, sources)
        product["simulation_notice"] = SIMULATION_LABEL
        product["simulation_provenance"] = dict(provenance)
        errors = I.validate_product(product)
        if errors:
            raise W.NonRetryableStageError("synthetic Stage 6 product: " + "; ".join(errors))

        data_path = _write_json(context.stage_dir / "investment-options.json", product)
        sources_path = _write_json(
            context.stage_dir / "source-inventory.json",
            {
                "schema_version": "damm.synthetic-source-inventory/v1",
                "label": SIMULATION_LABEL,
                "acceptance_eligible": False,
                "sources": product["source_inventory"],
                "simulation_provenance": provenance,
            },
        )
        markdown = f"> **{SIMULATION_LABEL}**\n\n" + I.render_markdown(product)
        markdown_path = context.stage_dir / "investment-options.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        html_path = context.stage_dir / "investment-options.html"
        html_path.write_text(
            I.render_html(markdown, f"{SIMULATION_LABEL}: Stage 6"), encoding="utf-8"
        )
        workbook_path = context.stage_dir / "cost-benefit.xlsx"
        I.write_workbook(product, workbook_path)
        try:
            from openpyxl import load_workbook

            workbook = load_workbook(workbook_path)
            notice = workbook.create_sheet("SIMULATED", 0)
            notice["A1"] = SIMULATION_LABEL
            notice["A2"] = "This workbook is not acceptance evidence."
            workbook.save(workbook_path)
        except ImportError as error:
            raise SimulationError("openpyxl is required for the happy simulation") from error

        return W.StageResult(
            artifacts={
                "investment_options_report": (markdown_path, html_path),
                "cost_benefit_workbook": workbook_path,
                "appraisal_data": data_path,
                "source_inventory": sources_path,
                "investment_options": data_path,
            },
            spent_usd=0.0,
        )

    return handler


def _stage8_handler(provenance: Mapping[str, Any]):
    def handler(context: W.StageContext) -> W.StageResult:
        directories: dict[str, Path] = {}
        for key in ("narrative_exports", "structured_exports", "source_inventory_exports"):
            directory = context.stage_dir / key
            directory.mkdir(parents=True, exist_ok=True)
            _write_json(directory / "SIMULATED.json", {
                "schema_version": "damm.synthetic-export/v1",
                "label": SIMULATION_LABEL,
                "acceptance_eligible": False,
                "artifact_key": key,
                "simulation_provenance": provenance,
            })
            directories[key] = directory

        package_manifest = _write_json(context.stage_dir / "package-manifest.json", {
            "schema_version": "damm.synthetic-package/v1",
            "label": SIMULATION_LABEL,
            "acceptance_eligible": False,
            "simulation_provenance": provenance,
            "members": sorted(directories),
        })
        bundle = context.stage_dir / "simulated-dar-package.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("SIMULATED-NOT-ACCEPTANCE-EVIDENCE.txt", SIMULATION_LABEL + "\n")
            archive.write(package_manifest, "package-manifest.json")
            for key, directory in sorted(directories.items()):
                archive.write(directory / "SIMULATED.json", f"{key}/SIMULATED.json")
        return W.StageResult(
            artifacts={
                **directories,
                "workflow_manifest": package_manifest,
                "complete_bundle": bundle,
            },
            spent_usd=0.0,
        )

    return handler


def _path_size(path: Path) -> int:
    if path.is_dir():
        return sum(candidate.stat().st_size for candidate in path.rglob("*") if candidate.is_file())
    return path.stat().st_size


def _manifest_artifacts(manifest: Mapping[str, Any], workspace: Path, output: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for stage in manifest.get("stages") or []:
        for artifact in stage.get("artifacts") or []:
            path = workspace / artifact["path"]
            records.append({
                "stage_id": stage["id"],
                "key": artifact["key"],
                "path": path.relative_to(output).as_posix(),
                "sha256": artifact["sha256"],
                "size_bytes": _path_size(path),
                "media_type": artifact["media_type"],
                "label": SIMULATION_LABEL,
            })
    return records


def _stage_summaries(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{
        "ordinal": stage["ordinal"],
        "stage_id": stage["id"],
        "status": stage["status"],
        "attempts": stage["attempts"],
        # Simulation spend is an integer-zero contract.  Keeping the JSON number
        # representation identical across Python and JavaScript makes the report
        # digest language-independent (``0`` rather than Python's ``0.0``).
        "spent_usd": 0 if stage["spent_usd"] == 0 else stage["spent_usd"],
    } for stage in manifest.get("stages") or []]


def _error_sha256(error_code: str | None, failed_stage: str | None, message: str | None) -> str | None:
    if not error_code and not failed_stage and not message:
        return None
    return _stable_sha256({
        "error_code": error_code,
        "failed_stage": failed_stage,
        "message": message,
    })


def _finish_report(report: dict[str, Any], output: Path) -> dict[str, Any]:
    report["report_sha256"] = _stable_sha256(report)
    _write_json(output / REPORT_NAME, report)
    return copy.deepcopy(report)


def _base_report(
    *,
    scenario_id: str,
    scenario_sha256: str,
    run_id: str,
    country: str,
    iso3: str,
    profile: str,
    code_identity: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "label": SIMULATION_LABEL,
        "execution_kind": "simulation",
        "acceptance_eligible": False,
        "scenario_id": scenario_id,
        "scenario_sha256": scenario_sha256,
        "code_identity": copy.deepcopy(dict(code_identity)),
        "run_id": run_id,
        "vendor": f"fixture/{scenario_id}",
        "country": country,
        "iso3": iso3,
        "profile": profile,
        "harness_verdict": "fail",
        "observed": {
            "workflow_status": "failed",
            "failed_stage": None,
            "error_code": None,
            "error_sha256": None,
        },
        "external_spend_usd": 0,
        "external_io": {
            "network_calls": 0,
            "database_writes": 0,
            "capabilities_minted": 0,
            "subprocess_calls": 0,
        },
        "fixture_call_count": 0,
        "stages": [],
        "artifacts": [],
        "assertions": [],
    }


def _simulate_overlength(
    scenario: Mapping[str, Any], report: dict[str, Any], output: Path
) -> dict[str, Any]:
    fixture = scenario["fixture"]
    repair_lengths = list(fixture["repair_lengths"])
    evidence_batches = int(fixture["evidence_batches"])
    failed_batch = int(fixture["failed_batch"])
    llm = _OverlengthFixtureLLM(
        repair_lengths,
        evidence_batches=evidence_batches,
        failed_batch=failed_batch,
    )
    sources = [
        _source(f"SRC-{index:03d}", index, characters=900)
        for index in range(1, evidence_batches + 1)
    ]
    limits = I.AppraisalLimits(
        evidence_batch_characters=1050,
        candidate_output_tokens=I.DEFAULT_APPRAISAL_LIMITS.candidate_output_tokens,
        option_output_tokens=I.DEFAULT_APPRAISAL_LIMITS.option_output_tokens,
        portfolio_output_tokens=I.DEFAULT_APPRAISAL_LIMITS.portfolio_output_tokens,
    )
    observed_batches = I.batch_evidence(sources, limits.evidence_batch_characters)
    failure: Exception | None = None
    try:
        I.synthesize_appraisal(report["country"], sources, llm, limits=limits)
    except Exception as error:  # the scenario verifies the exact typed failure below
        failure = error

    error_code = getattr(failure, "code", None) if failure is not None else None
    failed_stage = "investment_options" if failure is not None else None
    step_id = getattr(failure, "step_id", None) if failure is not None else None
    message = str(failure) if failure is not None else None
    report["observed"] = {
        "workflow_status": "failed" if failure is not None else "complete",
        "failed_stage": failed_stage,
        "error_code": error_code,
        "error_sha256": _error_sha256(error_code, failed_stage, message),
    }
    expected = scenario["expected"]
    checks = [
        ("real_stage6_typed_failure", isinstance(failure, I.AppraisalOutputInvalid), type(failure).__name__ if failure else "no failure"),
        ("expected_workflow_status", report["observed"]["workflow_status"] == expected["workflow_status"], report["observed"]["workflow_status"]),
        ("expected_failed_stage", failed_stage == expected["failed_stage"], str(failed_stage)),
        ("expected_error_code", error_code == expected["error_code"], str(error_code)),
        ("exact_failed_step", step_id == expected["step_id"], str(step_id)),
        ("declared_evidence_batches", len(observed_batches) == evidence_batches, str(len(observed_batches))),
        ("declared_failed_batch", step_id == f"candidate-map-{failed_batch:04d}-length-repair", str(failed_batch)),
        ("exact_repair_lengths", llm.observed_repair_lengths == repair_lengths, str(llm.observed_repair_lengths)),
        ("fixture_call_count", len(llm.calls) == expected["fixture_call_count"], str(len(llm.calls))),
        ("zero_external_spend", True, "$0.00"),
    ]
    report["assertions"] = [
        {"id": identifier, "ok": bool(ok), "detail": detail}
        for identifier, ok, detail in checks
    ]
    report["harness_verdict"] = "pass" if all(ok for _, ok, _ in checks) else "fail"
    report["fixture_call_count"] = len(llm.calls)
    report["stages"] = [
        {
            "ordinal": ordinal,
            "stage_id": stage_id,
            "status": "failed" if stage_id == "investment_options" else "not_run",
            "attempts": 1 if stage_id == "investment_options" else 0,
            "spent_usd": 0,
        }
        for ordinal, stage_id in enumerate(W.EXPECTED_STAGE_IDS, 1)
    ]
    reproduction = _write_json(output / "artifacts" / "stage6-reproduction.json", {
        "schema_version": "damm.stage6-reproduction/v1",
        "label": SIMULATION_LABEL,
        "acceptance_eligible": False,
        "scenario_id": report["scenario_id"],
        "run_id": report["run_id"],
        "vendor": report["vendor"],
        "code_identity": report["code_identity"],
        "observed_repair_lengths": llm.observed_repair_lengths,
        "fixture_calls": llm.calls,
        "observed": report["observed"],
    })
    report["artifacts"] = [{
        "stage_id": "investment_options",
        "key": "failure_reproduction",
        "path": reproduction.relative_to(output).as_posix(),
        "sha256": _file_sha256(reproduction),
        "size_bytes": reproduction.stat().st_size,
        "media_type": "application/json",
        "label": SIMULATION_LABEL,
    }]
    return report


def _simulate_happy(
    scenario: Mapping[str, Any],
    report: dict[str, Any],
    output: Path,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    count = int(scenario["fixture"]["source_count_by_profile"][report["profile"]])
    candidate_count = int(scenario["fixture"]["candidate_count"])
    sources = [_source(f"SRC-{index:03d}", index) for index in range(1, count + 1)]
    llm = _HappyFixtureLLM(candidate_count)
    synthetic = _synthetic_stage_handler(provenance)
    handlers = {stage_id: synthetic for stage_id in W.EXPECTED_STAGE_IDS}
    handlers["investment_options"] = _stage6_handler(provenance, sources, llm)
    handlers["export_package"] = _stage8_handler(provenance)
    workspace = output / "workflow"
    contract = W.load_contract(W.DEFAULT_CONTRACT_PATH)
    coordinator = W.WorkflowCoordinator(
        contract=contract,
        workspace=workspace,
        handlers=handlers,
        commands={},
        max_attempts=1,
        retry_delay_seconds=0,
        simulation_provenance=provenance,
    )
    manifest: dict[str, Any]
    caught: Exception | None = None
    try:
        manifest = coordinator.run(
            country=report["country"],
            iso3=report["iso3"],
        run_id=report["run_id"],
        ceiling_usd=None,
        vendor=report["vendor"],
        )
    except W.WorkflowRunFailed as error:
        manifest = error.manifest
        caught = error
    except Exception as error:
        manifest = getattr(coordinator, "_manifest", {})
        caught = error

    failure = manifest.get("failure") if isinstance(manifest, dict) else None
    failed_stage = manifest.get("current_stage") if manifest.get("status") == "failed" else None
    error_code = None
    error_message = None
    if isinstance(failure, dict):
        error_code = failure.get("type")
        error_message = failure.get("message")
    elif caught is not None:
        error_code = type(caught).__name__
        error_message = str(caught)
    report["observed"] = {
        "workflow_status": manifest.get("status") or "failed",
        "failed_stage": failed_stage,
        "error_code": error_code,
        "error_sha256": _error_sha256(error_code, failed_stage, error_message),
    }
    stages = manifest.get("stages") or []
    stage_manifests_marked = True
    for stage in stages:
        binding = next(
            (artifact for artifact in stage.get("artifacts") or [] if artifact.get("key") == "stage_manifest"),
            None,
        )
        if not binding:
            stage_manifests_marked = False
            continue
        value = json.loads((workspace / binding["path"]).read_text(encoding="utf-8"))
        stage_manifests_marked = stage_manifests_marked and value.get("simulation_provenance") == provenance

    expected_calls = int(scenario["expected"]["fixture_call_count"])
    expected = scenario["expected"]
    stage6_manifest = next(
        (stage for stage in stages if stage.get("id") == "investment_options"),
        None,
    )
    stage6_candidate_count = None
    if stage6_manifest:
        appraisal_binding = next(
            (
                artifact
                for artifact in stage6_manifest.get("artifacts") or []
                if artifact.get("key") == "appraisal_data"
            ),
            None,
        )
        if appraisal_binding:
            appraisal_product = json.loads(
                (workspace / appraisal_binding["path"]).read_text(encoding="utf-8")
            )
            stage6_candidate_count = len(appraisal_product.get("options") or [])
    checks = [
        ("real_eight_stage_coordinator", manifest.get("status") == "complete", str(manifest.get("status"))),
        ("expected_workflow_status", report["observed"]["workflow_status"] == expected["workflow_status"], report["observed"]["workflow_status"]),
        ("expected_failed_stage", failed_stage == expected["failed_stage"], str(failed_stage)),
        ("expected_error_code", error_code == expected["error_code"], str(error_code)),
        ("all_eight_stages_complete", len(stages) == 8 and all(stage.get("status") == "complete" for stage in stages), str(len(stages))),
        ("real_stage6_product", any(stage.get("id") == "investment_options" and stage.get("status") == "complete" for stage in stages), "investment_options"),
        ("declared_candidate_count", stage6_candidate_count == candidate_count, str(stage6_candidate_count)),
        ("fixture_call_count", len(llm.calls) == expected_calls, str(len(llm.calls))),
        ("zero_external_spend", manifest.get("spent_usd") == 0.0, str(manifest.get("spent_usd"))),
        ("root_provenance", manifest.get("simulation_provenance") == provenance, "bound"),
        ("stage_provenance", stage_manifests_marked, "bound" if stage_manifests_marked else "missing"),
    ]
    report["assertions"] = [
        {"id": identifier, "ok": bool(ok), "detail": detail}
        for identifier, ok, detail in checks
    ]
    report["harness_verdict"] = "pass" if all(ok for _, ok, _ in checks) else "fail"
    report["fixture_call_count"] = len(llm.calls)
    report["stages"] = _stage_summaries(manifest)
    report["artifacts"] = _manifest_artifacts(manifest, workspace, output)
    return report


def simulate_workflow(
    scenario_id: str,
    output_dir: str | os.PathLike[str],
    *,
    country: str | None = None,
    iso3: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Run one built-in cost-free scenario and return its hash-bound report."""

    scenario, _scenario_file, scenario_sha256 = _load_scenario(scenario_id)
    code_identity = _code_identity()
    if code_identity["aggregate_sha256"] != scenario["expected"]["code_sha256"]:
        raise SimulationError(
            "simulation production-code identity does not match the committed scenario"
        )
    selected_country, selected_iso3, selected_profile = _normalise_launch(
        scenario, country=country, iso3=iso3, profile=profile
    )
    output = Path(output_dir).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise SimulationError(f"simulation output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    identity = _stable_sha256({
        "scenario_sha256": scenario_sha256,
        "country": selected_country,
        "iso3": selected_iso3,
        "profile": selected_profile,
    })
    run_id = f"sim-{scenario_id[:32]}-{identity[:12]}"
    report = _base_report(
        scenario_id=scenario_id,
        scenario_sha256=scenario_sha256,
        run_id=run_id,
        country=selected_country,
        iso3=selected_iso3,
        profile=selected_profile,
        code_identity=code_identity,
    )
    provenance = _provenance(
        scenario_id,
        scenario_sha256,
        code_identity["aggregate_sha256"],
        selected_profile,
    )
    counters = {
        "network_attempts": 0,
        "subprocess_attempts": 0,
        "database_attempts": 0,
        "capabilities_minted": 0,
    }
    with _simulation_boundary(counters):
        if scenario["kind"] == "stage6_failure_reproduction":
            report = _simulate_overlength(scenario, report, output)
        else:
            report = _simulate_happy(scenario, report, output, provenance)

    external_attempts = (
        counters["network_attempts"]
        + counters["subprocess_attempts"]
        + counters["database_attempts"]
        + counters["capabilities_minted"]
    )
    if external_attempts:
        report["assertions"].append({
            "id": "no_external_io_attempts",
            "ok": False,
            "detail": str(external_attempts),
        })
        report["harness_verdict"] = "fail"
    report["external_io"] = {
        "network_calls": counters["network_attempts"],
        "database_writes": counters["database_attempts"],
        "capabilities_minted": counters["capabilities_minted"],
        "subprocess_calls": counters["subprocess_attempts"],
    }
    return _finish_report(report, output)


__all__ = [
    "REPORT_NAME",
    "SIMULATION_LABEL",
    "SimulationBoundaryError",
    "SimulationError",
    "simulate_workflow",
]
