#!/usr/bin/env python3
"""Focused tests for the canonical Stage 8 export packager."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile

from openpyxl import Workbook, load_workbook

import export_package as E


HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE.parents[2] / "workflow" / "dar-workflow-v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_minimal_docx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats.org/"
            "package/2006/content-types'><Default Extension='xml' "
            "ContentType='application/xml'/></Types>",
        )
        archive.writestr(
            "word/document.xml",
            "<?xml version='1.0'?><w:document xmlns:w='http://schemas.openxmlformats.org/"
            "wordprocessingml/2006/main'><w:body/></w:document>",
        )


class WorkflowFixture:
    def __init__(self, root: Path):
        self.root = root
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.contract_sha256 = digest(CONTRACT_PATH)
        self.manifest_path = root / "workflow-manifest.json"
        self.out = root / "exports" / "EGY_20260826"
        self.artifact_paths: dict[tuple[str, str], Path] = {}
        self.manifest = self._build()
        self.write_manifest()

    def _record(self, stage_id: str, key: str, path: Path, media_type: str):
        self.artifact_paths[(stage_id, key)] = path
        return {
            "key": key,
            "path": path.relative_to(self.root).as_posix(),
            "sha256": digest(path),
            "media_type": media_type,
        }

    def _workbook(self, path: Path) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Options"
        sheet.append(["Option", "Cost low", "Cost high"])
        sheet.append(["I-1", 10, 20])
        workbook.save(path)
        workbook.close()

    def _build_stage(self, ordinal: int, stage: dict):
        stage_id = stage["id"]
        stage_dir = self.root / "stages" / f"{ordinal:02d}_{stage_id}"
        stage_dir.mkdir(parents=True)
        records = []
        output_hashes = {}
        narrative = E.NARRATIVE_ARTIFACTS[stage_id]
        required_keys = list(stage["required_artifacts"])
        if stage_id == "damm_diagnostic":
            required_keys.extend(E.REQUIRED_SUPPLEMENTAL_ARTIFACTS[stage_id])
        for key in required_keys:
            if key == "stage_manifest":
                continue
            companion = None
            if key == narrative:
                if stage_id == "ai_digital_agriculture":
                    path = stage_dir / f"{key}.html"
                    path.write_text(
                        "<!doctype html>\r\n<html><body><h1>AI assessment</h1>"
                        "<p>Draft evidence.</p></body></html>\r\n",
                        encoding="utf-8",
                    )
                    media_type = "text/html"
                else:
                    path = stage_dir / f"{key}.md"
                    path.write_bytes(
                        f"# {stage['title']}\r\n\r\nDraft evidence for Egypt.\r\n".encode()
                    )
                    media_type = "text/markdown"
                    if stage_id == "country_research":
                        companion = stage_dir / f"{key}.html"
                        companion.write_text(
                            "<!doctype html>\n<html><body><h1>Country research</h1>"
                            "</body></html>\n",
                            encoding="utf-8",
                        )
            elif key == "cost_benefit_workbook":
                path = stage_dir / "cost_benefit.xlsx"
                self._workbook(path)
                media_type = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                path = stage_dir / f"{key}.json"
                if key == "engine_input":
                    value = {
                        "1.1": {
                            "value": "Exact machine-filled fixture row",
                            "cls": "Documented",
                            "level": 3,
                            "year": 2026,
                            "src": "Fixture source",
                            "tier": "T1",
                            "url": "https://example.test/engine-input",
                        }
                    }
                elif key == "source_inventory":
                    value = [
                        {
                            "ref": f"SRC-{ordinal}",
                            "title": f"Source for {stage_id}",
                            "url": f"https://example.test/{stage_id}",
                            "metadata": {"tier": "A", "ordinal": ordinal},
                        }
                    ]
                else:
                    value = {
                        "schema_version": f"damm.{key}/v1",
                        "country": "Egypt",
                        "iso3": "EGY",
                        "stage_id": stage_id,
                    }
                write_json(path, value)
                media_type = "application/json"
            record = self._record(stage_id, key, path, media_type)
            records.append(record)
            output_hashes[key] = record["sha256"]
            if companion is not None:
                companion_record = self._record(
                    stage_id, key, companion, "text/html"
                )
                records.append(companion_record)
                output_hashes[key] = [record["sha256"], companion_record["sha256"]]

        stage_manifest_path = stage_dir / "stage_manifest.json"
        write_json(
            stage_manifest_path,
            {
                "schema_version": "damm.stage-manifest/v1",
                "workflow_id": "dar-canonical-v1",
                "workflow_version": self.contract["workflow_version"],
                "stage_id": stage_id,
                "input_hashes": {},
                "output_hashes": output_hashes,
                "source_inventory": "source_inventory"
                if "source_inventory" in stage["required_artifacts"]
                else [],
                "quality_checks": [{"id": "fixture", "ok": True}],
                "execution_mode": "test_fixture",
                "spend_usd": 0,
                "status": "complete",
            },
        )
        records.append(
            self._record(
                stage_id, "stage_manifest", stage_manifest_path, "application/json"
            )
        )
        return {"id": stage_id, "status": "complete", "artifacts": records}

    def _build(self):
        snapshot = self.root / "input-snapshot.json"
        self.snapshot_path = snapshot
        write_json(
            snapshot,
            {
                "schema_version": "damm.workflow-input-snapshot/v1",
                "country": "Egypt",
                "iso3": "EGY",
                "contract_sha256": self.contract_sha256,
                "uploads_manifest": None,
                "ceiling_usd": None,
                "vendor": None,
            },
        )
        stages = [
            self._build_stage(ordinal, stage)
            for ordinal, stage in enumerate(self.contract["stages"][:7], 1)
        ]
        stages.append({"id": "export_package", "status": "running", "artifacts": []})
        return {
            "schema_version": "damm.workflow-run/v1",
            "workflow_id": "dar-canonical-v1",
            "workflow_version": self.contract["workflow_version"],
            "contract_sha256": self.contract_sha256,
            "country": "Egypt",
            "iso3": "EGY",
            "status": "running",
            "current_stage": "export_package",
            "input_snapshot": {
                "path": snapshot.relative_to(self.root).as_posix(),
                "sha256": digest(snapshot),
            },
            "uploads_manifest": None,
            "ceiling_usd": None,
            "vendor": None,
            "stages": stages,
        }

    def add_upload(
        self,
        *,
        document_id: str = "ttl-country-1",
        kind: str = "country_context_documents",
        original: bytes = b"%PDF-1.4\noriginal fixture\n",
        extracted_text: str = "Egypt digital agriculture evidence.\n",
    ) -> dict:
        content_path = self.root / f"inputs/upload-content/{document_id}.txt"
        original_path = self.root / f"inputs/upload-originals/{document_id}.pdf"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_text(extracted_text, encoding="utf-8")
        original_path.write_bytes(original)
        document = {
            "id": document_id,
            "kind": kind,
            "original_filename": "country-evidence.pdf",
            "content_path": content_path.relative_to(self.root).as_posix(),
            "content_sha256": digest(content_path),
            "content_media_type": "text/plain",
            "original_path": original_path.relative_to(self.root).as_posix(),
            "original_sha256": digest(original_path),
            "original_size_bytes": len(original),
            "metadata": {
                "extracted_characters": len(extracted_text),
                "app_upload_kind": kind,
                "source_mime_type": "application/pdf",
                "uploaded_at": "2026-08-26T10:00:00Z",
                "uploaded_by": "fixture-ttl",
                "extraction_status": "extracted",
            },
        }
        uploads_path = self.root / "inputs/uploads-manifest.json"
        write_json(
            uploads_path,
            {"schema_version": "damm.uploads-manifest/v1", "documents": [document]},
        )
        uploads_record = {
            "path": uploads_path.relative_to(self.root).as_posix(),
            "sha256": digest(uploads_path),
            "document_count": 1,
        }
        self.manifest["uploads_manifest"] = uploads_record
        write_json(
            self.snapshot_path,
            {
                "schema_version": "damm.workflow-input-snapshot/v1",
                "country": "Egypt",
                "iso3": "EGY",
                "contract_sha256": self.contract_sha256,
                "uploads_manifest": uploads_record,
                "ceiling_usd": None,
                "vendor": None,
            },
        )
        self.manifest["input_snapshot"]["sha256"] = digest(self.snapshot_path)
        self.write_manifest()
        return document

    def rebind_upload_manifest(self) -> None:
        uploads_path = self.root / "inputs/uploads-manifest.json"
        envelope = json.loads(uploads_path.read_text(encoding="utf-8"))
        uploads_record = {
            "path": uploads_path.relative_to(self.root).as_posix(),
            "sha256": digest(uploads_path),
            "document_count": len(envelope["documents"]),
        }
        self.manifest["uploads_manifest"] = uploads_record
        snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        snapshot["uploads_manifest"] = uploads_record
        write_json(self.snapshot_path, snapshot)
        self.manifest["input_snapshot"]["sha256"] = digest(self.snapshot_path)
        self.write_manifest()

    def write_manifest(self):
        write_json(self.manifest_path, self.manifest)

    def artifact_record(self, stage_id: str, key: str):
        stage = next(stage for stage in self.manifest["stages"] if stage["id"] == stage_id)
        return next(record for record in stage["artifacts"] if record["key"] == key)


class FakeConverters:
    def __init__(self):
        self.pandoc_calls: list[tuple[str, str]] = []
        self.pdf_calls: list[tuple[str, str]] = []

    def pandoc(self, source: Path, target: Path):
        self.pandoc_calls.append((source.suffix, target.suffix))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".md":
            target.write_text("# Converted HTML\n\nDraft evidence.\n", encoding="utf-8")
        elif target.suffix == ".html":
            target.write_text(
                "<!doctype html>\n<html><body><p>Draft evidence.</p></body></html>\n",
                encoding="utf-8",
            )
        elif target.suffix == ".docx":
            write_minimal_docx(target)
        else:
            raise AssertionError(f"unexpected pandoc target: {target}")

    def pdf(self, source: Path, target: Path):
        self.pdf_calls.append((source.suffix, target.suffix))
        target.write_bytes(b"%PDF-1.4\n% fixture\n")


class ExportPackageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="damm-export-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = WorkflowFixture(self.root)
        self.converters = FakeConverters()

    def build(self, *, resume: bool = False):
        return E.build_export_package(
            country="Egypt",
            iso3="EGY",
            out=self.fixture.out,
            workflow_manifest=self.fixture.manifest_path,
            contract_path=CONTRACT_PATH,
            pandoc_converter=self.converters.pandoc,
            pdf_converter=self.converters.pdf,
            created_at="2026-08-26T12:00:00Z",
            resume=resume,
        )

    def test_pure_manifest_validation_returns_all_canonical_bindings(self):
        validated = E.validate_workflow_manifest(
            self.fixture.manifest,
            self.fixture.contract,
            country="Egypt",
            iso3="egy",
            contract_sha256=self.fixture.contract_sha256,
        )

        self.assertEqual(validated.workflow_version, "1.0.0")
        self.assertEqual(tuple(validated.artifacts), E.EXPECTED_STAGE_IDS[:7])
        self.assertEqual(
            Path(validated.artifacts["country_research"]["country_research_report"].path).suffix,
            ".md",
        )
        self.assertEqual(
            len(
                validated.artifact_records["country_research"][
                    "country_research_report"
                ]
            ),
            2,
        )
        for stage in self.fixture.contract["stages"][:7]:
            expected = set(stage["required_artifacts"])
            expected.update(E.REQUIRED_SUPPLEMENTAL_ARTIFACTS.get(stage["id"], ()))
            self.assertEqual(
                set(validated.artifacts[stage["id"]]), expected
            )

    def test_manifest_validation_rejects_missing_narrative_and_wrong_run_identity(self):
        cases = []
        missing = json.loads(json.dumps(self.fixture.manifest))
        missing["stages"][0]["artifacts"] = [
            item
            for item in missing["stages"][0]["artifacts"]
            if item["key"] != "diagnostic_report"
        ]
        cases.append((missing, "missing required artifacts: diagnostic_report"))
        missing_engine_input = json.loads(json.dumps(self.fixture.manifest))
        missing_engine_input["stages"][0]["artifacts"] = [
            item
            for item in missing_engine_input["stages"][0]["artifacts"]
            if item["key"] != "engine_input"
        ]
        cases.append((missing_engine_input, "missing required artifacts: engine_input"))
        wrong_contract = json.loads(json.dumps(self.fixture.manifest))
        wrong_contract["contract_sha256"] = "0" * 64
        cases.append((wrong_contract, "not bound to the canonical contract bytes"))
        wrong_country = json.loads(json.dumps(self.fixture.manifest))
        wrong_country["country"] = "Jordan"
        cases.append((wrong_country, "country does not match"))
        wrong_stage = json.loads(json.dumps(self.fixture.manifest))
        wrong_stage["stages"][4]["status"] = "running"
        cases.append((wrong_stage, "strategic_foresight is not complete"))
        traversal = json.loads(json.dumps(self.fixture.manifest))
        traversal["stages"][0]["artifacts"][0]["path"] = "../outside.json"
        cases.append((traversal, "not a safe relative path"))

        for value, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(E.ManifestValidationError, message):
                    E.validate_workflow_manifest(
                        value,
                        self.fixture.contract,
                        country="Egypt",
                        iso3="EGY",
                        contract_sha256=self.fixture.contract_sha256,
                    )

    def test_full_build_exports_every_profile_and_hash_bound_bundle(self):
        result = self.build()

        self.assertEqual(
            result.package_dir.name, "EGY_20260826_dar_package_v1.0.0"
        )
        self.assertEqual(result.zip_path, Path(f"{self.fixture.out}_dar_package.zip"))
        self.assertTrue(result.zip_path.is_file())
        manifest = json.loads(result.package_manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "damm.dar-package/v1")
        self.assertEqual(manifest["lifecycle_state"], "draft")
        self.assertEqual(manifest["created_at"], "2026-08-26T12:00:00Z")
        self.assertEqual(manifest["export_profiles"], self.fixture.contract["export_profiles"])
        self.assertEqual(manifest["file_count"], 58)
        self.assertEqual(len(self.converters.pandoc_calls), 15)
        self.assertEqual(len(self.converters.pdf_calls), 7)

        narrative_files = list((result.package_dir / "narratives").rglob("*"))
        narrative_files = [path for path in narrative_files if path.is_file()]
        self.assertEqual(len(narrative_files), 28)
        for suffix in (".md", ".html", ".docx", ".pdf"):
            self.assertEqual(sum(path.suffix == suffix for path in narrative_files), 7)
        diagnostic_md = (
            result.package_dir
            / "narratives/01_damm_diagnostic/diagnostic_report.md"
        ).read_bytes()
        self.assertNotIn(b"\r", diagnostic_md)
        self.assertTrue(diagnostic_md.endswith(b"\n"))

        csv_path = result.package_dir / "source-inventory/source_inventory.csv"
        with csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 6)
        self.assertEqual(
            {row["stage_id"] for row in rows}, set(E.SOURCE_INVENTORY_STAGES)
        )
        self.assertIn('"tier":"A"', rows[0]["metadata"])
        xlsx_path = result.package_dir / "source-inventory/source_inventory.xlsx"
        workbook = load_workbook(xlsx_path, read_only=True, data_only=False)
        self.assertEqual(workbook["Sources"].max_row, 7)
        workbook.close()
        cost_benefit = (
            result.package_dir
            / "structured/06_investment_options/cost_benefit.xlsx"
        )
        self.assertTrue(cost_benefit.is_file())

        engine_source = self.fixture.artifact_paths[("damm_diagnostic", "engine_input")]
        engine_records = [
            record
            for record in manifest["files"]
            if record.get("stage_id") == "damm_diagnostic"
            and record.get("artifact_id") == "engine_input"
        ]
        self.assertEqual(len(engine_records), 1)
        engine_record = engine_records[0]
        self.assertEqual(engine_record["category"], "structured")
        self.assertEqual(engine_record["sha256"], digest(engine_source))
        self.assertEqual(engine_record["source_sha256"], digest(engine_source))
        packaged_engine = result.package_dir / engine_record["path"]
        self.assertEqual(packaged_engine.read_bytes(), engine_source.read_bytes())

        E.validate_package_files(result.package_dir, manifest)
        for record in manifest["files"]:
            payload = result.package_dir / record["path"]
            self.assertEqual(record["sha256"], digest(payload))
            self.assertEqual(record["bytes"], payload.stat().st_size)
        with zipfile.ZipFile(result.zip_path) as archive:
            self.assertIsNone(archive.testzip())
            root = result.package_dir.name + "/"
            self.assertIn(root + "package-manifest.json", archive.namelist())
            self.assertEqual(len(archive.namelist()), manifest["file_count"] + 1)
            self.assertEqual(
                archive.read(root + engine_record["path"]), engine_source.read_bytes()
            )

    def test_upload_manifest_extracted_text_and_original_are_packaged_with_provenance(self):
        document = self.fixture.add_upload(
            original=b"\x00fixture-original-binary\xff",
            extracted_text="Country evidence with café and soil data.\n",
        )

        result = self.build()
        package_manifest = json.loads(result.package_manifest.read_text(encoding="utf-8"))
        signature = package_manifest["upload_inputs"]
        self.assertEqual(signature["manifest_sha256"], self.fixture.manifest["uploads_manifest"]["sha256"])
        self.assertEqual(signature["document_count"], 1)
        self.assertEqual(signature["documents"][0]["id"], document["id"])
        expected = {
            "inputs/uploads-manifest.json": "uploads_manifest",
            document["content_path"]: "upload_extracted_text",
            document["original_path"]: "upload_original",
        }
        records = {record["path"]: record for record in package_manifest["files"]}
        for relative, artifact_id in expected.items():
            with self.subTest(relative=relative):
                record = records[relative]
                self.assertEqual(record["category"], "input")
                self.assertEqual(record["artifact_id"], artifact_id)
                self.assertEqual(record["sha256"], record["source_sha256"])
                self.assertEqual(
                    (result.package_dir / relative).read_bytes(),
                    (self.root / relative).read_bytes(),
                )
        self.assertEqual(records[document["original_path"]]["input_id"], document["id"])
        self.assertEqual(records[document["original_path"]]["input_kind"], document["kind"])
        with zipfile.ZipFile(result.zip_path) as archive:
            names = set(archive.namelist())
            for relative in expected:
                self.assertIn(f"{result.package_dir.name}/{relative}", names)

    def test_tampered_or_missing_frozen_upload_payload_fails_before_conversion(self):
        document = self.fixture.add_upload()
        original = self.root / document["original_path"]
        original.write_bytes(original.read_bytes() + b"tamper")
        with self.assertRaisesRegex(E.PackagingError, "SHA-256 mismatch"):
            self.build()
        self.assertEqual(self.converters.pandoc_calls, [])

        # A missing original is independently terminal.
        original.write_bytes(b"%PDF-1.4\noriginal fixture\n")
        original.unlink()
        with self.assertRaisesRegex(E.PackagingError, "missing"):
            self.build()
        self.assertEqual(self.converters.pandoc_calls, [])

        # Restore the original, then prove a missing extracted file is also terminal.
        original.write_bytes(b"%PDF-1.4\noriginal fixture\n")
        (self.root / document["content_path"]).unlink()
        with self.assertRaisesRegex(E.PackagingError, "missing"):
            self.build()
        self.assertEqual(self.converters.pandoc_calls, [])

    def test_hash_bound_upload_path_traversal_and_symlink_are_rejected(self):
        document = self.fixture.add_upload()
        uploads_path = self.root / "inputs/uploads-manifest.json"
        envelope = json.loads(uploads_path.read_text(encoding="utf-8"))
        outside = self.root / "outside.pdf"
        outside.write_bytes(b"outside")
        envelope["documents"][0]["original_path"] = "inputs/upload-originals/../../outside.pdf"
        envelope["documents"][0]["original_sha256"] = digest(outside)
        envelope["documents"][0]["original_size_bytes"] = outside.stat().st_size
        write_json(uploads_path, envelope)
        self.fixture.rebind_upload_manifest()
        with self.assertRaisesRegex(E.ManifestValidationError, "not a safe relative path"):
            self.build()

        # A lexically valid path that resolves through a symlink is also forbidden.
        symlink = self.root / "inputs/upload-originals/linked.pdf"
        symlink.symlink_to(outside)
        envelope["documents"][0]["original_path"] = symlink.relative_to(self.root).as_posix()
        write_json(uploads_path, envelope)
        self.fixture.rebind_upload_manifest()
        with self.assertRaisesRegex(E.PackagingError, "symbolic link"):
            self.build()
        self.assertEqual(self.converters.pandoc_calls, [])

    def test_artifact_byte_mutation_fails_before_conversion_and_publishes_nothing(self):
        path = self.fixture.artifact_paths[("country_research", "country_evidence_data")]
        path.write_text('{"tampered":true}\n', encoding="utf-8")

        with self.assertRaisesRegex(E.PackagingError, "SHA-256 mismatch"):
            self.build()

        self.assertEqual(self.converters.pandoc_calls, [])
        self.assertFalse(Path(f"{self.fixture.out}_dar_package.zip").exists())
        self.assertFalse(
            self.fixture.out.parent.joinpath(
                "EGY_20260826_dar_package_v1.0.0"
            ).exists()
        )

    def test_engine_input_mutation_or_stale_stage_binding_is_terminal(self):
        stage_id = "damm_diagnostic"
        key = "engine_input"
        path = self.fixture.artifact_paths[(stage_id, key)]
        path.write_text('{"1.1":{"tampered":true}}\n', encoding="utf-8")

        with self.assertRaisesRegex(E.PackagingError, "SHA-256 mismatch"):
            self.build()
        self.assertEqual(self.converters.pandoc_calls, [])

        self.fixture.artifact_record(stage_id, key)["sha256"] = digest(path)
        self.fixture.write_manifest()
        with self.assertRaisesRegex(
            E.ManifestValidationError, "output_hashes does not bind engine_input"
        ):
            self.build()
        self.assertEqual(self.converters.pandoc_calls, [])

    def test_rehashed_artifact_still_fails_stale_stage_manifest_binding(self):
        stage_id = "country_research"
        key = "country_evidence_data"
        path = self.fixture.artifact_paths[(stage_id, key)]
        write_json(path, {"tampered": True, "country": "Egypt"})
        self.fixture.artifact_record(stage_id, key)["sha256"] = digest(path)
        self.fixture.write_manifest()

        with self.assertRaisesRegex(
            E.ManifestValidationError, "output_hashes does not bind country_evidence_data"
        ):
            self.build()

        self.assertEqual(self.converters.pandoc_calls, [])

    def test_converter_failure_is_terminal_and_leaves_no_publication(self):
        def failing_pandoc(_source: Path, _target: Path):
            raise E.PackagingError("injected pandoc failure")

        with self.assertRaisesRegex(E.PackagingError, "injected pandoc failure"):
            E.build_export_package(
                country="Egypt",
                iso3="EGY",
                out=self.fixture.out,
                workflow_manifest=self.fixture.manifest_path,
                contract_path=CONTRACT_PATH,
                pandoc_converter=failing_pandoc,
                pdf_converter=self.converters.pdf,
            )

        self.assertFalse(Path(f"{self.fixture.out}_dar_package.zip").exists())
        self.assertFalse(
            self.fixture.out.parent.joinpath(
                "EGY_20260826_dar_package_v1.0.0"
            ).exists()
        )

    def test_missing_real_converters_fail_explicitly(self):
        source = self.root / "source.md"
        source.write_text("# Source\n", encoding="utf-8")
        with mock.patch.object(E.shutil, "which", return_value=None):
            with self.assertRaisesRegex(E.PackagingError, "pandoc.*not found"):
                E.default_pandoc_converter(source, self.root / "target.docx")
            with self.assertRaisesRegex(E.PackagingError, "soffice.*not found"):
                E.default_pdf_converter(self.root / "target.docx", self.root / "target.pdf")

    def test_package_manifest_rejects_post_build_tampering(self):
        result = self.build()
        manifest = json.loads(result.package_manifest.read_text(encoding="utf-8"))
        target = result.package_dir / manifest["files"][0]["path"]
        target.write_bytes(target.read_bytes() + b"tamper")

        with self.assertRaisesRegex(E.PackagingError, "byte count does not match"):
            E.validate_package_files(result.package_dir, manifest)

    def test_resume_reuses_verified_complete_package_without_conversion(self):
        first = self.build()
        calls = (list(self.converters.pandoc_calls), list(self.converters.pdf_calls))

        # Coordinator finalization legitimately changes only mutable Stage 8/root state.
        self.fixture.manifest["status"] = "complete"
        self.fixture.manifest["current_stage"] = None
        self.fixture.manifest["stages"][-1]["status"] = "complete"
        self.fixture.write_manifest()
        resumed = self.build(resume=True)

        self.assertEqual(resumed, first)
        self.assertEqual(self.converters.pandoc_calls, calls[0])
        self.assertEqual(self.converters.pdf_calls, calls[1])
        E.validate_package_zip(resumed.package_dir, resumed.zip_path)

    def test_resume_recovers_directory_only_by_atomically_recreating_zip(self):
        first = self.build()
        first.zip_path.unlink()
        calls = (len(self.converters.pandoc_calls), len(self.converters.pdf_calls))

        resumed = self.build(resume=True)

        self.assertEqual(resumed.package_dir, first.package_dir)
        self.assertTrue(resumed.zip_path.is_file())
        self.assertEqual(
            calls,
            (len(self.converters.pandoc_calls), len(self.converters.pdf_calls)),
        )
        self.assertEqual(
            list(resumed.zip_path.parent.glob(f".{resumed.zip_path.name}-recover-*")),
            [],
        )
        E.validate_package_zip(resumed.package_dir, resumed.zip_path)

    def test_resume_rejects_zip_only_and_identity_or_zip_mismatch(self):
        result = self.build()
        package_copy = self.root / "package-copy"
        shutil.copytree(result.package_dir, package_copy)
        shutil.rmtree(result.package_dir)
        with self.assertRaisesRegex(E.PackagingError, "ZIP without.*package directory"):
            self.build(resume=True)

        shutil.copytree(package_copy, result.package_dir)
        package_manifest = json.loads(
            result.package_manifest.read_text(encoding="utf-8")
        )
        package_manifest["country"] = "Jordan"
        write_json(result.package_manifest, package_manifest)
        with self.assertRaisesRegex(E.PackagingError, "identity mismatch for country"):
            self.build(resume=True)

        package_manifest["country"] = "Egypt"
        write_json(result.package_manifest, package_manifest)
        with zipfile.ZipFile(result.zip_path, "a") as archive:
            archive.writestr("unexpected.txt", "tamper")
        with self.assertRaisesRegex(E.PackagingError, "content set does not match"):
            self.build(resume=True)

    def test_resume_rejects_package_without_exact_engine_input_payload(self):
        result = self.build()
        package_manifest = json.loads(
            result.package_manifest.read_text(encoding="utf-8")
        )
        engine_records = [
            record
            for record in package_manifest["files"]
            if record.get("stage_id") == "damm_diagnostic"
            and record.get("artifact_id") == "engine_input"
        ]
        self.assertEqual(len(engine_records), 1)
        (result.package_dir / engine_records[0]["path"]).unlink()
        package_manifest["files"].remove(engine_records[0])
        package_manifest["file_count"] = len(package_manifest["files"])
        write_json(result.package_manifest, package_manifest)

        with self.assertRaisesRegex(E.PackagingError, "exact Stage 1 engine_input"):
            self.build(resume=True)


if __name__ == "__main__":
    unittest.main()
