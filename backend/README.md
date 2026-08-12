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

- **`ai_analysis` (Member 2 Scope, Epic 3)**:
  - `taxonomy/`: 6-tier taxonomy construction (`Repository → Module → Container →
    Component → Class → Method`), with a swappable provider that reads real tiers
    from `structure_overview.json` when present and infers them from build files
    otherwise.
  - `skeleton`: Compact AST skeleton rendering — signatures, annotations, field
    types and docstrings, never method bodies.
  - `chunker`: Chunks strictly on AST node boundaries; lazy source loading.
  - `tokens`: Token estimation and budget enforcement (2,000 per prompt).
  - `prompts`: Four-block prompt templates, per tier.
  - `summarizer`: Bottom-up summarization — each tier consumes only the summaries
    of the tier below, never its source.
  - `content`: The four wiki content areas (tech, tests, architecture, modules).
  - `llm/`: Ollama client (deterministic sampling), null fallback, embeddings.
  - `tools/`: Declared tool registry and validating dispatcher.

## Quickstart

```bash
# Install dependencies (the editable install puts both packages on the import path)
pip install -r requirements.txt
pip install -e .

# Run unit tests
python -m pytest tests/ -v

# Execute Core Indexing Engine CLI (Epic 1)
python -m core_indexing <path-or-git-url> -o indexes/

# Execute AI Analysis Engine CLI (Epic 3)
python -m ai_analysis indexes/ -o analysis/ --no-llm          # no model required
python -m ai_analysis indexes/ -o analysis/ --model <model>   # with a local SLM
```

## Verifying your changes

See **[`docs/testing-and-verification.md`](../docs/testing-and-verification.md)**
for the full guide: what to run, what the output should say, how to read a
failure, and which model to use on constrained hardware.

The short version — run this before every commit:

```bash
python -m pytest tests/ -q -m "not live"     # expect: 272 passed, 11 deselected
```
