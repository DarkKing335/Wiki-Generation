# RepoAtlas Documentation Index

This is the official architecture & product handbook cross-linked to cover the **current repository state** of the `RepoAtlas/` project in this workspace.

> **Read first.** RepoAtlas is currently a **scaffolding-stage** workspace: it contains no product code, only an empty module taxonomy, a vendored research corpus (`research/`), and a template library (`templates/`). Wherever a capability is not yet implemented, this handbook explicitly marks it **Not Determined** rather than inventing behavior.

## Alignment of Core Concepts

For the **intended** domain vocabulary (Repository, Index, Knowledge Graph, Harness, Agent, Artifact, Workspace), see the authored design doc `vision.md`.

## Document Map

| # | Document | Content | Status of evidence |
|---|---|---|---|
| 1 | `vision.md` | Product vision & Core Concepts (authored design) | Authored (aspirational) |
| 2 | `executive-summary.md` | Project overview, business purpose, stack, structure | Grounded (as-is) |
| 3 | `system-overview.md` | Intended system & data flow (authored design) | Authored (aspirational) |
| 4 | `architecture.md` | System, component, module, domain, deployment, runtime, flows | Grounded (as-is) |
| 5 | `repository-analysis.md` | Structure, build, framework, config, entry points, deps | Grounded (as-is) |
| 6 | `product.md` | Product vision (inferred), FR/NFR, personas, capabilities | Inferred |
| 7 | `epics.md` | 6 Epics (goal/scope/value/areas/criteria/dependencies) | Inferred |
| 8 | `user-stories.md` | User stories mapped to each Epic | Inferred |
| 9 | `adrs.md` | 5 architecture decision records | Inferred/Observed |

## Reading Order

1. Start with `executive-summary.md` (facts).
2. Read `vision.md` + `system-overview.md` for the intended product (design).
3. Read `repository-analysis.md` + `architecture.md` for the as-built truth.
4. Use `epics.md` → `user-stories.md` as the backlog groundwork.
5. `adrs.md` records the decisions made so far.

## Verification Note

Every "Determined" claim is traceable to folders/commits in `RepoAtlas/`. Every "Inferred" or "Not Determined" claim is labelled so that future work can confirm it.