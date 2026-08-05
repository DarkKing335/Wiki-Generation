# RepoAtlas — Repository Analysis

## Overview

The current repository represents the initial stage of the project. It mainly consists of project scaffolding, documentation, research resources, and templates. No application logic or executable components have been implemented.

---

## 1. Repository Structure

| Directory       |  Files | Purpose                                    |
| --------------- | -----: | ------------------------------------------ |
| `agents/`       |      0 | AI analysis and prompt templates           |
| `graphs/`       |      0 | Knowledge graph output (`graph.json`)      |
| `indexes/`      |      0 | Repository indexing results                |
| `output/`       |      0 | Generated analysis artifacts               |
| `wiki/`         |      0 | Generated static HTML wiki site bundle     |
| `packages/`     |      0 | Reserved for future project packages       |
| `repositories/` |      0 | Temporary repository workspace             |
| `research/`     | 15,403 | Reference materials and research resources |
| `templates/`    | 26,892 | Documentation and prompt templates         |
| `docs/`         |     13 | Project design documents & specifications  |

### Observation

The repository currently serves as a project scaffold. Placeholder directories are reserved for runtime implementations detailed in [`docs/designs/`](file:///e:/FPT/Wiki%20Generation/docs/designs).

---

## 2. Build System

No build process has been implemented.

The intended implementation is expected to provide a single command-line executable responsible for the complete repository analysis workflow.

---

## 3. Framework

No application framework has been identified.

The project will remain lightweight, incorporating targeted dependencies for language parsing, static site rendering, and local SLM interaction.

---

## 4. Configuration

No configuration mechanism currently exists.

The expected configuration includes:

- Repository input path or URL.
- Optional local SLM / remote LLM configuration.
- Output directory (`wiki/`).

---

## 5. Entry Point

No executable entry point currently exists.

The planned interface is a single CLI command:

```bash
repoatlas analyze <path|url>
```

---

## 6. Project Packages

No software packages have been implemented.

Current directories are reserved for future functionality.

---

## 7. Dependencies

Target runtime implementation requires:

- **Git** — For cloning remote repositories.
- **Java Parser** — `JavaParser` / `tree-sitter-java` for AST node extraction.
- **C# Parser** — `Microsoft.CodeAnalysis.CSharp` (Roslyn) / `tree-sitter-c-sharp` for AST extraction.
- **HTML Templating Engine** — Handlebars / Jinja templating library for compiling static HTML pages.
- **HTTP Client** — For communicating with local SLM inference servers (e.g. Ollama) or remote LLM APIs.
- **CLI Framework** — Command-line argument parsing and terminal formatting library.

---

## 8. System Layers

The intended architecture consists of a simple sequential workflow:

```text
Repository Input
        │
        ▼
Repository Analysis
        │
        ▼
Knowledge Graph
        │
        ▼
Documentation Generation
```

No service layer or distributed architecture is planned.

---

## Summary

| Aspect               | Status                         |
| -------------------- | ------------------------------ |
| Repository Structure | Available                      |
| Build System         | Not implemented                |
| Framework            | Not determined                 |
| Configuration        | Not implemented                |
| Entry Point          | Planned                        |
| Packages             | Placeholder only               |
| Dependencies         | Minimal, future implementation |
| System Layers        | Planned                        |
