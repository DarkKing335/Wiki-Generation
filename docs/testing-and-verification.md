# Testing & Verification

How to check that the backend works, ordered fastest-first. Each level takes
longer and proves more. Levels 1 and 2 need no model at all.

All commands run from `backend/`.

---

## Setup

```bash
cd backend
pip install -r requirements.txt
pip install -e .
```

The editable install is what puts `core_indexing` and `ai_analysis` on the import
path. Without it `pytest` still works — `pyproject.toml` sets `pythonpath =
["src"]` — but `python -m core_indexing` fails with `No module named
core_indexing`. Install once and both work.

Optional, for levels 3 and 4:

```bash
ollama pull qwen2.5-coder:7b-instruct-q2_K   # summarization
ollama pull nomic-embed-text                  # search_summaries
```

See [Choosing a model](#choosing-a-model) before pulling — the model that fits
depends on your hardware, and the obvious choice is often not the right one.

---

## Level 1 — Unit suite (~10s, no model)

The everyday check. Run it after any change and before every commit.

```bash
python -m pytest tests/ -q -m "not live"
```

Expected — a fixed number, independent of whether Ollama is running:

```
272 passed, 11 deselected
```

Use this form in scripts and CI. A plain `python -m pytest tests/ -q` also works,
but its count *varies with your environment*: the 11 live tests skip when no
model is reachable, and some pass when one is. With Ollama running and
`nomic-embed-text` pulled you will see `273 passed, 10 skipped`, because the
embedding test can run while the summarization ones cannot. Neither is a
failure — but only the `-m "not live"` form gives a number you can compare
against.

This level proves five of the six acceptance gates — see
[What each gate proves](#what-each-gate-proves).

---

## Level 2 — Pipeline end to end (~5s, no model)

Proves the two CLIs actually compose, which unit tests do not cover.

```bash
python -m core_indexing tests/fixtures/sample_repo -o indexes/
python -m ai_analysis indexes/ -o analysis/ --no-llm
```

Three lines matter in the output:

```
Taxonomy (heuristic): 2 module(s), 3 container(s), 4 component(s), 7 class(es), 18 method(s)
All prompts within budget (US-3.5)
Generated 35 summaries
```

> **If you see `1 module(s), 1 container(s)`** — build-file detection failed.
> The heuristic provider could not find `pom.xml` / `*.csproj`, so it collapsed
> the repository into a single container. Tiers 2 and 3 are meaningless in that
> state even though the run "succeeds".

---

## Level 3 — With a real model (~2.5 min)

```bash
python -m ai_analysis indexes/ -o analysis/ --model qwen2.5-coder:7b-instruct-q2_K
```

The line that matters:

```
Ground truth from the model: max 535 tokens over 29 prompt(s)
```

That is the model's own tokenizer confirming prompts really are under the 2,000
ceiling — not an estimate.

> **If that line is missing**, the run silently fell back to structural mode.
> Look above it for `falling back to structural mode`, which means the health
> check failed or the model would not load.

Inspect what was actually generated:

```bash
python -c "import json; d=json.load(open('analysis/summaries.json',encoding='utf-8')); \
print(next(s['summary'] for s in d['summaries'] if s['tier']==1))"
```

Reading the repository summary is the one check no test can perform. A pipeline
can pass every assertion and still produce nonsense.

---

## Level 4 — Measurement gates (~3 min, needs a model)

```bash
REPOATLAS_LIVE_MODEL=qwen2.5-coder:7b-instruct-q2_K \
  python -m pytest tests/test_ollama_live.py -v -m live
```

Free ~2 GB of RAM first (close browsers) or the model will not load — you get
skips with an explanatory reason, not failures.

This is the only level that can validate the offline token estimator, because it
is the only one that sees Ollama's real `prompt_eval_count`.

Measured on a 4 GB RTX 3050 laptop with `qwen2.5-coder:7b-instruct-q2_K`:

| Metric | Value |
|---|---|
| Prompts measured | 29 |
| Max real prompt tokens | 327 (budget 2000) |
| Mean real prompt tokens | 235 |
| Nodes summarized | 35 |
| Total wall clock | 180s |
| Module summary mean | 9.12s (budget 10s) |

---

## What each gate proves

| Gate | Requirement | Proven by | Status |
|---|---|---|---|
| Every prompt < 2,000 tokens | US-3.5, FR-15 | `test_tokens.py` | Pass |
| Estimator never under-reports | US-3.5 | `test_ollama_live.py` | Pass |
| Zero chunks split across AST boundaries | `epics.md` Epic 3 | `test_chunker.py` | Pass |
| Pipeline completes with no LLM | US-3.2, FR-9 | `test_no_llm.py` | Pass |
| Summary at every tier | Epic 2/4 handoff | `test_no_llm.py` | Pass |
| Module summary < 10s | `product.md`:31 | `test_ollama_live.py` | Pass (marginal) |
| Identical input → identical output | `product.md`:33 | `test_reproducibility.py` | Pass structural, **fails with LLM** |

### The known reproducibility failure

`test_two_live_runs_agree` fails on split CPU/GPU inference. This is **not a
code defect** — `llm/ollama.py` correctly pins `temperature=0`, `top_p=1`,
`top_k=1` and a fixed `seed`, and `test_reproducibility.py` guards all four.

The cause is below that layer: when Ollama splits a model across CPU and GPU,
floating-point reduction order is not stable between runs. Logits differ in the
last bits, and under greedy decoding a near-tie flips the chosen token.

Two things make it visible here specifically:

1. **Long generations are exposed.** Aggregating tiers generate 100–200 words;
   Class and Method generate 40–60. More tokens means more chances at a near-tie
   — which is why divergence only ever appears at Component tier and above.
2. **Bottom-up aggregation amplifies it.** One changed summary rewrites every
   ancestor's prompt, so a single flip propagates to the repository summary.

Full GPU offload should resolve it; verify on hardware with ≥8 GB VRAM. Until
then, reproducibility holds in `--no-llm` mode and is best-effort with a model.

---

## Choosing a model

The default `DEFAULT_MODEL` in `llm/ollama.py` is `qwen2.5-coder:7b`, which is
what the requirements target. It needs roughly 6 GB of free VRAM.

On smaller cards, use a lower-bit build of the **same 7B model** — parameter
count is what the requirement names, not bit width — and pass it with `--model`
rather than changing the default.

Measured on a 4 GB RTX 3050 laptop with 7.7 GB system RAM:

| Build | Size | Result |
|---|---|---|
| `qwen2.5-coder:7b` (q4_K_M) | 4.7 GB | Will not load — 2.0 GB short on VRAM, 2.53 GB short on pinned RAM |
| `qwen2.5-coder:7b-instruct-q3_K_S` | 3.5 GB | **Broken build** — CUDA kernel init fails regardless of free memory |
| `qwen2.5-coder:7b-instruct-q2_K` | 3.0 GB | **Works** — 33% CPU / 67% GPU split |

Note that `num_ctx` is pinned to 4096 (`DEFAULT_NUM_CTX`), sized to the 2,000
token budget plus generation headroom. Raising it reserves KV cache no prompt can
use and can prevent the model from loading at all.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Invalid value (at line N)` before any test runs | `pyproject.toml` is malformed — usually merge damage. It must contain exactly one `[project]` table and one `build-backend`. |
| `ModuleNotFoundError` on collection | `pip install -r requirements.txt` |
| `Ollama returned 500... Is it pulled?` | Misleading message. Almost always an out-of-memory failure, not a missing model. Get the real error with the `curl` below. |
| Live tests all skip | Model unreachable or will not load. The skip reason names which. |
| `test_the_estimator_never_under_reports` fails | Serious. Every offline token test is measuring the wrong thing; the safety margin in `tokens.py` is insufficient for this tokenizer. |
| Any `test_chunker` boundary test fails | A chunk is straddling an AST node — the core guarantee is broken. |
| `test_two_live_runs_agree` fails | Expected on split CPU/GPU inference. See [above](#the-known-reproducibility-failure). Not your bug. |
| Dozens of `.pyc` files show as modified | `__pycache__` was committed before `.gitignore` covered it. Untrack with `git rm -r --cached <path>/__pycache__`. |

Getting Ollama's real error, which the client message hides:

```bash
curl -s -X POST http://localhost:11434/api/chat \
  -d '{"model":"MODEL","messages":[{"role":"user","content":"ok"}],"stream":false}'
```

Typical answers: `cudaMalloc failed: out of memory` (VRAM), `failed to allocate
CUDA_Host buffer` (system RAM — close browsers), `CUDA error: shared object
initialization failed` (broken quantization, try a different build).

---

## Operational notes

- **Keep ~2 GB of RAM free.** A run can fail purely because a browser restarted.
  At 1.1 GB free the model will not load; at 2.1 GB it is fine.
- **First call costs 11–40s of cold load.** Ollama unloads after ~5 minutes idle,
  so a fresh run pays it again. Not a bug.
- **Runtime scales with node count, not repository size** — that is the point of
  hierarchical chunking. A 35-node repository takes ~2.5 minutes.
