"""Ollama client wire-format tests.

The client's sampling options are covered from the reproducibility angle in
``test_reproducibility.py``.  What is asserted here is the rest of the request
body — specifically ``keep_alive``, which is invisible in the output but is
worth 14% of a whole analysis pass.

Ollama evicts an idle model after five minutes by default, so a pause between
runs costs a cold load (measured at 6.8s for ``qwen2.5-coder:1.5b``) that the
next run pays before it generates a single token.  Nothing in the produced wiki
would reveal the field going missing, hence a test.

Every request is served by an ``httpx.MockTransport``, so these run without an
Ollama server; the live path is exercised separately in ``test_ollama_live.py``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest

from ai_analysis.llm.ollama import (
    DEFAULT_KEEP_ALIVE,
    DEFAULT_MODEL,
    OllamaClient,
    OllamaError,
)


class CapturingTransport(httpx.MockTransport):
    """Records every request body and replies with a minimal chat response."""

    def __init__(self, content: str = "a summary", **extra: Any):
        self.payloads: List[Dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.payloads.append(json.loads(request.content))
            body = {"message": {"content": content}, "model": DEFAULT_MODEL}
            body.update(extra)
            return httpx.Response(200, json=body)

        super().__init__(handler)

    @property
    def last(self) -> Dict[str, Any]:
        assert self.payloads, "no request was sent"
        return self.payloads[-1]


@pytest.fixture
def transport() -> CapturingTransport:
    return CapturingTransport()


@pytest.fixture
def client(transport):
    return OllamaClient(client=httpx.Client(transport=transport))


class TestKeepAlive:
    """Holding the weights between runs is the cheapest speed-up available."""

    def test_every_request_carries_a_keep_alive(self, client, transport):
        client.generate("summarize this")

        assert transport.last["keep_alive"] == DEFAULT_KEEP_ALIVE

    def test_the_default_outlives_ollamas_own_five_minute_idle_eviction(self):
        """A default at or under 5m would leave the cold load exactly where it was."""
        unit = DEFAULT_KEEP_ALIVE[-1]
        assert unit in "smh", f"unrecognised keep_alive unit in {DEFAULT_KEEP_ALIVE!r}"

        seconds = int(DEFAULT_KEEP_ALIVE[:-1]) * {"s": 1, "m": 60, "h": 3600}[unit]
        assert seconds > 5 * 60

    def test_it_is_configurable_for_machines_that_need_the_vram_back(self, transport):
        client = OllamaClient(
            keep_alive="0", client=httpx.Client(transport=transport)
        )
        client.generate("summarize this")

        assert transport.last["keep_alive"] == "0"

    def test_it_survives_a_tool_carrying_request(self, client, transport):
        """The tool branch rebuilds the payload; keep_alive must not fall out."""
        tools = [{"type": "function", "function": {"name": "read_source_range"}}]
        client.generate("summarize this", tools=tools)

        assert transport.last["keep_alive"] == DEFAULT_KEEP_ALIVE
        assert transport.last["tools"] == tools


class TestRequestShape:

    def test_a_system_prompt_precedes_the_user_prompt(self, client, transport):
        client.generate("the user part", system="the system part")

        assert [m["role"] for m in transport.last["messages"]] == ["system", "user"]

    def test_streaming_is_off(self, client, transport):
        """Responses are parsed as a single JSON object, not an event stream."""
        client.generate("summarize this")

        assert transport.last["stream"] is False

    def test_a_per_call_token_cap_reaches_the_wire(self, client, transport):
        client.generate("summarize this", max_tokens=64)

        assert transport.last["options"]["num_predict"] == 64


class TestResponseParsing:

    def test_ground_truth_token_counts_are_surfaced(self):
        transport = CapturingTransport(prompt_eval_count=812, eval_count=97)
        client = OllamaClient(client=httpx.Client(transport=transport))

        response = client.generate("summarize this")

        assert response.prompt_token_count == 812
        assert response.completion_token_count == 97

    def test_a_missing_model_names_the_pull_command(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "model not found"})

        client = OllamaClient(
            model="ghost:1b", client=httpx.Client(transport=httpx.MockTransport(handler))
        )

        with pytest.raises(OllamaError, match="ollama pull ghost:1b"):
            client.generate("summarize this")

    def test_an_unreachable_server_is_reported_as_such(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = OllamaClient(
            client=httpx.Client(transport=httpx.MockTransport(handler))
        )

        with pytest.raises(OllamaError, match="Is the server running"):
            client.generate("summarize this")
