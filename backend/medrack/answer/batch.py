"""The full-batch answer orchestrator (Stage 2.5, B1).

Drives :func:`medrack.answer.generate.generate_answer` over a list of
questions (typically all questions in a module, or filtered down to
a single chapter) and aggregates the results into a single
``BatchResult`` that downstream renderers and the CLI can consume.

Public interface:
    BatchResult — dataclass of metadata + per-question answers
    generate_full_batch(*, module_name, subject, questions, llm_client,
                         chapter_filter=None, force_regenerate=False) -> BatchResult

Design notes:
- The function is *agnostic* about how questions are obtained; it just
  takes a list. This makes it testable (the brief's tests build the
  list in-memory) and reusable (the CLI loads it from
  ``extracted.json``).
- The chapter filter is a case-insensitive substring match on
  ``question["module_chapter"]``. We do *not* normalise the chapter
  string further; the brief pins the match style.
- A failure of one question (e.g. ``LLMUnavailableError`` from the
  LLM client) does NOT abort the batch — the qid is recorded in
  ``BatchResult.failed_qids`` and the loop continues. This is what
  makes the "approve" flow safe to run unattended.
- ``time.perf_counter()`` is used for the wall-clock measurement so
  the elapsed time is monotonic and high-resolution (we don't care
  about absolute clock time, only about the duration).
- Mutable defaults (``list`` and ``dict``) use ``field(default_factory=...)``
  so each constructed ``BatchResult`` gets a fresh container — sharing
  a single mutable default across instances is a classic Python
  footgun.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from medrack.answer.cache import load_answer
from medrack.answer.generate import generate_answer
from medrack.answer.llm import LLMUnavailableError
from medrack.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BatchResult:
    """Aggregated result of running ``generate_full_batch``.

    Attributes
    ----------
    module_name:
        e.g. ``"psm-module-1"``.
    subject:
        e.g. ``"psm"`` — used to scope retrieval in the per-question
        generation step.
    chapters:
        Sorted, de-duplicated list of chapter names that were
        processed. ``[]`` if no questions matched the filter.
    questions_total:
        Number of questions the batch attempted to process (after
        the chapter filter is applied).
    questions_generated:
        Number answered by calling the LLM (i.e. cache miss or
        ``force_regenerate``).
    questions_cached:
        Number served from the on-disk answer cache.
    questions_failed:
        Number whose ``generate_answer`` raised
        :class:`LLMUnavailableError`. The qid is recorded in
        ``failed_qids`` and the loop continues — the batch is
        "best effort".
    answers:
        The answer dicts in input order, excluding failures. Each
        entry is the locked schema produced by
        :func:`medrack.answer.generate.generate_answer`.
    failed_qids:
        The qids of questions whose generation failed. The
        corresponding ``questions`` rows are NOT in ``answers``.
    total_tokens:
        Sum of ``total_tokens`` across the included answers
        (cached + generated; failures contribute 0).
    total_latency_seconds:
        Sum of the LLM ``latency_seconds`` across the included
        answers (cached + generated; failures contribute 0).
    elapsed_seconds:
        Wall-clock duration of the batch as measured by
        :func:`time.perf_counter`.
    """

    module_name: str
    subject: str
    chapters: list[str] = field(default_factory=list)
    questions_total: int = 0
    questions_generated: int = 0
    questions_cached: int = 0
    questions_failed: int = 0
    answers: list[dict] = field(default_factory=list)
    failed_qids: list[str] = field(default_factory=list)
    total_tokens: int = 0
    total_latency_seconds: float = 0.0
    elapsed_seconds: float = 0.0


def _passes_chapter_filter(question: dict, chapter_filter: str | None) -> bool:
    """Case-insensitive substring match on ``question['module_chapter']``.

    The filter is matched *as a substring* so callers can use coarse
    strings like ``"chapter 1"`` to catch ``"chapter 10"`` (which is
    what the brief calls out as acceptable behaviour).
    """
    if chapter_filter is None:
        return True
    chapter = (question.get("module_chapter") or "").lower()
    return chapter_filter.lower() in chapter


def generate_full_batch(
    *,
    module_name: str,
    subject: str,
    questions: list[dict],
    llm_client,
    chapter_filter: str | None = None,
    force_regenerate: bool = False,
    progress=None,
    marks: int | None = None,
    word_targets: dict | None = None,
) -> BatchResult:
    """Generate answers for every question in the list, returning a BatchResult.

    Parameters
    ----------
    module_name:
        e.g. ``"psm-module-1"``. Used for cache lookups and persisted
        answer files.
    subject:
        e.g. ``"psm"``. Passed through to ``generate_answer`` to
        scope retrieval against the ``kb_<subject>`` collection.
    questions:
        List of question dicts (typically from
        ``extracted.json``). Each must include ``qid``, ``type``,
        ``question_text``, and ``module_chapter`` (the latter is
        used by the chapter filter; missing chapters are treated as
        empty strings).
    llm_client:
        Any object exposing a ``complete(prompt)`` method that
        returns an :class:`LLMResponse`. Injectable for tests.
    chapter_filter:
        Optional case-insensitive substring filter applied to
        ``question['module_chapter']``. If ``None`` (the default),
        all questions are processed.
    force_regenerate:
        If True, skip the cache for every question and always call
        the LLM pipeline. Defaults to False.

    Returns
    -------
    BatchResult
        See the dataclass docstring. The result is always returned;
        a batch with *every* question failing is still a valid
        ``BatchResult`` (with empty ``answers`` and a full
        ``failed_qids`` list).

    Algorithm
    ---------
    1. Start the wall-clock timer.
    2. Filter ``questions`` by ``chapter_filter`` (substring match,
       case-insensitive).
    3. For each surviving question:
       a. If not ``force_regenerate``, call
          ``load_answer(module_name, chapter, qid)``. If non-None,
          use it directly; increment ``questions_cached`` and add
          the cached answer's tokens / latency to the running
          totals.
       b. Otherwise (or on cache miss), call
          ``generate_answer(...)``. On success, append to
          ``answers``, increment ``questions_generated``, add tokens
          and latency to the totals.
       c. If ``generate_answer`` raises
          :class:`LLMUnavailableError`, record the qid in
          ``failed_qids``, increment ``questions_failed``, and
          continue with the next question.
    4. Compute the chapter list (sorted, deduped) and the elapsed
       seconds, build the :class:`BatchResult`, return.
    """
    started = time.perf_counter()

    # Step 2: filter by chapter.
    filtered: list[dict] = [
        q for q in questions if _passes_chapter_filter(q, chapter_filter)
    ]

    # Step 3: iterate.
    answers: list[dict] = []
    failed_qids: list[str] = []
    questions_generated = 0
    questions_cached = 0
    questions_failed = 0
    total_tokens = 0
    total_latency_seconds = 0.0
    chapters_seen: set[str] = set()

    for _idx, question in enumerate(filtered):
        # Report progress at the top so every path (cache hit, generate,
        # failure) is counted uniformly. Reports questions completed so far.
        if progress is not None:
            try:
                progress(_idx, len(filtered))
            except Exception:  # noqa: BLE001 - progress must never break the batch
                pass
        qid = question["qid"]
        chapter = question.get("module_chapter") or "unknown"
        chapters_seen.add(chapter)

        # 3a: cache lookup.
        if not force_regenerate:
            cached = load_answer(module_name, chapter, qid)
            if cached is not None:
                logger.info(
                    "Batch cache hit: module=%s chapter=%s qid=%s",
                    module_name, chapter, qid,
                )
                # Mark the cached answer's cache_hit flag (the loader
                # gives us back the raw dict as written; the
                # orchestrator usually re-marks this when it serves
                # the answer).
                cached["cache_hit"] = True
                answers.append(cached)
                questions_cached += 1
                total_tokens += int(cached.get("total_tokens") or 0)
                total_latency_seconds += float(
                    cached.get("latency_seconds") or 0.0
                )
                continue

        # 3b: generate.
        try:
            # Per-question marks if the bank carries a valid 5/10; else the
            # caller-selected default (the UI "answer length" choice).
            q_marks = question.get("marks")
            if q_marks not in (5, 10):
                q_marks = marks
            # Per-marks word target (the UI's two length boxes), keyed by
            # the resolved marks. None -> prompt builder derives from marks.
            q_wct = word_targets.get(q_marks) if word_targets else None
            answer = generate_answer(
                module_name=module_name,
                subject=subject,
                chapter=chapter,
                question=question,
                llm_client=llm_client,
                force_regenerate=force_regenerate,
                marks=q_marks,
                word_count_target=q_wct,
            )
        except LLMUnavailableError as exc:
            # 3c: failure path — record and continue.
            logger.warning(
                "Batch LLM unavailable for qid=%s: %s; continuing batch.",
                qid, exc,
            )
            failed_qids.append(qid)
            questions_failed += 1
            continue

        answers.append(answer)
        questions_generated += 1
        total_tokens += int(answer.get("total_tokens") or 0)
        total_latency_seconds += float(answer.get("latency_seconds") or 0.0)

    if progress is not None:
        try:
            progress(len(filtered), len(filtered))
        except Exception:  # noqa: BLE001
            pass

    # Step 4: finalise.
    elapsed = time.perf_counter() - started
    chapters_sorted = sorted(chapters_seen)

    return BatchResult(
        module_name=module_name,
        subject=subject,
        chapters=chapters_sorted,
        questions_total=len(filtered),
        questions_generated=questions_generated,
        questions_cached=questions_cached,
        questions_failed=questions_failed,
        answers=answers,
        failed_qids=failed_qids,
        total_tokens=total_tokens,
        total_latency_seconds=total_latency_seconds,
        elapsed_seconds=elapsed,
    )


__all__ = ["BatchResult", "generate_full_batch"]
