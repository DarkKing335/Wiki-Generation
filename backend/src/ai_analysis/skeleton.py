"""AST skeleton rendering — compact structural text in place of source code.

This module is the mechanism behind ADR-010's central claim.  Instead of feeding
a 180-line class into a 7B model, the summarizer feeds a ~90-token skeleton
carrying every architecturally meaningful fact:

* annotations / attributes  (``@Service``, ``[ApiController]``) — what the type *is*
* inheritance and interfaces — how it fits the design
* field and property types — what it depends on
* method signatures — what it does
* docstrings — the author's own stated intent

What is deliberately omitted is the method *body*: the algorithm.  A component
summary never needs it, and when it genuinely does, the chunker fetches the exact
lines lazily (``docs/designs/ast-parser-design.md`` §8).

Requirements
------------
* FR-15  — Compact AST skeletons to enforce prompt token limits
* US-3.5 — Skeletons instead of raw function bodies

**Invariant:** no function in this module ever reads a source file.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from ai_analysis.ir_models import (
    ASTSymbolNode,
    RepositoryIndex,
    SymbolKind,
)

INDENT = "  "

#: Docstrings longer than this are truncated when rendering at scale.
DEFAULT_DOC_CHARS = 160


def _short_type(type_name: Optional[str]) -> str:
    """Strip package qualification for readability: ``java.lang.String`` → ``String``.

    Fully-qualified names cost tokens without adding meaning inside a skeleton
    that already states its own package.
    """
    if not type_name:
        return "void"
    # Preserve generics: List<com.x.Y> → List<Y>
    if "<" in type_name:
        base, _, rest = type_name.partition("<")
        inner = rest.rstrip(">")
        parts = [_short_type(p.strip()) for p in inner.split(",")] if inner else []
        return f"{_short_type(base)}<{', '.join(parts)}>"
    if type_name.endswith("[]"):
        return _short_type(type_name[:-2]) + "[]"
    return type_name.rsplit(".", 1)[-1]


def _condense(text: Optional[str], limit: int = DEFAULT_DOC_CHARS) -> str:
    """Collapse a docstring to a single line, truncated to *limit* characters."""
    if not text:
        return ""
    flat = " ".join(text.split())
    if limit and len(flat) > limit:
        flat = flat[: limit - 1].rstrip() + "…"
    return flat


def render_annotations(symbol: ASTSymbolNode) -> str:
    """Render annotations as ``[@Service @Transactional]``, or empty string."""
    if not symbol.annotations:
        return ""
    rendered = []
    for annotation in symbol.annotations:
        if annotation.arguments:
            args = ", ".join(f"{k}={v}" for k, v in annotation.arguments.items())
            rendered.append(f"@{annotation.name}({args})")
        else:
            rendered.append(f"@{annotation.name}")
    return "[" + " ".join(rendered) + "]"


def render_signature(symbol: ASTSymbolNode) -> str:
    """Render a callable's signature: ``processTransaction(TransactionDto dto) -> PaymentResult``."""
    signature = symbol.signature
    if signature is None:
        return f"{symbol.name}()"

    params = ", ".join(
        " ".join(filter(None, [
            " ".join(p.modifiers) if p.modifiers else "",
            _short_type(p.type),
            p.name,
        ])).strip()
        for p in signature.parameters
    )

    text = f"{symbol.name}({params})"

    if symbol.kind is not SymbolKind.CONSTRUCTOR and signature.return_type:
        text += f" -> {_short_type(signature.return_type)}"
    if signature.is_async:
        text = "async " + text
    if signature.thrown_exceptions:
        text += " throws " + ", ".join(_short_type(e) for e in signature.thrown_exceptions)

    return text


def render_member(symbol: ASTSymbolNode) -> str:
    """Render a field or property: ``stripeClient : StripeClient``."""
    text = f"{symbol.name} : {_short_type(symbol.field_type)}"
    accessors = symbol.property_accessors
    if accessors:
        parts = [
            name
            for name, present in (
                ("get", accessors.has_getter),
                ("set", accessors.has_setter),
                ("init", accessors.has_init),
            )
            if present
        ]
        if parts:
            text += " { " + "; ".join(parts) + "; }"
    return text


def render_class_skeleton(
    symbol: ASTSymbolNode,
    index: RepositoryIndex,
    *,
    include_private: bool = True,
    include_docstrings: bool = True,
    doc_chars: int = DEFAULT_DOC_CHARS,
    indent: int = 0,
) -> str:
    """Render one type declaration and its members as skeleton text.

    Parameters
    ----------
    include_private:
        When ``False``, private members are omitted.  The first degradation step
        applied by :mod:`ai_analysis.tokens` when a prompt exceeds budget.
    include_docstrings:
        When ``False``, docstrings are omitted entirely.  The second degradation
        step.
    """
    pad = INDENT * indent
    lines: List[str] = []

    header = f"{pad}{symbol.kind.value.title()}: {symbol.name}"
    annotations = render_annotations(symbol)
    if annotations:
        header += f"  {annotations}"
    if symbol.extends:
        header += f"  extends {_short_type(symbol.extends)}"
    if symbol.implements:
        header += "  implements " + ", ".join(_short_type(i) for i in symbol.implements)
    lines.append(header)

    if include_docstrings:
        doc = _condense(symbol.docstring, doc_chars)
        if doc:
            lines.append(f"{pad}{INDENT}Doc: {doc}")

    children = index.children_of(symbol.symbol_id)
    if not include_private:
        children = [c for c in children if "private" not in c.modifiers]

    members = [c for c in children if c.is_member]
    if members:
        lines.append(f"{pad}{INDENT}Fields:")
        for member in sorted(members, key=lambda s: s.range.start_line):
            lines.append(f"{pad}{INDENT * 2}- {render_member(member)}")

    callables = [c for c in children if c.is_callable]
    if callables:
        lines.append(f"{pad}{INDENT}Methods:")
        for callable_symbol in sorted(callables, key=lambda s: s.range.start_line):
            entry = f"{pad}{INDENT * 2}* {render_signature(callable_symbol)}"
            annotations = render_annotations(callable_symbol)
            if annotations:
                entry += f"  {annotations}"
            lines.append(entry)

            if include_docstrings:
                doc = _condense(callable_symbol.docstring, doc_chars)
                if doc:
                    lines.append(f"{pad}{INDENT * 3}Doc: {doc}")

    return "\n".join(lines)


def render_method_skeleton(
    symbol: ASTSymbolNode,
    index: RepositoryIndex,
    *,
    include_docstrings: bool = True,
    doc_chars: int = DEFAULT_DOC_CHARS,
) -> str:
    """Render a single callable, with the type that declares it for context."""
    lines: List[str] = []

    parent = index.build_registry().get(symbol.parent_symbol_id or "")
    if parent is not None:
        lines.append(f"Declared in: {parent.kind.value.title()} {parent.name}")

    entry = f"* {render_signature(symbol)}"
    annotations = render_annotations(symbol)
    if annotations:
        entry += f"  {annotations}"
    lines.append(entry)

    if include_docstrings:
        doc = _condense(symbol.docstring, doc_chars)
        if doc:
            lines.append(f"{INDENT}Doc: {doc}")

    if symbol.dependencies:
        deps = ", ".join(_short_type(d) for d in symbol.dependencies)
        lines.append(f"{INDENT}Uses: {deps}")

    lines.append(f"{INDENT}Source: {symbol.file_path}:{symbol.range.start_line}-{symbol.range.end_line}")

    return "\n".join(lines)


def render_component_skeleton(
    types: Sequence[ASTSymbolNode],
    index: RepositoryIndex,
    *,
    include_private: bool = False,
    include_docstrings: bool = True,
    doc_chars: int = DEFAULT_DOC_CHARS,
) -> str:
    """Render every type in a component (package / namespace).

    Private members are excluded by default here: at component level the caller
    is describing responsibility, not implementation.
    """
    return "\n".join(
        render_class_skeleton(
            t,
            index,
            include_private=include_private,
            include_docstrings=include_docstrings,
            doc_chars=doc_chars,
        )
        for t in types
    )


def render_summary_digest(entries: Iterable[tuple[str, str]], *, doc_chars: int = 0) -> str:
    """Render child summaries for an aggregating prompt.

    Used at tiers 1–4, where the model consumes the *summaries* of the level
    below rather than any code::

        - payment-service: Handles card charges via Stripe…
        - invoice-service: Renders invoice PDFs…
    """
    lines = []
    for name, summary in entries:
        text = _condense(summary, doc_chars) if doc_chars else " ".join(summary.split())
        lines.append(f"- {name}: {text}")
    return "\n".join(lines)
