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
from medrack.retrieval.reranker import MetadataBoostReranker, Reranker
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
    """

    chunks: List[Dict[str, Any]]
    analysis: QuestionAnalysis
    retrieval_latency_seconds: float
    rerank_latency_seconds: float
    top_k: int
    metadata_filter_active: bool


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
        reranker: Optional[Reranker] = None,
    ) -> None:
        self.analyzer = analyzer or QuestionAnalyzer()
        self.strategy = strategy or AdaptiveStrategy()
        self.reranker = reranker or MetadataBoostReranker()

    def retrieve(
        self,
        *,
        question: dict,
        subject: str,
        query_embedding: List[float],
        marks: int | None = None,
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

        # 4. Rerank.
        t0 = time.perf_counter()
        reranked = self.reranker.rerank(raw, analysis)
        rerank_latency = time.perf_counter() - t0

        return RetrievalResult(
            chunks=reranked,
            analysis=analysis,
            retrieval_latency_seconds=retrieval_latency,
            rerank_latency_seconds=rerank_latency,
            top_k=plan.top_k,
            metadata_filter_active=not plan.metadata_filter.is_empty(),
        )


def retrieve_for_question(
    *,
    question: dict,
    subject: str,
    query_embedding: List[float],
    marks: int | None = None,
) -> RetrievalResult:
    """Module-level convenience: default engine, default config.

    This is the v7 entry point. It replaces the direct
    ``medrack.ingest.index.query(...)`` call the answer pipeline used
    in earlier phases.
    """
    engine = RetrievalEngine()
    return engine.retrieve(
        question=question,
        subject=subject,
        query_embedding=query_embedding,
        marks=marks,
    )


__all__ = ["RetrievalEngine", "RetrievalResult", "retrieve_for_question"]
