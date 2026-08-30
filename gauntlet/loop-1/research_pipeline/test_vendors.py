#!/usr/bin/env python3

import os
import sys
import tempfile
import threading
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


if __name__ == "__main__":
    unittest.main()
