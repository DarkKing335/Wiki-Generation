"""Intermediate Representation loader — the input contract from Epic 1.

These models mirror ``core_indexing.models`` (Core Indexing Engine, Epic 1)
field-for-field so that ``indexes/repository_index.json`` can be deserialised
without depending on that package.  Epic 1 lives on an unmerged branch; Epic 3
must build and test independently of it.

**This module is read-only.**  It contains no parsing logic and must never
diverge from the producer's schema.  When Epic 1 merges, the intent is to
replace this module with a direct import of ``core_indexing.models``; the field
names and types are identical precisely so that swap is a no-op.

Reference documents
-------------------
* ``docs/designs/ast-parser-design.md`` §6 — Unified AST Node Schema
* ``docs/designs/ast-parser-design.md`` §7 — Repository Index & Symbol Table
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SymbolKind(str, Enum):
    """Discriminator for all code symbol types extracted by the AST parsers."""

    PACKAGE = "PACKAGE"
    NAMESPACE = "NAMESPACE"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    ENUM = "ENUM"
    RECORD = "RECORD"
    STRUCT = "STRUCT"
    ANNOTATION = "ANNOTATION"
    DELEGATE = "DELEGATE"
    METHOD = "METHOD"
    CONSTRUCTOR = "CONSTRUCTOR"
    FIELD = "FIELD"
    PROPERTY = "PROPERTY"


class Language(str, Enum):
    """Supported source languages."""

    JAVA = "java"
    CSHARP = "csharp"


#: Symbol kinds that occupy the CLASS tier of the 6-tier taxonomy.
TYPE_KINDS = frozenset({
    SymbolKind.CLASS,
    SymbolKind.INTERFACE,
    SymbolKind.ENUM,
    SymbolKind.RECORD,
    SymbolKind.STRUCT,
})

#: Symbol kinds that occupy the METHOD tier of the 6-tier taxonomy.
CALLABLE_KINDS = frozenset({
    SymbolKind.METHOD,
    SymbolKind.CONSTRUCTOR,
})

#: Symbol kinds that carry a declared type rather than behaviour.
MEMBER_KINDS = frozenset({
    SymbolKind.FIELD,
    SymbolKind.PROPERTY,
})


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

class SourceRange(BaseModel):
    """Exact line bounds of an AST node inside its source file.

    These bounds are what makes lazy source loading possible: the chunker can
    fetch exactly the lines a symbol occupies and nothing else.
    """

    start_line: int = Field(..., description="1-based start line number")
    end_line: int = Field(..., description="1-based end line number (inclusive)")

    @property
    def line_count(self) -> int:
        return max(0, self.end_line - self.start_line + 1)


class AnnotationInfo(BaseModel):
    """An annotation (Java) or attribute (C#) attached to a symbol."""

    name: str
    arguments: Dict[str, str] = Field(default_factory=dict)


class ParameterInfo(BaseModel):
    """A single method / constructor parameter."""

    name: str
    type: str
    modifiers: List[str] = Field(default_factory=list)


class MethodSignature(BaseModel):
    """Detailed method / constructor signature metadata."""

    return_type: Optional[str] = None
    parameters: List[ParameterInfo] = Field(default_factory=list)
    thrown_exceptions: List[str] = Field(default_factory=list)
    is_async: bool = False


class PropertyAccessors(BaseModel):
    """C# property accessor information (``{ get; set; }``)."""

    has_getter: bool = False
    has_setter: bool = False
    has_init: bool = False


# ---------------------------------------------------------------------------
# Core AST symbol node
# ---------------------------------------------------------------------------

class ASTSymbolNode(BaseModel):
    """The unified, language-agnostic representation of a single code symbol."""

    symbol_id: str
    language: Language
    kind: SymbolKind
    name: str
    fully_qualified_name: str
    file_path: str
    range: SourceRange
    modifiers: List[str] = Field(default_factory=list)
    annotations: List[AnnotationInfo] = Field(default_factory=list)
    docstring: Optional[str] = None
    parent_symbol_id: Optional[str] = None
    signature: Optional[MethodSignature] = None
    property_accessors: Optional[PropertyAccessors] = None
    field_type: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    extends: Optional[str] = None
    implements: List[str] = Field(default_factory=list)

    # -- convenience accessors used across the chunker and skeleton renderer --

    @property
    def is_type(self) -> bool:
        return self.kind in TYPE_KINDS

    @property
    def is_callable(self) -> bool:
        return self.kind in CALLABLE_KINDS

    @property
    def is_member(self) -> bool:
        return self.kind in MEMBER_KINDS

    @property
    def is_public(self) -> bool:
        return "public" in self.modifiers

    @property
    def annotation_names(self) -> List[str]:
        return [a.name for a in self.annotations]

    @property
    def package(self) -> str:
        """Package / namespace this symbol belongs to.

        Derived from the FQN by stripping the trailing simple name.  Returns an
        empty string for symbols in the default package.
        """
        fqn = self.fully_qualified_name
        return fqn.rsplit(".", 1)[0] if "." in fqn else ""


# ---------------------------------------------------------------------------
# File-level index
# ---------------------------------------------------------------------------

class ImportInfo(BaseModel):
    """A single import (Java) or using directive (C#)."""

    name: str
    is_wildcard: bool = False
    is_static: bool = False
    alias: Optional[str] = None


class FileIndex(BaseModel):
    """Metadata extracted from a single source file."""

    file_path: str
    language: Language
    package_or_namespace: Optional[str] = None
    imports: List[ImportInfo] = Field(default_factory=list)
    symbols: List[ASTSymbolNode] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Repository-level index
# ---------------------------------------------------------------------------

class RelationshipEdge(BaseModel):
    """A directed edge in the hierarchy or call graph."""

    source: str
    target: str
    kind: str
    line: Optional[int] = None


class DirectoryNode(BaseModel):
    """A node in the repository directory tree."""

    name: str
    path: str
    is_directory: bool = True
    children: List["DirectoryNode"] = Field(default_factory=list)
    language: Optional[Language] = None

    def walk(self):
        """Yield this node and every descendant, depth-first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def files(self):
        """Yield every non-directory node beneath this one."""
        for node in self.walk():
            if not node.is_directory:
                yield node


DirectoryNode.model_rebuild()


class RepositoryIndex(BaseModel):
    """Top-level Intermediate Representation for an analysed repository.

    This is the primary input to Epic 3, produced by Epic 1's ``IRGenerator``
    and written to ``indexes/repository_index.json``.
    """

    repository_name: str
    repository_path: str
    languages: List[Language] = Field(default_factory=list)
    directory_tree: Optional[DirectoryNode] = None
    files: List[FileIndex] = Field(default_factory=list)
    symbols: List[ASTSymbolNode] = Field(default_factory=list)
    relationships: List[RelationshipEdge] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Symbol lookup
    # ------------------------------------------------------------------

    def build_registry(self) -> Dict[str, ASTSymbolNode]:
        """Build an FQN → symbol lookup table.

        Registers each symbol under both its ``symbol_id`` and its
        ``fully_qualified_name``, matching the dual registration the Core
        Indexing Engine performs in ``RepositoryIndexer._register_symbols``.
        This registry is the ground truth used to resolve type references when
        cross-linking skeletons.
        """
        registry: Dict[str, ASTSymbolNode] = {}
        for symbol in self.symbols:
            registry[symbol.symbol_id] = symbol
            if symbol.fully_qualified_name:
                registry.setdefault(symbol.fully_qualified_name, symbol)
        return registry

    def children_of(self, parent_symbol_id: str) -> List[ASTSymbolNode]:
        """Return all symbols whose parent is *parent_symbol_id*."""
        return [s for s in self.symbols if s.parent_symbol_id == parent_symbol_id]

    def symbols_by_package(self) -> Dict[str, List[ASTSymbolNode]]:
        """Group every symbol by its package / namespace."""
        grouped: Dict[str, List[ASTSymbolNode]] = {}
        for symbol in self.symbols:
            grouped.setdefault(symbol.package, []).append(symbol)
        return grouped


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

class StructureOverview(BaseModel):
    """The compact skeleton map Epic 1 writes to ``structure_overview.json``.

    Deliberately permissive: the producing schema is still settling, and Epic 3
    only reads it to decide whether real Module/Container tiers are available.
    See :func:`ai_analysis.taxonomy.provider.resolve_provider`.
    """

    repository: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    total_symbols: int = 0
    modules: List[Dict[str, Any]] = Field(default_factory=list)


def _read_json_text(path: Path) -> str:
    """Read a JSON file, tolerating a UTF-8 byte-order mark.

    ``utf-8-sig`` strips a BOM when present and behaves as plain UTF-8 otherwise.
    Plenty of Windows tooling emits BOMs, and a leading ``\\ufeff`` makes an
    otherwise valid document fail to parse.
    """
    return path.read_text(encoding="utf-8-sig")


def load_repository_index(path: str | Path) -> RepositoryIndex:
    """Load and validate ``repository_index.json``.

    Parameters
    ----------
    path:
        Either the JSON file itself or the directory containing it.
    """
    path = Path(path)
    if path.is_dir():
        path = path / "repository_index.json"
    if not path.exists():
        raise FileNotFoundError(
            f"repository_index.json not found at '{path}'. "
            "Run the Core Indexing Engine first: python -m core_indexing <repo> -o indexes/"
        )
    return RepositoryIndex.model_validate_json(_read_json_text(path))


def load_structure_overview(path: str | Path) -> Optional[StructureOverview]:
    """Load ``structure_overview.json`` if present, else ``None``.

    Absence is not an error — Epic 3 falls back to heuristic taxonomy detection.
    """
    path = Path(path)
    if path.is_dir():
        path = path / "structure_overview.json"
    if not path.exists():
        return None
    data = json.loads(_read_json_text(path))
    return StructureOverview.model_validate(data)
