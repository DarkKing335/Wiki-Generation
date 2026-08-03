# RepoAtlas — User Stories (inferred)

> Every User Story is **inferred from the Epics** (which themselves are inferred from the empty folder taxonomy and the authored design docs). Implementation is **Not Determined**. Each story carries a **Technical Notes** section that reflects today's observable repo state.

## Epic 1 — Repository Ingestion & Management

### US-1.1 Register a repository
- **As a** platform engineer, **I want** to add a repository to a Workspace, **so that** RepoAtlas can analyze it and I can manage my fleet in one place.
- **Acceptance Criteria:**
  - A repository can be added with a unique identifier.
  - The repository appears in the managed set with its VCS origin.
  - Adding a duplicate or invalid target is rejected with a clear message.
- **Technical Notes:** Target module `repositories/`; currently **empty — not implemented**.
- **Definition of Done:** Add flow works end-to-end (CLI or API); tests cover success + failure paths; docs updated.

### US-1.2 List and remove repositories
- **As a** platform engineer, **I want** to list and remove repositories, **so that** I can keep the Workspace accurate.
- **Acceptance Criteria:** Listing shows all managed repos; removal detaches downstream data with confirmation; removal is idempotent.
- **Technical Notes:** `repositories/` is an empty placeholder today.
- **Definition of Done:** CRUD covered by tests; behavior documented.

## Epic 2 — Repository Indexing

### US-2.1 Index a repository into structured metadata
- **As a** platform engineer, **I want** to run indexing on a repository, **so that** files, symbols, and dependencies become queryable.
- **Acceptance Criteria:** Indexing produces structured entities; re-indexing after code change reflects deltas; partial failures are reported per-file.
- **Technical Notes:** Target module `indexes/`; currently **empty — not implemented**.
- **Definition of Done:** Index produced, stored, queryable; delta re-index tested.

### US-2.2 Query the index
- **As a** software engineer, **I want** to query the index by symbol/path/type, **so that** I can locate code fast.
- **Acceptance Criteria:** Symbol, path, and type queries return correct matches; results include file/line references.
- **Technical Notes:** No index query API exists yet.
- **Definition of Done:** Query API tested; example queries in docs.

## Epic 3 — Knowledge Graph

### US-3.1 Load index into the knowledge graph
- **As a** architect, **I want** the index to feed the graph, **so that** entities and relationships are canonical and queryable.
- **Acceptance Criteria:** Nodes/edges created from index; schema validated; provenance recorded.
- **Technical Notes:** Target `graphs/`; currently **empty**.
- **Definition of Done:** Loader tested against fixtures; provenance fields populated.

### US-3.2 Ask relationship queries
- **As a** software engineer, **I want** to ask "what depends on X" / "who uses Y", **so that** I can assess change impact.
- **Acceptance Criteria:** Correct neighbor/dependency answers; performance acceptable for workspace size; results cite source.
- **Technical Notes:** Graph query surface is **Not Determined**.
- **Definition of Done:** Representative queries tested and benchmarked.

## Epic 4 — AI Agents & Harnesses

### US-4.1 Run an agent using a harness
- **As a** platform engineer, **I want** an agent to run a harness over a repo, **so that** analysis is consistent and reproducible.
- **Acceptance Criteria:** Harness selection automatic by ecosystem; agent produces candidate facts; results are reviewable.
- **Technical Notes:** `agents/` is empty; harness folder does **not exist** (see ADR-002).
- **Definition of Done:** Agent run recorded with traceable provenance.

### US-4.2 Refresh facts on code change
- **As a** platform engineer, **I want** the graph to refresh on deltas, **so that** documentation never goes stale.
- **Acceptance Criteria:** Change detection triggers targeted re-analysis; unchanged facts are retained; refresh is incremental.
- **Technical Notes:** No scheduler exists yet.
- **Definition of Done:** Delta test passes; cost/coverage metrics recorded.

## Epic 5 — Wiki & Artifact Generation

### US-5.1 Generate wiki from the graph
- **As a** technical writer, **I want** wiki pages rendered from graph truth, **so that** documentation is current and accurate.
- **Acceptance Criteria:** Pages linkable and navigable; content derived from graph; provenance links shown.
- **Technical Notes:** `wiki/` empty; `templates/` provides candidate rendering scaffolds (shadcn/Next/etc.).
- **Definition of Done:** Sample wiki generated from fixtures; regeneration idempotent.

### US-5.2 Regenerate and publish artifacts
- **As a** platform engineer, **I want** to regenerate artifacts when the graph changes, **so that** the published docs reflect the code.
- **Acceptance Criteria:** Regeneration is on-demand or triggered; output versioned; stale artifacts flagged.
- **Technical Notes:** `output/` empty.
- **Definition of Done:** Versioned artifact history demonstrated.

## Epic 6 — Developer Experience & Packaging

### US-6.1 Initialize and configure RepoAtlas
- **As a** developer, **I want** to install and initialize RepoAtlas, **so that** I can run it on my own infrastructure.
- **Acceptance Criteria:** Installer/CLI works; config validated; first-run guide shown.
- **Technical Notes:** No installers or config exist.
- **Definition of Done:** Fresh-install walkthrough passes.

### US-6.2 Observe runs
- **As a** platform engineer, **I want** logs and metrics for jobs, **so that** I can monitor health and cost.
- **Acceptance Criteria:** Structured logs; job-level metrics; failure surfaced.
- **Technical Notes:** Observability stack **Not Determined**.
- **Definition of Done:** Metrics dashboards/example queries provided.

---

## Story-to-Epic mapping

| Story | Epic |
|---|---|
| US-1.1, US-1.2 | Epic 1 — Ingestion & Management |
| US-2.1, US-2.2 | Epic 2 — Indexing |
| US-3.1, US-3.2 | Epic 3 — Knowledge Graph |
| US-4.1, US-4.2 | Epic 4 — Agents & Harnesses |
| US-5.1, US-5.2 | Epic 5 — Wiki & Artifacts |
| US-6.1, US-6.2 | Epic 6 — DX & Packaging |

> All stories: **Planned**, acceptance criteria are target specs; none verifiable against code today.