# RepoAtlas — MVP Documentation

RepoAtlas is a small tool that reads a source repository and turns it into documentation a human doesn't have to write by hand. The MVP has one job: read the code, understand it well enough to describe it accurately, and produce two documents from that understanding.

## What the MVP delivers

1. **Tech Docs** — a technical description of the codebase, split into:
   - **Architecture** — the overall shape of the system: which modules exist and how they depend on each other.
   - **Modules** — a closer look at each module on its own: what it does, its main pieces, and how those pieces fit together.
2. **Test Docs** — a description of the existing test suite: what's tested, where the tests live, and which part of the codebase each test covers.

A third document, a short **Project Overview**, is nice to have but not required — it can ship with the MVP or be skipped without holding anything back.

## Documents in this set

| File              | What's in it                                                                                          |
| ----------------- | ----------------------------------------------------------------------------------------------------- |
| `vision.md`       | Why this exists, what the MVP actually covers, what's left for later                                  |
| `architecture.md` | How the tool works internally — the tools it uses and the pipeline that turns code into documentation |
| `epics.md`        | The work broken into epics                                                                            |
| `user-stories.md` | The epics broken into concrete stories                                                                |

## Reading order

Start with `vision.md` to get the scope, then `architecture.md` to see how it's built, then `epics.md` and `user-stories.md` as the backlog.
