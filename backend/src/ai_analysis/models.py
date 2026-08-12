"""Epic 3 output schema — taxonomy nodes, summaries and analysis results.

Implements the 6-tier taxonomy from ``docs/designs/hierarchical-prompting-chunking.md``
§1 and the analysis artefact consumed by the Knowledge Graph builder (Epic 2) and
the HTML Renderer (Epic 4).

Requirements
------------
* FR-13  — Hierarchical AST chunking along the 6-tier taxonomy
* US-3.3 — Architecture summaries
* US-3.4 — Module summaries
* US-3.5 — Token accounting per prompt
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ai_analysis.ir_models import Language


class Tier(int, Enum):
    """The 6-tier code taxonomy.

    Ordered so that ``Tier.METHOD > Tier.CLASS``, which lets the summarizer sort
    descending to walk bottom-up::

        Repository → Module → Container → Component → Class → Method
    """

    REPOSITORY = 1
    MODULE = 2
    CONTAINER = 3
    COMPONENT = 4
    CLASS = 5
    METHOD = 6

    @property
    def label(self) -> str:
        return self.name.capitalize()

    @property
    def child_tier(self) -> Optional["Tier"]:
        return Tier(self.value + 1) if self.value < Tier.METHOD.value else None

    @property
    def parent_tier(self) -> Optional["Tier"]:
        return Tier(self.value - 1) if self.value > Tier.REPOSITORY.value else None


class TaxonomyNode(BaseModel):
    """A single node in the 6-tier tree.

    Tiers 5 (Class) and 6 (Method) map onto AST symbols and carry a
    ``symbol_id``.  Tiers 1–4 are structural groupings and do not.
    """

    node_id: str = Field(
        ...,
        description="Stable identifier, unique across the tree. FQN for Class/Method tiers.",
    )
    tier: Tier
    name: str = Field(..., description="Display name, unqualified")
    symbol_id: Optional[str] = Field(
        default=None,
        description="Backing AST symbol; present for CLASS and METHOD tiers only",
    )
    path: Optional[str] = Field(
        default=None,
        description="Filesystem path for Module/Container tiers, source file for Class/Method",
    )
    language: Optional[Language] = None
    children: List["TaxonomyNode"] = Field(default_factory=list)

    # Provenance — how this node's tier was determined.  Lets the report show
    # which tiers came from Epic 1 and which Epic 3 had to infer.
    derived_by: str = Field(
        default="index",
        description="'index' when read from structure_overview.json, 'heuristic' when inferred",
    )
    marker_file: Optional[str] = Field(
        default=None,
        description="Build file that identified a Container (pom.xml, *.csproj, …)",
    )

    def walk(self):
        """Yield this node and every descendant, depth-first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def nodes_at(self, tier: Tier) -> List["TaxonomyNode"]:
        """All descendants (including self) at the given tier."""
        return [n for n in self.walk() if n.tier is tier]

    def find(self, node_id: str) -> Optional["TaxonomyNode"]:
        for node in self.walk():
            if node.node_id == node_id:
                return node
        return None

    @property
    def descendant_count(self) -> int:
        return sum(1 for _ in self.walk()) - 1


TaxonomyNode.model_rebuild()


class TaxonomyTree(BaseModel):
    """The complete 6-tier tree for one repository."""

    repository_name: str
    repository_path: str
    root: TaxonomyNode
    provider: str = Field(
        ...,
        description="Which TaxonomyProvider built this tree ('index' or 'heuristic')",
    )

    def nodes_at(self, tier: Tier) -> List[TaxonomyNode]:
        return self.root.nodes_at(tier)

    def bottom_up(self) -> List[TaxonomyNode]:
        """Every node ordered deepest tier first — the summarization order.

        Guarantees a node's children are all yielded before the node itself,
        which is what makes bottom-up aggregation possible in a single pass.
        """
        return sorted(self.root.walk(), key=lambda n: -n.tier.value)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

class TokenReport(BaseModel):
    """Token accounting for a single prompt — the evidence for US-3.5's DoD."""

    node_id: str
    tier: Tier
    estimated_tokens: int = Field(..., description="Pre-flight count from tokens.count_tokens")
    actual_tokens: Optional[int] = Field(
        default=None,
        description="Ground truth from Ollama's prompt_eval_count, when available",
    )
    tool_overhead_tokens: int = Field(
        default=0,
        description=(
            "Tokens spent on tool schemas the backend renders into the prompt. "
            "Included in estimated_tokens; tracked separately because it is "
            "invisible in the prompt string itself."
        ),
    )
    budget: int = Field(default=2000, description="Ceiling enforced for this prompt")
    was_degraded: bool = Field(
        default=False,
        description="True when the skeleton had to be trimmed to fit the budget",
    )

    elapsed_seconds: Optional[float] = Field(
        default=None,
        exclude=True,
        description=(
            "Wall-clock generation time, used to check the <10s-per-module NFR. "
            "Excluded from serialization: it varies run to run, and product.md "
            "requires identical repository states to produce identical output. "
            "Timings are reported on the console and in the live test suite "
            "instead of being baked into the documentation artefact."
        ),
    )

    @property
    def within_budget(self) -> bool:
        return self.estimated_tokens <= self.budget


class SummaryNode(BaseModel):
    """A generated summary attached to one taxonomy node."""

    node_id: str
    tier: Tier
    name: str
    summary: str
    generated_by: str = Field(
        ...,
        description="'llm' when a model produced it, 'structural' for the no-LLM fallback",
    )
    referenced_symbols: List[str] = Field(
        default_factory=list,
        description="FQNs the summary mentions that resolve against the symbol registry",
    )
    tokens: Optional[TokenReport] = None


class ContentSection(BaseModel):
    """One of the four wiki content areas (``docs/epics.md`` Epic 3 scope)."""

    key: str = Field(..., description="'tech' | 'tests' | 'architecture' | 'modules'")
    title: str
    body: str
    facts: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Structural evidence backing the prose, e.g. detected frameworks",
    )
    generated_by: str = "structural"


class AnalysisResult(BaseModel):
    """The Epic 3 deliverable, written to ``analysis/summaries.json``.

    Consumed by Epic 2 (folded into ``graph.json``) and Epic 4 (rendered into
    ``wiki/``).
    """

    repository_name: str
    repository_path: str
    model: Optional[str] = Field(default=None, description="Ollama model used, if any")
    llm_enabled: bool = False
    taxonomy: TaxonomyTree
    summaries: List[SummaryNode] = Field(default_factory=list)
    content: List[ContentSection] = Field(default_factory=list)
    token_reports: List[TokenReport] = Field(default_factory=list)

    def summary_for(self, node_id: str) -> Optional[SummaryNode]:
        for s in self.summaries:
            if s.node_id == node_id:
                return s
        return None

    @property
    def max_prompt_tokens(self) -> int:
        """Largest prompt generated during this run — the US-3.5 acceptance number."""
        return max((r.estimated_tokens for r in self.token_reports), default=0)

    @property
    def budget_violations(self) -> List[TokenReport]:
        return [r for r in self.token_reports if not r.within_budget]
