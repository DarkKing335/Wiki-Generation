"""Tool registry — declared tools with JSON-schema metadata.

``docs/system-overview.md`` §"Analysis Tools" specifies a fixed toolset for
RepoAtlas.  Epic 1 implemented its six as ordinary methods rather than declared
tools; this registry provides the declaration layer, currently holding Epic 3's
four.  Epic 1's tools can register into it unchanged when the branches merge.

Scope constraint
----------------
This is a registry plus dispatcher, deliberately **not** an agent loop.
``docs/vision.md`` lists "Agent orchestration or scheduling" as out of scope and
mandates single-shot analysis, so traversal order stays deterministic.  The one
model-driven decision is *lazy source fetch* — whether a method body is needed —
which is precisely the handshake ``docs/designs/ast-parser-design.md`` §8
specifies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolError(RuntimeError):
    """Raised when a tool call is malformed or its handler fails."""


@dataclass
class ToolParameter:
    """One parameter of a tool, rendered into JSON Schema."""

    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Any = None

    def to_schema(self) -> Dict[str, Any]:
        schema: Dict[str, Any] = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = self.enum
        return schema


@dataclass
class ToolDefinition:
    """A declared tool: metadata plus the handler that executes it."""

    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable[..., Any]] = None

    def to_schema(self) -> Dict[str, Any]:
        """Render as an OpenAI/Ollama-compatible function-tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {p.name: p.to_schema() for p in self.parameters},
                    "required": [p.name for p in self.parameters if p.required],
                },
            },
        }

    def validate(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Check *arguments* against this tool's schema and apply defaults.

        Returns the validated argument dict.  Raises :class:`ToolError` on a
        missing required parameter, an unknown parameter, a type mismatch, or a
        value outside a declared enum.
        """
        by_name = {p.name: p for p in self.parameters}

        unknown = set(arguments) - set(by_name)
        if unknown:
            raise ToolError(
                f"Tool '{self.name}' received unknown parameter(s): {', '.join(sorted(unknown))}"
            )

        validated: Dict[str, Any] = {}
        for name, parameter in by_name.items():
            if name not in arguments:
                if parameter.required:
                    raise ToolError(f"Tool '{self.name}' requires parameter '{name}'")
                if parameter.default is not None:
                    validated[name] = parameter.default
                continue

            value = arguments[name]
            if not _matches_type(value, parameter.type):
                raise ToolError(
                    f"Tool '{self.name}' parameter '{name}' expects {parameter.type}, "
                    f"got {type(value).__name__}"
                )
            if parameter.enum and value not in parameter.enum:
                raise ToolError(
                    f"Tool '{self.name}' parameter '{name}' must be one of "
                    f"{', '.join(parameter.enum)}; got {value!r}"
                )
            validated[name] = value

        return validated


def _matches_type(value: Any, json_type: str) -> bool:
    """Whether *value* satisfies a JSON Schema primitive type.

    ``bool`` is checked before ``int`` because ``bool`` subclasses ``int`` in
    Python, and a boolean passed where a number is expected is a real mismatch.
    """
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "boolean":
        return isinstance(value, bool)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "object":
        return isinstance(value, dict)
    return True


class ToolRegistry:
    """Holds tool definitions and exposes them as schemas."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> ToolDefinition:
        if tool.name in self._tools:
            raise ToolError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        logger.debug("Registered tool '%s'", tool.name)
        return tool

    def get(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(sorted(self._tools)) or "(none)"
            raise ToolError(f"Unknown tool '{name}'. Registered tools: {available}")
        return tool

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    @property
    def names(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self) -> List[Dict[str, Any]]:
        """Every registered tool as a JSON-schema definition, for the model."""
        return [self._tools[name].to_schema() for name in self.names]
