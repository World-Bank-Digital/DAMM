#!/usr/bin/env python3

import io
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vendors as V


class _AnthropicMessages:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def create(self, **request):
        self.requests.append(request)
        return self.response

class _CreateEndpoint:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def create(self, **request):
        self.requests.append(request)
        return self.response

    def generate_content(self, **request):
        self.requests.append(request)
        return self.response


class VendorJsonCallTest(unittest.TestCase):
    def setUp(self):
        patches = (
            mock.patch.dict(V.PRICES["anthropic"], {
                "claude-test": {"in_per_mtok": 5.0, "out_per_mtok": 25.0},
            }),
            mock.patch.dict(V.PRICES["openai"], {
                "gpt-test": {"in_per_mtok": 5.0, "out_per_mtok": 25.0},
            }),
            mock.patch.dict(V.PRICES["gemini"], {
                "gemini-test": {"in_per_mtok": 5.0, "out_per_mtok": 25.0},
            }),
        )
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_unknown_reasoning_model_is_rejected_before_transport(self):
        with self.assertRaisesRegex(V.VendorError, "no explicit tariff"):
            V.LLM(
                "anthropic", V.Ledger(ceiling=500, label="test"),
                model="claude-future-unknown",
            )

    def test_unknown_vendor_is_rejected_before_ledger_or_transport(self):
        ledger = V.Ledger(ceiling=500, label="test")
        with self.assertRaisesRegex(V.VendorError, "unknown vendor"):
            V.LLM("unknown", ledger, model="model-with-no-tariff")
        with self.assertRaisesRegex(V.VendorError, "unknown vendor"):
            ledger.estimated_cost(
                "unknown", model="model-with-no-tariff",
                in_tok=1_000, out_tok=1_000,
            )
        self.assertEqual(ledger.calls, [])
        self.assertEqual(ledger._reservations, {})

    def test_openai_incomplete_response_uses_typed_truncation_and_actual_usage(self):
        usage = SimpleNamespace(
            input_tokens=321,
            output_tokens=4096,
            output_tokens_details=SimpleNamespace(reasoning_tokens=1024),
        )
        response = SimpleNamespace(
            id="resp_truncated",
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output_text='{"value":"cut off',
            usage=usage,
            max_output_tokens=4096,
        )
        endpoint = _CreateEndpoint(response)
        openai = SimpleNamespace(OpenAI=lambda **_kwargs: SimpleNamespace(
            responses=endpoint))
        ledger = V.Ledger(ceiling=500, label="test")
        schema = {
            "type": "object",
            "properties": {
                "value": {"type": "string", "maxLength": 20},
                "refs": {
                    "type": "array", "uniqueItems": True,
                    "items": {"type": "string"},
                },
            },
            "required": ["value", "refs"],
            "additionalProperties": False,
        }
        with mock.patch.dict(sys.modules, {"openai": openai}):
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                llm = V.LLM("openai", ledger, model="gpt-test")
                with self.assertRaises(V.VendorOutputTruncated) as raised:
                    llm.json_call_once(
                        "system", "user", schema, "investment",
                        max_tokens=4096, detail="openai bounded unit",
                    )

        wire_schema = endpoint.requests[0]["text"]["format"]["schema"]
        self.assertNotIn(
            "maxLength", wire_schema["properties"]["value"])
        self.assertNotIn(
            "uniqueItems", wire_schema["properties"]["refs"])
        self.assertIn(
            "at most 20 characters",
            wire_schema["properties"]["value"]["description"],
        )
        self.assertIn(
            "unique",
            wire_schema["properties"]["refs"]["description"],
        )
        self.assertEqual(schema["properties"]["value"]["maxLength"], 20)
        self.assertTrue(schema["properties"]["refs"]["uniqueItems"])
        self.assertEqual(raised.exception.stop_reason, "max_output_tokens")
        self.assertEqual(raised.exception.input_tokens, 321)
        self.assertEqual(raised.exception.output_tokens, 4096)
        self.assertEqual(raised.exception.thinking_tokens, 1024)
        self.assertEqual(len(endpoint.requests), 1)
        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(ledger.calls[0]["in_tok"], 321)
        self.assertEqual(ledger.calls[0]["out_tok"], 4096)

    def test_gemini_max_tokens_is_typed_and_honors_the_requested_cap(self):
        usage = SimpleNamespace(
            prompt_token_count=222,
            candidates_token_count=1000,
            thoughts_token_count=3000,
        )
        response = SimpleNamespace(
            response_id="gemini-truncated",
            text='{"value":"cut off',
            usage_metadata=usage,
            candidates=[SimpleNamespace(
                finish_reason=SimpleNamespace(name="MAX_TOKENS"))],
        )
        endpoint = _CreateEndpoint(response)
        genai = types.ModuleType("google.genai")
        genai.Client = lambda **_kwargs: SimpleNamespace(models=endpoint)
        genai_types = types.ModuleType("google.genai.types")
        genai_types.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)
        genai_types.HttpRetryOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        genai_types.HttpOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        google = types.ModuleType("google")
        google.genai = genai
        genai.types = genai_types
        ledger = V.Ledger(ceiling=500, label="test")
        schema = {
            "type": "object",
            "properties": {
                "value": {"type": "string", "maxLength": 20},
                "refs": {
                    "type": "array", "uniqueItems": True,
                    "items": {"type": "string"},
                },
            },
        }
        with mock.patch.dict(sys.modules, {
                "google": google,
                "google.genai": genai,
                "google.genai.types": genai_types,
        }):
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                llm = V.LLM("gemini", ledger, model="gemini-test")
                with self.assertRaises(V.VendorOutputTruncated) as raised:
                    llm.json_call_once(
                        "system", "user", schema, "investment",
                        max_tokens=4000, detail="gemini bounded unit",
                    )

        config = endpoint.requests[0]["config"]
        self.assertEqual(config.max_output_tokens, 4000)
        value_schema = config.response_json_schema["properties"]["value"]
        refs_schema = config.response_json_schema["properties"]["refs"]
        self.assertNotIn("maxLength", value_schema)
        self.assertNotIn("uniqueItems", refs_schema)
        self.assertIn("at most 20 characters", value_schema["description"])
        self.assertIn("unique", refs_schema["description"])
        self.assertEqual(raised.exception.stop_reason, "MAX_TOKENS")
        self.assertEqual(raised.exception.input_tokens, 222)
        self.assertEqual(raised.exception.output_tokens, 4000)
        self.assertEqual(raised.exception.thinking_tokens, 3000)
        self.assertEqual(len(endpoint.requests), 1)
        self.assertEqual(len(ledger.calls), 1)

    def test_completed_malformed_output_is_accounted_once_with_actual_usage(self):
        usage = SimpleNamespace(
            input_tokens=777,
            output_tokens=888,
            output_tokens_details=SimpleNamespace(reasoning_tokens=444),
        )
        response = SimpleNamespace(
            id="resp_malformed",
            status="completed",
            incomplete_details=None,
            output_text='{"value":',
            usage=usage,
            max_output_tokens=2000,
        )
        endpoint = _CreateEndpoint(response)
        openai = SimpleNamespace(OpenAI=lambda **_kwargs: SimpleNamespace(
            responses=endpoint))
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {"openai": openai}):
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                llm = V.LLM("openai", ledger, model="gpt-test")
                with self.assertRaises(V.VendorMalformedOutput) as raised:
                    llm.json_call_once(
                        "system", "user", {"type": "object"}, "investment",
                        max_tokens=2000, detail="malformed bounded unit",
                    )

        self.assertEqual(raised.exception.input_tokens, 777)
        self.assertEqual(raised.exception.output_tokens, 888)
        self.assertEqual(raised.exception.thinking_tokens, 444)
        self.assertEqual(len(endpoint.requests), 1)
        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(ledger.calls[0]["in_tok"], 777)
        self.assertEqual(ledger.calls[0]["out_tok"], 888)

    def test_legacy_json_call_retries_once_with_double_output_room(self):
        ledger = V.Ledger(ceiling=500, label="test")
        llm = V.LLM("anthropic", ledger, model="claude-test")
        attempts = []

        def transport(_system, _user, _schema, max_tokens):
            attempts.append(max_tokens)
            if len(attempts) == 1:
                raise V._ProviderOutputTruncated(
                    stop_reason="max_tokens",
                    request_id="first",
                    max_tokens=max_tokens,
                    input_tokens=10,
                    output_tokens=max_tokens,
                    thinking_tokens=max_tokens - 1,
                    partial_output="",
                )
            return {"value": "complete"}, 11, 12

        llm._call_anthropic = transport
        response = llm.json_call(
            "system", "user", {"type": "object"}, "foresight",
            max_tokens=100, detail="legacy bounded unit",
        )

        self.assertEqual(response, {"value": "complete"})
        self.assertEqual(attempts, [100, 200])
        self.assertEqual(len(ledger.calls), 2)

    def test_json_call_does_not_start_when_worst_case_usage_crosses_stage_cap(self):
        ledger = V.Ledger(ceiling=1.0, label="test")
        llm = V.LLM("anthropic", ledger, model="claude-opus-5")
        transport = mock.Mock(return_value=({}, 1, 1))
        llm._call_anthropic = transport

        with self.assertRaises(V.BudgetExhausted):
            llm.json_call(
                "system", "user", {"type": "object"}, "investment",
                max_tokens=3000, detail="bounded call",
            )

        transport.assert_not_called()
        self.assertEqual(ledger.calls, [])

    def test_concurrent_calls_reserve_worst_case_spend_before_transport(self):
        ledger = V.Ledger(ceiling=100.0, label="test")
        first = V.LLM("anthropic", ledger, model="claude-test")
        second = V.LLM("anthropic", ledger, model="claude-test")
        entered = threading.Event()
        finish = threading.Event()

        def blocking_transport(*_args):
            entered.set()
            if not finish.wait(2):
                raise AssertionError("test did not release the first provider call")
            return {"ok": True}, 1, 1

        first._call_anthropic = blocking_transport
        second_transport = mock.Mock(return_value=({"ok": True}, 1, 1))
        second._call_anthropic = second_transport
        first._call_cost_headroom = mock.Mock(return_value=3.0)
        second._call_cost_headroom = mock.Mock(return_value=3.0)

        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(
                first.json_call,
                "system", "first", {"type": "object"}, "investment",
            )
            self.assertTrue(entered.wait(1), "first provider call never started")
            try:
                with self.assertRaises(V.BudgetExhausted):
                    second.json_call(
                        "system", "second", {"type": "object"}, "investment",
                    )
                second_transport.assert_not_called()
            finally:
                finish.set()
            self.assertEqual(running.result(timeout=2), {"ok": True})

        self.assertEqual(ledger._reservations, {})

    def test_settlement_atomically_replaces_reservation_with_actual_spend(self):
        # The investment share is five percent, so this ledger has a $6 pass cap.
        ledger = V.Ledger(ceiling=120.0, label="test")
        first = ledger.reserve("investment", 3.0)

        # Publishing a completed call must also retire its worst-case reservation
        # before any concurrent caller can inspect the budget. With separate record
        # and release operations, a second $3 reservation is falsely rejected here.
        ledger.settle(
            first,
            "anthropic",
            "investment",
            model="claude-test",
            detail="settled unit",
        )
        second = ledger.reserve("investment", 3.0)
        ledger.release(second)

        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(ledger._reservations, {})

    def test_unsettled_reservation_survives_a_process_crash_at_full_bound(self):
        # The investment pass cap is $5. A $3 call that may have reached its provider
        # must remain charged after restart, so another $3 request cannot begin.
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "durable-reservation.json")
            first = V.Ledger(ceiling=100.0, label="before-crash")
            first.attach(spend_path)
            first.reserve(
                "investment", 3.0,
                vendor="anthropic", model="claude-test",
                request_sha256="a" * 64,
            )

            saved = V.strict_json_load(spend_path)
            self.assertEqual(len(saved["reservation_journal"]), 1)

            resumed = V.Ledger(ceiling=100.0, label="after-crash")
            resumed.attach(spend_path)
            resumed.load(spend_path)

            self.assertEqual(resumed.spent("investment"), 3.0)
            self.assertEqual(resumed.summary()["unresolved_reservations"], 1)
            with self.assertRaises(V.BudgetExhausted):
                resumed.reserve(
                    "investment", 3.0,
                    vendor="anthropic", model="claude-test",
                    request_sha256="b" * 64,
                )

    def test_settlement_above_reserved_bound_is_recorded_and_fails_closed(self):
        ledger = V.Ledger(ceiling=100.0, label="test")
        with mock.patch.dict(V.PRICES, {
                "jina": {"_default": {"out_per_mtok": 1000.0}},
        }, clear=False):
            reservation = ledger.reserve(
                "research", 0.1, vendor="jina",
                request_sha256="c" * 64,
            )
            with self.assertRaisesRegex(
                    V.VendorUsageExceededReservation, "reserved upper bound"):
                ledger.settle(
                    reservation, "jina", "research", out_tok=500,
                    detail="provider exceeded advertised cap",
                )

        self.assertEqual(ledger.calls[0]["cost"], 0.5)
        self.assertEqual(ledger._reservations, {})

    def test_usage_above_reservation_is_durable_terminal_after_restart(self):
        request_sha256 = "d" * 64
        actual_cost = 0.1000004
        response = {"result": {"citations": [], "lead_prose": "paid result"}}
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "usage-exceeded.json")
            ledger = V.Ledger(ceiling=100.0, label="before-restart")
            ledger.attach(spend_path)
            reservation = ledger.reserve(
                "research", 0.1, vendor="perplexity", model="sonar-pro",
                request_sha256=request_sha256,
            )
            with self.assertRaises(V.VendorUsageExceededReservation):
                ledger.settle(
                    reservation, "perplexity", "research", model="sonar-pro",
                    structured_result=V._retrieval_result_journal(
                        request_sha256, response),
                    billed_cost=actual_cost,
                )

            self.assertEqual(
                ledger.calls[0]["structured_result"]["outcome"],
                V.VendorUsageExceededReservation.code,
            )

            resumed = V.Ledger(ceiling=100.0, label="after-restart")
            resumed.attach(spend_path)
            resumed.load(spend_path)
            with self.assertRaises(V.VendorUsageExceededReservation):
                resumed.claim_retrieval_result(
                    "perplexity", "research", request_sha256,
                    model="sonar-pro",
                )

            self.assertEqual(resumed.spent("research"), actual_cost)

    def test_legacy_pass_aliases_share_one_reservation_pool(self):
        ledger = V.Ledger(ceiling=100.0, label="test")
        reservation = ledger.reserve("automated_challenge", 6.0)
        try:
            with self.assertRaises(V.BudgetExhausted):
                ledger.reserve("g2", 6.0)
        finally:
            ledger.release(reservation)

    def test_anthropic_refusal_is_typed_and_accounted_once(self):
        usage = SimpleNamespace(
            input_tokens=50,
            output_tokens=12,
            output_tokens_details=SimpleNamespace(thinking_tokens=2),
        )
        response = SimpleNamespace(
            id="msg_refused",
            content=[SimpleNamespace(type="text", text="I cannot provide that.")],
            usage=usage,
            stop_reason="refusal",
        )
        messages = _AnthropicMessages(response)
        anthropic = SimpleNamespace(
            Anthropic=lambda **_kwargs: SimpleNamespace(messages=messages),
            transform_schema=lambda schema: schema,
        )
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {"anthropic": anthropic}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                llm = V.LLM("anthropic", ledger, model="claude-test")
                with self.assertRaises(V.VendorOutputRejected) as raised:
                    llm.json_call_once(
                        "system", "user", {"type": "object"}, "investment",
                        max_tokens=100, detail="refusal unit",
                    )

        self.assertEqual(raised.exception.stop_reason, "refusal")
        self.assertEqual(len(messages.requests), 1)
        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(ledger.calls[0]["in_tok"], 50)
        self.assertEqual(ledger.calls[0]["out_tok"], 12)

    def test_openai_content_filter_is_typed_and_accounted_once(self):
        usage = SimpleNamespace(
            input_tokens=60,
            output_tokens=8,
            output_tokens_details=SimpleNamespace(reasoning_tokens=3),
        )
        response = SimpleNamespace(
            id="resp_filtered",
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="content_filter"),
            output_text="",
            output=[],
            usage=usage,
            max_output_tokens=100,
        )
        endpoint = _CreateEndpoint(response)
        openai = SimpleNamespace(OpenAI=lambda **_kwargs: SimpleNamespace(
            responses=endpoint))
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {"openai": openai}):
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                llm = V.LLM("openai", ledger, model="gpt-test")
                with self.assertRaises(V.VendorOutputRejected) as raised:
                    llm.json_call(
                        "system", "user", {"type": "object"}, "investment",
                        max_tokens=100, detail="filter unit",
                    )

        self.assertEqual(raised.exception.stop_reason, "content_filter")
        self.assertEqual(len(endpoint.requests), 1)
        self.assertEqual(len(ledger.calls), 1)

    def test_openai_failed_response_is_terminal_and_accounted_once(self):
        usage = SimpleNamespace(
            input_tokens=61,
            output_tokens=2,
            output_tokens_details=SimpleNamespace(reasoning_tokens=1),
        )
        response = SimpleNamespace(
            id="resp_failed",
            status="failed",
            error=SimpleNamespace(
                code="invalid_prompt",
                message="provider detail must not enter the checkpoint",
            ),
            incomplete_details=None,
            output_text="",
            output=[],
            usage=usage,
            max_output_tokens=100,
        )
        endpoint = _CreateEndpoint(response)
        openai = SimpleNamespace(OpenAI=lambda **_kwargs: SimpleNamespace(
            responses=endpoint))
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {"openai": openai}):
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                llm = V.LLM("openai", ledger, model="gpt-test")
                with self.assertRaises(V.VendorOutputRejected) as raised:
                    llm.json_call(
                        "system", "user", {"type": "object"}, "investment",
                        max_tokens=100, detail="failed response unit",
                    )

        self.assertEqual(raised.exception.stop_reason, "failed:invalid_prompt")
        self.assertEqual(len(endpoint.requests), 1)
        self.assertEqual(len(ledger.calls), 1)
        self.assertNotIn(
            "provider detail", ledger.calls[0]["detail"],
        )

    def test_openai_requires_completed_status_before_accepting_json(self):
        usage = SimpleNamespace(
            input_tokens=62,
            output_tokens=9,
            output_tokens_details=SimpleNamespace(reasoning_tokens=2),
        )
        cases = (
            ("cancelled", None, "non_complete:cancelled"),
            ("queued", None, "non_complete:queued"),
            ("in_progress", None, "non_complete:in_progress"),
            ("incomplete", "provider_busy", "incomplete:provider_busy"),
            (None, None, "non_complete:missing"),
        )
        for status, incomplete_reason, expected_reason in cases:
            with self.subTest(status=status, reason=incomplete_reason):
                response = SimpleNamespace(
                    id=f"resp_{status or 'missing'}",
                    status=status,
                    error=None,
                    incomplete_details=(
                        SimpleNamespace(reason=incomplete_reason)
                        if incomplete_reason else None
                    ),
                    # A non-complete provider state must remain terminal even when
                    # its convenience text happens to contain valid JSON.
                    output_text='{"value":"looks complete"}',
                    output=[],
                    usage=usage,
                    max_output_tokens=100,
                )
                endpoint = _CreateEndpoint(response)
                openai = SimpleNamespace(OpenAI=lambda **_kwargs: SimpleNamespace(
                    responses=endpoint))
                ledger = V.Ledger(ceiling=500, label="test")
                with mock.patch.dict(sys.modules, {"openai": openai}):
                    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                        llm = V.LLM("openai", ledger, model="gpt-test")
                        with self.assertRaises(V.VendorOutputRejected) as raised:
                            llm.json_call(
                                "system", "user", {"type": "object"}, "investment",
                                max_tokens=100, detail="non-complete response unit",
                            )

                self.assertEqual(raised.exception.stop_reason, expected_reason)
                self.assertEqual(len(endpoint.requests), 1)
                self.assertEqual(len(ledger.calls), 1)

    def test_anthropic_requires_end_turn_before_accepting_json(self):
        usage = SimpleNamespace(
            input_tokens=51,
            output_tokens=10,
            output_tokens_details=SimpleNamespace(thinking_tokens=2),
        )
        for stop_reason in (
                "pause_turn", "tool_use", "stop_sequence", "",
                "model_context_window_exceeded"):
            with self.subTest(stop_reason=stop_reason or "missing"):
                response = SimpleNamespace(
                    id=f"msg_{stop_reason or 'missing'}",
                    content=[SimpleNamespace(
                        type="text", text='{"value":"looks complete"}')],
                    usage=usage,
                    stop_reason=stop_reason,
                )
                messages = _AnthropicMessages(response)
                anthropic = SimpleNamespace(
                    Anthropic=lambda **_kwargs: SimpleNamespace(messages=messages),
                    transform_schema=lambda schema: schema,
                )
                ledger = V.Ledger(ceiling=500, label="test")
                with mock.patch.dict(sys.modules, {"anthropic": anthropic}):
                    with mock.patch.dict(
                            os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                        llm = V.LLM("anthropic", ledger, model="claude-test")
                        with self.assertRaises(V.VendorOutputRejected) as raised:
                            # Use the legacy wrapper to prove context-window and other
                            # non-completion states do not trigger the larger retry.
                            llm.json_call(
                                "system", "user", {"type": "object"}, "investment",
                                max_tokens=100, detail="non-complete response unit",
                            )

                self.assertEqual(
                    raised.exception.stop_reason,
                    f"non_complete:{stop_reason or 'missing'}",
                )
                self.assertEqual(len(messages.requests), 1)
                self.assertEqual(len(ledger.calls), 1)

    def test_gemini_safety_stop_is_typed_and_accounted_once(self):
        usage = SimpleNamespace(
            prompt_token_count=70,
            candidates_token_count=5,
            thoughts_token_count=1,
        )
        response = SimpleNamespace(
            response_id="gemini-filtered",
            text="",
            usage_metadata=usage,
            prompt_feedback=None,
            candidates=[SimpleNamespace(
                finish_reason=SimpleNamespace(name="SAFETY"))],
        )
        endpoint = _CreateEndpoint(response)
        genai = types.ModuleType("google.genai")
        genai.Client = lambda **_kwargs: SimpleNamespace(models=endpoint)
        genai_types = types.ModuleType("google.genai.types")
        genai_types.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)
        genai_types.HttpRetryOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        genai_types.HttpOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        google = types.ModuleType("google")
        google.genai = genai
        genai.types = genai_types
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {
                "google": google,
                "google.genai": genai,
                "google.genai.types": genai_types,
        }):
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                llm = V.LLM("gemini", ledger, model="gemini-test")
                with self.assertRaises(V.VendorOutputRejected) as raised:
                    llm.json_call(
                        "system", "user", {"type": "object"}, "investment",
                        max_tokens=100, detail="safety unit",
                    )

        self.assertEqual(raised.exception.stop_reason, "SAFETY")
        self.assertEqual(len(endpoint.requests), 1)
        self.assertEqual(len(ledger.calls), 1)

    def test_gemini_prompt_block_without_candidate_is_terminal(self):
        usage = SimpleNamespace(
            prompt_token_count=71,
            candidates_token_count=0,
            thoughts_token_count=0,
        )
        response = SimpleNamespace(
            response_id="gemini-prompt-blocked",
            usage_metadata=usage,
            prompt_feedback=SimpleNamespace(
                block_reason=SimpleNamespace(name="SAFETY")),
            candidates=[],
        )
        endpoint = _CreateEndpoint(response)
        genai = types.ModuleType("google.genai")
        genai.Client = lambda **_kwargs: SimpleNamespace(models=endpoint)
        genai_types = types.ModuleType("google.genai.types")
        genai_types.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)
        genai_types.HttpRetryOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        genai_types.HttpOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        google = types.ModuleType("google")
        google.genai = genai
        genai.types = genai_types
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {
                "google": google,
                "google.genai": genai,
                "google.genai.types": genai_types,
        }):
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                llm = V.LLM("gemini", ledger, model="gemini-test")
                with self.assertRaises(V.VendorOutputRejected) as raised:
                    llm.json_call(
                        "system", "user", {"type": "object"}, "investment",
                        max_tokens=100, detail="prompt block unit",
                    )

        self.assertEqual(raised.exception.stop_reason, "SAFETY")
        self.assertEqual(len(endpoint.requests), 1)
        self.assertEqual(len(ledger.calls), 1)

    def test_anthropic_transforms_unsupported_constraints_before_request(self):
        usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=10,
            output_tokens_details=SimpleNamespace(thinking_tokens=0),
        )
        response = SimpleNamespace(
            id="msg_complete",
            content=[SimpleNamespace(type="text", text='{"value":"short"}')],
            usage=usage,
            stop_reason="end_turn",
        )
        messages = _AnthropicMessages(response)
        transform_schema = mock.Mock(side_effect=V._openai_schema)
        anthropic = SimpleNamespace(
            Anthropic=lambda **_kwargs: SimpleNamespace(messages=messages),
            transform_schema=transform_schema,
        )
        schema = {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string", "maxLength": 20,
                    "description": "A bounded value.",
                },
            },
            "required": ["value"],
            "additionalProperties": False,
        }
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {"anthropic": anthropic}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                llm = V.LLM("anthropic", ledger, model="claude-test")
                result = llm.json_call(
                    "system", "user", schema, "investment", max_tokens=100,
                )

        self.assertEqual(result, {"value": "short"})
        transform_schema.assert_called_once_with(schema)
        wire_schema = messages.requests[0]["output_config"]["format"]["schema"]
        self.assertNotIn("maxLength", wire_schema["properties"]["value"])
        self.assertEqual(schema["properties"]["value"]["maxLength"], 20)

    def test_anthropic_normalizes_nullable_type_arrays_before_sdk_transform(self):
        usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=10,
            output_tokens_details=SimpleNamespace(thinking_tokens=0),
        )
        response = SimpleNamespace(
            id="msg_nullable_complete",
            content=[SimpleNamespace(type="text", text='{"value":null}')],
            usage=usage,
            stop_reason="end_turn",
        )
        messages = _AnthropicMessages(response)
        transformed_inputs = []

        def sdk_transform(schema):
            # Faithful to the SDK contract: list-valued ``type`` currently raises
            # before the transport. Record the accepted input for semantic checks.
            def reject_type_arrays(value):
                if isinstance(value, dict):
                    self.assertFalse(isinstance(value.get("type"), list))
                    for child in value.values():
                        reject_type_arrays(child)
                elif isinstance(value, list):
                    for child in value:
                        reject_type_arrays(child)

            reject_type_arrays(schema)
            transformed_inputs.append(schema)
            return schema

        anthropic = SimpleNamespace(
            Anthropic=lambda **_kwargs: SimpleNamespace(messages=messages),
            transform_schema=sdk_transform,
        )
        schema = {
            "type": "object",
            "properties": {
                "value": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 1,
                    "description": "A bounded value or an explicit unknown.",
                },
            },
            "required": ["value"],
            "additionalProperties": False,
        }
        ledger = V.Ledger(ceiling=500, label="test")
        with mock.patch.dict(sys.modules, {"anthropic": anthropic}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                llm = V.LLM("anthropic", ledger, model="claude-test")
                result = llm.json_call_once(
                    "system", "user", schema, "investment", max_tokens=100,
                )

        self.assertEqual(result, {"value": None})
        nullable = transformed_inputs[0]["properties"]["value"]
        self.assertEqual(nullable["description"], schema["properties"]["value"]["description"])
        self.assertEqual(nullable["anyOf"][0], {
            "type": "number", "minimum": 0, "maximum": 1,
        })
        self.assertEqual(nullable["anyOf"][1], {"type": "null"})
        self.assertEqual(schema["properties"]["value"]["type"], ["number", "null"])

    def test_spend_checkpoint_refuses_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "target.json")
            link = os.path.join(directory, "spend.json")
            V.atomic_write_json(target, {"summary": {}, "calls": []})
            os.symlink(target, link)
            ledger = V.Ledger(ceiling=500, label="test")

            with self.assertRaisesRegex(ValueError, "regular file"):
                ledger.attach(link)

    def test_token_limited_response_is_accounted_and_not_replayed(self):
        usage = SimpleNamespace(
            input_tokens=1234,
            output_tokens=20000,
            output_tokens_details=SimpleNamespace(thinking_tokens=7000),
        )
        response = SimpleNamespace(
            id="msg_truncated",
            content=[SimpleNamespace(type="text", text='{"options":[{"title":"cut off')],
            usage=usage,
            stop_reason="max_tokens",
        )
        messages = _AnthropicMessages(response)
        client = SimpleNamespace(messages=messages)
        ledger = V.Ledger(ceiling=500, label="test")
        anthropic = SimpleNamespace(
            Anthropic=lambda **_kwargs: client,
            transform_schema=lambda schema: schema,
        )
        with mock.patch.dict(sys.modules, {"anthropic": anthropic}):
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                llm = V.LLM("anthropic", ledger, model="claude-opus-5")
                with self.assertRaises(V.VendorOutputTruncated) as raised:
                    llm.json_call_once(
                        "system",
                        "user",
                        {"type": "object"},
                        "investment",
                        max_tokens=20000,
                        detail="investment options and CBA",
                    )

        error = raised.exception
        self.assertEqual(error.stop_reason, "max_tokens")
        self.assertEqual(error.max_tokens, 20000)
        self.assertEqual(error.input_tokens, 1234)
        self.assertEqual(error.output_tokens, 20000)
        self.assertEqual(error.thinking_tokens, 7000)
        self.assertEqual(error.pass_name, "investment")
        self.assertEqual(error.detail, "investment options and CBA")
        self.assertEqual(error.request_id, "msg_truncated")
        self.assertEqual(len(messages.requests), 1)
        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(ledger.calls[0]["in_tok"], 1234)
        self.assertEqual(ledger.calls[0]["out_tok"], 20000)
        self.assertEqual(
            ledger.calls[0]["detail"],
            "TRUNCATED investment options and CBA; stop_reason=max_tokens; "
            "thinking_tokens=7000",
        )

    def test_exa_search_reserves_the_next_search_before_transport(self):
        per_search = 1.0
        ledger = V.Ledger(ceiling=(per_search * 1.5) / 0.35, label="test")
        transport = mock.Mock(return_value={"results": []})

        with mock.patch.dict(
                V.PRICES, {"exa": {"per_search": per_search}}, clear=False):
            with mock.patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
                with mock.patch.object(V, "_http", transport):
                    V.exa_search("first", ledger, "research")
                    with self.assertRaises(V.BudgetExhausted):
                        V.exa_search("must not leave", ledger, "research")

        self.assertEqual(transport.call_count, 1)
        self.assertEqual(len(ledger.calls), 1)

    def test_exa_ambiguous_transport_is_not_retried_and_consumes_upper_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "exa-ambiguous.json")
            ledger = V.Ledger(ceiling=1.0, label="test")
            ledger.attach(spend_path)
            transport = mock.Mock(side_effect=TimeoutError("response lost"))

            with mock.patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
                with mock.patch.object(V.urllib.request, "urlopen", transport):
                    with mock.patch.object(V.time, "sleep"):
                        with self.assertRaisesRegex(
                                V.VendorError, "outcome is ambiguous"):
                            V.exa_search("ambiguous", ledger, "research")

            self.assertEqual(transport.call_count, 1)
            self.assertEqual(len(ledger.calls), 1)
            self.assertEqual(ledger.calls[0]["cost"], 0.007)
            self.assertIn("AMBIGUOUS-UPPER-BOUND", ledger.calls[0]["detail"])

            resumed = V.Ledger(ceiling=1.0, label="resumed")
            resumed.attach(spend_path)
            resumed.load(spend_path)
            with mock.patch.object(
                    V, "_http",
                    side_effect=AssertionError("ambiguous request was reissued")) as http:
                with self.assertRaisesRegex(V.VendorError, "ambiguous"):
                    V.exa_search("ambiguous", resumed, "research")
            http.assert_not_called()

    def test_exa_malformed_success_is_charged_but_not_reported_as_no_evidence(self):
        ledger = V.Ledger(ceiling=1.0, label="test")
        with mock.patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
            with mock.patch.object(V, "_http", return_value="not JSON"):
                with self.assertRaisesRegex(
                        V.VendorError, "malformed Exa response"):
                    V.exa_search("malformed", ledger, "research")

        self.assertEqual(ledger.calls[0]["cost"], 0.007)
        self.assertEqual(
            ledger.calls[0]["structured_result"]["outcome"],
            "retrieval_output_malformed",
        )

    def test_jina_fetch_reserves_total_provider_cap_with_metadata_headroom(self):
        """The strict provider cap, not only returned content, bounds spend."""
        content_token_cap = 500
        metadata_headroom = 4096
        strict_token_budget = content_token_cap + metadata_headroom
        out_per_mtok = 1000.0
        worst_case = strict_token_budget / 1e6 * out_per_mtok
        ledger = V.Ledger(ceiling=(worst_case * 1.5) / 0.35, label="test")
        transport = mock.Mock(return_value={
            "data": {
                "content": "verified page",
                "usage": {"tokens": strict_token_budget},
            },
        })

        with mock.patch.dict(V.PRICES, {
                "jina": {"_default": {"out_per_mtok": out_per_mtok}},
        }, clear=False):
            with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                with mock.patch.object(V, "_http", transport):
                    self.assertEqual(
                        V.jina_fetch(
                            "https://example.test/page", ledger, "research",
                            max_chars=content_token_cap,
                        ),
                        "verified page",
                    )
                    with self.assertRaises(V.BudgetExhausted):
                        V.jina_fetch(
                            "https://example.test/other", ledger, "research",
                            max_chars=content_token_cap,
                        )

        self.assertEqual(transport.call_count, 1)
        headers = transport.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Max-Tokens"], str(content_token_cap))
        self.assertEqual(headers["X-Token-Budget"], str(strict_token_budget))
        self.assertEqual(ledger.calls[0]["out_tok"], strict_token_budget)

    def test_jina_usage_above_strict_cap_is_terminal_across_restart(self):
        content_token_cap = 500
        strict_token_budget = (
            content_token_cap + V.JINA_READER_METADATA_HEADROOM_TOKENS)
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "jina-over-cap.json")
            ledger = V.Ledger(ceiling=1.0, label="test")
            ledger.attach(spend_path)
            response = {
                "data": {
                    "content": "provider exceeded the advertised strict cap",
                    "usage": {"tokens": strict_token_budget + 1},
                },
            }
            with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                with mock.patch.object(V, "_http", return_value=response) as transport:
                    with self.assertRaises(V.VendorUsageExceededReservation):
                        V.jina_fetch(
                            "https://example.test/over-cap", ledger, "research",
                            max_chars=content_token_cap,
                        )

            resumed = V.Ledger(ceiling=1.0, label="resumed")
            resumed.attach(spend_path)
            resumed.load(spend_path)
            with mock.patch.object(
                    V, "_http",
                    side_effect=AssertionError("over-cap request was reissued")):
                with self.assertRaises(V.VendorUsageExceededReservation):
                    V.jina_fetch(
                        "https://example.test/over-cap", resumed, "research",
                        max_chars=content_token_cap,
                    )

        self.assertEqual(transport.call_count, 1)

    def test_jina_fetch_separates_content_trim_from_total_provider_cap(self):
        """A total cap retains metadata room while the content trim stays narrow."""
        ledger = V.Ledger(ceiling=1.0, label="test")
        transport = mock.Mock(return_value={
            "data": {"content": "verified page", "usage": {"tokens": 500}},
        })

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(V, "_http", transport):
                self.assertEqual(
                    V.jina_fetch(
                        "https://example.test/page", ledger, "research",
                        max_chars=500,
                    ),
                    "verified page",
                )

        headers = transport.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Max-Tokens"], "500")
        self.assertEqual(
            headers["X-Token-Budget"],
            str(500 + V.JINA_READER_METADATA_HEADROOM_TOKENS),
        )

    def test_same_jina_url_in_two_scan_lanes_does_not_cross_claim(self):
        response = {
            "data": {"content": "verified page", "usage": {"tokens": 10}},
        }
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "shared-scan-spend.json")
            country = V.Ledger(ceiling=500, label="country")
            country.attach(spend_path)
            with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                with mock.patch.object(V, "_http", return_value=response):
                    V.jina_fetch(
                        "https://example.test/shared", country,
                        "country_research", max_chars=500,
                    )

            international = V.Ledger(ceiling=500, label="international")
            international.attach(spend_path)
            international.load(spend_path)
            transport = mock.Mock(return_value=response)
            with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                with mock.patch.object(V, "_http", transport):
                    self.assertEqual(
                        V.jina_fetch(
                            "https://example.test/shared", international,
                            "international_lessons", max_chars=500,
                        ),
                        "verified page",
                    )

            self.assertEqual(transport.call_count, 1)
            self.assertEqual(len(international.calls), 2)

    def test_concurrent_identical_jina_fetches_share_one_paid_result(self):
        workers = 4
        start = threading.Barrier(workers)
        response = {
            "data": {"content": "shared page", "usage": {"tokens": 10}},
        }

        def transport(*_args, **_kwargs):
            # Keep the first request in flight long enough for all peers to exercise
            # the identical-request concurrency path.
            time.sleep(0.05)
            return response

        ledger = V.Ledger(ceiling=500, label="test")

        def fetch():
            start.wait(timeout=2)
            return V.jina_fetch(
                "https://example.test/shared", ledger, "research",
                max_chars=500,
            )

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(V, "_http", side_effect=transport) as http:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    results = list(pool.map(lambda _index: fetch(), range(workers)))

        self.assertEqual(results, ["shared page"] * workers)
        self.assertEqual(http.call_count, 1)
        self.assertEqual(len(ledger.calls), 1)

    def test_jina_explicit_rejection_keeps_conservative_bound_and_replays_durably(self):
        ledger = V.Ledger(ceiling=1.0, label="test")
        rejection = V.JinaSourceRejected(
            "provider rejected", status=422, provider_status=42203,
            provider_name="SubmittedDataMalformedError")

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(
                    V, "_http",
                    side_effect=rejection) as transport:
                with self.assertRaisesRegex(
                        V.JinaSourceRejected, "provider rejected"):
                    V.jina_fetch(
                        "https://example.test/failure", ledger, "research",
                        max_chars=500,
                    )
                with self.assertRaisesRegex(
                        V.JinaSourceRejected, "retrieval failure"):
                    V.jina_fetch(
                        "https://example.test/failure", ledger, "research",
                        max_chars=500,
                    )

        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(transport.call_count, 1)
        strict_token_budget = 500 + V.JINA_READER_METADATA_HEADROOM_TOKENS
        self.assertEqual(ledger.calls[0]["out_tok"], strict_token_budget)
        self.assertEqual(
            ledger.calls[0]["cost"],
            ledger.estimated_cost("jina", out_tok=strict_token_budget),
        )
        self.assertEqual(
            ledger.calls[0]["structured_result"]["outcome"],
            "retrieval_source_rejected",
        )
        self.assertEqual(ledger._reservations, {})

    def test_jina_account_rejection_is_terminal_and_never_reissued(self):
        """An API-key or credit failure is not an evidence-source rejection."""
        ledger = V.Ledger(ceiling=1.0, label="test")
        response = V.urllib.error.HTTPError(
            "https://r.jina.ai/https://example.test/account",
            402,
            "Payment Required",
            {},
            io.BytesIO(b'{"code":402,"name":"PaymentRequired"}'),
        )

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(
                    V.urllib.request, "urlopen", side_effect=response) as transport:
                with mock.patch.object(V.time, "sleep"):
                    with self.assertRaisesRegex(
                            V.VendorPaidRequestTerminal, "Reader endpoint"):
                        V.jina_fetch(
                            "https://example.test/account", ledger, "research",
                            max_chars=500,
                        )
                    with self.assertRaisesRegex(
                            V.VendorPaidRequestTerminal, "durable"):
                        V.jina_fetch(
                            "https://example.test/account", ledger, "research",
                            max_chars=500,
                        )

        response.close()
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(len(ledger.calls), 1)
        self.assertEqual(
            ledger.calls[0]["out_tok"],
            500 + V.JINA_READER_METADATA_HEADROOM_TOKENS,
        )
        self.assertEqual(
            ledger.calls[0]["structured_result"]["outcome"],
            "retrieval_http_terminal",
        )

    def test_jina_non_source_http_failures_do_not_become_source_gaps(self):
        """Account, throttle, and service errors must fail closed before a retry."""
        for status in (401, 402, 403, 404, 409, 422, 429, 503):
            with self.subTest(status=status):
                ledger = V.Ledger(ceiling=1.0, label=f"test-{status}")
                response = V.urllib.error.HTTPError(
                    "https://r.jina.ai/https://example.test/endpoint-failure",
                    status,
                    "endpoint failure",
                    {"Retry-After": "0"},
                    io.BytesIO(b'{"name":"EndpointFailure"}'),
                )
                with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                    with mock.patch.object(
                            V.urllib.request, "urlopen", side_effect=response):
                        with mock.patch.object(V.time, "sleep") as sleeper:
                            with self.assertRaises(V.VendorPaidRequestTerminal):
                                V.jina_fetch(
                                    "https://example.test/endpoint-failure",
                                    ledger, "research", max_chars=500,
                                )
                        if status == 429:
                            sleeper.assert_not_called()
                response.close()
                self.assertEqual(
                    ledger.calls[0]["structured_result"]["outcome"],
                    "retrieval_http_terminal",
                )

    def test_jina_40904_budget_rejection_is_source_local_and_durable(self):
        """The deliberate per-page strict cap can reject one source safely."""
        ledger = V.Ledger(ceiling=1.0, label="test")
        response = V.urllib.error.HTTPError(
            "https://r.jina.ai/https://example.test/over-budget",
            409,
            "Conflict",
            {},
            io.BytesIO(
                b'{"code":409,"name":"BudgetExceededError","status":40904}'
            ),
        )

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(
                    V.urllib.request, "urlopen", side_effect=response) as transport:
                with mock.patch.object(V.time, "sleep"):
                    with self.assertRaises(V.JinaSourceRejected) as raised:
                        V.jina_fetch(
                            "https://example.test/over-budget", ledger, "research",
                            max_chars=500,
                        )
                    self.assertEqual(raised.exception.status, 409)
                    self.assertEqual(raised.exception.provider_status, 40904)
                    self.assertEqual(
                        raised.exception.provider_name, "BudgetExceededError")
                    with self.assertRaisesRegex(
                            V.VendorHTTPRejected, "durable"):
                        V.jina_fetch(
                            "https://example.test/over-budget", ledger, "research",
                            max_chars=500,
                        )

        response.close()
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(
            ledger.calls[0]["structured_result"]["outcome"],
            "retrieval_source_rejected",
        )

    def test_jina_42203_submitted_data_rejection_is_source_local(self):
        ledger = V.Ledger(ceiling=1.0, label="test")
        response = V.urllib.error.HTTPError(
            "https://r.jina.ai/https://example.test/malformed",
            422,
            "Unprocessable Content",
            {},
            io.BytesIO(
                b'{"code":422,"name":"SubmittedDataMalformedError","status":42203}'
            ),
        )

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(
                    V.urllib.request, "urlopen", side_effect=response) as transport:
                with self.assertRaises(V.JinaSourceRejected) as raised:
                    V.jina_fetch(
                        "https://example.test/malformed?token=not-for-ledger",
                        ledger, "research",
                        max_chars=500,
                    )

        response.close()
        self.assertEqual(raised.exception.http_status, 422)
        self.assertEqual(raised.exception.provider_status, 42203)
        self.assertEqual(
            raised.exception.provider_name, "SubmittedDataMalformedError")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(
            ledger.calls[0]["structured_result"]["outcome"],
            "retrieval_source_rejected",
        )
        self.assertNotIn("not-for-ledger", ledger.calls[0]["detail"])
        self.assertNotIn(
            "not-for-ledger", str(ledger.calls[0]["structured_result"]))

    def test_jina_classified_http_outcomes_replay_without_transport_after_restart(self):
        cases = (
            (
                "source-budget",
                409,
                b'{"code":409,"name":"BudgetExceededError","status":40904}',
                V.JinaSourceRejected,
                "retrieval_source_rejected",
            ),
            (
                "source-malformed",
                422,
                b'{"code":422,"name":"SubmittedDataMalformedError","status":42203}',
                V.JinaSourceRejected,
                "retrieval_source_rejected",
            ),
            (
                "terminal",
                402,
                b'{"code":402,"name":"PaymentRequired"}',
                V.VendorPaidRequestTerminal,
                "retrieval_http_terminal",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            for label, status, payload, error_type, outcome in cases:
                with self.subTest(label=label):
                    spend_path = os.path.join(directory, f"jina-{label}.json")
                    ledger = V.Ledger(ceiling=1.0, label=label)
                    ledger.attach(spend_path)
                    response = V.urllib.error.HTTPError(
                        f"https://r.jina.ai/https://example.test/{label}",
                        status, "rejected", {}, io.BytesIO(payload),
                    )
                    with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                        with mock.patch.object(
                                V.urllib.request, "urlopen", side_effect=response) as transport:
                            with mock.patch.object(V.time, "sleep"):
                                with self.assertRaises(error_type):
                                    V.jina_fetch(
                                        f"https://example.test/{label}", ledger,
                                        "research", max_chars=500,
                                    )
                    response.close()
                    self.assertEqual(transport.call_count, 1)
                    self.assertEqual(
                        ledger.calls[0]["structured_result"]["outcome"], outcome)
                    spent_before_restart = ledger.spent()

                    resumed = V.Ledger(ceiling=1.0, label=f"{label}-resumed")
                    resumed.attach(spend_path)
                    resumed.load(spend_path)
                    with mock.patch.object(
                            V, "_http",
                            side_effect=AssertionError("classified request was reissued")):
                        with self.assertRaises(error_type) as raised:
                            V.jina_fetch(
                                f"https://example.test/{label}", resumed,
                                "research", max_chars=500,
                            )
                    self.assertEqual(resumed.spent(), spent_before_restart)
                    if error_type is V.JinaSourceRejected:
                        self.assertEqual(raised.exception.http_status, status)

    def test_jina_ambiguous_transport_consumes_bound_without_a_retry(self):
        ledger = V.Ledger(ceiling=1.0, label="test")
        transport = mock.Mock(side_effect=TimeoutError("response lost"))

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(V.urllib.request, "urlopen", transport):
                with mock.patch.object(V.time, "sleep"):
                    with self.assertRaisesRegex(
                            V.VendorError, "outcome is ambiguous"):
                        V.jina_fetch(
                            "https://example.test/ambiguous", ledger, "research",
                            max_chars=500,
                        )

        self.assertEqual(transport.call_count, 1)
        self.assertEqual(
            ledger.calls[0]["out_tok"],
            500 + V.JINA_READER_METADATA_HEADROOM_TOKENS,
        )
        self.assertIn("AMBIGUOUS-UPPER-BOUND", ledger.calls[0]["detail"])

    def test_jina_unmetered_success_consumes_the_hard_upper_bound(self):
        token_cap = 500
        ledger = V.Ledger(ceiling=1.0, label="test")

        with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            with mock.patch.object(V, "_http", return_value={
                    "data": {"content": "unmetered page"},
            }):
                with self.assertRaisesRegex(
                        V.VendorError, "billed-token usage"):
                    V.jina_fetch(
                        "https://example.test/unmetered", ledger, "research",
                        max_chars=token_cap,
                    )

        self.assertEqual(
            ledger.calls[0]["out_tok"],
            token_cap + V.JINA_READER_METADATA_HEADROOM_TOKENS,
        )
        self.assertIn("UNMETERED-UPPER-BOUND", ledger.calls[0]["detail"])
        self.assertEqual(ledger._reservations, {})

    def test_jina_nonfinite_success_response_settles_and_replays_after_restart(self):
        """A malformed 200 response cannot leave a paid Reader claim pending."""
        token_cap = 500
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "jina-nonfinite-success.json")
            ledger = V.Ledger(ceiling=1.0, label="test")
            ledger.attach(spend_path)
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            response.read.return_value = (
                b'{"data":{"usage":{"tokens":NaN}}}')

            with mock.patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
                with mock.patch.object(
                        V.urllib.request, "urlopen", return_value=response) as transport:
                    with self.assertRaises(V.VendorUsageUnmetered):
                        V.jina_fetch(
                            "https://example.test/nonfinite", ledger, "research",
                            max_chars=token_cap,
                        )

            self.assertEqual(transport.call_count, 1)
            self.assertEqual(len(ledger.calls), 1)
            self.assertEqual(
                ledger.calls[0]["structured_result"]["outcome"],
                "retrieval_usage_missing",
            )
            self.assertEqual(ledger._reservations, {})
            spent_before_restart = ledger.spent()

            resumed = V.Ledger(ceiling=1.0, label="resumed")
            resumed.attach(spend_path)
            resumed.load(spend_path)
            with mock.patch.object(
                    V, "_http",
                    side_effect=AssertionError("nonfinite response was reissued")) as http:
                with self.assertRaises(V.VendorUsageUnmetered):
                    V.jina_fetch(
                        "https://example.test/nonfinite", resumed, "research",
                        max_chars=token_cap,
                    )
            http.assert_not_called()
            self.assertEqual(resumed.spent(), spent_before_restart)

    def test_duplicate_success_usage_settles_unmetered_and_never_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "spend.json")
            ledger = V.Ledger(ceiling=1, label="synthetic")
            ledger.attach(path)
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = (b'{"data":{"content":"evidence","usage":{"tokens":3000,"tokens":0}}}')
            with mock.patch.dict(os.environ, {"JINA_API_KEY": "fixture"}):
                with mock.patch.object(V.urllib.request, "urlopen", return_value=response) as transport:
                    with self.assertRaises(V.VendorUsageUnmetered):
                        V.jina_fetch("https://example.test/page", ledger, "research", max_chars=500)
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(ledger.calls[0]["out_tok"], 4596)
            self.assertEqual(ledger._reservations, {})
            resumed = V.Ledger(ceiling=1, label="synthetic")
            resumed.attach(path)
            resumed.load(path)
            with mock.patch.object(V, "_http") as http:
                with self.assertRaises(V.VendorUsageUnmetered):
                    V.jina_fetch("https://example.test/page", resumed, "research", max_chars=500)
            http.assert_not_called()
            self.assertEqual(resumed.spent(), ledger.spent())

    def test_jina_ambiguous_error_envelopes_are_terminal(self):
        for body in (
            b'{"status":40101,"status":42203,"name":"SubmittedDataMalformedError"}',
            b'{"status":42203,"name":"AuthenticationError","name":"SubmittedDataMalformedError"}',
            b'{"code":401,"status":42203,"name":"SubmittedDataMalformedError"}',
        ):
            with self.subTest(body=body):
                ledger = V.Ledger(ceiling=1, label="synthetic")
                error = V.urllib.error.HTTPError("https://example.test", 422, "rejected", {}, io.BytesIO(body))
                with mock.patch.dict(os.environ, {"JINA_API_KEY": "fixture"}):
                    with mock.patch.object(V.urllib.request, "urlopen", side_effect=error):
                        with self.assertRaises(V.VendorPaidRequestTerminal):
                            V.jina_fetch("https://example.test/page", ledger, "research", max_chars=500)
                self.assertEqual(ledger.calls[0]["structured_result"]["outcome"], "retrieval_http_terminal")

    def test_jina_malformed_content_with_valid_usage_is_terminal_and_not_replayed(self):
        # Post-incident audit: token usage does not validate the evidence payload.
        for content in ({"invented": "evidence " * 40}, ["text"], 42, None):
            with self.subTest(content_type=type(content).__name__):
                with tempfile.TemporaryDirectory() as directory:
                    path = os.path.join(directory, "spend.json")
                    ledger = V.Ledger(ceiling=1, label="synthetic")
                    ledger.attach(path)
                    with mock.patch.dict(os.environ, {"JINA_API_KEY": "fixture"}):
                        with mock.patch.object(V, "_http", return_value={
                                "data": {"content": content, "usage": {"tokens": 10}}}) as http:
                            with self.assertRaises(V.VendorUsageUnmetered):
                                V.jina_fetch("https://example.test/page", ledger, "research", max_chars=500)
                    self.assertEqual(http.call_count, 1)
                    self.assertEqual(ledger.calls[0]["out_tok"], 4596)
                    self.assertEqual(ledger._reservations, {})
                    resumed = V.Ledger(ceiling=1, label="synthetic")
                    resumed.attach(path)
                    resumed.load(path)
                    with mock.patch.object(V, "_http") as http:
                        with self.assertRaises(V.VendorUsageUnmetered):
                            V.jina_fetch("https://example.test/page", resumed, "research", max_chars=500)
                    http.assert_not_called()

    def test_jina_failure_diagnostics_do_not_disclose_provider_or_url_material(self):
        import traceback
        import json
        sentinel = "SYNTHETIC_PRIVATE_VALUE"
        for status, name, provider_status in ((422, "SubmittedDataMalformedError", 42203),
                                               (402, sentinel, 40200)):
            with self.subTest(status=status):
                ledger = V.Ledger(ceiling=1, label="synthetic")
                url = f"https://user:{sentinel}@example.test/{sentinel}?key={sentinel}#{sentinel}"
                body = json.dumps({"status": provider_status, "name": name, "message": sentinel}).encode()
                error = V.urllib.error.HTTPError(url, status, sentinel, {}, io.BytesIO(body))
                with mock.patch.dict(os.environ, {"JINA_API_KEY": "fixture"}):
                    with mock.patch.object(V.urllib.request, "urlopen", side_effect=error):
                        try:
                            V.jina_fetch(url, ledger, "research", max_chars=500)
                        except V.VendorError as caught:
                            rendered = "".join(traceback.format_exception(caught))
                        else:
                            self.fail("rejection was accepted")
                self.assertNotIn(sentinel, rendered)
                self.assertNotIn(sentinel, json.dumps(ledger.snapshot()))

    def test_perplexity_reserves_capped_request_before_transport(self):
        per_request = 1.0
        ledger = V.Ledger(ceiling=(per_request * 1.5) / 0.35, label="test")
        transport = mock.Mock(return_value={
            "usage": {
                "prompt_tokens": 0, "completion_tokens": 0,
                "cost": {"total_cost": per_request},
            },
            "choices": [{"message": {"content": "lead"}}],
            "citations": [],
        })

        with mock.patch.dict(V.PRICES, {
                "perplexity": {
                    "sonar-pro": {
                        "in_per_mtok": 0.0,
                        "out_per_mtok": 0.0,
                        "per_request": per_request,
                    },
                },
        }, clear=False):
            with mock.patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"}):
                with mock.patch.object(V, "_http", transport):
                    with mock.patch.object(V, "_PPX_MIN_GAP", 0):
                        V.perplexity_citations("first", ledger, "research")
                        with self.assertRaises(V.BudgetExhausted):
                            V.perplexity_citations(
                                "must not leave", ledger, "research")

        self.assertEqual(transport.call_count, 1)
        payload = transport.call_args.args[1]
        self.assertEqual(payload["max_tokens"], V.PERPLEXITY_MAX_TOKENS)
        self.assertEqual(len(ledger.calls), 1)

    def test_perplexity_reconciles_the_provider_reported_total_cost(self):
        provider_cost = 0.009321
        ledger = V.Ledger(ceiling=100.0, label="test")
        response = {
            "usage": {
                "prompt_tokens": 5, "completion_tokens": 7,
                "cost": {"total_cost": provider_cost},
            },
            "choices": [{"message": {"content": "lead"}}],
            "citations": [],
        }
        with mock.patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"}):
            with mock.patch.object(V, "_http", return_value=response):
                with mock.patch.object(V, "_PPX_MIN_GAP", 0):
                    V.perplexity_citations("cost reconciliation", ledger, "research")

        self.assertEqual(ledger.calls[0]["cost"], provider_cost)
        self.assertEqual(
            ledger.calls[0]["provider_reported_cost"], provider_cost)
        self.assertIn("derived_cost", ledger.calls[0])

    def test_perplexity_missing_provider_cost_consumes_the_hard_bound(self):
        token_cap = 500
        ledger = V.Ledger(ceiling=100.0, label="test")
        response = {
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            "choices": [{"message": {"content": "lead"}}],
            "citations": [],
        }
        with mock.patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"}):
            with mock.patch.object(V, "_http", return_value=response):
                with mock.patch.object(V, "_PPX_MIN_GAP", 0):
                    with self.assertRaisesRegex(
                            V.VendorError, "provider-reported total cost"):
                        V.perplexity_citations(
                            "missing cost", ledger, "research",
                            max_tokens=token_cap,
                        )

        self.assertEqual(ledger.calls[0]["out_tok"], token_cap)
        self.assertIn("UNMETERED-UPPER-BOUND", ledger.calls[0]["detail"])

    def test_perplexity_unmetered_success_consumes_the_hard_upper_bound(self):
        token_cap = 500
        ledger = V.Ledger(ceiling=100.0, label="test")
        transport = mock.Mock(return_value={
            "choices": [{"message": {"content": "unmetered lead"}}],
            "citations": ["https://example.test/source"],
        })

        with mock.patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"}):
            with mock.patch.object(V, "_http", transport):
                with mock.patch.object(V, "_PPX_MIN_GAP", 0):
                    with self.assertRaisesRegex(
                            V.VendorError, "token usage"):
                        V.perplexity_citations(
                            "unmetered", ledger, "research", max_tokens=token_cap,
                        )

        self.assertEqual(ledger.calls[0]["out_tok"], token_cap)
        self.assertIn("UNMETERED-UPPER-BOUND", ledger.calls[0]["detail"])
        self.assertEqual(ledger._reservations, {})

    def test_reasoning_transport_ambiguity_is_durable_and_not_reissued(self):
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "llm-ambiguous.json")
            ledger = V.Ledger(ceiling=500, label="test")
            ledger.attach(spend_path)
            llm = V.LLM(
                "anthropic", ledger, model="claude-test",
            ).enable_durable_outcomes()
            llm._call_anthropic = mock.Mock(
                side_effect=TimeoutError("response lost"))

            with self.assertRaisesRegex(V.VendorError, "outcome is ambiguous"):
                llm.json_call(
                    "system", "user", {"type": "object"}, "foresight",
                    max_tokens=100, detail="ambiguous unit",
                )

            self.assertEqual(len(ledger.calls), 1)
            self.assertGreater(ledger.calls[0]["cost"], 0)
            self.assertEqual(
                ledger.calls[0]["structured_result"]["outcome"],
                "transport_outcome_ambiguous",
            )

            resumed_ledger = V.Ledger(ceiling=500, label="resumed")
            resumed_ledger.attach(spend_path)
            resumed_ledger.load(spend_path)
            resumed = V.LLM(
                "anthropic", resumed_ledger, model="claude-test",
            ).enable_durable_outcomes()
            transport = mock.Mock(
                side_effect=AssertionError("ambiguous call was reissued"))
            resumed._call_anthropic = transport

            with self.assertRaisesRegex(V.VendorError, "outcome is ambiguous"):
                resumed.json_call(
                    "system", "user", {"type": "object"}, "foresight",
                    max_tokens=100, detail="ambiguous unit",
                )
            transport.assert_not_called()

    def test_malformed_usage_cannot_release_headroom_after_a_paid_response(self):
        with tempfile.TemporaryDirectory() as directory:
            spend_path = os.path.join(directory, "malformed-usage.json")
            ledger = V.Ledger(ceiling=500, label="test")
            ledger.attach(spend_path)
            llm = V.LLM("anthropic", ledger, model="claude-test")
            llm._call_anthropic = mock.Mock(
                return_value=({"value": "response"}, "not-a-token-count", 1))

            with self.assertRaises(TypeError):
                llm.json_call_once(
                    "system", "user", {"type": "object"}, "foresight",
                    max_tokens=100, detail="malformed usage",
                )

            self.assertEqual(ledger.summary()["unresolved_reservations"], 1)
            self.assertGreater(ledger.spent("foresight"), 0)

            resumed_ledger = V.Ledger(ceiling=500, label="resumed")
            resumed_ledger.attach(spend_path)
            resumed_ledger.load(spend_path)
            resumed = V.LLM("anthropic", resumed_ledger, model="claude-test")
            transport = mock.Mock(
                side_effect=AssertionError("unresolved request was reissued"))
            resumed._call_anthropic = transport
            with self.assertRaises(V.VendorRequestPending):
                resumed.json_call_once(
                    "system", "user", {"type": "object"}, "foresight",
                    max_tokens=100, detail="malformed usage",
                )
            transport.assert_not_called()

    def test_reasoning_success_without_authoritative_usage_charges_the_bound(self):
        schema = {"type": "object"}

        anthropic_response = SimpleNamespace(
            id="a", content=[SimpleNamespace(type="text", text="{}")],
            usage=SimpleNamespace(output_tokens=1),
            stop_reason="end_turn", stop_details=None,
        )
        anthropic = SimpleNamespace(
            Anthropic=lambda **_kwargs: SimpleNamespace(
                messages=_AnthropicMessages(anthropic_response)),
            transform_schema=lambda value: value,
        )

        openai_response = SimpleNamespace(
            id="o", status="completed", incomplete_details=None,
            output_text="{}", output=[], error=None,
            usage=SimpleNamespace(output_tokens=1), max_output_tokens=100,
        )
        openai = SimpleNamespace(
            OpenAI=lambda **_kwargs: SimpleNamespace(
                responses=_CreateEndpoint(openai_response)))

        gemini_response = SimpleNamespace(
            response_id="g", text="{}",
            usage_metadata=SimpleNamespace(
                candidates_token_count=1, thoughts_token_count=0),
            candidates=[SimpleNamespace(
                finish_reason=SimpleNamespace(name="STOP"))],
            prompt_feedback=None,
        )
        genai = types.ModuleType("google.genai")
        genai.Client = lambda **_kwargs: SimpleNamespace(
            models=_CreateEndpoint(gemini_response))
        genai_types = types.ModuleType("google.genai.types")
        genai_types.GenerateContentConfig = (
            lambda **kwargs: SimpleNamespace(**kwargs))
        genai_types.HttpRetryOptions = (
            lambda **kwargs: SimpleNamespace(**kwargs))
        genai_types.HttpOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        google = types.ModuleType("google")
        google.genai = genai
        genai.types = genai_types

        cases = (
            ("anthropic", "claude-test", {"anthropic": anthropic},
             {"ANTHROPIC_API_KEY": "test-key"}),
            ("openai", "gpt-test", {"openai": openai},
             {"OPENAI_API_KEY": "test-key"}),
            ("gemini", "gemini-test", {
                "google": google, "google.genai": genai,
                "google.genai.types": genai_types,
            }, {"GEMINI_API_KEY": "test-key"}),
        )
        for vendor, model, modules, environment in cases:
            with self.subTest(vendor=vendor):
                ledger = V.Ledger(ceiling=500, label=vendor)
                with mock.patch.dict(sys.modules, modules):
                    with mock.patch.dict(os.environ, environment):
                        llm = V.LLM(
                            vendor, ledger, model=model).enable_durable_outcomes()
                        with self.assertRaisesRegex(
                                V.VendorTransportAmbiguous,
                                "outcome is ambiguous"):
                            llm.json_call_once(
                                "system", "user", schema, "foresight",
                                max_tokens=100, detail="missing usage",
                            )
                self.assertGreater(ledger.calls[0]["cost"], 0)
                self.assertEqual(
                    ledger.calls[0]["structured_result"]["outcome"],
                    V.VendorTransportAmbiguous.code,
                )

    def test_reasoning_sdk_clients_explicitly_disable_hidden_retries(self):
        anthropic_kwargs = {}
        openai_kwargs = {}
        gemini_kwargs = {}

        anthropic_response = SimpleNamespace(
            id="a", content=[SimpleNamespace(type="text", text="{}")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn", stop_details=None,
        )
        anthropic_client = SimpleNamespace(
            messages=_AnthropicMessages(anthropic_response))

        def anthropic_factory(**kwargs):
            anthropic_kwargs.update(kwargs)
            return anthropic_client

        openai_response = SimpleNamespace(
            id="o", status="completed", incomplete_details=None,
            output_text="{}", output=[], error=None,
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            max_output_tokens=10,
        )
        openai_endpoint = _CreateEndpoint(openai_response)

        def openai_factory(**kwargs):
            openai_kwargs.update(kwargs)
            return SimpleNamespace(responses=openai_endpoint)

        gemini_response = SimpleNamespace(
            response_id="g", text="{}",
            usage_metadata=SimpleNamespace(
                prompt_token_count=1, candidates_token_count=1,
                thoughts_token_count=0),
            candidates=[SimpleNamespace(
                finish_reason=SimpleNamespace(name="STOP"))],
            prompt_feedback=None,
        )
        gemini_endpoint = _CreateEndpoint(gemini_response)

        def gemini_factory(**kwargs):
            gemini_kwargs.update(kwargs)
            return SimpleNamespace(models=gemini_endpoint)

        anthropic = SimpleNamespace(
            Anthropic=anthropic_factory, transform_schema=lambda value: value)
        openai = SimpleNamespace(OpenAI=openai_factory)
        genai = types.ModuleType("google.genai")
        genai.Client = gemini_factory
        genai_types = types.ModuleType("google.genai.types")
        genai_types.GenerateContentConfig = (
            lambda **kwargs: SimpleNamespace(**kwargs))
        genai_types.HttpRetryOptions = (
            lambda **kwargs: SimpleNamespace(**kwargs))
        genai_types.HttpOptions = lambda **kwargs: SimpleNamespace(**kwargs)
        google = types.ModuleType("google")
        google.genai = genai
        genai.types = genai_types

        with mock.patch.dict(sys.modules, {
                "anthropic": anthropic,
                "openai": openai,
                "google": google,
                "google.genai": genai,
                "google.genai.types": genai_types,
        }):
            with mock.patch.dict(os.environ, {
                    "ANTHROPIC_API_KEY": "test-key",
                    "OPENAI_API_KEY": "test-key",
                    "GEMINI_API_KEY": "test-key",
            }):
                V.LLM("anthropic", V.Ledger(), model="claude-test")._call_anthropic(
                    "system", "user", {"type": "object"}, 10)
                V.LLM("openai", V.Ledger(), model="gpt-test")._call_openai(
                    "system", "user", {"type": "object"}, 10)
                V.LLM("gemini", V.Ledger(), model="gemini-test")._call_gemini(
                    "system", "user", {"type": "object"}, 10)

        self.assertEqual(anthropic_kwargs["max_retries"], 0)
        self.assertEqual(openai_kwargs["max_retries"], 0)
        self.assertEqual(
            gemini_kwargs["http_options"].retry_options.attempts, 1)

    def test_current_model_tariffs_select_the_documented_context_tier(self):
        cases = (
            ("anthropic", "claude-sonnet-5", 1, (2.0, 10.0)),
            ("openai", "gpt-5.6-terra", 272000, (2.5, 12.0)),
            ("openai", "gpt-5.6-terra", 272001, (5.0, 18.0)),
            ("openai", "gpt-5.6-luna", 272000, (0.25, 1.2)),
            ("openai", "gpt-5.6-luna", 272001, (0.5, 1.8)),
            ("openai", "gpt-5.6-sol", 272000, (5.0, 20.0)),
            ("openai", "gpt-5.6-sol", 272001, (10.0, 30.0)),
            ("gemini", "gemini-3.1-pro-preview", 200000, (2.0, 12.0)),
            ("gemini", "gemini-3.1-pro-preview", 200001, (4.0, 18.0)),
            ("gemini", "gemini-2.5-pro", 200000, (1.25, 10.0)),
            ("gemini", "gemini-2.5-pro", 200001, (2.5, 15.0)),
        )

        for vendor, model, input_tokens, expected in cases:
            with self.subTest(vendor=vendor, model=model, input_tokens=input_tokens):
                price = V.Ledger._price(vendor, model, in_tok=input_tokens)
                self.assertEqual(
                    (price["in_per_mtok"], price["out_per_mtok"]), expected,
                )

        self.assertNotIn("gemini-pro-latest", V._MODEL_PREFS["gemini"])

    def test_legacy_json_call_claims_a_matching_durable_result_before_transport(self):
        response = {"value": "already paid"}
        first_ledger = V.Ledger(ceiling=500, label="first")
        first = V.LLM(
            "anthropic", first_ledger, model="claude-opus-5",
        ).enable_durable_outcomes()
        first._call_anthropic = mock.Mock(return_value=(response, 100, 20))
        self.assertEqual(first.json_call(
            "system", "user", {"type": "object"}, "foresight",
            max_tokens=100, detail="crash gap",
        ), response)

        resumed_ledger = V.Ledger(ceiling=500, label="resumed")
        resumed_ledger.restore(first_ledger.snapshot())
        resumed = V.LLM(
            "anthropic", resumed_ledger, model="claude-opus-5",
        ).enable_durable_outcomes()
        transport = mock.Mock(side_effect=AssertionError("transport must not run"))
        resumed._call_anthropic = transport

        self.assertEqual(resumed.json_call(
            "system", "user", {"type": "object"}, "foresight",
            max_tokens=100, detail="crash gap",
        ), response)
        transport.assert_not_called()
        self.assertEqual(len(resumed_ledger.calls), 1)

    def test_legacy_json_call_claims_truncation_then_larger_durable_result(self):
        response = {"value": "paid on bounded retry"}
        first_ledger = V.Ledger(ceiling=500, label="first")
        first = V.LLM(
            "anthropic", first_ledger, model="claude-opus-5",
        ).enable_durable_outcomes()
        first._call_anthropic = mock.Mock(side_effect=[
            V._ProviderOutputTruncated(
                stop_reason="max_tokens", request_id="first", max_tokens=100,
                input_tokens=80, output_tokens=100, thinking_tokens=20,
                partial_output='{"value":',
            ),
            (response, 90, 40),
        ])
        self.assertEqual(first.json_call(
            "system", "user", {"type": "object"}, "foresight",
            max_tokens=100, detail="bounded retry",
        ), response)
        self.assertEqual(len(first_ledger.calls), 2)

        resumed_ledger = V.Ledger(ceiling=500, label="resumed")
        resumed_ledger.restore(first_ledger.snapshot())
        resumed = V.LLM(
            "anthropic", resumed_ledger, model="claude-opus-5",
        ).enable_durable_outcomes()
        transport = mock.Mock(side_effect=AssertionError("transport must not run"))
        resumed._call_anthropic = transport

        self.assertEqual(resumed.json_call(
            "system", "user", {"type": "object"}, "foresight",
            max_tokens=100, detail="bounded retry",
        ), response)
        transport.assert_not_called()
        self.assertEqual(len(resumed_ledger.calls), 2)

    def test_legacy_json_call_replays_a_durable_rejection_without_transport(self):
        first_ledger = V.Ledger(ceiling=500, label="first")
        first = V.LLM(
            "anthropic", first_ledger, model="claude-opus-5",
        ).enable_durable_outcomes()
        first._call_anthropic = mock.Mock(side_effect=V._ProviderOutputRejected(
            stop_reason="refusal", request_id="first", max_tokens=100,
            input_tokens=80, output_tokens=0, thinking_tokens=0,
            partial_output="",
        ))
        with self.assertRaises(V.VendorOutputRejected):
            first.json_call(
                "system", "user", {"type": "object"}, "foresight",
                max_tokens=100, detail="rejected",
            )

        resumed_ledger = V.Ledger(ceiling=500, label="resumed")
        resumed_ledger.restore(first_ledger.snapshot())
        resumed = V.LLM(
            "anthropic", resumed_ledger, model="claude-opus-5",
        ).enable_durable_outcomes()
        transport = mock.Mock(side_effect=AssertionError("transport must not run"))
        resumed._call_anthropic = transport
        with self.assertRaises(V.VendorOutputRejected):
            resumed.json_call(
                "system", "user", {"type": "object"}, "foresight",
                max_tokens=100, detail="rejected",
            )
        transport.assert_not_called()
        self.assertEqual(len(resumed_ledger.calls), 1)


if __name__ == "__main__":
    unittest.main()
