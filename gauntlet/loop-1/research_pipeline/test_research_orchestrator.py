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
