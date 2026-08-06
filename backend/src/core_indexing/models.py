"""Unified AST Node Schema — Pydantic data models for the Core Indexing Engine.

These models implement the standardized Intermediate Representation (IR)
defined in ``docs/designs/ast-parser-design.md`` (Section 6: Unified AST
Node Schema).  Every language parser driver normalises raw AST trees into
these structures so that downstream modules (Knowledge Graph builder,
Hierarchical Chunker, HTML Renderer) consume a single, language-agnostic
format.

Reference documents
-------------------
* ``docs/designs/ast-parser-design.md`` — Unified AST Node Schema
* ``docs/designs/hierarchical-prompting-chunking.md`` — 6-Tier Taxonomy
* ``docs/architecture.md`` — Component Architecture
"""

from __future__ import annotations

from enum import Enum
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


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

class SourceRange(BaseModel):
    """Exact line bounds of an AST node inside its source file."""

    start_line: int = Field(..., description="1-based start line number")
    end_line: int = Field(..., description="1-based end line number (inclusive)")


class AnnotationInfo(BaseModel):
    """An annotation (Java) or attribute (C#) attached to a symbol.

    Example (Java)::

        @Transactional(readOnly = false)
        →  AnnotationInfo(name="Transactional", arguments={"readOnly": "false"})

    Example (C#)::

        [HttpGet("/orders")]
        →  AnnotationInfo(name="HttpGet", arguments={"value": "/orders"})
    """

    name: str
    arguments: Dict[str, str] = Field(default_factory=dict)


class ParameterInfo(BaseModel):
    """A single method / constructor parameter."""

    name: str
    type: str
    modifiers: List[str] = Field(
        default_factory=list,
        description="e.g. ['ref'], ['out'], ['in'], ['params'] for C#",
    )


class MethodSignature(BaseModel):
    """Detailed method / constructor signature metadata."""

    return_type: Optional[str] = None
    parameters: List[ParameterInfo] = Field(default_factory=list)
    thrown_exceptions: List[str] = Field(
        default_factory=list,
        description="Java 'throws' clause; not applicable to C#",
    )
    is_async: bool = Field(
        default=False,
        description="True when the C# method is declared 'async'",
    )


class PropertyAccessors(BaseModel):
    """C# property accessor information (``{ get; set; }``)."""

    has_getter: bool = False
    has_setter: bool = False
    has_init: bool = False


# ---------------------------------------------------------------------------
# Core AST Symbol Node
# ---------------------------------------------------------------------------

class ASTSymbolNode(BaseModel):
    """The unified, language-agnostic representation of a single code symbol.

    This is the **primary output unit** of every language parser.  The schema
    matches the JSON structure defined in ``docs/designs/ast-parser-design.md``
    Section 6 ("Unified AST Node Schema").

    Examples of ``symbol_id`` values::

        "com.example.auth.UserService"
        "com.example.auth.UserService.authenticate(String,String)"
        "MyApp.Controllers.OrderController"
    """

    symbol_id: str = Field(
        ...,
        description=(
            "Globally unique identifier.  For Java this is the fully-qualified "
            "name built from the package declaration; for C# it is built from "
            "the namespace."
        ),
    )

    language: Language

    kind: SymbolKind

    name: str = Field(..., description="Simple (unqualified) symbol name")

    fully_qualified_name: str = Field(
        ...,
        description="Fully-qualified name (package/namespace + type + member)",
    )

    file_path: str = Field(
        ...,
        description="Relative path of the source file from the repository root",
    )

    range: SourceRange

    modifiers: List[str] = Field(
        default_factory=list,
        description="e.g. ['public', 'static', 'final'] or ['public', 'async']",
    )

    annotations: List[AnnotationInfo] = Field(
        default_factory=list,
        description="Java annotations or C# attributes attached to this symbol",
    )

    docstring: Optional[str] = Field(
        default=None,
        description="Javadoc (Java) or XML doc comment (C#) text",
    )

    parent_symbol_id: Optional[str] = Field(
        default=None,
        description="``symbol_id`` of the enclosing symbol (class for a method, etc.)",
    )

    signature: Optional[MethodSignature] = Field(
        default=None,
        description="Present only when ``kind`` is METHOD or CONSTRUCTOR",
    )

    property_accessors: Optional[PropertyAccessors] = Field(
        default=None,
        description="Present only when ``kind`` is PROPERTY (C#)",
    )

    field_type: Optional[str] = Field(
        default=None,
        description="Present when ``kind`` is FIELD or PROPERTY — the declared type",
    )

    dependencies: List[str] = Field(
        default_factory=list,
        description="FQNs of symbols this node directly depends on",
    )

    # Inheritance / implementation
    extends: Optional[str] = Field(
        default=None,
        description="FQN of the base class (Java extends / C# base class)",
    )
    implements: List[str] = Field(
        default_factory=list,
        description="FQNs of implemented interfaces",
    )


# ---------------------------------------------------------------------------
# File-level index
# ---------------------------------------------------------------------------

class ImportInfo(BaseModel):
    """A single import (Java) or using directive (C#)."""

    name: str = Field(..., description="The imported name or namespace")
    is_wildcard: bool = Field(
        default=False, description="True for Java wildcard imports (``import x.y.*``)"
    )
    is_static: bool = Field(
        default=False,
        description="True for Java static imports or C# ``using static``",
    )
    alias: Optional[str] = Field(
        default=None,
        description="C# using alias name (``using Alias = Namespace.Type``)",
    )


class FileIndex(BaseModel):
    """Metadata extracted from a single source file."""

    file_path: str = Field(
        ..., description="Relative path from repository root"
    )
    language: Language
    package_or_namespace: Optional[str] = Field(
        default=None,
        description="Java package or C# namespace declared in this file",
    )
    imports: List[ImportInfo] = Field(
        default_factory=list,
        description="Import / using directives declared in this file",
    )
    symbols: List[ASTSymbolNode] = Field(
        default_factory=list,
        description="All AST symbols extracted from this file",
    )


# ---------------------------------------------------------------------------
# Repository-level index (top-level IR)
# ---------------------------------------------------------------------------

class RelationshipEdge(BaseModel):
    """A directed edge in the hierarchy or call graph."""

    source: str = Field(..., description="Source symbol FQN / symbol_id")
    target: str = Field(..., description="Target symbol FQN / symbol_id")
    kind: str = Field(
        ...,
        description=(
            "Relationship type: 'extends', 'implements', 'calls', "
            "'uses_field', 'instantiates', 'contains'"
        ),
    )
    line: Optional[int] = Field(
        default=None, description="Line number where the relationship occurs"
    )


class DirectoryNode(BaseModel):
    """A node in the repository directory tree."""

    name: str
    path: str = Field(..., description="Relative path from repository root")
    is_directory: bool = True
    children: List[DirectoryNode] = Field(default_factory=list)
    language: Optional[Language] = Field(
        default=None, description="Detected language if this is a source file"
    )


class RepositoryIndex(BaseModel):
    """Top-level Intermediate Representation (IR) for an analysed repository.

    This is the **primary deliverable** of the Core Indexing Engine.  It is
    serialised to ``indexes/repository_index.json`` and consumed by:

    * Member 2 — Knowledge Graph builder (``graph.json``)
    * Hierarchical Chunker — 6-tier taxonomy construction
    * HTML Renderer — symbol cross-linking
    """

    repository_name: str
    repository_path: str = Field(
        ..., description="Absolute path to the analysed repository"
    )
    languages: List[Language] = Field(
        default_factory=list,
        description="Languages detected in the repository",
    )
    directory_tree: Optional[DirectoryNode] = Field(
        default=None,
        description="Repository directory structure tree",
    )
    files: List[FileIndex] = Field(
        default_factory=list,
        description="Per-file indexes produced by the language parsers",
    )
    symbols: List[ASTSymbolNode] = Field(
        default_factory=list,
        description="Flattened list of all symbols across all files",
    )
    relationships: List[RelationshipEdge] = Field(
        default_factory=list,
        description="All inter-symbol relationships (inheritance, calls, …)",
    )


# Allow recursive DirectoryNode
DirectoryNode.model_rebuild()
