"""Epic 3's four declared tools.

| Tool                 | Purpose                                                    |
| -------------------- | ---------------------------------------------------------- |
| ``read_source_range`` | Fetch exact source lines — the lazy-load escape hatch      |
| ``get_skeleton``      | Fetch a symbol's AST skeleton without its body             |
| ``search_summaries``  | Overview-First Retrieval over already-generated summaries  |
| ``summarize``         | The Epic 3 tool named in ``docs/system-overview.md``       |

The six Epic 1 tools (``scan_structure``, ``save_structure``, ``read_file``,
``parse_java_ast``, ``parse_csharp_ast``, ``build_import_graph``) are not
declared here — they belong to the Core Indexing Engine and can register into the
same :class:`ToolRegistry` when the branches merge.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from ai_analysis.chunker import Chunker
from ai_analysis.llm.embeddings import EmbeddingClient
from ai_analysis.models import Tier
from ai_analysis.skeleton import render_class_skeleton, render_method_skeleton
from ai_analysis.tools.registry import ToolDefinition, ToolParameter, ToolRegistry

logger = logging.getLogger(__name__)


def build_registry(
    chunker: Chunker,
    *,
    embeddings: Optional[EmbeddingClient] = None,
    summaries: Optional[Dict[str, str]] = None,
    summarize_fn: Optional[Callable[[str, str], str]] = None,
) -> ToolRegistry:
    """Construct the registry, binding handlers to this run's state.

    Parameters
    ----------
    embeddings:
        Client backing ``search_summaries``.  Defaults to an *offline* client
        that keyword-ranks without touching the network, so the registry is
        usable with no Ollama server running.  Callers running with an LLM pass
        a live client.
    summaries:
        Live mapping of ``node_id`` → summary text.  The summarizer mutates it as
        it walks bottom-up, so ``search_summaries`` sees whatever has been
        produced so far.
    summarize_fn:
        Optional callback backing the ``summarize`` tool.  When absent the tool
        is still declared but reports that direct invocation is unavailable —
        traversal is driven by the summarizer, not by the model.
    """
    registry = ToolRegistry()
    summaries = summaries if summaries is not None else {}
    # Built once rather than per call, so availability is probed at most once.
    embeddings = embeddings if embeddings is not None else EmbeddingClient.offline()

    # -- read_source_range ------------------------------------------------
    def _read_source_range(file_path: str, start_line: int, end_line: int) -> str:
        return chunker.read_source_range(file_path, start_line, end_line)

    registry.register(ToolDefinition(
        name="read_source_range",
        description=(
            "Read the exact source lines of a code element. Use only when the "
            "structural skeleton is insufficient and the actual algorithm inside "
            "a method body is required."
        ),
        parameters=[
            ToolParameter(
                name="file_path",
                type="string",
                description="Repository-relative path of the source file.",
            ),
            ToolParameter(
                name="start_line",
                type="integer",
                description="First line to read, 1-based and inclusive.",
            ),
            ToolParameter(
                name="end_line",
                type="integer",
                description="Last line to read, 1-based and inclusive.",
            ),
        ],
        handler=_read_source_range,
    ))

    # -- get_skeleton -----------------------------------------------------
    def _get_skeleton(fqn: str) -> str:
        symbol = chunker.registry.get(fqn)
        if symbol is None:
            return f"No symbol named '{fqn}' exists in this repository."
        if symbol.is_callable:
            return render_method_skeleton(symbol, chunker.index)
        return render_class_skeleton(symbol, chunker.index)

    registry.register(ToolDefinition(
        name="get_skeleton",
        description=(
            "Get the AST skeleton of a type or method by fully qualified name: "
            "its annotations, signature, fields and documentation, without any "
            "method bodies."
        ),
        parameters=[
            ToolParameter(
                name="fqn",
                type="string",
                description="Fully qualified name, e.g. com.example.auth.UserService.",
            ),
        ],
        handler=_get_skeleton,
    ))

    # -- search_summaries -------------------------------------------------
    def _search_summaries(query: str, tier: Optional[str] = None, limit: int = 5) -> str:
        candidates = _summary_candidates(chunker, summaries, tier)
        if not candidates:
            return "No summaries have been generated yet."

        ranked = embeddings.rank(query, candidates, top_k=limit)
        if not ranked:
            return f"No summaries matched '{query}'."

        return "\n".join(
            f"- {node_id} (score {score:.2f}): {summaries.get(node_id, '')}"
            for node_id, score in ranked
        )

    registry.register(ToolDefinition(
        name="search_summaries",
        description=(
            "Search summaries already generated for this repository, to locate "
            "the relevant module or component before drilling into code."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="What to look for, in natural language.",
            ),
            ToolParameter(
                name="tier",
                type="string",
                description="Restrict results to one taxonomy tier.",
                required=False,
                enum=[t.name.lower() for t in Tier],
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum results to return.",
                required=False,
                default=5,
            ),
        ],
        handler=_search_summaries,
    ))

    # -- summarize --------------------------------------------------------
    def _summarize(tier: str, target_fqn: str) -> str:
        if summarize_fn is None:
            return (
                "Direct summarization is not available: summaries are produced by "
                "a deterministic bottom-up traversal, not on demand."
            )
        return summarize_fn(tier, target_fqn)

    registry.register(ToolDefinition(
        name="summarize",
        description=(
            "Generate a natural-language summary for one taxonomy node using "
            "bottom-up hierarchical chunking."
        ),
        parameters=[
            ToolParameter(
                name="tier",
                type="string",
                description="Taxonomy tier of the target.",
                enum=[t.name.lower() for t in Tier],
            ),
            ToolParameter(
                name="target_fqn",
                type="string",
                description="Fully qualified name or taxonomy node id of the target.",
            ),
        ],
        handler=_summarize,
    ))

    return registry


def _summary_candidates(
    chunker: Chunker,
    summaries: Dict[str, str],
    tier: Optional[str],
) -> List[Tuple[str, str]]:
    """Collect ``(node_id, summary)`` pairs, optionally filtered by tier."""
    if tier is None:
        return [(node_id, text) for node_id, text in summaries.items() if text]

    wanted = tier.upper()
    tiers_by_node = {n.node_id: n.tier.name for n in chunker.tree.root.walk()}

    return [
        (node_id, text)
        for node_id, text in summaries.items()
        if text and tiers_by_node.get(node_id) == wanted
    ]
