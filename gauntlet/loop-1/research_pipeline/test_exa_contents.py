"""Bounded citation retrieval at the real HTTP and durable-ledger boundaries."""
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest import mock

import vendors as V

URL = "https://example.test/citation"
PAGE = "A synthetic country publication reports rural coverage at 42 percent. " * 20


def page_response(**changes):
    return {"results": [{"id": URL, "url": URL, "text": PAGE}],
            "statuses": [{"id": URL, "status": "success"}],
            "costDollars": {"total": 0.001}, **changes}


class ExaContentsTest(unittest.TestCase):
    def test_document_id_can_differ_when_requested_status_and_result_url_match(self):
        # Sanitized live PDF response captured 2026-09-06: Exa's document ID
        # differs from the request, while status.id and result.url match it.
        payload = page_response(results=[{
            "id": "https://example.test/document-identity",
            "url": URL, "text": PAGE,
        }])
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "spend.json")
            ledger = V.Ledger(ceiling=1)
            ledger.attach(path)
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                    mock.patch.object(V.urllib.request, "urlopen",
                        return_value=io.BytesIO(json.dumps(payload).encode())) as http, \
                    mock.patch.object(V, "jina_fetch", side_effect=AssertionError("Reader called")):
                source = {"url": URL}
                self.assertEqual(V.read_source(source, ledger, "research"),
                                 {"text": PAGE, "retrieval_provider": "exa"})
                restarted = V.Ledger(ceiling=1)
                restarted.attach(path)
                restarted.load(path)
                self.assertEqual(V.read_source(source, restarted, "research")["text"], PAGE)
                self.assertEqual(http.call_count, 1)
                self.assertAlmostEqual(restarted.spent(), .001)
                self.assertEqual(restarted.summary()["unresolved_reservations"], 0)

    def test_unknown_http_transport_and_malformed_results_never_fallback_or_replay(self):
        cases = []
        for status, tag in [(401, "INVALID_API_KEY"), (402, "NO_MORE_CREDITS"),
                            (403, "ACCESS_DENIED"), (429, "RATE_LIMIT_EXCEEDED"),
                            (500, "DEFAULT_ERROR"), (422, "UNKNOWN"),
                            (401, "FETCH_DOCUMENT_ERROR"), (403, "SOURCE_NOT_AVAILABLE")]:
            cases.append((f"http-{status}-{tag}", lambda s=status, t=tag:
                V.urllib.error.HTTPError("https://api.exa.ai/contents", s, "Rejected", {},
                    io.BytesIO(json.dumps({"tag": t, "error": "SYNTHETIC_PRIVATE_DETAIL"}).encode()))))
        cases.append(("transport", lambda: V.urllib.error.URLError("SYNTHETIC_PRIVATE_DETAIL")))
        malformed = [None, {}, {"results": []}, page_response(statuses=[]),
                     page_response(results=[{"id": URL, "url": URL, "text": 42}]),
                     page_response(statuses=[{"id": URL + "/other", "status": "success"}]),
                     page_response(results=[{"id": None, "url": URL, "text": PAGE}]),
                     page_response(results=[{"id": URL, "url": "https://other.test/unrelated", "text": PAGE}]),
                     page_response(results=[{"id": URL, "url": URL, "text": PAGE + "\ud800"}]),
                     page_response(results=[], statuses=[{"id": URL, "status": "error", "error": {
                         "tag": "CRAWL_UNKNOWN_ERROR", "httpStatusCode": 500}}]),
                     page_response(results=[], statuses=[{"id": URL, "status": "error", "error": {
                         "tag": [], "httpStatusCode": 404}}]),
                     page_response(costDollars={"total": True}),
                     page_response(costDollars={"total": -1}),
                     page_response(costDollars={"total": "0.001"})]
        malformed.append(page_response(costDollars={"total": 10 ** 400}))
        for document_id in ("", "  ", True, 42, [], {}):
            malformed.append(page_response(results=[{
                "id": document_id, "url": URL, "text": PAGE}]))
        for i, payload in enumerate(malformed):
            cases.append((f"malformed-{i}", lambda p=payload: io.BytesIO(json.dumps(p).encode())))
        for i, raw in enumerate([b'\xff', b'{"results":[],"results":[],"statuses":[]}', b'{"x":NaN}']):
            cases.append((f"invalid-json-{i}", lambda r=raw: io.BytesIO(r)))
        for name, response in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "spend.json")
                ledger = V.Ledger(ceiling=1)
                ledger.attach(path)
                def respond(*_args, **_kwargs):
                    value = response()
                    if isinstance(value, Exception):
                        raise value
                    return value
                with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                        mock.patch.object(V.urllib.request, "urlopen", side_effect=respond) as http, \
                        mock.patch.object(V, "jina_fetch", side_effect=AssertionError("Reader called")) as reader:
                    with self.assertRaises(V.VendorPaidRequestTerminal):
                        V.read_source({"url": URL}, ledger, "research")
                    self.assertAlmostEqual(ledger.spent(), 0.001)
                    self.assertEqual(ledger.summary()["unresolved_reservations"], 0)
                    restarted = V.Ledger(ceiling=1)
                    restarted.attach(path)
                    restarted.load(path)
                    with self.assertRaises(V.VendorPaidRequestTerminal):
                        V.read_source({"url": URL}, restarted, "research")
                    self.assertEqual(http.call_count, 1)
                    reader.assert_not_called()
                    self.assertNotIn("SYNTHETIC_PRIVATE_DETAIL", Path(path).read_text())

    def test_invalid_cost_keeps_safe_reason_after_restart_without_reissue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "spend.json")
            ledger = V.Ledger(ceiling=1)
            ledger.attach(path)
            response = page_response(costDollars={"total": "SYNTHETIC_PRIVATE_DETAIL"})
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                    mock.patch.object(V.urllib.request, "urlopen",
                        return_value=io.BytesIO(json.dumps(response).encode())) as http:
                with self.assertRaises(V.VendorUsageUnmetered) as first:
                    V.read_source({"url": URL}, ledger, "research")
                self.assertEqual(first.exception.detail, "exa_contents_cost_invalid")
                self.assertEqual(ledger.calls[-1]["structured_result"]["failure"],
                                 {"kind": "exa_contents_cost_invalid"})
                restarted = V.Ledger(ceiling=1)
                restarted.attach(path)
                restarted.load(path)
                with self.assertRaises(V.VendorUsageUnmetered) as replay:
                    V.read_source({"url": URL}, restarted, "research")
                self.assertEqual(replay.exception.detail, first.exception.detail)
                self.assertEqual(http.call_count, 1)
                self.assertAlmostEqual(restarted.spent(), 0.001)
                self.assertEqual(restarted.summary()["unresolved_reservations"], 0)
                self.assertNotIn("SYNTHETIC_PRIVATE_DETAIL", Path(path).read_text())
                self.assertNotIn(URL, Path(path).read_text())

    def test_content_rejection_keeps_the_distinguishing_safe_reason(self):
        cases = [
            (None, "exa_contents_envelope_invalid"),
            ({}, "exa_contents_statuses_invalid"),
            (page_response(statuses=[]), "exa_contents_statuses_invalid"),
            (page_response(statuses=[{"id": URL + "/other", "status": "success"}]),
             "exa_contents_status_identity_mismatch"),
            (page_response(results=[]), "exa_contents_results_invalid"),
            (page_response(results=[None]), "exa_contents_result_invalid"),
            (page_response(results=[{"id": None, "url": URL, "text": PAGE}]),
             "exa_contents_result_invalid"),
            (page_response(results=[{"id": URL, "url": URL + "/other", "text": PAGE}]),
             "exa_contents_result_identity_mismatch"),
            (page_response(results=[{"id": URL, "url": URL}]),
             "exa_contents_text_invalid"),
            (page_response(results=[{"id": URL, "url": URL, "text": 42}]),
             "exa_contents_text_invalid"),
            (page_response(results=[{"id": URL, "url": URL, "text": []}]),
             "exa_contents_text_invalid"),
            (page_response(results=[{"id": URL, "url": URL, "text": {}}]),
             "exa_contents_text_invalid"),
            (page_response(results=[{"id": URL, "url": URL, "text": PAGE + "\ud800"}]),
             "exa_contents_text_encoding_invalid"),
            (page_response(statuses=[{"id": URL, "status": "SYNTHETIC_PRIVATE_DETAIL"}]),
             "exa_contents_status_unclassified"),
            (page_response(results=[], statuses=[{"id": URL, "status": "error", "error": {
                "tag": "SYNTHETIC_PRIVATE_DETAIL", "httpStatusCode": 500}}]),
             "exa_contents_source_error_unclassified"),
            (page_response(statuses=[{"id": URL, "status": "error", "error": {
                "tag": "CRAWL_NOT_FOUND", "httpStatusCode": 404}}]),
             "exa_contents_error_result_conflict"),
        ]
        for response, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "spend.json")
                ledger = V.Ledger(ceiling=1)
                ledger.attach(path)
                with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                        mock.patch.object(V.urllib.request, "urlopen",
                            return_value=io.BytesIO(json.dumps(response).encode())) as http:
                    with self.assertRaises(V.VendorUsageUnmetered) as first:
                        V.read_source({"url": URL}, ledger, "research")
                    self.assertEqual(first.exception.detail, reason)
                    self.assertEqual(ledger.calls[-1]["structured_result"]["failure"],
                                     {"kind": reason})
                    restarted = V.Ledger(ceiling=1)
                    restarted.attach(path)
                    restarted.load(path)
                    with self.assertRaises(V.VendorUsageUnmetered) as replay:
                        V.read_source({"url": URL}, restarted, "research")
                    self.assertEqual(replay.exception.detail, reason)
                    self.assertEqual(http.call_count, 1)
                    self.assertAlmostEqual(restarted.spent(), 0.001)
                    self.assertEqual(restarted.summary()["unresolved_reservations"], 0)
                    self.assertNotIn("SYNTHETIC_PRIVATE_DETAIL", Path(path).read_text())
                    self.assertNotIn(URL, Path(path).read_text())

    def test_legacy_or_untrusted_diagnostic_checkpoint_never_reissues(self):
        for failure in [None, {"kind": "SYNTHETIC_PRIVATE_DETAIL"},
                        {"kind": []}, {"kind": "exa_contents_cost_invalid", "url": URL}]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "spend.json")
                ledger = V.Ledger(ceiling=1)
                ledger.attach(path)
                with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                        mock.patch.object(V.urllib.request, "urlopen",
                            return_value=io.BytesIO(b"{}")) as http:
                    with self.assertRaises(V.VendorUsageUnmetered):
                        V.read_source({"url": URL}, ledger, "research")
                    saved = json.loads(Path(path).read_text())
                    journal = saved["calls"][-1]["structured_result"]
                    if failure is None:
                        del journal["failure"]
                    else:
                        journal["failure"] = failure
                    Path(path).write_text(json.dumps(saved))
                    restarted = V.Ledger(ceiling=1)
                    restarted.attach(path)
                    restarted.load(path)
                    with self.assertRaises(V.VendorPaidRequestTerminal) as replay:
                        V.read_source({"url": URL}, restarted, "research")
                    if failure is None:
                        self.assertIsInstance(replay.exception, V.VendorUsageUnmetered)
                        self.assertEqual(replay.exception.detail, "durable retrieval usage missing")
                    else:
                        self.assertEqual(str(replay.exception), "durable Exa contents failure is invalid")
                    self.assertEqual(http.call_count, 1)
                    self.assertAlmostEqual(restarted.spent(), 0.001)
                    self.assertEqual(restarted.summary()["unresolved_reservations"], 0)

    def test_simultaneous_identical_citations_share_one_charge(self):
        barrier = threading.Barrier(6)
        ledger = V.Ledger(ceiling=1)
        def read(_index):
            barrier.wait(timeout=5)
            return V.read_source({"url": URL}, ledger, "research")
        with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                mock.patch.object(V.urllib.request, "urlopen", side_effect=lambda *_a, **_k:
                    io.BytesIO(json.dumps(page_response()).encode())) as http:
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(read, range(6)))
            self.assertTrue(all(result == {"text": PAGE, "retrieval_provider": "exa"} for result in results))
            self.assertEqual(http.call_count, 1)
            self.assertAlmostEqual(ledger.spent(), 0.001)

    def test_crash_before_settlement_blocks_reissue_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "spend.json")
            ledger = V.Ledger(ceiling=1)
            ledger.attach(path)
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                    mock.patch.object(V.urllib.request, "urlopen", side_effect=KeyboardInterrupt) as http:
                with self.assertRaises(KeyboardInterrupt):
                    V.read_source({"url": URL}, ledger, "research")
                restarted = V.Ledger(ceiling=1)
                restarted.attach(path)
                restarted.load(path)
                with self.assertRaises(V.VendorRequestPending):
                    V.read_source({"url": URL}, restarted, "research")
                self.assertEqual(http.call_count, 1)
                self.assertEqual(restarted.summary()["unresolved_reservations"], 1)
                self.assertAlmostEqual(restarted.spent(), 0.001)

    def test_documented_source_http_errors_are_local_and_durable(self):
        for status, tag in [(400, "NO_CONTENT_FOUND"), (422, "FETCH_DOCUMENT_ERROR"),
                            (403, "ROBOTS_FILTER_FAILED")]:
            with self.subTest(status=status, tag=tag), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / "spend.json")
                ledger = V.Ledger(ceiling=1)
                ledger.attach(path)
                error = V.urllib.error.HTTPError("https://api.exa.ai/contents", status, "Rejected", {},
                    io.BytesIO(json.dumps({"tag": tag, "error": "SYNTHETIC_PRIVATE_DETAIL"}).encode()))
                with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                        mock.patch.object(V.urllib.request, "urlopen", side_effect=error) as http, \
                        mock.patch.object(V, "jina_fetch", side_effect=AssertionError("Reader called")) as reader:
                    with self.assertRaises(V.SourceRejected):
                        V.read_source({"url": URL}, ledger, "research")
                    restarted = V.Ledger(ceiling=1)
                    restarted.attach(path)
                    restarted.load(path)
                    with self.assertRaises(V.SourceRejected):
                        V.read_source({"url": URL}, restarted, "research")
                    self.assertEqual(http.call_count, 1)
                    reader.assert_not_called()
                    self.assertNotIn("SYNTHETIC_PRIVATE_DETAIL", Path(path).read_text())

    def test_authoritative_missing_citation_never_triggers_reader_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "spend.json")
            ledger = V.Ledger(ceiling=1)
            ledger.attach(path)
            payload = {"results": [], "statuses": [{"id": URL, "status": "error",
                "error": {"tag": "CRAWL_NOT_FOUND", "httpStatusCode": 404}}]}
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                    mock.patch.object(V.urllib.request, "urlopen",
                        return_value=io.BytesIO(json.dumps(payload).encode())) as http, \
                    mock.patch.object(V, "jina_fetch", side_effect=AssertionError("Reader called")) as reader:
                with self.assertRaises(V.VendorHTTPRejected):
                    V.read_source({"url": URL}, ledger, "research")
                restarted = V.Ledger(ceiling=1)
                restarted.attach(path)
                restarted.load(path)
                with self.assertRaises(V.VendorHTTPRejected):
                    V.read_source({"url": URL}, restarted, "research")
                self.assertAlmostEqual(restarted.spent(), 0.001)
                self.assertEqual(http.call_count, 1)
                reader.assert_not_called()

    def test_above_bound_cost_is_terminal_even_with_usable_text_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "spend.json")
            ledger = V.Ledger(ceiling=1)
            ledger.attach(path)
            payload = page_response(costDollars={"total": 0.002})
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "synthetic"}), \
                    mock.patch.object(V.urllib.request, "urlopen",
                        return_value=io.BytesIO(json.dumps(payload).encode())) as http, \
                    mock.patch.object(V, "jina_fetch", side_effect=AssertionError("Reader called")):
                with self.assertRaises(V.VendorUsageExceededReservation):
                    V.read_source({"url": URL}, ledger, "research")
                self.assertAlmostEqual(ledger.spent(), 0.002)
                restarted = V.Ledger(ceiling=1)
                restarted.attach(path)
                restarted.load(path)
                with self.assertRaises(V.VendorUsageExceededReservation):
                    V.read_source({"url": URL}, restarted, "research")
                self.assertEqual(http.call_count, 1)


if __name__ == "__main__":
    unittest.main()
