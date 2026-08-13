# RepoAtlas — Project Understanding: Backend Understanding

> **Document goal:** Explain how the RepoAtlas backend is structured — its Python packages, layers, execution flow, and how it understands the repository being analyzed.

---

## 1. Backend Overview

The RepoAtlas backend is a **Python application** that implements the repository analysis pipeline. It is located at `backend/` and currently contains the fully implemented Core Indexing Engine.

```
backend/
├── pyproject.toml          # Build & dependency configuration
├── requirements.txt        # Runtime dependencies (tree-sitter, pydantic, pathspec, httpx)
├── README.md               # Backend quickstart
├── src/
│   ├── cli.py              # ✅ IMPLEMENTED — Single-command CLI Entrypoint (repoatlas analyze)
│   ├── core_indexing/      # ✅ IMPLEMENTED — Core Indexing Engine (Epic 1)
│   │   ├── models.py       # Unified IR schema (Pydantic)
│   │   ├── scanner.py      # Repository Scanner (Local paths & Git URL cloning)
│   │   ├── indexer.py      # Cross-file symbol indexer
│   │   ├── ir_generator.py # IR JSON exporter
│   │   └── parsers/
│   │       ├── base.py     # Abstract parser contract
│   │       ├── java_parser.py
│   │       └── csharp_parser.py
│   ├── knowledge_graph/    # ✅ IMPLEMENTED — Knowledge Graph Subsystem (Epic 2)
│   │   ├── builder.py      # graph.json Builder
│   │   ├── models.py       # Graph Nodes & Edges Schema
│   │   └── query.py        # Dependency & Shortest Path Query Engine
│   ├── ai_analysis/        # ✅ IMPLEMENTED — AI Analysis Subsystem (Epic 3)
│   │   ├── chunker.py      # 6-Tier AST Hierarchical Chunker
│   │   ├── content.py      # Lazy source file reader & signature extractor
│   │   ├── summarizer.py   # Bottom-up Ollama LLM Summarizer
│   │   └── llm/            # Ollama SLM client (qwen2.5-coder:3b) & NullLLM fallback
│   └── wiki_generation/    # ✅ IMPLEMENTED — Wiki Site Generation Subsystem (Epic 4)
│       ├── renderer.py     # Jinja2 renderer & search_index.json builder
│       └── templates/      # M3 static layout templates & Local AI Widget
└── tests/                  # ✅ 289+ Passing Unit & Integration Tests
    ├── test_cli.py
    ├── test_scanner.py
    ├── test_java_parser.py
    ├── test_csharp_parser.py
    ├── test_knowledge_graph.py
    ├── test_chunker.py
    ├── test_summarizer.py
    └── test_wiki_renderer.py
```

---

## 2. Backend Architecture Style

RepoAtlas does **not** follow a traditional MVC or service/controller pattern. Instead it follows a **pipeline architecture** — a linear sequence of transformation stages where each stage consumes the output of the previous one.

```
Input Stage (Scanner)
    ↓
Parsing Stage (tree-sitter Java/C# Parsers)
    ↓
Indexing Stage (RepositoryIndexer)
    ↓
Export Stage (IRGenerator: repository_index.json, structure_overview.json)
    ↓
Graph Stage (GraphBuilder: graph.json)
    ↓
Analysis Stage (6-Tier Chunker + Ollama SLM Summarizer)
    ↓
Rendering Stage (WikiRenderer Jinja2 Static HTML + search_index.json)
```

There is no:
- Controller / Route layer
- Service / Repository layer (in the MVC sense)
- Database
- ORM

> **Observed fact:** The backend is a stateless CLI application. No persistent server state is required. All output is written to structured file artifacts (`indexes/`, `graphs/`, `analysis/`, `wiki/`).

---

## 3. Implemented Backend: Pipeline Execution Flow

### 3.1 Orchestrated CLI Execution

When the user runs:

```bash
repoatlas analyze <path-or-git-url>
```

The unified execution flow (`cli.py`) runs all stages seamlessly:

```python
# cli.py
1. scanner = RepositoryScanner(target=args.target, output_dir=...)
   tree, file_indexes = scanner.scan_and_parse()

2. indexer = RepositoryIndexer(...)
   index = indexer.build_index()

3. generator = IRGenerator(index=index, output_dir=...)
   generator.generate_all()

4. graph = GraphBuilder.build_from_ir(index)
   graph.save("graphs/graph.json")

5. chunker = HierarchicalChunker(overview_path)
   summarizer = BottomUpSummarizer(chunker=chunker, llm_client=...)
   summaries = summarizer.summarize_all()

6. renderer = WikiRenderer(output_dir="wiki/")
   renderer.render_site(index, graph, summaries)
```

---

## 4. How the Backend "Understands" a Repository

The backend's understanding proceeds through 5 distinct phases:

### Phase 1: Structural Understanding
Navigates file tree, obeys `.gitignore`, detects Java and C# files. Output: `structure.json`.

### Phase 2: Syntactic Understanding (AST)
Uses `tree-sitter-java` and `tree-sitter-c-sharp` to extract packages, classes, methods, fields, signatures, and doc comments into universal `ASTSymbolNode` models.

### Phase 3: Relational Understanding
Extracts `extends`, `implements`, `uses_field`, and `contains` relations into `repository_index.json`.

### Phase 4: Topological & Semantic Graph Understanding
Builds persistent `graph.json` knowledge graph enabling dependency and shortest path querying.

### Phase 5: Hierarchical & Architectural Understanding
Chunker structures codebase into 6 taxonomy tiers (Repository → Module → Container → Component → Class → Method). Ollama SLM (`qwen2.5-coder:3b`) generates bottom-up natural language summaries.

---

## 5. Backend Testing

### Test Suite

**Location:** `backend/tests/`  
**Framework:** `pytest`  
**Test count:** 289+ tests (all passing)

### Running Tests

```bash
cd backend
pytest
```

---

## 6. Backend Dependencies

| Dependency | Purpose |
|------------|---------|
| `tree-sitter` | AST parsing engine |
| `tree-sitter-java` | Java AST grammar |
| `tree-sitter-c-sharp` | C# AST grammar |
| `pydantic` | Schema validation and JSON serialization |
| `pathspec` | `.gitignore` pattern matching |
| `httpx` | Ollama Local SLM API client |
| `jinja2` | M3 Static HTML Template rendering engine |

---

## 7. Fact vs. Inference vs. Implemented

| Claim | Status |
|-------|--------|
| Backend is a Python pipeline application | ✅ **Observed Fact** |
| Backend test suite passes (289+ tests) | ✅ **Observed Fact** (`pytest tests/`) |
| `tree-sitter-java` and `tree-sitter-c-sharp` are the AST engines | ✅ **Observed Fact** |
| Knowledge Graph builder and Query API implemented | ✅ **Observed Fact** (`knowledge_graph/`) |
| AI Analysis Engine with 6-tier taxonomy implemented | ✅ **Observed Fact** (`ai_analysis/`) |
| Default local SLM model is `qwen2.5-coder:3b` via Ollama | ✅ **Observed Fact** (`ollama.py`) |
| Single CLI `repoatlas analyze` end-to-end orchestration implemented | ✅ **Observed Fact** (`src/cli.py`) |


