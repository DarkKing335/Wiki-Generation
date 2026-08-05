# RepoAtlas Documentation Index

## Document Map

| #   | Document                 | Content                                                                       |
| --- | ------------------------ | ----------------------------------------------------------------------------- |
| 1   | `vision.md`              | Vision, principles, HTML wiki standard, local-first LLM                      |
| 2   | `executive-summary.md`   | Intended system & data flow (authored design with AST & HTML rendering)       |
| 3   | `system-overview.md`     | Pipeline, tools (including AST parsers), local/remote LLM, HTML generation    |
| 4   | `architecture.md`        | System/component/module view, AST Engine, HTML Renderer, Hierarchical Chunker |
| 5   | `repository-analysis.md` | Structure, build, deps — AST parsers & static site output directory           |
| 6   | `product.md`             | FR/NFR (including FR-11 to FR-15), personas, capabilities                     |
| 7   | `epics.md`               | Epics 1–5 (updated with AST, Hierarchical SLM, and HTML Wiki scope)           |
| 8   | `user-stories.md`        | User stories per Epic (including US-1.3, US-1.4, US-3.5, US-4.5)              |
| 9   | `adrs.md`                | ADRs 001–010 (incorporating AST Parsing, HTML Output, & Hierarchical SLM)     |
| 10  | `designs/ast-parser-design.md` | Deep-dive Java & C# AST Parser Subsystem architecture and unified schema |
| 11  | `designs/html-wiki-storage.md` | Deep-dive HTML Static Wiki Site structure, UI components, & rendering pipeline |
| 12  | `designs/hierarchical-prompting-chunking.md` | Deep-dive 6-tier AST taxonomy & bottom-up Local SLM chunking strategy |

## Reading Order

1. `executive-summary.md` — facts + what's new in project.
2. `vision.md` + `system-overview.md` — intended design.
3. `repository-analysis.md` + `architecture.md` — as-built truth and component design.
4. `designs/ast-parser-design.md` + `designs/html-wiki-storage.md` + `designs/hierarchical-prompting-chunking.md` — technical design specs.
5. `epics.md` → `user-stories.md` — project backlog.
6. `adrs.md` — architectural decision records (ADR-001 through ADR-010).

## Guiding Constraint for This Version

Every design document in this set is written to keep RepoAtlas **deterministic, AST-grounded, and local-first**: utilizing language-specific parsers (Java & C#), generating a standardized interactive HTML wiki site, and leveraging hierarchical AST chunking for Local SLMs. Scope extensions are governed by explicit ADRs (ADR-008, ADR-009, ADR-010).
