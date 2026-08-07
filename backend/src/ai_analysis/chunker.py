"""Hierarchical AST chunker (FR-13, US-3.5).

Produces the context for each summarization prompt, and is the component that
makes the "zero context boundary cuts" guarantee in ``docs/epics.md`` Epic 3
literally true: a chunk is always exactly one AST node's skeleton, never a slice
of lines.

Contrast with naive chunking
----------------------------
Line-based chunking splits every N lines, cutting through method bodies and
severing annotations from the signatures they modify.  Here, the unit of
chunking *is* the AST node, so a chunk cannot straddle a syntactic boundary —
there is no line arithmetic anywhere in the chunk construction path.

Lazy source loading
-------------------
:meth:`Chunker.read_source_range` implements the handshake in
``docs/designs/ast-parser-design.md`` §8: raw source is fetched only on explicit
request, and only for the exact line range the AST recorded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ai_analysis.ir_models import ASTSymbolNode, RepositoryIndex
from ai_analysis.models import TaxonomyNode, TaxonomyTree, Tier
from ai_analysis import skeleton as skel

logger = logging.getLogger(__name__)

#: Cap on lazily loaded source, so a pathological method cannot blow the budget.
MAX_SOURCE_TOKENS = 600


@dataclass
class Chunk:
    """One AST-bounded unit of context for a single prompt."""

    node_id: str
    tier: Tier
    name: str
    text: str
    """The rendered skeleton, or the child-summary digest at aggregating tiers."""

    symbol_id: Optional[str] = None
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    referenced_symbols: List[str] = field(default_factory=list)
    """FQNs appearing in this chunk — the grounding set for the generated summary."""

    @property
    def is_ast_bounded(self) -> bool:
        """Whether this chunk maps onto a single AST node.

        True at tiers 5–6.  Aggregating tiers compose child summaries, which are
        text, not code, and therefore cannot cut a syntactic boundary either.
        """
        return self.symbol_id is not None


class Chunker:
    """Builds prompt context from the taxonomy tree and the symbol index."""

    def __init__(self, index: RepositoryIndex, tree: TaxonomyTree):
        self.index = index
        self.tree = tree
        self.registry: Dict[str, ASTSymbolNode] = index.build_registry()
        self.repo_path = Path(index.repository_path)
        self._source_cache: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Chunk construction
    # ------------------------------------------------------------------

    def chunk_for(
        self,
        node: TaxonomyNode,
        child_summaries: Optional[List[tuple[str, str]]] = None,
        **render_options,
    ) -> Chunk:
        """Build the chunk for *node*.

        Tiers 5 and 6 render an AST skeleton.  Tiers 1–4 render a digest of
        *child_summaries* — they never touch code, which is what keeps the
        repository-level prompt small no matter how large the repository is.
        """
        if node.tier is Tier.METHOD:
            return self._method_chunk(node, **render_options)
        if node.tier is Tier.CLASS:
            return self._class_chunk(node, **render_options)
        return self._aggregate_chunk(node, child_summaries or [], **render_options)

    def _method_chunk(self, node: TaxonomyNode, **options) -> Chunk:
        symbol = self._require_symbol(node)
        options.pop("include_private", None)  # not meaningful for a single member
        text = skel.render_method_skeleton(symbol, self.index, **options)

        return Chunk(
            node_id=node.node_id,
            tier=node.tier,
            name=node.name,
            text=text,
            symbol_id=symbol.symbol_id,
            file_path=symbol.file_path,
            start_line=symbol.range.start_line,
            end_line=symbol.range.end_line,
            referenced_symbols=self._references_of(symbol),
        )

    def _class_chunk(self, node: TaxonomyNode, **options) -> Chunk:
        symbol = self._require_symbol(node)
        text = skel.render_class_skeleton(symbol, self.index, **options)

        references = self._references_of(symbol)
        for child in self.index.children_of(symbol.symbol_id):
            references.extend(self._references_of(child))

        return Chunk(
            node_id=node.node_id,
            tier=node.tier,
            name=node.name,
            text=text,
            symbol_id=symbol.symbol_id,
            file_path=symbol.file_path,
            start_line=symbol.range.start_line,
            end_line=symbol.range.end_line,
            referenced_symbols=sorted(set(references)),
        )

    def _aggregate_chunk(
        self,
        node: TaxonomyNode,
        child_summaries: List[tuple[str, str]],
        **options,
    ) -> Chunk:
        doc_chars = options.get("doc_chars", 0)
        text = skel.render_summary_digest(child_summaries, doc_chars=doc_chars)

        if not text:
            # No child produced a summary — fall back to naming the children so
            # the prompt still has something structural to describe.
            text = "\n".join(f"- {c.name} ({c.tier.label})" for c in node.children)

        return Chunk(
            node_id=node.node_id,
            tier=node.tier,
            name=node.name,
            text=text,
            file_path=node.path,
            referenced_symbols=sorted(
                {c.symbol_id for c in node.walk() if c.symbol_id}
            ),
        )

    # ------------------------------------------------------------------
    # Lazy source loading (ast-parser-design.md §8)
    # ------------------------------------------------------------------

    def read_source_range(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        *,
        max_tokens: int = MAX_SOURCE_TOKENS,
    ) -> str:
        """Fetch exactly lines *start_line*–*end_line* of *file_path*.

        Line numbers are 1-based and inclusive, matching ``SourceRange``.  This
        is the only place in Epic 3 that reads source code, and it runs only when
        something explicitly asks for a method body.
        """
        if start_line < 1 or end_line < start_line:
            raise ValueError(
                f"Invalid line range {start_line}-{end_line} for '{file_path}'"
            )

        lines = self._source_lines(file_path)
        if not lines:
            return ""

        excerpt = "\n".join(lines[start_line - 1 : end_line])
        from ai_analysis.tokens import truncate_to_tokens

        return truncate_to_tokens(excerpt, max_tokens)

    def read_symbol_source(self, symbol_id: str, **kwargs) -> str:
        """Fetch the source of a symbol by FQN or ``symbol_id``."""
        symbol = self.registry.get(symbol_id)
        if symbol is None:
            raise KeyError(f"Unknown symbol '{symbol_id}'")
        return self.read_source_range(
            symbol.file_path, symbol.range.start_line, symbol.range.end_line, **kwargs
        )

    def _source_lines(self, file_path: str) -> List[str]:
        cached = self._source_cache.get(file_path)
        if cached is not None:
            return cached

        absolute = self.repo_path / file_path
        try:
            lines = absolute.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            logger.warning("Could not read source '%s': %s", absolute, exc)
            lines = []

        self._source_cache[file_path] = lines
        return lines

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_symbol(self, node: TaxonomyNode) -> ASTSymbolNode:
        if node.symbol_id is None:
            raise ValueError(f"Taxonomy node '{node.node_id}' (tier {node.tier.name}) has no symbol")
        symbol = self.registry.get(node.symbol_id)
        if symbol is None:
            raise KeyError(f"Symbol '{node.symbol_id}' missing from the repository index")
        return symbol

    def _references_of(self, symbol: ASTSymbolNode) -> List[str]:
        """Every FQN this symbol names that resolves against the registry.

        Used to ground generated summaries: a summary should only mention symbols
        that actually exist (``docs/designs/ast-parser-design.md``:178).
        """
        candidates = list(symbol.dependencies) + list(symbol.implements)
        if symbol.extends:
            candidates.append(symbol.extends)
        if symbol.field_type:
            candidates.append(symbol.field_type)
        if symbol.signature:
            if symbol.signature.return_type:
                candidates.append(symbol.signature.return_type)
            candidates.extend(p.type for p in symbol.signature.parameters)

        return sorted({c for c in candidates if c in self.registry})
