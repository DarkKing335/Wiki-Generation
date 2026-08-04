# RepoAtlas — Executive Summary

## Project Overview

**RepoAtlas** is a lightweight CLI tool that analyzes a repository (provided as a local path or repository URL) and generates a wiki consisting of exactly **four documents**: **Tech**, **Tests**: **Architecture**, and **Modules**. The wiki is produced from a knowledge graph built using a fixed set of **five tools**. The LLM used for summarization can run **locally** by default or use a remote API if configured.

At the time of this analysis, the `/RepoAtlas/` repository contains no product implementation. It currently consists of the project scaffolding, a vendored research corpus, a vendored template library, and the project design documentation.

## Key Design

| Component                          | Description                                                                                                                                                                                               |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local or remote LLM                | The `summarize` tool uses a local LLM endpoint by default and can optionally use a remote API through a single configuration setting.                                                                     |
| Fixed wiki                         | The generated wiki always contains four documents: Tech, Tests, Architecture, and Modules.                                                                                                                |
| Fixed toolset                      | The system provides five tools: `scan_structure`, `save_structure`, `read_file`, `build_import_graph`, and `summarize`.                                                                                   |
| Architecture and module extraction | Repository structure is identified through heuristic clustering based on directory layout and import graph density. The LLM is responsible only for generating descriptions of the identified components. |

The overall design intentionally remains small and focused. The workflow is executed in a single CLI run, persists only a single `graph.json` knowledge graph, and does not include a repository catalog, background refresh process, plugin system, or API/Gateway layer.

## Business Purpose

Help developers understand and maintain unfamiliar repositories through a single CLI command while allowing source code to remain on the local machine unless the user explicitly chooses to use a remote LLM.

## Current Repository Status

Current observations include:

- Empty project directories such as `agents/`, `graphs/`, `indexes/`, `output/`, `packages/`, `repositories/`, and `wiki/`.
- A vendored research corpus containing approximately **15,403** files.
- A vendored template library containing approximately **26,892** files.
- A single staged Git commit.

## Summary

RepoAtlas is currently in the **preparation and research stage**. The project is intentionally limited to one CLI command, five fixed tools, one knowledge graph (`graph.json`), four generated wiki documents, and a single configuration option for selecting the summarization mode (local LLM, remote LLM, or no LLM).
