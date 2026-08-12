"""Heuristic taxonomy detection — infers Module and Container tiers.

Fallback used when ``structure_overview.json`` does not carry real tiers.  The
rules mirror how these concepts are actually expressed in Java and C# projects:

* **Container** (tier 3) — a deployable unit, marked by a build file:
  ``pom.xml``, ``build.gradle``, ``build.gradle.kts``, ``*.csproj``.
  Each directory containing one is a container.
* **Module** (tier 2) — a business/domain grouping, taken from the container's
  parent directory relative to the repository root.  Containers sitting directly
  at the root belong to a single module named after the repository.

Tiers 4–6 come from the AST and are built by :class:`BaseTaxonomyProvider`.

Reference: ``docs/designs/hierarchical-prompting-chunking.md`` §1 and §4.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ai_analysis.ir_models import RepositoryIndex, StructureOverview
from ai_analysis.taxonomy.base import BaseTaxonomyProvider, ContainerSpec

logger = logging.getLogger(__name__)

#: Exact filenames that mark a directory as a deployable container.
CONTAINER_MARKER_NAMES = ("pom.xml", "build.gradle", "build.gradle.kts")

#: Glob patterns that mark a directory as a deployable container.
CONTAINER_MARKER_GLOBS = ("*.csproj", "*.fsproj", "*.vbproj")

#: Directories never descended into when hunting for build files.
SKIP_DIRS = frozenset({
    ".git", ".svn", ".hg", ".idea", ".vscode", "__pycache__",
    "node_modules", "bin", "obj", "target", "build", ".gradle", "dist",
})


def find_containers(repo_path: Path) -> List[Tuple[str, str]]:
    """Locate every container directory beneath *repo_path*.

    Returns a list of ``(relative_dir, marker_file)`` sorted by depth then name,
    so parents precede children and the result is deterministic.
    ``relative_dir`` is ``"."`` for a container at the repository root.
    """
    found: Dict[str, str] = {}

    for current in _walk_dirs(repo_path):
        rel_dir = current.relative_to(repo_path).as_posix() or "."

        marker = _marker_in(current)
        if marker is not None:
            found.setdefault(rel_dir, marker.relative_to(repo_path).as_posix())

    return sorted(found.items(), key=lambda kv: (kv[0].count("/"), kv[0]))


def _marker_in(directory: Path) -> Optional[Path]:
    """Return the build file marking *directory* as a container, if any."""
    for name in CONTAINER_MARKER_NAMES:
        candidate = directory / name
        if candidate.exists():
            return candidate
    for pattern in CONTAINER_MARKER_GLOBS:
        matches = sorted(directory.glob(pattern))
        if matches:
            return matches[0]
    return None


def _walk_dirs(root: Path):
    """Yield *root* and every descendant directory, skipping build output."""
    if not root.is_dir():
        return
    yield root
    try:
        entries = sorted(root.iterdir())
    except (PermissionError, OSError):
        return
    for entry in entries:
        if entry.is_dir() and entry.name not in SKIP_DIRS:
            yield from _walk_dirs(entry)


def module_name_for(container_rel_dir: str, repository_name: str) -> Tuple[str, str]:
    """Derive the owning module of a container.

    Returns ``(module_name, module_path)``.

    >>> module_name_for("billing/payment-service", "acme")
    ('billing', 'billing')
    >>> module_name_for("payment-service", "acme")
    ('acme', '.')
    >>> module_name_for(".", "acme")
    ('acme', '.')
    """
    if container_rel_dir in (".", ""):
        return repository_name, "."
    parts = container_rel_dir.split("/")
    if len(parts) == 1:
        return repository_name, "."
    return parts[-2], "/".join(parts[:-1])


class HeuristicTaxonomyProvider(BaseTaxonomyProvider):
    """Infers Module and Container tiers from build files and directory layout."""

    name = "heuristic"

    def discover(
        self,
        index: RepositoryIndex,
        overview: Optional[StructureOverview] = None,
    ) -> List[ContainerSpec]:
        repo_path = Path(index.repository_path)
        containers = find_containers(repo_path)

        if containers:
            logger.info(
                "Detected %d container(s) from build files: %s",
                len(containers),
                ", ".join(d for d, _ in containers),
            )
        else:
            logger.warning(
                "No build files found under '%s'; treating the repository as one container",
                repo_path,
            )
            return [
                ContainerSpec(
                    directory=".",
                    name=index.repository_name,
                    module_name=index.repository_name,
                    module_path=".",
                )
            ]

        specs: List[ContainerSpec] = []
        for container_dir, marker in containers:
            module_name, module_path = module_name_for(container_dir, index.repository_name)
            name = (
                index.repository_name
                if container_dir in (".", "")
                else container_dir.split("/")[-1]
            )
            specs.append(
                ContainerSpec(
                    directory=container_dir,
                    name=name,
                    module_name=module_name,
                    module_path=module_path,
                    marker_file=marker,
                )
            )
        return specs
