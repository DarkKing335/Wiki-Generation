"""LLM client contract (ADR-006 — optional local or remote LLM).

A single interface covers all three execution modes described in
``docs/system-overview.md``:

* **Local SLM** (default) — :class:`~ai_analysis.llm.ollama.OllamaClient`
* **Remote LLM** — a future implementation of this same ABC
* **No LLM** — :class:`~ai_analysis.llm.null.NullLLMClient`, which produces
  structural descriptions so the pipeline still completes (US-3.2, FR-9)

Because all three satisfy this contract, the summarizer never branches on which
mode is active — the analysis workflow is identical regardless of provider,
which is exactly what ADR-006 requires.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """A tool invocation requested by the model."""

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """A single model response."""

    text: str

    prompt_token_count: Optional[int] = None
    """Ground-truth prompt tokens reported by the backend, when available.

    Ollama returns this as ``prompt_eval_count``.  It is the real number against
    which the estimator in :mod:`ai_analysis.tokens` is validated.
    """

    completion_token_count: Optional[int] = None
    elapsed_seconds: Optional[float] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: Optional[str] = None

    @property
    def requested_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMClient(ABC):
    """Contract every summarization backend must satisfy."""

    #: Short identifier recorded on generated summaries.
    name: str = "abstract"

    #: Whether this client actually invokes a model.  ``False`` for the null
    #: client, which lets callers report ``llm_enabled`` honestly.
    enabled: bool = True

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate a completion for *prompt*.

        Parameters
        ----------
        tools:
            JSON-schema tool definitions the model may request.  Implementations
            that do not support tool calling ignore this and return no
            ``tool_calls``; callers must handle an empty list either way.
        max_tokens:
            Cap on generated tokens.  Callers set this per tier, since
            generation length is the dominant cost in per-node latency.
        """
        ...

    def health_check(self) -> bool:
        """Whether this client is usable right now.  Never raises."""
        return True

    def close(self) -> None:
        """Release any held resources."""
        return None

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
