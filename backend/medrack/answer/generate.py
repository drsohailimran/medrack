"""The answer-generation orchestrator (Stage 2.4, A5).

Ties together LLM + retrieval + prompt + cache. Given a question and a
module, ``generate_answer`` either returns a cached answer (if present
and not forced to regenerate) or builds the full pipeline:

    embed question -> query kb_<subject> for top_k=8 chunks
                    -> build MCQ or Theory prompt
                    -> call LLM
                    -> build answer dict
                    -> save to cache
                    -> return

Public interface:
    generate_answer(*, module_name, subject, chapter, question,
                    llm_client, force_regenerate=False) -> dict

Design notes:
- The locked answer-dict schema is defined by the brief; see the
  ``build_answer_dict`` helper for the field-by-field construction.
- The cache key stored in the answer dict is the deterministic
  ``cache_key_for_question`` hash from ``medrack.answer.cache``. In
  Stage 2.5, callers can compare keys to detect template/model drift;
  for A5 the cache is a pure hit-or-miss lookup controlled by the
  ``force_regenerate`` flag.
- The retrieval step uses ``medrack.ingest.embed.get_model()`` (the
  module-level singleton) and ``medrack.ingest.index.query``. The
  subject filter is enforced structurally by the per-subject
  ChromaDB collection layout.
- ``medrack.utils.logger.get_logger`` is used so this module's events
  (cache hits, retrievals, LLM calls) show up in the standard MedRack
  log stream.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from medrack.answer.cache import (
    cache_key_for_question,
    load_answer,
    save_answer,
)
from medrack.answer.llm import LLMClient
from medrack.answer.prompt import build_mcq_prompt, build_theory_prompt
from medrack.ingest.embed import get_model
from medrack.ingest.index import query
from medrack.utils.logger import get_logger

logger = get_logger(__name__)


# How many chunks to pull from the KB. The brief pins this at 8.
# (medrack.config.RETRIEVAL_TOP_K is the same value, but we hard-code
# here so the orchestrator is self-contained and test-friendly.)
RETRIEVAL_TOP_K = 8


def _clean_answer_text(text: str) -> str:
    """Strip truncated tails that cause TruncationRule fails / ugly PDFs.

    - Trailing empty bullets (``•`` / ``-`` alone)
    - Trailing incomplete connector lines (``and``, ``including``, …)
    - Incomplete last bullets cut by max_tokens (e.g. ``• HBNC is``)
    - Orphan heading with no body after a cut-off
    - Trailing ellipsis-only endings
    """
    if not text:
        return text
    lines = text.splitlines()
    empty_bullet = re.compile(r"^\s*[•\-\u2013\u2014\*]\s*$")
    bullet_line = re.compile(r"^\s*[•\-\u2013\u2014\*]\s+\S")
    connector_end = re.compile(
        r"(?i)\b(and|or|with|include|includes|including|such as|e\.g\.|i\.e\.|"
        r"is|are|was|were|to|of|for|the|a|an|in|on|by|as|from|that|which|"
        r"this|these|those|its|their|has|have|had|be|been|being)\s*$"
    )
    # Complete sentence / bullet usually ends with . ! ? : ) or closing **
    complete_end = re.compile(r"[.!?…:)\]]\s*$|\*\*\s*$")

    def _drop_trailing_blanks() -> None:
        while lines and not lines[-1].strip():
            lines.pop()

    def _is_incomplete_line(line: str) -> bool:
        s = line.strip()
        if not s:
            return True
        if empty_bullet.match(line):
            return True
        if connector_end.search(s):
            return True
        # Short bullet cut mid-thought (no terminal punctuation)
        if bullet_line.match(line) and not complete_end.search(s) and len(s) < 80:
            return True
        # Any last line without sentence end and very short
        if not complete_end.search(s) and len(s) < 40 and not s.endswith("**"):
            return True
        return False

    # Drop trailing blank / empty bullets / incomplete last lines (token cut-off)
    for _ in range(12):
        _drop_trailing_blanks()
        if not lines:
            break
        if _is_incomplete_line(lines[-1]):
            lines.pop()
            continue
        break

    # Drop orphan heading (bold / title) left with no body after cut-off
    heading_re = re.compile(r"^\s*(\*\*[^*].+\*\*|#{1,3}\s+\S|[A-Z][A-Za-z0-9 /&-]{2,60})\s*$")
    for _ in range(4):
        _drop_trailing_blanks()
        if not lines:
            break
        prev_blank = len(lines) >= 2 and not lines[-2].strip() if len(lines) >= 2 else True
        if heading_re.match(lines[-1]) and not bullet_line.match(lines[-1]):
            # heading with nothing under it
            lines.pop()
            continue
        break

    cleaned = "\n".join(lines).rstrip()
    cleaned = re.sub(r"(\.\.\.|…)\s*$", "", cleaned).rstrip()
    return cleaned


def _retrieval_query_boost(question_text: str) -> str:
    """Append topic cues so retrieval prefers the right Park chapters."""
    q = question_text or ""
    extras: list[str] = []
    if re.search(r"(?i)\badolescent", q):
        extras.append(
            "RKSK ARSH Rashtriya Kishor Swasthya Karyakram "
            "adolescent reproductive sexual health school health"
        )
    if re.search(r"(?i)\b(antenatal|anc)\b", q):
        extras.append("antenatal care ANC objectives elements high risk pregnancy")
    if re.search(r"(?i)\b(post\s*natal|postnatal|post\s*partal|pnc)\b", q):
        extras.append("postnatal care postpartum mother newborn")
    if re.search(r"(?i)\b(essential obstetric|emoc|bemoc|cemoc)\b", q):
        extras.append("essential obstetric care EmOC RCH FRU JSSK")
    if not extras:
        return q
    return q + "\n" + " ".join(extras)


def _embed_query(question_text: str) -> list[float]:
    """Encode the question text with the cached sentence-transformer.

    Returns a flat 1D list[float] (the brief's nominal interface) so
    ``medrack.ingest.index.query`` can wrap-or-flatten it as needed.
    """
    model = get_model()
    vec = model.encode([question_text], show_progress_bar=False)
    # vec is shape (1, dim); take the first row and tolist() it.
    return vec[0].tolist()


def _build_prompt(
    question: dict,
    chunk_texts: list[str],
    marks: int | None = None,
    subject: str = "psm",
    word_count_target: int | None = None,
):
    """Return ``(BuildResult, system_template_label)``.

    Picks the MCQ or Theory template based on ``question["type"]``.
    Raises ``ValueError`` for unknown types — fail loud, not silent.

    Args:
        question: question dict from extracted.json.
        chunk_texts: retrieved KB chunks for the question.
        marks: target marks value (5 or 10) for theory questions. If
            None, falls back to the configured default.
        subject: subject key for the subject-aware prompt context
            (Phase 2, directive v1.0). Defaults to ``"psm"`` for
            backward compatibility; unknown subjects fall back to the
            ``generic`` entry inside the prompt builder.
    """
    qtype = question.get("type")
    if qtype == "mcq":
        return build_mcq_prompt(
            question_text=question["question_text"],
            options=question.get("options", {}),
            retrieved_chunks=chunk_texts,
            subject=subject,
        )
    if qtype == "theory":
        # Use the question's marks (5 or 10) to set the answer length.
        # If marks is None, fall back to the configured default.
        if marks is None:
            from medrack import config
            marks = config.THEORY_DEFAULT_MARKS
        # Tell Pyright marks is now int (not None).
        assert marks is not None
        return build_theory_prompt(
            question_text=question["question_text"],
            retrieved_chunks=chunk_texts,
            marks=marks,
            word_count_target=word_count_target,
            subject=subject,
        )
    raise ValueError(
        f"Unknown question type: {qtype!r}. Expected 'mcq' or 'theory'."
    )


def _transform_chunks(raw_results: list[dict]) -> list[dict]:
    """Convert ChromaDB query results into the answer-dict shape.

    Each input row has ``id``, ``text``, ``metadata`` (with the
    fields ``page_start``, ``page_end``, ...), and ``distance``.
    We project to ``chunk_id``, ``text``, ``page_start``, ``page_end``,
    ``distance`` per the locked schema.
    """
    out: list[dict] = []
    for r in raw_results:
        md = r.get("metadata") or {}
        out.append({
            "chunk_id": r.get("id"),
            "text": r.get("text", ""),
            "page_start": md.get("page_start"),
            "page_end": md.get("page_end"),
            "distance": r.get("distance"),
        })
    return out


def build_answer_dict(
    *,
    question: dict,
    module_name: str,
    subject: str,
    chapter: str,
    system_template: str,
    llm_response,  # LLMResponse (forward ref to avoid import cycle in tests)
    retrieval_chunks: list[dict],
    cache_hit: bool = False,
    cache_key: str | None = None,
    target_word_count: int | None = None,
) -> dict:
    """Construct the answer dict in the brief's locked schema.

    The function is exposed (not internal) so the orchestrator can be
    unit-tested on schema construction without touching the LLM or
    ChromaDB. ``cache_key`` is stored under the underscored key
    ``_cache_key`` so callers can perform staleness checks; it is not
    part of the public schema, just internal bookkeeping.

    Phase 3: also records ``package_version``, ``versions``,
    ``target_word_count``, and ``embedding_model`` on every cached
    answer. These are read by ``medrack.answer.versioning.is_stale``
    to determine if a cached answer needs regeneration. The
    ``stale`` and ``stale_reasons`` fields default to ``False`` and
    ``[]`` for fresh answers; they get populated by ``load_answer`` if
    a version mismatch is detected.
    """
    from medrack import __version__ as _pkg_version
    from medrack import config as _config

    now_iso = datetime.now(timezone.utc).isoformat()
    n_retrieved = len(retrieval_chunks)
    answer: dict[str, Any] = {
        "qid": question["qid"],
        "module_name": module_name,
        "module_subject": subject,
        "question_text": question["question_text"],
        "question_type": question.get("type", "unknown"),
        "module_chapter": question.get("module_chapter") or "unknown",
        "answer_text": llm_response.text,
        "retrieval_chunks": retrieval_chunks,
        "prompt_tokens": llm_response.prompt_tokens,
        "completion_tokens": llm_response.completion_tokens,
        "total_tokens": llm_response.total_tokens,
        "model": llm_response.model,
        "latency_seconds": llm_response.latency_seconds,
        "cache_hit": cache_hit,
        "used_general_fallback": n_retrieved == 0,
        "kb_chunks_retrieved": n_retrieved,
        "generated_at": now_iso,
        # Phase 3: layered answer versioning (directive v1.0).
        # These fields let load_answer decide if this cache entry is
        # still valid without consulting the orchestrator.
        "package_version": _pkg_version,
        "versions": dict(_config.PIPELINE_VERSIONS),
        "embedding_model": _config.EMBEDDING_MODEL,
        # staleness defaults — load_answer will set stale=True if a
        # version drift is detected at read time.
        "stale": False,
        "stale_reasons": [],
    }
    if target_word_count is not None:
        answer["target_word_count"] = target_word_count
    # Internal: stash the cache key for Stage 2.5 invalidation. The
    # public schema does not include this, but persisting it is what
    # makes a future "is this cache entry stale?" check possible.
    if cache_key is not None:
        answer["_cache_key"] = cache_key
    return answer


def generate_answer(
    *,
    module_name: str,
    subject: str,
    chapter: str,
    question: dict,
    llm_client: LLMClient,
    force_regenerate: bool = False,
    marks: int | None = None,
    word_count_target: int | None = None,
) -> dict:
    """Generate an answer for a question, using the cache when possible.

    Parameters
    ----------
    module_name:
        e.g. ``"psm-module-1"``.
    subject:
        The module's subject, used to scope retrieval
        (``kb_<subject>`` collection). e.g. ``"psm"``.
    chapter:
        Chapter name, e.g. ``"chapter 1"``. Used as the cache directory.
    question:
        Question dict (from ``extracted.json``). Must include at least
        ``qid``, ``type``, ``question_text``, and (for MCQ) ``options``.
    llm_client:
        An ``LLMClient`` (or any object with a ``complete(prompt)``
        method that returns an ``LLMResponse``). Injectable for tests.
    force_regenerate:
        If True, skip the cache lookup and always run the full pipeline.
        Defaults to False.
    marks:
        Target marks value (5 or 10) for theory questions. If None, the
        configured default (10-mark) is used. Ignored for MCQs.

    Returns
    -------
    dict
        The answer dict (locked schema). On a cache hit, the same dict
        that was previously persisted is returned, with ``cache_hit=True``.

    Algorithm
    ---------
    1. If not ``force_regenerate``, look up the cached answer. If
       present, return it with ``cache_hit=True`` (the prototype does
       not do staleness checks; see ``build_answer_dict`` for the
       ``_cache_key`` hook used by Stage 2.5).
    2. Embed the question text with the cached sentence-transformer.
    3. Query the ``kb_<subject>`` collection for top_k=8 chunks.
    4. Build the prompt (MCQ or Theory template).
    5. Call ``llm_client.complete(prompt)`` → ``LLMResponse``.
    6. Build the answer dict, save to cache, return.
    """
    qid = question["qid"]
    question_text = question["question_text"]

    # Step 1: cache lookup (unless force_regenerate).
    # P0: if the cached answer is stale (pipeline drift or KB reindex),
    # fall through and regenerate instead of serving outdated text.
    if not force_regenerate:
        cached = load_answer(module_name, chapter, qid)
        if cached is not None and not cached.get("stale"):
            logger.info(
                "Cache hit: module=%s chapter=%s qid=%s",
                module_name, chapter, qid,
            )
            cached["cache_hit"] = True
            return cached
        if cached is not None and cached.get("stale"):
            logger.info(
                "Cache stale (reasons=%s); regenerating: module=%s chapter=%s qid=%s",
                cached.get("stale_reasons"), module_name, chapter, qid,
            )

    # Step 2: embed the question text (with topic boost for retrieval).
    logger.info(
        "Generating answer: module=%s chapter=%s qid=%s subject=%s",
        module_name, chapter, qid, subject,
    )
    retrieval_query = _retrieval_query_boost(question_text)
    query_embedding = _embed_query(retrieval_query)

    # Step 3: adaptive retrieval (Phase 7). The retrieval engine
    # composes question analysis, strategy-based top_k + filter, and
    # metadata-boost reranking. The vector similarity remains the
    # primary mechanism; metadata is an additional signal.
    from medrack.retrieval import retrieve_for_question
    # Use boosted text for analysis when helpful (keeps original stem in question dict).
    q_for_retrieval = dict(question)
    if retrieval_query != question_text:
        q_for_retrieval = {
            **question,
            "question_text": retrieval_query,
        }
    retrieval_result = retrieve_for_question(
        question=q_for_retrieval,
        subject=subject,
        query_embedding=query_embedding,
        marks=marks,
    )
    raw_results = retrieval_result.chunks
    retrieval_chunks = _transform_chunks(raw_results)
    # Cap the context that goes into the prompt: fewest, shortest chunks
    # that still ground the answer. Full chunks remain in retrieval_chunks
    # (the answer metadata); only the prompt context is trimmed so the LLM
    # input stays a few thousand tokens (avoids endpoint hangs on huge
    # book chunks). See config.PROMPT_CONTEXT_* .
    from medrack import config as _cfg
    _max_chunks = getattr(_cfg, "PROMPT_CONTEXT_MAX_CHUNKS", 5)
    _max_chars = getattr(_cfg, "PROMPT_CONTEXT_MAX_CHARS_PER_CHUNK", 1500)
    chunk_texts = [(r.get("text") or "")[:_max_chars] for r in raw_results[:_max_chunks]]
    logger.info(
        "Retrieved %d chunks from kb_%s (top_k=%d, filter=%s, marks=%s, sections=%s)",
        len(retrieval_chunks), subject,
        retrieval_result.top_k, retrieval_result.metadata_filter_active,
        marks, retrieval_result.analysis.target_sections,
    )

    # Step 4: build the prompt (MCQ or Theory). Subject flows through
    # to the prompt builder for subject-aware context (Phase 2).
    build_result = _build_prompt(
        question, chunk_texts, marks=marks, subject=subject,
        word_count_target=word_count_target,
    )
    system_template = build_result.system_template
    # Phase 3: capture the word count target the LLM was instructed
    # to hit. Recorded on the cached answer so a future word-count
    # revision (e.g. 775 -> 900) can mark old caches stale.
    target_word_count = build_result.word_count_target

    # Step 5: call the LLM. Budget the output tokens as the answer's word
    # target (~1.4 tokens/word) PLUS a fixed allowance for any tables /
    # flowcharts — their Markdown and DOT markup also consume tokens, so
    # without the allowance a diagram would truncate the written explanation.
    # The allowance covers roughly two tables + a flowchart. ~750 words ->
    # ~1550 tokens; ~375 words -> ~1025 tokens.
    # Budget tokens for the length band (P0.4).
    # Cap output near HARD MAXIMUM so the model cannot fill ~1900 tokens
    # and produce 1100+ word 10-mark laundry lists (seen on open EOC stems).
    # ~1.25–1.35 tokens/word is enough for point-form bullets + headings.
    _tw = target_word_count or 500
    _marks_i = int(marks) if marks is not None else (10 if _tw >= 500 else 5)
    if _marks_i <= 3 or _tw <= 150:
        max_out = int(_tw * 1.30) + 100
    elif _marks_i <= 5 or _tw <= 400:
        # P0.5c: keep answers compact but leave headroom to *finish* the last
        # bullet. Prior 551-token cap cut Q6 mid-phrase ("• HBNC is").
        # ~1.4 tokens/word for markdown bullets → ~560 body + finish buffer.
        max_out = int(_tw * 1.30) + 200  # 375 → ~687 tokens
    else:
        # 10-mark: enough headroom for multi-part full depth within band
        max_out = int(_tw * 1.40) + 200  # 750 → ~1250 tokens
    llm_response = llm_client.complete(build_result.prompt, max_output_tokens=max_out)

    # Build the cache key. Phase 3: includes PIPELINE_VERSIONS, subject,
    # target_word_count, and embedding_model so any pipeline drift
    # produces a different cache key (and the orchestrator regenerates).
    # Use getattr with a default in case the client doesn't expose `.model`
    # (e.g. MockLLMClient in tests).
    cache_key = cache_key_for_question(
        module_name=module_name,
        qid=qid,
        question_text=question_text,
        prompt_template=system_template,
        model=getattr(llm_client, "model", "unknown"),
        subject=subject,
        target_word_count=target_word_count,
    )

    # Step 6: assemble the answer dict.
    # Clean truncated tails (empty bullets, mid-phrase cuts) before validate/cache.
    if hasattr(llm_response, "text") and isinstance(llm_response.text, str):
        llm_response.text = _clean_answer_text(llm_response.text)

    answer = build_answer_dict(
        question=question,
        module_name=module_name,
        subject=subject,
        chapter=chapter,
        system_template=system_template,
        llm_response=llm_response,
        retrieval_chunks=retrieval_chunks,
        cache_hit=False,
        cache_key=cache_key,
        target_word_count=target_word_count,
    )

    # P0: record the KB revision this answer was grounded on.
    try:
        from medrack.answer.kb_revision import get_kb_revision
        answer["kb_revision"] = get_kb_revision(subject)
    except Exception:  # noqa: BLE001
        answer["kb_revision"] = 0

    # P0: validation gate (does NOT rewrite the answer; attaches a report).
    # FAIL → needs_review=True. Answer is still cached so overnight runs
    # are not blocked, but the UI / operator can filter on needs_review.
    try:
        from medrack.validation.pipeline import ValidationPipeline

        source_text = "\n\n".join(chunk_texts)
        # Prefer explicit marks arg; fall back to question field.
        v_marks = marks
        if v_marks is None:
            v_marks = question.get("marks")
        report = ValidationPipeline().validate(
            answer["answer_text"],
            blueprint=None,
            context={
                "source_text": source_text,
                "question_text": question_text,
                "marks": v_marks,
                "subject": subject,
                "target_word_count": target_word_count,
            },
        )
        answer["validation"] = report.to_dict()
        answer["needs_review"] = not report.pass_
        if answer["needs_review"]:
            logger.warning(
                "Validation FAIL for qid=%s failed_rules=%s score=%.2f",
                qid, report.failed_rules, report.score,
            )
        else:
            logger.info(
                "Validation PASS for qid=%s score=%.2f",
                qid, report.score,
            )
    except Exception:  # noqa: BLE001 — never block generation on validator bugs
        logger.exception("Validation pipeline failed for qid=%s", qid)
        answer["validation"] = {
            "schema_version": 1,
            "pass": True,
            "score": 1.0,
            "results": [],
            "failed_rules": [],
            "warnings": [],
            "informational_messages": ["validator_error_skipped"],
        }
        answer["needs_review"] = False

    save_answer(module_name, chapter, qid, answer)
    logger.info(
        "Saved answer: module=%s chapter=%s qid=%s tokens=%d needs_review=%s",
        module_name, chapter, qid, answer["total_tokens"],
        answer.get("needs_review"),
    )
    return answer


__all__ = ["generate_answer", "build_answer_dict", "RETRIEVAL_TOP_K"]
