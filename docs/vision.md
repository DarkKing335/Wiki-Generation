# RepoAtlas — Project Vision

## Purpose

RepoAtlas is a lightweight CLI tool that analyzes a single repository and generates a wiki that helps developers understand and maintain its source code.

## RepoAtlas in One Sentence

**RepoAtlas is a self-hostable CLI tool that analyzes a repository via language-specific AST parsers (Java & C#) and generates an interactive, multi-page static HTML wiki (covering Tech, Tests, Architecture, and Modules) from a knowledge graph, using a local SLM optimized via hierarchical AST chunking.**

## Core Principles

1. **Single-Shot Analysis** — One execution performs a complete analysis of the repository. No state is preserved between runs except the generated output files.
2. **File-Based Architecture** — The knowledge graph is stored as a single `graph.json` file.
3. **Full Re-analysis** — Repository changes are handled by running the analysis again rather than maintaining incremental updates.
4. **Model-Agnostic, Local-First** — The summarization model can run locally (for example through Ollama or another local inference server) or use a remote API. Local SLM execution is the default, while remote execution is optional.
5. **Template-Driven Analysis** — Repository-specific guidance is defined through prompt templates rather than a dedicated framework.
6. **Standardized HTML Output** — Every analysis generates a self-contained, interactive static HTML documentation website (`wiki/`) featuring navigation trees, breadcrumbs, search, and dynamic symbol cross-hyperlinks.
7. **Open Source and Self-Hosted** — The tool runs entirely on the user's machine and does not require any hosted backend services.
8. **AST-Grounded SLM Optimization** — Code context is chunked along syntactically valid AST node boundaries using a 6-tier taxonomy (`Repository → Module → Container → Component → Class → Method`), reducing token bloat and eliminating model hallucinations.

## Generated Wiki

Each execution generates a self-contained, interactive static HTML wiki website stored in `wiki/`.

| #   | View / Section    | Description                                                                              | HTML Deliverable |
| --- | ---------------- | ---------------------------------------------------------------------------------------- | ---------------- |
| 1   | **Tech**         | Programming languages, frameworks, dependencies, build process, and runtime environment. | `wiki/tech.html` |
| 2   | **Tests**        | Available test suites, test coverage, and instructions for running tests.                | `wiki/tests.html` |
| 3   | **Architecture** | High-level architecture, major layers, services, and structural dependency diagrams.     | `wiki/architecture.html` |
| 4   | **Modules**      | Detailed module purpose, container boundaries, component clusters, and AST symbol views. | `wiki/modules/*.html` & `wiki/symbols/*.html` |

For repositories with clear module separations, the Modules section renders specialized sub-pages for components, containers, and class symbol detail pages.

## Core Concepts

| Term                | Definition                                                                                                        |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Repository**      | The repository analyzed during a single execution, provided as a local directory or Git URL.                      |
| **AST Node**        | Language-specific syntactic representation of code elements (classes, methods, fields, annotations, docstrings).|
| **Repository Index**| Centralized symbol table mapping fully qualified names (FQNs), file locations, and AST relationships.            |
| **Knowledge Graph** | Relationships derived from the AST repository index and stored in `graph.json`.                                  |
| **Hierarchical Chunk**| Syntactically bound code context chunk structured along the 6-tier AST taxonomy for Local SLM processing.       |
| **Analysis Pass**   | A bounded set of local SLM calls guided by prompt skeletons and hierarchical chunking.                           |
| **Wiki Site**       | The generated static HTML website bundle in `wiki/` containing pages, search scripts, and CSS/JS assets.           |

## Out of Scope

The following capabilities are intentionally excluded:

- Multi-repository workspace management.
- Plugin systems, marketplaces, or framework registries.
- Agent orchestration or scheduling.
- Incremental refresh mechanisms.
- API, Gateway, or Control Plane services.
- Policy or guardrail engines for tool execution.

## Assumptions

- The input is a Git repository or a local project directory.
- A local or remote LLM is available for summarization. If no LLM is available, the tool still generates documentation from structural analysis, although Architecture and Modules descriptions will be limited.
- The tool executes entirely on the user's local machine.

## Summary

RepoAtlas analyzes a repository, builds a knowledge graph (`graph.json`), performs a bounded analysis using prompt templates and an optional LLM, and generates four wiki documents: **Tech**, **Tests**, **Architecture**, and **Modules**. The project intentionally maintains a focused scope with a single CLI workflow, a fixed toolset, and a fixed documentation output.
