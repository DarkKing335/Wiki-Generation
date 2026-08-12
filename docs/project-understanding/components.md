# RepoAtlas — Project Understanding: Components

> **Document goal:** Understand each significant component in the RepoAtlas system — what it does, what it takes as input, what it produces, and how it relates to other components.

---

## 1. Component Overview

A "component" here is a **specific, focused implementation unit** — a class or module with a well-defined responsibility. Components are organized by the module they belong to.

```
Core Indexing Engine (✅ Implemented)
├── RepositoryScanner
├── BaseLanguageParser
├── JavaParser
├── CSharpParser
├── RepositoryIndexer
├── IRGenerator
└── Unified IR Models (models.py)

Knowledge Graph (🔲 Planned — Member 2)
├── Graph Builder
└── Query Engine

AI Analysis (🔲 Planned — Member 3)
├── Hierarchical Chunker
├── SLM/LLM Client
└── Bottom-Up Summarizer

Wiki Generation + CLI (🔲 Planned — Member 4)
├── HTML Template Compiler
├── Hyperlink Resolver
├── Static Site Writer
└── CLI Orchestrator
```

---

## 2. Component: RepositoryScanner

**File:** `backend/src/core_indexing/scanner.py`  
**Class:** `RepositoryScanner`  
**Status:** ✅ Implemented  
**User Stories:** US-1.1, US-1.2

### Purpose

The entry point for repository analysis. Accepts a local path or Git URL, prepares the repository for parsing, traverses the directory tree while applying `.gitignore` rules, and routes source files to the appropriate language parsers.

### Responsibility

- Accept and validate local directory paths or detect Git URLs (GitHub, GitLab, Bitbucket, custom patterns)
- Clone remote repositories via `git clone --depth 1` into a temporary directory
- Load `.gitignore` rules using `pathspec` for exclusion filtering
- Build a `DirectoryNode` tree of the repository structure
- Persist the structure to `indexes/structure.json`
- Walk all files, dispatch `.java` → `JavaParser` and `.cs` → `CSharpParser`

### Input

| Input | Type | Description |
|-------|------|-------------|
| `target` | `str` | Local path or Git URL |
| `output_dir` | `str` | Where to save IR files (default: `indexes/`) |

### Output

| Output | Type | Description |
|--------|------|-------------|
| `structure.json` | JSON file | Repository directory tree |
| `DirectoryNode` | Python object | Tree structure for `RepositoryIndexer` |
| `List[FileIndex]` | Python objects | Per-file parsed AST results |

### Key Design Details

- Default excludes: `.git`, `node_modules`, `bin`, `obj`, `target`, `build`, `.gradle`, `__pycache__`, etc.
- Registrar pattern: parsers are registered as a dict `{".java": JavaParser(), ".cs": CSharpParser()}`
- Cleanup: temporary clone directories are removed via `cleanup()` in a `finally` block

### Dependencies

- `pathspec` — `.gitignore` matching
- `JavaParser`, `CSharpParser` — language-specific parsing
- `models.DirectoryNode`, `models.FileIndex` — output schemas

### Relationship with Other Components

- **Calls:** `JavaParser.parse()` and `CSharpParser.parse()` for each source file
- **Provides to:** `RepositoryIndexer` — the `DirectoryNode` tree and `List[FileIndex]`

---

## 3. Component: BaseLanguageParser

**File:** `backend/src/core_indexing/parsers/base.py`  
**Class:** `BaseLanguageParser` (abstract)  
**Status:** ✅ Implemented

### Purpose

Abstract contract that all language-specific parsers must satisfy. Provides shared parsing utilities.

### Responsibility

- Define the `parse(file_path, content, repo_path) → FileIndex` interface
- Provide `language` and `file_extensions` properties that concrete parsers must implement
- Provide shared utility methods: `_relative_path()`, `_clean_javadoc()`, `_clean_xml_doc()`

### Shared Utilities

| Method | Purpose |
|--------|---------|
| `_relative_path(file_path, repo_path)` | Compute a portable relative path |
| `_clean_javadoc(raw)` | Strip `/** … */` markers and leading `*` |
| `_clean_xml_doc(lines)` | Strip `///` XML doc-comment markers |

### Relationship with Other Components

- **Extended by:** `JavaParser`, `CSharpParser`
- **Used by:** `RepositoryScanner` — invokes `parser.parse()` on each source file

---

## 4. Component: JavaParser

**File:** `backend/src/core_indexing/parsers/java_parser.py`  
**Class:** `JavaParser`  
**Status:** ✅ Implemented  
**User Story:** US-1.3  
**Technology:** `tree-sitter-java`

### Purpose

Parse Java source files into normalized `ASTSymbolNode` instances using the tree-sitter parsing engine.

### Responsibility

Extract from `.java` files:

| Element | Details |
|---------|---------|
| Package declaration | FQN (e.g., `com.example.auth`) |
| Import statements | Explicit, wildcard, and static imports |
| Type declarations | Classes, interfaces, enums, records, annotation types |
| Annotations | `@RestController`, `@Service`, `@Autowired`, `@Entity`, `@Test`, etc. with arguments |
| Fields | Name, type, visibility modifiers, static/final |
| Methods | Signature, return type, parameters, thrown exceptions, access modifiers, Javadoc, line numbers |
| Constructors | Parameters, modifiers, Javadoc |
| Inheritance | `extends` and `implements` relationships |
| Method invocations | Call-graph edges (dependency tracking) |

### How a Java File Is Processed

```
.java source file (text)
    ↓
tree-sitter-java Parser
    ↓
Parse Tree (concrete syntax tree)
    ↓
JavaParser traversal:
    - Extract package_declaration → package FQN
    - Extract import_declaration → ImportInfo list
    - For each type_declaration:
        - Extract class/interface/enum/record name, modifiers, annotations
        - Build ASTSymbolNode (kind=CLASS/INTERFACE/ENUM/RECORD)
        - Extract field_declaration → ASTSymbolNode (kind=FIELD)
        - Extract method_declaration → ASTSymbolNode (kind=METHOD)
          ↳ Extract parameters → ParameterInfo list
          ↳ Extract Javadoc → docstring
        - Extract extends/implements → RelationshipEdge list
    ↓
FileIndex (file_path, language=JAVA, symbols, imports)
```

### Input

| Input | Description |
|-------|-------------|
| `file_path` | Absolute path to `.java` file |
| `content` | Raw UTF-8 text of the source file |
| `repo_path` | Repository root (for relative path computation) |

### Output

`FileIndex` containing:
- `file_path` (relative)
- `language = Language.JAVA`
- `package_or_namespace` (Java package FQN)
- `imports` — list of `ImportInfo`
- `symbols` — list of `ASTSymbolNode`

### Dependencies

- `tree_sitter` — core parsing engine
- `tree_sitter_java` — Java grammar
- `core_indexing.models` — all IR schema types

### Relationship with Other Components

- **Extends:** `BaseLanguageParser`
- **Called by:** `RepositoryScanner`
- **Output consumed by:** `RepositoryIndexer`

---

## 5. Component: CSharpParser

**File:** `backend/src/core_indexing/parsers/csharp_parser.py`  
**Class:** `CSharpParser`  
**Status:** ✅ Implemented  
**User Story:** US-1.4  
**Technology:** `tree-sitter-c-sharp`

### Purpose

Parse C# source files into normalized `ASTSymbolNode` instances using the tree-sitter parsing engine.

### Responsibility

Extract from `.cs` files:

| Element | Details |
|---------|---------|
| Namespace declarations | Scope and FQN |
| Using directives | Regular, aliased (`using Alias = Ns.Type`), and static |
| Type declarations | Classes, structs, interfaces, enums, records, delegates |
| Attributes | `[ApiController]`, `[HttpGet]`, `[Route]`, `[Fact]`, `[Key]`, etc. with arguments |
| Properties | Accessor info (`{ get; set; }`, `{ get; init; }`) |
| Fields | Modifiers, type |
| Methods | Async modifier (`async Task<T>`), parameters (`ref`, `out`, `in`), XML doc comments, line ranges |
| Constructors | Parameters, modifiers |
| Inheritance / implementation | Base class and interface relationships |
| Method invocations | Call-graph edges |

### How a C# File Is Processed

```
.cs source file (text)
    ↓
tree-sitter-c-sharp Parser
    ↓
Parse Tree (concrete syntax tree)
    ↓
CSharpParser traversal:
    - Extract namespace_declaration → namespace FQN
    - Extract using_directive → ImportInfo list (including aliases, static)
    - For each type_declaration (class/struct/interface/enum/record):
        - Extract name, modifiers, attributes
        - Build ASTSymbolNode
        - Extract property_declaration → ASTSymbolNode (kind=PROPERTY)
          ↳ Extract accessor_list → PropertyAccessors
        - Extract field_declaration → ASTSymbolNode (kind=FIELD)
        - Extract method_declaration → ASTSymbolNode (kind=METHOD)
          ↳ Extract async modifier
          ↳ Extract parameters (ref/out/in modifiers)
          ↳ Extract XML doc comments (/// <summary>)
        - Extract base_list → extends/implements RelationshipEdge list
    ↓
FileIndex (file_path, language=CSHARP, symbols, imports)
```

### Input / Output

Same structure as `JavaParser` with `language = Language.CSHARP`.

### Key Difference from JavaParser

C# has `PropertyAccessors` (`{ get; set; init; }`) which Java does not. The C# parser creates `ASTSymbolNode` with `kind=PROPERTY` and `property_accessors` populated accordingly.

### Dependencies / Relationships

Same pattern as `JavaParser` — extends `BaseLanguageParser`, called by `RepositoryScanner`, output consumed by `RepositoryIndexer`.

---

## 6. Component: Unified IR Models

**File:** `backend/src/core_indexing/models.py`  
**Status:** ✅ Implemented  
**Role:** Shared schema layer

### Purpose

Define the language-agnostic data structures that every component in the Core Indexing Engine produces and consumes — and that downstream modules (Knowledge Graph, Wiki Generator) will import.

### Key Models

| Model | Role |
|-------|------|
| `ASTSymbolNode` | Single code symbol (class, method, field, etc.) — the primary output unit of parsers |
| `SymbolKind` | Enum: `CLASS`, `INTERFACE`, `METHOD`, `FIELD`, `PROPERTY`, `ENUM`, `RECORD`, etc. |
| `Language` | Enum: `JAVA`, `CSHARP` |
| `SourceRange` | Line range (`start_line`, `end_line`) of a symbol in its source file |
| `AnnotationInfo` | A single annotation/attribute with name and arguments dict |
| `ParameterInfo` | A single method parameter (name, type, modifiers) |
| `MethodSignature` | Full method/constructor signature (return type, parameters, exceptions, async flag) |
| `PropertyAccessors` | C# property accessor flags (has_getter, has_setter, has_init) |
| `ImportInfo` | A single import/using directive |
| `FileIndex` | All metadata extracted from a single source file |
| `RelationshipEdge` | A typed directed edge between two symbols |
| `DirectoryNode` | A node in the repository directory tree (recursive) |
| `RepositoryIndex` | Top-level IR: aggregates all `FileIndex`, symbols, relationships, directory tree |

### ASTSymbolNode — Full Schema

```
ASTSymbolNode:
├── symbol_id           (globally unique: "com.example.UserService.authenticate(String,String)")
├── language            (JAVA | CSHARP)
├── kind                (CLASS | METHOD | FIELD | PROPERTY | …)
├── name                (simple name: "authenticate")
├── fully_qualified_name (package/namespace + type + member)
├── file_path           (relative path from repo root)
├── range               (start_line, end_line)
├── modifiers           (["public", "static", "final"])
├── annotations         ([{name: "Transactional", arguments: {readOnly: "false"}}])
├── docstring           (Javadoc or XML doc comment text)
├── parent_symbol_id    (enclosing symbol's symbol_id)
├── signature           (only for METHOD/CONSTRUCTOR)
│   ├── return_type
│   ├── parameters      ([{name, type, modifiers}])
│   ├── thrown_exceptions
│   └── is_async
├── property_accessors  (only for C# PROPERTY)
├── field_type          (only for FIELD/PROPERTY)
├── dependencies        ([FQNs this symbol depends on])
├── extends             (FQN of base class)
└── implements          ([FQNs of implemented interfaces])
```

### Relationship with Other Components

- **Produced by:** `JavaParser`, `CSharpParser`
- **Consumed by:** `RepositoryIndexer`, `IRGenerator`
- **Shared with (planned):** Knowledge Graph Builder, AI Analysis Chunker, Wiki Generator

---

## 7. Component: RepositoryIndexer

**File:** `backend/src/core_indexing/indexer.py`  
**Class:** `RepositoryIndexer`  
**Status:** ✅ Implemented

### Purpose

Aggregate all per-file `FileIndex` objects into a single `RepositoryIndex` — the top-level IR. Also extract cross-file relationship edges.

### Responsibility

- Maintain a FQN symbol registry (`Dict[str, ASTSymbolNode]`) for fast lookup
- Collect all symbols from all files into a flat list
- Extract structural relationships:
  - **extends** — class inheritance
  - **implements** — interface implementation
  - **uses_field** — field/property type dependencies
  - **contains** — parent→child containment (class contains method, etc.)
- Deduplicate relationship edges (by source + target + kind tuple)
- Detect languages present in the repository

### Input

| Input | Type |
|-------|------|
| `repository_name` | `str` |
| `repository_path` | `str` |
| `directory_tree` | `DirectoryNode` |
| `file_indexes` | `List[FileIndex]` |

### Output

`RepositoryIndex` — the complete IR:
- All symbols in a flat list + symbol registry
- All typed relationship edges
- Directory tree
- Per-file indexes
- Language set

### Relationship with Other Components

- **Receives from:** `RepositoryScanner` (via `file_indexes`)
- **Provides to:** `IRGenerator`

---

## 8. Component: IRGenerator

**File:** `backend/src/core_indexing/ir_generator.py`  
**Class:** `IRGenerator`  
**Status:** ✅ Implemented

### Purpose

Serialize the `RepositoryIndex` into JSON files consumed by downstream pipeline modules.

### Responsibility

Generate two distinct output files:

| File | Purpose | Consumer |
|------|---------|---------|
| `repository_index.json` | Full IR with all symbols, relationships, file indexes | Member 2 (Knowledge Graph), Member 4 (Wiki Generator) |
| `structure_overview.json` | Compact 6-tier skeleton (repository → module → container → component → classes → methods) | Member 3 (Hierarchical Chunker) |

### `structure_overview.json` — How It Is Built

```python
# Groups symbols by package/namespace (component tier)
# For each component:
#   - Filter class-type symbols (CLASS, INTERFACE, ENUM, RECORD, STRUCT)
#   - For each class: list method/constructor names
# Result: hierarchical module → container → component → class → methods structure
```

> **Note:** The current implementation groups all classes into a single `"MainContainer"`. Module-level grouping within `structure_overview.json` is simplified and may need refinement for multi-module repositories.

### Input

`RepositoryIndex` object + output directory path

### Output

- `indexes/repository_index.json`
- `indexes/structure_overview.json`

### Relationship with Other Components

- **Receives from:** `RepositoryIndexer`
- **Provides to:** Member 2 (Knowledge Graph), Member 3 (Chunker), Member 4 (Wiki)

---

## 9. Component: Knowledge Graph Builder (Planned)

**Status:** 🔲 Not currently implemented — To be implemented  
**Owner:** Member 2  
**Location:** `backend/src/knowledge_graph/` (empty)

### Purpose (Planned)

Read `repository_index.json` and transform it into a `graph.json` knowledge graph with nodes (code entities) and typed edges (relationships).

### Input (Planned)

`indexes/repository_index.json` — specifically the `symbols` and `relationships` arrays

### Output (Planned)

`graphs/graph.json`

### Note on Relationship to IR

The `RepositoryIndex` already contains `RelationshipEdge` objects with types `extends`, `implements`, `uses_field`, `contains`. The Knowledge Graph Builder's task is to transform these into a graph format and potentially add higher-level semantic relationships (e.g., module-level groupings, call-graph aggregation).

---

## 10. Component: Hierarchical Chunker (Planned)

**Status:** 🔲 Not currently implemented — To be implemented  
**Owner:** Member 3  
**Location:** `backend/src/ai_analysis/taxonomy/` (empty)

### Purpose (Planned)

Structure the `structure_overview.json` data along the 6-tier AST taxonomy and produce per-level AST skeleton prompts for the LLM.

### 6-Tier Taxonomy

```
Repository → Module → Container → Component → Class → Method
```

### Chunking Process (Planned)

```
structure_overview.json
    ↓
For each tier level (bottom-up):
    - Extract relevant AST nodes at this tier
    - Produce compact skeleton prompt:
        [SYSTEM_PROMPT]
        [TARGET_CONTEXT: Module/Container/Component]
        [STRUCTURAL_SKELETON: class signatures + docstrings]
        [TASK_INSTRUCTION: summarize in <100 words]
    - Enforce token limit < 2,000 tokens per prompt
    ↓
Prompt batch per tier level
```

### Key Constraints (From Design)

- Chunks MUST align with AST node boundaries — no line-based splitting
- Prompts MUST stay under 2,000 tokens for local 7B/8B SLMs
- Raw source body loaded lazily only if LLM explicitly requests deep inspection

---

## 11. Component: HTML Template Compiler (Planned)

**Status:** 🔲 Not currently implemented — To be implemented  
**Owner:** Member 4

### Purpose (Planned)

Load HTML templates (Handlebars or Jinja) and compile wiki pages from `graph.json`, `repository_index.json`, and AI summaries.

### Templates Structure (Planned, from design)

- `page.hbs` / `page.html.j2` — Generic page layout with sidebar, navbar, breadcrumb
- `symbol.hbs` — AST class/interface symbol page
- `module.hbs` — Module documentation page

### Process (Planned)

```
graph.json + IR + summaries
    ↓
Template Loader
    ↓
Context Builder (map IR data to template variables)
    ↓
Hyperlink Resolver (FQN → symbols/<fqn>.html)
    ↓
HTML Page Writer
    ↓
wiki/ directory
```

---

## 12. Component Cross-Reference Table

| Component | Produces | Consumed By |
|-----------|----------|------------|
| RepositoryScanner | `DirectoryNode` + `List[FileIndex]` | RepositoryIndexer |
| JavaParser | `FileIndex` (JAVA) | RepositoryIndexer |
| CSharpParser | `FileIndex` (CSHARP) | RepositoryIndexer |
| RepositoryIndexer | `RepositoryIndex` | IRGenerator |
| IRGenerator | `repository_index.json`, `structure_overview.json` | KG Builder, Chunker, Wiki |
| KG Builder (planned) | `graph.json` | AI Summarizer, Wiki |
| Hierarchical Chunker (planned) | AST skeleton prompts | LLM Client |
| LLM Client (planned) | Summaries | Bottom-Up Summarizer |
| Bottom-Up Summarizer (planned) | Component/Module/Arch summaries | Wiki Generator |
| HTML Template Compiler (planned) | `wiki/*.html` | End user (browser) |

---

## 13. Fact vs. Inference vs. Planned

| Claim | Status |
|-------|--------|
| `JavaParser` uses `tree-sitter-java` | ✅ **Observed Fact** (import in source) |
| `CSharpParser` uses `tree-sitter-c-sharp` | ✅ **Observed Fact** (import in source) |
| `RepositoryIndexer` extracts `extends`, `implements`, `uses_field`, `contains` edges | ✅ **Observed Fact** (indexer.py) |
| `IRGenerator` groups all classes into a single "MainContainer" | ✅ **Observed Fact** (ir_generator.py) |
| `models.py` defines 12 Pydantic model classes | ✅ **Observed Fact** (models.py) |
| Knowledge Graph Builder is not implemented | ✅ **Observed Fact** (empty directory) |
| AI Analysis components are not implemented | ✅ **Observed Fact** (empty directories) |
| Hierarchical Chunker uses 6-tier taxonomy | 💡 **Inferred** from design documents |
| Wiki generator uses Handlebars/Jinja templates | 💡 **Inferred** from `html-wiki-storage.md` |
| Module-level grouping in `structure_overview.json` will need refinement | 💡 **Inferred** from IRGenerator source analysis |
