#!/usr/bin/env python3
"""Paid accounting breaches must escape every evidence fallback."""

import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ai_assessment as A
import foresight as F
import research_orchestrator as R
import scans as S
import vendors as V


def _usage_exceeded(vendor, pass_name):
    return V.VendorUsageExceededReservation(
        vendor=vendor, model="", pass_name=pass_name,
        reserved=0.01, actual=0.02,
    )


def _ambiguous(vendor, pass_name):
    return V.VendorTransportAmbiguous(
        vendor=vendor, model="", pass_name=pass_name, detail="synthetic",
        max_tokens=500, input_tokens=0, output_tokens=500,
    )


def _pending(vendor, pass_name):
    return V.VendorRequestPending(
        vendor=vendor, model="", pass_name=pass_name,
        request_sha256="a" * 64, headroom=0.01,
    )


class TerminalPaidOutcomePropagationTest(unittest.TestCase):
    def setUp(self):
        # Existing cases inject terminal outcomes at the Reader boundary.
        self.enterContext(mock.patch.object(V, "exa_contents", return_value=""))

    def test_operator_docs_do_not_claim_old_ledgers_are_automatically_repriced(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as handle:
            readme = handle.read()
        self.assertIn("does not retroactively reprice", readme)
        self.assertNotIn(
            "a wrong price is a one-line correction rather than a re-run", readme)

    def test_public_tariff_audit_omits_private_account_funding_state(self):
        with open(os.path.join(
                HERE, "PROVIDER-TARIFF-AUDIT-2026-09-03.md"),
                encoding="utf-8") as handle:
            audit = handle.read().casefold()
        self.assertNotIn("auto-top-up was already enabled", audit)
        self.assertNotIn("balances consistent with both package sizes", audit)

    def test_stage1_perplexity_overage_escapes_peer_unavailable_fallback(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland indicator"], "likely_publishers": [],
        }
        error = _usage_exceeded("perplexity", "research")

        with mock.patch.object(R.V, "exa_search", return_value=[]):
            with mock.patch.object(
                    R.V, "perplexity_citations", side_effect=error):
                with self.assertRaises(V.VendorUsageExceededReservation):
                    R.retrieve(
                        {"id": "1.1", "name": "Indicator",
                         "description": "Construct", "open_question": ""},
                        "Exampleland", llm, object(),
                        log=lambda _message: None,
                    )

    def test_stage3_pending_search_escapes_discovery_fallback(self):
        error = _pending("exa", "ai")
        with mock.patch.object(A.V, "exa_search", side_effect=error):
            with self.assertRaises(V.VendorRequestPending):
                A._search_sources(["query"], [], object(), "ASIS")

    def test_stage3_unmetered_reader_response_escapes_fetch_fallback(self):
        ledger = V.Ledger(ceiling=500, label="unmetered-stage3")
        discovery = [{
            "title": "Source", "url": "https://example.test/source",
            "published": "2026-01-01",
        }]
        with mock.patch.object(A.V, "exa_search", return_value=discovery):
            with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                with mock.patch.object(A.V, "_http", return_value={
                        "data": {"content": "unmetered content"}}):
                    with self.assertRaises(V.VendorError):
                        A._search_sources(["query"], [], ledger, "ASIS")

    def test_stage3_explicit_reader_rejection_can_still_degrade(self):
        discovery = [{
            "title": "Source", "url": "https://example.test/source",
            "published": "2026-01-01",
        }]
        with mock.patch.object(A.V, "exa_search", return_value=discovery):
            with mock.patch.object(
                    A.V, "jina_fetch",
                    side_effect=V.JinaSourceRejected("synthetic 422")):
                self.assertEqual(
                    A._search_sources(["query"], [], object(), "ASIS"), [])

    def test_stage5_ambiguous_search_escapes_discovery_fallback(self):
        error = _ambiguous("exa", "foresight")
        with mock.patch.object(F.V, "exa_search", side_effect=error):
            with self.assertRaises(V.VendorTransportAmbiguous):
                F.foresight_context_sources("Exampleland", [], object())

    def test_stage2_or_4_ambiguous_fetch_escapes_page_fallback(self):
        discovery = [{
            "title": "Foreign strategy",
            "url": "https://peer.example/strategy",
        }]
        error = _ambiguous("jina", "scans")
        with mock.patch.object(S.V, "exa_search", return_value=discovery):
            with mock.patch.object(S.V, "jina_fetch", side_effect=error):
                with self.assertRaises(V.VendorTransportAmbiguous):
                    S._search_and_fetch(
                        ["query"], object(), lambda _message: None,
                    )


if __name__ == "__main__":
    unittest.main()
