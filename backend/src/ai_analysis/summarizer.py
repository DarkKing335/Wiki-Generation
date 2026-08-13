"""Bottom-up hierarchical summarization (US-3.1 – US-3.5, ADR-010).

The traversal that makes a 200k-line repository describable by a 7B model::

    Method AST nodes + docstrings
          │ summarize each method
          ▼
    Class summaries      ← method summaries + class AST metadata
          │
          ▼
    Component summaries  ← class summaries within a package/namespace
          │
          ▼
    Container / Module summaries
          │
          ▼
    Repository architecture summary

The invariant that makes it work: **each tier consumes only the summaries of the
tier below, never its source.** By the time the repository-level prompt is built
it is summarizing a handful of module summaries — a few hundred tokens — no
matter how large the repository is.

Grounding
---------
Each generated summary is checked against the symbol registry: identifiers the
model mentions that resolve to real symbols are recorded on the summary.  This
is the mechanism behind ``docs/designs/ast-parser-design.md``:178 — *"the LLM is
forced to reference indexed FQNs"* — and provides the hook a future evaluation
harness would use to measure hallucination rate.
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby
from typing import Dict, List, Optional, Sequence, Tuple

from ai_analysis.chunker import Chunker
from ai_analysis.ir_models import RepositoryIndex
from ai_analysis.llm.base import LLMClient
from ai_analysis.llm.null import NullLLMClient
from ai_analysis.models import (
    SummaryNode,
    TaxonomyNode,
    TaxonomyTree,
    Tier,
    TokenReport,
)
from ai_analysis.prompts import Prompt, build_prompt, completion_limit
from ai_analysis.tokens import (
    CHAT_TEMPLATE_OVERHEAD,
    DEFAULT_BUDGET,
    count_tokens,
    enforce_budget,
)
from ai_analysis.tools.dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)

#: Identifier-shaped tokens: FQNs, CamelCase type names, method names.
_IDENTIFIER = re.compile(r"\b[A-Za-z_][\w.]*\b")

#: Tiers whose prompts render AST skeletons rather than child summaries.
_CODE_TIERS = (Tier.CLASS, Tier.METHOD)

#: The only tool worth offering mid-summarization.
#:
#: Measured against qwen2.5-coder:7b, the full four-tool schema set adds ~470
#: tokens to every prompt it is attached to — more than the skeleton itself.
#: ``get_skeleton``, ``search_summaries`` and ``summarize`` are not useful while
#: summarizing one specific node, so only the lazy-load handshake is exposed.
LAZY_LOAD_TOOL = "read_source_range"

#: Minimum body length before lazy source loading is offered.  A one-line
#: accessor has no algorithm worth fetching.
MIN_LINES_FOR_SOURCE = 5

#: Sibling nodes summarized concurrently within a single tier.
#:
#: ``TaxonomyTree.bottom_up`` orders strictly by descending tier, so every node in
#: a tier has had all of its children summarized already — siblings never depend
#: on each other and are structurally safe to run in parallel.  Node ordering and
#: token accounting stay identical at any worker count.
#:
#: Throughput peaks at exactly 2 and then *regresses* — measured end-to-end on
#: qwen2.5-coder:1.5b over the sample repository: 52.4s / 38.4s / 41.2s / 43.0s
#: at 1 / 2 / 3 / 4 workers.
#:
#: The reason is that a stock Ollama server runs a single inference slot
#: (``OLLAMA_NUM_PARALLEL`` defaults to 1, and the server log only ever shows
#: ``slot id 0``), so concurrent requests do not actually infer in parallel.
#: What the second worker overlaps is the ~0.66s of fixed per-request server
#: overhead that every call pays regardless of prompt or output size.  A third
#: worker has no overhead left to hide and only adds queueing.
#:
#: **Set this to 1 when you need reproducible output.**  The cause is not
#: batched inference — with one slot there is no batching.  It is Ollama's
#: prompt cache: it selects and reuses a cached KV prefix by longest-common-
#: prefix similarity across requests, so interleaving changes which prefix is
#: resident when a given prompt runs, which changes ``n_past`` and with it the
#: numerics.  That is enough to flip token choices at ``temperature=0`` with a
#: fixed seed.  Measured over the sample repository: two sequential runs are
#: byte-identical, while 2 workers diverged from sequential on 15 and 19 of 35
#: summaries across two measurements — roughly half the tree, and that
#: difference cascades, because aggregating tiers compose their children's text.
#:
#: Node ordering and token accounting stay stable at any worker count; only the
#: generated prose varies.
DEFAULT_MAX_WORKERS = 2

#: Minimum body length before a method is worth an LLM call at all.
#:
#: A getter, a one-line delegate or an empty test stub has no behaviour a model
#: can describe better than its own signature and docstring already do.  Local
#: SLM inference is the dominant cost in the whole pipeline — measured at 5-8
#: tokens/second on CPU — so skipping these is the single largest runtime saving
#: available, and it costs nothing in summary quality.
MIN_LINES_FOR_LLM = 4


class Summarizer:
    """Walks the taxonomy bottom-up, producing one summary per node."""

    def __init__(
        self,
        index: RepositoryIndex,
        tree: TaxonomyTree,
        llm: LLMClient,
        *,
        chunker: Optional[Chunker] = None,
        dispatcher: Optional[ToolDispatcher] = None,
        budget: int = DEFAULT_BUDGET,
        allow_lazy_source: bool = True,
        skip_trivial_methods: bool = True,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ):
        self.index = index
        self.tree = tree
        self.llm = llm
        self.chunker = chunker or Chunker(index, tree)
        self.dispatcher = dispatcher
        self.budget = budget
        self.allow_lazy_source = allow_lazy_source
        self.skip_trivial_methods = skip_trivial_methods
        self.max_workers = max(1, max_workers)

        #: Describes trivial methods without a model call. Always available, so
        #: the structural path costs nothing even when an LLM is configured.
        self._structural_fallback = NullLLMClient()

        #: node_id → summary text, populated as the walk proceeds.  Shared with
        #: the tool registry so ``search_summaries`` sees partial results.
        self.summaries: Dict[str, str] = {}
        self.nodes: List[SummaryNode] = []
        self.token_reports: List[TokenReport] = []

        self._ancestry: Dict[str, List[TaxonomyNode]] = {}
        self._index_ancestry(self.tree.root, [])
        self._overhead_cache: Dict[int, int] = {}

    # ------------------------------------------------------------------

    def run(self) -> List[SummaryNode]:
        """Summarize every node, deepest tier first.

        Tiers are processed in strict bottom-up order because an aggregating node
        composes its children's summaries.  Within a tier, siblings are mutually
        independent and run concurrently when ``max_workers`` allows it.  Results
        are always recorded in ``bottom_up`` order regardless of completion
        order, keeping ``nodes`` and ``token_reports`` reproducible.
        """
        ordered = self.tree.bottom_up()
        logger.info(
            "Summarizing %d node(s) bottom-up using %s (%d worker(s))",
            len(ordered), self.llm.name, self.max_workers,
        )

        for _, group in groupby(ordered, key=lambda n: n.tier.value):
            self._record(self._summarize_tier(list(group)))

        return self.nodes

    def _summarize_tier(self, group: List[TaxonomyNode]) -> List[SummaryNode]:
        """Summarize one tier's worth of siblings, preserving *group* order."""
        if self.max_workers == 1 or len(group) == 1:
            return [self._summarize_node(node) for node in group]

        workers = min(self.max_workers, len(group))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # ``map`` yields in submit order, not completion order.
            return list(pool.map(self._summarize_node, group))

    def _record(self, summaries: List[SummaryNode]) -> None:
        """Commit a completed tier so the next tier can aggregate it."""
        for summary in summaries:
            self.summaries[summary.node_id] = summary.summary
            self.nodes.append(summary)
            self.token_reports.append(summary.tokens)

    # ------------------------------------------------------------------

    def _summarize_node(self, node: TaxonomyNode) -> SummaryNode:
        prompt, report = self._build_prompt(node)
        use_llm = self.llm.enabled and self._worth_an_llm_call(node)

        started = time.perf_counter()
        if use_llm:
            text = self._generate(prompt, node, report)
        else:
            text = self._structural_fallback.generate(prompt.user).text or self._fallback_text(node)
        report.elapsed_seconds = time.perf_counter() - started

        # ``token_reports`` is appended by :meth:`_record`, not here, so its order
        # follows the bottom-up walk rather than thread completion order.
        return SummaryNode(
            node_id=node.node_id,
            tier=node.tier,
            name=node.name,
            summary=text,
            generated_by="llm" if use_llm else "structural",
            referenced_symbols=self._ground(text),
            tokens=report,
        )

    def _worth_an_llm_call(self, node: TaxonomyNode) -> bool:
        """Whether *node* has enough behaviour to justify a model call.

        Only methods are filtered.  Every aggregating tier summarizes several
        children and genuinely needs prose; a trivial method does not.
        """
        if not self.skip_trivial_methods or node.tier is not Tier.METHOD:
            return True
        if node.symbol_id is None:
            return True

        symbol = self.chunker.registry.get(node.symbol_id)
        if symbol is None:
            return True
        return symbol.range.line_count >= MIN_LINES_FOR_LLM

    def _tool_schemas(self, node: TaxonomyNode) -> Optional[List[dict]]:
        """Tool schemas to attach to *node*'s request, or ``None``."""
        if self.dispatcher is None or not self._may_request_source(node):
            return None
        if LAZY_LOAD_TOOL not in self.dispatcher.registry:
            return None
        return [self.dispatcher.registry.get(LAZY_LOAD_TOOL).to_schema()]

    def _tool_overhead(self, schemas: Optional[List[dict]]) -> int:
        """Tokens the backend spends rendering *schemas* into the prompt.

        Ollama serialises tool definitions into the chat template, so they count
        against the context window even though they never appear in the prompt
        string this code builds.  Measured live, omitting this made the estimate
        read ~3x low at code tiers.
        """
        if not schemas:
            return 0

        cached = self._overhead_cache.get(id(self.dispatcher))
        if cached is None:
            cached = count_tokens(json.dumps(schemas))
            self._overhead_cache[id(self.dispatcher)] = cached
        return cached

    def _build_prompt(self, node: TaxonomyNode) -> Tuple[Prompt, TokenReport]:
        """Render the prompt for *node*, trimming until it fits the budget."""
        child_summaries = [
            (child.name, self.summaries.get(child.node_id, ""))
            for child in node.children
        ]
        ancestry_nodes = self._ancestry.get(node.node_id, [])
        overhead = self._tool_overhead(self._tool_schemas(node)) + CHAT_TEMPLATE_OVERHEAD

        def render(**options) -> str:
            chunk = self.chunker.chunk_for(node, child_summaries=child_summaries, **options)
            return build_prompt(
                tier=node.tier,
                name=node.name,
                skeleton=chunk.text,
                node_id=node.node_id,
                ancestry=[a.name for a in ancestry_nodes],
                ancestry_tiers=[a.tier for a in ancestry_nodes],
                language=node.language.value if node.language else None,
            ).full_text

        # Tool schemas consume budget before the skeleton gets any, so degrade
        # against what is actually left.
        result = enforce_budget(
            render, budget=self.budget - overhead, node_id=node.node_id
        )

        # Rebuild the structured Prompt at whatever detail level fit.
        options = _OPTIONS_FOR_STEP.get(result.steps_applied[-1], {})
        chunk = self.chunker.chunk_for(node, child_summaries=child_summaries, **options)
        prompt = build_prompt(
            tier=node.tier,
            name=node.name,
            skeleton=chunk.text,
            node_id=node.node_id,
            ancestry=[a.name for a in ancestry_nodes],
            ancestry_tiers=[a.tier for a in ancestry_nodes],
            language=node.language.value if node.language else None,
        )

        report = TokenReport(
            node_id=node.node_id,
            tier=node.tier,
            estimated_tokens=count_tokens(prompt.full_text) + overhead,
            tool_overhead_tokens=overhead - CHAT_TEMPLATE_OVERHEAD,
            budget=self.budget,
            was_degraded=result.was_degraded,
        )
        return prompt, report

    def _generate(self, prompt: Prompt, node: TaxonomyNode, report: TokenReport) -> str:
        """Call the model, honouring at most one round of tool requests."""
        tools = self._tool_schemas(node)
        limit = completion_limit(node.tier)

        response = self.llm.generate(
            prompt.user, system=prompt.system, tools=tools, max_tokens=limit
        )

        # Ground truth from the model's own tokenizer — what the estimate in
        # tokens.py is validated against (US-3.5).
        if response.prompt_token_count is not None:
            report.actual_tokens = response.prompt_token_count

        if not response.requested_tools or self.dispatcher is None:
            return response.text or self._fallback_text(node)

        # One follow-up round only. Traversal stays deterministic; the model
        # gets to fetch context, not to drive the walk (vision.md:53).
        self.dispatcher.reset()
        results = self.dispatcher.dispatch_all(response.tool_calls)
        extra = "\n\n".join(r.as_context() for r in results if r.as_context())

        if not extra:
            return response.text or self._fallback_text(node)

        followup = build_prompt(
            tier=prompt.tier,
            name=node.name,
            skeleton=self.chunker.chunk_for(
                node,
                child_summaries=[
                    (c.name, self.summaries.get(c.node_id, "")) for c in node.children
                ],
            ).text,
            node_id=node.node_id,
            extra_context=extra,
        )
        second = self.llm.generate(
            followup.user, system=followup.system, max_tokens=limit
        )
        return second.text or response.text or self._fallback_text(node)

    def _may_request_source(self, node: TaxonomyNode) -> bool:
        """Whether lazy source loading is offered for this node.

        Only at code tiers, and only when there is a body worth fetching — a
        one-line accessor has no algorithm to explain.
        """
        if not self.allow_lazy_source or node.tier not in _CODE_TIERS:
            return False
        if node.symbol_id is None:
            return False

        symbol = self.chunker.registry.get(node.symbol_id)
        if symbol is None:
            return False
        return symbol.range.line_count > MIN_LINES_FOR_SOURCE

    def _fallback_text(self, node: TaxonomyNode) -> str:
        """Used when the model returns nothing at all.

        An empty summary must not propagate upward as blank context, so the node
        still gets a factual description (US-3.2's no-interruption requirement).
        """
        return f"{node.name} is a {node.tier.label.lower()} containing {len(node.children)} element(s)."

    # ------------------------------------------------------------------
    # Grounding
    # ------------------------------------------------------------------

    def _ground(self, text: str) -> List[str]:
        """Return the identifiers in *text* that resolve to real symbols.

        Matching is on simple names as well as FQNs, because a summary naturally
        writes ``StripePaymentProcessor`` rather than the fully qualified form.
        """
        if not text:
            return []

        registry = self.chunker.registry
        by_simple_name = self._simple_name_map()

        found: set[str] = set()
        for token in _IDENTIFIER.findall(text):
            if token in registry:
                found.add(registry[token].fully_qualified_name)
            elif token in by_simple_name:
                found.update(by_simple_name[token])

        return sorted(found)

    def _simple_name_map(self) -> Dict[str, List[str]]:
        cached = getattr(self, "_simple_names", None)
        if cached is not None:
            return cached

        mapping: Dict[str, List[str]] = {}
        for symbol in self.index.symbols:
            mapping.setdefault(symbol.name, []).append(symbol.fully_qualified_name)

        self._simple_names = mapping
        return mapping

    # ------------------------------------------------------------------

    def _index_ancestry(self, node: TaxonomyNode, trail: List[TaxonomyNode]) -> None:
        self._ancestry[node.node_id] = list(trail)
        for child in node.children:
            self._index_ancestry(child, trail + [node])


#: Maps a degradation step name back to the render options that produced it, so
#: the structured prompt can be rebuilt at the detail level that fit the budget.
_OPTIONS_FOR_STEP: Dict[str, Dict[str, object]] = {
    "full": {},
    "no-private": {"include_private": False},
    "short-docs": {"include_private": False, "doc_chars": 80},
    "no-docs": {"include_private": False, "include_docstrings": False},
    "signatures-only": {
        "include_private": False,
        "include_docstrings": False,
        "doc_chars": 0,
    },
}
