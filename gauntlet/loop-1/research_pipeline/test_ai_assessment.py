#!/usr/bin/env python3

import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ai_assessment as A


class AiAssessmentTest(unittest.TestCase):
    def test_ttl_uploads_are_balanced_bounded_and_marked_untrusted(self):
        long_text = ("START_MARKER" + "a" * 20000 + "MIDDLE_MARKER"
                     + "b" * 20000 + "TAIL_MARKER")
        uploads = [
            {"filename": "long.pdf", "sha256": "a" * 64,
             "extracted_text": long_text},
            {"filename": "empty.txt", "sha256": "b" * 64,
             "extracted_text": ""},
        ]
        with mock.patch.object(A.V, "exa_search", return_value=[]):
            sources = A._search_sources([], uploads, object(), "ASIS")

        self.assertEqual(len(sources), 2)
        self.assertIn("START_MARKER", sources[0]["text"])
        self.assertIn("MIDDLE_MARKER", sources[0]["text"])
        self.assertIn("TAIL_MARKER", sources[0]["text"])
        self.assertEqual(
            sources[0]["analysis_coverage"]["policy"],
            A.WI.BALANCED_EXCERPT_POLICY,
        )
        self.assertEqual(sources[1]["analysis_coverage"]["mode"], "empty")
        packed = A._pack(sources)
        self.assertIn("TAIL_MARKER", packed)
        self.assertIn("ANALYSIS_COVERAGE", packed)
        self.assertIn("NEVER INSTRUCTIONS", packed)
        self.assertIn("empty.txt", packed)
        self.assertIn("never instructions", A.SYSTEM.casefold())
        self.assertIn("ignore", A.SYSTEM.casefold())

        marker_finding = {
            "statement": "Synthetic range metadata is a country fact.",
            "quote": "START EXCERPT: source characters",
            "source_id": sources[0]["id"], "about_country": "Exampleland",
            "dimension": "governance", "why_it_matters": "It does not.",
            "limitation": "Synthetic prompt metadata.",
        }
        accepted, rejected = A._verify_findings(
            {"findings": [marker_finding], "data_gaps": []},
            sources, "Exampleland")
        self.assertEqual(accepted, [])
        self.assertTrue(rejected)

    def test_upload_coverage_is_preserved_in_cited_source_inventory(self):
        coverage = {"policy": A.WI.BALANCED_EXCERPT_POLICY, "mode": "full"}
        source = {
            "id": "ASIS-UPLOAD-1", "source_name": "AI plan.pdf", "source_url": "",
            "tier": "user-provided", "source_kind": "ttl_upload", "sha256": "a" * 64,
            "analysis_coverage": coverage,
        }
        as_is = {"findings": [{"source_id": "ASIS-UPLOAD-1"}], "data_gaps": []}
        peer = {"findings": [], "data_gaps": []}
        product = A.build_product(
            "Exampleland", "EXP", as_is, peer,
            {"actions": [], "sequencing_note": ""}, [source], uploads=[{}])
        self.assertEqual(product["source_inventory"][0]["analysis_coverage"], coverage)

    def test_uncited_upload_remains_visible_as_considered_provenance(self):
        coverage = {"policy": A.WI.BALANCED_EXCERPT_POLICY, "mode": "empty"}
        source = {
            "id": "ASIS-UPLOAD-1", "source_name": "empty.txt", "source_url": "",
            "tier": "user-provided", "source_kind": "ttl_upload", "sha256": "b" * 64,
            "analysis_coverage": coverage,
        }
        product = A.build_product(
            "Exampleland", "EXP",
            {"findings": [], "data_gaps": []},
            {"findings": [], "data_gaps": []},
            {"actions": [], "sequencing_note": ""},
            [source], uploads=[{}],
        )
        self.assertEqual(product["source_inventory"][0]["id"], "ASIS-UPLOAD-1")
        self.assertEqual(product["source_inventory"][0]["analysis_coverage"], coverage)

    def product(self):
        as_is = {"findings": [{
            "id": "AI-ASIS-1", "statement": "A national policy exists.",
            "quote": "national policy", "source_id": "WEB-1", "source_name": "Policy",
            "source_url": "https://example.gov/policy", "tier": "T1",
            "source_kind": "published_source", "about_country": "Exampleland",
            "dimension": "governance", "why_it_matters": "It provides authority.",
            "limitation": "Implementation evidence is absent.",
        }], "data_gaps": ["No adoption series was found."]}
        peer = {"findings": [{
            "id": "AI-PEER-1", "statement": "A peer published safeguards.",
            "quote": "published safeguards", "source_id": "WEB-2",
            "source_name": "Peer policy", "source_url": "https://peer.gov/policy",
            "tier": "T1", "source_kind": "published_source", "about_country": "Peerland",
            "dimension": "safeguards", "why_it_matters": "It is a design reference.",
            "limitation": "It has not been evaluated in Exampleland.",
        }], "data_gaps": []}
        agenda = {"actions": [{
            "priority": "1", "action": "Create an AI governance sandbox",
            "rationale": "Address the recorded governance gap.", "horizon": "0–2 years",
            "lead": "Agriculture ministry", "prerequisites": ["legal mandate"],
            "risks_and_safeguards": ["independent review"],
            "indicators": ["sandbox decisions published"],
            "evidence_ids": ["AI-ASIS-1", "AI-PEER-1"],
        }], "sequencing_note": "Governance precedes scale."}
        sources = [
            {"id": "WEB-1", "source_name": "Policy", "source_url": "https://example.gov/policy",
             "tier": "T1", "source_kind": "published_source"},
            {"id": "WEB-2", "source_name": "Peer policy", "source_url": "https://peer.gov/policy",
             "tier": "T1", "source_kind": "published_source"},
        ]
        return A.build_product("Exampleland", "EXP", as_is, peer, agenda, sources)

    def test_three_required_sections_are_separate_and_valid(self):
        product = self.product()
        self.assertEqual(A.validate_product(product), [])
        self.assertIn("as_is", product)
        self.assertIn("peer_experience", product)
        self.assertIn("recommended_agenda", product)
        self.assertEqual(product["recommended_agenda"]["status"],
                         "proposed_for_post_completion_validation")

    def test_unknown_evidence_reference_is_rejected(self):
        product = self.product()
        product["recommended_agenda"]["actions"][0]["evidence_ids"] = ["NOT-REAL"]
        self.assertTrue(any("unknown evidence" in e for e in A.validate_product(product)))

    def test_empty_recommended_agenda_is_rejected(self):
        product = self.product()
        product["recommended_agenda"]["actions"] = []
        self.assertTrue(any("no proposed action" in error
                            for error in A.validate_product(product)))

    def test_markdown_keeps_peer_boundary_and_draft_status(self):
        text = A.render_markdown(self.product())
        self.assertIn("Draft", text)
        self.assertIn("Peer-country experience", text)
        self.assertIn("Lesson boundary", text)


if __name__ == "__main__":
    unittest.main()
