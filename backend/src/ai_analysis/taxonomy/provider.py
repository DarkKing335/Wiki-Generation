"""Taxonomy provider contract and selection.

The 6-tier taxonomy (``docs/designs/hierarchical-prompting-chunking.md`` §1) needs
Module and Container tiers that the Core Indexing Engine does not currently
produce — ``ir_generator.py::_build_skeleton_modules`` hardcodes a single module
named after the repository containing one container literally named
``"MainContainer"``.

Rather than assume either state, Epic 3 inspects the input and picks:

* :class:`~ai_analysis.taxonomy.from_index.IndexTaxonomyProvider` when
  ``structure_overview.json`` carries real tiers — the preferred path
* :class:`~ai_analysis.taxonomy.heuristic.HeuristicTaxonomyProvider` otherwise,
  detecting Containers from build files and Modules from directory grouping

When Epic 1 implements real tier detection (see
``docs/designs/taxonomy-input-contract.md``), this module starts selecting the
index-backed provider automatically and the heuristic can be deleted.  No caller
changes.

Requirements
------------
* FR-13  — Hierarchical AST chunking along the 6-tier taxonomy
* US-3.3 — Architecture layers identified
* US-3.4 — Modules identified automatically
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ai_analysis.ir_models import RepositoryIndex, StructureOverview
from ai_analysis.models import TaxonomyTree

logger = logging.getLogger(__name__)

#: Container name Epic 1 emits when it has not actually detected containers.
STUB_CONTAINER_NAME = "MainContainer"


class TaxonomyProvider(ABC):
    """Builds the 6-tier tree for a repository."""

    #: Short identifier recorded on the tree and on every node it derives.
    name: str = "abstract"

    @abstractmethod
    def build(
        self,
        index: RepositoryIndex,
        overview: Optional[StructureOverview] = None,
    ) -> TaxonomyTree:
        """Construct the taxonomy tree for *index*."""
        ...


def _containers_in(overview: StructureOverview) -> List[Dict[str, Any]]:
    """Flatten every container dict across every module of *overview*."""
    containers: List[Dict[str, Any]] = []
    for module in overview.modules:
        if isinstance(module, dict):
            for container in module.get("containers", []) or []:
                if isinstance(container, dict):
                    containers.append(container)
    return containers


def has_real_tiers(overview: Optional[StructureOverview]) -> bool:
    """Whether *overview* carries genuine Module and Container tiers.

    Two signals, both required:

    1. No container is named ``"MainContainer"`` — Epic 1's stub sentinel.
    2. Every container declares a non-empty ``path``.  A real container is a
       directory on disk; the stub has no path because it corresponds to nothing.

    The ``path`` requirement is the load-bearing one, and is what
    ``docs/designs/taxonomy-input-contract.md`` asks Member 1 to supply.
    """
    if overview is None or not overview.modules:
        return False

    containers = _containers_in(overview)
    if not containers:
        return False

    if any(c.get("name") == STUB_CONTAINER_NAME for c in containers):
        return False

    return all(c.get("path") for c in containers)


def resolve_provider(
    overview: Optional[StructureOverview] = None,
    force: Optional[str] = None,
) -> TaxonomyProvider:
    """Choose the taxonomy provider appropriate to the available input.

    Parameters
    ----------
    overview:
        Parsed ``structure_overview.json``, or ``None`` if absent.
    force:
        ``'index'`` or ``'heuristic'`` to override the automatic choice.  Used by
        tests and by the ``--taxonomy`` CLI flag.
    """
    # Imported here to avoid a circular import: the concrete providers import
    # TaxonomyProvider from this module.
    from ai_analysis.taxonomy.from_index import IndexTaxonomyProvider
    from ai_analysis.taxonomy.heuristic import HeuristicTaxonomyProvider

    if force == "index":
        return IndexTaxonomyProvider()
    if force == "heuristic":
        return HeuristicTaxonomyProvider()
    if force is not None:
        raise ValueError(f"Unknown taxonomy provider '{force}'; expected 'index' or 'heuristic'")

    if has_real_tiers(overview):
        logger.info("structure_overview.json carries real tiers; using index taxonomy provider")
        return IndexTaxonomyProvider()

    logger.info(
        "structure_overview.json has stub or missing Module/Container tiers; "
        "falling back to heuristic build-file detection"
    )
    return HeuristicTaxonomyProvider()
