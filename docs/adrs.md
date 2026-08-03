# RepoAtlas — Architecture Decision Records (ADR)

> **Honesty notice:** RepoAtlas contains **no ADR files** in its own tree. The decisions below are **inferred from observable repository evidence** (folder taxonomy, git state, vendored content). Each record names the evidence that supports the inference. They are reconstruction, not official records.

## ADR-001: Module Taxonomy as Physical Folders

**Context** — Before any code exists, the repository already defines a fixed, single-repo folder taxonomy: `agents/`, `graphs/`, `indexes/`, `output/`, `packages/`, `repositories/`, `wiki/`. This is the earliest observable architectural statement of the intended system boundaries.

**Decision** — Adopt a monorepo-style physical folder taxonomy matching the product's domain: input (`repositories`), index (`indexes`), knowledge (`graphs`), automation (`agents`), sharing (`packages`), and outputs (`wiki`, `output`).

*Evidence: the seven empty directories exist at the root of `RepoAtlas/`.*

**Alternatives**
- Single flat source tree (no domain folders).
- Multi-repo (each module a separate git repo).
- Fully package-managed monorepo with workspace manifests (pnpm/turbo) from day one.

**Consequences** — Positive: boundaries are explicit; the taxonomy is easy to explain and matches the Vision. Negative: no package manifests or workspace tooling exist yet, so the taxonomy is nominal; naming drift would be easy to bake in before code arrives; a "Harness" concept (see ADR-002) has no folder, exposing a gap in the taxonomy.

## ADR-002: Harness Concept Absent from Taxonomy

**Context** — The authored design docs (`docs/vision.md`) explicitly define **Harness** as a core concept ("reusable execution capability for repository analysis"). The physical taxonomy does **not** contain a harness folder; `agents/` is the only automation placeholder.

**Decision** — (Inferred) Harness is treated as part of the Agent/automation layer rather than a first-class top-level module, at least at scaffolding stage.

*Evidence: `agents/` exists; no `harnesses/` (or `harness/`) folder exists anywhere under `RepoAtlas/`.*

**Alternatives**
- A dedicated top-level `harnesses/` folder mirroring the Vision's Core Concepts.
- Embedding harnesses as nested data/blueprints inside `agents/`.
- No explicit harness concept (rejected: contradicts `docs/vision.md`).

**Consequences** — If the intended Harness framework is meant to be independently reusable, the missing folder signals a **design taxonomy gap** that should be resolved before implementation. Documenting this now prevents the "explain the term again in every doc" problem the Vision warns about.

## ADR-003: Research-First Approach (Vendored Reference Corpus)

**Context** — `research/projects/` contains full clones of eight third-party repository-intelligence projects: `CodeWiki`, `Understand-Anything`, `sourcebridge`, `llm_wiki`, `ExplainThisRepo`, `Lingma-SWE-GPT`, `RepoUnderstander`, and `4604aedabac6de04be003694c5ceec5d` (llm-codekb note). `research/notes/` and `research/papers/` are empty placeholders.

**Decision** — (Inferred) The project adopts a **research-first strategy**: comprehensively study and reuse reference implementations before building, using a vendored local corpus rather than only remote lookups.

*Evidence: 15,403 files of third-party code committed under `research/`; empty `notes/` and `papers/` folders reserved for synthesis.*

**Alternatives**
- Build without prior-art study (faster to start, higher risk of repeating known pitfalls).
- Maintain only web bookmarks (no local corpus).
- Fork/upstream contributions directly (no local copy).

**Consequences** — Positive: rich source of patterns and lessons for the future Harness/Agent design; enables offline study. Negative: large vendored corpus (15k+ files) bloats the repo, duplicates license/third-party dependency surfaces, and must be tracked for provenance/licensing. It also means most of the "code" in the repo is not RepoAtlas's.

## ADR-004: UI/UX Scaffolding Reuse via Template Stock

**Context** — `templates/` contains 26,892 files of web scaffolding: `ui/chakra-ui`, `ui/mantine`, `ui/tremor`, `ui/ui` (shadcn-style), `architecture/analog`, `architecture/nx-examples`, `dashboard/payload`, `react/examples`.

**Decision** — (Inferred) Reuse mature, community UI/framework templates as the base for any future RepoAtlas interfaces instead of authoring bespoke frontends from scratch.

*Evidence: `templates/` tree of vendored template packs.*

**Alternatives**
- Build a custom UI from scratch (slower, more control).
- No UI planning at this stage (contradicts future product needs).

**Consequences** — Positive: fast start for the future Wiki/console surfaces; proven patterns. Negative: heavy template debt, duplicated dependencies; needs careful curation so templates don't become "accidental architecture" for the product.

## ADR-005: Single Git Repository, Single Commit, Everything Staged

**Context** — `git log` shows exactly one commit (`05b89a0 first commit`). `git status` shows all vendored directories staged (`A`) but **uncommitted**; the `docs/` design files at workspace root are untracked.

**Decision** — (Inferred) Keep all phases — scaffolding, research corpus, templates — in **one repository** under a single root, and stage content incrementally rather than committing mixed-purpose changes.

*Evidence: `git log --oneline` → 1 commit; `git status -s` → all `A` entries for vendored dirs, `??` for `docs/`.*

**Alternatives**
- Separate repos for research vs product (better isolation, more overhead).
- Commit everything in one atomic commit (simpler history, noisier).
- Git-LFS / submodules for vendored content (smaller repo, added tooling).

**Consequences** — Positive: simple, transparent history; easy to reason about the workspace. Negative: 42k+ staged files make the index heavy; a single-commit history is opaque about provenance; mixing third-party and future first-party code in one tree complicates licensing and code review. Recommend revisiting this decision once product code begins.

---

## ADR Summary

| ADR | Topic | Evidence | Type |
|---|---|---|---|
| 001 | Folder taxonomy | seven root folders | Inferred |
| 002 | No harness folder | absent `harnesses/` vs `docs/vision.md` | Inferred |
| 003 | Research-first | `research/projects/` 15k files | Inferred |
| 004 | UI template reuse | `templates/` 27k files | Inferred |
| 005 | Single-repo/staged | git log + status | Observed |

> None of these are recorded in a formal `adr/` directory inside the project; this document is the reconstruction and should be relocated/renamed as the project's formal ADR log when the repo matures.