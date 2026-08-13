# RepoAtlas — Project Understanding Map

> **Purpose of this document group:** Answer the question  
> *"How does RepoAtlas understand a repository being analyzed?"*  
>
> Not just a description of source code — but an explicit trace of how the system moves from **source code → structure → AST → relationships → modules/components → architecture → summaries → Wiki**.

---

## What does RepoAtlas understand?

```
Repository (local path or Git URL)
│
├── Source
│   ├── Files (.java, .cs)
│   ├── Directory Structure
│   ├── AST Nodes (Classes, Methods, Fields, Annotations…)
│   └── Metadata (FQNs, modifiers, docstrings, line ranges)
│
├── Relationships
│   ├── Imports / Using directives
│   ├── Inheritance (extends, implements)
│   ├── Calls (method invocations)
│   ├── Field usage (uses_field)
│   └── Containment (parent → child)
│
├── Components
│   (Packages / Namespaces inferred from AST symbol grouping)
│
├── Modules
│   (Business-domain groupings inferred from structure + AI)
│
├── Architecture
│   (Layers / tiers inferred from package structure + annotation patterns + AI summarization)
│
└── Project Documentation (Wiki)
    ├── Tech         → wiki/tech.html
    ├── Tests        → wiki/tests.html
    ├── Architecture → wiki/architecture.html
    └── Modules      → wiki/modules/*.html + wiki/symbols/*.html
```

---

## Document Index

| File | Purpose | Primary Audience |
|------|---------|-----------------|
| [architecture.md](./architecture.md) | System layers, component interactions, end-to-end flow | All members |
| [modules.md](./modules.md) | Module definitions, responsibilities, dependencies | Member 1 + Member 2 |
| [components.md](./components.md) | Component-level deep-dive (scanner, parsers, indexer, etc.) | Member 1 + Member 2 |
| [data-flow.md](./data-flow.md) | Data schemas, formats, and pipeline flow step by step | All members |

---

## Team Ownership Map

### Member 1 — Source Understanding

**Scope:** How raw source code becomes structured, queryable metadata.

```
Source Files (.java / .cs)
    → RepositoryScanner          (scanner.py)
    → JavaParser / CSharpParser  (parsers/)
    → ASTSymbolNode              (models.py)
    → FileIndex / RepositoryIndex
    → repository_index.json + structure_overview.json
```

**Primary documentation responsibilities:**
- [components.md](./components.md) — Scanner, Base Parser, JavaParser, CSharpParser, Indexer, IRGenerator sections
- [data-flow.md](./data-flow.md) — Steps 1–4 (Scan → Parse → Index → Export IR)

**User Stories:** US-1.1, US-1.2, US-1.3, US-1.4

---

### Member 2 — Relationship Understanding

**Scope:** How extracted AST metadata becomes a queryable knowledge graph of relationships.

```
repository_index.json  (from Member 1)
    → Knowledge Graph Builder
    → graph.json
    → Query Engine
    → Module / Architecture understanding
```

**Primary documentation responsibilities:**
- [modules.md](./modules.md) — Knowledge Graph section, relationship model
- [data-flow.md](./data-flow.md) — Step 5 (IR → Knowledge Graph)
- [architecture.md](./architecture.md) — Knowledge Graph layer description

**User Stories:** US-2.1, US-2.2, US-2.3

---

### Member 3 — AI Understanding

**Scope:** How structured knowledge is chunked and fed to an LLM to generate human-readable summaries.

```
structure_overview.json  (from Member 1)
+ graph.json             (from Member 2)
    → Hierarchical Chunker (6-tier taxonomy)
    → Local SLM / Remote LLM
    → Component Summaries
    → Module Summaries
    → Architecture Summary
    → (No-LLM fallback: structural summaries from AST symbol tables)
```

> **Key principle:** The LLM does **not** read the full repository.  
> It receives structured evidence (AST skeletons) and generates understanding from that.

**Primary documentation responsibilities:**
- [architecture.md](./architecture.md) — AI Analysis layer, LLM role
- [modules.md](./modules.md) — AI Analysis module section
- [components.md](./components.md) — Chunker, Summarizer sections

**User Stories:** US-3.1, US-3.2, US-3.3, US-3.4, US-3.5

---

### Member 4 — Wiki / End-to-End Understanding

**Scope:** How Project Understanding is rendered into a navigable, interactive HTML documentation site via CLI orchestration.

```
graph.json + AST summaries
    → HTML Template Compiler
    → Hyperlink Resolver
    → Static HTML Site Writer
    → wiki/ (index.html, tech.html, tests.html, architecture.html,
              modules/*.html, symbols/*.html)
```

**Primary documentation responsibilities:**
- [architecture.md](./architecture.md) — Wiki Generation layer, CLI Orchestration
- [data-flow.md](./data-flow.md) — Steps 7–8 (Summarization → Wiki)
- Overall end-to-end flow documentation

**User Stories:** US-4.1, US-4.2, US-4.3, US-4.4, US-4.5, US-4.6, US-5.1, US-5.2

---

## Implementation Status Summary

| Layer | Status |
|-------|--------|
| Git & Local Repository Scanner | ✅ **Implemented** (`backend/src/core_indexing/scanner.py`) |
| Java AST Parser | ✅ **Implemented** (`backend/src/core_indexing/parsers/java_parser.py`) |
| C# AST Parser | ✅ **Implemented** (`backend/src/core_indexing/parsers/csharp_parser.py`) |
| Unified IR Models | ✅ **Implemented** (`backend/src/core_indexing/models.py`) |
| Repository Indexer | ✅ **Implemented** (`backend/src/core_indexing/indexer.py`) |
| IR Generator | ✅ **Implemented** (`backend/src/core_indexing/ir_generator.py`) |
| Core Indexing CLI | ✅ **Implemented** (`backend/src/core_indexing/__main__.py`) |
| Knowledge Graph Builder | ✅ **Implemented** (`backend/src/knowledge_graph/builder.py`) |
| Graph Query Engine | ✅ **Implemented** (`backend/src/knowledge_graph/query.py`) |
| Hierarchical Chunker | ✅ **Implemented** (`backend/src/ai_analysis/chunker.py`) |
| Local SLM Summarizer | ✅ **Implemented** (`backend/src/ai_analysis/summarizer.py`) |
| No-LLM Fallback | ✅ **Implemented** (`backend/src/ai_analysis/llm/null.py`) |
| Wiki M3 HTML Renderer | ✅ **Implemented** (`backend/src/wiki_generation/renderer.py`) |
| Embedded Local AI Widget | ✅ **Implemented** (`backend/src/wiki_generation/templates/base.html`) |
| Full CLI Orchestration | ✅ **Implemented** (`backend/src/cli.py`) |
| Test Suite (289+ tests) | ✅ **Implemented** (`backend/tests/`) |


---

## Related Documents

| Document | Location |
|----------|----------|
| Project Vision | [docs/vision.md](../vision.md) |
| Executive Summary | [docs/executive-summary.md](../executive-summary.md) |
| System Overview | [docs/system-overview.md](../system-overview.md) |
| Overall Architecture | [docs/architecture.md](../architecture.md) |
| AST Parser Design | [docs/designs/ast-parser-design.md](../designs/ast-parser-design.md) |
| Hierarchical Chunking Design | [docs/designs/hierarchical-prompting-chunking.md](../designs/hierarchical-prompting-chunking.md) |
| HTML Wiki Storage Design | [docs/designs/html-wiki-storage.md](../designs/html-wiki-storage.md) |
| User Stories | [docs/user-stories.md](../user-stories.md) |
| Epics | [docs/epics.md](../epics.md) |
| ADRs | [docs/adrs.md](../adrs.md) |
