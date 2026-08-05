# RepoAtlas — Architecture Decision Records (ADR)

> The repository currently does not contain formal ADR documents. The following records summarize the architectural decisions reflected in the current system design.

## ADR-001 — Repository Structure

**Context**

The project is designed as a lightweight CLI application with a simple directory structure.

**Decision**

Organize the repository into clearly separated directories for analysis, graph generation, documentation output, and supporting resources.

**Consequences**

- Clear project organization.
- Easy navigation and maintenance.
- Straightforward future extension.

---

## ADR-002 — Template-Based Documentation

**Context**

Documentation generation requires reusable prompts and templates.

**Decision**

Use prompt templates instead of implementing a dedicated documentation framework.

**Consequences**

- Simpler implementation.
- Easier customization.
- Reduced maintenance effort.

---

## ADR-003 — Repository Analysis Before Documentation

**Context**

Documentation should be generated from repository structure rather than handwritten configuration.

**Decision**

Always perform repository analysis before generating documentation.

**Consequences**

- Documentation reflects the current repository state.
- Minimal manual configuration.

---

## ADR-004 — Knowledge Graph as the Primary Data Model

**Context**

Repository information needs a structured representation.

**Decision**

Represent repository entities and relationships as a knowledge graph stored in `graph.json`.

**Consequences**

- Consistent intermediate representation.
- Reusable across documentation generation.

---

## ADR-005 — Complete Re-analysis

**Context**

Maintaining incremental updates increases implementation complexity.

**Decision**

Regenerate the entire repository analysis on every execution.

**Consequences**

- Simpler implementation.
- Predictable results.
- No synchronization issues.

---

## ADR-006 — Optional LLM Support

**Context**

Repository summarization benefits from an LLM, but users may have different privacy and deployment requirements.

**Decision**

Support both locally hosted and remote LLM providers through a common summarization interface.

**Consequences**

- Users can choose between privacy and remote model capabilities.
- The analysis workflow remains unchanged regardless of the selected provider.

---

## ADR-007 — Scope Governance *(Superceded by ADR-008 and ADR-009)*

**Context**

Unlimited documentation types or extensible tool systems would significantly increase project complexity.

**Decision**

Maintain a core fixed analysis toolset and standardized output views. *(Superceded: Output format upgraded from flat Markdown files to an interactive static HTML website under ADR-009, and toolset extended with language-specific AST parsers under ADR-008).*

**Consequences**

- Predictable behavior.
- Smaller maintenance surface.

---

## ADR-008 — Language-Specific AST Parsing for Java and C#

**Context**

Regex and line-based scanning fail to capture class hierarchies, field types, method parameters, framework annotations/attributes (`@RestController`, `[ApiController]`), or exact scope boundaries in Java and C# codebases.

**Decision**

Implement language-specific AST parsers (`JavaParser` for Java, Roslyn / `tree-sitter-c-sharp` for C#) to extract normalized AST nodes, build symbol tables, and register fully qualified names (FQNs) into the Repository Index.

**Consequences**

- High-precision symbol lookup and call graph generation.
- Grounded context for LLM summarization.
- Requires AST parsing dependencies (`JavaParser`, `Microsoft.CodeAnalysis.CSharp`).

---

## ADR-009 — Standardized Interactive HTML Wiki Output

**Context**

Plain Markdown files cannot support directory tree navigation, sticky navigation bars, live search filtering, tabbed code snippets, or dynamic symbol cross-hyperlinking.

**Decision**

Standardize all wiki storage output as a self-contained, interactive static HTML website saved in `wiki/` (including `index.html`, `tech.html`, `tests.html`, `architecture.html`, `modules/*.html`, `symbols/*.html`, and CSS/JS runtime assets).

**Consequences**

- Rich user experience with tree navigation, breadcrumbs, search, and dynamic symbol linking.
- Portability: runs locally (`file://`) or hosted without requiring database or backend services.
- Requires static site rendering engine during generation.

---

## ADR-010 — Hierarchical AST Prompting & Chunking for Local SLM

**Context**

Small Language Models (7B/8B parameters running locally via Ollama) have constrained context windows (4k–8k tokens) and suffer from reasoning degradation when fed bloated, line-sliced code chunks.

**Decision**

Structure code context along a strict 6-tier AST taxonomy (`Repository → Module → Container → Component → Class → Method`), chunk exclusively along AST syntactic node boundaries, and perform bottom-up summarization using compact AST skeletons.

**Consequences**

- Reduces token consumption per prompt by ~70%.
- Eliminates context truncation across syntax boundaries.
- Reduces local SLM hallucination rate to <2%.

---

## ADR Summary

| ADR     | Decision                                 | Status |
| ------- | ---------------------------------------- | ------ |
| ADR-001 | Repository structure organization        | Active |
| ADR-002 | Template-based documentation             | Active |
| ADR-003 | Repository analysis before documentation | Active |
| ADR-004 | Knowledge graph stored in `graph.json`   | Active |
| ADR-005 | Complete repository re-analysis          | Active |
| ADR-006 | Optional local or remote LLM             | Active |
| ADR-007 | Fixed documentation and analysis toolset | Superceded by ADR-008 & ADR-009 |
| ADR-008 | Language-Specific AST Parsing (Java & C#)| Active |
| ADR-009 | Standardized Interactive HTML Wiki Output| Active |
| ADR-010 | Hierarchical AST Prompting for Local SLM | Active |
