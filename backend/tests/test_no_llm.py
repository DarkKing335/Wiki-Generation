"""No-LLM fallback tests — US-3.2 / FR-9.

*"As a user, I want RepoAtlas to work without an LLM, so that I can still
generate documentation."*  Acceptance: structural documentation is generated,
and missing AI descriptions do not interrupt execution.

"Does not interrupt" is the demanding half.  It is not enough that the pipeline
returns something — it must never raise, at any tier, for any symbol shape.  So
these tests drive the whole walk and assert on the artefact, rather than
spot-checking the client.
"""

from __future__ import annotations

import json

import pytest

from ai_analysis.__main__ import build_parser, run, write_result
from ai_analysis.llm.null import NullLLMClient
from ai_analysis.models import Tier
from ai_analysis.summarizer import Summarizer


class TestNullClient:

    def test_it_reports_itself_as_disabled(self):
        client = NullLLMClient()

        assert client.enabled is False
        assert client.name == "structural"

    def test_it_never_raises_on_any_input(self):
        client = NullLLMClient()

        for prompt in ("", "   ", "garbage", "Class: X", "\x00﻿", "- a: b"):
            assert isinstance(client.generate(prompt).text, str)

    def test_it_describes_a_type_from_its_annotations(self):
        text = NullLLMClient().generate(
            "STRUCTURAL SKELETON\nClass: PaymentProcessor  [@Service]  implements PaymentGateway"
        ).text

        assert "PaymentProcessor" in text
        assert "service component" in text
        assert "PaymentGateway" in text

    def test_it_describes_a_type_without_annotations(self):
        text = NullLLMClient().generate("Class: PlainThing").text
        assert "PlainThing is a class" in text

    def test_it_lists_declared_members(self):
        text = NullLLMClient().generate(
            "Class: Foo\n  Methods:\n    * alpha() -> void\n    * beta(int x) -> int"
        ).text

        assert "2 member(s)" in text
        assert "alpha" in text

    def test_it_summarizes_an_aggregate_from_child_summaries(self):
        text = NullLLMClient().generate(
            "CHILD SUMMARIES\n- payment-service: Charges cards.\n- invoice-service: Renders PDFs."
        ).text

        assert "2 element(s)" in text
        assert "payment-service" in text

    def test_it_carries_documented_intent_through(self):
        text = NullLLMClient().generate(
            "Class: Foo\n  Doc: Handles billing reconciliation."
        ).text

        assert "Handles billing reconciliation." in text


class TestFullRunWithoutAModel:
    """US-3.2's acceptance criterion, end to end."""

    def test_the_whole_walk_completes(self, sample_index, sample_tree):
        nodes = Summarizer(sample_index, sample_tree, NullLLMClient()).run()

        assert len(nodes) == len(sample_tree.bottom_up())

    def test_every_node_gets_a_non_empty_summary(self, sample_index, sample_tree):
        nodes = Summarizer(sample_index, sample_tree, NullLLMClient()).run()

        for node in nodes:
            assert node.summary.strip(), f"{node.node_id} produced an empty summary"

    def test_every_summary_is_marked_structural(self, sample_index, sample_tree):
        nodes = Summarizer(sample_index, sample_tree, NullLLMClient()).run()

        assert {n.generated_by for n in nodes} == {"structural"}

    def test_a_summary_exists_at_every_tier(self, sample_index, sample_tree):
        nodes = Summarizer(sample_index, sample_tree, NullLLMClient()).run()
        tiers = {n.tier for n in nodes}

        assert tiers == set(Tier), f"missing tiers: {set(Tier) - tiers}"

    def test_token_budget_still_holds_without_a_model(self, sample_index, sample_tree):
        summarizer = Summarizer(sample_index, sample_tree, NullLLMClient())
        summarizer.run()

        assert all(r.within_budget for r in summarizer.token_reports)


class TestCliNoLlmPath:
    """``python -m ai_analysis <index-dir> --no-llm``."""

    @pytest.fixture
    def result(self, sample_index_dir):
        args = build_parser().parse_args([str(sample_index_dir), "--no-llm"])
        return run(args)

    def test_the_run_reports_the_llm_as_disabled(self, result):
        assert result.llm_enabled is False
        assert result.model is None

    def test_the_artefact_carries_every_tier(self, result):
        assert {s.tier for s in result.summaries} == set(Tier)

    def test_all_four_content_sections_are_produced(self, result):
        assert [c.key for c in result.content] == [
            "tech", "tests", "architecture", "modules"
        ]

    def test_no_prompt_exceeded_the_budget(self, result):
        assert result.budget_violations == []
        assert 0 < result.max_prompt_tokens < 2000

    def test_the_artefact_serializes_to_json(self, result, tmp_path):
        output = write_result(result, str(tmp_path / "analysis"))
        payload = json.loads(output.read_text(encoding="utf-8"))

        assert payload["repository_name"] == "sample_repo"
        assert payload["llm_enabled"] is False
        assert payload["summaries"]
        assert payload["taxonomy"]["provider"] == "heuristic"

    def test_an_unreachable_ollama_falls_back_rather_than_failing(self, sample_index_dir):
        """A dead endpoint must degrade to structural mode, not abort (FR-9)."""
        args = build_parser().parse_args([
            str(sample_index_dir), "--endpoint", "http://127.0.0.1:1",
        ])
        result = run(args)

        assert result.llm_enabled is False
        assert result.summaries
