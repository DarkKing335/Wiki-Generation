# RepoAtlas — Product (inferred)

> These are **inferences** drawn from the repo's folder taxonomy (`docs/vision.md` and `docs/system-overview.md` intend) and the naming of empty directories. No capability is implemented; statements are classified as **Inferred / Planned** vs **Not Determined**.

## 1. Product Vision (inferred)

**Working vision (from `docs/vision.md`):** *"An AI-powered repository intelligence platform that reads, understands, and evolves software repositories into navigable knowledge using AI, Knowledge Graphs, Harnesses, and AI Agents."*

**Determined intent from folder names** (`graph`, `index`, `agents`, `wiki`): the product is meant to take a repo → an index → a knowledge graph → continuously-maintained wiki/artifacts, driven by agents. Confirmed aspirational, not yet built.

## 2. Functional Requirements (Inferred — NOT implemented)

The taxonomy yields a candidate functional surface. **Status: Not Determined** (no code); these are the *implied* requirements of a future version.

| # | Requirement (inferred) | Implied by | Realized? |
|---|---|---|---|
| FR-1 | Ingest one or more repositories | `repositories/` | — |
| FR-2 | Index repo into structured metadata | `indexes/` | — |
| FR-3 | Build/maintain a knowledge graph | `graphs/` | — |
| FR-4 | Run AI agents over the graph | `agents/` | — |
| FR-5 | Generate wiki artifacts | `wiki/`, `output/` | — |
| FR-6 | Share/manage reusable packages | `packages/` | — |

## 3. Non-functional Requirements (inferred, all **NotDetermined**)

- Extensibility (agents/harnesses), model-agnosticism, incremental-refresh efficiency, observability, security — all stated as design goals in `docs/vision.md` but **not observable in code**.

## 4. Personas (inferred)

| Persona | Goal with RepoAtlas |
|---|---|
| Software Engineer | Understand an unfamiliar repo quickly; find dependencies |
| Architect | See cross-cutting/module structure; review architecture |
| Platform Engineer | Keep documentation fresh automatically |
| Tech Writer | Publish accurate, current wiki artifacts |
| Researcher / Evaluator | (from corpus) compare reference tools, study approaches |

No UI exists; these are **intended users**, not evidenced users.

## 5. Business Capabilities (inferred)

| Capability | Mapped to | Detail |
| Repository Management | `repositories/` | add/manage repos; Workspace grouping |
| Code & Dependency Understanding | `indexes/`, `graphs` | parse, entities, relationships |
| Automated Analysis Agents | `agents/` | ongoing survey/refresh |
| Wiki/Docs Generation | `wiki/`, `output/` | derived artifacts |
| Packaging/Sharing | `packages/` | reusable modules |

### Business capability map

```mermaid
graph LR
    C[Repository Management] -->|feeds| I[Indexing]
    I -->|feeds| G[Knowledge Graph]
    G -->|drives| A[Agents]
    G -->|renders| W[Wiki/Output]
    P[Packaging] -.shared-. FG
```

## 6. Evidence & Confidence

- **Inferred:** business capabilities, personas, FR/NFR list, product intent.
- **Determined: the folder taxonomy** (determined) and the design `docs/vision` & `docs/system-overview` (authored).
- **Not Determined:** all realized behavior, metrics, and performance.

## 7. Summary

The product lives at **Stage: ideation/scaffolding**. One must refrain from claiming a shipped platform turns; instead the doc positions RepoAtlas as cleanly intended but **unbuilt**, with product view sparkline from naming + design docs alone.