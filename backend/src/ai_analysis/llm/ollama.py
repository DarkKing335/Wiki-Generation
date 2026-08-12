"""Ollama client — the default local SLM backend (US-3.1, FR-3, ADR-006).

Determinism
-----------
``docs/product.md`` lists Reproducibility as a non-functional requirement:
*"Identical repository states produce identical AST symbol graphs and static wiki
pages."*  LLM sampling is stochastic, so that requirement is violated by
construction unless sampling is switched off.  Every request therefore pins
``temperature=0``, ``top_p=1``, ``top_k=1`` and a fixed ``seed``.

Token ground truth
------------------
Ollama returns ``prompt_eval_count`` on each response — the real prompt token
count from the model's own tokenizer.  It is surfaced on
:class:`~ai_analysis.llm.base.LLMResponse` so US-3.5's budget claim can be
verified against measurement rather than estimation.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from ai_analysis.llm.base import LLMClient, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:3b"

#: Fixed seed for reproducible generation.
DEFAULT_SEED = 42

#: Generous enough for a cold model load on first call.
DEFAULT_TIMEOUT = 180.0

#: Context window requested from the backend.
#:
#: Sized to what Epic 3 can actually produce rather than to the model's maximum.
#: FR-15 caps every prompt at 2,000 tokens and the largest per-tier generation
#: cap is ~380 (``prompts.completion_limit`` at Tier.REPOSITORY), so ~2,400 is
#: the true ceiling for a single exchange; 4,096 leaves comfortable headroom.
#:
#: This is not a micro-optimisation.  KV cache scales linearly with ``num_ctx``,
#: and it is allocated up front — requesting 8,192 reserved several hundred MB of
#: VRAM that no prompt could ever occupy, which on a 4 GB card is the difference
#: between a 7B model loading and failing with ``cudaMalloc failed``.
DEFAULT_NUM_CTX = 4096


class OllamaError(RuntimeError):
    """Raised when the Ollama server cannot fulfil a request."""


class OllamaClient(LLMClient):
    """Talks to a locally hosted Ollama server."""

    name = "ollama"
    enabled = True

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        seed: int = DEFAULT_SEED,
        timeout: float = DEFAULT_TIMEOUT,
        num_ctx: int = DEFAULT_NUM_CTX,
        max_tokens: int = 400,
        client: Optional[httpx.Client] = None,
    ):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.seed = seed
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    # ------------------------------------------------------------------

    def build_options(self, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Sampling options — deterministic by design, see module docstring."""
        return {
            "temperature": 0,
            "top_p": 1,
            "top_k": 1,
            "seed": self.seed,
            "num_ctx": self.num_ctx,
            "num_predict": max_tokens or self.max_tokens,
        }

    @property
    def options(self) -> Dict[str, Any]:
        return self.build_options()

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": self.build_options(max_tokens),
        }
        if tools:
            payload["tools"] = tools

        started = time.perf_counter()
        try:
            response = self._client.post(f"{self.endpoint}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama returned {exc.response.status_code} for model '{self.model}'. "
                f"Is it pulled? Try: ollama pull {self.model}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.endpoint}: {exc}. Is the server running?"
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama returned malformed JSON: {exc}") from exc

        elapsed = time.perf_counter() - started
        message = data.get("message") or {}

        return LLMResponse(
            text=(message.get("content") or "").strip(),
            prompt_token_count=data.get("prompt_eval_count"),
            completion_token_count=data.get("eval_count"),
            elapsed_seconds=elapsed,
            tool_calls=self._parse_tool_calls(message),
            model=data.get("model", self.model),
        )

    @staticmethod
    def _parse_tool_calls(message: Dict[str, Any]) -> List[ToolCall]:
        """Extract tool calls from a response message.

        Arguments arrive as an object from Ollama, but some models emit a JSON
        string instead; both are accepted.
        """
        calls: List[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            name = function.get("name")
            if not name:
                continue

            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    logger.warning("Could not parse tool arguments for '%s': %r", name, arguments)
                    arguments = {}

            calls.append(ToolCall(name=name, arguments=arguments))
        return calls

    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Whether the server is reachable and the model is present."""
        try:
            response = self._client.get(f"{self.endpoint}/api/tags", timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Ollama health check failed at %s: %s", self.endpoint, exc)
            return False

        available = {m.get("name", "") for m in response.json().get("models", [])}
        if self.model in available:
            return True

        # Ollama reports "name:tag"; accept a bare name matching a single tag.
        if any(name.split(":")[0] == self.model.split(":")[0] for name in available):
            return True

        logger.warning(
            "Model '%s' not found on the Ollama server. Available: %s",
            self.model,
            ", ".join(sorted(available)) or "(none)",
        )
        return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
