# RepoAtlas Backend

Python backend subsystem for RepoAtlas code indexing, knowledge graph construction, hierarchical chunking, and documentation generation.

## Components

- **`core_indexing` (Member 1 Scope)**:
  - `scanner`: Repository Scanner (supports local paths and Git URLs, respects `.gitignore`).
  - `parsers/java_parser`: Java AST Parser (`tree-sitter-java`).
  - `parsers/csharp_parser`: C# AST Parser (`tree-sitter-c-sharp`).
  - `models`: Pydantic schemas for the Unified AST Node Representation and IR.
  - `indexer`: Global symbol registry and cross-file relationship builder.
  - `ir_generator`: Exporter for `repository_index.json` and `structure_overview.json`.
- **`knowledge_graph` (Epic 2)**:
  - `builder`: Deterministic `graph.json` generation from the repository index.
  - `models`: Versioned, self-contained graph schema.
  - `query`: Incoming/outgoing dependencies, neighbors, and shortest paths.
  - Optional enrichment from Epic 3's `summaries.json`.

## Quickstart

```bash
# Install the package and development dependencies
python -m pip install -e ".[dev]"

# Run unit tests
python -m pytest tests/ -v

# Execute End-to-End Analysis CLI (Local-First AI with qwen2.5-coder:3b or No-LLM fallback)
repoatlas analyze <path-or-git-url>
repoatlas analyze <path-or-git-url> --no-llm

# Execute Core Indexing Engine CLI individually
python -m core_indexing <path-or-git-url> -o indexes/

# Build and query the Epic 2 knowledge graph individually
python -m knowledge_graph build indexes/ -o graphs/
python -m knowledge_graph dependencies graphs/ <symbol-id>
```

## Recommended Local AI Model

RepoAtlas is optimized for code-specialized Local Small Language Models (SLMs) via Ollama:
- **Default / Recommended**: `qwen2.5-coder:3b` (~1.9 GB download, ~2.5 GB RAM, fast & highly accurate for code understanding)
- **High Detail**: `qwen2.5-coder:7b` (~4.7 GB download, ~5.5 GB RAM)
- **No-LLM Mode**: `--no-llm` generates deterministic structural documentation without requiring Ollama.

