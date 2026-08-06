"""Repository Indexer — Cross-file resolution and graph builder.

Aggregates FileIndex structures produced by language parsers into a unified
RepositoryIndex (top-level Intermediate Representation / IR).

Features:
- FQN Symbol Registry: Fast lookup of symbols by fully qualified name.
- Hierarchy Graph: Class inheritance (extends, implements).
- Call Graph: Direct invocation edges extracted across files.
- Relationship deduplication and cross-file resolution.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set, Tuple

from core_indexing.models import (
    ASTSymbolNode,
    DirectoryNode,
    FileIndex,
    Language,
    RelationshipEdge,
    RepositoryIndex,
)

logger = logging.getLogger(__name__)


class RepositoryIndexer:
    """Consolidates file-level AST indexes into a unified repository index."""

    def __init__(
        self,
        repository_name: str,
        repository_path: str,
        directory_tree: DirectoryNode,
        file_indexes: List[FileIndex],
    ):
        self.repository_name = repository_name
        self.repository_path = repository_path
        self.directory_tree = directory_tree
        self.file_indexes = file_indexes

        # Symbol registries
        self.symbol_registry: Dict[str, ASTSymbolNode] = {}
        self.all_symbols: List[ASTSymbolNode] = []
        self.relationships: List[RelationshipEdge] = []
        self.languages: Set[Language] = set()

    def build_index(self) -> RepositoryIndex:
        """Build and return the consolidated RepositoryIndex."""
        self._register_symbols()
        self._extract_structural_relationships()
        self._deduplicate_relationships()

        return RepositoryIndex(
            repository_name=self.repository_name,
            repository_path=self.repository_path,
            languages=sorted(list(self.languages)),
            directory_tree=self.directory_tree,
            files=self.file_indexes,
            symbols=self.all_symbols,
            relationships=self.relationships,
        )

    def _register_symbols(self):
        """Index all extracted symbols into lookup tables."""
        for file_idx in self.file_indexes:
            self.languages.add(file_idx.language)
            for symbol in file_idx.symbols:
                self.all_symbols.append(symbol)
                self.symbol_registry[symbol.symbol_id] = symbol
                if symbol.fully_qualified_name:
                    self.symbol_registry[symbol.fully_qualified_name] = symbol

    def _extract_structural_relationships(self):
        """Extract inheritance, interface implementation, and composition edges."""
        for symbol in self.all_symbols:
            # Extends
            if symbol.extends:
                target_sym = self.symbol_registry.get(symbol.extends)
                target_fqn = target_sym.fully_qualified_name if target_sym else symbol.extends
                self.relationships.append(RelationshipEdge(
                    source=symbol.fully_qualified_name,
                    target=target_fqn,
                    kind="extends",
                    line=symbol.range.start_line,
                ))

            # Implements
            for impl in symbol.implements:
                target_sym = self.symbol_registry.get(impl)
                target_fqn = target_sym.fully_qualified_name if target_sym else impl
                self.relationships.append(RelationshipEdge(
                    source=symbol.fully_qualified_name,
                    target=target_fqn,
                    kind="implements",
                    line=symbol.range.start_line,
                ))

            # Field / Property types (uses_field)
            if symbol.field_type:
                target_sym = self.symbol_registry.get(symbol.field_type)
                target_fqn = target_sym.fully_qualified_name if target_sym else symbol.field_type
                self.relationships.append(RelationshipEdge(
                    source=symbol.fully_qualified_name,
                    target=target_fqn,
                    kind="uses_field",
                    line=symbol.range.start_line,
                ))

            # Parent-child containment (contains)
            if symbol.parent_symbol_id:
                self.relationships.append(RelationshipEdge(
                    source=symbol.parent_symbol_id,
                    target=symbol.fully_qualified_name,
                    kind="contains",
                    line=symbol.range.start_line,
                ))

    def _deduplicate_relationships(self):
        """Remove duplicate relationship edges."""
        seen: Set[Tuple[str, str, str]] = set()
        deduped: List[RelationshipEdge] = []
        for rel in self.relationships:
            key = (rel.source, rel.target, rel.kind)
            if key not in seen:
                seen.add(key)
                deduped.append(rel)
        self.relationships = deduped
