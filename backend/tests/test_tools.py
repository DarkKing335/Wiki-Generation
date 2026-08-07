"""Tool registry and dispatcher tests.

Implements the lazy-loading handshake in ``docs/designs/ast-parser-design.md``
§8, where the model *requests* a method body rather than receiving it
unconditionally.  Because the model chooses when to call, two properties carry
the safety of the design: every call is schema-validated before its handler
runs, and the number of calls per summary is bounded.  A confused model must not
be able to spend the whole token budget fetching source it does not need.
"""

from __future__ import annotations

import pytest

from ai_analysis.chunker import Chunker
from ai_analysis.llm.base import ToolCall
from ai_analysis.llm.embeddings import EmbeddingClient
from ai_analysis.models import Tier
from ai_analysis.tools.definitions import build_registry
from ai_analysis.tools.dispatcher import DEFAULT_CALL_BUDGET, ToolDispatcher
from ai_analysis.tools.registry import (
    ToolDefinition,
    ToolError,
    ToolParameter,
    ToolRegistry,
)

PROCESSOR_PATH = (
    "billing/payment-service/src/main/java/com/acme/billing/payment/PaymentProcessor.java"
)


@pytest.fixture
def registry(sample_index, sample_tree):
    chunker = Chunker(sample_index, sample_tree)
    return build_registry(chunker, embeddings=EmbeddingClient.offline())


@pytest.fixture
def dispatcher(registry):
    return ToolDispatcher(registry)


class TestToolSchemas:
    """The declaration layer the model is handed."""

    def test_all_four_epic3_tools_are_registered(self, registry):
        assert registry.names == [
            "get_skeleton",
            "read_source_range",
            "search_summaries",
            "summarize",
        ]

    def test_schemas_are_well_formed_function_definitions(self, registry):
        for schema in registry.schemas():
            assert schema["type"] == "function"
            function = schema["function"]

            assert function["name"]
            assert function["description"]
            assert function["parameters"]["type"] == "object"
            assert isinstance(function["parameters"]["properties"], dict)
            assert isinstance(function["parameters"]["required"], list)

    def test_required_parameters_are_a_subset_of_declared_ones(self, registry):
        for schema in registry.schemas():
            parameters = schema["function"]["parameters"]
            assert set(parameters["required"]) <= set(parameters["properties"])

    def test_optional_parameters_are_not_marked_required(self, registry):
        search = registry.get("search_summaries").to_schema()["function"]["parameters"]

        assert "query" in search["required"]
        assert "tier" not in search["required"]
        assert "limit" not in search["required"]

    def test_enums_are_published_to_the_model(self, registry):
        search = registry.get("search_summaries").to_schema()
        tier = search["function"]["parameters"]["properties"]["tier"]

        assert set(tier["enum"]) == {t.name.lower() for t in Tier}


class TestRegistry:

    def test_duplicate_registration_is_rejected(self):
        registry = ToolRegistry()
        tool = ToolDefinition(name="x", description="d")
        registry.register(tool)

        with pytest.raises(ToolError, match="already registered"):
            registry.register(ToolDefinition(name="x", description="d"))

    def test_unknown_tool_lookup_lists_what_is_available(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="alpha", description="d"))

        with pytest.raises(ToolError, match="alpha"):
            registry.get("beta")

    def test_membership_and_length(self, registry):
        assert "read_source_range" in registry
        assert "nonexistent" not in registry
        assert len(registry) == 4


class TestValidation:
    """A malformed call must be rejected before any handler runs."""

    @pytest.fixture
    def tool(self):
        return ToolDefinition(
            name="sample",
            description="d",
            parameters=[
                ToolParameter(name="text", type="string", description="d"),
                ToolParameter(name="count", type="integer", description="d"),
                ToolParameter(
                    name="mode", type="string", description="d",
                    required=False, enum=["fast", "slow"], default="fast",
                ),
            ],
        )

    def test_valid_arguments_pass_through(self, tool):
        assert tool.validate({"text": "a", "count": 1}) == {
            "text": "a", "count": 1, "mode": "fast"
        }

    def test_missing_required_parameter_is_rejected(self, tool):
        with pytest.raises(ToolError, match="requires parameter 'count'"):
            tool.validate({"text": "a"})

    def test_unknown_parameter_is_rejected(self, tool):
        with pytest.raises(ToolError, match="unknown parameter"):
            tool.validate({"text": "a", "count": 1, "extra": True})

    def test_type_mismatch_is_rejected(self, tool):
        with pytest.raises(ToolError, match="expects integer"):
            tool.validate({"text": "a", "count": "not a number"})

    def test_booleans_are_not_accepted_as_integers(self, tool):
        """``bool`` subclasses ``int`` in Python; the schema must not be fooled."""
        with pytest.raises(ToolError, match="expects integer"):
            tool.validate({"text": "a", "count": True})

    def test_value_outside_the_enum_is_rejected(self, tool):
        with pytest.raises(ToolError, match="must be one of"):
            tool.validate({"text": "a", "count": 1, "mode": "sideways"})

    def test_optional_default_is_applied(self, tool):
        assert tool.validate({"text": "a", "count": 1})["mode"] == "fast"


class TestDispatcher:

    def test_a_valid_call_executes_its_handler(self, dispatcher):
        result = dispatcher.dispatch(ToolCall(
            name="read_source_range",
            arguments={"file_path": PROCESSOR_PATH, "start_line": 1, "end_line": 1},
        ))

        assert result.ok
        assert result.content == "package com.acme.billing.payment;"

    def test_read_source_range_returns_exactly_the_requested_lines(
        self, dispatcher, sample_repo_dir
    ):
        result = dispatcher.dispatch(ToolCall(
            name="read_source_range",
            arguments={"file_path": PROCESSOR_PATH, "start_line": 25, "end_line": 34},
        ))
        lines = (sample_repo_dir / PROCESSOR_PATH).read_text(encoding="utf-8").splitlines()

        assert result.content == "\n".join(lines[24:34])

    def test_a_schema_violation_becomes_a_failed_result_not_an_exception(self, dispatcher):
        result = dispatcher.dispatch(ToolCall(
            name="read_source_range",
            arguments={"file_path": PROCESSOR_PATH, "start_line": "one", "end_line": 5},
        ))

        assert result.ok is False
        assert "expects integer" in result.error

    def test_an_unknown_tool_becomes_a_failed_result(self, dispatcher):
        result = dispatcher.dispatch(ToolCall(name="delete_everything", arguments={}))

        assert result.ok is False
        assert "Unknown tool" in result.error

    def test_a_raising_handler_does_not_abort_the_run(self, dispatcher):
        """US-3.2: a tool failure degrades the summary, never interrupts."""
        result = dispatcher.dispatch(ToolCall(
            name="read_source_range",
            arguments={"file_path": PROCESSOR_PATH, "start_line": 50, "end_line": 10},
        ))

        assert result.ok is False
        assert result.error

    def test_a_declared_tool_without_a_handler_reports_cleanly(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="declared", description="d"))

        result = ToolDispatcher(registry).dispatch(ToolCall(name="declared"))

        assert result.ok is False
        assert "no handler" in result.error


class TestCallBudget:
    """An unbounded tool surface would defeat skeleton prompting entirely."""

    def test_calls_are_capped(self, registry):
        dispatcher = ToolDispatcher(registry, call_budget=2)
        call = ToolCall(
            name="read_source_range",
            arguments={"file_path": PROCESSOR_PATH, "start_line": 1, "end_line": 2},
        )

        assert dispatcher.dispatch(call).ok
        assert dispatcher.dispatch(call).ok

        exhausted = dispatcher.dispatch(call)
        assert exhausted.ok is False
        assert "budget" in exhausted.error

    def test_rejected_calls_still_consume_budget(self, registry):
        """Otherwise a malformed-call loop would be free and unbounded."""
        dispatcher = ToolDispatcher(registry, call_budget=1)
        dispatcher.dispatch(ToolCall(name="nope", arguments={}))

        assert dispatcher.budget_remaining == 0

    def test_reset_restores_the_budget_between_summaries(self, registry):
        dispatcher = ToolDispatcher(registry, call_budget=1)
        dispatcher.dispatch(ToolCall(name="nope", arguments={}))
        dispatcher.reset()

        assert dispatcher.budget_remaining == 1
        assert dispatcher.calls_made == 0

    def test_dispatch_all_stops_once_the_budget_runs_out(self, registry):
        dispatcher = ToolDispatcher(registry, call_budget=1)
        call = ToolCall(
            name="read_source_range",
            arguments={"file_path": PROCESSOR_PATH, "start_line": 1, "end_line": 1},
        )
        results = dispatcher.dispatch_all([call, call, call])

        assert [r.ok for r in results] == [True, False, False]

    def test_default_budget_is_modest(self):
        assert DEFAULT_CALL_BUDGET <= 5


class TestToolHandlers:

    def test_get_skeleton_returns_structure_without_bodies(self, dispatcher):
        result = dispatcher.dispatch(ToolCall(
            name="get_skeleton",
            arguments={"fqn": "com.acme.billing.payment.PaymentProcessor"},
        ))

        assert result.ok
        assert "@Service" in result.content
        assert "compareTo" not in result.content

    def test_get_skeleton_reports_an_unknown_symbol_plainly(self, dispatcher):
        result = dispatcher.dispatch(ToolCall(
            name="get_skeleton", arguments={"fqn": "com.acme.NoSuchThing"},
        ))

        assert result.ok
        assert "No symbol named" in result.content

    def test_search_summaries_reports_an_empty_corpus(self, dispatcher):
        result = dispatcher.dispatch(ToolCall(
            name="search_summaries", arguments={"query": "payments"},
        ))

        assert result.ok
        assert "No summaries" in result.content

    def test_search_summaries_ranks_a_populated_corpus(self, sample_index, sample_tree):
        chunker = Chunker(sample_index, sample_tree)
        summaries = {
            "a": "Charges customer cards through the payment gateway.",
            "b": "Renders invoice documents into PDF files.",
        }
        registry = build_registry(
            chunker, embeddings=EmbeddingClient.offline(), summaries=summaries
        )
        result = ToolDispatcher(registry).dispatch(ToolCall(
            name="search_summaries", arguments={"query": "invoice pdf rendering"},
        ))

        assert result.ok
        assert result.content.splitlines()[0].startswith("- b")

    def test_summarize_declines_when_no_callback_is_bound(self, dispatcher):
        """Traversal is deterministic; the model does not get to drive it."""
        result = dispatcher.dispatch(ToolCall(
            name="summarize",
            arguments={"tier": "class", "target_fqn": "com.acme.X"},
        ))

        assert result.ok
        assert "not available" in result.content
