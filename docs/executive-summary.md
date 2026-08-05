# RepoAtlas — Executive Summary

## Project Overview

**RepoAtlas** is a lightweight CLI tool that analyzes a repository (provided as a local path or repository URL) and generates an **interactive static HTML wiki website** (covering **Tech**, **Tests**, **Architecture**, and **Modules**). The wiki is produced from a knowledge graph built using language-specific AST parsers (Java and C#) and a fixed analysis toolset. The LLM used for summarization is optimized for **Local SLMs** (using hierarchical AST chunking) by default, or can use a remote API if configured.

At the time of this analysis, the `/RepoAtlas/` repository contains project scaffolding, vendored research resources, templates, and comprehensive project design documentation.

## Key Design

| Component                          | Description                                                                                                                                                                                               |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local SLM or Remote LLM            | Summarization uses a local SLM endpoint by default (leveraging a 6-tier AST taxonomy: Repository → Module → Container → Component → Class → Method) or an optional remote API. |
| Interactive HTML Wiki Storage      | Output is rendered as a standalone static HTML website (`wiki/`) with collapsible navigation trees, breadcrumbs, search, and dynamic symbol cross-hyperlinking.                                          |
| AST-Driven Toolset                 | The system provides analysis tools: `scan_structure`, `save_structure`, `read_file`, `parse_java_ast`, `parse_csharp_ast`, `build_import_graph`, and `summarize`.                                      |
| Architecture & Module Extraction   | Code structures are identified via language-specific AST parsers (Java & C#) and symbol table indices. The LLM generates concise descriptions guided by AST skeletons.                                |

The overall design remains focused and deterministic. The workflow is executed in a single CLI run, persists a single `graph.json` knowledge graph, and outputs a complete static HTML documentation site.

## Business Purpose

Help developers understand and maintain unfamiliar repositories through a single CLI command while allowing source code to remain on the local machine unless the user explicitly chooses to use a remote LLM.

## Current Repository Status

Current observations include:

- Empty project directories such as `agents/`, `graphs/`, `indexes/`, `output/`, `packages/`, `repositories/`, and `wiki/`.
- A vendored research corpus containing approximately **15,403** files.
- A vendored template library containing approximately **26,892** files.
- Comprehensive technical design specifications under `docs/designs/` for Java/C# AST parsing, HTML Wiki storage, and hierarchical SLM prompting.

## Summary

RepoAtlas is currently in the **preparation and research stage**. The system is designed to execute via one CLI command, parse code using language-specific AST drivers (Java & C#), construct a knowledge graph (`graph.json`), perform hierarchical bottom-up summarization using local SLMs, and render a self-contained interactive static HTML wiki site.
