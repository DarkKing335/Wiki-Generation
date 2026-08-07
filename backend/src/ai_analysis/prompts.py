"""Prompt construction for local SLMs (FR-15, US-3.5).

Implements the four-block prompt format specified in
``docs/designs/hierarchical-prompting-chunking.md`` §7::

    ┌──────────────────────────────────────────────────────────────┐
    │ SYSTEM PROMPT                                                │
    ├──────────────────────────────────────────────────────────────┤
    │ TARGET CONTEXT (Level 4: Component)                          │
    ├──────────────────────────────────────────────────────────────┤
    │ STRUCTURAL SKELETON (from structure_overview.json)           │
    ├──────────────────────────────────────────────────────────────┤
    │ TASK INSTRUCTION                                             │
    └──────────────────────────────────────────────────────────────┘

Word limits tighten as the tier deepens: a method needs a sentence, a repository
needs a paragraph.  Keeping outputs short matters twice over — it bounds
generation time against the <10s-per-module NFR, and it keeps the *next* tier's
aggregating prompt small, since that prompt is built from these outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ai_analysis.models import Tier

SYSTEM_PROMPT = (
    "You are an expert software architect analyzing a Java/C# codebase. "
    "You describe code precisely and factually, using only the structural "
    "information provided. Never invent class, method, or package names that "
    "do not appear in the input."
)

#: Maximum words requested per tier.
WORD_LIMITS: Dict[Tier, int] = {
    Tier.METHOD: 40,
    Tier.CLASS: 60,
    Tier.COMPONENT: 100,
    Tier.CONTAINER: 100,
    Tier.MODULE: 120,
    Tier.REPOSITORY: 200,
}

#: Rough tokens-per-word for English prose, plus headroom to finish a sentence.
_TOKENS_PER_WORD = 1.4
_COMPLETION_HEADROOM = 1.3


def completion_limit(tier: Tier) -> int:
    """Generation cap for *tier*, derived from its word limit.

    Generation time is dominated by tokens produced, not tokens read.  Leaving a
    flat, generous cap in place lets the model ramble well past the word limit
    the prompt requested, which is the single largest contributor to per-node
    latency against the <10s target in ``docs/product.md``.
    """
    return int(WORD_LIMITS[tier] * _TOKENS_PER_WORD * _COMPLETION_HEADROOM) + 16

#: What each tier is being asked to describe.
TASK_INSTRUCTIONS: Dict[Tier, str] = {
    Tier.METHOD: (
        "Summarize what this method does and what it operates on. "
        "State its responsibility, not its implementation steps."
    ),
    Tier.CLASS: (
        "Summarize the responsibility of this type. Note its architectural role "
        "if the annotations or attributes indicate one (controller, service, "
        "repository, entity, test)."
    ),
    Tier.COMPONENT: (
        "Summarize the responsibility of this component (package or namespace) "
        "based on the types it contains."
    ),
    Tier.CONTAINER: (
        "Summarize what this deployable unit does, based on the components it "
        "contains. Note what kind of application it appears to be."
    ),
    Tier.MODULE: (
        "Summarize this module's business or domain responsibility, based on the "
        "containers it groups."
    ),
    Tier.REPOSITORY: (
        "Summarize the overall architecture of this repository: its purpose, its "
        "major modules, and how they relate."
    ),
}

#: Label for the skeleton block — code-derived at tiers 5-6, summary-derived above.
_SKELETON_LABELS: Dict[Tier, str] = {
    Tier.METHOD: "STRUCTURAL SKELETON (AST method signature)",
    Tier.CLASS: "STRUCTURAL SKELETON (AST type declaration)",
}
_AGGREGATE_LABEL = "CHILD SUMMARIES"


@dataclass
class Prompt:
    """A rendered prompt, split into the parts a chat API expects."""

    system: str
    user: str
    tier: Tier
    node_id: str
    ancestry: List[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """System and user text combined — what token counting measures."""
        return f"{self.system}\n\n{self.user}"


def format_ancestry(ancestry: Sequence[str], tiers: Sequence[Tier]) -> str:
    """Render the breadcrumb line: ``Module: billing | Container: payment-service``.

    Mirrors the dynamic breadcrumbs the HTML wiki renders
    (``docs/designs/html-wiki-storage.md`` §3), so the model sees the same
    positional context a reader eventually will.
    """
    return " | ".join(
        f"{tier.label}: {name}" for name, tier in zip(ancestry, tiers) if name
    )


def build_prompt(
    tier: Tier,
    name: str,
    skeleton: str,
    node_id: str,
    *,
    ancestry: Optional[Sequence[str]] = None,
    ancestry_tiers: Optional[Sequence[Tier]] = None,
    language: Optional[str] = None,
    extra_context: Optional[str] = None,
    word_limit: Optional[int] = None,
) -> Prompt:
    """Assemble the four-block prompt for one taxonomy node.

    Parameters
    ----------
    skeleton:
        The chunk text — an AST skeleton at tiers 5-6, a child-summary digest above.
    extra_context:
        Optional lazily loaded source, appended as a clearly marked block so the
        model can tell implementation detail from structure.
    """
    limit = word_limit or WORD_LIMITS[tier]
    blocks: List[str] = []

    # --- TARGET CONTEXT ---
    context_lines = [f"TARGET CONTEXT (Level {tier.value}: {tier.label})"]
    breadcrumb = (
        format_ancestry(ancestry, ancestry_tiers)
        if ancestry and ancestry_tiers
        else ""
    )
    if breadcrumb:
        context_lines.append(breadcrumb)
    context_lines.append(f"{tier.label}: {name}")
    if language:
        context_lines.append(f"Language: {language}")
    blocks.append("\n".join(context_lines))

    # --- STRUCTURAL SKELETON / CHILD SUMMARIES ---
    label = _SKELETON_LABELS.get(tier, _AGGREGATE_LABEL)
    blocks.append(f"{label}\n{skeleton}")

    if extra_context:
        blocks.append(
            "SOURCE EXCERPT (requested for algorithmic detail)\n" + extra_context
        )

    # --- TASK INSTRUCTION ---
    blocks.append(
        "TASK INSTRUCTION\n"
        f"{TASK_INSTRUCTIONS[tier]}\n"
        f"Answer in under {limit} words. "
        "Write plain prose, no headings, no bullet points, no preamble."
    )

    return Prompt(
        system=SYSTEM_PROMPT,
        user="\n\n".join(blocks),
        tier=tier,
        node_id=node_id,
        ancestry=list(ancestry or []),
    )
