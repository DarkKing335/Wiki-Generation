# RepoAtlas — Automated AST-Grounded Repository Documentation Generator

**RepoAtlas** is a self-hostable CLI tool that analyzes software repositories using language-specific AST parsers (Java & C#) and generates an interactive, multi-page static HTML documentation wiki (**Tech**, **Tests**, **Architecture**, and **Modules**) powered by a persistent Knowledge Graph, Local SLM hierarchical chunking, and an embedded **Local AI Assistant**.

---

## 🌟 Key Features

- **AST-Aware Parsing (Java & C#)**: Replaces regex line-scanning with syntax tree parsing (`tree-sitter`) to extract classes, interfaces, enums, records, structs, methods, constructors, fields, properties, annotations/attributes (`@RestController`, `[ApiController]`), Javadoc, XML comments, and call-graph edges.
- **Git & Local Repository Scanner**: Accepts local project paths, remote Git URLs (`https://...`, `git@...`), or GitHub shorthand (`owner/repo`), automatically cloning remote repositories into temporary workspaces and conducting clean teardowns.
- **Hierarchical AST Taxonomy (6-Tier)**: Chunks context strictly along AST node boundaries (`Repository → Module → Container → Component → Class → Method`) to fit small local models (7B/8B SLMs) under 2,000 tokens per prompt.
- **Modern M3 / Bento Grid UI System**: Produces a zero-dependency static HTML site bundle (`wiki/`) with Tailwind CSS, Material Symbols Outlined, Bento Grid card layouts, and CSS font-fallback declarations eliminating FOUT (flash of unstyled text) during tab navigation.
- **Multi-tier Module Taxonomy Breakdown**: Visualizes full structural hierarchy (*Modules → Containers / Deployables → Packages / Components → Classes & Symbols*) with AI summaries and clickable symbol links.
- **Embedded Local AI Assistant Widget**: Floating "Ask Local AI" chat widget embedded directly into every static wiki page, connected to local Ollama (`qwen2.5-coder:3b`) with real-time streaming and client-side hybrid `search_index.json` query analysis.

---

## 🏗️ Repository Architecture

```
Wiki Generation/
├── backend/                        # Python Backend Subsystem
│   ├── pyproject.toml              # Build & dependency configuration
│   ├── requirements.txt            # Dependency list (tree-sitter, pydantic, pathspec, httpx)
│   ├── src/
│   │   ├── cli.py                  # Single-command CLI Entrypoint (repoatlas analyze)
│   │   ├── core_indexing/          # Core Indexing Engine (Epic 1)
│   │   │   ├── models.py           # Unified AST Node Schema & IR Models
│   │   │   ├── scanner.py          # Local/Git Repository Scanner (Git cloning & local discovery)
│   │   │   ├── indexer.py          # Symbol Registry & Cross-File Resolution
│   │   │   ├── ir_generator.py     # JSON IR Exporter (repository_index.json, structure_overview.json)
│   │   │   └── parsers/            # Java & C# tree-sitter Parsers
│   │   ├── knowledge_graph/        # Graph Builder & Dependency Engine (Epic 2)
│   │   ├── ai_analysis/            # Hierarchical Chunker & Ollama LLM Summarizer (Epic 3)
│   │   └── wiki_generation/        # Jinja2 Wiki Site Generator & Renderer (Epic 4)
│   │       ├── renderer.py         # Static HTML & search_index.json generator
│   │       └── templates/          # Modern M3 templates (base, index, tech, architecture, modules, tests, symbol)
│   └── tests/                      # Unit & Integration Test Suite (289 passing tests)
├── docs/                           # Architecture Specs, Epics, User Stories & ADRs
└── README.md
```

---

## ⚡ Quickstart & Usage

### 1. Installation

Requires **Python 3.10+** and **Ollama** (optional for AI mode):

```bash
cd backend
python -m pip install -e ".[dev]"
```

### 2. Single-Command Analysis (CLI)

Analyze a local codebase or remote Git URL:

```bash
# Analyze a local project directory
repoatlas analyze /path/to/target/project

# Analyze a remote Git repository URL or shorthand
repoatlas analyze https://github.com/jenkins-docs/simple-java-maven-app.git
repoatlas analyze spring-projects/spring-petclinic
```

**Generated Artifacts** in `wiki/`:
- `index.html`: Master Overview Dashboard with Bento Grid metrics.
- `tech.html`: Technology Stack and environment documentation.
- `architecture.html`: System layers and component organization.
- `modules.html`: 3-Column structural taxonomy breakdown (Modules, Deployables, Packages, Classes).
- `tests.html`: Test framework runner guide and test method listings.
- `symbols/*.html`: AST Class & Method detail pages with syntax-highlighted signatures.
- `search_index.json`: Fast client-side search index powering live search and local AI context lookup.

### 3. Running Unit Tests

Run the complete backend test suite (289 tests):

```bash
cd backend
pytest
```

---

## 📋 Module Responsibilities & Epics

| Epic | Component | Responsibility | Status |
| :--- | :--- | :--- | :--- |
| **Epic 1** | **Core Indexing Engine** | Repository Scanner, Java & C# AST Parsers, Remote Git Cloning, IR Generation (US-1.1 – US-1.4) | **Completed** |
| **Epic 2** | **Knowledge Graph** | Convert IR metadata into persistent `graph.json` and graph query engine (US-2.1 – US-2.3) | **Completed** |
| **Epic 3** | **AI Analysis & Chunking** | 6-Tier AST Hierarchical Chunker & Local Ollama SLM bottom-up summarizer (US-3.1 – US-3.5) | **Completed** |
| **Epic 4** | **Wiki Generation** | Render static HTML site bundle (`wiki/`) with modern M3 design, search, Local AI Widget (US-4.1 – US-4.7) | **Completed** |
| **Epic 5** | **CLI Orchestration** | Single unified CLI command `repoatlas analyze <path\|url>` (US-5.1 – US-5.2) | **Completed** |

---

## 📚 Documentation Index

Detailed design specs and architectural decision records are available in [`docs/`](docs/README.md):

- [Executive Summary](docs/executive-summary.md)
- [System Architecture](docs/architecture.md)
- [Epics Overview](docs/epics.md)
- [User Stories](docs/user-stories.md)
- [Java & C# AST Parser Design](docs/designs/ast-parser-design.md)
- [Hierarchical Prompting & Chunking Design](docs/designs/hierarchical-prompting-chunking.md)
- [Knowledge Graph Schema](docs/designs/knowledge-graph-schema.md)
- [Standardized HTML Wiki Storage Design](docs/designs/html-wiki-storage.md)
- [Architectural Decision Records (ADRs)](docs/adrs.md)
