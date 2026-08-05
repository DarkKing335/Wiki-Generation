# RepoAtlas — Product

## 1. Product Vision

RepoAtlas is a lightweight CLI tool that analyzes a single repository and generates exactly four wiki documents (**Tech**, **Tests**, **Architecture**, and **Modules**) using a fixed analysis toolset and an optional LLM that can run locally or through a remote API.

## 2. Functional Requirements

| ID    | Requirement                | Description                                                                                                          | Status |
| ----- | -------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------ |
| FR-1  | Repository Input           | Accept a local repository path or Git URL for a single analysis.                                                     | —      |
| FR-2  | Repository Analysis        | Scan repository structure and file layout.                                                                          | —      |
| FR-3  | LLM / SLM Support          | Support local SLMs (default) and remote LLM providers through configuration.                                         | —      |
| FR-4  | Tech View Generation       | Generate **Tech** documentation (`tech.html`) describing tech stack, dependencies, and environment.                | —      |
| FR-5  | Tests View Generation      | Generate **Tests** documentation (`tests.html`) describing test suites and execution instructions.                   | —      |
| FR-6  | Architecture View          | Generate **Architecture** documentation (`architecture.html`) describing layers and system diagrams.                | —      |
| FR-7  | Modules & Symbol View      | Generate **Modules** & AST symbol pages (`modules/*.html`, `symbols/*.html`) describing components and types.        | —      |
| FR-8  | Knowledge Graph            | Build a persistent knowledge graph and save it as `graph.json`.                                                      | —      |
| FR-9  | Operation Without LLM      | Continue generating structural HTML documentation from AST symbol tables even without an LLM.                        | —      |
| FR-10 | Full Re-analysis           | Regenerate the knowledge graph and HTML wiki site whenever the analysis command is executed again.                   | —      |
| FR-11 | Java AST Parsing           | Parse Java code into normalized AST nodes, extracting classes, annotations, fields, methods, and Javadoc.           | —      |
| FR-12 | C# AST Parsing             | Parse C# code into normalized AST nodes, extracting classes, attributes, properties, methods, and XML docs.         | —      |
| FR-13 | Hierarchical AST Chunking  | Structure code context along the 6-tier AST taxonomy (`Repository → Module → Container → Component → Class → Method`).| —      |
| FR-14 | HTML Wiki Site Storage     | Standardize wiki storage as an interactive static HTML website (`wiki/`) with trees, breadcrumbs, search, and links.| —      |
| FR-15 | Local SLM Optimization     | Inject compact AST skeletons to enforce prompt token limits (<2,000 tokens) for local 7B/8B models.                | —      |

## 3. Non-Functional Requirements

- **Simplicity** — Executed via a single CLI command, producing a clean, self-contained HTML website (`wiki/`).
- **Privacy & Local-First** — Source code stays on the local machine; local SLM execution is default.
- **SLM Performance** — Prompts adhere to strict context limits (<2k tokens), achieving <10s generation per module.
- **HTML UX & Responsiveness** — Generated pages load in <100ms with working search, breadcrumb trails, and deep hyperlinking.
- **Reproducibility** — Identical repository states produce identical AST symbol graphs and static wiki pages.
- **Portability** — Static HTML site runs locally (`file://`) or hosted without requiring database or backend services.

## 4. Personas

| Persona                   | Goal                                                                                                             |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Software Engineer**     | Understand an unfamiliar repository by generating an interactive HTML wiki with a single command.                |
| **Repository Maintainer** | Regenerate project documentation whenever the codebase changes, keeping code local.                              |

## 5. Core Capabilities

| Capability          | Implementation                                      |
| ------------------- | --------------------------------------------------- |
| Repository Input    | CLI command (`repoatlas analyze <path\|url>`)       |
| Language Parsing    | `parse_java_ast`, `parse_csharp_ast` (Java & C#)    |
| AST Context Engine  | 6-tier taxonomy Hierarchical Chunker                |
| AI Summarization    | `summarize` (Local SLM bottom-up processing)        |
| Knowledge Graph     | `graph.json` & Repository Symbol Index              |
| Wiki Rendering      | Interactive Static HTML Site Engine (`wiki/`)       |

## 6. Summary

RepoAtlas focuses on a simple workflow: analyze one repository, build a knowledge graph, optionally enrich it with an LLM, and generate four wiki documents. The product intentionally maintains a fixed scope with a single CLI interface, a small analysis toolset, and predictable outputs.
