"""Shared taxonomy construction.

Both providers differ only in how they discover tiers 2 and 3 (Module and
Container).  Tiers 4–6 (Component, Class, Method) come straight from the AST and
are identical either way, so they live here.

Reference: ``docs/designs/hierarchical-prompting-chunking.md`` §1.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ai_analysis.ir_models import ASTSymbolNode, RepositoryIndex, StructureOverview
from ai_analysis.models import TaxonomyNode, TaxonomyTree, Tier
from ai_analysis.taxonomy.provider import TaxonomyProvider

logger = logging.getLogger(__name__)

#: Container name used for symbols that sit outside any detected container.
UNSCOPED_CONTAINER = "(unscoped)"


@dataclass
class ContainerSpec:
    """A discovered tier-3 container and the tier-2 module that owns it."""

    directory: str
    """Repository-relative directory, or ``"."`` for the repository root."""

    name: str
    module_name: str
    module_path: str
    marker_file: Optional[str] = None
    symbols: List[ASTSymbolNode] = field(default_factory=list)


class BaseTaxonomyProvider(TaxonomyProvider):
    """Assembles the 6-tier tree given a container discovery strategy."""

    @abstractmethod
    def discover(
        self,
        index: RepositoryIndex,
        overview: Optional[StructureOverview],
    ) -> List[ContainerSpec]:
        """Return the containers for this repository, in stable order."""
        ...

    # ------------------------------------------------------------------

    def build(
        self,
        index: RepositoryIndex,
        overview: Optional[StructureOverview] = None,
    ) -> TaxonomyTree:
        specs = self.discover(index, overview)
        self._assign_symbols(index.symbols, specs)

        root = TaxonomyNode(
            node_id=index.repository_name,
            tier=Tier.REPOSITORY,
            name=index.repository_name,
            path=index.repository_path,
            derived_by=self.name,
        )

        # Preserve discovery order while grouping containers under their module.
        modules: Dict[str, TaxonomyNode] = {}
        for spec in specs:
            if not spec.symbols:
                continue

            module_node = modules.get(spec.module_name)
            if module_node is None:
                module_node = TaxonomyNode(
                    node_id=f"{index.repository_name}/{spec.module_name}",
                    tier=Tier.MODULE,
                    name=spec.module_name,
                    path=spec.module_path,
                    derived_by=self.name,
                )
                modules[spec.module_name] = module_node
                root.children.append(module_node)

            container_node = self._build_container(index, spec)
            if container_node.children:
                module_node.children.append(container_node)

        # Drop modules whose containers all turned out empty.
        root.children = [m for m in root.children if m.children]

        return TaxonomyTree(
            repository_name=index.repository_name,
            repository_path=index.repository_path,
            root=root,
            provider=self.name,
        )

    # ------------------------------------------------------------------
    # Symbol assignment
    # ------------------------------------------------------------------

    def _assign_symbols(
        self,
        symbols: List[ASTSymbolNode],
        specs: List[ContainerSpec],
    ) -> None:
        """Attach each symbol to the container that owns its file.

        A symbol belongs to the container whose directory is the *longest*
        matching prefix of its file path, so a nested container wins over its
        parent.  Symbols matching nothing land in a synthetic ``(unscoped)``
        container rather than being dropped.
        """
        by_dir = {s.directory: s for s in specs}
        # Longest directory first — most specific match wins.
        ordered = sorted(by_dir, key=len, reverse=True)

        unscoped: Optional[ContainerSpec] = None

        for symbol in symbols:
            file_path = symbol.file_path.replace("\\", "/")
            owner: Optional[ContainerSpec] = None

            for directory in ordered:
                if directory in (".", ""):
                    continue
                if file_path.startswith(directory + "/"):
                    owner = by_dir[directory]
                    break

            if owner is None:
                # A root-level container catches everything left over.
                root_spec = by_dir.get(".") or by_dir.get("")
                if root_spec is not None:
                    owner = root_spec
                else:
                    if unscoped is None:
                        unscoped = ContainerSpec(
                            directory=UNSCOPED_CONTAINER,
                            name=UNSCOPED_CONTAINER,
                            module_name=UNSCOPED_CONTAINER,
                            module_path=".",
                        )
                        specs.append(unscoped)
                    owner = unscoped

            owner.symbols.append(symbol)

        if unscoped is not None:
            logger.info(
                "%d symbol(s) sit outside any detected container", len(unscoped.symbols)
            )

    # ------------------------------------------------------------------
    # Tier construction (identical for both providers)
    # ------------------------------------------------------------------

    def _build_container(self, index: RepositoryIndex, spec: ContainerSpec) -> TaxonomyNode:
        node = TaxonomyNode(
            node_id=f"{index.repository_name}::{spec.directory}",
            tier=Tier.CONTAINER,
            name=spec.name,
            path=spec.directory,
            derived_by=self.name,
            marker_file=spec.marker_file,
        )

        by_package: Dict[str, List[ASTSymbolNode]] = {}
        for symbol in spec.symbols:
            by_package.setdefault(symbol.package or "(default)", []).append(symbol)

        for package in sorted(by_package):
            component = self._build_component(index, node.node_id, package, by_package[package])
            if component.children:
                node.children.append(component)

        return node

    def _build_component(
        self,
        index: RepositoryIndex,
        container_node_id: str,
        package: str,
        symbols: List[ASTSymbolNode],
    ) -> TaxonomyNode:
        node = TaxonomyNode(
            node_id=f"{container_node_id}::{package}",
            tier=Tier.COMPONENT,
            name=package,
            derived_by=self.name,
        )
        for type_symbol in sorted((s for s in symbols if s.is_type), key=lambda s: s.name):
            node.children.append(self._build_class(index, type_symbol))
        return node

    def _build_class(self, index: RepositoryIndex, symbol: ASTSymbolNode) -> TaxonomyNode:
        node = TaxonomyNode(
            node_id=symbol.symbol_id,
            tier=Tier.CLASS,
            name=symbol.name,
            symbol_id=symbol.symbol_id,
            path=symbol.file_path,
            language=symbol.language,
            derived_by=self.name,
        )

        # Only callables become tier-6 nodes.  Fields and properties are class
        # metadata rendered into the skeleton, not summarization targets — the
        # taxonomy defines tier 6 as "Executable Functions / Units".
        callables = [c for c in index.children_of(symbol.symbol_id) if c.is_callable]
        for member in sorted(callables, key=lambda s: s.range.start_line):
            node.children.append(
                TaxonomyNode(
                    node_id=member.symbol_id,
                    tier=Tier.METHOD,
                    name=member.name,
                    symbol_id=member.symbol_id,
                    path=member.file_path,
                    language=member.language,
                    derived_by=self.name,
                )
            )

        return node
