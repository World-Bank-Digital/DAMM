#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ai_assessment as A


class ScriptedLLM:
    model = "fixture-model"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def enable_durable_outcomes(self):
        return self

    def json_call(self, system, user, schema, pass_name, max_tokens=8000,
                  detail=""):
        self.calls.append({
            "system": system,
            "user": user,
            "schema": schema,
            "pass_name": pass_name,
            "max_tokens": max_tokens,
            "detail": detail,
        })
        if not self.responses:
            raise AssertionError(f"unexpected model call: {detail}")
        return self.responses.pop(0)


class AiAssessmentTest(unittest.TestCase):
    @staticmethod
    def sources():
        return {
            "as_is": [{
                "id": "ASIS-WEB-1",
                "source_name": "National AI policy",
                "source_url": "https://example.gov/ai-policy",
                "tier": "T1",
                "text": "Exampleland adopted a national AI policy.",
                "source_kind": "published_source",
            }],
            "peer": [{
                "id": "PEER-WEB-1",
                "source_name": "Peer AI safeguards",
                "source_url": "https://peer.gov/ai-safeguards",
                "tier": "T1",
                "text": "Peerland published agricultural AI safeguards.",
                "source_kind": "published_source",
            }],
        }

    @staticmethod
    def evidence_response(*, peer=False, valid=True):
        return {
            "findings": [{
                "statement": (
                    "Peerland published agricultural AI safeguards."
                    if peer else "Exampleland adopted a national AI policy."
                ),
                "quote": (
                    "Peerland published agricultural AI safeguards."
                    if peer and valid
                    else "Exampleland adopted a national AI policy."
                    if valid
                    else "This quotation is not in the named source."
                ),
                "source_id": "PEER-WEB-1" if peer else "ASIS-WEB-1",
                "about_country": "Peerland" if peer else "Exampleland",
                "dimension": "safeguards" if peer else "governance",
                "why_it_matters": "It establishes a documented baseline.",
                "limitation": "Implementation evidence is not available.",
            }],
            "data_gaps": [],
        }

    @staticmethod
    def agenda_response(*, valid=True):
        return {
            "actions": [{
                "priority": "1",
                "action": "Create an AI governance sandbox",
                "rationale": "Address the documented governance gap.",
                "horizon": "0–2 years",
                "lead": "Agriculture ministry",
                "prerequisites": ["legal mandate"],
                "risks_and_safeguards": ["independent review"],
                "indicators": ["sandbox decisions published"],
                "evidence_ids": [
                    "AI-ASIS-1", "AI-PEER-1"
                ] if valid else ["NOT-VERIFIED"],
            }],
            "sequencing_note": "Governance precedes scale.",
        }

    def run_main_with(self, directory, llm, sources):
        argv = [
            "ai_assessment.py",
            "--country", "Exampleland",
            "--iso", "EXP",
            "--out", "EXP_stage3",
            "--vendor", "anthropic/claude-opus-5",
        ]
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(A, "LOOP1", directory):
                with mock.patch.object(A.V, "load_env"):
                    with mock.patch.object(A.V, "LLM", return_value=llm):
                        with mock.patch.object(A, "_uploads", return_value=[]):
                            with mock.patch.object(
                                A,
                                "_search_sources",
                                side_effect=[sources["as_is"], sources["peer"]],
                            ):
                                with mock.patch("builtins.print"):
                                    return A.main()

    def test_each_semantically_invalid_stage3_unit_gets_one_distinct_repair(self):
        invalid_as = self.evidence_response(valid=False)
        invalid_peer = self.evidence_response(peer=True, valid=False)
        invalid_agenda = self.agenda_response(valid=False)
        llm = ScriptedLLM([
            invalid_as,
            self.evidence_response(),
            invalid_peer,
            self.evidence_response(peer=True),
            invalid_agenda,
            self.agenda_response(),
        ])
        sources = self.sources()

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_main_with(directory, llm, sources), 0)
            self.assertTrue(os.path.exists(os.path.join(
                directory, "EXP_stage3_ai_assessment.json")))

        self.assertEqual([call["detail"] for call in llm.calls], [
            "as-is AI assessment",
            "as-is AI assessment [semantic repair 1/1]",
            "peer AI experience",
            "peer AI experience [semantic repair 1/1]",
            "recommended AI agenda",
            "recommended AI agenda [semantic repair 1/1]",
        ])
        request_hashes = {
            A.V.json_call_request_sha256(
                call["system"], call["user"], call["schema"],
                call["pass_name"], call["max_tokens"], call["detail"],
            )
            for call in llm.calls
        }
        self.assertEqual(len(request_hashes), len(llm.calls))
        self.assertIn("This quotation is not in the named source.",
                      llm.calls[1]["user"])
        self.assertIn("NOT-VERIFIED", llm.calls[5]["user"])

    def test_exhausted_country_evidence_repair_stops_before_peer_and_agenda(self):
        llm = ScriptedLLM([
            self.evidence_response(valid=False),
            self.evidence_response(valid=False),
        ])

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                self.run_main_with(directory, llm, self.sources()),
                A.V.NONRETRYABLE_STAGE_EXIT,
            )
            self.assertFalse(os.path.exists(os.path.join(
                directory, "EXP_stage3_ai_assessment.json")))

        self.assertEqual([call["detail"] for call in llm.calls], [
            "as-is AI assessment",
            "as-is AI assessment [semantic repair 1/1]",
        ])

    def test_exhausted_peer_evidence_repair_stops_before_agenda(self):
        llm = ScriptedLLM([
            self.evidence_response(),
            self.evidence_response(peer=True, valid=False),
            self.evidence_response(peer=True, valid=False),
        ])

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                self.run_main_with(directory, llm, self.sources()),
                A.V.NONRETRYABLE_STAGE_EXIT,
            )

        self.assertEqual([call["detail"] for call in llm.calls], [
            "as-is AI assessment",
            "peer AI experience",
            "peer AI experience [semantic repair 1/1]",
        ])

    def test_exhausted_agenda_repair_is_nonretryable_and_bounded(self):
        llm = ScriptedLLM([
            self.evidence_response(),
            self.evidence_response(peer=True),
            self.agenda_response(valid=False),
            self.agenda_response(valid=False),
        ])

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                self.run_main_with(directory, llm, self.sources()),
                A.V.NONRETRYABLE_STAGE_EXIT,
            )

        self.assertEqual([call["detail"] for call in llm.calls], [
            "as-is AI assessment",
            "peer AI experience",
            "recommended AI agenda",
            "recommended AI agenda [semantic repair 1/1]",
        ])

    def test_blank_finding_and_agenda_content_require_semantic_repair(self):
        blank_finding = self.evidence_response()
        blank_finding["findings"][0].update({
            "statement": "  ",
            "dimension": "",
            "why_it_matters": "\t",
            "limitation": "",
        })
        blank_agenda = self.agenda_response()
        blank_agenda["actions"][0].update({
            "priority": "",
            "action": "  ",
            "rationale": "",
            "horizon": "",
            "lead": "",
            "prerequisites": [],
            "risks_and_safeguards": [],
            "indicators": [],
            "evidence_ids": [],
        })
        blank_agenda["sequencing_note"] = ""
        llm = ScriptedLLM([
            blank_finding,
            self.evidence_response(),
            self.evidence_response(peer=True),
            blank_agenda,
            self.agenda_response(),
        ])

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_main_with(directory, llm, self.sources()), 0)

        self.assertEqual([call["detail"] for call in llm.calls], [
            "as-is AI assessment",
            "as-is AI assessment [semantic repair 1/1]",
            "peer AI experience",
            "recommended AI agenda",
            "recommended AI agenda [semantic repair 1/1]",
        ])

    def test_stage3_crash_after_paid_result_resumes_without_transport(self):
        prompt = (
            "COUNTRY UNDER REVIEW: Exampleland\n\nSOURCES:\nsynthetic evidence\n\n"
            "Produce the as-is AI assessment."
        )
        response = {"findings": [], "data_gaps": ["Synthetic gap."]}

        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "stage3-spend.json")
            first_ledger = A.V.Ledger(ceiling=500, label="stage3-first")
            first_ledger.attach(spend_path)
            first = A.V.LLM(
                "anthropic", first_ledger, model="claude-opus-5",
            ).enable_durable_outcomes()
            first._call_anthropic = mock.Mock(return_value=(response, 100, 20))
            self.assertEqual(first.json_call(
                A.SYSTEM, prompt, A.EVIDENCE_SCHEMA, A.PASS,
                max_tokens=5000, detail="as-is AI assessment",
            ), response)

            # Simulate process death before Stage 3 can publish any product/state.
            resumed_ledger = A.V.Ledger(ceiling=500, label="stage3-resumed")
            resumed_ledger.attach(spend_path)
            resumed_ledger.load(spend_path)
            resumed = A.V.LLM(
                "anthropic", resumed_ledger, model="claude-opus-5",
            ).enable_durable_outcomes()
            transport = mock.Mock(side_effect=AssertionError("paid replay"))
            resumed._call_anthropic = transport

            self.assertEqual(resumed.json_call(
                A.SYSTEM, prompt, A.EVIDENCE_SCHEMA, A.PASS,
                max_tokens=5000, detail="as-is AI assessment",
            ), response)
            transport.assert_not_called()
            self.assertEqual(len(resumed_ledger.calls), 1)

    def test_stage3_crash_reuses_paid_retrieval_results_without_transport(self):
        exa_response = {"results": [{
            "title": "Synthetic national AI policy",
            "url": "https://example.gov/ai-policy",
            "publishedDate": "2026-01-01",
        }]}
        contents_response = {
            "results": [{"id": "https://example.gov/ai-policy", "url": "https://example.gov/ai-policy",
                         "text": "Published national AI policy evidence. " * 12}],
            "statuses": [{"id": "https://example.gov/ai-policy", "status": "success"}],
        }

        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "stage3-retrieval-spend.json")
            first_ledger = A.V.Ledger(ceiling=500, label="stage3-first")
            first_ledger.attach(spend_path)
            with mock.patch.dict(os.environ, {
                    "EXA_API_KEY": "test-key", "JINA_API_KEY": "test-key",
            }):
                with mock.patch.object(
                        A.V, "_http", side_effect=[exa_response, contents_response]):
                    first = A._search_sources(
                        ["Exampleland national AI policy"], [], first_ledger, "ASIS")
            self.assertEqual(len(first), 1)

            # The product/state write never happened, but both provider outcomes did.
            resumed_ledger = A.V.Ledger(ceiling=500, label="stage3-resumed")
            resumed_ledger.attach(spend_path)
            resumed_ledger.load(spend_path)
            transport = mock.Mock(side_effect=AssertionError("paid retrieval replay"))
            with mock.patch.dict(os.environ, {
                    "EXA_API_KEY": "test-key", "JINA_API_KEY": "test-key",
            }):
                with mock.patch.object(A.V, "_http", transport):
                    resumed = A._search_sources(
                        ["Exampleland national AI policy"], [], resumed_ledger, "ASIS")

            self.assertEqual(resumed, first)
            transport.assert_not_called()
            self.assertEqual(len(resumed_ledger.calls), 2)
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

    def test_html_is_deterministic_offline_and_distinguishes_proposals(self):
        product = self.product()
        product["recommended_agenda"]["actions"][0]["action"] = (
            "Create <script>alert('unsafe')</script> governance sandbox"
        )

        first = A.render_html(product)
        second = A.render_html(product)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("<!doctype html>"))
        self.assertIn("AI in digital agriculture", first)
        self.assertIn("Evidence coverage", first)
        self.assertIn('role="img"', first)
        self.assertIn("Proposed national agenda", first)
        self.assertIn("not an automatic financing decision", first)
        self.assertIn("&lt;script&gt;alert(&#x27;unsafe&#x27;)&lt;/script&gt;", first)
        self.assertNotIn("<script>", first)
        self.assertNotRegex(first, r"<(?:link|script)[^>]+https?://")


if __name__ == "__main__":
    unittest.main()
