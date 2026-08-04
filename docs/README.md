# RepoAtlas Documentation Index

## Document Map

| #   | Document                 | Content                                                                       |
| --- | ------------------------ | ----------------------------------------------------------------------------- |
| 1   | `vision.md`              | Vision, principles, the 4 wiki documents, local-first LLM                     |
| 2   | `executive-summary.md`   | Intended system & data flow (authored design)                                 |
| 3   | `system-overview.md`     | Pipeline, the 5 tools, local/remote LLM, how Architecture/Modules are derived |
| 4   | `architecture.md`        | System/component/module view, as-is + intended design                         |
| 5   | `repository-analysis.md` | Structure, build, deps — as observed                                          |
| 6   | `product.md`             | FR/NFR, personas, capabilities                                                |
| 7   | `epics.md`               | 5 Epics                                                                       |
| 8   | `user-stories.md`        | Stories per Epic, including local/remote/no-LLM cases                         |
| 9   | `adrs.md`                | 9 ADRs (fixed 4-doc/5-tool scope)                                             |

## Reading Order

1. `executive-summary.md` — facts + what's new in project.
2. `vision.md` + `system-overview.md` — intended design.
3. `repository-analysis.md` + `architecture.md` — as-built truth.
4. `epics.md` → `user-stories.md` — backlog.
5. `adrs.md` — decisions, including why scope stays fixed at 4 docs / 5 tools.

## Guiding Constraint for This Version

Every design document in this set is written to keep RepoAtlas **small on purpose**: a fixed toolset, a fixed document set, one config switch for the LLM, and no service layer. If a future need doesn't fit, the right move is to write a new ADR explaining why the scope grows — not to expand silently.
