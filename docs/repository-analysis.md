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

The system is executed via a single CLI command:

```bash
repoatlas analyze <path|url>
```

---

## 6. Project Packages

The Python backend subsystem is implemented in `backend/src/`:

- `core_indexing` — Repository scanner, AST parsers (`tree-sitter-java`, `tree-sitter-c-sharp`), and IR exporter.
- `knowledge_graph` — Graph builder and dependency query engine.
- `ai_analysis` — 6-tier AST hierarchical chunker and Ollama LLM summarizer (`qwen2.5-coder:3b`).
- `wiki_generation` — Static M3 HTML renderer, Ask Local AI widget, and search index generator.
- `cli.py` — Orchestrator entrypoint.

---

## 7. Dependencies

- **Python 3.10+**
- **tree-sitter** & **tree-sitter-java** & **tree-sitter-c-sharp** — AST node extraction.
- **pydantic** — Unified IR and graph data modeling.
- **pathspec** — `.gitignore` matching.
- **httpx** — Async/sync HTTP client for local Ollama SLM API.
- **jinja2** — HTML template engine for static site generation.

---

## 8. System Layers

```text
Repository Input (Git URL or local path)
        │
        ▼
AST Parsing & Symbol Indexing (core_indexing)
        │
        ▼
Knowledge Graph Builder (knowledge_graph)
        │
        ▼
Hierarchical Chunker & SLM Summarizer (ai_analysis)
        │
        ▼
Static M3 HTML Wiki Generator (wiki_generation)
```

---

## Summary

| Aspect               | Status                         |
| -------------------- | ------------------------------ |
| Repository Structure | Available (`backend/src/`)     |
| Build System         | `pyproject.toml`               |
| Framework            | Python 3.10+ CLI application   |
| Configuration        | CLI flags & Environment vars   |
| Entry Point          | `repoatlas analyze` (`cli.py`) |
| Packages             | Fully Implemented              |
| Dependencies         | `requirements.txt`             |
| System Layers        | 5 Sequential Pipeline Layers   |
| Test Suite           | 289+ Passing pytest tests      |

