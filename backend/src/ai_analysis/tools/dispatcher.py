"""Tool dispatch — validates and executes model-requested tool calls.

Every call is validated against the tool's declared JSON schema before its
handler runs, and the number of calls per summary is capped.  Both matter because
the model, not the pipeline, chooses when to invoke a tool: an unbounded or
unvalidated tool surface would let a confused model spend the whole token budget
fetching source it does not need, defeating the point of skeleton prompting.

Handler exceptions are converted into error *results* rather than propagating.
A failed tool call must degrade the summary, never abort the run — consistent
with US-3.2's requirement that missing AI capability does not interrupt execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ai_analysis.llm.base import ToolCall
from ai_analysis.tools.registry import ToolError, ToolRegistry

logger = logging.getLogger(__name__)

#: Maximum tool calls permitted while producing a single summary.
DEFAULT_CALL_BUDGET = 3


@dataclass
class ToolResult:
    """Outcome of one dispatched tool call."""

    name: str
    arguments: Dict[str, Any]
    content: str
    ok: bool = True
    error: Optional[str] = None

    def as_context(self) -> str:
        """Render for inclusion in a follow-up prompt."""
        if not self.ok:
            return f"[{self.name} failed: {self.error}]"
        return self.content


class ToolDispatcher:
    """Executes validated tool calls against a registry, under a call budget."""

    def __init__(self, registry: ToolRegistry, *, call_budget: int = DEFAULT_CALL_BUDGET):
        self.registry = registry
        self.call_budget = call_budget
        self._calls_made = 0

    @property
    def calls_made(self) -> int:
        return self._calls_made

    @property
    def budget_remaining(self) -> int:
        return max(0, self.call_budget - self._calls_made)

    def reset(self) -> None:
        """Restore the budget. Called between summaries."""
        self._calls_made = 0

    def dispatch(self, call: ToolCall) -> ToolResult:
        """Validate and execute one tool call. Never raises."""
        if self.budget_remaining <= 0:
            logger.warning("Tool call budget exhausted; refusing '%s'", call.name)
            return ToolResult(
                name=call.name,
                arguments=call.arguments,
                content="",
                ok=False,
                error=f"Tool call budget of {self.call_budget} exhausted",
            )

        self._calls_made += 1

        try:
            tool = self.registry.get(call.name)
            arguments = tool.validate(call.arguments)
        except ToolError as exc:
            logger.warning("Rejected tool call '%s': %s", call.name, exc)
            return ToolResult(
                name=call.name, arguments=call.arguments, content="", ok=False, error=str(exc)
            )

        if tool.handler is None:
            return ToolResult(
                name=call.name,
                arguments=arguments,
                content="",
                ok=False,
                error=f"Tool '{call.name}' is declared but has no handler",
            )

        try:
            content = tool.handler(**arguments)
        except Exception as exc:  # noqa: BLE001 - a tool failure must not abort the run
            logger.warning("Tool '%s' raised: %s", call.name, exc)
            return ToolResult(
                name=call.name, arguments=arguments, content="", ok=False, error=str(exc)
            )

        logger.debug("Tool '%s' executed with %s", call.name, arguments)
        return ToolResult(
            name=call.name,
            arguments=arguments,
            content=content if isinstance(content, str) else str(content),
        )

    def dispatch_all(self, calls: List[ToolCall]) -> List[ToolResult]:
        """Dispatch several calls in order, stopping when the budget runs out."""
        return [self.dispatch(call) for call in calls]
