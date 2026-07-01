"""PipelineService — Inspect each pipeline stage (Phase 12).

The :class:`PipelineService` is the stable interface for inspecting
the MedRack pipeline stage-by-stage:

  Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator

For a given question, the service returns a structured breakdown
of each stage's output. The service is read-only; it does NOT
mutate any backend state.

This is the "Pipeline Inspection" feature requested in the
Phase 12 directive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineStageOutput:
    """Output of a single pipeline stage."""

    stage: str  # "planner" | "blueprint" | "retrieval" | "reranker" | "writer" | "validator"
    output: Dict[str, Any]
    latency_seconds: float = 0.0

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "stage": self.stage,
            "output": self.output,
            "latency_seconds": self.latency_seconds,
        }


@dataclass
class PipelineTrace:
    """A complete pipeline trace for a single question.

    Attributes
    ----------
    qid:
        The question identifier.
    stages:
        Ordered list of stage outputs (Planner, Blueprint,
        Retrieval, Reranker, Writer, Validator).
    total_latency_seconds:
        Sum of all stage latencies.
    """

    qid: str
    stages: List[PipelineStageOutput] = field(default_factory=list)
    total_latency_seconds: float = 0.0

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "qid": self.qid,
            "stages": [s.to_dict() for s in self.stages],
            "total_latency_seconds": self.total_latency_seconds,
        }


class PipelineService:
    """Service for pipeline inspection.

    The service is stateless; it delegates to the existing
    backend modules. Each ``inspect_*`` method corresponds to
    one pipeline stage.
    """

    SCHEMA_VERSION = 1

    def inspect_planner(
        self,
        question_text: str,
        subject: str,
        marks: int = 10,
        question_type: str = "theory",
    ) -> PipelineStageOutput:
        """Run the Planner on a question and return its output."""
        from medrack.planner import plan_for_question
        import time
        t0 = time.perf_counter()
        bp = plan_for_question(
            question_text=question_text,
            subject=subject,
            marks=marks,
            question_type=question_type,
        )
        latency = time.perf_counter() - t0
        return PipelineStageOutput(
            stage="planner",
            output=bp.to_dict(),
            latency_seconds=latency,
        )

    def inspect_blueprint(
        self,
        question_text: str,
        subject: str,
        marks: int = 10,
        question_type: str = "theory",
    ) -> PipelineStageOutput:
        """Run the Planner + Blueprint Retrieval spec, return the spec."""
        from medrack.planner import plan_for_question
        from medrack.retrieval import build_blueprint_retrieval
        import time
        t0 = time.perf_counter()
        bp = plan_for_question(
            question_text=question_text,
            subject=subject,
            marks=marks,
            question_type=question_type,
        )
        spec = build_blueprint_retrieval(bp)
        latency = time.perf_counter() - t0
        return PipelineStageOutput(
            stage="blueprint",
            output=spec.to_dict(),
            latency_seconds=latency,
        )

    def inspect(
        self,
        qid: str,
        question_text: str,
        subject: str,
        marks: int = 10,
        question_type: str = "theory",
    ) -> PipelineTrace:
        """Run the full pipeline inspection (all stages, read-only).

        For the retrieval/reranker/writer/validator stages, the
        service returns the *configuration* (e.g. which rules are
        enabled, which rerankers are wired) rather than executing
        a real generation. Real generation is the
        :class:`QuestionService`'s job.
        """
        stages: List[PipelineStageOutput] = []
        # Stage 1: Planner
        stages.append(self.inspect_planner(
            question_text, subject, marks, question_type
        ))
        # Stage 2: Blueprint
        stages.append(self.inspect_blueprint(
            question_text, subject, marks, question_type
        ))
        # Stage 3: Retrieval config (top_k, strategy)
        from medrack.retrieval import AdaptiveStrategy
        strategy = AdaptiveStrategy()
        stages.append(PipelineStageOutput(
            stage="retrieval",
            output={
                "strategy": type(strategy).__name__,
                "top_k_by_marks": {
                    "5": strategy.TOP_K_BY_MARKS.get(5, 5),
                    "10": strategy.TOP_K_BY_MARKS.get(10, 8),
                },
            },
        ))
        # Stage 4: Reranker config
        from medrack.retrieval import (
            HeuristicReranker, IdentityReranker, MetadataBoostReranker
        )
        stages.append(PipelineStageOutput(
            stage="reranker",
            output={
                "metadata_reranker": "MetadataBoostReranker",
                "semantic_reranker_options": [
                    "IdentityReranker",
                    "HeuristicReranker",
                ],
                "default_semantic_reranker": "IdentityReranker",
            },
        ))
        # Stage 5: Writer config
        from medrack.config import THEORY_LONG_TARGET_WORDS, THEORY_SHORT_TARGET_WORDS
        stages.append(PipelineStageOutput(
            stage="writer",
            output={
                "theory_long_target_words": THEORY_LONG_TARGET_WORDS,
                "theory_short_target_words": THEORY_SHORT_TARGET_WORDS,
            },
        ))
        # Stage 6: Validator config
        from medrack.validation import DEFAULT_RULES
        stages.append(PipelineStageOutput(
            stage="validator",
            output={
                "rule_count": len(DEFAULT_RULES),
                "rule_names": [r.__name__ for r in DEFAULT_RULES],
            },
        ))
        total = sum(s.latency_seconds for s in stages)
        return PipelineTrace(
            qid=qid,
            stages=stages,
            total_latency_seconds=total,
        )


__all__ = [
    "PipelineService",
    "PipelineStageOutput",
    "PipelineTrace",
]
