#!/usr/bin/env python3

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scan_stage as S


class FakeScanLedger:
    def __init__(self, ceiling, label):
        self.ceiling = ceiling

    def attach(self, _path):
        return None

    def load(self, _path):
        return 17

    def save(self, _path):
        return None

    def spent(self, _pass_name=None):
        return 0.94

    def cap(self, _pass_name):
        return 37.5

    def summary(self):
        return {"total": 3.31, "calls": 296}


class SnapshotLedger:
    def __init__(self, calls=None):
        self.calls = list(calls or [])

    def snapshot(self):
        return {"calls": json.loads(json.dumps(self.calls))}


class ScanStageTest(unittest.TestCase):
    def test_upload_synthesis_llm_enables_durable_paid_outcomes(self):
        llm = mock.Mock()
        with mock.patch.object(S.V, "LLM", return_value=llm) as constructor:
            result = S._durable_llm("anthropic", object(), "claude-test")

        constructor.assert_called_once_with(
            "anthropic", mock.ANY, model="claude-test")
        llm.enable_durable_outcomes.assert_called_once_with()
        self.assertIs(result, llm)

    def test_all_search_transport_failures_are_retryable_errors(self):
        messages = []
        with mock.patch.object(
                S.SC.V, "exa_search", side_effect=RuntimeError("search unavailable")):
            with self.assertRaisesRegex(RuntimeError, "every search request failed"):
                S.SC._search_and_fetch(
                    ["first query", "second query"], object(), messages.append,
                )
        self.assertTrue(any("search failed" in message for message in messages))

    def test_all_page_fetch_transport_failures_are_retryable_errors(self):
        messages = []
        with (
            mock.patch.object(S.SC.V, "exa_search", return_value=[{
                "url": "https://example.org/strategy",
                "title": "Published strategy",
            }]),
            mock.patch.object(S.SC.V, "jina_fetch", return_value=""),
        ):
            with self.assertRaisesRegex(RuntimeError, "every selected page fetch failed"):
                S.SC._search_and_fetch(["query"], object(), messages.append)
        self.assertTrue(any("fetch failed" in message for message in messages))

    def test_partial_search_failure_cannot_become_a_clean_abstention(self):
        def search(query, *_args, **_kwargs):
            if query == "broken query":
                raise RuntimeError("search unavailable")
            return []

        with mock.patch.object(S.SC.V, "exa_search", side_effect=search):
            pages = S.SC._search_and_fetch(
                ["broken query", "clean empty query"], object(), lambda _message: None,
            )
        self.assertEqual(pages, [])
        self.assertTrue(pages.technical_failures)

        class QueryLlm:
            def json_call(self, *_args, **_kwargs):
                return {"queries": ["query"]}

        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            with self.assertRaisesRegex(RuntimeError, "clean abstention"):
                S.SC.scan_country(
                    {"n": 3, "title": "Governance", "content": "Institutions"},
                    "Exampleland", QueryLlm(), object(), lambda _message: None,
                )

    def test_register_research_preserves_partial_retrieval_failure(self):
        pages = S.SC.RetrievedPages([], ["search failed: RuntimeError"])
        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            with self.assertRaisesRegex(RuntimeError, "clean abstention"):
                S.SC.research_initiative(
                    "Farm service", "Exampleland", object(), object(),
                    lambda _message: None,
                )

    def test_query_planning_failure_blocks_a_later_clean_abstention(self):
        pages = [{
            "url": "https://peer.example/strategy",
            "title": "Peerland strategy",
            "tier": "T1",
            "text": "Peerland published an approach.",
        }]

        class PlannerFails:
            def __init__(self):
                self.calls = 0

            def json_call(self, *_args, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("planner unavailable")
                return {
                    "found": False,
                    "statement": "",
                    "quote": "",
                    "source_name": "",
                    "source_url": "",
                    "published_year": None,
                    "about_country": "",
                    "why_it_matters": "",
                    "abstained_because": "nothing relevant",
                }

        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            with self.assertRaisesRegex(RuntimeError, "query planning failed"):
                S.SC.scan_international(
                    {"n": 3, "title": "Governance", "content": "Institutions"},
                    "Exampleland", PlannerFails(), object(), lambda _message: None,
                )

    def test_paid_query_plan_is_reused_after_crash_before_evidence_checkpoint(self):
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        transports = []

        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "scan_spend.json")
            for resumed in (False, True):
                ledger = S.SC.V.Ledger(ceiling=500, label="query-crash-probe")
                ledger.attach(spend_path)
                if resumed:
                    ledger.load(spend_path)
                llm = S.SC.V.LLM("anthropic", ledger, model="test-model")
                llm.enable_durable_outcomes()

                def transport(*_args):
                    transports.append("paid")
                    return {"queries": ["peer strategy"]}, 10, 5

                llm._call_anthropic = transport
                with mock.patch.object(
                        S.SC, "_search_and_fetch",
                        side_effect=RuntimeError("crash before evidence checkpoint")):
                    with self.assertRaisesRegex(
                            RuntimeError, "crash before evidence checkpoint"):
                        S.SC.scan_international(
                            chapter, "Nigeria", llm, ledger, lambda _message: None,
                        )

            with open(spend_path, encoding="utf-8") as handle:
                calls = json.load(handle)["calls"]
            planner_calls = [
                call for call in calls
                if call.get("detail") == "queries intl ch3"
            ]

        self.assertEqual(transports, ["paid"])
        self.assertEqual(len(planner_calls), 1)

    def test_unverifiable_register_quote_is_a_technical_contract_failure(self):
        pages = [{
            "url": "https://example.gov/service",
            "title": "Farm service",
            "tier": "T1",
            "text": "The Farm service is operating.",
        }]

        class InvalidQuote:
            def json_call(self, *_args, **_kwargs):
                return {
                    "found": True,
                    "name": "Farm service",
                    "lead": "Ministry",
                    "uc": ["advisory"],
                    "status": "Operating",
                    "scale": "Published service",
                    "results": "No independent evaluation was found.",
                    "results_tier": "",
                    "quote": "This quote is not on the page.",
                    "source_name": "Ministry",
                    "source_url": pages[0]["url"],
                    "abstained_because": "",
                }

        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            with self.assertRaisesRegex(ValueError, "register quote"):
                S.SC.research_initiative(
                    "Farm service", "Exampleland", InvalidQuote(), object(),
                    lambda _message: None,
                )

    def test_international_recovery_chunks_extraction_into_distinct_page_batches(self):
        pages = [
            {
                "url": f"https://peer.example/strategy-{index}",
                "title": f"Peerland ministry strategy {index}",
                "tier": "T1",
                "text": f"Peerland published approach {index}.",
            }
            for index in range(1, 4)
        ]

        class RefuseFirstBatch:
            def __init__(self):
                self.finding_prompts = []

            def json_call(self, _system, prompt, schema, *_args, **_kwargs):
                if schema == S.SC.QUERY_SCHEMA:
                    return {"queries": ["peer strategy"]}
                self.finding_prompts.append(prompt)
                if len(self.finding_prompts) == 1:
                    raise RuntimeError("structured output refusal")
                return {
                    "found": True,
                    "statement": "Peerland published an approach.",
                    "quote": "Peerland published approach 3.",
                    "source_name": "Peerland ministry",
                    "source_url": pages[2]["url"],
                    "published_year": 2026,
                    "about_country": "Peerland",
                    "why_it_matters": "It is a bounded transfer candidate.",
                    "abstained_because": "",
                }

        llm = RefuseFirstBatch()
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            record, refusal = S.SC.scan_international(
                chapter, "Exampleland", llm, object(), lambda _message: None,
                recovery=True,
            )

        self.assertIsNone(refusal)
        self.assertEqual(record["source_url"], pages[2]["url"])
        self.assertEqual(len(llm.finding_prompts), 2)
        self.assertIn(pages[0]["url"], llm.finding_prompts[0])
        self.assertIn(pages[1]["url"], llm.finding_prompts[0])
        self.assertNotIn(pages[2]["url"], llm.finding_prompts[0])
        self.assertIn(pages[2]["url"], llm.finding_prompts[1])

    def test_international_scan_keeps_foreign_evidence_beyond_country_heavy_results(self):
        results = [
            {
                "url": f"https://fmard.gov.ng/nigeria-strategy-{index}",
                "title": f"Nigeria agriculture strategy {index}",
            }
            for index in range(1, S.SC.MAX_PAGES + 1)
        ] + [{
            "url": "https://kilimo.go.ke/digital-agriculture-strategy",
            "title": "Kenya digital agriculture strategy",
        }]
        peer_text = "Kenya published a digital agriculture strategy."

        class ForeignFinding:
            def json_call(self, _system, _prompt, schema, *_args, **_kwargs):
                if schema == S.SC.QUERY_SCHEMA:
                    return {"queries": ["peer digital agriculture strategy"]}
                return {
                    "found": True,
                    "statement": "Kenya published a digital agriculture strategy.",
                    "quote": peer_text,
                    "source_name": "Kenya agriculture ministry",
                    "source_url": results[-1]["url"],
                    "published_year": 2026,
                    "about_country": "Kenya",
                    "why_it_matters": "It is a bounded transfer candidate.",
                    "abstained_because": "",
                }

        with (
            mock.patch.object(S.SC.V, "exa_search", return_value=results),
            mock.patch.object(
                S.SC.V, "jina_fetch",
                side_effect=lambda url, *_args, **_kwargs: (
                    peer_text if url == results[-1]["url"] else "Nigeria programme"
                ),
            ),
        ):
            record, why = S.SC.scan_international(
                {"n": 3, "title": "Governance", "content": "Institutions"},
                "Nigeria", ForeignFinding(), object(), lambda _message: None,
            )

        self.assertIsNone(why)
        self.assertEqual(record["source_url"], results[-1]["url"])

    def test_all_recovery_batches_failing_technically_remains_a_failure(self):
        pages = [
            {
                "url": f"https://peer.example/strategy-{index}",
                "title": f"Peerland strategy {index}",
                "tier": "T1",
                "text": f"Peerland approach {index}.",
            }
            for index in range(1, 7)
        ]

        class RefuseEveryBatch:
            def __init__(self):
                self.prompts = []

            def json_call(self, _system, prompt, schema, *_args, **_kwargs):
                if schema == S.SC.QUERY_SCHEMA:
                    return {"queries": ["peer strategy"]}
                self.prompts.append(prompt)
                raise RuntimeError("structured output refusal")

        llm = RefuseEveryBatch()
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            with self.assertRaisesRegex(RuntimeError, "bounded extraction recovery"):
                S.SC.scan_international(
                    chapter, "Exampleland", llm, object(), lambda _message: None,
                    recovery=True,
                )

        self.assertEqual(len(llm.prompts), S.SC.RECOVERY_BATCH_LIMIT)
        for index, prompt in enumerate(llm.prompts):
            included = pages[index * 2:(index + 1) * 2]
            excluded = [page for page in pages if page not in included]
            self.assertTrue(all(page["url"] in prompt for page in included))
            self.assertTrue(all(page["url"] not in prompt for page in excluded))

    def test_one_technical_batch_cannot_be_downgraded_by_clean_abstentions(self):
        pages = [
            {
                "url": f"https://peer.example/strategy-{index}",
                "title": f"Peerland strategy {index}",
                "tier": "T1",
                "text": f"Peerland approach {index}.",
            }
            for index in range(1, 5)
        ]

        class MixedOutcomes:
            def __init__(self):
                self.calls = 0

            def json_call(self, _system, _prompt, schema, *_args, **_kwargs):
                if schema == S.SC.QUERY_SCHEMA:
                    return {"queries": ["peer strategy"]}
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("structured output refusal")
                return {
                    "found": False,
                    "statement": "",
                    "quote": "",
                    "source_name": "",
                    "source_url": "",
                    "published_year": None,
                    "about_country": "",
                    "why_it_matters": "",
                    "abstained_because": "nothing relevant in this batch",
                }

        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            with self.assertRaisesRegex(RuntimeError, "bounded extraction recovery"):
                S.SC.scan_international(
                    {"n": 3, "title": "Governance", "content": "Institutions"},
                    "Exampleland", MixedOutcomes(), object(), lambda _message: None,
                )

    def test_local_contract_failure_advances_to_the_next_batch(self):
        pages = [
            {
                "url": f"https://peer.example/strategy-{index}",
                "title": f"Peerland strategy {index}",
                "tier": "T1",
                "text": f"Peerland approach {index}.",
            }
            for index in range(1, 4)
        ]

        class InvalidThenValid:
            def __init__(self):
                self.calls = 0

            def json_call(self, _system, _prompt, schema, *_args, **_kwargs):
                if schema == S.SC.QUERY_SCHEMA:
                    return {"queries": ["peer strategy"]}
                self.calls += 1
                if self.calls == 1:
                    return {
                        "found": True,
                        "statement": 42,
                        "quote": "Peerland approach 1.",
                        "source_name": "Peerland ministry",
                        "source_url": pages[0]["url"],
                        "published_year": 2026,
                        "about_country": "Peerland",
                        "why_it_matters": "Candidate.",
                        "abstained_because": "",
                    }
                return {
                    "found": True,
                    "statement": "Peerland published an approach.",
                    "quote": "Peerland approach 3.",
                    "source_name": "Peerland ministry",
                    "source_url": pages[2]["url"],
                    "published_year": 2026,
                    "about_country": "Peerland",
                    "why_it_matters": "It is a bounded transfer candidate.",
                    "abstained_because": "",
                }

        llm = InvalidThenValid()
        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            record, why = S.SC.scan_international(
                {"n": 3, "title": "Governance", "content": "Institutions"},
                "Exampleland", llm, object(), lambda _message: None,
            )
        self.assertIsNone(why)
        self.assertEqual(record["source_url"], pages[2]["url"])
        self.assertEqual(llm.calls, 2)

    def test_recovery_resume_uses_frozen_excerpts_without_retrieval(self):
        pages = [{
            "url": "https://peer.example/strategy",
            "title": "Peerland strategy",
            "tier": "T1",
            "text": "Peerland published approach." + ("x" * 8000),
        }]
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        saved = []

        class QueryOnly:
            def json_call(self, _system, _prompt, schema, *_args, **_kwargs):
                if schema == S.SC.QUERY_SCHEMA:
                    return {"queries": ["peer strategy"]}
                raise AssertionError("extraction started before its evidence was durable")

        def interrupt_after_plan(value):
            saved.append(value)
            raise RuntimeError("simulated crash after evidence checkpoint")

        with mock.patch.object(S.SC, "_search_and_fetch", return_value=pages):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                S.SC.scan_international(
                    chapter, "Exampleland", QueryOnly(), object(),
                    lambda _message: None,
                    save_recovery=interrupt_after_plan,
                )
        self.assertEqual(len(saved[0]["pages"][0]["text"]), S.SC.PAGE_CHARS)
        tampered = json.loads(json.dumps(saved[0]))
        tampered["retrieval_failures"] = ["search failed: RuntimeError"]
        with self.assertRaisesRegex(ValueError, "plan digest"):
            S.SC._validate_recovery_unit(
                tampered, "international", chapter, "Exampleland", QueryOnly())

        class ResumeLlm:
            def json_call(self, _system, _prompt, _schema, *_args, **_kwargs):
                return {
                    "found": True,
                    "statement": "Peerland published an approach.",
                    "quote": "Peerland published approach.",
                    "source_name": "Peerland ministry",
                    "source_url": pages[0]["url"],
                    "published_year": 2026,
                    "about_country": "Peerland",
                    "why_it_matters": "It is a bounded transfer candidate.",
                    "abstained_because": "",
                }

        with mock.patch.object(
                S.SC, "_search_and_fetch",
                side_effect=AssertionError("resume must not retrieve again")):
            record, why = S.SC.scan_international(
                chapter, "Exampleland", ResumeLlm(), object(), lambda _message: None,
                recovery_state=saved[0],
            )
        self.assertIsNone(why)
        self.assertEqual(record["source_url"], pages[0]["url"])

    def test_unclaimed_durable_scan_result_is_bound_by_ledger_index(self):
        response = {
            "found": False,
            "statement": "",
            "quote": "",
            "source_name": "",
            "source_url": "",
            "published_year": None,
            "about_country": "",
            "why_it_matters": "",
            "abstained_because": "nothing relevant",
        }
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        pages = [{
            "url": "https://peer.example/strategy",
            "title": "Peerland strategy",
            "tier": "T1",
            "text": "Peerland published approach.",
        }]

        class NoReplayLlm:
            vendor = "anthropic"
            model = "test-model"

            def __init__(self):
                self.ledger = SnapshotLedger()

            def json_call_once(self, *_args, **_kwargs):
                raise AssertionError("a paid result must not be replayed")

        llm = NoReplayLlm()
        unit = S.SC._new_recovery_unit(
            "international", chapter, "Exampleland", pages, llm, None)
        prompt = S.SC._finding_prompt("international", chapter, "Exampleland", pages)
        detail = "international ch3 recovery batch 1/3"
        request_sha256 = S.SC.V.json_call_request_sha256(
            S.SC.SYSTEM, prompt, S.SC.FINDING_SCHEMA, S.SC.PASS, 2500, detail)
        journal = {
            "schema_version": "damm.structured-result/v1",
            "request_sha256": request_sha256,
            "outcome": "complete",
            "response_sha256": S.SC.V.stable_json_sha256(response),
            "response": response,
        }
        llm.ledger.calls.append({
            "vendor": llm.vendor,
            "model": llm.model,
            "pass_name": S.SC.PASS,
            "structured_result": journal,
        })
        checkpoints = []

        claimed = S.SC._checkpointed_recovery_call(
            llm, unit, checkpoints.append, "batch-0001", S.SC.SYSTEM, prompt,
            S.SC.FINDING_SCHEMA, 2500, detail)

        self.assertEqual(claimed, response)
        self.assertEqual(checkpoints[-1]["steps"]["batch-0001"]["ledger_call_index"], 0)

        llm.ledger.calls[0]["pass_name"] = "unrelated-pass"
        with self.assertRaisesRegex(ValueError, "spend binding is invalid"):
            S.SC._checkpointed_recovery_call(
                llm, checkpoints[-1], None, "batch-0001", S.SC.SYSTEM, prompt,
                S.SC.FINDING_SCHEMA, 2500, detail)

    def test_unclaimed_durable_scan_result_rejects_wrong_ledger_pass(self):
        response = {"found": False}
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        pages = [{
            "url": "https://peer.example/strategy",
            "title": "Peerland strategy",
            "tier": "T1",
            "text": "Peerland published approach.",
        }]

        class NoReplayLlm:
            vendor = "anthropic"
            model = "test-model"

            def __init__(self):
                self.ledger = SnapshotLedger()

            def json_call_once(self, *_args, **_kwargs):
                raise AssertionError("wrong-pass spend must fail before transport")

        llm = NoReplayLlm()
        unit = S.SC._new_recovery_unit(
            "international", chapter, "Exampleland", pages, llm, None)
        prompt = S.SC._finding_prompt(
            "international", chapter, "Exampleland", pages)
        detail = "international ch3 recovery batch 1/3"
        request_sha256 = S.SC.V.json_call_request_sha256(
            S.SC.SYSTEM, prompt, S.SC.FINDING_SCHEMA, S.SC.PASS, 2500, detail)
        journal = {
            "schema_version": "damm.structured-result/v1",
            "request_sha256": request_sha256,
            "outcome": "complete",
            "response_sha256": S.SC.V.stable_json_sha256(response),
            "response": response,
        }
        llm.ledger.calls.append({
            "vendor": llm.vendor,
            "model": llm.model,
            "pass_name": "unrelated-pass",
            "structured_result": journal,
        })

        with self.assertRaisesRegex(ValueError, "ledger pass does not match"):
            S.SC._checkpointed_recovery_call(
                llm, unit, None, "batch-0001", S.SC.SYSTEM, prompt,
                S.SC.FINDING_SCHEMA, 2500, detail)

    def test_real_durable_llm_claims_crash_gap_without_provider_replay(self):
        response = {"found": False}
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        pages = [{
            "url": "https://peer.example/strategy",
            "title": "Peerland strategy",
            "tier": "T1",
            "text": "Peerland published approach.",
        }]
        ledger = S.SC.V.Ledger(ceiling=500, label="scan-crash-gap")
        llm = S.SC.V.LLM(
            "anthropic", ledger, model="test-model").enable_durable_outcomes()
        unit = S.SC._new_recovery_unit(
            "international", chapter, "Exampleland", pages, llm, None)
        prompt = S.SC._finding_prompt("international", chapter, "Exampleland", pages)
        detail = "international ch3 recovery batch 1/3"
        transport = mock.Mock(return_value=(response, 10, 20))
        llm._call_anthropic = transport

        # The provider outcome and spend survived, but the scan-unit state write did not.
        llm.json_call_once(
            S.SC.SYSTEM, prompt, S.SC.FINDING_SCHEMA, S.SC.PASS,
            max_tokens=2500, detail=detail)
        transport.reset_mock()
        transport.side_effect = AssertionError("paid provider request was replayed")

        claimed = S.SC._checkpointed_recovery_call(
            llm, unit, None, "batch-0001", S.SC.SYSTEM, prompt,
            S.SC.FINDING_SCHEMA, 2500, detail)

        self.assertEqual(claimed, response)
        transport.assert_not_called()
        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(unit["steps"]["batch-0001"]["ledger_call_index"], 0)

    def test_duplicate_paid_scan_results_fail_closed_without_transport(self):
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        pages = [{
            "url": "https://peer.example/strategy",
            "title": "Peerland strategy",
            "tier": "T1",
            "text": "Peerland published approach.",
        }]

        class NoReplayLlm:
            vendor = "anthropic"
            model = "test-model"

            def __init__(self):
                self.ledger = SnapshotLedger()

            def json_call_once(self, *_args, **_kwargs):
                raise AssertionError("ambiguous spend must fail before transport")

        llm = NoReplayLlm()
        unit = S.SC._new_recovery_unit(
            "international", chapter, "Exampleland", pages, llm, None)
        prompt = S.SC._finding_prompt("international", chapter, "Exampleland", pages)
        detail = "international ch3 recovery batch 1/3"
        request_sha256 = S.SC.V.json_call_request_sha256(
            S.SC.SYSTEM, prompt, S.SC.FINDING_SCHEMA, S.SC.PASS, 2500, detail)
        response = {"found": False}
        journal = {
            "schema_version": "damm.structured-result/v1",
            "request_sha256": request_sha256,
            "outcome": "complete",
            "response_sha256": S.SC.V.stable_json_sha256(response),
            "response": response,
        }
        call = {"vendor": llm.vendor, "model": llm.model,
                "structured_result": journal}
        llm.ledger.calls.extend([call, json.loads(json.dumps(call))])

        with self.assertRaisesRegex(ValueError, "duplicate paid outcomes"):
            S.SC._checkpointed_recovery_call(
                llm, unit, None, "batch-0001", S.SC.SYSTEM, prompt,
                S.SC.FINDING_SCHEMA, 2500, detail)

    def test_json_call_only_adapter_reuses_its_synthetic_checkpoint(self):
        response = {"found": False}
        chapter = {"n": 3, "title": "Governance", "content": "Institutions"}
        pages = [{
            "url": "https://peer.example/strategy",
            "title": "Peerland strategy",
            "tier": "T1",
            "text": "Peerland published approach.",
        }]

        class ReplayStyleLlm:
            vendor = "fixture"
            model = "replay"

            def __init__(self):
                self.ledger = SnapshotLedger()
                self.calls = 0

            def json_call(self, *_args, **_kwargs):
                self.calls += 1
                return response

        llm = ReplayStyleLlm()
        unit = S.SC._new_recovery_unit(
            "international", chapter, "Exampleland", pages, llm, None)
        prompt = S.SC._finding_prompt("international", chapter, "Exampleland", pages)
        detail = "international ch3 recovery batch 1/3"
        first = S.SC._checkpointed_recovery_call(
            llm, unit, None, "batch-0001", S.SC.SYSTEM, prompt,
            S.SC.FINDING_SCHEMA, 2500, detail)
        second = S.SC._checkpointed_recovery_call(
            llm, unit, None, "batch-0001", S.SC.SYSTEM, prompt,
            S.SC.FINDING_SCHEMA, 2500, detail)

        self.assertEqual(first, response)
        self.assertEqual(second, response)
        self.assertEqual(llm.calls, 1)

    def test_country_and_international_scan_lanes_have_distinct_protected_caps(self):
        ledger = S.V.Ledger(ceiling=100, label="protected-scan-lanes")
        self.assertEqual(ledger.cap("country_research"), 7.5)
        self.assertEqual(ledger.cap("international_lessons"), 7.5)
        searches_to_cap = int(
            ledger.cap("country_research") / S.V.PRICES["exa"]["per_search"]
        )
        ledger.record("exa", "country_research", searches=searches_to_cap)
        with self.assertRaises(S.V.BudgetExhausted):
            ledger.check(
                "country_research",
                headroom=S.V.PRICES["exa"]["per_search"],
            )
        # Exhausting Stage 2 does not borrow or consume Stage 4's protected share.
        ledger.check("international_lessons")
        ledger.record("exa", "international_lessons", searches=searches_to_cap)
        with self.assertRaises(S.V.BudgetExhausted):
            ledger.check(
                "international_lessons",
                headroom=S.V.PRICES["exa"]["per_search"],
            )
        spent = round(searches_to_cap * S.V.PRICES["exa"]["per_search"], 6)
        self.assertEqual(ledger.spent("country_research"), spent)
        self.assertEqual(ledger.spent("international_lessons"), spent)
        self.assertEqual(ledger.spent(), round(spent * 2, 6))

    def setUp(self):
        # These scan fixtures exercise Reader fallback and downstream synthesis.
        self.enterContext(mock.patch.object(S.SC.V, "exa_contents", return_value=""))
        self.price_patcher = mock.patch.dict(S.SC.V.PRICES["anthropic"], {
            "test-model": {"in_per_mtok": 5.0, "out_per_mtok": 25.0},
        })
        self.price_patcher.start()
        self.addCleanup(self.price_patcher.stop)
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

    def test_unresolved_register_failure_blocks_country_lane_completion(self):
        state = {"country": {}, "abstained": {}, "failures": {
            "register:Farm service": {
                "lane": "register", "chapter": "Farm service",
                "error": "the scan failed: provider reset",
            },
        }}
        for chapter in S.SC.prescriptive_chapters():
            state["abstained"][f"country:{chapter['n']}"] = {
                "lane": "country", "chapter": chapter["n"], "why": "not found",
            }
        self.assertFalse(S.autonomous_lane_complete(state, "country"))

    def test_migrated_country_failure_blocks_international_lane_completion(self):
        state = {
            "country": {},
            "international": {
                f"international:{chapter['n']}": {"chapter": chapter["n"]}
                for chapter in S.SC.prescriptive_chapters()
            },
            "register": {
                "register:Farm service": {"name": "Farm service"},
            },
            "abstained": {
                "country:3": {
                    "lane": "country",
                    "chapter": 3,
                    "why": "the scan failed: structured output refusal",
                },
            },
        }

        migrated = S.SC.migrate_legacy_technical_abstentions(state)

        self.assertEqual(migrated, ("country:3",))
        self.assertFalse(S.autonomous_lane_complete(state, "international"))
        state["failures"].clear()
        self.assertTrue(S.autonomous_lane_complete(state, "international"))

    def test_legacy_technical_abstention_is_reopened_as_a_failure(self):
        state = {
            "abstained": {
                "international:3": {
                    "lane": "international",
                    "chapter": 3,
                    "why": "the scan failed: structured output refusal",
                },
                "international:4": {
                    "lane": "international",
                    "chapter": 4,
                    "why": "nothing relevant was found",
                },
            },
        }

        migrated = S.SC.migrate_legacy_technical_abstentions(state)

        self.assertEqual(migrated, ("international:3",))
        self.assertIn("international:3", state["failures"])
        self.assertNotIn("international:3", state["abstained"])
        self.assertIn("international:4", state["abstained"])

    def test_register_failure_is_retried_when_fresh_discovery_drifted(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutions"},
        ]
        argv = [
            "scans.py", "--country", "Exampleland", "--iso", "EXP",
            "--out", "run", "--lane", "country", "--ceiling", "500",
            "--vendor", "anthropic/test", "--resume",
        ]
        entry = {
            "name": "Farm service",
            "lead": "Ministry",
            "uc": ["advisory"],
            "status": "Operating",
            "scale": "Published service",
            "results": "No independent evaluation was found.",
            "results_tier": "",
            "tier": "T1",
            "src": "Ministry",
            "src_url": "https://example.gov/farm-service",
            "overlap": [],
            "verification_note": "Existence verified.",
        }
        state = {
            "country": {},
            "international": {},
            "register": {},
            "abstained": {
                "country:3": {
                    "lane": "country", "chapter": 3, "why": "not found",
                },
            },
            "failures": {
                "register:Farm service": {
                    "lane": "register", "chapter": "Farm service",
                    "error": "the scan failed: provider reset",
                },
            },
            "overlap": "",
        }

        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(S.SC, "discover_initiatives", return_value=[]),
                mock.patch.object(
                    S.SC, "research_initiative", return_value=(entry, None),
                ) as research,
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(S.SC.main(), 0)

            self.assertEqual(research.call_args.args[0], "Farm service")
            with open(state_path, encoding="utf-8") as handle:
                recovered = json.load(handle)
            self.assertNotIn("register:Farm service", recovered["failures"])
            self.assertIn("register:Farm service", recovered["register"])
            with mock.patch.object(
                    S.SC, "prescriptive_chapters", return_value=chapters):
                self.assertTrue(S.autonomous_lane_complete(recovered, "country"))

    def test_register_alias_failure_resolves_against_existing_entry(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutions"},
        ]
        argv = [
            "scans.py", "--country", "Exampleland", "--iso", "EXP",
            "--out", "run", "--lane", "country", "--ceiling", "500",
            "--vendor", "anthropic/test", "--resume",
        ]
        existing = {
            "name": "Al Mufeed",
            "lead": "Ministry",
            "uc": ["advisory"],
            "status": "Operating",
            "scale": "Published service",
            "results": "No independent evaluation was found.",
            "results_tier": "",
            "tier": "T1",
            "src": "Ministry",
            "src_url": "https://example.gov/al-mufeed",
            "overlap": [],
            "verification_note": "Existence verified.",
        }
        state = {
            "country": {},
            "international": {},
            "register": {"register:Al Mufeed": existing},
            "abstained": {
                "country:3": {
                    "lane": "country", "chapter": 3, "why": "not found",
                },
            },
            "failures": {
                "register:FAO El-Mufeed": {
                    "lane": "register", "chapter": "FAO El-Mufeed",
                    "error": "the scan failed: provider reset",
                },
            },
            "overlap": "",
        }

        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(S.SC, "discover_initiatives", return_value=[]),
                mock.patch.object(S.SC, "research_initiative") as research,
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(S.SC.main(), 0)

            research.assert_not_called()
            with open(state_path, encoding="utf-8") as handle:
                recovered = json.load(handle)
            self.assertNotIn("register:FAO El-Mufeed", recovered["failures"])
            with mock.patch.object(
                    S.SC, "prescriptive_chapters", return_value=chapters):
                self.assertTrue(S.autonomous_lane_complete(recovered, "country"))

    def test_successful_register_alias_clears_parallel_alias_failure(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutions"},
        ]
        argv = [
            "scans.py", "--country", "Exampleland", "--iso", "EXP",
            "--out", "run", "--lane", "country", "--ceiling", "500",
            "--vendor", "anthropic/test", "--resume",
        ]
        entry = {
            "name": "Al Mufeed",
            "lead": "Ministry",
            "uc": ["advisory"],
            "status": "Operating",
            "scale": "Published service",
            "results": "No independent evaluation was found.",
            "results_tier": "",
            "tier": "T1",
            "src": "Ministry",
            "src_url": "https://example.gov/al-mufeed",
            "overlap": [],
            "verification_note": "Existence verified.",
        }
        state = {
            "country": {},
            "international": {},
            "register": {},
            "abstained": {
                "country:3": {
                    "lane": "country", "chapter": 3, "why": "not found",
                },
            },
            "failures": {
                name: {
                    "lane": "register", "chapter": name.partition(":")[2],
                    "error": "the scan failed: provider reset",
                }
                for name in ("register:Al Mufeed", "register:FAO El-Mufeed")
            },
            "overlap": "",
        }

        def research(name, *_args):
            if name == "Al Mufeed":
                return entry, None
            raise RuntimeError("provider reset")

        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(S.SC, "discover_initiatives", return_value=[]),
                mock.patch.object(S.SC, "research_initiative", side_effect=research),
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(S.SC.main(), 0)

            with open(state_path, encoding="utf-8") as handle:
                recovered = json.load(handle)
            self.assertEqual(recovered["failures"], {})
            self.assertEqual(len(recovered["register"]), 1)

    def test_pending_empty_lane_recovery_survives_crash_before_calls(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutions"},
        ]
        state = {
            "country": {},
            "international": {},
            "register": {},
            "abstained": {
                "international:3": {
                    "lane": "international", "chapter": 3, "why": "not found",
                },
            },
            "failures": {},
            "overlap": "",
        }
        self.assertEqual(
            S.SC.reopen_completed_empty_lane(state, "international", chapters),
            ("international:3",),
        )
        self.assertEqual(
            state["empty_lane_recovery_pending"]["international"],
            ["international:3"],
        )
        recovered = {
            "chapter": 3,
            "chapter_title": "Governance",
            "lane": "international",
            "statement": "A peer published an approach.",
            "quote": "published approach",
            "why_it_matters": "It is a bounded transfer candidate.",
            "source_name": "Peer ministry",
            "source_url": "https://peer.example/3",
            "tier": "T1",
            "published_year": 2026,
            "about_country": "Peerland",
            "applies_to": "dar_only",
        }

        def assert_recovery(_chapter, _country, _llm, _ledger, _log, **kwargs):
            self.assertTrue(kwargs["recovery"])
            self.assertIsNone(kwargs["recovery_state"])
            return recovered, None

        argv = [
            "scans.py", "--country", "Exampleland", "--iso", "EXP",
            "--out", "run", "--lane", "international", "--ceiling", "500",
            "--vendor", "anthropic/test", "--resume",
        ]
        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(
                    S.SC, "scan_international", side_effect=assert_recovery,
                ) as research,
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(S.SC.main(), 0)
            self.assertEqual(research.call_count, 1)
            with open(state_path, encoding="utf-8") as handle:
                completed = json.load(handle)
            self.assertNotIn(
                "international", completed["empty_lane_recovery_pending"])

    def test_all_lane_resume_recovers_completed_empty_international_lane(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutions"},
        ]
        argv = [
            "scans.py", "--country", "Exampleland", "--iso", "EXP",
            "--out", "run", "--lane", "all", "--ceiling", "500",
            "--vendor", "anthropic/test", "--resume",
        ]

        class BoundaryLlm:
            def json_call(self, *_args, **kwargs):
                if kwargs["detail"] == "queries intl ch3":
                    return {"queries": ["Peerland digital agriculture strategy"]}
                if kwargs["detail"] == (
                        "international ch3 empty-lane recovery batch 1/3"):
                    return {
                        "found": True,
                        "statement": "A peer published an approach.",
                        "quote": "Peerland published an approach.",
                        "source_name": "Peer ministry",
                        "source_url": "https://peer.example/strategy",
                        "published_year": 2026,
                        "about_country": "Peerland",
                        "why_it_matters": "It is a bounded transfer candidate.",
                        "abstained_because": "",
                    }
                raise AssertionError(f"unexpected LLM call: {kwargs['detail']}")

        def search(query, *_args, **_kwargs):
            if query == "Peerland digital agriculture strategy":
                return [{
                    "url": "https://peer.example/strategy",
                    "title": "Peerland strategy",
                }]
            return []

        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({
                    "country": {
                        "country:3": {
                            "chapter": 3,
                            "chapter_title": "Governance",
                            "lane": "country",
                            "statement": "Institutions are documented.",
                        },
                    },
                    "international": {},
                    "register": {},
                    "abstained": {
                        "international:3": {
                            "lane": "international",
                            "chapter": 3,
                            "why": "no page could be retrieved",
                        },
                    },
                    "failures": {},
                    "overlap": "",
                }, handle)

            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=BoundaryLlm()),
                mock.patch.object(S.SC.V, "exa_search", side_effect=search),
                mock.patch.object(
                    S.SC.V, "jina_fetch",
                    return_value="Peerland published an approach.",
                ),
                mock.patch.dict(
                    os.environ, {"DAMM_CHECKPOINT_BINDING_SHA256": ""},
                ),
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(sys, "stdout", new_callable=io.StringIO) as output,
            ):
                self.assertEqual(S.SC.main(), 0)

            self.assertIn(
                "completed-but-empty international scans for bounded recovery attempt 1/1",
                output.getvalue(),
            )
            with open(os.path.join(directory, "run_scans.json"), encoding="utf-8") as handle:
                product = json.load(handle)
            self.assertEqual(product["international_pointers"], [{
                "chapter": 3,
                "chapter_title": "Governance",
                "lane": "international",
                "statement": "A peer published an approach.",
                "quote": "Peerland published an approach.",
                "why_it_matters": "It is a bounded transfer candidate.",
                "source_name": "Peer ministry",
                "source_url": "https://peer.example/strategy",
                "tier": "T5",
                "published_year": 2026,
                "about_country": "Peerland",
                "applies_to": "dar_only",
            }])

    def test_resume_researches_a_completed_empty_international_lane_once(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutional arrangements"},
        ]

        def recovered_pointer(chapter, _country, _llm, _ledger, _log, **_kwargs):
            return ({
                "chapter": chapter["n"],
                "chapter_title": chapter["title"],
                "lane": "international",
                "statement": "A peer published an approach.",
                "quote": "published approach",
                "why_it_matters": "It is a bounded transfer candidate.",
                "source_name": "Peer ministry",
                "source_url": f"https://peer.example/{chapter['n']}",
                "tier": "T1",
                "published_year": 2026,
                "about_country": "Peerland",
                "applies_to": "dar_only",
            }, None)

        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({
                    "country": {},
                    "international": {},
                    "register": {},
                    "abstained": {
                        f"international:{chapter['n']}": {
                            "lane": "international",
                            "chapter": chapter["n"],
                            "why": "no page could be retrieved",
                        }
                        for chapter in chapters
                    },
                    "overlap": "",
                }, handle)

            argv = [
                "scans.py", "--country", "Exampleland", "--iso", "EXP",
                "--out", "run", "--lane", "international", "--ceiling", "500",
                "--vendor", "anthropic/test", "--resume",
            ]
            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(
                    S.SC, "scan_international", side_effect=recovered_pointer,
                ) as research,
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(S.SC.main(), 0)

            self.assertEqual(research.call_count, len(chapters))
            with open(os.path.join(directory, "run_scans.json"), encoding="utf-8") as handle:
                product = json.load(handle)
            self.assertEqual(len(product["international_pointers"]), len(chapters))
            with open(state_path, encoding="utf-8") as handle:
                recovered_state = json.load(handle)
            self.assertEqual(
                recovered_state["empty_lane_recovery_attempts"]["international"], 1,
            )

    def test_completed_empty_lane_recovery_is_bounded_to_one_attempt(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutional arrangements"},
        ]
        state = {
            "international": {},
            "abstained": {
                "international:3": {
                    "lane": "international", "chapter": 3, "why": "not found",
                },
            },
        }
        self.assertEqual(
            S.SC.reopen_completed_empty_lane(state, "international", chapters),
            ("international:3",),
        )
        state["abstained"]["international:3"] = {
            "lane": "international", "chapter": 3, "why": "still not found",
        }
        self.assertEqual(
            S.SC.reopen_completed_empty_lane(state, "international", chapters), (),
        )
        self.assertEqual(state["empty_lane_recovery_attempts"]["international"], 1)

    def test_resume_retries_technical_scan_failures_instead_of_freezing_abstention(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutional arrangements"},
        ]
        argv = [
            "scans.py", "--country", "Exampleland", "--iso", "EXP",
            "--out", "run", "--lane", "international", "--ceiling", "500",
            "--vendor", "anthropic/test", "--resume",
        ]
        recovered = {
            "chapter": 3,
            "chapter_title": "Governance",
            "lane": "international",
            "statement": "A peer published an approach.",
            "quote": "published approach",
            "why_it_matters": "It is a bounded transfer candidate.",
            "source_name": "Peer ministry",
            "source_url": "https://peer.example/3",
            "tier": "T1",
            "published_year": 2026,
            "about_country": "Peerland",
            "applies_to": "dar_only",
        }

        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    S.SC, "scan_international", side_effect=RuntimeError("provider reset"),
                ),
            ):
                self.assertEqual(S.SC.main(), 0)

            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, encoding="utf-8") as handle:
                failed_state = json.load(handle)
            self.assertNotIn("international:3", failed_state["abstained"])
            self.assertIn("international:3", failed_state["failures"])

            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    S.SC, "scan_international", return_value=(recovered, None),
                ) as research,
            ):
                self.assertEqual(S.SC.main(), 0)

            self.assertEqual(research.call_count, 1)

    def test_mixed_abstention_and_failure_can_use_recovery_on_final_attempt(self):
        chapters = [
            {"n": 3, "title": "Governance", "content": "Institutions"},
            {"n": 4, "title": "Infrastructure", "content": "Shared systems"},
        ]
        state = {
            "country": {},
            "international": {},
            "register": {},
            "abstained": {
                "international:3": {
                    "lane": "international", "chapter": 3, "why": "not found",
                },
            },
            "failures": {
                "international:4": {
                    "lane": "international", "chapter": 4,
                    "error": "the scan failed: provider reset",
                },
            },
            "overlap": "",
        }

        def result(chapter, _country, _llm, _ledger, _log, **_kwargs):
            if result.calls == 0:
                result.calls += 1
                return None, "no page could be retrieved"
            result.calls += 1
            return ({
                "chapter": chapter["n"],
                "chapter_title": chapter["title"],
                "lane": "international",
                "statement": "A peer published an approach.",
                "quote": "published approach",
                "why_it_matters": "It is a bounded transfer candidate.",
                "source_name": "Peer ministry",
                "source_url": f"https://peer.example/{chapter['n']}",
                "tier": "T1",
                "published_year": 2026,
                "about_country": "Peerland",
                "applies_to": "dar_only",
            }, None)

        result.calls = 0
        argv = [
            "scans.py", "--country", "Exampleland", "--iso", "EXP",
            "--out", "run", "--lane", "international", "--ceiling", "500",
            "--vendor", "anthropic/test", "--resume",
        ]
        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "run_scans_state.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
            with (
                mock.patch.object(S.SC, "LOOP1", directory),
                mock.patch.object(S.SC, "prescriptive_chapters", return_value=chapters),
                mock.patch.object(S.SC.V, "load_env"),
                mock.patch.object(S.SC.V, "Ledger", FakeScanLedger),
                mock.patch.object(S.SC.V, "LLM", return_value=object()),
                mock.patch.object(S.SC.WI, "bind_checkpoint_state"),
                mock.patch.object(S.SC, "scan_international", side_effect=result) as research,
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(S.SC.main(), 0)

            self.assertEqual(research.call_count, 3)
            with open(os.path.join(directory, "run_scans.json"), encoding="utf-8") as handle:
                product = json.load(handle)
            self.assertEqual(len(product["international_pointers"]), 2)
            with open(state_path, encoding="utf-8") as handle:
                recovered_state = json.load(handle)
            self.assertEqual(
                recovered_state["empty_lane_recovery_attempts"]["international"], 1,
            )

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
