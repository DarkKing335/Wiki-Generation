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

## ADR-007 — Fixed Documentation and Toolset

**Context**

Unlimited documentation types or extensible tool systems would significantly increase project complexity.

**Decision**

Limit the generated output to four documentation files and maintain a fixed set of repository analysis tools.

**Consequences**

- Predictable behavior.
- Smaller maintenance surface.
- Easier testing and documentation.

---

## ADR Summary

| ADR     | Decision                                 |
| ------- | ---------------------------------------- |
| ADR-001 | Repository structure organization        |
| ADR-002 | Template-based documentation             |
| ADR-003 | Repository analysis before documentation |
| ADR-004 | Knowledge graph stored in `graph.json`   |
| ADR-005 | Complete repository re-analysis          |
| ADR-006 | Optional local or remote LLM             |
| ADR-007 | Fixed documentation and analysis toolset |
