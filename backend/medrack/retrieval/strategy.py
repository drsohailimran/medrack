"""Pluggable retrieval strategies (Phase 7).

A :class:`RetrievalStrategy` decides *what* to retrieve given a
:class:`QuestionAnalysis` — specifically, the ``top_k`` and the
:class:`MetadataFilter`. Strategies do not perform the retrieval
themselves; they only produce a :class:`RetrievalPlan` that the
:class:`engine.RetrievalEngine` then executes against the vector index.

This split (plan vs execute) is what makes the strategy pluggable: the
engine is the same for every strategy; only the plan differs.

v1 strategies
-------------
- :class:`IdentityStrategy` — preserves the v0 behavior (top_k=8,
  no metadata filter). Exists for A/B comparison against adaptive.
- :class:`AdaptiveStrategy` — the v1 default. Adjusts top_k by
  marks (5-mark=5, 10-mark=8) and produces a metadata filter that
  targets the question's detected topic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from medrack.ingest.metadata import MetadataFilter


@dataclass
class RetrievalPlan:
    """A strategy's plan for how to retrieve.

    Attributes
    ----------
    top_k:
        Number of chunks to request from the vector index.
    metadata_filter:
        Optional :class:`MetadataFilter` to pass to ``query()``. An
        empty filter means "no filter" (all chunks match). Strategies
        that don't use metadata set this to ``None`` or to an empty
        :class:`MetadataFilter`.
    """

    top_k: int
    metadata_filter: MetadataFilter = field(default_factory=MetadataFilter)


class RetrievalStrategy(ABC):
    """Abstract base class for retrieval strategies.

    A strategy is a pure function: ``(analysis) -> plan``. It has no
    side effects, no I/O, and does not know about the vector index.
    """

    @abstractmethod
    def plan(self, analysis: "QuestionAnalysis") -> RetrievalPlan:
        """Compute a retrieval plan for this analysis."""


class IdentityStrategy(RetrievalStrategy):
    """v0-compatible strategy. Always returns top_k=8 and no filter.

    Useful for A/B testing against :class:`AdaptiveStrategy` and for
    callers that need bit-identical behavior to the pre-Phase-7
    retrieval.
    """

    DEFAULT_TOP_K = 8

    def plan(self, analysis: "QuestionAnalysis") -> RetrievalPlan:
        return RetrievalPlan(top_k=self.DEFAULT_TOP_K)


class AdaptiveStrategy(RetrievalStrategy):
    """v1 adaptive strategy.

    Decisions
    ---------
    - **top_k by marks**: 5-mark questions retrieve 5 chunks; 10-mark
      questions retrieve 8 chunks. The directive's first example:
      "10-mark questions retrieve more evidence than 5-mark questions".
      Unknown marks default to 8.
    - **metadata filter by topic**: the analysis's ``target_sections``
      are translated into a :class:`MetadataFilter`. A section list of
      length 1 or 2 is a strong signal; longer lists fall back to
      "no filter" to avoid over-constraining retrieval (the directive
      says "do not remove useful evidence merely to reduce tokens").

    This is the v1 default. The boost itself happens in the reranker
    (see :mod:`medrack.retrieval.reranker`); the strategy only chooses
    *what* to retrieve, not *how* to rank.
    """

    TOP_K_BY_MARKS = {5: 5, 10: 8}
    DEFAULT_TOP_K = 8
    # If a question matches more than this many sections, drop the
    # filter and let the reranker do the work — too broad a filter
    # is worse than no filter.
    MAX_SECTIONS_FOR_FILTER = 2

    def plan(self, analysis: "QuestionAnalysis") -> RetrievalPlan:
        top_k = self.TOP_K_BY_MARKS.get(analysis.marks, self.DEFAULT_TOP_K)

        if not analysis.target_sections:
            return RetrievalPlan(top_k=top_k)

        if len(analysis.target_sections) > self.MAX_SECTIONS_FOR_FILTER:
            # Too broad — let the reranker handle the boost; don't
            # filter out potentially-relevant chunks at the index layer.
            return RetrievalPlan(top_k=top_k)

        # Classify the sections into structure vs medical groups.
        # The analyzer's section names use the ``section_*`` convention
        # which matches the MetadataFilter groups directly.
        structure, medical = self._split_sections(analysis.target_sections)
        return RetrievalPlan(
            top_k=top_k,
            metadata_filter=MetadataFilter(structure=structure, medical=medical),
        )

    @staticmethod
    def _split_sections(sections: List[str]) -> tuple:
        """Split section names into structure-group and medical-group.

        Section names like ``section_table`` go to structure;
        ``section_management`` goes to medical. Unknown sections are
        treated as medical (the larger group).
        """
        from medrack.ingest.metadata import StructureMetadata, MedicalMetadata

        structure_fields = {f for f in StructureMetadata.__dataclass_fields__}
        medical_fields = {f for f in MedicalMetadata.__dataclass_fields__}

        structure = [s for s in sections if s in structure_fields]
        medical = [s for s in sections if s in medical_fields]
        return structure, medical


__all__ = [
    "RetrievalPlan",
    "RetrievalStrategy",
    "IdentityStrategy",
    "AdaptiveStrategy",
]
