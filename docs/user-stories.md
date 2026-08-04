# RepoAtlas — User Stories

## Epic 1 — Core toolset

**Scan the project structure**
As someone building the pipeline, I want to scan a repo's full folder/file tree, so I know what's there before analyzing anything. Vendor and build folders (`node_modules`, `.git`, `dist`, etc.) are excluded.

**Build the dependency tree**
As someone building the pipeline, I want the file tree broken down into classes and functions with their call relationships recorded, so later steps can navigate the codebase by structure instead of by guesswork.

**Search within the structure**
As someone building the pipeline, I want to look up a specific class, function, or snippet by name, so I don't have to re-scan the repo for every question.

**Summarize a unit of code**
As someone building the pipeline, I want to summarize a file, class, or function, so I know what it's responsible for. Every summary keeps a reference back to its source location.

**Link module knowledge**
As someone building the pipeline, I want to merge the summaries of the pieces inside one module into a single module-level summary, so the Modules doc reflects a coherent picture of the module instead of a loose list of unrelated snippets.

## Epic 2 — Tech Docs: Architecture

**Generate the architecture overview**
As an engineer or architect, I want an automatically generated Architecture doc, so I can understand the main modules and how they relate without reading the whole codebase. The module list matches reality, the diagram shows real relationships, and every claim traces back to actual files.

## Epic 3 — Tech Docs: Modules

**Summarize each module**
As an engineer, I want a standalone summary for each module — purpose, main pieces, related files — so I know what it does before diving into the code.

**Summarize by component (frontend)**
As a frontend engineer, I want frontend modules broken down component by component, so I can look up a specific component quickly.

**Summarize by MVC (backend)**
As a backend engineer, I want backend modules broken down by Model/View/Controller, so I can follow how a request flows through the system.

## Epic 4 — Test Docs

**List and summarize existing tests**
As an engineer, I want a list of existing tests with short descriptions, so I know what's covered and what isn't. Every test file gets found, and every test/group is described along with the module it maps to.

## Epic 5 — End-to-end workflow

**Run the whole pipeline in one command**
As an operator, I want to run scan → summarize → link → generate as a single command driven by `AGENTS.md`, so I don't have to run each step by hand. One run on a sample repo produces both Tech Docs and Test Docs.

**Configure the LLM and sample repos**
As someone building the pipeline, I want to configure which LLM is used and which repos serve as the test set, so I can evaluate pipeline quality across different kinds of repos before expanding scope. The sample set stays fixed so it can be used as a regression check when the pipeline changes.

## Epic 6 (optional) — Project Overview

**Generate a project overview**
As someone new to the project, I want a short, high-level overview document, so I can understand what the project does before getting into the technical details. Optional — skip if it's competing with the two required documents.

---

## Story-to-epic map

| Story                                                                                                           | Epic              |
| --------------------------------------------------------------------------------------------------------------- | ----------------- |
| Scan structure, Build dependency tree, Search within structure, Summarize a unit of code, Link module knowledge | Epic 1            |
| Generate the architecture overview                                                                              | Epic 2            |
| Summarize each module, Summarize by component, Summarize by MVC                                                 | Epic 3            |
| List and summarize existing tests                                                                               | Epic 4            |
| Run the whole pipeline, Configure LLM and sample repos                                                          | Epic 5            |
| Generate a project overview                                                                                     | Epic 6 (optional) |
