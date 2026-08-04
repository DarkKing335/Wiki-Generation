# RepoAtlas — Product

## 1. Product Vision

RepoAtlas is a lightweight CLI tool that analyzes a single repository and generates exactly four wiki documents (**Tech**, **Tests**, **Architecture**, and **Modules**) using a fixed analysis toolset and an optional LLM that can run locally or through a remote API.

## 2. Functional Requirements

| ID    | Requirement                | Description                                                                                                          | Status |
| ----- | -------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------ |
| FR-1  | Repository Input           | Accept a local repository path or Git URL for a single analysis.                                                     | —      |
| FR-2  | Repository Analysis        | Scan the repository structure, read source files, and build an import graph.                                         | —      |
| FR-3  | LLM Support                | Support both local and remote LLM providers through configuration.                                                   | —      |
| FR-4  | Tech Documentation         | Generate a **Tech** document containing programming languages, frameworks, dependencies, and build/run instructions. | —      |
| FR-5  | Tests Documentation        | Generate a **Tests** document describing available test suites and how to execute them.                              | —      |
| FR-6  | Architecture Documentation | Generate an **Architecture** document describing repository layers and component relationships.                      | —      |
| FR-7  | Modules Documentation      | Generate a **Modules** document describing repository modules and their responsibilities.                            | —      |
| FR-8  | Knowledge Graph            | Build a knowledge graph and save it as `graph.json`.                                                                 | —      |
| FR-9  | Operation Without LLM      | Continue generating documentation from structural analysis even when no LLM is configured.                           | —      |
| FR-10 | Full Re-analysis           | Regenerate the knowledge graph and documentation whenever the analysis is executed again.                            | —      |

## 3. Non-Functional Requirements

- **Simplicity** — The system consists of a single CLI command, a fixed analysis workflow, and four generated documents.
- **Privacy** — Local LLM execution is supported to avoid sending repository code to external services.
- **Reproducibility** — Identical repository states should produce consistent knowledge graphs and documentation.
- **Portability** — The application runs entirely on the user's machine without requiring backend services.

## 4. Personas

| Persona                   | Goal                                                                                                             |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Software Engineer**     | Understand an unfamiliar repository by generating documentation with a single command.                           |
| **Repository Maintainer** | Regenerate project documentation whenever the repository changes while keeping source code on the local machine. |

## 5. Core Capabilities

| Capability          | Implementation                                      |
| ------------------- | --------------------------------------------------- |
| Repository Input    | CLI command                                         |
| Structural Analysis | `scan_structure`, `read_file`, `build_import_graph` |
| AI Summarization    | `summarize`                                         |
| Knowledge Graph     | `graph.json`                                        |
| Wiki Generation     | Tech, Tests, Architecture, Modules                  |

## 6. Summary

RepoAtlas focuses on a simple workflow: analyze one repository, build a knowledge graph, optionally enrich it with an LLM, and generate four wiki documents. The product intentionally maintains a fixed scope with a single CLI interface, a small analysis toolset, and predictable outputs.
