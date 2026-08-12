# RepoAtlas — Automated AST-Grounded Repository Documentation Generator

**RepoAtlas** is a self-hostable CLI tool that analyzes software repositories using language-specific AST parsers (Java & C#) and generates an interactive, multi-page static HTML documentation wiki (**Tech**, **Tests**, **Architecture**, and **Modules**) powered by a persistent Knowledge Graph and Local SLM hierarchical chunking.

---

## 🌟 Key Features

- **AST-Aware Parsing (Java & C#)**: Replaces regex line-scanning with syntax tree parsing (`tree-sitter`) to extract classes, interfaces, enums, records, structs, methods, constructors, fields, properties, annotations/attributes (`@RestController`, `[ApiController]`), Javadoc, XML comments, and call-graph edges.
- **Unified Intermediate Representation (IR)**: Normalizes AST symbol metadata into a standardized language-agnostic schema (`repository_index.json`) for downstream Knowledge Graph construction.
- **Repository Scanner**: Accepts local project paths or remote Git URLs (clones automatically), respecting `.gitignore` rules and persisting structural maps (`structure.json`).
- **Hierarchical AST Taxonomy (6-Tier)**: Chunks context strictly along AST node boundaries (`Repository → Module → Container → Component → Class → Method`) to fit small local models (7B/8B SLMs) under 2,000 tokens per prompt.
- **Interactive Static HTML Wiki**: Produces a zero-dependency static HTML site bundle (`wiki/`) with tree navigation, sticky search header, dynamic breadcrumbs, syntax highlighting, and symbol cross-hyperlinks.

---

## 🏗️ Repository Architecture

```
Wiki Generation/
├── backend/                        # Python Backend Subsystem
│   ├── pyproject.toml              # Build & dependency configuration
│   ├── requirements.txt            # Dependency list (tree-sitter, pydantic, pathspec)
│   ├── src/
│   │   └── core_indexing/          # Core Indexing Engine (Member 1 Scope)
│   │       ├── models.py           # Unified AST Node Schema & IR Models
│   │       ├── scanner.py          # Local/Git Repository Scanner (US-1.1, US-1.2)
│   │       ├── indexer.py          # Symbol Registry & Cross-File Resolution
│   │       ├── ir_generator.py     # JSON IR Exporter (repository_index.json, structure_overview.json)
│   │       └── parsers/
│   │           ├── base.py         # Abstract Base Language Parser Driver
│   │           ├── java_parser.py  # Java AST Parser (US-1.3)
│   │           └── csharp_parser.py# C# AST Parser (US-1.4)
│   └── tests/                      # Unit & End-to-End Test Suite (73 tests)
│       ├── test_java_parser.py
│       ├── test_csharp_parser.py
│       ├── test_scanner.py
│       ├── test_ir_generator.py
│       └── fixtures/               # Java & C# sample code fixtures
├── frontend/                       # Web Application / UI Assets
├── docs/                           # Architecture, Specs, Epics & ADRs (ADR-001 - ADR-010)
└── README.md
```

---

## ⚡ Quickstart & Usage

### 1. Installation

Requires **Python 3.10+**.

```bash
cd backend
python -m pip install -e ".[dev]"
```

### 2. Running Core Indexing Engine (Source Scanner)

Analyze a local codebase or remote Git URL:

```bash
cd backend

# Analyze a local project directory
python -m core_indexing /path/to/target/project -o indexes/

# Analyze a remote Git repository
python -m core_indexing https://github.com/example/repo.git -o indexes/
```

**Generated IR Artifacts** in `indexes/`:
- `structure.json`: Directory tree representation of the repository.
- `repository_index.json`: Standardized IR symbol graph consumed by Member 2 (Knowledge Graph).
- `structure_overview.json`: Compact 6-tier taxonomy map consumed by the Hierarchical Chunker.

### 3. Building and Querying the Knowledge Graph

Build `graphs/graph.json` from Epic 1 output:

```bash
python -m knowledge_graph build indexes/ -o graphs/
```

Optionally fold Epic 3 summaries and content into the graph:

```bash
python -m knowledge_graph build indexes/ -a analysis/ -o graphs/
```

Query a symbol's dependencies or find a directed path:

```bash
python -m knowledge_graph dependencies graphs/ com.example.OrderService
python -m knowledge_graph path graphs/ com.example.OrderService com.example.OrderRepository
```

See [`docs/designs/knowledge-graph-schema.md`](docs/designs/knowledge-graph-schema.md)
for the graph contract and complete query interface.

### 4. Running Unit Tests

Run the complete backend test suite:

```bash
cd backend
python -m pytest tests/ -v
```

---

## 📋 Module Responsibilities & Epics

| Epic | Component | Responsibility | Status |
| :--- | :--- | :--- | :--- |
| **Epic 1** | **Core Indexing Engine** | Repository Scanner, Java (`tree-sitter-java`) & C# (`tree-sitter-c-sharp`) AST Parsers, IR Generation (US-1.1 – US-1.4) | **Completed (Member 1)** |
| **Epic 2** | **Knowledge Graph** | Convert IR metadata into persistent `graph.json` and graph query engine (US-2.1 – US-2.3) | **Completed** |
| **Epic 3** | **AI Analysis & Chunking** | 6-Tier AST Hierarchical Chunker & Local SLM bottom-up summarizer (US-3.1 – US-3.5) | Planned |
| **Epic 4** | **Wiki Generation** | Render static HTML site bundle (`wiki/`) with trees, search, breadcrumbs & links (US-4.1 – US-4.5) | Planned |
| **Epic 5** | **CLI Orchestration** | Single unified CLI command `repoatlas analyze <path\|url>` (US-5.1 – US-5.2) | Planned |

---

## 📚 Documentation Index

Detailed design specs and architectural decision records are available in [`docs/`](docs/README.md):

- [Executive Summary](docs/executive-summary.md)
- [System Architecture](docs/architecture.md)
- [Java & C# AST Parser Design](docs/designs/ast-parser-design.md)
- [Hierarchical Prompting & Chunking Design](docs/designs/hierarchical-prompting-chunking.md)
- [Knowledge Graph Schema](docs/designs/knowledge-graph-schema.md)
- [Standardized HTML Wiki Storage Design](docs/designs/html-wiki-storage.md)
- [Architectural Decision Records (ADRs)](docs/adrs.md)
