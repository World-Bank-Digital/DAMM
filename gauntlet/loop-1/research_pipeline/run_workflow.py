#!/usr/bin/env python3
"""One-launch execution seam for the canonical DAR workflow.

The coordinator owns ordering, retries, immutable input snapshots, events, artifact
verification, and checkpoints.  Analytical work remains behind one of two injected
adapters per stage:

* ``CommandSpec`` executes one existing command and snapshots its declared outputs.
* a Python handler accepts ``StageContext`` and returns ``StageResult`` (or an artifact
  mapping). The CLI ships command bindings for all eight canonical stages; handlers are
  an extension seam, not a launch prerequisite.

There is deliberately no paused or awaiting-human transition.  A run either advances,
retries within its declared bound, completes, or fails terminally with a checkpoint.

CLI example::

    python3 run_workflow.py \
      --country Egypt --iso EGY --out ../EGY_2026_workflow --ceiling 500 \
      --resume

Handlers have the public signature ``handler(context: StageContext)``.  Every returned
artifact path is checked, copied under the workflow workspace when necessary, hashed,
and recorded before the stage can become complete.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
import uuid


HERE = Path(__file__).resolve().parent
LOOP1 = HERE.parent
REPO_ROOT = HERE.parents[2]
DEFAULT_CONTRACT_PATH = REPO_ROOT / "workflow" / "dar-workflow-v1.json"

WORKFLOW_RUN_SCHEMA = "damm.workflow-run/v1"
WORKFLOW_EVENT_SCHEMA = "damm.workflow-event/v1"
WORKFLOW_INPUT_SCHEMA = "damm.workflow-input-snapshot/v1"
WORKFLOW_STAGE_SCHEMA = "damm.workflow-stage/v1"
UPLOADS_SCHEMA = "damm.uploads-manifest/v1"
CHECKPOINT_BINDING_SCHEMA = "damm.legacy-namespace/v1"

EXPECTED_STAGE_IDS = (
    "damm_diagnostic",
    "country_research",
    "ai_digital_agriculture",
    "international_lessons",
    "strategic_foresight",
    "investment_options",
    "draft_dar",
    "export_package",
)
EXPECTED_STAGE_BUDGET_ALLOCATIONS = {
    "damm_diagnostic": 0.45,
    "country_research": 0.075,
    "ai_digital_agriculture": 0.10,
    "international_lessons": 0.075,
    "strategic_foresight": 0.10,
    "investment_options": 0.05,
    "draft_dar": 0.15,
    "export_package": 0.00,
}

# Bridge names consumed by the integrating DAR generator.  They are additional to the
# richer artifact vocabulary in the canonical contract and make the manifest a stable
# execution interface while product schemas evolve.
CANONICAL_STAGE_ARTIFACT_KEYS = {
    "damm_diagnostic": ("engine_input",),
    "ai_digital_agriculture": ("ai_assessment",),
    "international_lessons": ("scans",),
    "strategic_foresight": ("foresight",),
    "investment_options": ("investment_options",),
}

UPLOAD_KINDS = frozenset(
    {
        "country_context_documents",
        "ai_documents",
        "international_strategy_documents",
        "foresight_documents",
        "investment_documents",
    }
)


class WorkflowError(RuntimeError):
    """Base class for coordinator failures."""


class WorkflowContractError(WorkflowError):
    """The canonical contract does not satisfy the executable invariants."""


class WorkflowConfigurationError(WorkflowError):
    """The launch or execution bindings are invalid."""


class RetryableStageError(WorkflowError):
    """A stage failed in a way that may succeed within the bounded retry policy."""


class MissingRequiredArtifacts(RetryableStageError):
    """A stage returned a partial product eligible for bounded automatic retry."""


class WorkflowRunFailed(WorkflowError):
    """A started workflow reached the terminal failed state."""

    def __init__(self, message: str, manifest: Mapping[str, Any]):
        super().__init__(message)
        self.manifest = dict(manifest)


ArtifactPath = str | os.PathLike[str]
ArtifactValue = ArtifactPath | Sequence[ArtifactPath]
StageHandler = Callable[["StageContext"], "StageResult | Mapping[str, ArtifactValue]"]


@dataclass(frozen=True)
class StageResult:
    """Outputs reported by a Python handler or command adapter."""

    artifacts: Mapping[str, ArtifactValue]
    spent_usd: float | None = None


@dataclass(frozen=True)
class CommandSpec:
    """One subprocess invocation and the legacy files it is expected to produce."""

    argv: tuple[str, ...]
    artifacts: Mapping[str, ArtifactValue]
    cwd: Path = HERE
    env: Mapping[str, str] = field(default_factory=dict)
    spend_path: Path | None = None
    checkpoint_namespace: str | None = None


@dataclass(frozen=True)
class StageContext:
    """Stable public input passed to every declared Python stage handler."""

    run_id: str
    country: str
    iso3: str
    contract: Mapping[str, Any]
    stage: Mapping[str, Any]
    workspace: Path
    stage_dir: Path
    manifest_path: Path
    input_snapshot_path: Path
    uploads_manifest_path: Path | None
    ceiling_usd: float | None
    vendor: str | None
    attempt: int
    prior_stages: tuple[Mapping[str, Any], ...]

    @property
    def stage_id(self) -> str:
        return str(self.stage["id"])

    @property
    def ordinal(self) -> int:
        return int(self.stage["ordinal"])

    @property
    def required_artifacts(self) -> tuple[str, ...]:
        values = list(self.stage.get("required_artifacts") or [])
        values.extend(CANONICAL_STAGE_ARTIFACT_KEYS.get(self.stage_id, ()))
        return tuple(dict.fromkeys(str(value) for value in values))


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _contract_sha256(contract: Mapping[str, Any]) -> str:
    """Hash the normative file bytes when this is the canonical repository contract."""

    try:
        raw = DEFAULT_CONTRACT_PATH.read_bytes()
        if json.loads(raw) == contract:
            return _sha256_bytes(raw)
    except (OSError, json.JSONDecodeError):
        pass
    # Injected contracts still receive a deterministic identity for unit tests and
    # alternate deployments, but the production canonical contract is byte-bound.
    return _sha256_bytes(_stable_json_bytes(contract))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _directory_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for item in sorted(path.rglob("*"), key=lambda candidate: candidate.as_posix()):
        if item.is_symlink():
            raise WorkflowConfigurationError(
                f"artifact directory contains a symbolic link: {item}"
            )
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        file_hash = bytes.fromhex(_file_sha256(item))
        digest.update(file_hash)
        size += item.stat().st_size
    return digest.hexdigest(), size


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_bytes(path, _stable_json_bytes(value) + b"\n")


def _utc_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_contract(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate executable invariants beyond what a generic JSON Schema can express."""

    stages = contract.get("stages")
    if not isinstance(stages, list) or len(stages) != 8:
        raise WorkflowContractError("canonical workflow must contain exactly eight stages")
    stage_ids = tuple(stage.get("id") for stage in stages)
    if stage_ids != EXPECTED_STAGE_IDS:
        raise WorkflowContractError(
            "canonical stage order must be " + ", ".join(EXPECTED_STAGE_IDS)
        )
    if [stage.get("ordinal") for stage in stages] != list(range(1, 9)):
        raise WorkflowContractError("canonical stage ordinals must be exactly 1 through 8")

    positions = {stage_id: index for index, stage_id in enumerate(stage_ids)}
    for stage in stages:
        stage_id = str(stage["id"])
        if stage.get("human_input_required") is not False:
            raise WorkflowContractError(f"{stage_id} requires human input")
        required = stage.get("required_artifacts")
        if not isinstance(required, list) or not required or any(
            not isinstance(item, str) or not item.strip() for item in required
        ):
            raise WorkflowContractError(f"{stage_id} has no valid required_artifacts")
        if len(required) != len(set(required)):
            raise WorkflowContractError(f"{stage_id} repeats a required artifact")
        dependencies = stage.get("depends_on")
        if not isinstance(dependencies, list):
            raise WorkflowContractError(f"{stage_id} depends_on must be an array")
        for dependency in dependencies:
            if dependency not in positions or positions[dependency] >= positions[stage_id]:
                raise WorkflowContractError(
                    f"{stage_id} has an unresolved or forward dependency {dependency}"
                )

    policy = contract.get("execution_policy") or {}
    if policy.get("required_human_actions_during_run") != []:
        raise WorkflowContractError("active workflow must require zero human actions")
    if policy.get("budget_policy") != (
        "preauthorized_ceiling_with_fixed_protected_allocations"
    ):
        raise WorkflowContractError("workflow budget policy is not canonical")
    if policy.get("fixed_stage_budget_allocations") != (
        EXPECTED_STAGE_BUDGET_ALLOCATIONS
    ):
        raise WorkflowContractError(
            "workflow fixed stage budget allocations are not canonical"
        )
    active_states = set(policy.get("allowed_active_states") or [])
    if active_states & {"paused", "awaiting_human", "awaiting_budget"}:
        raise WorkflowContractError("active workflow exposes a human-wait state")
    if policy.get("post_completion_review_only") is not True:
        raise WorkflowContractError("human review must be post-completion only")
    return contract


def load_contract(path: str | os.PathLike[str] = DEFAULT_CONTRACT_PATH) -> Mapping[str, Any]:
    contract_path = Path(path)
    try:
        value = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowContractError(f"cannot read workflow contract {contract_path}: {error}") from error
    if not isinstance(value, dict):
        raise WorkflowContractError("workflow contract root must be an object")
    return validate_contract(value)


def _legacy_paths(legacy_out: str) -> dict[str, Path]:
    return {
        "research": LOOP1 / f"{legacy_out}_research.json",
        "engine_input": LOOP1 / f"{legacy_out}_g2_input.json",
        "g2": LOOP1 / f"{legacy_out}_g2_findings.json",
        "scored": LOOP1 / f"{legacy_out}_v17.json",
        "diagnostic": LOOP1 / f"{legacy_out}_diagnostic.html",
        "diagnostic_sources": LOOP1 / f"{legacy_out}_diagnostic_sources.json",
        "diagnostic_stage_spend": LOOP1 / f"{legacy_out}_diagnostic_stage_spend.json",
        "scans": LOOP1 / f"{legacy_out}_scans.json",
        "foresight_json": LOOP1 / f"{legacy_out}_foresight.json",
        "foresight_html": LOOP1 / f"{legacy_out}_foresight.html",
        "foresight_sources": LOOP1 / f"{legacy_out}_foresight_sources.json",
        "ai_json": LOOP1 / f"{legacy_out}_ai_assessment.json",
        "ai_md": LOOP1 / f"{legacy_out}_ai_assessment.md",
        "ai_sources": LOOP1 / f"{legacy_out}_ai_sources.json",
        "investment_json": LOOP1 / f"{legacy_out}_investment_options.json",
        "investment_md": LOOP1 / f"{legacy_out}_investment_options.md",
        "investment_sources": LOOP1 / f"{legacy_out}_investment_sources.json",
        "cost_benefit": LOOP1 / f"{legacy_out}_cost_benefit.xlsx",
        "dar_json": LOOP1 / f"{legacy_out}_dar.json",
        "dar_html": LOOP1 / f"{legacy_out}_dar.html",
        "country_json": LOOP1 / f"{legacy_out}_country_research.json",
        "country_md": LOOP1 / f"{legacy_out}_country_research.md",
        "country_html": LOOP1 / f"{legacy_out}_country_research.html",
        "country_sources": LOOP1 / f"{legacy_out}_country_research_sources.json",
        "international_json": LOOP1 / f"{legacy_out}_international_lessons.json",
        "international_md": LOOP1 / f"{legacy_out}_international_lessons.md",
        "international_html": LOOP1 / f"{legacy_out}_international_lessons.html",
        "international_sources": LOOP1 / f"{legacy_out}_international_lessons_sources.json",
    }


def build_existing_stage_commands(
    *,
    country: str,
    iso3: str,
    legacy_out: str,
    ceiling_usd: float,
    vendor: str,
    workflow_version: str,
    python_executable: str = sys.executable,
) -> dict[str, CommandSpec]:
    """Map every canonical stage to its concrete pipeline executable.

    The legacy scans command currently contains both country and international lanes; it
    is therefore invoked with ``--resume`` for the international stage and its verified
    output is snapshotted under the separate canonical key.  Required artifact checking
    makes legacy incompleteness terminal rather than treating return code zero as proof.
    """

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", legacy_out):
        raise WorkflowConfigurationError("legacy_out must be a safe basename")
    paths = _legacy_paths(legacy_out)

    def command(script: str, *, extra: Sequence[str] = ()) -> tuple[str, ...]:
        return (
            python_executable,
            str(HERE / script),
            "--country",
            country,
            "--iso",
            iso3,
            "--out",
            legacy_out,
            "--ceiling",
            str(ceiling_usd),
            "--vendor",
            vendor,
            "--resume",
            *extra,
        )

    return {
        "damm_diagnostic": CommandSpec(
            argv=command("diagnostic_stage.py"),
            cwd=LOOP1,
            artifacts={
                "damm_observations": paths["research"],
                "automated_challenge": paths["g2"],
                "scored_assessment": paths["scored"],
                "diagnostic_report": paths["diagnostic"],
                "source_inventory": paths["diagnostic_sources"],
                "engine_input": paths["engine_input"],
            },
            spend_path=paths["diagnostic_stage_spend"],
            checkpoint_namespace=legacy_out,
        ),
        "country_research": CommandSpec(
            argv=command(
                "scan_stage.py",
                extra=("--lane", "country", "--uploads-manifest", "{uploads_manifest}"),
            ),
            cwd=LOOP1,
            artifacts={
                "country_research_report": (
                    paths["country_md"],
                    paths["country_html"],
                ),
                "country_evidence_data": paths["country_json"],
                "source_inventory": paths["country_sources"],
            },
            spend_path=LOOP1 / f"{legacy_out}_country_research_spend.json",
            checkpoint_namespace=legacy_out,
        ),
        "ai_digital_agriculture": CommandSpec(
            argv=command(
                "ai_assessment.py",
                extra=("--uploads-manifest", "{uploads_manifest}"),
            ),
            cwd=LOOP1,
            artifacts={
                "ai_assessment_report": paths["ai_md"],
                "ai_evidence_data": paths["ai_json"],
                "source_inventory": paths["ai_sources"],
                "ai_assessment": paths["ai_json"],
            },
            spend_path=LOOP1 / f"{legacy_out}_ai_spend.json",
            checkpoint_namespace=legacy_out,
        ),
        "international_lessons": CommandSpec(
            argv=command(
                "scan_stage.py",
                extra=(
                    "--lane",
                    "international",
                    "--uploads-manifest",
                    "{uploads_manifest}",
                ),
            ),
            cwd=LOOP1,
            artifacts={
                "international_lessons_report": (
                    paths["international_md"],
                    paths["international_html"],
                ),
                "strategy_comparison_data": paths["international_json"],
                "source_inventory": paths["international_sources"],
                "scans": paths["scans"],
            },
            spend_path=LOOP1 / f"{legacy_out}_international_lessons_spend.json",
            checkpoint_namespace=legacy_out,
        ),
        "strategic_foresight": CommandSpec(
            argv=command(
                "foresight.py",
                extra=("--uploads-manifest", "{uploads_manifest}"),
            ),
            cwd=LOOP1,
            artifacts={
                "foresight_report": paths["foresight_html"],
                "foresight_data": paths["foresight_json"],
                "source_inventory": paths["foresight_sources"],
                "foresight": paths["foresight_json"],
            },
            spend_path=LOOP1 / f"{legacy_out}_foresight_spend.json",
            checkpoint_namespace=legacy_out,
        ),
        "investment_options": CommandSpec(
            argv=command(
                "investment_options.py",
                extra=("--uploads-manifest", "{uploads_manifest}"),
            ),
            cwd=LOOP1,
            artifacts={
                "investment_options_report": paths["investment_md"],
                "cost_benefit_workbook": paths["cost_benefit"],
                "appraisal_data": paths["investment_json"],
                "source_inventory": paths["investment_sources"],
                "investment_options": paths["investment_json"],
            },
            spend_path=LOOP1 / f"{legacy_out}_investment_spend.json",
            checkpoint_namespace=legacy_out,
        ),
        "draft_dar": CommandSpec(
            argv=command(
                "generate_dar.py",
                extra=("--workflow-manifest", "{workflow_manifest}"),
            ),
            cwd=LOOP1,
            artifacts={
                "draft_dar_report": paths["dar_html"],
                "dar_source_data": paths["dar_json"],
                "claim_provenance": paths["dar_json"],
            },
            spend_path=LOOP1 / f"{legacy_out}_generation_spend.json",
            checkpoint_namespace=legacy_out,
        ),
        "export_package": CommandSpec(
            argv=(
                python_executable,
                str(HERE / "export_package.py"),
                "--country", country,
                "--iso", iso3,
                "--out", str(LOOP1 / legacy_out),
                "--workflow-manifest", "{workflow_manifest}",
                "--resume",
            ),
            cwd=LOOP1,
            artifacts={
                "narrative_exports": (
                    LOOP1 / f"{legacy_out}_dar_package_v{workflow_version}" / "narratives"
                ),
                "structured_exports": (
                    LOOP1 / f"{legacy_out}_dar_package_v{workflow_version}" / "structured"
                ),
                "source_inventory_exports": (
                    LOOP1 / f"{legacy_out}_dar_package_v{workflow_version}" / "source-inventory"
                ),
                "workflow_manifest": (
                    LOOP1 / f"{legacy_out}_dar_package_v{workflow_version}"
                    / "package-manifest.json"
                ),
                "complete_bundle": LOOP1 / f"{legacy_out}_dar_package.zip",
            },
            checkpoint_namespace=legacy_out,
        ),
    }


class WorkflowCoordinator:
    """Deterministic coordinator around injected stage execution adapters."""

    def __init__(
        self,
        *,
        contract: Mapping[str, Any],
        workspace: str | os.PathLike[str],
        handlers: Mapping[str, StageHandler] | None = None,
        commands: Mapping[str, CommandSpec] | None = None,
        event_sink: Callable[[Mapping[str, Any]], None] | None = None,
        command_runner: Callable[[CommandSpec, StageContext], Any] | None = None,
        max_attempts: int = 2,
        retry_delay_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.contract = validate_contract(contract)
        self.contract_sha256 = _contract_sha256(self.contract)
        self.workspace = Path(workspace).expanduser().resolve()
        self.handlers = dict(handlers or {})
        self.commands = dict(commands or {})
        self.event_sink = event_sink
        self.command_runner = command_runner or self._default_command_runner
        if not isinstance(max_attempts, int) or max_attempts < 1:
            raise WorkflowConfigurationError("max_attempts must be a positive integer")
        if retry_delay_seconds < 0:
            raise WorkflowConfigurationError("retry_delay_seconds cannot be negative")
        self.max_attempts = max_attempts
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.sleep = sleep
        self.clock = clock
        self.monotonic = monotonic
        self.manifest_path = self.workspace / "workflow-manifest.json"
        self.events_path = self.workspace / "workflow-events.jsonl"
        self._sequence = 0
        self._manifest: dict[str, Any] = {}

    def validate_execution_plan(self) -> None:
        expected = set(EXPECTED_STAGE_IDS)
        unknown = (set(self.handlers) | set(self.commands)) - expected
        if unknown:
            raise WorkflowConfigurationError(
                "execution mappings name unknown stages: " + ", ".join(sorted(unknown))
            )
        overlap = set(self.handlers) & set(self.commands)
        if overlap:
            raise WorkflowConfigurationError(
                "stages have both a command and a handler: " + ", ".join(sorted(overlap))
            )
        missing = expected - set(self.handlers) - set(self.commands)
        if missing:
            raise WorkflowConfigurationError(
                "no execution mapping for stages: " + ", ".join(sorted(missing))
            )
        bad_handlers = [stage_id for stage_id, handler in self.handlers.items() if not callable(handler)]
        if bad_handlers:
            raise WorkflowConfigurationError(
                "stage handlers are not callable: " + ", ".join(sorted(bad_handlers))
            )
        bad_commands = [
            stage_id
            for stage_id, command in self.commands.items()
            if not isinstance(command, CommandSpec) or not command.argv
        ]
        if bad_commands:
            raise WorkflowConfigurationError(
                "invalid command mappings: " + ", ".join(sorted(bad_commands))
            )

        namespaces = {
            (command.cwd.expanduser().resolve(), command.checkpoint_namespace)
            for command in self.commands.values()
            if command.checkpoint_namespace is not None
        }
        if len(namespaces) > 1:
            raise WorkflowConfigurationError(
                "canonical commands must share one checkpoint namespace"
            )
        for _directory, namespace in namespaces:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", str(namespace)):
                raise WorkflowConfigurationError("checkpoint namespace is not a safe basename")

    def _checkpoint_namespace(self) -> tuple[Path, str] | None:
        values = {
            (command.cwd.expanduser().resolve(), str(command.checkpoint_namespace))
            for command in self.commands.values()
            if command.checkpoint_namespace is not None
        }
        if not values:
            return None
        if len(values) != 1:
            raise WorkflowConfigurationError(
                "canonical commands must share one checkpoint namespace"
            )
        return next(iter(values))

    def _checkpoint_binding_payload(
        self,
        *,
        namespace: str,
        run_id: str,
        country: str,
        iso3: str,
        input_snapshot: Mapping[str, Any],
        uploads_record: Mapping[str, Any] | None,
        ceiling_usd: float | None,
        vendor: str | None,
    ) -> dict[str, Any]:
        return {
            "schema_version": CHECKPOINT_BINDING_SCHEMA,
            "namespace": namespace,
            "workspace_identity_sha256": _sha256_bytes(
                str(self.workspace).encode("utf-8")
            ),
            "run_id": run_id,
            "workflow_id": self.contract["workflow_id"],
            "workflow_version": self.contract["workflow_version"],
            "contract_sha256": self.contract_sha256,
            "input_snapshot_sha256": input_snapshot["sha256"],
            "uploads_manifest_sha256": (
                uploads_record.get("sha256") if uploads_record is not None else None
            ),
            "country": country,
            "iso3": iso3,
            "ceiling_usd": ceiling_usd,
            "vendor": vendor,
        }

    @staticmethod
    def _publish_exclusive(path: Path, payload: bytes) -> bool:
        """Publish complete bytes without replacing another workflow's claim."""
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, path)
                return True
            except FileExistsError:
                return False
        finally:
            if temporary.exists():
                temporary.unlink()

    def _claim_checkpoint_namespace(
        self,
        *,
        run_id: str,
        country: str,
        iso3: str,
        input_snapshot: Mapping[str, Any],
        uploads_record: Mapping[str, Any] | None,
        ceiling_usd: float | None,
        vendor: str | None,
    ) -> dict[str, Any] | None:
        namespace_spec = self._checkpoint_namespace()
        if namespace_spec is None:
            return None
        directory, namespace = namespace_spec
        directory.mkdir(parents=True, exist_ok=True)
        claim_path = directory / f"{namespace}_namespace.json"
        payload = self._checkpoint_binding_payload(
            namespace=namespace,
            run_id=run_id,
            country=country,
            iso3=iso3,
            input_snapshot=input_snapshot,
            uploads_record=uploads_record,
            ceiling_usd=ceiling_usd,
            vendor=vendor,
        )
        encoded = _stable_json_bytes(payload) + b"\n"
        collisions = []
        prefix = f"{namespace}_"
        for candidate in directory.iterdir():
            if not candidate.name.startswith(prefix) or candidate == claim_path:
                continue
            try:
                if candidate.resolve() == self.workspace:
                    continue
            except OSError:
                pass
            collisions.append(candidate.name)
        if claim_path.exists():
            try:
                existing = claim_path.read_bytes()
            except OSError as error:
                raise WorkflowConfigurationError(
                    f"cannot read checkpoint namespace claim {claim_path}: {error}"
                ) from error
            if existing != encoded:
                raise WorkflowConfigurationError(
                    f"checkpoint namespace {namespace} is claimed by another run or input"
                )
            if collisions:
                raise WorkflowConfigurationError(
                    f"checkpoint namespace {namespace} already contains state without a "
                    "resumable workflow manifest"
                )
        else:
            if collisions:
                preview = ", ".join(sorted(collisions)[:5])
                raise WorkflowConfigurationError(
                    f"checkpoint namespace {namespace} contains unbound legacy state: {preview}"
                )
            if not self._publish_exclusive(claim_path, encoded):
                try:
                    existing = claim_path.read_bytes()
                except OSError as error:
                    raise WorkflowConfigurationError(
                        f"checkpoint namespace {namespace} was claimed concurrently"
                    ) from error
                if existing != encoded:
                    raise WorkflowConfigurationError(
                        f"checkpoint namespace {namespace} was claimed concurrently"
                    )

        workspace_path = self.workspace / "inputs" / "checkpoint-binding.json"
        _atomic_write_bytes(workspace_path, encoded)
        return {
            "path": workspace_path.relative_to(self.workspace).as_posix(),
            "sha256": _sha256_bytes(encoded),
            "namespace": namespace,
        }

    def _verify_checkpoint_namespace(
        self,
        record: Any,
        *,
        run_id: str,
        country: str,
        iso3: str,
        input_snapshot: Mapping[str, Any],
        uploads_record: Mapping[str, Any] | None,
        ceiling_usd: float | None,
        vendor: str | None,
    ) -> None:
        namespace_spec = self._checkpoint_namespace()
        if namespace_spec is None:
            if record is not None:
                raise WorkflowConfigurationError(
                    "resume execution plan removed the checkpoint namespace"
                )
            return
        directory, namespace = namespace_spec
        if not isinstance(record, dict) or record.get("namespace") != namespace:
            raise WorkflowConfigurationError(
                "resume checkpoint has no matching checkpoint namespace binding"
            )
        self._verify_recorded_artifact(record, "checkpoint_binding")
        expected = self._checkpoint_binding_payload(
            namespace=namespace,
            run_id=run_id,
            country=country,
            iso3=iso3,
            input_snapshot=input_snapshot,
            uploads_record=uploads_record,
            ceiling_usd=ceiling_usd,
            vendor=vendor,
        )
        workspace_path = self._resolve_workspace_record_path(
            record.get("path"), "checkpoint_binding"
        )
        try:
            workspace_value = json.loads(workspace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkflowConfigurationError(
                f"invalid checkpoint namespace binding: {error}"
            ) from error
        if workspace_value != expected:
            raise WorkflowConfigurationError(
                "checkpoint namespace binding does not match the canonical run input"
            )
        claim_path = directory / f"{namespace}_namespace.json"
        try:
            claim_bytes = claim_path.read_bytes()
        except OSError as error:
            raise WorkflowConfigurationError(
                f"checkpoint namespace claim is missing: {claim_path}"
            ) from error
        if claim_bytes != workspace_path.read_bytes():
            raise WorkflowConfigurationError(
                "checkpoint namespace claim differs from the workflow binding"
            )

    def _default_command_runner(self, spec: CommandSpec, context: StageContext) -> Any:
        replacements = {
            "{workflow_manifest}": str(context.manifest_path),
            "{workspace}": str(context.workspace),
            "{stage_dir}": str(context.stage_dir),
            "{input_snapshot}": str(context.input_snapshot_path),
            "{uploads_manifest}": str(context.uploads_manifest_path or ""),
        }
        argv = [replacements.get(token, token) for token in spec.argv]
        environment = os.environ.copy()
        environment.update(spec.env)
        environment["DAMM_WORKFLOW_WORKSPACE"] = str(context.workspace)
        uploads_record = self._manifest.get("uploads_manifest")
        if isinstance(uploads_record, dict):
            environment["DAMM_UPLOADS_MANIFEST_SHA256"] = str(
                uploads_record.get("sha256") or ""
            )
        checkpoint_binding = self._manifest.get("checkpoint_binding")
        if isinstance(checkpoint_binding, dict):
            binding_path = self._resolve_workspace_record_path(
                checkpoint_binding.get("path"), "checkpoint_binding"
            )
            environment["DAMM_CHECKPOINT_BINDING_PATH"] = str(binding_path)
            environment["DAMM_CHECKPOINT_BINDING_SHA256"] = str(
                checkpoint_binding.get("sha256") or ""
            )
        return subprocess.run(
            argv,
            cwd=str(spec.cwd),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def _stage_record(self, stage_id: str) -> dict[str, Any]:
        for record in self._manifest["stages"]:
            if record["id"] == stage_id:
                return record
        raise WorkflowContractError(f"manifest has no stage {stage_id}")

    def _checkpoint(self) -> None:
        self._manifest["updated_at"] = _utc_now(self.clock)
        _atomic_write_json(self.manifest_path, self._manifest)

    def _emit(self, event: str, **fields: Any) -> dict[str, Any]:
        self._sequence += 1
        payload = {
            "schema_version": WORKFLOW_EVENT_SCHEMA,
            "sequence": self._sequence,
            "event": event,
            "timestamp": _utc_now(self.clock),
            "run_id": self._manifest["run_id"],
            "workflow_id": self._manifest["workflow_id"],
            "workflow_version": self._manifest["workflow_version"],
            **fields,
        }
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            stream.write("\n")
            stream.flush()
        if self.event_sink is not None:
            self.event_sink(payload)
        return payload

    def _freeze_uploads_manifest(
        self, uploads_manifest: str | os.PathLike[str] | None
    ) -> tuple[dict[str, Any] | None, Path | None]:
        if uploads_manifest is None:
            return None, None
        source = Path(uploads_manifest).expanduser().resolve()
        try:
            raw = source.read_bytes()
            envelope = json.loads(raw)
        except (OSError, json.JSONDecodeError) as error:
            raise WorkflowConfigurationError(f"invalid uploads manifest {source}: {error}") from error
        if not isinstance(envelope, dict) or envelope.get("schema_version") != UPLOADS_SCHEMA:
            raise WorkflowConfigurationError(
                f"uploads manifest must be a {UPLOADS_SCHEMA} object"
            )
        documents = self._verify_upload_documents(envelope)
        frozen = self.workspace / "inputs" / "uploads-manifest.json"
        _atomic_write_bytes(frozen, raw)
        return (
            {
                "path": frozen.relative_to(self.workspace).as_posix(),
                "sha256": _sha256_bytes(raw),
                "document_count": len(documents),
            },
            frozen,
        )

    def _verified_workspace_upload_path(
        self, value: Any, label: str, required_parent: str
    ) -> Path:
        root = self.workspace.resolve()
        relative = Path(str(value or ""))
        if (
            not str(value or "").strip()
            or relative.is_absolute()
            or ".." in relative.parts
            or tuple(relative.parts[:2]) != ("inputs", required_parent)
        ):
            raise WorkflowConfigurationError(
                f"{label} must be a workspace-relative inputs/{required_parent}/ path"
            )
        unresolved = root / relative
        try:
            resolved = unresolved.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as error:
            raise WorkflowConfigurationError(
                f"{label} is missing or escapes the workspace"
            ) from error
        if unresolved.is_symlink() or resolved != unresolved.absolute():
            raise WorkflowConfigurationError(f"{label} may not traverse a symbolic link")
        if not resolved.is_file():
            raise WorkflowConfigurationError(f"{label} is not a regular file")
        return resolved

    def _verify_upload_documents(self, envelope: Any) -> list[dict[str, Any]]:
        if not isinstance(envelope, dict) or envelope.get("schema_version") != UPLOADS_SCHEMA:
            raise WorkflowConfigurationError(
                f"uploads manifest must be a {UPLOADS_SCHEMA} object"
            )
        documents = envelope.get("documents")
        if not isinstance(documents, list):
            raise WorkflowConfigurationError("uploads manifest documents must be an array")
        seen: set[str] = set()
        seen_paths: set[str] = set()
        for index, document in enumerate(documents):
            label = f"uploads manifest document {index + 1}"
            if not isinstance(document, dict):
                raise WorkflowConfigurationError(f"{label} must be an object")
            required = (
                "id",
                "kind",
                "original_filename",
                "content_path",
                "content_sha256",
                "content_media_type",
                "original_path",
                "original_sha256",
            )
            missing = [key for key in required if not str(document.get(key) or "").strip()]
            if missing:
                raise WorkflowConfigurationError(
                    f"{label} is missing " + ", ".join(missing)
                )
            document_id = str(document["id"])
            if document_id in seen:
                raise WorkflowConfigurationError(f"duplicate upload id {document_id}")
            seen.add(document_id)
            if document["kind"] not in UPLOAD_KINDS:
                raise WorkflowConfigurationError(
                    f"{label} has unsupported kind {document['kind']}"
                )
            content = self._verified_workspace_upload_path(
                document["content_path"], f"{label} content_path", "upload-content"
            )
            original = self._verified_workspace_upload_path(
                document["original_path"], f"{label} original_path", "upload-originals"
            )
            for path_field in ("content_path", "original_path"):
                portable_path = Path(str(document[path_field])).as_posix()
                if portable_path in seen_paths:
                    raise WorkflowConfigurationError(
                        f"uploads manifest duplicates input path {portable_path}"
                    )
                seen_paths.add(portable_path)
            declared_hash = str(document["content_sha256"])
            if not re.fullmatch(r"[0-9a-f]{64}", declared_hash):
                raise WorkflowConfigurationError(f"{label} content_sha256 is not lowercase SHA-256")
            actual_hash = _file_sha256(content)
            if actual_hash != declared_hash:
                raise WorkflowConfigurationError(
                    f"{label} content hash mismatch: expected {declared_hash}, got {actual_hash}"
                )
            if str(document["content_media_type"]).split(";", 1)[0].strip() != "text/plain":
                raise WorkflowConfigurationError(
                    f"{label} content_media_type must be text/plain"
                )
            original_hash = str(document["original_sha256"])
            if not re.fullmatch(r"[0-9a-f]{64}", original_hash):
                raise WorkflowConfigurationError(
                    f"{label} original_sha256 is not lowercase SHA-256"
                )
            actual_original_hash = _file_sha256(original)
            if actual_original_hash != original_hash:
                raise WorkflowConfigurationError(
                    f"{label} original hash mismatch: expected {original_hash}, "
                    f"got {actual_original_hash}"
                )
            original_size = document.get("original_size_bytes")
            if (
                isinstance(original_size, bool)
                or not isinstance(original_size, int)
                or original_size < 0
                or original.stat().st_size != original_size
            ):
                raise WorkflowConfigurationError(
                    f"{label} original_size_bytes does not match the original file"
                )
            metadata = document.get("metadata")
            if not isinstance(metadata, dict):
                raise WorkflowConfigurationError(f"{label} metadata must be an object")
            metadata_required = (
                "extracted_characters",
                "app_upload_kind",
                "source_mime_type",
                "uploaded_at",
                "uploaded_by",
                "extraction_status",
            )
            metadata_missing = [
                key for key in metadata_required
                if key not in metadata or metadata.get(key) in (None, "")
            ]
            if metadata_missing:
                raise WorkflowConfigurationError(
                    f"{label} metadata is missing " + ", ".join(metadata_missing)
                )
            if metadata.get("app_upload_kind") != document["kind"]:
                raise WorkflowConfigurationError(
                    f"{label} metadata.app_upload_kind does not match kind"
                )
            if metadata.get("extraction_status") != "extracted":
                raise WorkflowConfigurationError(
                    f"{label} extraction_status is not extracted"
                )
            try:
                extracted_text = content.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise WorkflowConfigurationError(
                    f"{label} extracted content is not UTF-8 text"
                ) from error
            extracted_characters = metadata.get("extracted_characters")
            if (
                isinstance(extracted_characters, bool)
                or not isinstance(extracted_characters, int)
                or extracted_characters != len(extracted_text)
            ):
                raise WorkflowConfigurationError(
                    f"{label} metadata.extracted_characters does not match content"
                )
        return documents

    def _create_input_snapshot(
        self,
        *,
        country: str,
        iso3: str,
        uploads_record: Mapping[str, Any] | None,
        ceiling_usd: float | None,
        vendor: str | None,
    ) -> tuple[dict[str, str], Path]:
        snapshot = {
            "schema_version": WORKFLOW_INPUT_SCHEMA,
            "country": country,
            "iso3": iso3,
            "contract_sha256": self.contract_sha256,
            "uploads_manifest": uploads_record,
            "ceiling_usd": ceiling_usd,
            "vendor": vendor,
        }
        path = self.workspace / "inputs" / "input-snapshot.json"
        payload = _stable_json_bytes(snapshot) + b"\n"
        _atomic_write_bytes(path, payload)
        return {
            "path": path.relative_to(self.workspace).as_posix(),
            "sha256": _sha256_bytes(payload),
        }, path

    @staticmethod
    def _reported_spend_from(path: Path | None) -> float | None:
        if path is None or not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            amount = float((value.get("summary") or {}).get("total"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        return amount if math.isfinite(amount) and amount >= 0 else None

    def _refresh_command_spend(self, stage_id: str, record: dict[str, Any]) -> float | None:
        """Capture the cumulative ledger after every attempt, including failures."""
        spec = self.commands.get(stage_id)
        if spec is None or spec.spend_path is None:
            return None
        amount = self._reported_spend_from(spec.spend_path)
        if amount is None:
            return None
        prior = record.get("_spent_usd")
        if prior is not None and amount + 1e-9 < float(prior):
            raise WorkflowConfigurationError(
                f"{stage_id} spend ledger decreased from {prior} to {amount}"
            )
        record["_spent_usd"] = amount
        record["spent_usd"] = amount
        authoritative, reported = self._spend_totals()
        self._manifest["spent_usd"] = authoritative
        self._manifest["reported_spent_usd"] = reported
        self._enforce_stage_budget(stage_id, amount)
        return amount

    def _enforce_stage_budget(self, stage_id: str, amount: float) -> None:
        """Reject a ledger that spent another stage's protected launch allocation."""

        ceiling = self._manifest.get("ceiling_usd")
        if ceiling is None:
            return
        share = self.contract["execution_policy"][
            "fixed_stage_budget_allocations"
        ][stage_id]
        cap = float(ceiling) * float(share)
        if amount > cap + 1e-9:
            raise WorkflowConfigurationError(
                f"{stage_id} spend ${amount:.6f} exceeds its protected "
                f"allocation ${cap:.6f}"
            )

    def _execute_binding(self, context: StageContext) -> tuple[StageResult, str]:
        if context.stage_id in self.handlers:
            result = self.handlers[context.stage_id](context)
            if isinstance(result, Mapping):
                result = StageResult(artifacts=result)
            if not isinstance(result, StageResult):
                raise WorkflowConfigurationError(
                    f"handler for {context.stage_id} did not return StageResult or an artifact mapping"
                )
            return result, "handler"

        spec = self.commands[context.stage_id]
        completed = self.command_runner(spec, context)
        return_code = getattr(completed, "returncode", None)
        if return_code != 0:
            stdout = str(getattr(completed, "stdout", "") or "")
            stderr = str(getattr(completed, "stderr", "") or "")
            detail = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
            if len(detail) > 1200:
                detail = detail[-1200:]
            raise RetryableStageError(
                f"command for {context.stage_id} exited {return_code}"
                + (f": {detail}" if detail else "")
            )
        reported_spend = (
            self._reported_spend_from(spec.spend_path)
            if spec.spend_path is not None
            else 0.0
        )
        if spec.spend_path is not None and reported_spend is None:
            raise RetryableStageError(
                f"command for {context.stage_id} did not write a valid spend ledger"
            )
        self._enforce_stage_budget(context.stage_id, float(reported_spend))
        return (
            StageResult(
                artifacts=spec.artifacts,
                # A command without a ledger is a deliberately no-call/shared-ledger
                # stage.  Record an auditable zero instead of an ambiguous null.
                spent_usd=reported_spend,
            ),
            "command",
        )

    @staticmethod
    def _artifact_values(value: ArtifactValue) -> list[Path]:
        if isinstance(value, (str, os.PathLike)):
            return [Path(value)]
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            paths = []
            for item in value:
                if not isinstance(item, (str, os.PathLike)):
                    raise WorkflowConfigurationError("artifact lists may contain only paths")
                paths.append(Path(item))
            return paths
        raise WorkflowConfigurationError("artifact value must be a path or an array of paths")

    @staticmethod
    def _media_type(path: Path) -> str:
        if path.is_dir():
            return "application/x-directory"
        explicit = {
            ".md": "text/markdown",
            ".json": "application/json",
            ".jsonl": "application/x-ndjson",
            ".csv": "text/csv",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
            ".html": "text/html",
            ".zip": "application/zip",
        }
        return explicit.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    def _snapshot_path(self, source: Path, logical_key: str, context: StageContext) -> Path:
        candidate = source if source.is_absolute() else context.stage_dir / source
        candidate = candidate.expanduser().resolve()
        if not candidate.exists():
            raise MissingRequiredArtifacts(
                f"{context.stage_id} artifact {logical_key} does not exist: {candidate}"
            )
        try:
            candidate.relative_to(self.workspace)
            return candidate
        except ValueError:
            destination_dir = context.stage_dir / "artifacts" / logical_key
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / (candidate.name or "artifact")
            suffix = 2
            while destination.exists():
                destination = destination_dir / f"{candidate.stem}-{suffix}{candidate.suffix}"
                suffix += 1
            if candidate.is_dir():
                shutil.copytree(candidate, destination)
            else:
                shutil.copy2(candidate, destination)
            return destination.resolve()

    def _artifact_record(self, logical_key: str, path: Path) -> dict[str, Any]:
        if path.is_dir():
            digest, _size = _directory_digest(path)
        else:
            digest = _file_sha256(path)
        return {
            "key": logical_key,
            "path": path.relative_to(self.workspace).as_posix(),
            "sha256": digest,
            "media_type": self._media_type(path),
        }

    def _collect_artifacts(
        self, result: StageResult, context: StageContext, execution_mode: str
    ) -> list[dict[str, Any]]:
        if result.spent_usd is not None and (
            not isinstance(result.spent_usd, (int, float))
            or not math.isfinite(float(result.spent_usd))
            or result.spent_usd < 0
        ):
            raise WorkflowConfigurationError(
                f"{context.stage_id} reported invalid spent_usd"
            )
        if "stage_manifest" in result.artifacts:
            raise WorkflowConfigurationError(
                "stage_manifest is coordinator-owned and must not be returned by a handler"
            )

        records: list[dict[str, Any]] = []
        populated: set[str] = set()
        for logical_key, value in result.artifacts.items():
            if not isinstance(logical_key, str) or not logical_key.strip():
                raise WorkflowConfigurationError("artifact keys must be nonempty strings")
            paths = self._artifact_values(value)
            if not paths:
                continue
            for source in paths:
                snapshotted = self._snapshot_path(source, logical_key, context)
                records.append(self._artifact_record(logical_key, snapshotted))
            populated.add(logical_key)

        required = set(context.required_artifacts) - {"stage_manifest"}
        missing = sorted(required - populated)
        if missing:
            raise MissingRequiredArtifacts(
                f"{context.stage_id} is missing required artifacts: " + ", ".join(missing)
            )

        spend_usd = float(result.spent_usd) if result.spent_usd is not None else 0.0
        output_hashes: dict[str, str | list[str]] = {}
        for record in records:
            key = str(record["key"])
            digest = str(record["sha256"])
            prior = output_hashes.get(key)
            if prior is None:
                output_hashes[key] = digest
            elif isinstance(prior, list):
                prior.append(digest)
            else:
                output_hashes[key] = [prior, digest]

        upstream_manifests: dict[str, str] = {}
        for prior_stage in self._manifest["stages"]:
            if prior_stage["status"] != "complete":
                continue
            binding = next(
                (
                    artifact
                    for artifact in prior_stage.get("artifacts", [])
                    if artifact.get("key") == "stage_manifest"
                ),
                None,
            )
            if binding is not None:
                upstream_manifests[str(prior_stage["id"])] = str(binding["sha256"])

        source_records = [
            {"artifact_key": record["key"], "sha256": record["sha256"]}
            for record in records
            if record["key"] in {"source_inventory", "claim_provenance"}
        ]
        stage_manifest_path = context.stage_dir / "stage-manifest.json"
        stage_manifest = {
            "schema_version": WORKFLOW_STAGE_SCHEMA,
            "workflow_id": self.contract["workflow_id"],
            "workflow_version": self.contract["workflow_version"],
            "run_id": context.run_id,
            "stage_id": context.stage_id,
            "ordinal": context.ordinal,
            "attempt": context.attempt,
            "execution_mode": execution_mode,
            "input_snapshot": self._manifest["input_snapshot"],
            "input_hashes": {
                "input_snapshot": self._manifest["input_snapshot"]["sha256"],
                "checkpoint_binding": (
                    (self._manifest.get("checkpoint_binding") or {}).get("sha256")
                ),
                "upstream_stage_manifests": upstream_manifests,
            },
            "artifacts": records,
            "output_hashes": output_hashes,
            "source_inventory": source_records,
            "quality_checks": [
                {"id": "required_artifacts_present", "ok": True},
                {"id": "artifact_sha256_bound", "ok": True},
                {"id": "no_human_action_required", "ok": True},
            ],
            "spend_usd": spend_usd,
            "status": "complete",
        }
        _atomic_write_json(stage_manifest_path, stage_manifest)
        records.append(self._artifact_record("stage_manifest", stage_manifest_path))
        return records

    def _spend_totals(self) -> tuple[float | None, float]:
        reported_values = [
            record.get("_spent_usd") for record in self._manifest["stages"]
            if record.get("_spent_usd") is not None
        ]
        reported_total = round(
            sum(float(value) for value in reported_values), 8
        )
        return reported_total, reported_total

    def _public_manifest(self) -> dict[str, Any]:
        """Return a copy without coordinator-private bookkeeping fields."""

        value = json.loads(json.dumps(self._manifest))
        for stage in value.get("stages", []):
            stage.pop("_spent_usd", None)
        return value

    def _checkpoint_public(self) -> None:
        self._manifest["updated_at"] = _utc_now(self.clock)
        public = self._public_manifest()
        _atomic_write_json(self.manifest_path, public)

    def _resolve_workspace_record_path(self, value: Any, label: str) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise WorkflowConfigurationError(f"{label} path is empty")
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts:
            raise WorkflowConfigurationError(f"{label} path is not workspace-relative")
        resolved = (self.workspace / relative).resolve()
        try:
            resolved.relative_to(self.workspace)
        except ValueError as error:
            raise WorkflowConfigurationError(f"{label} path escapes the workspace") from error
        return resolved

    def _verify_recorded_artifact(self, record: Any, label: str) -> None:
        if not isinstance(record, dict):
            raise WorkflowConfigurationError(f"{label} is not an object")
        digest = str(record.get("sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise WorkflowConfigurationError(f"{label} has no valid SHA-256")
        path = self._resolve_workspace_record_path(record.get("path"), label)
        if not path.exists():
            raise WorkflowConfigurationError(f"{label} is missing: {path}")
        actual = _directory_digest(path)[0] if path.is_dir() else _file_sha256(path)
        if actual != digest:
            raise WorkflowConfigurationError(
                f"{label} hash mismatch: expected {digest}, got {actual}"
            )

    def _restore_event_sequence(self, run_id: str) -> None:
        if not self.events_path.is_file():
            raise WorkflowConfigurationError("resume checkpoint has no workflow event log")
        sequence = 0
        try:
            for index, line in enumerate(
                self.events_path.read_text(encoding="utf-8").splitlines(), 1
            ):
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("event is not an object")
                if event.get("sequence") != index:
                    raise ValueError("event sequence is not contiguous")
                if event.get("run_id") != run_id:
                    raise ValueError("event run_id does not match")
                sequence = index
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise WorkflowConfigurationError(f"invalid workflow event log: {error}") from error
        self._sequence = sequence

    def _restore_run(
        self,
        *,
        country: str,
        iso3: str,
        uploads_manifest: str | os.PathLike[str] | None,
        requested_run_id: str | None,
        ceiling_usd: float | None,
        vendor: str | None,
    ) -> tuple[str, Path, Path | None, bool]:
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkflowConfigurationError(f"invalid workflow checkpoint: {error}") from error
        if not isinstance(manifest, dict):
            raise WorkflowConfigurationError("workflow checkpoint is not an object")
        expected_root = {
            "schema_version": WORKFLOW_RUN_SCHEMA,
            "workflow_id": self.contract["workflow_id"],
            "workflow_version": self.contract["workflow_version"],
            "contract_sha256": self.contract_sha256,
            "country": country,
            "iso3": iso3,
            "ceiling_usd": ceiling_usd,
            "vendor": vendor,
        }
        for key, expected in expected_root.items():
            if manifest.get(key) != expected:
                raise WorkflowConfigurationError(
                    f"resume checkpoint {key} does not match the launch request"
                )
        run_id = str(manifest.get("run_id") or "")
        if not run_id or (requested_run_id is not None and requested_run_id != run_id):
            raise WorkflowConfigurationError("resume checkpoint run_id does not match")

        snapshot_record = manifest.get("input_snapshot")
        if not isinstance(snapshot_record, dict):
            raise WorkflowConfigurationError("resume checkpoint has no input_snapshot")
        input_snapshot_path = self._resolve_workspace_record_path(
            snapshot_record.get("path"), "input_snapshot"
        )
        self._verify_recorded_artifact(snapshot_record, "input_snapshot")
        try:
            snapshot = json.loads(input_snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkflowConfigurationError(f"invalid frozen input snapshot: {error}") from error
        expected_snapshot = {
            "schema_version": WORKFLOW_INPUT_SCHEMA,
            "country": country,
            "iso3": iso3,
            "contract_sha256": self.contract_sha256,
            "uploads_manifest": manifest.get("uploads_manifest"),
            "ceiling_usd": ceiling_usd,
            "vendor": vendor,
        }
        if snapshot != expected_snapshot:
            raise WorkflowConfigurationError("frozen input snapshot does not match checkpoint")

        frozen_uploads: Path | None = None
        uploads_record = manifest.get("uploads_manifest")
        if uploads_record is not None:
            if not isinstance(uploads_record, dict):
                raise WorkflowConfigurationError("uploads_manifest checkpoint is invalid")
            self._verify_recorded_artifact(uploads_record, "uploads_manifest")
            frozen_uploads = self._resolve_workspace_record_path(
                uploads_record.get("path"), "uploads_manifest"
            )
            try:
                frozen_envelope = json.loads(frozen_uploads.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise WorkflowConfigurationError(
                    f"invalid frozen uploads manifest: {error}"
                ) from error
            frozen_documents = self._verify_upload_documents(frozen_envelope)
            document_count = uploads_record.get("document_count")
            if (
                isinstance(document_count, bool)
                or not isinstance(document_count, int)
                or document_count != len(frozen_documents)
            ):
                raise WorkflowConfigurationError(
                    "uploads_manifest document_count does not match the frozen manifest"
                )
            if uploads_manifest is not None:
                supplied = Path(uploads_manifest).expanduser().resolve()
                if (
                    not supplied.is_file()
                    or _file_sha256(supplied) != uploads_record.get("sha256")
                ):
                    raise WorkflowConfigurationError(
                        "resume uploads manifest differs from the frozen launch input"
                    )
        elif uploads_manifest is not None:
            raise WorkflowConfigurationError(
                "cannot add an uploads manifest after the workflow has launched"
            )

        self._verify_checkpoint_namespace(
            manifest.get("checkpoint_binding"),
            run_id=run_id,
            country=country,
            iso3=iso3,
            input_snapshot=snapshot_record,
            uploads_record=uploads_record,
            ceiling_usd=ceiling_usd,
            vendor=vendor,
        )

        stages = manifest.get("stages")
        stage_ids = [
            stage.get("id") for stage in stages or [] if isinstance(stage, dict)
        ]
        if not isinstance(stages, list) or stage_ids != list(EXPECTED_STAGE_IDS):
            raise WorkflowConfigurationError("resume checkpoint stages are not canonical")
        encountered_incomplete = False
        for stage in stages:
            status = stage.get("status")
            if status == "complete":
                if encountered_incomplete:
                    raise WorkflowConfigurationError(
                        "completed stages are not a contiguous prefix"
                    )
                artifacts = stage.get("artifacts")
                if not isinstance(artifacts, list):
                    raise WorkflowConfigurationError(f"{stage['id']} artifacts are invalid")
                for index, artifact in enumerate(artifacts, 1):
                    self._verify_recorded_artifact(
                        artifact, f"{stage['id']} artifact {index}"
                    )
                spend = stage.get("spent_usd")
                if (
                    isinstance(spend, bool)
                    or not isinstance(spend, (int, float))
                    or spend < 0
                ):
                    raise WorkflowConfigurationError(f"{stage['id']} spend_usd is invalid")
                stage["_spent_usd"] = float(spend)
            else:
                encountered_incomplete = True
                if status not in {"queued", "running", "retrying"}:
                    raise WorkflowConfigurationError(
                        f"cannot resume stage {stage.get('id')} from status {status}"
                    )
                spend = stage.get("spent_usd")
                if (
                    spend is not None
                    and (
                        isinstance(spend, bool)
                        or not isinstance(spend, (int, float))
                        or not math.isfinite(float(spend))
                        or spend < 0
                    )
                ):
                    raise WorkflowConfigurationError(
                        f"{stage['id']} spend_usd is invalid"
                    )
                stage["_spent_usd"] = (
                    float(spend) if spend is not None else None
                )
                if status in {"running", "retrying"}:
                    stage["status"] = "queued"

        status = manifest.get("status")
        completed = status == "complete" and all(
            stage.get("status") == "complete" for stage in stages
        )
        if status not in {"running", "retrying", "complete"}:
            raise WorkflowConfigurationError(
                f"cannot resume terminal workflow status {status}"
            )
        if status == "complete" and not completed:
            raise WorkflowConfigurationError("completed workflow has incomplete stages")
        self._manifest = manifest
        self._restore_event_sequence(run_id)
        if completed:
            return run_id, input_snapshot_path, frozen_uploads, True

        self._manifest["status"] = "running"
        self._manifest["current_stage"] = next(
            (
                stage["id"]
                for stage in stages
                if stage["status"] != "complete"
            ),
            None,
        )
        self._manifest["failure"] = None
        self._manifest["completed_at"] = None
        self._manifest["human_review"] = {
            "available": False,
            "status": "not_available",
        }
        authoritative, reported = self._spend_totals()
        self._manifest["spent_usd"] = authoritative
        self._manifest["reported_spent_usd"] = reported
        self._checkpoint_public()
        return run_id, input_snapshot_path, frozen_uploads, False

    def run(
        self,
        *,
        country: str,
        iso3: str,
        uploads_manifest: str | os.PathLike[str] | None = None,
        run_id: str | None = None,
        ceiling_usd: float | None = None,
        vendor: str | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        self.validate_execution_plan()
        country = " ".join(str(country).split())
        iso3 = str(iso3).strip().upper()
        if not country:
            raise WorkflowConfigurationError("country cannot be empty")
        if not re.fullmatch(r"[A-Z]{3}", iso3):
            raise WorkflowConfigurationError("iso3 must be exactly three letters")
        if ceiling_usd is not None and (
            not isinstance(ceiling_usd, (int, float))
            or not math.isfinite(float(ceiling_usd))
            or ceiling_usd <= 0
        ):
            raise WorkflowConfigurationError("ceiling_usd must be finite and positive")
        requested_run_id = str(run_id) if run_id is not None else None
        if requested_run_id is not None and not requested_run_id.strip():
            raise WorkflowConfigurationError("run_id cannot be empty")

        self.workspace.mkdir(parents=True, exist_ok=True)
        resumed = False
        if self.manifest_path.exists() and resume:
            run_id, input_snapshot_path, frozen_uploads, completed = self._restore_run(
                country=country,
                iso3=iso3,
                uploads_manifest=uploads_manifest,
                requested_run_id=requested_run_id,
                ceiling_usd=float(ceiling_usd) if ceiling_usd is not None else None,
                vendor=vendor,
            )
            if completed:
                return self._public_manifest()
            resumed = True
        elif self.manifest_path.exists():
            raise WorkflowConfigurationError(
                f"workflow manifest already exists at {self.manifest_path}"
            )
        if not resumed:
            run_id = str(requested_run_id or uuid.uuid4())
            if self.events_path.exists() and self.events_path.stat().st_size:
                raise WorkflowConfigurationError(
                    f"workflow event log already exists at {self.events_path}"
                )
            _atomic_write_bytes(self.events_path, b"")

            uploads_record, frozen_uploads = self._freeze_uploads_manifest(uploads_manifest)
            input_snapshot, input_snapshot_path = self._create_input_snapshot(
                country=country,
                iso3=iso3,
                uploads_record=uploads_record,
                ceiling_usd=float(ceiling_usd) if ceiling_usd is not None else None,
                vendor=vendor,
            )
            checkpoint_binding = self._claim_checkpoint_namespace(
                run_id=run_id,
                country=country,
                iso3=iso3,
                input_snapshot=input_snapshot,
                uploads_record=uploads_record,
                ceiling_usd=(
                    float(ceiling_usd) if ceiling_usd is not None else None
                ),
                vendor=vendor,
            )
            started_at = _utc_now(self.clock)
            self._manifest = {
            "schema_version": WORKFLOW_RUN_SCHEMA,
            "run_id": run_id,
            "workflow_id": self.contract["workflow_id"],
            "workflow_version": self.contract["workflow_version"],
            "contract_sha256": self.contract_sha256,
            "country": country,
            "iso3": iso3,
            "status": "running",
            "current_stage": None,
            "started_at": started_at,
            "completed_at": None,
            "updated_at": started_at,
            "input_snapshot": input_snapshot,
            "uploads_manifest": uploads_record,
            "checkpoint_binding": checkpoint_binding,
            "ceiling_usd": float(ceiling_usd) if ceiling_usd is not None else None,
            "vendor": vendor,
            "spent_usd": 0.0,
            "reported_spent_usd": 0.0,
            "required_human_actions_during_run": [],
            "human_review": {"available": False, "status": "not_available"},
            "failure": None,
            "stages": [
                {
                    "ordinal": stage["ordinal"],
                    "id": stage["id"],
                    "status": "queued",
                    "attempts": 0,
                    "started_at": None,
                    "completed_at": None,
                    "execution_mode": (
                        "handler" if stage["id"] in self.handlers else "command"
                    ),
                    "artifacts": [],
                    "spent_usd": None,
                    "_spent_usd": None,
                }
                for stage in self.contract["stages"]
            ],
            }
            self._checkpoint_public()
        workflow_started = self.monotonic()
        if resumed:
            self._emit(
                "resume",
                status="running",
                country=country,
                iso3=iso3,
                input_snapshot=self._manifest["input_snapshot"],
                spent_usd=self._manifest["spent_usd"],
            )
        else:
            self._emit(
                "start",
                status="running",
                country=country,
                iso3=iso3,
                input_snapshot=self._manifest["input_snapshot"],
                spent_usd=0.0,
            )

        for stage in self.contract["stages"]:
            stage_id = str(stage["id"])
            record = self._stage_record(stage_id)
            if record["status"] == "complete":
                continue
            stage_dir = self.workspace / "stages" / f"{stage['ordinal']:02d}-{stage_id}"
            stage_dir.mkdir(parents=True, exist_ok=True)
            stage_started = self.monotonic()
            last_error: Exception | None = None

            try:
                self._refresh_command_spend(stage_id, record)
            except WorkflowConfigurationError as error:
                last_error = error

            first_attempt = int(record.get("attempts") or 0) + 1
            if last_error is None and first_attempt > self.max_attempts:
                last_error = RetryableStageError(
                    f"{stage_id} exhausted {self.max_attempts} attempts before restart"
                )
            for attempt in (
                range(first_attempt, self.max_attempts + 1)
                if last_error is None else ()
            ):
                record["attempts"] = attempt
                record["status"] = "running"
                record["started_at"] = record["started_at"] or _utc_now(self.clock)
                self._manifest["current_stage"] = stage_id
                self._manifest["status"] = "running"
                self._checkpoint_public()
                self._emit(
                    "stage_start",
                    status="running",
                    stage_id=stage_id,
                    stage_ordinal=stage["ordinal"],
                    attempt=attempt,
                    elapsed_seconds=round(self.monotonic() - stage_started, 3),
                    cumulative_spent_usd=self._manifest["spent_usd"],
                )

                context = StageContext(
                    run_id=run_id,
                    country=country,
                    iso3=iso3,
                    contract=self.contract,
                    stage=stage,
                    workspace=self.workspace,
                    stage_dir=stage_dir,
                    manifest_path=self.manifest_path,
                    input_snapshot_path=input_snapshot_path,
                    uploads_manifest_path=frozen_uploads,
                    ceiling_usd=float(ceiling_usd) if ceiling_usd is not None else None,
                    vendor=vendor,
                    attempt=attempt,
                    prior_stages=tuple(
                        item for item in self._public_manifest()["stages"]
                        if item["status"] == "complete"
                    ),
                )
                try:
                    result, execution_mode = self._execute_binding(context)
                    completed_spend = (
                        float(result.spent_usd)
                        if result.spent_usd is not None else 0.0
                    )
                    prior_spend = record.get("_spent_usd")
                    if (
                        prior_spend is not None
                        and completed_spend + 1e-9 < float(prior_spend)
                    ):
                        raise WorkflowConfigurationError(
                            f"{stage_id} completed spend is below its "
                            "failed-attempt ledger"
                        )
                    artifacts = self._collect_artifacts(result, context, execution_mode)
                except RetryableStageError as error:
                    last_error = error
                    try:
                        self._refresh_command_spend(stage_id, record)
                    except WorkflowConfigurationError as spend_error:
                        last_error = spend_error
                        break
                    if attempt >= self.max_attempts:
                        break
                    record["status"] = "retrying"
                    self._manifest["status"] = "retrying"
                    self._checkpoint_public()
                    self._emit(
                        "retry",
                        status="retrying",
                        stage_id=stage_id,
                        stage_ordinal=stage["ordinal"],
                        attempt=attempt,
                        next_attempt=attempt + 1,
                        elapsed_seconds=round(self.monotonic() - stage_started, 3),
                        cumulative_spent_usd=self._manifest["spent_usd"],
                        error={"type": type(error).__name__, "message": str(error)},
                    )
                    if self.retry_delay_seconds:
                        self.sleep(self.retry_delay_seconds)
                    continue
                except Exception as error:
                    last_error = error
                    try:
                        self._refresh_command_spend(stage_id, record)
                    except WorkflowConfigurationError as spend_error:
                        last_error = spend_error
                    break

                record["status"] = "complete"
                record["completed_at"] = _utc_now(self.clock)
                record["execution_mode"] = execution_mode
                record["artifacts"] = artifacts
                record["_spent_usd"] = completed_spend
                record["spent_usd"] = record["_spent_usd"]
                authoritative, reported = self._spend_totals()
                self._manifest["spent_usd"] = authoritative
                self._manifest["reported_spent_usd"] = reported
                self._checkpoint_public()
                self._emit(
                    "stage_complete",
                    status="complete",
                    stage_id=stage_id,
                    stage_ordinal=stage["ordinal"],
                    attempt=attempt,
                    elapsed_seconds=round(self.monotonic() - stage_started, 3),
                    spent_usd=record["_spent_usd"],
                    cumulative_spent_usd=authoritative,
                    artifacts=artifacts,
                )
                last_error = None
                break

            if last_error is not None:
                record["status"] = "failed"
                record["completed_at"] = _utc_now(self.clock)
                failure = {"type": type(last_error).__name__, "message": str(last_error)}
                self._manifest["status"] = "failed"
                self._manifest["current_stage"] = stage_id
                self._manifest["completed_at"] = _utc_now(self.clock)
                self._manifest["human_review"] = {
                    "available": False,
                    "status": "not_available",
                }
                self._manifest["failure"] = failure
                authoritative, reported = self._spend_totals()
                self._manifest["spent_usd"] = authoritative
                self._manifest["reported_spent_usd"] = reported
                self._checkpoint_public()
                self._emit(
                    "failure",
                    status="failed",
                    stage_id=stage_id,
                    stage_ordinal=stage["ordinal"],
                    attempt=record["attempts"],
                    elapsed_seconds=round(self.monotonic() - stage_started, 3),
                    cumulative_spent_usd=authoritative,
                    failed_stage_spent_usd=record.get("_spent_usd"),
                    error=failure,
                )
                public = self._public_manifest()
                raise WorkflowRunFailed(
                    f"workflow failed at {stage_id}: {last_error}", public
                ) from last_error

        self._manifest["status"] = "complete"
        self._manifest["current_stage"] = None
        self._manifest["completed_at"] = _utc_now(self.clock)
        self._manifest["human_review"] = {"available": True, "status": "pending"}
        self._checkpoint_public()
        self._emit(
            "workflow_complete",
            status="complete",
            elapsed_seconds=round(self.monotonic() - workflow_started, 3),
            spent_usd=self._manifest["spent_usd"],
            cumulative_spent_usd=self._manifest["spent_usd"],
            manifest_path=self.manifest_path.relative_to(self.workspace).as_posix(),
        )
        return self._public_manifest()


def _load_handler(specification: str) -> tuple[str, StageHandler]:
    if "=" not in specification:
        raise WorkflowConfigurationError(
            "handler must use STAGE=MODULE:CALLABLE syntax"
        )
    stage_id, target = specification.split("=", 1)
    if ":" not in target:
        raise WorkflowConfigurationError(
            "handler must use STAGE=MODULE:CALLABLE syntax"
        )
    module_name, attribute = target.rsplit(":", 1)
    try:
        module = importlib.import_module(module_name)
        handler = getattr(module, attribute)
    except (ImportError, AttributeError) as error:
        raise WorkflowConfigurationError(
            f"cannot load handler {specification}: {error}"
        ) from error
    if not callable(handler):
        raise WorkflowConfigurationError(f"handler {specification} is not callable")
    return stage_id, handler


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", required=True)
    parser.add_argument("--iso", required=True, dest="iso3")
    parser.add_argument("--out", required=True, help="workflow workspace directory")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH))
    parser.add_argument("--ceiling", type=float, default=500.0, dest="ceiling_usd")
    parser.add_argument("--vendor", default="anthropic/claude-opus-5")
    parser.add_argument("--uploads-manifest")
    parser.add_argument("--handler", action="append", default=[], metavar="STAGE=MODULE:CALLABLE")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--run-id")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume an interrupted active workflow, or start it if no checkpoint exists",
    )
    parser.add_argument(
        "--legacy-out",
        help="safe basename passed to existing scripts (defaults to --out directory name)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _cli_parser()
    args = parser.parse_args(argv)
    workspace = Path(args.out).expanduser().resolve()
    legacy_out = args.legacy_out or re.sub(r"_workflow$", "", workspace.name)
    try:
        contract = load_contract(args.contract)
        commands = build_existing_stage_commands(
            country=" ".join(args.country.split()),
            iso3=args.iso3.strip().upper(),
            legacy_out=legacy_out,
            ceiling_usd=args.ceiling_usd,
            vendor=args.vendor,
            workflow_version=str(contract["workflow_version"]),
        )
        handlers: dict[str, StageHandler] = {}
        for specification in args.handler:
            stage_id, handler = _load_handler(specification)
            if stage_id in handlers:
                raise WorkflowConfigurationError(f"duplicate handler for {stage_id}")
            handlers[stage_id] = handler
            commands.pop(stage_id, None)

        def stdout_event(event: Mapping[str, Any]) -> None:
            print(json.dumps(event, sort_keys=True, separators=(",", ":")), flush=True)

        coordinator = WorkflowCoordinator(
            contract=contract,
            workspace=workspace,
            handlers=handlers,
            commands=commands,
            event_sink=stdout_event,
            max_attempts=args.max_attempts,
        )
        coordinator.run(
            country=args.country,
            iso3=args.iso3,
            uploads_manifest=args.uploads_manifest,
            run_id=args.run_id,
            ceiling_usd=args.ceiling_usd,
            vendor=args.vendor,
            resume=args.resume,
        )
        return 0
    except WorkflowRunFailed:
        return 1
    except WorkflowError as error:
        print(f"workflow configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
