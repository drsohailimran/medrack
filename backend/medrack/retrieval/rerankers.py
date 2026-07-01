"""medrack.retrieval.rerankers — Reranker interface + v1 implementation (Phase 10).

The Reranker is the fourth stage of the pipeline:

    Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator

It receives the chunks returned by the vector index, plus the
original question (and optionally the Blueprint Retrieval spec),
and returns the same chunks in improved relevance order.

The Reranker's single responsibility
--------------------------------------
"Re-order retrieved evidence according to semantic relevance."

What the Reranker does NOT do
----------------------------
- It does not generate text (the writer's job).
- It does not summarize evidence (the writer's job).
- It does not perform planning (the planner's job).
- It does not modify the blueprint (the blueprint is frozen).
- It does not perform validation (the validator's job).
- It does not change metadata (chunks' metadata is preserved as-is).
- It does not perform retrieval (the engine's job).
- It does not implement BM25 or any other IR algorithm — it only
  *re-orders* the chunks the retrieval engine returns.

The Reranker **preserves traceability**: every output chunk carries
its original ``id`` and ``metadata``, so the writer can cite it.

Architecture
------------
A generic :class:`Reranker` ABC defines the interface. v1 ships two
concrete implementations:

  - :class:`IdentityReranker` — no-op pass-through. Returns the
    input chunks in their input order. Useful for A/B testing and
    for disabling reranking entirely (per the directive: "the
    system must still function correctly if reranking is disabled").
  - :class:`HeuristicReranker` — deterministic, side-effect-free
    reranker that combines three signals:
      1. **Embedding similarity** (primary signal) — the existing
         distance from the vector index. Used as the default rank
         when the heuristic signals are neutral.
      2. **Blueprint section relevance** — a chunk whose metadata
         flags include any of the blueprint's
         ``required_metadata_categories`` gets a positive boost.
      3. **Lightweight keyword overlap** — a chunk that shares more
         non-stopword tokens with the question gets a positive
         boost.

The v1 heuristic reranker is **conservative**: when both signals are
neutral, it preserves the input order. It does NOT replace the
embedding similarity; it only re-orders the chunks the retrieval
engine returned.

Future implementations
----------------------
The interface is designed to accept future rerankers without
changing callers:

  - :class:`CrossEncoderReranker` (future phase): a real
    cross-encoder model loaded as a separate ML dependency.
  - :class:`BGEReranker` (future phase): BGE cross-encoder reranker.
  - Other semantic rerankers: subclass :class:`Reranker` and call
    out to a model API.

All of these will accept the same ``(question, chunks,
blueprint_spec, top_n) -> reranked_chunks`` interface.
"""
from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from medrack.ingest.metadata import flatten_for_chroma


# ----------------------------------------------------------------------
# Stopwords (same vocabulary as the keyword extractor in Phase 6)
# ----------------------------------------------------------------------

_STOPWORDS = frozenset(
    "the a an and or of in on at to for with by from as is are was were be been "
    "being have has had do does did will would shall should may might can could "
    "this that these those it its their there which who whom whose what when where "
    "why how also such only just more most other into over under between through "
    "during before after above below up down out off per each both either neither "
    "very much many few some any all no not nor only own same than too very s t d "
    "re et al fig table".split()
)

_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9-]{3,}\b")


def _extract_keywords(text: str) -> Set[str]:
    """Tokenize, lowercase, drop stopwords, drop short tokens."""
    if not text:
        return set()
    tokens = (t.lower() for t in _TOKEN_RE.findall(text))
    return {t for t in tokens if t not in _STOPWORDS and not t.isdigit()}


def _keyword_overlap_count(question: str, chunk_text: str) -> int:
    """Count how many question keywords appear in the chunk text."""
    q_kw = _extract_keywords(question)
    if not q_kw or not chunk_text:
        return 0
    c_text_lower = chunk_text.lower()
    return sum(1 for kw in q_kw if kw in c_text_lower)


# ----------------------------------------------------------------------
# Reranker ABC (generic, future-proof)
# ----------------------------------------------------------------------

class Reranker(ABC):
    """Abstract base class for rerankers.

    A reranker is a pure function:
    ``(question, chunks, blueprint_spec, top_n) -> reranked_chunks``.

    It has no I/O, no side effects on the input. It preserves chunk
    identities (the same ``id`` values appear in input and output,
    possibly in a different order).

    Future cross-encoder, BGE, or other semantic rerankers can
    subclass this ABC and call out to a model API. The v1
    implementation is a deterministic heuristic.
    """

    @abstractmethod
    def rerank(
        self,
        *,
        question: str,
        chunks: List[Dict[str, Any]],
        blueprint_spec: Optional[Any] = None,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rerank chunks. Returns a new list (does not mutate input).

        Parameters
        ----------
        question:
            The original question text. Used for keyword overlap
            scoring and (optionally) for cross-encoder model calls.
        chunks:
            The chunks returned by the vector index. Each is a dict
            with keys ``id``, ``text``, ``metadata``, ``distance``.
        blueprint_spec:
            Optional :class:`medrack.retrieval.blueprint_retrieval
            .BlueprintRetrieval`. When provided, the reranker can
            use ``required_metadata_categories`` to boost chunks
            whose metadata matches. Duck-typed: any object with a
            ``required_metadata_categories`` list works.
        top_n:
            Optional truncation. If set, only the top N chunks by
            reranked score are returned. If None, all chunks are
            returned in the new order.

        Returns
        -------
        list of dict
            The reranked chunks. Same shape as input. Chunk ``id``
            values are preserved (so the writer can cite them).
        """


# ----------------------------------------------------------------------
# v1: HeuristicReranker (deterministic, no LLM)
# ----------------------------------------------------------------------

@dataclass
class _ChunkScore:
    """Internal score record for a single chunk."""

    chunk: Dict[str, Any]
    score: float
    # Number of matching keywords (for debugging / observability)
    keyword_matches: int
    # Whether the chunk matches any required_metadata_category
    section_match: bool


class HeuristicReranker(Reranker):
    """v1 deterministic reranker.

    Combines three signals (per the directive):

    1. **Embedding similarity** (primary signal) — the existing
       distance from the vector index. Used as the default rank
       when the heuristic signals are neutral. The reranker does
       NOT replace the embedding similarity; it only re-orders
       the chunks the retrieval engine returned.

    2. **Blueprint section relevance** — a chunk whose metadata
       flags include any of the blueprint's
       ``required_metadata_categories`` gets a positive boost.

    3. **Lightweight keyword overlap** — a chunk that shares more
       non-stopword tokens with the question gets a positive boost.

    The v1 is **conservative**: when both heuristic signals are
    neutral (no section match, no keyword overlap), the input order
    is preserved. This means the system "still functions correctly
    if reranking is disabled" (per the directive).

    The v1 deliberately does NOT implement BM25, tf-idf, or any
    other term-frequency normalization. It only re-orders the
    chunks the retrieval engine returned. Future rerankers
    (CrossEncoder, BGE, etc.) can subclass and call out to a
    model API.
    """

    # Boost constants (tuned for the v1 heuristic)
    SECTION_MATCH_BOOST = 1.0
    KEYWORD_MATCH_BOOST = 0.5  # per matching keyword
    LENGTH_NORMALIZATION_BASE = math.e

    def rerank(
        self,
        *,
        question: str,
        chunks: List[Dict[str, Any]],
        blueprint_spec: Optional[Any] = None,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        # Extract the set of categories the blueprint wants
        required_categories: Set[str] = set()
        if blueprint_spec is not None:
            cats = getattr(blueprint_spec, "required_metadata_categories", None)
            if cats:
                required_categories = set(cats)

        scored: List[_ChunkScore] = []
        for chunk in chunks:
            chunk_text = chunk.get("text", "") or ""
            chunk_meta = chunk.get("metadata") or {}

            # 1. Section match: does the chunk's flattened metadata
            # include any required category?
            section_match = False
            if required_categories and chunk_meta:
                # chunk_meta may be a Chroma-style dict (already flat)
                # or a ChunkMetadata (nested). Handle both.
                if isinstance(chunk_meta, dict):
                    flat = chunk_meta
                else:
                    flat = flatten_for_chroma(chunk_meta)
                for cat in required_categories:
                    if flat.get(cat) is True:
                        section_match = True
                        break

            # 2. Keyword overlap
            keyword_matches = _keyword_overlap_count(question, chunk_text)

            # 3. Composite score: section boost + per-keyword boost
            #    (NOT BM25 — the directive says avoid BM25).
            section_boost = (
                self.SECTION_MATCH_BOOST if section_match else 0.0
            )
            keyword_boost = keyword_matches * self.KEYWORD_MATCH_BOOST
            numerator = section_boost + keyword_boost
            # Length normalization (log) to avoid long-chunk bias.
            denom = math.log(len(chunk_text) + self.LENGTH_NORMALIZATION_BASE)
            if denom < 1.0:
                denom = 1.0  # safety
            score = numerator / denom

            scored.append(
                _ChunkScore(
                    chunk=chunk,
                    score=score,
                    keyword_matches=keyword_matches,
                    section_match=section_match,
                )
            )

        # Sort by score DESC, then by input order (stable sort).
        # Python's sort is stable, so we just sort by score and the
        # original order is preserved among ties.
        scored.sort(key=lambda s: -s.score)

        reranked = [s.chunk for s in scored]

        # Annotate the reranked chunks with score metadata (for
        # observability; not part of the chunk's content). The
        # chunk's original metadata is preserved (we add new keys,
        # not modify existing ones).
        for s, chunk in zip(scored, reranked):
            chunk["_rerank_score"] = s.score
            chunk["_rerank_keyword_matches"] = s.keyword_matches
            chunk["_rerank_section_match"] = s.section_match

        # Optional truncation. Per the contract: top_n=None means
        # "no truncation"; top_n=0 means "no chunks" (empty list);
        # top_n=N means "keep the top N".
        if top_n is not None:
            if top_n <= 0:
                return []
            reranked = reranked[:top_n]

        return reranked


# ----------------------------------------------------------------------
# IdentityReranker (no-op pass-through)
# ----------------------------------------------------------------------

class IdentityReranker(Reranker):
    """No-op reranker.

    Returns the input chunks in their input order, optionally
    truncated to ``top_n``. Useful for:
      - A/B testing against a real reranker (compare relevance).
      - Disabling reranking entirely (the operator can swap
        ``HeuristicReranker`` for ``IdentityReranker`` in the
        engine).
      - Fallback when a real cross-encoder model fails to load.
    """

    def rerank(
        self,
        *,
        question: str,
        chunks: List[Dict[str, Any]],
        blueprint_spec: Optional[Any] = None,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not chunks:
            return []
        # Defensive copy so callers can mutate freely
        out = [dict(c) for c in chunks]
        if top_n is not None and top_n > 0:
            out = out[:top_n]
        return out


# ----------------------------------------------------------------------
# Top-N truncation helper
# ----------------------------------------------------------------------

def truncate_top_n(
    chunks: List[Dict[str, Any]],
    top_n: int,
) -> List[Dict[str, Any]]:
    """Truncate a list of chunks to the top N by index.

    The v1 :class:`HeuristicReranker` applies truncation by score
    (top N by reranked score). This helper applies truncation by
    list position (top N by input order) for the
    :class:`IdentityReranker` case.

    Both are valid: a future phase can decide whether to truncate
    before or after reranking.
    """
    if top_n <= 0:
        return []
    return list(chunks)[:top_n]


__all__ = [
    "Reranker",
    "HeuristicReranker",
    "IdentityReranker",
    "truncate_top_n",
]
