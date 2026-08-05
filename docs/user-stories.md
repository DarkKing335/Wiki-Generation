# RepoAtlas — User Stories

## Epic 1 — Repository Indexing

### US-1.1 Analyze a Repository

**As a** software engineer,
**I want** to analyze a repository from a local path or Git URL,
**so that** RepoAtlas can extract its structure without additional setup.

**Acceptance Criteria**

- Accept both local paths and Git URLs.
- Clone remote repositories automatically.
- Generate the repository structure and import graph.
- Display clear error messages for invalid repositories.

**Definition of Done**

- Successfully analyzes at least one supported programming language.

---

### US-1.2 Save Repository Structure

**As a** software engineer,
**I want** the scanned repository structure to be stored locally during execution,
**so that** later stages can reuse it without scanning the repository again.

**Acceptance Criteria**

- Repository structure is saved after scanning.
- Later processing stages reuse the saved structure.

**Definition of Done**

- Structure file is successfully generated and reused during the same execution.

---

### US-1.3 Java AST Parsing

**As a** software engineer,
**I want** Java source files to be parsed into AST nodes using `JavaParser`,
**so that** classes, interfaces, annotations, methods, parameters, and Javadoc are accurately indexed.

**Acceptance Criteria**

- Extract Java classes, interfaces, enums, records, annotations (`@Service`, `@RestController`, `@Test`).
- Extract field types, visibility modifiers, method signatures, parameters, and Javadoc string.
- Register all extracted symbols into the Repository Index.

**Definition of Done**

- Passes unit tests parsing representative Java projects into normalized AST JSON.

---

### US-1.4 C# AST Parsing

**As a** software engineer,
**I want** C# source files to be parsed into AST nodes using Roslyn / `tree-sitter-c-sharp`,
**so that** namespaces, classes, attributes, properties, methods, and XML comments are indexed.

**Acceptance Criteria**

- Extract C# namespaces, classes, structs, interfaces, records, attributes (`[ApiController]`, `[HttpGet]`).
- Extract property accessors (`{ get; set; }`), async status, method parameters, and XML doc comments (`/// <summary>`).
- Register extracted symbols into the Repository Index.

**Definition of Done**

- Passes unit tests parsing representative C# solutions into normalized AST JSON.

---

## Epic 2 — Knowledge Graph

### US-2.1 Generate a Knowledge Graph

**As a** software engineer,
**I want** the repository metadata to be converted into a knowledge graph,
**so that** I can inspect the project structure.

**Acceptance Criteria**

- Generate `graph.json`.
- Store repository entities and relationships.
- Define a documented graph schema.

**Definition of Done**

- Graph generation passes validation tests.

---

### US-2.2 Query the Knowledge Graph

**As a** software engineer,
**I want** to query repository relationships,
**so that** I can understand dependencies without repeating the analysis.

**Acceptance Criteria**

- Load `graph.json`.
- Support relationship queries.
- Return dependency information.

**Definition of Done**

- Representative graph queries execute successfully.

---

### US-2.3 Regenerate After Repository Changes

**As a** software engineer,
**I want** to rerun the analysis after modifying the repository,
**so that** the documentation remains up to date.

**Acceptance Criteria**

- Running the analysis recreates `graph.json`.
- Previous results are replaced completely.

**Definition of Done**

- Repository updates are correctly reflected in regenerated documentation.

---

## Epic 3 — AI Analysis

### US-3.1 Configure a Local LLM

**As a** software engineer,
**I want** to use a locally hosted LLM / SLM,
**so that** repository code remains on my machine.

**Acceptance Criteria**

- Configure a local inference endpoint.
- Repository summaries are generated through the local model.

**Definition of Done**

- Successfully tested with a supported local LLM.

---

### US-3.2 Run Without an LLM

**As a** user,
**I want** RepoAtlas to work without an LLM,
**so that** I can still generate documentation.

**Acceptance Criteria**

- Structural documentation is generated.
- Missing AI descriptions do not interrupt execution.

**Definition of Done**

- Complete analysis succeeds without LLM configuration.

---

### US-3.3 Generate Architecture Summaries

**As a** software engineer,
**I want** architecture components to be summarized automatically,
**so that** I can quickly understand the repository architecture.

**Acceptance Criteria**

- Repository layers are identified.
- Descriptions are generated when an LLM is available.

**Definition of Done**

- Architecture information is included in the generated knowledge graph.

---

### US-3.4 Generate Module Summaries

**As a** software engineer,
**I want** repository modules to be summarized automatically,
**so that** I can understand their responsibilities.

**Acceptance Criteria**

- Modules are identified automatically.
- Descriptions are generated when an LLM is available.

**Definition of Done**

- Module information is included in the generated knowledge graph.

---

### US-3.5 Hierarchical AST Chunking for Local SLM

**As a** software engineer,
**I want** code chunks to be structured along the 6-tier AST taxonomy (`Repository → Module → Container → Component → Class → Method`),
**so that** small local language models (7B/8B) can process context without exceeding token limits (<2,000 tokens per prompt).

**Acceptance Criteria**

- Chunks are created exclusively along syntactically valid AST node boundaries.
- Prompts use compact AST skeletons (signatures, fields, docstrings) instead of raw function bodies.
- Summarization proceeds bottom-up from methods to repository-level summaries.

**Definition of Done**

- Verified token consumption stays under 2,000 tokens per prompt for representative classes.

---

## Epic 4 — Wiki Generation

### US-4.1 Generate Tech Documentation

**As a** software engineer,
**I want** a Tech view describing the project technology stack,
**so that** I can build and run the project.

**Definition of Done**

- `wiki/tech.html` is generated.

---

### US-4.2 Generate Tests Documentation

**As a** software engineer,
**I want** documentation describing project testing,
**so that** I understand how to execute the test suite.

**Definition of Done**

- `wiki/tests.html` is generated.

---

### US-4.3 Generate Architecture Documentation

**As a** software engineer,
**I want** an Architecture view describing the system structure,
**so that** I understand the repository at a high level.

**Definition of Done**

- `wiki/architecture.html` is generated.

---

### US-4.4 Generate Modules Documentation

**As a** software engineer,
**I want** documentation describing repository modules,
**so that** I understand the responsibilities of each module.

**Definition of Done**

- `wiki/modules/*.html` and `wiki/symbols/*.html` are generated.

---

### US-4.5 Render Interactive Static HTML Wiki Site

**As a** software engineer,
**I want** the generated documentation to be rendered as an interactive static HTML website,
**so that** I can navigate using a sidebar tree view, breadcrumbs, live search, and hyperlinked symbol definitions.

**Acceptance Criteria**

- Output is rendered as a standalone static HTML website bundle in `wiki/`.
- Includes sidebar tree navigation, sticky navbar, dynamic breadcrumbs, live search bar, and CSS syntax highlighting.
- AST symbol types in code blocks hyperlink directly to `symbols/<fqn>.html`.

**Definition of Done**

- Static website opens and functions smoothly in modern web browsers (`file://`).

---

## Epic 5 — Command-Line Interface

### US-5.1 Execute the Complete Workflow

**As a** software engineer,
**I want** a single command that performs the complete analysis,
**so that** I do not need to execute each stage manually.

**Definition of Done**

- `repoatlas analyze <path|url>` generates all documentation.

---

### US-5.2 Configure the LLM

**As a** software engineer,
**I want** to choose between local or disabled LLM modes,
**so that** I can control privacy, cost, and execution environment.

**Definition of Done**

- All supported LLM modes are tested.

---

## Story Mapping

| User Story      | Epic   |
| --------------- | ------ |
| US-1.1 – US-1.4 | Epic 1 |
| US-2.1 – US-2.3 | Epic 2 |
| US-3.1 – US-3.5 | Epic 3 |
| US-4.1 – US-4.5 | Epic 4 |
| US-5.1 – US-5.2 | Epic 5 |

## Status

**Planned — In Preparation for Sprint Implementation.**
