# RepoAtlas — Vision

## The problem

Anyone dropping into an unfamiliar repository — a new hire, a reviewer, or the original author six months later — runs into the same two questions: what does this codebase actually look like architecturally, and what does the test suite actually cover? Answering either one by reading code file by file takes hours, and the answer goes stale the moment the code changes again.

RepoAtlas exists to answer those two questions automatically, straight from the source code, so the documentation stays honest instead of drifting away from what the code really does.

## What the MVP is

A tool that scans a repository and produces two documents:

- **Tech Docs**, covering the overall **Architecture** (the modules and how they relate) and a **Modules** breakdown (what each module does on its own).
- **Test Docs**, covering what the existing tests check and which parts of the code they map to.

A short **Project Overview** document is a nice extra on top, but it's optional — it doesn't block the two documents above.

## What's deliberately left out for now

Some ideas that show up in the broader repository-intelligence space are useful directions but not part of this MVP:

- A persistent, cross-repository knowledge graph that stays around between runs.
- A scheduler that re-runs analysis automatically on every commit.
- A dedicated guardrail/policy layer for the tools — for now, quality control is just "every claim points back to a real file" plus a human reading the output before it ships.
- A web UI — the output is markdown for now.
- Routing across multiple LLM providers.

These stay on the table for later; they're just not what "done" means for this version.

## The approach, in short

Understanding a whole repository well enough to describe it accurately is harder than summarizing one file at a time — code that implements one piece of functionality is usually scattered across several files, not laid out sequentially in one place. Systems built for this kind of task (LingmaAgent, RepoUnderstander, and similar work) handle it by first building a structural map of the repository — a hierarchy of files, classes, and functions plus the call relationships between them — and only then summarizing, working from that map instead of reading everything in file order. RepoAtlas follows the same idea at MVP scale: build the structure first, then summarize guided by it, and always keep a pointer back to the exact file/class/function a claim came from.

A few technical questions need answers before this can be built:

- Which LLM to use for summarization.
- Which sample repositories to test the pipeline against — ideally a handful spanning different languages and architectures.
- How to segment a repository into pieces that fit a model's context window without cutting a class or component in half.
- How to reliably pull out an accurate Architecture view and accurate Module boundaries instead of a plausible-sounding but wrong one.

## What success looks like

Given any repository from the sample set, the pipeline produces Tech Docs and Test Docs without manual editing, and everything in those documents can be traced back to a real file, class, or function — nothing invented.
