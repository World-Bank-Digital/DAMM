"""Synthetic HTTP-to-evidence coverage for the shared retrieval policy."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import research_orchestrator as R
import ai_assessment as A
import foresight as F
import scans as S
import vendors as V


PAGE = "The synthetic survey measured rural advisory reach at 42 percent. " * 12
URL = "https://worldbank.org/synthetic-source"


class SourceRetrievalTest(unittest.TestCase):
    def test_duplicate_search_results_preserve_available_usable_page_text(self):
        llm = mock.Mock()
        llm.json_call.return_value = {"queries": ["first", "second"]}
        consumers = {
            "diagnostic": lambda ledger: R.retrieve(
                {"id": "1.1", "name": "Indicator", "description": "Reach", "open_question": ""},
                "Exampleland", llm, ledger, lambda _: None)[0],
            "country_and_international": lambda ledger: S._search_and_fetch(
                ["first", "second"], ledger, lambda _: None),
        }
        for label, consume in consumers.items():
            for first in ("", "short", " " * 300):
                with self.subTest(stage=label, first=first):
                    def search(query, *_args, **_kwargs):
                        return [{"url": URL, "title": "Synthetic",
                                 "text": PAGE if query == "second" else first}]
                    with mock.patch.object(V, "exa_search", side_effect=search), \
                            mock.patch.object(V, "perplexity_citations", return_value={"citations": []}), \
                            mock.patch.object(V, "jina_fetch", side_effect=V.VendorPaidRequestTerminal("synthetic")) as reader:
                        pages = consume(V.Ledger(ceiling=1))
                    self.assertEqual(len(pages), 1)
                    self.assertEqual(pages[0]["text"], PAGE)
                    self.assertEqual(pages[0]["url"], URL)
                    self.assertEqual(pages[0]["retrieval_provider"], "exa")
                    reader.assert_not_called()

    def test_missing_or_short_extractive_text_uses_reader_and_restarts_offline(self):
        for excerpt in (None, "", "short excerpt", " " * 250):
            with self.subTest(excerpt=excerpt), tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / "spend.json")
                ledger = V.Ledger(ceiling=1, label="synthetic")
                ledger.attach(path)
                page = {"url": URL, "text": excerpt,
                        "summary": "Generated summary. " * 100,
                        "lead_prose": "Generated discovery lead. " * 100}
                payload = {"code": 200, "status": 20000, "data": {
                    "content": PAGE, "usage": {"tokens": 100}}}
                with mock.patch.dict(os.environ, {"JINA_API_KEY": "synthetic"}), \
                        mock.patch.object(V.urllib.request, "urlopen",
                            return_value=io.BytesIO(json.dumps(payload).encode())) as http:
                    result = V.read_source(page, ledger, "research", max_chars=400)
                    self.assertEqual(result, {"text": PAGE[:400], "retrieval_provider": "jina"})
                    self.assertEqual(http.call_count, 1)
                    restarted = V.Ledger(ceiling=1, label="synthetic restart")
                    restarted.attach(path)
                    restarted.load(path)
                    self.assertEqual(V.read_source(page, restarted, "research", max_chars=400), result)
                    self.assertEqual(http.call_count, 1)
                    self.assertEqual(restarted.spent(), ledger.spent())

    def test_extractive_text_is_bounded_without_another_paid_request(self):
        with mock.patch.object(V, "jina_fetch", side_effect=AssertionError("unexpected Reader")):
            result = V.read_source({"url": URL, "text": PAGE},
                                   V.Ledger(ceiling=1), "research", max_chars=400)
        self.assertEqual(result, {"text": PAGE[:400], "retrieval_provider": "exa"})

    def test_terminal_reader_fallback_propagates_through_every_research_consumer(self):
        llm = mock.Mock()
        llm.json_call.return_value = {"queries": ["Exampleland Indicator"]}
        consumers = {
            "diagnostic": lambda ledger: R.retrieve(
                {"id": "1.1", "name": "Indicator", "description": "Reach", "open_question": ""},
                "Exampleland", llm, ledger, lambda _: None),
            "country_and_international": lambda ledger: S._search_and_fetch(
                ["synthetic"], ledger, lambda _: None),
            "ai_assessment": lambda ledger: A._search_sources(["synthetic"], [], ledger, "AI"),
            "foresight": lambda ledger: F.foresight_context_sources("Exampleland", [], ledger),
        }
        for label, consume in consumers.items():
            with self.subTest(stage=label):
                ledger = V.Ledger(ceiling=1)
                with mock.patch.object(V, "exa_search", return_value=[{
                        "url": URL, "title": "Synthetic", "text": "short"}]), \
                        mock.patch.object(V, "perplexity_citations", return_value={"citations": []}), \
                        mock.patch.object(V, "jina_fetch", side_effect=V.VendorPaidRequestTerminal("synthetic")) as reader:
                    with self.assertRaises(V.VendorPaidRequestTerminal):
                        consume(ledger)
                    self.assertEqual(reader.call_count, 1)

    def test_all_research_consumers_use_extractive_page_text(self):
        consumers = {
            "country_and_international_scans": lambda ledger: S._search_and_fetch(
                ["synthetic"], ledger, lambda _: None),
            "ai_assessment": lambda ledger: A._search_sources(["synthetic"], [], ledger, "AI"),
            "foresight": lambda ledger: F.foresight_context_sources("Exampleland", [], ledger),
        }
        for label, consume in consumers.items():
            with self.subTest(stage=label):
                def respond(request, **_kwargs):
                    if request.full_url != "https://api.exa.ai/search":
                        raise V.urllib.error.HTTPError(request.full_url, 422, "Rejected", {},
                            io.BytesIO(b'{"code":422,"status":42206,"name":"AssertionFailureError"}'))
                    wants_text = "text" in json.loads(request.data).get("contents", {})
                    return io.BytesIO(json.dumps({"results": [{
                        "url": URL, "title": "Synthetic survey", "text": PAGE if wants_text else "",
                    }]}).encode())
                ledger = V.Ledger(ceiling=1, label="synthetic")
                with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic", "JINA_API_KEY": "synthetic"}), \
                        mock.patch.object(V.urllib.request, "urlopen", side_effect=respond):
                    pages = consume(ledger)
                self.assertEqual(len(pages), 1)
                self.assertEqual(pages[0]["text"], PAGE)
                self.assertEqual(pages[0]["retrieval_provider"], "exa")
                self.assertTrue(all(call["vendor"] == "exa" for call in ledger.calls))

    def test_stage1_uses_source_text_already_returned_by_search_and_restarts_offline(self):
        requests = []

        def respond(request, **_kwargs):
            requests.append(request)
            if request.full_url != "https://api.exa.ai/search":
                raise V.urllib.error.HTTPError(request.full_url, 422, "Rejected", {},
                    io.BytesIO(b'{"code":422,"status":42206,"name":"AssertionFailureError"}'))
            return io.BytesIO(json.dumps({"results": [{
                "url": URL, "title": "Synthetic survey", "text": PAGE,
                "summary": "This generated summary must not become evidence.",
            }]}).encode())

        llm = mock.Mock()
        llm.json_call.return_value = {"queries": ["Exampleland Indicator"], "likely_publishers": []}
        spec = {"id": "1.1", "name": "Indicator", "description": "Reach", "open_question": ""}
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "spend.json")
            ledger = V.Ledger(ceiling=1, label="synthetic")
            ledger.attach(path)
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic", "JINA_API_KEY": "synthetic"}), \
                    mock.patch.object(V.urllib.request, "urlopen", side_effect=respond), \
                    mock.patch.object(V, "perplexity_citations", return_value={
                        "citations": [URL], "lead_prose": "Generated lead is not evidence."}):
                pack, *_ = R.retrieve(spec, "Exampleland", llm, ledger, lambda _: None)
                self.assertEqual(len(pack), 1)
                self.assertEqual(pack[0]["text"], PAGE)
                self.assertEqual(pack[0]["retrieval_provider"], "exa")
                self.assertTrue(V.quote_verify("rural advisory reach at 42 percent", pack[0]["text"]))
                self.assertFalse(V.quote_verify("Generated lead is not evidence", pack[0]["text"]))
                self.assertEqual(len(requests), 1)
                self.assertEqual(json.loads(requests[0].data)["contents"],
                                 {"text": {"maxCharacters": 18000}})
                self.assertEqual(ledger.spent(), 0.007)
                resumed = V.Ledger(ceiling=1, label="synthetic restart")
                resumed.attach(path)
                resumed.load(path)
                pack, *_ = R.retrieve(spec, "Exampleland", llm, resumed, lambda _: None)
                self.assertEqual(pack[0]["text"], PAGE)
                self.assertEqual(len(requests), 1)
                self.assertEqual(resumed.spent(), 0.007)


if __name__ == "__main__":
    unittest.main()
