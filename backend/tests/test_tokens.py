"""Token budget tests — US-3.5's Definition of Done (FR-15).

*"Verified token consumption stays under 2,000 tokens per prompt."*

The load-bearing assertions here are:

1. Every prompt built across the whole fixture corpus fits the budget.
2. The estimator never *under*-reports.  An estimate that reads low would let a
   prompt through that the model then truncates mid-skeleton — precisely the
   failure ADR-010 exists to prevent.

Assertion 2 is checked structurally offline (margin applied, monotonic in input
length) and against real ``prompt_eval_count`` ground truth in
``test_ollama_live.py``, which needs a running model.
"""

from __future__ import annotations

import pytest

from ai_analysis.chunker import Chunker
from ai_analysis.llm.null import NullLLMClient
from ai_analysis.models import Tier
from ai_analysis.prompts import build_prompt, completion_limit
from ai_analysis.summarizer import Summarizer
from ai_analysis.tokens import (
    DEFAULT_BUDGET,
    SAFETY_MARGIN,
    TARGET_MAX,
    count_tokens,
    enforce_budget,
    truncate_to_tokens,
)


class TestCountTokens:

    def test_empty_text_costs_nothing(self):
        assert count_tokens("") == 0

    def test_margin_inflates_the_raw_count(self):
        text = "public class PaymentProcessor implements PaymentGateway { }" * 20
        raw = count_tokens(text, apply_margin=False)
        margined = count_tokens(text)

        assert margined > raw
        assert margined >= int(raw * SAFETY_MARGIN)

    def test_estimate_grows_with_input(self):
        short = "Class: A"
        long = "Class: A\n" * 100
        assert count_tokens(long) > count_tokens(short)

    def test_never_under_reports_against_the_raw_tokenizer(self):
        """The margin exists so a differently-tuned tokenizer cannot overrun."""
        samples = [
            "Class: PaymentProcessor  [@Service]  implements PaymentGateway",
            "* charge(TransactionDto dto) -> PaymentResult throws PaymentException",
            "- payment-service: Charges customer cards through Stripe.",
            "public async Task<IActionResult> GetById(Guid id)",
        ]
        for text in samples:
            assert count_tokens(text) >= count_tokens(text, apply_margin=False)


class TestEnforceBudget:

    def test_full_detail_is_kept_when_it_fits(self):
        result = enforce_budget(lambda **_: "short text", budget=DEFAULT_BUDGET)

        assert result.within_budget
        assert result.was_degraded is False
        assert result.steps_applied == ["full"]

    def test_degrades_in_order_until_it_fits(self):
        """Each option set must be tried in increasing order of information loss."""
        def render(include_private=True, include_docstrings=True, doc_chars=160):
            if include_private:
                return "x " * 5000
            if include_docstrings and doc_chars == 160:
                return "x " * 3000
            return "x " * 10

        result = enforce_budget(render, budget=DEFAULT_BUDGET)

        assert result.within_budget
        assert result.was_degraded is True
        assert result.steps_applied[0] == "full"
        assert result.steps_applied[-1] == "short-docs"

    def test_flags_a_prompt_that_cannot_be_shrunk(self):
        """An unshrinkable prompt is reported, never silently truncated."""
        result = enforce_budget(lambda **_: "x " * 20000, budget=DEFAULT_BUDGET)

        assert result.within_budget is False
        assert result.was_degraded is True

    def test_renderers_rejecting_an_option_set_are_skipped(self):
        def render(**options):
            if options:
                raise TypeError("unsupported")
            return "fits"

        result = enforce_budget(render, budget=DEFAULT_BUDGET)
        assert result.text == "fits"

    def test_target_band_is_reported(self):
        result = enforce_budget(lambda **_: "word " * 900, budget=DEFAULT_BUDGET)
        assert result.in_target_band == (900 <= TARGET_MAX)


class TestTruncateToTokens:

    def test_short_text_passes_through_untouched(self):
        assert truncate_to_tokens("one line", 100) == "one line"

    def test_truncation_lands_on_a_line_boundary(self):
        text = "\n".join(f"line number {i}" for i in range(200))
        result = truncate_to_tokens(text, 40)

        assert count_tokens(result) <= 40 + count_tokens("… (000 more lines omitted)")
        assert "more lines omitted" in result
        for line in result.splitlines()[:-1]:
            assert line in text


class TestPromptBudgetAcrossTheCorpus:
    """US-3.5 acceptance gate, over every node in the fixture repository."""

    def test_every_prompt_fits_the_budget(self, sample_index, sample_tree):
        summarizer = Summarizer(sample_index, sample_tree, NullLLMClient())
        summarizer.run()

        violations = [r for r in summarizer.token_reports if not r.within_budget]
        assert not violations, [
            (r.node_id, r.estimated_tokens) for r in violations
        ]

    def test_a_report_is_produced_for_every_node(self, sample_index, sample_tree):
        summarizer = Summarizer(sample_index, sample_tree, NullLLMClient())
        summarizer.run()

        assert len(summarizer.token_reports) == len(sample_tree.bottom_up())

    def test_reports_carry_the_configured_ceiling(self, sample_index, sample_tree):
        summarizer = Summarizer(sample_index, sample_tree, NullLLMClient())
        summarizer.run()

        assert all(r.budget == DEFAULT_BUDGET for r in summarizer.token_reports)

    def test_repository_prompt_does_not_grow_with_repository_size(
        self, sample_index, sample_tree
    ):
        """The whole point of bottom-up: tier 1 sees summaries, not code."""
        summarizer = Summarizer(sample_index, sample_tree, NullLLMClient())
        summarizer.run()

        root_report = next(
            r for r in summarizer.token_reports if r.tier is Tier.REPOSITORY
        )
        class_reports = [r for r in summarizer.token_reports if r.tier is Tier.CLASS]

        assert root_report.estimated_tokens < DEFAULT_BUDGET
        assert root_report.estimated_tokens <= max(
            r.estimated_tokens for r in class_reports
        ) * 3

    @pytest.mark.parametrize("tier", list(Tier))
    def test_prompts_fit_at_every_tier(self, sample_index, sample_tree, tier):
        chunker = Chunker(sample_index, sample_tree)

        for node in sample_tree.nodes_at(tier):
            chunk = chunker.chunk_for(
                node,
                child_summaries=[(c.name, "A summary sentence.") for c in node.children],
            )
            prompt = build_prompt(
                tier=node.tier, name=node.name, skeleton=chunk.text, node_id=node.node_id
            )
            assert count_tokens(prompt.full_text) < DEFAULT_BUDGET


class TestCompletionLimits:

    def test_deeper_tiers_get_tighter_generation_caps(self):
        assert completion_limit(Tier.METHOD) < completion_limit(Tier.REPOSITORY)

    def test_every_tier_has_a_limit(self):
        for tier in Tier:
            assert completion_limit(tier) > 0
