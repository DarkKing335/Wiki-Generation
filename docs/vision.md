# RepoAtlas — Project Vision

## Purpose

RepoAtlas is a lightweight CLI tool that analyzes a single repository and generates a wiki that helps developers understand and maintain its source code.

## RepoAtlas in One Sentence

**RepoAtlas is a self-hostable CLI tool that analyzes a repository and generates a four-part wiki (Tech, Tests, Architecture, and Modules) from a knowledge graph of its structure, using an LLM that can run locally or through a remote API.**

## Core Principles

1. **Single-Shot Analysis** — One execution performs a complete analysis of the repository. No state is preserved between runs except the generated output files.
2. **File-Based Architecture** — The knowledge graph is stored as a single `graph.json` file.
3. **Full Re-analysis** — Repository changes are handled by running the analysis again rather than maintaining incremental updates.
4. **Model-Agnostic, Local-First** — The summarization model can run locally (for example through Ollama or another local inference server) or use a remote API. Local execution is the default, while remote execution is optional.
5. **Template-Driven Analysis** — Repository-specific guidance is defined through prompt templates rather than a dedicated framework.
6. **Human-Readable Output** — Every analysis generates the same four wiki documents instead of an extensible artifact system.
7. **Open Source and Self-Hosted** — The tool runs entirely on the user's machine and does not require any hosted backend services.

## Generated Wiki

Each execution generates exactly four Markdown documents.

| #   | Document         | Description                                                                              |
| --- | ---------------- | ---------------------------------------------------------------------------------------- |
| 1   | **Tech**         | Programming languages, frameworks, dependencies, build process, and runtime environment. |
| 2   | **Tests**        | Available test suites, test coverage, and instructions for running tests.                |
| 3   | **Architecture** | High-level architecture, major layers, services, and their relationships.                |
| 4   | **Modules**      | The purpose of each module and its primary components.                                   |

For repositories with a clear frontend and backend separation, the Modules documentation may present specialized views such as component summaries for frontend applications or MVC summaries for backend applications. These views are different presentations of the same knowledge graph rather than separate analysis pipelines.

## Core Concepts

| Term                | Definition                                                                                                        |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Repository**      | The repository analyzed during a single execution, provided as a local directory or Git URL.                      |
| **Index**           | Structured metadata extracted from source code, including files, symbols, dependencies, and import relationships. |
| **Knowledge Graph** | Relationships derived from the repository index and stored in `graph.json`.                                       |
| **Analysis Pass**   | A bounded set of LLM calls guided by prompt templates to generate the wiki documentation.                         |
| **Wiki**            | The four generated Markdown documents.                                                                            |

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
