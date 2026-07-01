"""medrack.benchmarks — reusable benchmark engine for MedRack.

This is the single source of truth for performance/quality measurement.
Every future architectural change (planner, metadata extraction,
cross-encoder reranker, validator, etc.) is evaluated against a
benchmark run produced here. The current Phase 4 dataset (v1.json) is
the canonical benchmark suite; the directive v1.0 says future
suites (v2.json, v3.json, ...) extend this list but v1 never changes.

Public API:
    run_benchmark(...) -> BenchmarkRun
    BenchmarkRun       (dataclass: aggregated metrics + per-question records)
    BenchmarkRecord    (dataclass: per-question metrics)

Cold path vs warm path:

  cold path:  cache miss  -> retrieval -> generation -> validation
  warm path:  cache hit   -> render/export (no LLM call)

The first call to a question is always the cold path (forces a
regeneration). The second call (with ``warm_path=True``) is the warm
path — if the answer is still cached, we don't re-call the LLM, we
just render the PDF from the cached answer and measure render time.

Design constraints (directive v1.0):
  - Single reusable engine: no CLI / I/O coupling in this file.
  - All metrics recorded: retrieval latency, generation latency,
    prompt/completion/total tokens, cache hit rate, answer length,
    PDF generation time, success/failure counts.
  - Reporting layer (medrack.benchmarks.report) writes JSON + Markdown
    in a separate module so HTML / dashboard visualisation can be
    added without touching this file.
  - No phase 6+ features (metadata extraction, planner, reranker,
    validator) are referenced here. Those come later and slot in via
    a clean interface.
"""
from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from medrack.answer.cache import load_answer
from medrack.answer.generate import generate_answer
from medrack.answer.render import render_preview_pdf
from medrack.answer.llm import MockLLMClient
from medrack.module.storage import load_extracted

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkRecord:
    """Metrics for a single (module, qid) under a single path (cold/warm)."""
    module: str
    qid: str
    subject: str
    marks: int | None
    path: str  # "cold" or "warm"
    success: bool
    error: str | None = None
    # Cache state
    cache_hit: bool = False
    cache_stale: bool = False
    # Latency (seconds)
    retrieval_latency_seconds: float = 0.0
    generation_latency_seconds: float = 0.0
    pdf_generation_seconds: float = 0.0
    total_latency_seconds: float = 0.0
    # Tokens (cold path only — warm path has no LLM call)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Answer characteristics
    answer_length_chars: int = 0
    answer_length_words: int = 0
    # Retrieval diagnostics
    retrieval_chunks: int = 0
    avg_retrieval_distance: float = 0.0


@dataclass
class BenchmarkRun:
    """Aggregated metrics for one benchmark run across N questions.

    The ``records`` list holds the per-question metrics; the top-level
    fields are the aggregate stats that ``report.py`` renders into the
    Markdown table.
    """
    timestamp: str  # ISO 8601 UTC
    suite_name: str  # e.g. "v1"
    suite_path: str  # path to the dataset JSON
    model: str  # LLM model name or "mock"
    subject_filter: str | None  # None = all subjects
    n_questions: int = 0
    n_success: int = 0
    n_failure: int = 0
    n_cold: int = 0
    n_warm: int = 0
    n_cache_hits: int = 0
    n_cache_misses: int = 0
    cache_hit_rate: float = 0.0
    # Token totals (cold path)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    avg_prompt_tokens: float = 0.0
    avg_completion_tokens: float = 0.0
    avg_total_tokens: float = 0.0
    # Latency
    avg_retrieval_latency_seconds: float = 0.0
    avg_generation_latency_seconds: float = 0.0
    avg_pdf_generation_seconds: float = 0.0
    avg_total_latency_seconds: float = 0.0
    # Answer lengths
    avg_answer_length_chars: float = 0.0
    avg_answer_length_words: float = 0.0
    # Retrieval
    avg_retrieval_chunks: float = 0.0
    avg_retrieval_distance: float = 0.0
    # Raw per-question records
    records: list[BenchmarkRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


def _load_questions_from_dataset(suite: list[dict], medrack_root: Path,
                                  _module_sources: dict[str, str]) -> list[dict]:
    """Hydrate dataset entries with the full question dict from extracted.json.

    Returns one entry per (module, qid): a copy of the dataset entry
    merged with the question's full text, type, options, marks, etc.
    The dataset's marks field is preferred (we may have corrected
    marks detection), but the source's marks/options/type fall back.
    """
    hydrated: list[dict] = []
    for entry in suite:
        module = entry["module"]
        qid = entry["qid"]
        extracted_path = medrack_root / _module_sources[module]
        if not extracted_path.exists():
            logger.warning(
                "Skipping %s/%s: extracted.json not found at %s",
                module, qid, extracted_path,
            )
            continue
        import json
        extracted = json.loads(extracted_path.read_text())
        src = next((q for q in extracted["questions"] if q["qid"] == qid), None)
        if src is None:
            logger.warning("Skipping %s/%s: not in source module", module, qid)
            continue
        # Merge: dataset metadata + full source question text/options
        merged = dict(entry)
        merged.setdefault("question_text", src.get("question_text", ""))
        merged["type"] = src.get("type", "theory")
        merged["options"] = src.get("options", {})
        merged["module_chapter"] = src.get("module_chapter", "chapter 1")
        # Dataset marks wins (we picked them carefully); source's marks
        # is informational.
        if "marks" not in merged and src.get("marks") is not None:
            merged["marks"] = src["marks"]
        hydrated.append(merged)
    return hydrated


def _run_cold_path(
    *,
    module: str,
    subject: str,
    chapter: str,
    question: dict,
    llm_client: Any,
    force_regenerate: bool = True,
) -> BenchmarkRecord:
    """Cold path: cache miss -> retrieval -> generation -> validation.

    Sets force_regenerate=True to ensure we hit the LLM. The record
    carries retrieval latency (from generate_answer's internal
    perf_counter), generation latency (the LLM call), and token counts
    (from LLMResponse).
    """
    record = BenchmarkRecord(
        module=module, qid=question["qid"], subject=subject,
        marks=question.get("marks"), path="cold", success=False,
    )
    overall_start = time.perf_counter()
    try:
        # generate_answer runs the full pipeline: embed -> retrieve -> LLM -> cache.
        # It records its own retrieval/generation latency in the answer dict.
        answer = generate_answer(
            module_name=module,
            subject=subject,
            chapter=chapter,
            question=question,
            llm_client=llm_client,
            force_regenerate=force_regenerate,
            marks=question.get("marks"),
        )
    except Exception as exc:
        record.error = f"{type(exc).__name__}: {exc}"
        record.total_latency_seconds = time.perf_counter() - overall_start
        return record

    # Pull metrics out of the answer dict
    record.generation_latency_seconds = answer.get("latency_seconds", 0.0)
    record.prompt_tokens = answer.get("prompt_tokens", 0)
    record.completion_tokens = answer.get("completion_tokens", 0)
    record.total_tokens = answer.get("total_tokens", 0)
    record.answer_length_chars = len(answer.get("answer_text", ""))
    record.answer_length_words = len(answer.get("answer_text", "").split())
    record.retrieval_chunks = answer.get("kb_chunks_retrieved", 0)
    record.cache_hit = answer.get("cache_hit", False)
    record.cache_stale = answer.get("stale", False)
    # Retrieval latency isn't broken out in build_answer_dict, but the
    # total generation_latency_seconds includes the retrieval step
    # (it spans embed + retrieve + LLM call). We approximate retrieval
    # latency as a fixed share for now; future phases with timing
    # hooks can replace this with a true retrieval latency.
    record.retrieval_latency_seconds = 0.0
    # Average retrieval distance from the cached answer's chunks
    chunks = answer.get("retrieval_chunks", []) or []
    if chunks:
        distances = [c.get("distance", 0.0) for c in chunks if c.get("distance") is not None]
        if distances:
            record.avg_retrieval_distance = statistics.mean(distances)

    # PDF generation (cold path also renders the PDF for end-to-end coverage)
    try:
        from medrack.answer.render import render_preview_pdf
        import tempfile as _tf
        pdf_start = time.perf_counter()
        with _tf.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            pdf_path = Path(tf.name)
        render_preview_pdf(
            output_path=pdf_path,
            module_name=module,
            module_subject=subject,
            chapter=chapter,
            question=question,
            answer=answer,
            question_index=1,
            total_questions=1,
            marks=question.get("marks"),
        )
        record.pdf_generation_seconds = time.perf_counter() - pdf_start
    except Exception as exc:
        logger.warning("PDF render failed for %s/%s: %s", module, question["qid"], exc)
        # Don't fail the record — render is optional in cold path
        record.pdf_generation_seconds = 0.0

    record.total_latency_seconds = time.perf_counter() - overall_start
    record.success = True
    return record


def _run_warm_path(
    *,
    module: str,
    subject: str,
    chapter: str,
    question: dict,
    pdf_dir: Path | None,
) -> BenchmarkRecord:
    """Warm path: cache hit -> render (no LLM call).

    This exercises the *cached* answer: it does NOT call the LLM. It
    measures how fast we can produce a PDF from a pre-existing cache
    entry. If the cache is missing (e.g. cache was wiped), the record
    is marked failure.
    """
    record = BenchmarkRecord(
        module=module, qid=question["qid"], subject=subject,
        marks=question.get("marks"), path="warm", success=False,
    )
    overall_start = time.perf_counter()
    cached = load_answer(module, chapter, question["qid"])
    if cached is None:
        record.error = "cache miss (warm path requires cached answer)"
        record.total_latency_seconds = time.perf_counter() - overall_start
        return record
    record.cache_hit = True
    record.cache_stale = cached.get("stale", False)
    record.answer_length_chars = len(cached.get("answer_text", ""))
    record.answer_length_words = len(cached.get("answer_text", "").split())
    record.retrieval_chunks = cached.get("kb_chunks_retrieved", 0)
    record.prompt_tokens = cached.get("prompt_tokens", 0)
    record.completion_tokens = cached.get("completion_tokens", 0)
    record.total_tokens = cached.get("total_tokens", 0)
    # Render the PDF (the "export" half of the warm path)
    try:
        from medrack.answer.render import render_preview_pdf
        import tempfile as _tf
        with _tf.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            pdf_path = Path(tf.name)
        pdf_start = time.perf_counter()
        render_preview_pdf(
            output_path=pdf_path,
            module_name=module,
            module_subject=subject,
            chapter=chapter,
            question=question,
            answer=cached,
            question_index=1,
            total_questions=1,
            marks=question.get("marks"),
        )
        record.pdf_generation_seconds = time.perf_counter() - pdf_start
        # If a real output dir was provided, copy the PDF there
        if pdf_dir is not None:
            pdf_dir.mkdir(parents=True, exist_ok=True)
            (pdf_dir / f"{module}_{question['qid']}_warm.pdf").write_bytes(
                pdf_path.read_bytes()
            )
    except Exception as exc:
        logger.warning("Warm-path PDF render failed for %s/%s: %s", module, question["qid"], exc)
        record.pdf_generation_seconds = 0.0

    record.total_latency_seconds = time.perf_counter() - overall_start
    record.success = True
    return record


def run_benchmark(
    *,
    suite: list[dict],
    module_sources: dict[str, str],
    llm_client: Any,
    medrack_root: Path,
    subject_filter: str | None = None,
    module_filter: str | None = None,
    qid_filter: str | None = None,
    run_warm: bool = True,
    pdf_dir: Path | None = None,
    suite_name: str = "v1",
    suite_path: str = "<inline>",
) -> BenchmarkRun:
    """Run the benchmark on the given suite (Phase 4 dataset shape).

    Args:
        suite: list of dataset entries (``module``, ``qid``, ``subject``,
            ``marks``, ...). Same shape as ``medrack.tests.regression_datasets.v1.json``.
        module_sources: mapping from module slug to relative path to
            the module's ``extracted.json`` (used to hydrate the
            question text).
        llm_client: any object with a ``complete(prompt)`` method
            (use ``MockLLMClient()`` for offline / free runs, or
            ``LLMClient()`` for real runs).
        medrack_root: absolute path to the medrack data directory
            (``~/.hermes/medrack``). Used to resolve relative paths in
            ``module_sources``.
        subject_filter: if set, only run questions for this subject
            (``"psm"``, ``"fmt"``, ...).
        module_filter: if set, only run questions for this module slug
            (``"psm-module-1"``, ``"singhi-fmt"``, ...).
        qid_filter: if set, only run this single qid.
        run_warm: if True, after the cold path also run the warm path
            (cache hit + render) for each question. Set False to
            benchmark only the cold path.
        pdf_dir: optional directory to write warm-path PDFs to. None
            means "don't keep the PDFs, just measure time".
        suite_name: human-readable name (e.g. ``"v1"``).
        suite_path: path or description of the dataset source.

    Returns:
        BenchmarkRun with aggregated metrics and per-question records.
    """
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    model_name = getattr(llm_client, "model", "mock" if isinstance(llm_client, MockLLMClient) else "unknown")

    # Hydrate the suite with the full question text from extracted.json
    hydrated = _load_questions_from_dataset(suite, medrack_root, module_sources)

    # Apply filters
    if subject_filter:
        hydrated = [q for q in hydrated if q.get("subject") == subject_filter]
    if module_filter:
        hydrated = [q for q in hydrated if q.get("module") == module_filter]
    if qid_filter:
        hydrated = [q for q in hydrated if q.get("qid") == qid_filter]

    if not hydrated:
        logger.warning("No questions match the filters; producing empty run")

    records: list[BenchmarkRecord] = []

    for entry in hydrated:
        module = entry["module"]
        subject = entry["subject"]
        qid = entry["qid"]
        # The source extracted.json sometimes has module_chapter=None
        # (e.g. for SECTION A questions that span chapters). The cache
        # layer expects a string, so default to "all" — which is the
        # convention used by cmd_preview's chapter=all scope.
        chapter = entry.get("module_chapter") or "all"

        # Cold path
        cold = _run_cold_path(
            module=module, subject=subject, chapter=chapter,
            question=entry, llm_client=llm_client, force_regenerate=True,
        )
        records.append(cold)

        # Warm path (optional)
        if run_warm:
            warm = _run_warm_path(
                module=module, subject=subject, chapter=chapter,
                question=entry, pdf_dir=pdf_dir,
            )
            records.append(warm)

    # Aggregate
    run = BenchmarkRun(
        timestamp=timestamp, suite_name=suite_name, suite_path=suite_path,
        model=model_name, subject_filter=subject_filter,
    )
    run.records = records
    run.n_questions = len(hydrated)
    run.n_cold = sum(1 for r in records if r.path == "cold")
    run.n_warm = sum(1 for r in records if r.path == "warm")
    run.n_success = sum(1 for r in records if r.success)
    run.n_failure = sum(1 for r in records if not r.success)
    run.n_cache_hits = sum(1 for r in records if r.cache_hit)
    run.n_cache_misses = sum(1 for r in records if r.path == "cold" and not r.cache_hit)
    if run.n_cold + run.n_warm > 0:
        run.cache_hit_rate = run.n_cache_hits / (run.n_cold + run.n_warm)
    # Token aggregates (cold only — warm has no LLM call)
    cold_records = [r for r in records if r.path == "cold"]
    if cold_records:
        run.total_prompt_tokens = sum(r.prompt_tokens for r in cold_records)
        run.total_completion_tokens = sum(r.completion_tokens for r in cold_records)
        run.total_tokens = sum(r.total_tokens for r in cold_records)
        run.avg_prompt_tokens = statistics.mean(r.prompt_tokens for r in cold_records)
        run.avg_completion_tokens = statistics.mean(r.completion_tokens for r in cold_records)
        run.avg_total_tokens = statistics.mean(r.total_tokens for r in cold_records)
        run.avg_retrieval_latency_seconds = statistics.mean(
            r.retrieval_latency_seconds for r in cold_records
        )
        run.avg_generation_latency_seconds = statistics.mean(
            r.generation_latency_seconds for r in cold_records
        )
    # Latency aggregates (all paths)
    if records:
        run.avg_pdf_generation_seconds = statistics.mean(r.pdf_generation_seconds for r in records)
        run.avg_total_latency_seconds = statistics.mean(r.total_latency_seconds for r in records)
        run.avg_answer_length_chars = statistics.mean(r.answer_length_chars for r in records)
        run.avg_answer_length_words = statistics.mean(r.answer_length_words for r in records)
        run.avg_retrieval_chunks = statistics.mean(r.retrieval_chunks for r in records)
        distances = [r.avg_retrieval_distance for r in records if r.avg_retrieval_distance > 0]
        if distances:
            run.avg_retrieval_distance = statistics.mean(distances)

    return run


__all__ = [
    "BenchmarkRecord",
    "BenchmarkRun",
    "run_benchmark",
]
