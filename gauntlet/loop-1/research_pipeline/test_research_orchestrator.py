#!/usr/bin/env python3
"""Focused failure-boundary tests for canonical Stage 1 retrieval."""

import os
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import research_orchestrator as R


class ResearchOrchestratorRetrievalTest(unittest.TestCase):
    @staticmethod
    def spec():
        return {
            "id": "1.1",
            "name": "Synthetic indicator",
            "description": "Synthetic construct",
            "open_question": "",
        }

    def test_all_failed_discovery_requests_cannot_be_published_as_evidence_absence(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["first query", "second query"],
            "likely_publishers": [],
        }
        ledger = object()

        with mock.patch.object(
                R.V, "exa_search",
                side_effect=R.V.VendorError("discovery transport failed")):
            with mock.patch.object(
                    R.V, "perplexity_citations",
                    return_value={"citations": [], "lead_prose": "", "error": ""}):
                with self.assertRaisesRegex(
                        RuntimeError, "every Exa discovery request failed"):
                    R.retrieve(
                        self.spec(), "Exampleland", llm, ledger,
                        log=lambda _message: None,
                    )

    def test_ambiguous_exa_outcome_propagates_instead_of_becoming_a_gap(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["one query"], "likely_publishers": [],
        }
        ambiguous = R.V.VendorTransportAmbiguous(
            vendor="exa", model="", pass_name="research", detail="one query",
            max_tokens=0, input_tokens=0, output_tokens=0,
        )

        with mock.patch.object(R.V, "exa_search", side_effect=ambiguous):
            with mock.patch.object(
                    R.V, "perplexity_citations",
                    return_value={"citations": [], "lead_prose": "", "error": ""}):
                with self.assertRaises(R.V.VendorTransportAmbiguous):
                    R.retrieve(
                        self.spec(), "Exampleland", llm, object(),
                        log=lambda _message: None,
                    )

    def test_explicit_reader_rejections_do_not_abort_other_verified_evidence(self):
        """A 409/422 page response is a rejected source, not a failed row.

        The paid Nigeria canary failed Stage 1 when Jina explicitly rejected one
        URL while another selected source could still be read.  The row must retain
        the usable page and let downstream evidence rules decide its outcome.
        """
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland Synthetic indicator"],
            "likely_publishers": [],
        }
        discovery = [
            {
                "title": "Reader rejects this URL with a budget response",
                "url": "https://example.test/rejected-409",
                "published": "2026-01-01",
            },
            {
                "title": "Reader rejects this URL as malformed",
                "url": "https://example.test/rejected-422",
                "published": "2026-01-01",
            },
            {
                "title": "Usable published source",
                "url": "https://example.test/usable",
                "published": "2026-01-01",
            },
        ]

        def fetch(url, *_args, **_kwargs):
            if url.endswith("/rejected-409"):
                raise R.V.JinaSourceRejected(
                    "synthetic Reader 409 BudgetExceededError")
            if url.endswith("/rejected-422"):
                raise R.V.JinaSourceRejected(
                    "synthetic Reader 422 SubmittedDataMalformed")
            return "Verified source evidence. " * 20

        messages = []
        with mock.patch.object(R.V, "exa_search", return_value=discovery):
            with mock.patch.object(R.V, "perplexity_citations", return_value={
                    "citations": [], "lead_prose": "", "error": "",
            }):
                with mock.patch.object(R.V, "jina_fetch", side_effect=fetch):
                    pack, _plan, _peer, _construct = R.retrieve(
                        self.spec(), "Exampleland", llm, object(),
                        log=messages.append,
                    )

        self.assertEqual([item["url"] for item in pack], [
            "https://example.test/usable",
        ])
        self.assertEqual(sum("Reader rejected" in message for message in messages), 2)

    def test_all_explicit_reader_rejections_stop_without_claiming_evidence_absence(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland Synthetic indicator"],
            "likely_publishers": [],
        }
        discovery = [
            {
                "title": "Over-budget page",
                "url": "https://example.test/rejected-409",
                "published": "2026-01-01",
            },
            {
                "title": "Malformed page",
                "url": "https://example.test/rejected-422",
                "published": "2026-01-01",
            },
        ]

        def reject(url, *_args, **_kwargs):
            code = "409 BudgetExceededError" if url.endswith("409") else "422 SubmittedDataMalformed"
            raise R.V.JinaSourceRejected(f"synthetic Reader {code}")

        with mock.patch.object(R.V, "exa_search", return_value=discovery):
            with mock.patch.object(R.V, "perplexity_citations", return_value={
                    "citations": [], "lead_prose": "", "error": "",
            }):
                with mock.patch.object(R.V, "jina_fetch", side_effect=reject):
                    with self.assertRaisesRegex(
                            R.SelectedReaderEvidenceUnavailable,
                            "evidence absence cannot be established") as caught:
                        R.retrieve(
                            self.spec(), "Exampleland", llm, object(),
                            log=lambda _message: None,
                        )
        self.assertEqual(
            R.V.stage_failure_exit(caught.exception),
            R.V.NONRETRYABLE_STAGE_EXIT,
        )

    def test_ambiguous_reader_outcome_still_propagates(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland Synthetic indicator"],
            "likely_publishers": [],
        }
        ambiguous = R.V.VendorTransportAmbiguous(
            vendor="jina", model="", pass_name="research", detail="synthetic",
            max_tokens=500, input_tokens=0, output_tokens=500,
        )
        discovery = [{
            "title": "Uncertain billing result",
            "url": "https://example.test/ambiguous",
            "published": "2026-01-01",
        }]

        with mock.patch.object(R.V, "exa_search", return_value=discovery):
            with mock.patch.object(R.V, "perplexity_citations", return_value={
                    "citations": [], "lead_prose": "", "error": "",
            }):
                with mock.patch.object(R.V, "jina_fetch", side_effect=ambiguous):
                    with self.assertRaises(R.V.VendorTransportAmbiguous):
                        R.retrieve(
                            self.spec(), "Exampleland", llm, object(),
                            log=lambda _message: None,
                        )

    def test_unclassified_reader_rejection_propagates_instead_of_becoming_a_gap(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland Synthetic indicator"],
            "likely_publishers": [],
        }
        discovery = [{
            "title": "Unclassified endpoint rejection",
            "url": "https://example.test/unclassified",
            "published": "2026-01-01",
        }]

        with mock.patch.object(R.V, "exa_search", return_value=discovery):
            with mock.patch.object(R.V, "perplexity_citations", return_value={
                    "citations": [], "lead_prose": "", "error": "",
            }):
                with mock.patch.object(
                        R.V, "jina_fetch",
                        side_effect=R.V.VendorHTTPRejected(
                            "synthetic unclassified Reader rejection")):
                    with self.assertRaises(R.V.VendorHTTPRejected):
                        R.retrieve(
                            self.spec(), "Exampleland", llm, object(),
                            log=lambda _message: None,
                        )

    def test_all_too_short_reader_pages_stop_without_a_data_gap(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland Synthetic indicator"],
            "likely_publishers": [],
        }
        discovery = [{
            "title": "Short landing page",
            "url": "https://example.test/short",
            "published": "2026-01-01",
        }]

        with mock.patch.object(R.V, "exa_search", return_value=discovery):
            with mock.patch.object(R.V, "perplexity_citations", return_value={
                    "citations": [], "lead_prose": "", "error": "",
            }):
                with mock.patch.object(R.V, "jina_fetch", return_value="brief"):
                    with self.assertRaisesRegex(
                            R.SelectedReaderEvidenceUnavailable,
                            "evidence absence cannot be established"):
                        R.retrieve(
                            self.spec(), "Exampleland", llm, object(),
                            log=lambda _message: None,
                        )

    def test_no_discovered_pages_still_returns_empty_evidence_pack(self):
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland Synthetic indicator"],
            "likely_publishers": [],
        }

        with mock.patch.object(R.V, "exa_search", return_value=[]):
            with mock.patch.object(R.V, "perplexity_citations", return_value={
                    "citations": [], "lead_prose": "", "error": "",
            }):
                pack, _plan, _peer, _construct = R.retrieve(
                    self.spec(), "Exampleland", llm, object(),
                    log=lambda _message: None,
                )

        self.assertEqual(pack, [])

    def test_parallel_rows_share_one_identical_page_fetch_without_missing_evidence(self):
        workers = R.ROW_WORKERS
        start = threading.Barrier(workers)
        llm = mock.Mock()
        llm.json_call.return_value = {
            "queries": ["Exampleland Synthetic indicator"],
            "likely_publishers": [],
        }
        ledger = R.V.Ledger(ceiling=500, label="parallel-stage1")
        discovery = [{
            "title": "Shared national publication",
            "url": "https://example.test/shared-publication",
            "published": "2026-01-01",
        }]
        page = "Published evidence for every synthetic row. " * 20

        def transport(*_args, **_kwargs):
            time.sleep(0.05)
            return {"data": {"content": page, "usage": {"tokens": 100}}}

        def retrieve(index):
            start.wait(timeout=2)
            spec = dict(self.spec(), id=f"1.{index + 1}")
            return R.retrieve(
                spec, "Exampleland", llm, ledger,
                log=lambda _message: None,
            )

        with mock.patch.object(R.V, "exa_search", return_value=discovery):
            with mock.patch.object(R.V, "perplexity_citations", return_value={
                    "citations": [], "lead_prose": "", "error": "",
            }):
                with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                    with mock.patch.object(
                            R.V, "_http", side_effect=transport) as http:
                        with ThreadPoolExecutor(max_workers=workers) as pool:
                            results = list(pool.map(retrieve, range(workers)))

        self.assertEqual(http.call_count, 1)
        self.assertEqual(len(ledger.calls), 1)
        self.assertTrue(all(len(pack) == 1 for pack, *_rest in results))


if __name__ == "__main__":
    unittest.main()
