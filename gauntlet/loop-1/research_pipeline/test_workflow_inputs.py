#!/usr/bin/env python3

import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import workflow_inputs as W
import vendors as V


class WorkflowInputsTest(unittest.TestCase):
    def test_balanced_excerpt_covers_start_middle_and_end_transparently(self):
        text = ("START_MARKER" + "a" * 500 + "MIDDLE_MARKER"
                + "b" * 500 + "TAIL_MARKER")
        first = W.balanced_text_excerpt(text, 150)
        second = W.balanced_text_excerpt(text, 150)

        self.assertEqual(first, second)
        self.assertIn("START_MARKER", first["text"])
        self.assertIn("MIDDLE_MARKER", first["text"])
        self.assertIn("TAIL_MARKER", first["text"])
        coverage = first["coverage"]
        self.assertEqual(coverage["policy"], W.BALANCED_EXCERPT_POLICY)
        self.assertEqual(coverage["mode"], "balanced_excerpt")
        self.assertEqual(coverage["included_source_characters"], 150)
        self.assertEqual(
            [segment["label"] for segment in coverage["segments"]],
            ["start", "middle", "end"],
        )
        self.assertEqual(
            coverage["included_source_characters"]
            + coverage["omitted_source_characters"],
            coverage["source_characters"],
        )

    def test_short_and_empty_documents_report_full_coverage(self):
        full = W.document_excerpt({"extracted_text": "complete document"}, 100)
        empty = W.document_excerpt({"extracted_text": ""}, 100)

        self.assertEqual(full["text"], "complete document")
        self.assertEqual(full["coverage"]["mode"], "full")
        self.assertEqual(full["coverage"]["omitted_source_characters"], 0)
        self.assertEqual(empty["coverage"]["mode"], "empty")
        self.assertEqual(empty["coverage"]["segments"], [])

    def test_reads_hash_bound_utf8_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = "Country foresight evidence.".encode()
            content_directory = os.path.join(directory, "inputs", "upload-content")
            os.makedirs(content_directory)
            content = os.path.join(content_directory, "u1.txt")
            with open(content, "wb") as handle:
                handle.write(raw)
            manifest = os.path.join(directory, "inputs", "uploads-manifest.json")
            with open(manifest, "w") as handle:
                json.dump({
                    "schema_version": W.SCHEMA_VERSION,
                    "documents": [{
                        "id": "u1", "kind": "foresight_documents",
                        "original_filename": "foresight.pdf",
                        "content_path": "inputs/upload-content/u1.txt",
                        "content_sha256": hashlib.sha256(raw).hexdigest(),
                        "content_media_type": "text/plain",
                        "metadata": {"source_mime_type": "application/pdf"},
                    }],
                }, handle)
            docs = W.load_upload_documents(manifest, {"foresight_documents"})
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["filename"], "foresight.pdf")
            self.assertEqual(docs[0]["extracted_text"], raw.decode())

    def test_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            content_directory = os.path.join(directory, "inputs", "upload-content")
            os.makedirs(content_directory)
            content = os.path.join(content_directory, "u1.txt")
            with open(content, "w") as handle:
                handle.write("changed")
            manifest = os.path.join(directory, "inputs", "uploads-manifest.json")
            with open(manifest, "w") as handle:
                json.dump({
                    "schema_version": W.SCHEMA_VERSION,
                    "documents": [{
                        "id": "u1", "kind": "ai_documents",
                        "original_filename": "ai.docx",
                        "content_path": "inputs/upload-content/u1.txt",
                        "content_sha256": "0" * 64, "content_media_type": "text/plain",
                    }],
                }, handle)
            with self.assertRaisesRegex(ValueError, "does not match"):
                W.load_upload_documents(manifest, {"ai_documents"})

    def test_canonical_upload_reader_rejects_manifest_mutation_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = os.path.join(directory, "inputs")
            content_directory = os.path.join(inputs, "upload-content")
            os.makedirs(content_directory)
            outside = os.path.join(directory, "outside.txt")
            with open(outside, "w") as handle:
                handle.write("outside evidence")
            manifest = os.path.join(inputs, "uploads-manifest.json")

            def write_manifest(content_path):
                with open(manifest, "w") as handle:
                    json.dump({
                        "schema_version": W.SCHEMA_VERSION,
                        "documents": [{
                            "id": "u1", "kind": "ai_documents",
                            "original_filename": "ai.txt",
                            "content_path": content_path,
                            "content_sha256": hashlib.sha256(
                                b"outside evidence").hexdigest(),
                            "content_media_type": "text/plain",
                        }],
                    }, handle)

            write_manifest("inputs/upload-content/../../outside.txt")
            with self.assertRaisesRegex(ValueError, "not a canonical"):
                W.load_upload_documents(manifest, {"ai_documents"})

            link = os.path.join(content_directory, "link.txt")
            os.symlink(outside, link)
            write_manifest("inputs/upload-content/link.txt")
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                W.load_upload_documents(manifest, {"ai_documents"})

            os.unlink(link)
            with open(link, "w") as handle:
                handle.write("outside evidence")
            write_manifest("inputs/upload-content/link.txt")
            with open(manifest, "rb") as handle:
                expected = hashlib.sha256(handle.read()).hexdigest()
            with open(manifest, "a") as handle:
                handle.write("\n")
            with mock.patch.dict(
                os.environ,
                {
                    "DAMM_WORKFLOW_WORKSPACE": directory,
                    "DAMM_UPLOADS_MANIFEST_SHA256": expected,
                },
                clear=False,
            ):
                with self.assertRaisesRegex(ValueError, "frozen launch input"):
                    W.load_upload_documents(manifest, {"ai_documents"})

    def test_missing_optional_manifest_is_empty_not_blocking(self):
        self.assertEqual(W.load_upload_documents(None, {"ai_documents"}), [])

    def test_state_and_spend_checkpoints_reject_a_foreign_workflow_identity(self):
        first_identity = "a" * 64
        second_identity = "b" * 64
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = os.path.join(directory, "spend.json")
            with mock.patch.dict(
                    os.environ,
                    {"DAMM_CHECKPOINT_BINDING_SHA256": first_identity},
                    clear=False):
                state = W.bind_checkpoint_state({"rows": {}}, loaded=False)
                self.assertEqual(
                    state[W.CHECKPOINT_IDENTITY_FIELD], first_identity)
                ledger = V.Ledger(ceiling=500, label="bound")
                ledger.record("exa", "research", searches=1)
                ledger.save(ledger_path)

            with mock.patch.dict(
                    os.environ,
                    {"DAMM_CHECKPOINT_BINDING_SHA256": second_identity},
                    clear=False):
                with self.assertRaisesRegex(ValueError, "not bound"):
                    W.bind_checkpoint_state(state, loaded=True)
                with self.assertRaisesRegex(ValueError, "not bound"):
                    V.Ledger(ceiling=500, label="bound").load(ledger_path)

    def test_attached_spend_ledger_journals_each_record_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = os.path.join(directory, "spend.json")
            other_path = os.path.join(directory, "other-spend.json")
            ledger = V.Ledger(ceiling=500, label="journalled")

            ledger.attach(ledger_path)
            with open(ledger_path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["summary"]["calls"], 0)

            # There is deliberately no explicit save here. A command that fails or is
            # killed after the paid call must still leave its spend for the coordinator
            # and a subsequent retry to carry forward.
            ledger.record("exa", "research", searches=2, detail="paid attempt")
            with open(ledger_path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["summary"]["calls"], 1)
            self.assertEqual(saved["calls"][0]["detail"], "paid attempt")
            self.assertGreater(saved["summary"]["total"], 0)

            resumed = V.Ledger(ceiling=500, label="journalled")
            resumed.attach(ledger_path)
            self.assertEqual(resumed.load(ledger_path), 1)
            self.assertEqual(resumed.summary()["calls"], 1)
            with self.assertRaisesRegex(ValueError, "already bound"):
                resumed.save(other_path)

    def test_dual_spend_checkpoints_reconcile_only_prefix_histories(self):
        first = V.Ledger(ceiling=500, label="dual")
        first.record("exa", "generation", searches=1, detail="first")
        embedded = first.snapshot()
        first.record("exa", "generation", searches=1, detail="second")
        journal_ahead = first.snapshot()

        resumed = V.Ledger(ceiling=500, label="dual")
        resumed.restore(journal_ahead)
        self.assertEqual(resumed.reconcile(embedded), 2)
        self.assertEqual([call["detail"] for call in resumed.calls], ["first", "second"])

        older_journal = V.Ledger(ceiling=500, label="dual")
        older_journal.restore(embedded)
        self.assertEqual(older_journal.reconcile(journal_ahead), 2)
        self.assertEqual(
            [call["detail"] for call in older_journal.calls], ["first", "second"])

        divergent = V.Ledger(ceiling=500, label="dual")
        divergent.record("exa", "generation", searches=1, detail="different")
        with self.assertRaisesRegex(ValueError, "divergent"):
            resumed.reconcile(divergent.snapshot())


if __name__ == "__main__":
    unittest.main()
