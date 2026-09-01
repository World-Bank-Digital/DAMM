#!/usr/bin/env python3

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scan_stage as S


class ScanStageTest(unittest.TestCase):
    def test_country_and_international_scan_lanes_have_distinct_protected_caps(self):
        ledger = S.V.Ledger(ceiling=100, label="protected-scan-lanes")
        self.assertEqual(ledger.cap("country_research"), 7.5)
        self.assertEqual(ledger.cap("international_lessons"), 7.5)
        searches_to_cap = int(
            ledger.cap("country_research") / S.V.PRICES["exa"]["per_search"]
        )
        ledger.record("exa", "country_research", searches=searches_to_cap)
        with self.assertRaises(S.V.BudgetExhausted):
            ledger.check("country_research")
        # Exhausting Stage 2 does not borrow or consume Stage 4's protected share.
        ledger.check("international_lessons")
        ledger.record("exa", "international_lessons", searches=searches_to_cap)
        with self.assertRaises(S.V.BudgetExhausted):
            ledger.check("international_lessons")
        self.assertEqual(ledger.spent("country_research"), 7.5)
        self.assertEqual(ledger.spent("international_lessons"), 7.5)
        self.assertEqual(ledger.spent(), 15.0)

    def setUp(self):
        self.scans = {
            "country": "Exampleland",
            "iso3": "EXP",
            "assessment_year": 2026,
            "country_findings": [{
                "chapter": 3,
                "statement": "A strategy exists.",
                "quote": "strategy",
                "source_name": "Ministry",
                "source_url": "https://example.gov/strategy.pdf",
                "tier": "T1",
            }],
            "register_entries": [{
                "name": "Farm service",
                "status": "Operating",
                "lead": "Ministry",
                "scale": "100 users",
                "src": "Ministry",
                "src_url": "https://example.gov/service",
                "tier": "T1",
            }],
            "international_pointers": [{
                "chapter": 4,
                "about_country": "Peerland",
                "statement": "A peer published an approach.",
                "why_it_matters": "It demonstrates a delivery option.",
                "quote": "approach",
                "source_name": "Peer ministry",
                "source_url": "https://peer.gov/approach.pdf",
                "tier": "T1",
            }],
        }

    def upload(self, text=None):
        return {
            "id": "u1",
            "filename": "strategy.txt",
            "category": "country_context_documents",
            "mime_type": "text/plain",
            "sha256": "a" * 64,
            "uploaded_at": "2026-08-26T00:00:00Z",
            "extracted_text": (
                text or "Exampleland adopted a national digital agriculture strategy."
            ),
        }

    def raw_upload_finding(self, **overrides):
        chapter = int(S.SC.prescriptive_chapters()[0]["n"])
        value = {
            "chapter": chapter,
            "statement": "A national strategy was adopted.",
            "quote": "Exampleland adopted a national digital agriculture strategy.",
            "upload_id": "u1",
            "about_country": "Exampleland",
            "why_it_matters": "It provides a policy basis for the roadmap.",
            "limitation": "Implementation results are not established.",
            "published_year": 2026,
        }
        value.update(overrides)
        return {
            "findings": [value],
            "document_assessments": [{
                "upload_id": value["upload_id"],
                "status": "used",
                "rationale": "The document contains an exact-quote country finding.",
            }],
            "data_gaps": [],
        }

    def test_country_and_international_are_separate_products(self):
        country = S.build_product(self.scans, "country")
        peer = S.build_product(self.scans, "international")
        self.assertEqual(country["schema_version"], "damm.country-research/v1")
        self.assertNotIn("strategies", country)
        self.assertEqual(peer["schema_version"], "damm.international-lessons/v1")
        self.assertNotIn("country_findings", peer)
        self.assertEqual(S.validate_product(country, "country"), [])
        self.assertEqual(S.validate_product(peer, "international"), [])

    def test_uploads_are_optional_and_change_execution_mode(self):
        autonomous = S.build_product(self.scans, "country")
        assisted = S.build_product(self.scans, "country", [{
            "id": "u1",
            "filename": "plan.pdf",
            "category": "country_context_documents",
            "sha256": "a" * 64,
        }])
        self.assertEqual(autonomous["execution_mode"], "autonomous_research")
        self.assertEqual(assisted["execution_mode"], "upload_assisted")
        self.assertTrue(any(s["source_kind"] == "ttl_upload"
                            for s in assisted["source_inventory"]))

    def test_markdown_states_autonomous_fallback(self):
        text = S.render_markdown(S.build_product(self.scans, "international"),
                                 "international")
        self.assertIn("autonomous research was used", text)
        self.assertIn("not a recommendation to copy", text)

    def test_country_html_is_deterministic_offline_and_visualizes_source_mix(self):
        scans = dict(self.scans)
        scans["country_findings"] = [dict(
            self.scans["country_findings"][0],
            statement="A strategy exists <script>alert('unsafe')</script>.",
        )]
        product = S.build_product(scans, "country")

        first = S.render_html(product, "country")
        second = S.render_html(product, "country")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("<!doctype html>"))
        self.assertIn("Country research and credible-source inventory", first)
        self.assertIn("Source composition", first)
        self.assertIn('role="img"', first)
        self.assertIn("@media print", first)
        self.assertIn("&lt;script&gt;alert(&#x27;unsafe&#x27;)&lt;/script&gt;", first)
        self.assertNotIn("<script>", first)
        self.assertNotRegex(first, r"<(?:link|script)[^>]+https?://")

    def test_international_html_keeps_transfer_boundary_visible(self):
        product = S.build_product(self.scans, "international")

        report = S.render_html(product, "international")

        self.assertIn("International strategies and lessons", report)
        self.assertIn("Adaptation boundary", report)
        self.assertIn("not rankings, endorsements, or proof of transferability", report)
        self.assertIn("Peerland", report)

    def test_upload_cannot_replace_required_international_lesson(self):
        scans = dict(self.scans, international_pointers=[])
        product = S.build_product(scans, "international", [{
            "id": "u1",
            "filename": "peer-plan.pdf",
            "category": "international_strategy_documents",
            "sha256": "a" * 64,
        }])
        self.assertTrue(any("strategies is empty" in error
                            for error in S.validate_product(product, "international")))

    def test_upload_synthesis_requires_exact_quote_and_country_gate(self):
        accepted, refused = S.verify_upload_synthesis(
            self.raw_upload_finding(), [self.upload()], "country", "Exampleland")
        self.assertEqual(len(accepted), 1)
        self.assertEqual(refused, [])
        self.assertEqual(accepted[0]["source_kind"], "ttl_upload")
        self.assertEqual(accepted[0]["source_sha256"], "a" * 64)

        bad_quote = self.raw_upload_finding(quote="This text is not in the upload.")
        accepted, refused = S.verify_upload_synthesis(
            bad_quote, [self.upload()], "country", "Exampleland")
        self.assertEqual(accepted, [])
        self.assertTrue(any("exactly" in reason for reason in refused))

        foreign = self.raw_upload_finding(
            quote="Peerland adopted a national digital agriculture strategy.",
            about_country="Peerland",
        )
        accepted, refused = S.verify_upload_synthesis(
            foreign,
            [self.upload("Peerland adopted a national digital agriculture strategy.")],
            "country",
            "Exampleland",
        )
        self.assertEqual(accepted, [])
        self.assertTrue(refused)

    def test_international_upload_gate_rejects_country_under_review(self):
        accepted, refused = S.verify_upload_synthesis(
            self.raw_upload_finding(), [self.upload()], "international", "Exampleland")
        self.assertEqual(accepted, [])
        self.assertTrue(any("not a precedent" in reason for reason in refused))

    def test_verified_upload_finding_is_in_product_without_full_text(self):
        upload = self.upload()
        accepted, _ = S.verify_upload_synthesis(
            self.raw_upload_finding(), [upload], "country", "Exampleland")
        assessments, assessment_errors = S.verify_document_assessments(
            self.raw_upload_finding(), [upload], accepted)
        self.assertEqual(assessment_errors, [])
        product = S.build_product(
            self.scans, "country", [upload], accepted, ["One gap remains."],
            assessments)
        self.assertTrue(any(row.get("source_kind") == "ttl_upload"
                            for row in product["country_findings"]))
        self.assertNotIn("extracted_text", product["ttl_documents"][0])
        self.assertEqual(product["ttl_documents"][0]["synthesis_status"], "used")
        self.assertEqual(
            product["ttl_documents"][0]["analysis_coverage"]["mode"],
            "full_text",
        )
        self.assertEqual(product["ttl_synthesis_data_gaps"], ["One gap remains."])
        upload_source = next(row for row in product["source_inventory"]
                             if row["source_kind"] == "ttl_upload")
        self.assertEqual(
            upload_source["verified_quote"],
            "Exampleland adopted a national digital agriculture strategy.",
        )

    def test_hash_bound_upload_synthesis_cache_prevents_second_call(self):
        upload = self.upload()
        response = self.raw_upload_finding()

        class FakeLlm:
            def __init__(self):
                self.calls = 0

            def json_call(self, *_args, **_kwargs):
                self.calls += 1
                return response

        with tempfile.TemporaryDirectory() as directory:
            cache = os.path.join(directory, "upload_synthesis.json")
            shared = os.path.join(directory, "scans_spend.json")
            ledger = S.V.Ledger(ceiling=500, label="test")
            llm = FakeLlm()
            first, _, first_assessments = S.synthesize_uploads(
                "Exampleland", "EXP", "country", [upload], ledger, llm,
                cache, shared)
            second, _, second_assessments = S.synthesize_uploads(
                "Exampleland", "EXP", "country", [upload], ledger, None,
                cache, shared)

            self.assertEqual(llm.calls, 1)
            self.assertEqual(first, second)
            self.assertEqual(first_assessments, second_assessments)
            with open(cache, encoding="utf-8") as handle:
                cached = json.load(handle)
            self.assertEqual(
                cached["identity_sha256"],
                S.upload_synthesis_identity(
                    "country", "Exampleland", "EXP", [upload]),
            )

    def test_upload_prompt_substantively_samples_every_large_document(self):
        uploads = []
        for index in range(1, 6):
            marker = f"TAIL-MARKER-{index}"
            upload = dict(
                self.upload("A" * 18000 + marker),
                id=f"u{index}",
                filename=f"strategy-{index}.txt",
                sha256=str(index) * 64,
            )
            uploads.append(upload)

        prompt = S._upload_prompt("Exampleland", "country", uploads)

        for index in range(1, 6):
            self.assertIn(f"[UPLOAD u{index}]", prompt)
            self.assertIn(f"TAIL-MARKER-{index}", prompt)
        self.assertEqual(
            prompt.count(S.UPLOAD_SYNTHESIS_PROMPT_POLICY), len(uploads))

    def test_every_upload_requires_one_consistent_document_assessment(self):
        first = self.upload()
        second = dict(
            self.upload("No relevant evidence is present."),
            id="u2",
            filename="background.txt",
            sha256="b" * 64,
        )
        accepted, refused = S.verify_upload_synthesis(
            self.raw_upload_finding(), [first, second], "country", "Exampleland")
        self.assertEqual(len(accepted), 1)
        self.assertEqual(refused, [])

        assessments, errors = S.verify_document_assessments(
            {
                "document_assessments": [
                    {
                        "upload_id": "u1",
                        "status": "used",
                        "rationale": "It supplied the accepted exact quote.",
                    },
                    {
                        "upload_id": "u2",
                        "status": "no_relevant_evidence",
                        "rationale": "It contains no evidence for a DAR chapter.",
                    },
                ]
            },
            [first, second],
            accepted,
        )
        self.assertEqual(errors, [])
        self.assertEqual([row["upload_id"] for row in assessments], ["u1", "u2"])

        _, errors = S.verify_document_assessments(
            {"document_assessments": assessments[:1]},
            [first, second],
            accepted,
        )
        self.assertTrue(any("omits uploads: u2" in error for error in errors))

    def test_autonomous_lane_completion_requires_every_chapter(self):
        state = {"country": {}, "abstained": {}}
        self.assertFalse(S.autonomous_lane_complete(state, "country"))
        for chapter in S.SC.prescriptive_chapters():
            state["abstained"][f"country:{chapter['n']}"] = {
                "lane": "country", "chapter": chapter["n"], "why": "not found",
            }
        self.assertTrue(S.autonomous_lane_complete(state, "country"))

    def test_lane_spend_is_delta_from_frozen_shared_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            shared = os.path.join(directory, "run_scans_spend.json")
            lane = os.path.join(directory, "run_international_lessons_spend.json")
            with open(shared, "w", encoding="utf-8") as handle:
                json.dump({"summary": {"total": 12.5}}, handle)

            started = S.checkpoint_lane_spend("international", shared, lane)
            self.assertEqual(started["summary"]["total"], 0.0)
            self.assertEqual(
                started["shared_ledger"]["baseline_total_usd"], 12.5)

            with open(shared, "w", encoding="utf-8") as handle:
                json.dump({"summary": {"total": 19.75}}, handle)
            finished = S.checkpoint_lane_spend(
                "international", shared, lane, complete=True)

            self.assertEqual(finished["schema_version"], "damm.stage-spend/v1")
            self.assertEqual(finished["status"], "complete")
            self.assertEqual(finished["summary"]["total"], 7.25)
            self.assertEqual(finished["shared_ledger"]["before_total_usd"], 12.5)
            self.assertEqual(finished["shared_ledger"]["after_total_usd"], 19.75)
            self.assertEqual(finished["shared_ledger"]["path"],
                             "run_scans_spend.json")
            self.assertEqual(len(finished["shared_ledger"]["sha256"]), 64)

    def test_lane_spend_keeps_original_baseline_across_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            shared = os.path.join(directory, "run_scans_spend.json")
            lane = os.path.join(directory, "run_country_research_spend.json")
            with open(shared, "w", encoding="utf-8") as handle:
                json.dump({"summary": {"total": 0.0}}, handle)
            S.checkpoint_lane_spend("country", shared, lane)

            with open(shared, "w", encoding="utf-8") as handle:
                json.dump({"summary": {"total": 4.0}}, handle)
            S.checkpoint_lane_spend("country", shared, lane)
            with open(shared, "w", encoding="utf-8") as handle:
                json.dump({"summary": {"total": 6.5}}, handle)
            finished = S.checkpoint_lane_spend(
                "country", shared, lane, complete=True)

            self.assertEqual(finished["summary"]["total"], 6.5)
            self.assertEqual(
                finished["shared_ledger"]["baseline_total_usd"], 0.0)
            self.assertEqual(finished["shared_ledger"]["before_total_usd"], 4.0)


if __name__ == "__main__":
    unittest.main()
