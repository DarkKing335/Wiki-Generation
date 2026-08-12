"""Live model tests — opt-in, requires a running Ollama server (US-3.1, FR-3).

Everything else in the suite proves Epic 3's claims *offline*.  Two things
cannot be proven that way, because both are properties of a real model:

* **Estimator soundness (US-3.5).**  ``tokens.count_tokens`` is a ``cl100k``
  estimate plus a safety margin.  Whether that margin is actually sufficient can
  only be settled against ``prompt_eval_count`` — the real count from the real
  tokenizer.  This is the test that validates the offline budget guard.
* **Latency (``docs/product.md``:31).**  Module summary generation under 10
  seconds is a wall-clock property of the hardware and model in use.

Deselected by default.  Run with::

    python -m pytest tests/test_ollama_live.py -v -m live

The model is read from ``REPOATLAS_LIVE_MODEL`` so the suite can be pointed at
whichever quantization fits the machine under test.  The 7B default assumes
roughly 6 GB of free VRAM; on smaller cards use a lower-bit build of the same
model, which keeps the 7B/8B parameter target intact::

    REPOATLAS_LIVE_MODEL=qwen2.5-coder:7b-instruct-q3_K_S \\
        python -m pytest tests/test_ollama_live.py -v -m live
"""

from __future__ import annotations

import os
import time

import pytest

from ai_analysis.llm.embeddings import EmbeddingClient
from ai_analysis.llm.ollama import DEFAULT_ENDPOINT, DEFAULT_MODEL, OllamaClient
from ai_analysis.models import Tier
from ai_analysis.summarizer import Summarizer
from ai_analysis.tokens import DEFAULT_BUDGET

pytestmark = pytest.mark.live

#: Override to test a quantization that fits the available VRAM.
LIVE_MODEL = os.environ.get("REPOATLAS_LIVE_MODEL", DEFAULT_MODEL)
LIVE_ENDPOINT = os.environ.get("REPOATLAS_LIVE_ENDPOINT", DEFAULT_ENDPOINT)

#: ``docs/product.md``:31 — module summary generation budget, in seconds.
MODULE_LATENCY_BUDGET = 10.0


@pytest.fixture(scope="module")
def live_client():
    """A health-checked Ollama client, or a skip explaining why not."""
    client = OllamaClient(model=LIVE_MODEL, endpoint=LIVE_ENDPOINT)

    if not client.health_check():
        client.close()
        pytest.skip(
            f"Ollama not reachable at {LIVE_ENDPOINT} or model '{LIVE_MODEL}' not pulled. "
            f"Try: ollama pull {LIVE_MODEL}"
        )

    # health_check only proves the tag is listed; loading it is a separate
    # question on a memory-constrained machine.  Fail the skip here rather than
    # in the middle of a 40-node walk.
    try:
        client.generate("Reply with the single word: ok", max_tokens=8)
    except Exception as exc:  # noqa: BLE001 - surface the load failure as a skip
        client.close()
        pytest.skip(
            f"Model '{LIVE_MODEL}' is present but would not load: {exc}. "
            "On a small GPU, try a lower-bit quantization of the same model."
        )

    yield client
    client.close()


@pytest.fixture(scope="module")
def live_run(live_client, request):
    """One full bottom-up walk over the fixture corpus, against the real model.

    Module-scoped: a live walk is the slowest thing in the suite, and every
    assertion below reads from the same measured run.
    """
    index = request.getfixturevalue("sample_index")
    tree = request.getfixturevalue("sample_tree")

    summarizer = Summarizer(index, tree, live_client)
    started = time.perf_counter()
    nodes = summarizer.run()
    elapsed = time.perf_counter() - started

    return summarizer, nodes, elapsed


@pytest.fixture(scope="module")
def sample_index(request):
    """Module-scoped copy of the session fixture, for ``live_run``."""
    from tests.conftest import _load_sample_index_dict
    from ai_analysis.ir_models import RepositoryIndex

    return RepositoryIndex.model_validate(_load_sample_index_dict())


@pytest.fixture(scope="module")
def sample_tree(sample_index):
    from ai_analysis.taxonomy.heuristic import HeuristicTaxonomyProvider

    return HeuristicTaxonomyProvider().build(sample_index)


class TestTokenGroundTruth:
    """US-3.5, settled against the model's own tokenizer."""

    def test_the_estimator_never_under_reports(self, live_run):
        """The assertion the whole offline budget guard depends on.

        If the estimate reads below the real count, every offline token test in
        this suite is measuring the wrong thing.
        """
        summarizer, _, _ = live_run
        measured = [r for r in summarizer.token_reports if r.actual_tokens is not None]

        assert measured, "no prompt_eval_count came back from the model"

        under = [
            (r.node_id, r.estimated_tokens, r.actual_tokens)
            for r in measured
            if r.estimated_tokens < r.actual_tokens
        ]
        assert not under, f"estimator under-reported on {len(under)} prompt(s): {under[:5]}"

    def test_every_real_prompt_is_under_the_ceiling(self, live_run):
        summarizer, _, _ = live_run
        measured = [r for r in summarizer.token_reports if r.actual_tokens is not None]

        over = [(r.node_id, r.actual_tokens) for r in measured if r.actual_tokens > DEFAULT_BUDGET]
        assert not over, f"prompts exceeded {DEFAULT_BUDGET} real tokens: {over[:5]}"

    def test_the_margin_is_not_wastefully_wide(self, live_run):
        """Over-reporting is safe, but a 3x margin would throw away context."""
        summarizer, _, _ = live_run
        measured = [r for r in summarizer.token_reports if r.actual_tokens]

        ratios = [r.estimated_tokens / r.actual_tokens for r in measured]
        worst = max(ratios)

        assert worst < 3.0, f"estimate runs {worst:.1f}x the real count"

    def test_report_measured_token_usage(self, live_run, capsys):
        """Not an assertion — the benchmark number the design doc claims."""
        summarizer, _, _ = live_run
        measured = [r for r in summarizer.token_reports if r.actual_tokens]

        with capsys.disabled():
            print(f"\n  model:            {LIVE_MODEL}")
            print(f"  prompts measured: {len(measured)}")
            print(f"  max real tokens:  {max(r.actual_tokens for r in measured)}")
            print(
                f"  mean real tokens: "
                f"{sum(r.actual_tokens for r in measured) / len(measured):.0f}"
            )


class TestLatency:
    """``docs/product.md``:31 — under 10 seconds per module summary."""

    def test_module_summaries_meet_the_latency_budget(self, live_run):
        summarizer, _, _ = live_run
        module_reports = [
            r for r in summarizer.token_reports
            if r.tier is Tier.MODULE and r.elapsed_seconds is not None
        ]

        assert module_reports, "no module-tier timings were recorded"

        slow = [
            (r.node_id, round(r.elapsed_seconds, 2))
            for r in module_reports
            if r.elapsed_seconds > MODULE_LATENCY_BUDGET
        ]
        assert not slow, f"module summaries over {MODULE_LATENCY_BUDGET}s: {slow}"

    def test_report_timings(self, live_run, capsys):
        summarizer, nodes, elapsed = live_run
        timed = [r for r in summarizer.token_reports if r.elapsed_seconds]

        with capsys.disabled():
            print(f"\n  nodes summarized: {len(nodes)}")
            print(f"  total wall clock: {elapsed:.1f}s")
            print(f"  slowest node:     {max(r.elapsed_seconds for r in timed):.2f}s")
            for tier in (Tier.MODULE, Tier.REPOSITORY):
                per_tier = [r.elapsed_seconds for r in timed if r.tier is tier]
                if per_tier:
                    print(
                        f"  {tier.label.lower():11} mean: "
                        f"{sum(per_tier) / len(per_tier):.2f}s"
                    )


class TestGeneratedQuality:
    """Sanity checks — a live run must produce usable prose, not empty strings."""

    def test_every_node_gets_a_non_empty_summary(self, live_run):
        _, nodes, _ = live_run
        empty = [n.node_id for n in nodes if not n.summary.strip()]

        assert not empty, f"{len(empty)} node(s) produced nothing: {empty[:5]}"

    def test_summaries_reference_real_symbols(self, live_run):
        """Grounding: the model should name things that actually exist."""
        _, nodes, _ = live_run
        class_summaries = [n for n in nodes if n.tier is Tier.CLASS]

        grounded = [n for n in class_summaries if n.referenced_symbols]
        assert grounded, "no class summary referenced a single indexed symbol"

    def test_the_repository_summary_is_substantive(self, live_run):
        _, nodes, _ = live_run
        root = next(n for n in nodes if n.tier is Tier.REPOSITORY)

        assert len(root.summary.split()) > 10


class TestLiveReproducibility:
    """``docs/product.md``:33, with sampling actually in play."""

    def test_two_live_runs_agree(self, live_client, sample_index, sample_tree):
        """The pinned seed and temperature=0 must make generation repeatable."""
        first = Summarizer(sample_index, sample_tree, live_client).run()
        second = Summarizer(sample_index, sample_tree, live_client).run()

        differing = [
            a.node_id for a, b in zip(first, second) if a.summary != b.summary
        ]
        assert not differing, (
            f"{len(differing)} summary(ies) changed between identical runs: "
            f"{differing[:5]}"
        )


class TestEmbeddings:
    """``nomic-embed-text`` backs Overview-First Retrieval."""

    def test_semantic_ranking_beats_keyword_order(self):
        client = EmbeddingClient(endpoint=LIVE_ENDPOINT)
        if not client.available:
            pytest.skip("nomic-embed-text is not pulled; try: ollama pull nomic-embed-text")

        ranked = client.rank(
            "rendering invoice documents to PDF",
            [
                ("payment", "Charges customer cards through the payment gateway."),
                ("invoice", "Produces printable invoice documents for customers."),
            ],
        )
        client.close()

        assert ranked[0][0] == "invoice"
