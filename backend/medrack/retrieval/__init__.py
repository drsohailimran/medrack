"""medrack.retrieval — adaptive retrieval layer (Phase 7).

This package is the retrieval layer that the answer pipeline (and future
phases like the Planner) will consume. It builds on the Phase 6
metadata layer: the adaptive strategy uses structured metadata to
influence *ranking* (not to *replace* vector similarity), so that
questions about management retrieve more management chunks, questions
about classification retrieve more classification chunks, etc.

Architecture
------------
The retrieval layer is a pipeline of three pluggable steps:

  1. ``analyzer.QuestionAnalyzer``  — extracts (marks, target_sections)
     from a question dict.
  2. ``engine.RetrievalEngine``     — calls into the vector index
     (``medrack.ingest.index.query``) with a strategy-derived top_k
     and metadata filter.
  3. ``reranker.Reranker``          — reorders the returned chunks so
     that metadata-matching chunks are boosted.

All three components are pluggable. The v1 implementation is
deterministic (no LLM, no API). Future phases (cross-encoder reranker,
LLM-based analyzers) can be added as new modules here without
changing the answer pipeline.

The retrieval layer imports nothing from:
  - ``medrack.answer.*``
  - ``medrack.bot.*``
  - ``medrack.dashboard.*``
  - ``medrack.benchmarks.*``

It does import from:
  - ``medrack.ingest.*`` (vector index, metadata schema)
  - ``medrack.ingest.extractors.*`` (the same regex patterns used
    by the ingest extractor, so the v1 analyzer uses the same
    vocabulary as the v1 chunk metadata)

This is one-way coupling: the retrieval layer depends on ingest, not
vice versa.
"""
from medrack.retrieval.strategy import (
    AdaptiveStrategy,
    IdentityStrategy,
    RetrievalStrategy,
    RetrievalPlan,
)
from medrack.retrieval.analyzer import QuestionAnalyzer, QuestionAnalysis
from medrack.retrieval.reranker import MetadataBoostReranker, Reranker
from medrack.retrieval.engine import RetrievalEngine, RetrievalResult, retrieve_for_question
from medrack.retrieval.blueprint_retrieval import (
    BlueprintRetrieval,
    SectionRetrievalSpec,
    build_blueprint_retrieval,
    PRIORITY_REQUIRED,
    PRIORITY_RECOMMENDED,
    PRIORITY_OPTIONAL,
    DEFAULT_MIN_CHUNKS,
    DEFAULT_MAX_CHUNKS,
)
from medrack.retrieval.rerankers import (
    Reranker as SemanticReranker,
    HeuristicReranker,
    IdentityReranker,
    truncate_top_n,
)

__all__ = [
    "AdaptiveStrategy",
    "IdentityStrategy",
    "RetrievalStrategy",
    "RetrievalPlan",
    "QuestionAnalyzer",
    "QuestionAnalysis",
    "MetadataBoostReranker",
    "Reranker",
    "RetrievalEngine",
    "RetrievalResult",
    "retrieve_for_question",
    "BlueprintRetrieval",
    "SectionRetrievalSpec",
    "build_blueprint_retrieval",
    "PRIORITY_REQUIRED",
    "PRIORITY_RECOMMENDED",
    "PRIORITY_OPTIONAL",
    "DEFAULT_MIN_CHUNKS",
    "DEFAULT_MAX_CHUNKS",
    "SemanticReranker",
    "HeuristicReranker",
    "IdentityReranker",
    "truncate_top_n",
]
