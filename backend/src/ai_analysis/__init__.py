"""RepoAtlas AI Analysis Engine (Epic 3).

Hierarchical AST chunking and bottom-up summarization for local Small Language
Models.  Consumes the Intermediate Representation produced by the Core Indexing
Engine (Epic 1) and produces tier-by-tier natural-language summaries consumed by
the Knowledge Graph builder (Epic 2) and the HTML Renderer (Epic 4).

Requirements
------------
* FR-3   — Local SLM (default) and remote LLM support
* FR-9   — Operation without an LLM
* FR-13  — Hierarchical AST chunking along the 6-tier taxonomy
* FR-15  — Local SLM optimisation, prompts under 2,000 tokens
* US-3.1 – US-3.5

Reference documents
-------------------
* ``docs/designs/hierarchical-prompting-chunking.md`` — 6-tier taxonomy, prompting
* ``docs/designs/ast-parser-design.md`` §8 — lazy loading workflow
* ``docs/adrs.md`` ADR-010 — Hierarchical AST prompting for local SLM
"""

from __future__ import annotations

__version__ = "0.1.0"
