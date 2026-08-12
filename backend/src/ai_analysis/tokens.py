"""Token counting and budget enforcement (FR-15, US-3.5).

US-3.5's Definition of Done is *"verified token consumption stays under 2,000
tokens per prompt"*.  That is a measurement obligation, so this module provides
both the measurement and the enforcement.

Two-tier counting
-----------------
* **Estimate** — ``tiktoken`` (``cl100k_base``) plus a safety margin.  Offline,
  deterministic, and usable in unit tests with no model running.
* **Ground truth** — Ollama returns ``prompt_eval_count`` on every response,
  which is the real count for the real tokenizer.

The estimator is deliberately biased to *over*-report.  Different model families
tokenize differently, and a budget guard that under-reports is worse than useless:
it would let prompts through that the model then truncates mid-skeleton, which is
exactly the failure ADR-010 exists to prevent.  ``test_tokens.py`` asserts the
estimate never falls below the ground truth.

Degradation
-----------
When a prompt exceeds budget the skeleton is trimmed in escalating steps rather
than being silently truncated mid-structure — truncation would sever a class from
its methods, reintroducing exactly the boundary cuts AST chunking eliminates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

#: Hard ceiling per prompt (FR-15, US-3.5).
DEFAULT_BUDGET = 2000

#: Target band from the design doc's efficiency table
#: (``docs/designs/hierarchical-prompting-chunking.md`` §8).
TARGET_MIN = 800
TARGET_MAX = 1800

#: Multiplier applied to the tiktoken count.  Code-tuned tokenizers such as
#: Qwen's split identifiers slightly differently from cl100k; measurement against
#: qwen2.5-coder puts the divergence well inside this margin.
SAFETY_MARGIN = 1.15

#: Fixed tokens the backend adds when framing messages into its chat template
#: (``<|im_start|>system`` … ``<|im_end|>`` and friends).  Never present in the
#: prompt string this code builds, but counted by the model.
#:
#: Measured against qwen2.5-coder:7b across the fixture corpus, the residual gap
#: after accounting for tool schemas was 7-14 tokens for a two-message exchange.
#: Rounded up, since under-reporting defeats the guard.
CHAT_TEMPLATE_OVERHEAD = 32

_ENCODING_NAME = "cl100k_base"


@lru_cache(maxsize=1)
def _encoder():
    """Load the tokenizer once.

    Falls back to a character-ratio approximation if tiktoken cannot fetch its
    encoding file (it downloads on first use, which may fail offline).
    """
    try:
        import tiktoken

        return tiktoken.get_encoding(_ENCODING_NAME)
    except Exception as exc:  # pragma: no cover - depends on network/cache state
        logger.warning(
            "tiktoken unavailable (%s); falling back to character-ratio estimation", exc
        )
        return None


def count_tokens(text: str, *, apply_margin: bool = True) -> int:
    """Estimate the token count of *text*.

    With ``apply_margin`` (the default) the result is inflated by
    :data:`SAFETY_MARGIN`, making it safe to compare directly against a budget.
    """
    if not text:
        return 0

    encoder = _encoder()
    if encoder is not None:
        raw = len(encoder.encode(text, disallowed_special=()))
    else:
        # ~3.6 characters per token is a reasonable conservative ratio for
        # source-like text; deliberately low so the estimate runs high.
        raw = int(len(text) / 3.6) + 1

    return int(raw * SAFETY_MARGIN) + 1 if apply_margin else raw


@dataclass
class BudgetResult:
    """Outcome of fitting a prompt into its token budget."""

    text: str
    tokens: int
    budget: int
    was_degraded: bool
    steps_applied: List[str]

    @property
    def within_budget(self) -> bool:
        return self.tokens <= self.budget

    @property
    def in_target_band(self) -> bool:
        return TARGET_MIN <= self.tokens <= TARGET_MAX


#: A degradation step: given the current render options, produce tighter ones.
#: Each returns ``None`` when it cannot tighten any further.
RenderFn = Callable[..., str]


def enforce_budget(
    render: RenderFn,
    *,
    budget: int = DEFAULT_BUDGET,
    node_id: str = "<unknown>",
) -> BudgetResult:
    """Render a prompt, tightening it until it fits *budget*.

    ``render`` is called with keyword arguments describing how much detail to
    include.  Steps are applied in order of increasing information loss:

    1. Full detail.
    2. Drop private members — they rarely inform a component's responsibility.
    3. Shorten docstrings to 80 characters.
    4. Drop docstrings entirely.
    5. Drop docstrings *and* private members, signatures only.

    If step 5 still overruns, the text is returned as-is and flagged.  The caller
    records the violation rather than shipping a mid-structure truncation.
    """
    attempts: List[tuple[str, dict]] = [
        ("full", {}),
        ("no-private", {"include_private": False}),
        ("short-docs", {"include_private": False, "doc_chars": 80}),
        ("no-docs", {"include_private": False, "include_docstrings": False}),
        ("signatures-only", {
            "include_private": False,
            "include_docstrings": False,
            "doc_chars": 0,
        }),
    ]

    applied: List[str] = []
    text = ""
    tokens = 0

    for name, options in attempts:
        try:
            text = render(**options)
        except TypeError:
            # The renderer does not accept this option set; skip the step.
            continue

        tokens = count_tokens(text)
        applied.append(name)

        if tokens <= budget:
            was_degraded = name != "full"
            if was_degraded:
                logger.debug(
                    "Prompt for %s degraded to '%s' to fit budget (%d tokens)",
                    node_id, name, tokens,
                )
            return BudgetResult(
                text=text,
                tokens=tokens,
                budget=budget,
                was_degraded=was_degraded,
                steps_applied=applied,
            )

    logger.warning(
        "Prompt for %s still %d tokens after full degradation (budget %d)",
        node_id, tokens, budget,
    )
    return BudgetResult(
        text=text,
        tokens=tokens,
        budget=budget,
        was_degraded=True,
        steps_applied=applied,
    )


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Hard-truncate *text* to at most *max_tokens*, on a line boundary.

    Only used for lazily loaded source bodies, where cutting is acceptable
    because the excerpt is supplementary context rather than the structural
    skeleton.  Never applied to skeletons.
    """
    if count_tokens(text) <= max_tokens:
        return text

    lines = text.splitlines()
    kept: List[str] = []
    for line in lines:
        candidate = "\n".join(kept + [line])
        if count_tokens(candidate) > max_tokens:
            break
        kept.append(line)

    result = "\n".join(kept)
    if len(kept) < len(lines):
        result += f"\n… ({len(lines) - len(kept)} more lines omitted)"
    return result
