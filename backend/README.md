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

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests
python -m pytest tests/ -v

# Execute Core Indexing Engine CLI
python -m core_indexing <path-or-git-url> -o indexes/
```
