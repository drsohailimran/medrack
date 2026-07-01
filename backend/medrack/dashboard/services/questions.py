"""QuestionService — Question generation operations (Phase 12).

The :class:`QuestionService` is the stable interface for generating
answers, batches, revisions, and re-answering stale answers.

The service delegates to ``medrack.answer.generate.generate_answer``
(the canonical answer-generation function).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GenerationRequest:
    """A request to generate a single answer."""

    qid: str
    question_text: str
    subject: str
    marks: int
    question_type: str = "theory"
    book_id: Optional[str] = None
    chapter: Optional[str] = None
    # Optional explicit answer length (words). If None, derived from marks.
    word_count_target: Optional[int] = None


@dataclass
class GenerationResult:
    """The result of a single answer generation."""

    qid: str
    ok: bool
    answer_text: Optional[str] = None
    pdf_path: Optional[str] = None
    cache_hit: bool = False
    error: Optional[str] = None
    token_count: int = 0
    latency_seconds: float = 0.0

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "qid": self.qid,
            "ok": self.ok,
            "answer_text": self.answer_text,
            "pdf_path": self.pdf_path,
            "cache_hit": self.cache_hit,
            "error": self.error,
            "token_count": self.token_count,
            "latency_seconds": self.latency_seconds,
        }


class QuestionService:
    """Service for question generation.

    The service is stateless; it delegates to the existing
    ``medrack.answer.generate.generate_answer`` function.
    """

    SCHEMA_VERSION = 1

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a single answer for the given request.

        Note: ``generate_answer`` requires a ``module_name`` (e.g.
        ``"psm-module-1"``) and ``chapter``. If the request does
        not provide these, sensible defaults are inferred.
        """
        from medrack.answer.generate import generate_answer
        from medrack.state import get_llm_client
        import time
        # Honor $MEDRACK_LLM_MODE so the dashboard path can run in mock
        # mode for offline testing (the CLI already used this helper).
        llm_client = get_llm_client()
        module_name = request.book_id or f"{request.subject}-default"
        chapter = request.chapter or "default"
        t0 = time.perf_counter()
        try:
            result = generate_answer(
                module_name=module_name,
                subject=request.subject,
                chapter=chapter,
                question={
                    "qid": request.qid,
                    "type": request.question_type,
                    "question_text": request.question_text,
                },
                llm_client=llm_client,
                marks=request.marks,
                word_count_target=request.word_count_target,
            )
            latency = time.perf_counter() - t0
            return GenerationResult(
                qid=request.qid,
                ok=result.get("ok", True) if isinstance(result, dict) else True,
                answer_text=result.get("answer_text") if isinstance(result, dict) else None,
                pdf_path=result.get("pdf_path") if isinstance(result, dict) else None,
                cache_hit=result.get("cache_hit", False) if isinstance(result, dict) else False,
                token_count=(
                    result.get("total_tokens", result.get("token_count", 0))
                    if isinstance(result, dict) else 0
                ),
                latency_seconds=latency,
            )
        except Exception as e:
            latency = time.perf_counter() - t0
            return GenerationResult(
                qid=request.qid,
                ok=False,
                error=str(e),
                latency_seconds=latency,
            )

    def generate_batch(
        self,
        requests: List[GenerationRequest],
    ) -> List[GenerationResult]:
        """Generate answers for a batch of requests (sequential)."""
        return [self.generate(req) for req in requests]

    def revise(
        self,
        qid: str,
        subject: str,
        revised_question_text: str,
    ) -> GenerationResult:
        """Revise an existing answer with a new question text.

        The cached answer is invalidated (marked stale) and a new
        answer is generated. If no cached entry exists, the
        stale-marking step is a no-op.
        """
        from medrack.answer.versioning import mark_stale as mark_cached_stale
        from medrack.answer.cache import _answers_root
        import json
        # The cache is a flat file tree at <answers>/<qid>.json or
        # <answers>/<module>/<chapter>/<qid>.json. We scan for the
        # qid and mark any matching entry stale. This is best-effort;
        # if no entry exists, generation will simply write a fresh one.
        root = _answers_root()
        if root.exists():
            for path in root.rglob(f"{qid}.json"):
                try:
                    with path.open() as f:
                        data = json.load(f)
                except Exception:
                    continue
                marked = mark_cached_stale(data)
                try:
                    with path.open("w") as f:
                        json.dump(marked, f, indent=2, sort_keys=True)
                except Exception:
                    pass
        return self.generate(GenerationRequest(
            qid=qid,
            question_text=revised_question_text,
            subject=subject,
            marks=10,
        ))

    def re_answer_stale(
        self,
        module_name: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Re-answer all stale cached answers for a module.

        If ``dry_run`` is True, returns the list of stale qids
        without regenerating.

        ``module_name`` corresponds to a subject-scoped module
        (e.g. ``"psm-module-1"``). If None, all modules are
        scanned.
        """
        from medrack.answer.versioning import find_stale_answers
        stale = find_stale_answers(module_name=module_name)
        qids = [s.get("qid") for s in stale if s.get("qid")]
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "stale_count": len(qids),
                "stale_qids": qids,
            }
        # Otherwise re-generate each
        results = []
        for s in stale:
            res = self.generate(GenerationRequest(
                qid=s.get("qid", ""),
                question_text=s.get("question_text", ""),
                subject=module_name or s.get("subject", "psm"),
                marks=s.get("marks", 10),
            ))
            results.append(res.to_dict())
        return {
            "ok": True,
            "dry_run": False,
            "reanswered_count": len(results),
            "results": results,
        }


__all__ = [
    "QuestionService",
    "GenerationRequest",
    "GenerationResult",
]
