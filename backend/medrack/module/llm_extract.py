"""LLM question extractor for MedRack module / question-bank ingest.

Stage 2.3 / Task M3 of the MedRack module ingest pipeline.

Public API:
    extract_questions_with_llm — ask an LLM to extract structured questions
                                 (both theory long/short-answer AND MCQs)
                                 from the cleaned page text of a module or
                                 question bank.

Design notes:
    * The LLM client is injectable. Tests pass a ``unittest.mock.MagicMock``
      whose ``complete(prompt, max_output_tokens=None) -> str`` returns a
      JSON string.
    * The page text is processed in *batches* so that an entire bank (not
      just the first few pages) is covered — the previous version only read
      the first 10 pages / 4000 chars, which silently dropped most of a
      large bank's questions. Each batch is a separate LLM call; results are
      merged and de-duplicated by normalised question text.
    * The response parser is robust to markdown fences, leading/trailing
      prose, and a *truncated* JSON array (it salvages every complete
      object it can), so a batch that overruns the output budget still
      contributes the questions it did emit.
    * Any failure of a single batch (client exception, unparseable output)
      is logged and skipped — the other batches still contribute.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)

# How much page text to hand the LLM per call. Large banks are processed in
# several batches so every page is seen. Input is small relative to modern
# context windows; the real constraint is keeping each batch's *output*
# (the questions JSON) within the model's max-output budget.
_MAX_CHARS_PER_BATCH = 9000
# Output-token budget per batch — generous so a batch's full question list
# is not truncated. (The extractor also salvages truncated arrays.)
_MAX_OUTPUT_TOKENS = 8000


def _build_prompt(subject: str, body: str) -> str:
    """Assemble the LLM prompt for one batch of page text."""
    return (
        f"Subject: {subject}\n\n"
        "You are extracting EXAM QUESTIONS from a medical question bank / "
        "module. Read the text below and return a JSON array containing "
        "EVERY question you find — do not skip any. Include BOTH "
        "long-answer / short-answer (theory) questions AND multiple-choice "
        "(MCQ) questions.\n\n"
        "Each array element must be an object with these keys:\n"
        '  "question_text": the full question text (do NOT include the answer),\n'
        '  "type": "mcq" if the question has lettered options, else "theory",\n'
        '  "marks": the marks as an integer if stated near the question '
        '(e.g. "(10 marks)" -> 10, "5 M" -> 5, "Long answer" -> 10, '
        '"Short note" -> 5), else null,\n'
        '  "options": for MCQs, an object mapping "a"/"b"/"c"/"d"/... to '
        "option text; for theory questions use an empty object {},\n"
        '  "answer": the correct option letter for MCQs if an answer key is '
        "visible, else null.\n\n"
        "Capture numbered questions (1., 2., Q1, Q.1), bulleted questions, "
        '"Write short notes on ...", "Describe ...", "Explain ...", '
        '"Define ...", "Enumerate ...", and every MCQ. '
        "Return ONLY the JSON array — no prose, no markdown code fences.\n\n"
        f"--- BEGIN TEXT ---\n{body}\n--- END TEXT ---"
    )


def _batch_pages(pages_text: list[str], max_chars: int) -> list[list[str]]:
    """Group consecutive pages into batches, each under ``max_chars``.

    A single page longer than ``max_chars`` becomes its own batch (it is
    never split further — the model sees it whole).
    """
    batches: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for page in pages_text:
        page = page or ""
        page_len = len(page) + 2  # +2 for the "\n\n" join
        if current and current_len + page_len > max_chars:
            batches.append(current)
            current = []
            current_len = 0
        current.append(page)
        current_len += page_len
    if current:
        batches.append(current)
    return batches


# ---------------------------------------------------------------------------
# Marks-section detection. Question banks usually group questions under
# headings that state the marks ("Long Answer Questions (10 marks)", "Short
# Notes — 5 marks"), with all 10-mark questions in one block and all 5-mark
# questions in another. We split the text at those headings so every question
# inherits its section's marks, and each block is answered at the right length.
# ---------------------------------------------------------------------------
_MARK10_RE = re.compile(
    r"(?i)\b(?:10|ten)\s*[-–]?\s*marks?\b|\blong\s+answer|\blong\s+essay|\bLAQ\b"
)
_MARK5_RE = re.compile(
    r"(?i)\b(?:5|five)\s*[-–]?\s*marks?\b|\bshort\s+answer|\bshort\s+notes?\b|\bSAQ\b"
)
_QNUM_RE = re.compile(r"^\s*(?:Q\.?\s*)?\d+\s*[.\):]")


def _heading_marks(line: str) -> int | None:
    """Return 10 or 5 if ``line`` looks like a marks-section heading, else None.

    A heading is a short line that names the marks/section — not a numbered
    question and not a line ending in '?'.
    """
    s = line.strip()
    if not s or len(s) > 55:
        return None
    if _QNUM_RE.match(s) or s.endswith("?"):
        return None  # a question line, not a section heading
    if _MARK10_RE.search(s):
        return 10
    if _MARK5_RE.search(s):
        return 5
    return None


def _split_by_marks_sections(pages_text: list[str]) -> list[tuple[int | None, str]]:
    """Split the joined page text into ``(marks, text)`` segments at marks
    headings. Text before the first heading gets ``marks=None``."""
    full = "\n".join(p or "" for p in pages_text)
    segments: list[tuple[int | None, str]] = []
    current_marks: int | None = None
    buf: list[str] = []
    for line in full.split("\n"):
        m = _heading_marks(line)
        if m is not None:
            if buf:
                segments.append((current_marks, "\n".join(buf)))
                buf = []
            current_marks = m
            continue  # drop the heading line itself
        buf.append(line)
    if buf:
        segments.append((current_marks, "\n".join(buf)))
    return segments


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split one text into ``<=max_chars`` chunks on line boundaries."""
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for line in text.split("\n"):
        if cur and cur_len + len(line) + 1 > max_chars:
            chunks.append("\n".join(cur))
            cur = []
            cur_len = 0
        cur.append(line)
        cur_len += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def _salvage_json_array(text: str) -> list[dict[str, Any]]:
    """Extract every complete top-level ``{...}`` object from ``text``.

    Used when the model's JSON array is truncated (output budget hit) or
    wrapped in stray prose — we still recover the objects it did finish.
    """
    objs: list[dict[str, Any]] = []
    depth = 0
    start: int | None = None
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        objs.append(json.loads(text[start : i + 1]))
                    except Exception:  # noqa: BLE001
                        pass
                    start = None
    return objs


def _parse_response(response: str) -> list[dict[str, Any]]:
    """Parse the LLM's response into a list of question dicts.

    Robust to markdown fences, leading/trailing prose, and truncated
    arrays (salvages complete objects).
    """
    text = (response or "").strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    # Trim to the first '[' so leading prose doesn't break json.loads.
    start = text.find("[")
    if start > 0:
        text = text[start:]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = _salvage_json_array(text)
    if not isinstance(parsed, list):
        raise ValueError("LLM response is not a JSON array")
    return parsed


def extract_questions_with_llm(
    pages_text: list[str],
    subject: str,
    llm_client: object = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Use the LLM to extract structured questions from page text.

    Args:
        pages_text: cleaned page texts. ALL pages are processed, in
            batches, so a large bank is fully covered.
        subject:    subject slug (e.g. "psm", "fmt") — included in the
            prompt for context.
        llm_client: object exposing
            ``complete(prompt, max_output_tokens=None) -> str``. Required.
        progress_cb: optional callback ``(batch_index, batch_total)`` called
            after each batch so the caller can advance a progress bar.

    Returns:
        A merged, de-duplicated list of question dicts. Returns ``[]`` if
        no questions could be extracted (every batch failed / empty).
    """
    if llm_client is None:
        raise NotImplementedError(
            "extract_questions_with_llm() requires an llm_client; "
            "the default real client is not yet wired (Stage 2.4)."
        )

    # Split the bank at marks-section headings, then batch each segment so a
    # question inherits the marks of the section it sits under.
    segments = _split_by_marks_sections(pages_text)
    batches: list[tuple[int | None, str]] = []
    for seg_marks, seg_text in segments:
        for chunk in _chunk_text(seg_text, _MAX_CHARS_PER_BATCH):
            if chunk.strip():
                batches.append((seg_marks, chunk))

    total = len(batches)
    all_questions: list[dict] = []
    seen: set[str] = set()

    for idx, (seg_marks, body) in enumerate(batches):
        prompt = _build_prompt(subject, body)
        try:
            response = llm_client.complete(prompt, max_output_tokens=_MAX_OUTPUT_TOKENS)
            questions = _parse_response(response)
        except Exception as exc:  # noqa: BLE001 — one bad batch must not sink the rest
            logger.warning(
                "LLM extraction batch %d/%d failed for subject=%r: %s",
                idx + 1, total, subject, exc,
            )
            questions = []

        for q in questions:
            if not isinstance(q, dict):
                continue
            qt = (q.get("question_text") or "").strip()
            if not qt:
                continue
            # De-dupe on the FULL normalised text — a truncated key would
            # wrongly merge distinct questions that share a long prefix
            # (e.g. "Write short notes on: (a) X" vs "(b) Y").
            key = " ".join(qt.lower().split())
            if key in seen:
                continue
            seen.add(key)
            # Section marks (from the heading) win; otherwise keep any inline
            # marks the model detected, normalised to an int.
            if seg_marks is not None:
                q["marks"] = seg_marks
            else:
                mv = q.get("marks")
                if isinstance(mv, str) and mv.strip().isdigit():
                    q["marks"] = int(mv)
            all_questions.append(q)

        if progress_cb:
            _safe_progress(progress_cb, idx + 1, total)

    return all_questions


def _safe_progress(cb: Callable[[int, int], None], i: int, n: int) -> None:
    try:
        cb(i, n)
    except Exception:  # noqa: BLE001 — progress must never break extraction
        pass
