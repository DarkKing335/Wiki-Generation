"""Bottom-up summarization tests (US-3.1 - US-3.5, ADR-010).

Epic 3's central invariant is that **each tier consumes only the summaries of
the tier below, never its source**.  That is what keeps the repository-level
prompt small no matter how large the repository is, and it is the claim ADR-010
rests on.  Nothing else in the suite asserts it directly, so it is the main
subject here.

Every test drives the summarizer with a recording ``LLMClient`` so the exact
prompts sent to the model can be inspected, rather than inferring behaviour from
token counts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pytest

from ai_analysis.chunker import Chunker
from ai_analysis.llm.base import LLMClient, LLMResponse, ToolCall
from ai_analysis.llm.embeddings import EmbeddingClient
from ai_analysis.llm.null import NullLLMClient
from ai_analysis.models import Tier
from ai_analysis.summarizer import MIN_LINES_FOR_LLM, Summarizer
from ai_analysis.tools.definitions import build_registry
from ai_analysis.tools.dispatcher import ToolDispatcher

#: Fragments that exist only inside method bodies in the sample repository.
BODY_FRAGMENTS = (
    "compareTo",
    "tokenize",
    "System.out.println",
    "ArrayList",
    "templateEngine.expand",
    "PdfWriter.fromHtml",
    "_repository.LoadAsync",
    "return NotFound()",
)

#: Marker returned by the recording client, so a parent prompt can be checked
#: for its children's summaries.
MOCK_SUMMARY = "MOCKSUMMARY"

_LEVEL = re.compile(r"TARGET CONTEXT \(Level (\d+): (\w+)\)")


class RecordingLLMClient(LLMClient):
    """Captures every prompt it is given and returns a marker summary."""

    name = "recording"
    enabled = True

    def __init__(self, tool_calls_on_first: Optional[List[ToolCall]] = None):
        self.prompts: List[str] = []
        self.systems: List[Optional[str]] = []
        self.tool_payloads: List[Optional[list]] = []
        self._pending_tool_calls = tool_calls_on_first or []

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        self.prompts.append(prompt)
        self.systems.append(system)
        self.tool_payloads.append(tools)

        calls, self._pending_tool_calls = self._pending_tool_calls, []
        return LLMResponse(
            text=f"{MOCK_SUMMARY} for prompt {len(self.prompts)}",
            prompt_token_count=len(prompt) // 4,
            tool_calls=calls,
        )

    def tier_of(self, prompt: str) -> Optional[str]:
        match = _LEVEL.search(prompt)
        return match.group(2) if match else None

    def prompts_at(self, tier_name: str) -> List[str]:
        return [p for p in self.prompts if self.tier_of(p) == tier_name]


@pytest.fixture
def recorder():
    return RecordingLLMClient()


@pytest.fixture
def summarizer(sample_index, sample_tree, recorder):
    return Summarizer(sample_index, sample_tree, recorder)


class TestBottomUpOrder:
    """Children must be summarized before the parents that consume them."""

    def test_traversal_runs_deepest_tier_first(self, summarizer):
        summarizer.run()
        tiers = [r.tier.value for r in summarizer.token_reports]

        assert tiers == sorted(tiers, reverse=True)

    def test_walk_starts_at_method_and_ends_at_repository(self, summarizer):
        summarizer.run()
        reports = summarizer.token_reports

        assert reports[0].tier is Tier.METHOD
        assert reports[-1].tier is Tier.REPOSITORY

    def test_every_node_is_summarized_exactly_once(self, summarizer, sample_tree):
        nodes = summarizer.run()
        expected = [n.node_id for n in sample_tree.bottom_up()]

        assert [n.node_id for n in nodes] == expected
        assert len(set(n.node_id for n in nodes)) == len(expected)

    def test_a_parent_sees_its_children_summaries(self, summarizer, recorder, sample_tree):
        """The aggregation contract, checked on the prompt text itself."""
        summarizer.run()

        for prompt in recorder.prompts_at("Component"):
            assert MOCK_SUMMARY in prompt, "component prompt lost its class summaries"

    def test_summaries_map_is_populated_as_the_walk_proceeds(self, summarizer, sample_tree):
        summarizer.run()

        for node in sample_tree.root.walk():
            assert node.node_id in summarizer.summaries
            assert summarizer.summaries[node.node_id]


class TestNoSourceLeaks:
    """The invariant: aggregating tiers never see code."""

    def test_no_prompt_contains_a_method_body(self, summarizer, recorder):
        summarizer.run()

        for prompt in recorder.prompts:
            for fragment in BODY_FRAGMENTS:
                assert fragment not in prompt, (
                    f"body fragment '{fragment}' reached the model in:\n{prompt[:400]}"
                )

    def test_repository_prompt_contains_no_code_at_all(self, summarizer, recorder):
        summarizer.run()
        repository_prompts = recorder.prompts_at("Repository")

        assert repository_prompts
        for prompt in repository_prompts:
            assert "Class:" not in prompt
            assert "Fields:" not in prompt
            assert "Methods:" not in prompt

    def test_aggregating_tiers_render_summaries_not_skeletons(self, summarizer, recorder):
        summarizer.run()

        for tier_name in ("Component", "Container", "Module", "Repository"):
            for prompt in recorder.prompts_at(tier_name):
                assert "CHILD SUMMARIES" in prompt
                assert "STRUCTURAL SKELETON" not in prompt

    def test_code_tiers_render_skeletons(self, summarizer, recorder):
        summarizer.run()

        for tier_name in ("Class", "Method"):
            for prompt in recorder.prompts_at(tier_name):
                assert "STRUCTURAL SKELETON" in prompt

    def test_repository_prompt_is_smaller_than_the_corpus(self, summarizer, recorder):
        """Tier 1 cost must not scale with repository size."""
        summarizer.run()
        repository_prompt = recorder.prompts_at("Repository")[0]

        assert len(repository_prompt) < min(
            len(p) for p in recorder.prompts_at("Class")
        ) * 6


class TestTrivialMethodSkipping:
    """A one-line accessor has no behaviour worth a model call."""

    def test_short_methods_are_described_structurally(self, summarizer, sample_index):
        nodes = summarizer.run()
        registry = sample_index.build_registry()

        for node in nodes:
            if node.tier is not Tier.METHOD:
                continue
            lines = registry[node.node_id].range.line_count
            if lines < MIN_LINES_FOR_LLM:
                assert node.generated_by == "structural"

    def test_substantial_methods_reach_the_model(self, summarizer, sample_index):
        nodes = summarizer.run()
        registry = sample_index.build_registry()

        charged = next(
            n for n in nodes
            if n.node_id == "com.acme.billing.payment.PaymentProcessor.charge"
        )
        assert registry[charged.node_id].range.line_count >= MIN_LINES_FOR_LLM
        assert charged.generated_by == "llm"

    def test_skipping_can_be_disabled(self, sample_index, sample_tree, recorder):
        summarizer = Summarizer(
            sample_index, sample_tree, recorder, skip_trivial_methods=False
        )
        nodes = summarizer.run()

        assert all(n.generated_by == "llm" for n in nodes)

    def test_aggregating_tiers_are_never_skipped(self, summarizer):
        nodes = summarizer.run()

        for node in nodes:
            if node.tier is not Tier.METHOD:
                assert node.generated_by == "llm"


class TestTokenAccounting:

    def test_ground_truth_is_recorded_from_the_response(self, summarizer):
        summarizer.run()
        measured = [r for r in summarizer.token_reports if r.actual_tokens is not None]

        assert measured, "no prompt_eval_count was captured"

    def test_elapsed_time_is_recorded_for_every_node(self, summarizer):
        summarizer.run()
        assert all(r.elapsed_seconds is not None for r in summarizer.token_reports)

    def test_elapsed_time_is_excluded_from_serialization(self, summarizer):
        """Timings vary run to run and would break the reproducibility NFR."""
        summarizer.run()
        dumped = summarizer.token_reports[0].model_dump(mode="json")

        assert "elapsed_seconds" not in dumped


class TestGrounding:
    """Summaries are checked against the symbol registry (ast-parser-design.md:178)."""

    def test_referenced_symbols_resolve_to_real_symbols(self, summarizer, sample_index):
        nodes = summarizer.run()
        registry = sample_index.build_registry()

        for node in nodes:
            for reference in node.referenced_symbols:
                assert reference in registry

    def test_invented_identifiers_are_not_grounded(self, summarizer):
        summarizer.run()
        assert summarizer._ground("TotallyMadeUpClassName does things") == []

    def test_real_identifiers_are_grounded(self, summarizer):
        summarizer.run()
        grounded = summarizer._ground("PaymentProcessor charges cards")

        assert "com.acme.billing.payment.PaymentProcessor" in grounded


class TestLazySourceLoading:
    """The model may request a body; it may not drive the traversal."""

    @pytest.fixture
    def tool_summarizer(self, sample_index, sample_tree):
        chunker = Chunker(sample_index, sample_tree)
        dispatcher = ToolDispatcher(
            build_registry(chunker, embeddings=EmbeddingClient.offline())
        )
        recorder = RecordingLLMClient(tool_calls_on_first=[
            ToolCall(
                name="read_source_range",
                arguments={
                    "file_path": (
                        "billing/payment-service/src/main/java/com/acme/billing/"
                        "payment/PaymentProcessor.java"
                    ),
                    "start_line": 25,
                    "end_line": 34,
                },
            )
        ])
        summarizer = Summarizer(
            sample_index, sample_tree, recorder,
            chunker=chunker, dispatcher=dispatcher,
        )
        return summarizer, recorder

    def test_only_the_lazy_load_tool_is_offered(self, tool_summarizer):
        summarizer, recorder = tool_summarizer
        summarizer.run()

        for payload in recorder.tool_payloads:
            if not payload:
                continue
            names = [t["function"]["name"] for t in payload]
            assert names == ["read_source_range"]

    def test_tools_are_offered_only_at_code_tiers(self, tool_summarizer):
        summarizer, recorder = tool_summarizer
        summarizer.run()

        for prompt, payload in zip(recorder.prompts, recorder.tool_payloads):
            if payload:
                assert recorder.tier_of(prompt) in ("Class", "Method", None)

    def test_a_requested_body_comes_back_as_a_marked_excerpt(self, tool_summarizer):
        summarizer, recorder = tool_summarizer
        summarizer.run()

        excerpts = [p for p in recorder.prompts if "SOURCE EXCERPT" in p]
        assert excerpts, "the tool result never reached a follow-up prompt"
        assert "compareTo" in excerpts[0], "the excerpt did not carry the real body"

    def test_only_one_followup_round_occurs(self, tool_summarizer):
        """Traversal stays deterministic — no agent loop (vision.md:53)."""
        summarizer, recorder = tool_summarizer
        summarizer.run()

        assert len([p for p in recorder.prompts if "SOURCE EXCERPT" in p]) == 1


class TestFallbacks:

    def test_an_empty_response_still_yields_a_summary(self, sample_index, sample_tree):
        class SilentClient(LLMClient):
            name = "silent"
            enabled = True

            def generate(self, prompt, *, system=None, tools=None, max_tokens=None):
                return LLMResponse(text="")

        nodes = Summarizer(sample_index, sample_tree, SilentClient()).run()
        assert all(n.summary for n in nodes)

    def test_structural_client_completes_the_whole_walk(self, sample_index, sample_tree):
        nodes = Summarizer(sample_index, sample_tree, NullLLMClient()).run()

        assert len(nodes) == len(sample_tree.bottom_up())
        assert all(n.generated_by == "structural" for n in nodes)
