"""Reproducibility tests — ``docs/product.md``:33.

*"Identical repository states produce identical AST symbol graphs and static
wiki pages."*

This is a non-functional requirement that LLM sampling violates by construction
unless sampling is switched off, so it is asserted from two directions:

* the artefact is byte-identical across repeated runs (the observable property);
* the Ollama client pins ``temperature``, ``top_p``, ``top_k`` and ``seed`` on
  every request (the mechanism that makes it hold once a model is involved).

The second matters because the first, on its own, would keep passing if someone
removed the sampling pins — the no-LLM path is deterministic regardless.
"""

from __future__ import annotations

import hashlib
import json

from ai_analysis.__main__ import build_parser, run, write_result
from ai_analysis.llm.null import NullLLMClient
from ai_analysis.llm.ollama import DEFAULT_SEED, OllamaClient
from ai_analysis.summarizer import Summarizer


def digest(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestDeterministicOutput:

    def test_two_runs_produce_byte_identical_artefacts(self, sample_index_dir, tmp_path):
        args = build_parser().parse_args([str(sample_index_dir), "--no-llm"])

        first = write_result(run(args), str(tmp_path / "run1"))
        second = write_result(run(args), str(tmp_path / "run2"))

        assert digest(first) == digest(second)

    def test_summaries_are_stable_across_summarizer_instances(
        self, sample_index, sample_tree
    ):
        first = Summarizer(sample_index, sample_tree, NullLLMClient()).run()
        second = Summarizer(sample_index, sample_tree, NullLLMClient()).run()

        assert [(n.node_id, n.summary) for n in first] == [
            (n.node_id, n.summary) for n in second
        ]

    def test_traversal_order_is_stable(self, sample_index, sample_tree):
        first = [n.node_id for n in sample_tree.bottom_up()]
        second = [n.node_id for n in sample_tree.bottom_up()]

        assert first == second

    def test_taxonomy_construction_is_stable(self, sample_index):
        from ai_analysis.taxonomy.heuristic import HeuristicTaxonomyProvider

        first = HeuristicTaxonomyProvider().build(sample_index)
        second = HeuristicTaxonomyProvider().build(sample_index)

        assert first.model_dump(mode="json") == second.model_dump(mode="json")

    def test_token_reports_are_stable(self, sample_index, sample_tree):
        runs = []
        for _ in range(2):
            summarizer = Summarizer(sample_index, sample_tree, NullLLMClient())
            summarizer.run()
            runs.append([
                (r.node_id, r.estimated_tokens) for r in summarizer.token_reports
            ])

        assert runs[0] == runs[1]

    def test_wall_clock_timings_are_not_serialized(self, sample_index_dir, tmp_path):
        """Timings vary run to run and would break byte-identity if included."""
        args = build_parser().parse_args([str(sample_index_dir), "--no-llm"])
        output = write_result(run(args), str(tmp_path / "run"))
        payload = json.loads(output.read_text(encoding="utf-8"))

        for report in payload.get("token_reports", []):
            assert "elapsed_seconds" not in report


class TestSamplingIsPinned:
    """The mechanism behind reproducibility once a model is in the loop."""

    def test_generation_is_fully_greedy(self):
        options = OllamaClient().options

        assert options["temperature"] == 0
        assert options["top_p"] == 1
        assert options["top_k"] == 1

    def test_the_seed_is_fixed(self):
        assert OllamaClient().options["seed"] == DEFAULT_SEED

    def test_the_seed_survives_a_per_call_token_limit(self):
        options = OllamaClient().build_options(max_tokens=64)

        assert options["seed"] == DEFAULT_SEED
        assert options["temperature"] == 0
        assert options["num_predict"] == 64

    def test_a_custom_seed_is_honoured(self):
        assert OllamaClient(seed=7).options["seed"] == 7

    def test_context_window_is_sized_to_the_prompt_budget(self):
        """Reserving more KV cache than FR-15 can ever use costs VRAM for nothing."""
        from ai_analysis.tokens import DEFAULT_BUDGET

        num_ctx = OllamaClient().options["num_ctx"]

        assert num_ctx >= DEFAULT_BUDGET
        assert num_ctx <= DEFAULT_BUDGET * 3
