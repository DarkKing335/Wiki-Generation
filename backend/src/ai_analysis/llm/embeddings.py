"""Embeddings for Overview-First Retrieval.

``docs/designs/hierarchical-prompting-chunking.md`` §6 specifies that retrieval
searches top-level summaries first, locating the relevant region of the codebase
before drilling into low-level AST nodes.  This module provides the semantic
search behind the ``search_summaries`` tool.

Uses ``nomic-embed-text`` via Ollama's ``/api/embeddings``.  Degrades to
substring matching when embeddings are unavailable, so retrieval keeps working
with no model and no network — consistent with US-3.2's requirement that a
missing model never interrupts execution.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

import httpx

from ai_analysis.llm.ollama import DEFAULT_ENDPOINT

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL = "nomic-embed-text"


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two vectors; ``0.0`` if either has no magnitude."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingClient:
    """Embeds text via Ollama, with a keyword fallback."""

    def __init__(
        self,
        model: str = DEFAULT_EMBED_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        enabled: bool = True,
        timeout: float = 60.0,
        client: Optional[httpx.Client] = None,
    ):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.enabled = enabled
        self._timeout = timeout
        # Created lazily: building an httpx.Client sets up an SSL context, which
        # is wasted work for an offline client that never sends a request.
        self._client = client
        self._owns_client = client is None
        self._cache: Dict[str, List[float]] = {}
        self._available: Optional[bool] = None if enabled else False

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    @classmethod
    def offline(cls) -> "EmbeddingClient":
        """A client that never touches the network and always keyword-ranks.

        Used by the no-LLM path (US-3.2) and by unit tests, so neither depends on
        a running Ollama server.
        """
        return cls(enabled=False)

    @property
    def available(self) -> bool:
        """Whether the embedding model responds.  Probed once, then cached."""
        if self._available is None:
            self._available = self.embed("probe") is not None
            if not self._available:
                logger.info(
                    "Embedding model '%s' unavailable; search_summaries will use "
                    "keyword matching",
                    self.model,
                )
        return self._available

    def embed(self, text: str) -> Optional[List[float]]:
        """Embed *text*, or return ``None`` if embeddings are unavailable."""
        if not self.enabled:
            return None

        cached = self._cache.get(text)
        if cached is not None:
            return cached

        try:
            response = self.client.post(
                f"{self.endpoint}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            response.raise_for_status()
            vector = response.json().get("embedding")
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Embedding request failed: %s", exc)
            return None

        if not vector:
            return None

        self._cache[text] = vector
        return vector

    def rank(
        self,
        query: str,
        candidates: Sequence[Tuple[str, str]],
        *,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """Rank ``(identifier, text)`` candidates against *query*.

        Returns ``(identifier, score)`` pairs, highest first.  Falls back to
        keyword overlap when embeddings are unavailable.
        """
        if not candidates:
            return []

        query_vector = self.embed(query) if self.available else None
        if query_vector is None:
            return self._keyword_rank(query, candidates, top_k=top_k)

        scored: List[Tuple[str, float]] = []
        for identifier, text in candidates:
            vector = self.embed(text)
            if vector is None:
                continue
            scored.append((identifier, cosine_similarity(query_vector, vector)))

        if not scored:
            return self._keyword_rank(query, candidates, top_k=top_k)

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    @classmethod
    def _keyword_rank(
        cls,
        query: str,
        candidates: Sequence[Tuple[str, str]],
        *,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """Score by term overlap, matching on a 4-character stem.

        Exact word matching is too brittle for a fallback — a query for "card
        payment" would miss a summary saying "charges cards". Comparing on a
        short prefix absorbs the common English inflections (plurals, -ing/-es)
        without pulling in a stemming dependency.
        """
        terms = cls._words(query)
        if not terms:
            return [(identifier, 0.0) for identifier, _ in candidates[:top_k]]

        scored: List[Tuple[str, float]] = []
        for identifier, text in candidates:
            words = cls._words(text)
            matched = sum(1 for term in terms if cls._matches_any(term, words))
            if matched:
                scored.append((identifier, matched / len(terms)))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    #: Words shorter than this are ignored as too generic to discriminate.
    _MIN_TERM = 3

    #: Prefix length used for stem comparison.
    _STEM = 4

    @staticmethod
    def _words(text: str) -> set:
        """Lowercased alphanumeric words, splitting on dots for FQNs."""
        return {
            word
            for word in re.split(r"[^a-z0-9]+", text.lower())
            if len(word) >= EmbeddingClient._MIN_TERM
        }

    @classmethod
    def _matches_any(cls, term: str, words: set) -> bool:
        if term in words:
            return True
        stem = term[: cls._STEM]
        if len(term) < cls._STEM:
            return False
        return any(word.startswith(stem) for word in words)

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
