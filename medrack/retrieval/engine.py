"""Adaptive retrieval engine (Phase 7).

The :class:`RetrievalEngine` is the public entry point for the
retrieval layer. It composes:

  1. a :class:`QuestionAnalyzer` (analyzes the question)
  2. a :class:`RetrievalStrategy` (produces a plan from the analysis)
  3. the vector index (``medrack.ingest.index.query``)
  4. a :class:`Reranker` (reorders the results)

The engine is the *only* thing the answer pipeline needs to import
from this package. It exposes a single function,
:meth:`RetrievalEngine.retrieve`, that takes a question dict plus a
subject and returns a list of retrieval results (the same shape the
old direct ``query()`` call returned).

Architecture
------------
The engine is intentionally dumb about the strategy and reranker; you
can swap either without changing the engine. The default wiring is:

  analyzer = QuestionAnalyzer()
  strategy = AdaptiveStrategy()
  reranker = MetadataBoostReranker()

A v0-compat engine is also available via the module-level
:func:`retrieve_for_question` helper, which uses the defaults.

The engine does **not** call into any LLM, planner, blueprint, or
validation layer. It is pure retrieval.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from medrack.ingest.index import query as vector_query
from medrack.retrieval.analyzer import QuestionAnalyzer, QuestionAnalysis
from medrack.retrieval.blueprint_retrieval import BlueprintRetrieval
from medrack.retrieval.rerankers import (
    Reranker,
    HeuristicReranker,
    IdentityReranker,
)
from medrack.retrieval.reranker import MetadataBoostReranker
from medrack.retrieval.strategy import AdaptiveStrategy, RetrievalStrategy


@dataclass
class RetrievalResult:
    """The result of a retrieval call.

    Attributes
    ----------
    chunks:
        The reranked list of chunks (same shape as
        ``medrack.ingest.index.query`` returns). Each is a dict with
        keys ``id``, ``text``, ``metadata``, ``distance``.
    analysis:
        The :class:`QuestionAnalysis` produced by the analyzer. Kept
        for downstream logging / debugging.
    retrieval_latency_seconds:
        Wall-clock time spent in the vector index call. Excludes
        analysis + reranking.
    rerank_latency_seconds:
        Wall-clock time spent in the reranker. Excludes analysis +
        retrieval.
    top_k:
        The top_k that was actually used (may differ from the default
        if the strategy adapted it).
    metadata_filter_active:
        True iff a non-empty :class:`MetadataFilter` was applied at
        the index layer.
    blueprint_spec:
        Optional :class:`BlueprintRetrieval` consumed by the
        reranker. ``None`` if the caller did not provide a planner
        blueprint. The v1 retrieval layer does not produce this
        internally; the answer pipeline (future phase) will.
    """

    chunks: List[Dict[str, Any]]
    analysis: QuestionAnalysis
    retrieval_latency_seconds: float
    rerank_latency_seconds: float
    top_k: int
    metadata_filter_active: bool
    blueprint_spec: Optional[BlueprintRetrieval] = None


class RetrievalEngine:
    """Adaptive retrieval engine.

    Composes an analyzer, a strategy, and a reranker. The defaults
    are the v1 adaptive strategy. Future phases can construct an
    engine with a different strategy or reranker for A/B testing
    without changing callers.
    """

    def __init__(
        self,
        *,
        analyzer: Optional[QuestionAnalyzer] = None,
        strategy: Optional[RetrievalStrategy] = None,
        metadata_reranker: Optional[MetadataBoostReranker] = None,
        semantic_reranker: Optional[Reranker] = None,
    ) -> None:
        self.analyzer = analyzer or QuestionAnalyzer()
        self.strategy = strategy or AdaptiveStrategy()
        # Phase 7: metadata-boost reranker (the existing
        # v1 reranker). Default is the v1 implementation.
        self.metadata_reranker = metadata_reranker or MetadataBoostReranker()
        # Phase 10: semantic reranker (generic, pluggable).
        # Default is IdentityReranker (no-op) so the system still
        # functions correctly if reranking is disabled. The
        # operator can opt in to HeuristicReranker or a future
        # cross-encoder by passing it in.
        self.semantic_reranker = semantic_reranker or IdentityReranker()

    def retrieve(
        self,
        *,
        question: dict,
        subject: str,
        query_embedding: List[float],
        marks: int | None = None,
        blueprint_spec: Optional[BlueprintRetrieval] = None,
    ) -> RetrievalResult:
        """Retrieve chunks for a question.

        Parameters
        ----------
        question:
            Question dict (must have ``question_text``; may have
            ``marks``).
        subject:
            The subject, e.g. ``"psm"``. Used to scope the vector
            index to ``kb_<subject>``.
        query_embedding:
            The pre-computed question embedding (1D or 2D list).
        marks:
            Optional explicit marks value (5 or 10). If None, the
            analyzer looks at the question dict.
        blueprint_spec:
            Optional :class:`BlueprintRetrieval` (Phase 9). When
            provided, the cross-encoder reranker uses
            ``required_metadata_categories`` to boost matching chunks.
            When None, the reranker is a no-op (the system still
            functions correctly).

        Returns
        -------
        RetrievalResult
            The reranked chunks plus diagnostic info. The
            ``chunks`` field is what the answer pipeline should use.
        """
        # 1. Analyze the question.
        analysis = self.analyzer.analyze(question, marks=marks)

        # 2. Get the plan from the strategy.
        plan = self.strategy.plan(analysis)

        # 3. Query the vector index.
        t0 = time.perf_counter()
        raw = vector_query(
            subject=subject,
            query_embedding=query_embedding,
            top_k=plan.top_k,
            metadata_filter=plan.metadata_filter,
        )
        retrieval_latency = time.perf_counter() - t0

        # 4. Metadata-boost rerank (Phase 7).
        t0 = time.perf_counter()
        after_metadata_boost = self.metadata_reranker.rerank(raw, analysis)
        meta_rerank_latency = time.perf_counter() - t0

        # 5. Semantic rerank (Phase 10, generic Reranker interface).
        #    This is the pluggable final stage. Default is
        #    IdentityReranker (no-op); operators can swap in
        #    HeuristicReranker, a future CrossEncoderReranker,
        #    BGEReranker, or any other semantic reranker. It
        #    accepts the Blueprint Retrieval spec for
        #    section-aware boosting.
        t0 = time.perf_counter()
        after_semantic = self.semantic_reranker.rerank(
            question=question.get("question_text", ""),
            chunks=after_metadata_boost,
            blueprint_spec=blueprint_spec,
        )
        sem_rerank_latency = time.perf_counter() - t0

        # Total rerank latency = both stages combined
        rerank_latency = meta_rerank_latency + sem_rerank_latency

        return RetrievalResult(
            chunks=after_semantic,
            analysis=analysis,
            retrieval_latency_seconds=retrieval_latency,
            rerank_latency_seconds=rerank_latency,
            top_k=plan.top_k,
            metadata_filter_active=not plan.metadata_filter.is_empty(),
            blueprint_spec=blueprint_spec,
        )


def retrieve_for_question(
    *,
    question: dict,
    subject: str,
    query_embedding: List[float],
    marks: int | None = None,
    blueprint_spec: Optional[BlueprintRetrieval] = None,
) -> RetrievalResult:
    """Module-level convenience: default engine, default config.

    The v7 entry point. Replaces the direct
    ``medrack.ingest.index.query(...)`` call the answer pipeline used
    in earlier phases.
    """
    engine = RetrievalEngine()
    return engine.retrieve(
        question=question,
        subject=subject,
        query_embedding=query_embedding,
        marks=marks,
        blueprint_spec=blueprint_spec,
    )


__all__ = ["RetrievalEngine", "RetrievalResult", "retrieve_for_question"]
