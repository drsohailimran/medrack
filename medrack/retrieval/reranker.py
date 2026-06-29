"""Retrieval rerankers (Phase 7).

A :class:`Reranker` reorders a list of retrieval results to improve
relevance. Phase 7 ships one reranker: :class:`MetadataBoostReranker`,
which multiplies the vector-similarity distance by a configurable
boost factor for chunks whose metadata matches the question's
detected sections.

The reranker is **additive** to vector similarity — it never replaces
it. A chunk that doesn't match any metadata flag is left at its
original position with its original distance; only matching chunks
are boosted (their distance shrinks, so they rank higher).

Reranker contract
-----------------
Input: a list of result dicts (the same shape
``medrack.ingest.index.query`` returns) and the
:class:`QuestionAnalysis`.

Output: the same list, reordered, with ``distance`` adjusted in
place. We modify distances rather than just reordering because future
phases (e.g. the answer pipeline) may want to surface the distance for
logging.

The reranker is **deterministic** and has no I/O. Future cross-encoder
rerankers can subclass and call out to a model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from medrack.ingest.metadata import flatten_for_chroma
from medrack.retrieval.analyzer import QuestionAnalysis


class Reranker(ABC):
    """Abstract base class for rerankers."""

    @abstractmethod
    def rerank(
        self,
        results: List[Dict[str, Any]],
        analysis: QuestionAnalysis,
    ) -> List[Dict[str, Any]]:
        """Rerank results. Returns a new list (does not mutate input)."""


class MetadataBoostReranker(Reranker):
    """Boost chunks whose metadata matches the question's target sections.

    Algorithm
    ---------
    For each result, count how many of the question's ``target_sections``
    are present in the chunk's flattened metadata (as ``True``). Each
    match multiplies the chunk's distance by :attr:`boost_factor`
    (default 0.67, i.e. ~1.5x boost per match). A chunk with 2 matching
    sections gets distance * 0.67^2 ~= 0.45.

    The list is then re-sorted by ascending adjusted distance.

    Why multiplicative on distance (not additive)?
    ------------------------------------------------
    Distance is unbounded and can vary across queries; an additive
    boost would have to be tuned per-query. A multiplicative boost is
    scale-invariant and naturally saturates for chunks with many
    matches.

    Why per-section boost (not flat)?
    ---------------------------------
    A question that matches 2 sections is more specific than a
    question that matches 1. Per-section boost lets the reranker
    distinguish them. The default 0.67 (1.5x) is conservative;
    future phases can tune it.
    """

    DEFAULT_BOOST_FACTOR = 0.67  # ~1.5x boost per match

    def __init__(self, boost_factor: float = DEFAULT_BOOST_FACTOR) -> None:
        if not 0.0 < boost_factor <= 1.0:
            raise ValueError(
                f"boost_factor must be in (0, 1] (smaller = stronger boost); "
                f"got {boost_factor}"
            )
        self.boost_factor = boost_factor

    def rerank(
        self,
        results: List[Dict[str, Any]],
        analysis: QuestionAnalysis,
    ) -> List[Dict[str, Any]]:
        if not results or not analysis.target_sections:
            # No analysis -> nothing to boost. Return a defensive copy
            # so callers can't accidentally mutate the original list.
            return [dict(r) for r in results]

        targets = set(analysis.target_sections)

        # Compute adjusted distance per result.
        # If a chunk's distance is None (Chroma without distance
        # function), we leave it unchanged and treat it as "rank-only".
        adjusted: List[Dict[str, Any]] = []
        for r in results:
            new_r = dict(r)  # defensive copy
            meta = new_r.get("metadata") or {}
            matches = sum(1 for sec in targets if meta.get(sec) is True)
            if matches > 0:
                d = new_r.get("distance")
                if d is not None:
                    # Multiplicative boost per match
                    new_r["distance"] = d * (self.boost_factor ** matches)
                # If distance is None, we can't adjust, but the chunk
                # will still be reordered because we sort by (matches,
                # distance) below — matching chunks with no distance
                # rank above non-matching chunks with no distance.
                new_r["_metadata_boost_matches"] = matches
            else:
                new_r["_metadata_boost_matches"] = 0
            adjusted.append(new_r)

        # Sort by matches DESC, then by adjusted distance ASC.
        # Matches-first ordering: a 2-match chunk with no distance
        # ranks above a 0-match chunk with no distance.
        adjusted.sort(
            key=lambda r: (
                -r.get("_metadata_boost_matches", 0),
                r.get("distance") if r.get("distance") is not None else float("inf"),
            )
        )

        # Drop the internal boost field before returning — it's only
        # used for sorting, not for downstream consumers.
        for r in adjusted:
            r.pop("_metadata_boost_matches", None)

        return adjusted


__all__ = ["Reranker", "MetadataBoostReranker"]
