"""MCQ question extraction from cleaned page text using regex.

Stage 2.3 / Task M2 of the MedRack module ingest pipeline.

Public API:
    ExtractedQuestion       — dataclass for a single extracted question.
    extract_mcqs_from_pages — extract every question (MCQ or theory) from a
                              list of cleaned page dicts.
    regex_extraction_coverage — fraction of pages that yield ≥ 1 question.
                              Used by callers to decide whether to fall
                              back to the LLM extractor (M3).

Design notes:
    * The input pages are assumed to have already been run through
      medrack.ingest.clean.clean_pages — letter-spacing artifacts
      (e.g. "D e f i n i t i o n") have been collapsed. We deliberately
      do NOT depend on `clean` here, to keep the module self-contained
      and easy to unit-test against synthetic strings.
    * The question-start regex is intentionally permissive about
      whitespace after the number+dot. The real PSM Module 1 PDF has
      patterns like "1.Definition of health..." with no space after the
      period, so we accept `1.` followed by zero or more spaces.
    * Option scanning is also permissive: options may be separated by
      ")( " (touching) or by " " (spaced). We use a non-greedy body
      with a lookahead that stops at the next option or the answer key.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# A question starts with a number (and optional period / parenthesis)
# at the start of a line, optionally followed by whitespace. We accept:
#   "1."   "1)"   "Q1"   "Q.1"   "Question 1"   "12."
QUESTION_START_RE = re.compile(
    r"(?:^|\n)\s*"
    r"(?:"                                                      # leading marker
    r"\d+[.)]"                                                   #   "1." or "1)"
    r"|Q\.?\s*\d+"                                               #   "Q1" or "Q.1"
    r"|Question\s+\d+"                                           #   "Question 1"
    r")"
    r"\s*",                                                      # space after
    re.IGNORECASE,
)

# Question-start detector for the NEWLINE-INSERTION preprocessor.
# This pattern matches `\d+\.` ANYWHERE in the text, not just at line
# starts, so we can find them on pages where the whole content is one
# line. The `(?:[A-Z]|[a-z])` lookahead requires a letter right after
# the period to reduce false positives (avoids matching decimal numbers).
QUESTION_START_INLINE_RE = re.compile(
    r"\d+[.)]\s*(?=[A-Za-z])"
)


def _insert_newlines_before_questions(text: str) -> str:
    """Insert a newline before each question-start pattern not already at
    the start of a line. Returns the text with newlines inserted.
    """
    out: list[str] = []
    last_end = 0
    for match in QUESTION_START_INLINE_RE.finditer(text):
        # Don't insert a newline if the match is already at the start of
        # a line (preceded only by whitespace from a newline).
        prefix = text[last_end:match.start()]
        out.append(text[last_end:match.start()])
        if not prefix.endswith("\n") and not prefix.rstrip().endswith("\n"):
            out.append("\n")
        out.append(match.group())
        last_end = match.end()
    out.append(text[last_end:])
    return "".join(out)

# Option body: `(a) text`  where text is a non-greedy run of non-paren
# chars, terminated by either the next option marker or the answer key.
# Use re.DOTALL so a single option may wrap across lines.
OPTION_RE = re.compile(
    r"\(([a-d])\)\s*"                                            # "(a)"
    r"([^()]+?)"                                                 # option body
    r"(?=\s*\([a-d]\)|\s*(?:Key|Answer)\s*:|$)",                 # terminator
    re.IGNORECASE | re.DOTALL,
)

# Answer key, e.g. "Key:b" or "Answer: a".
ANSWER_RE = re.compile(
    r"(?:Key|Answer)\s*:\s*([a-d])",
    re.IGNORECASE,
)

# Trailing sentence punctuation that often appears on the last option
# before the answer key (e.g. "...(d) yellow. Key:b"). We strip these
# from option values so they read as clean labels, but only when they
# sit at the end (not embedded numbers like "U.S.A.").
_TRAILING_PUNCT_RE = re.compile(r"[\s.,;:]+$")


def _clean_option_value(raw: str) -> str:
    """Strip whitespace and trailing sentence punctuation from an option body."""
    return _TRAILING_PUNCT_RE.sub("", raw.strip())


@dataclass
class ExtractedQuestion:
    qid: str
    type: str                                # "mcq" or "theory"
    question_text: str
    options: dict[str, str] = field(default_factory=dict)
    answer: Optional[str] = None
    module_chapter: Optional[str] = None
    page_num: int = 0
    extraction_method: str = "regex"
    marks: Optional[int] = None              # 5 or 10 for theory; None for MCQ
    section: Optional[str] = None            # "A", "B", "C", "D", etc.


def _extract_question_for_page(
    page: dict,
    page_text: str,
    match: re.Match,
    next_start: Optional[int],
    qid_counter: list[int],
) -> ExtractedQuestion:
    """Build one ExtractedQuestion from a single question-start match.

    `page_text` is the preprocessed text (newlines inserted before question
    starts). `page` is kept for the page_num field in the result. The match
    indices are valid in `page_text`, NOT in `page["text"]`.
    """
    start = match.start()

    if next_start is not None:
        raw = page_text[start:next_start]
    else:
        raw = page_text[start:]

    # Drop the question-number prefix from the text we hand to option /
    # answer scanners, so the scanners only see question body.
    head_end = match.end()
    body = raw[head_end - start :]

    options_pairs = OPTION_RE.findall(body)
    options = {letter: _clean_option_value(value) for letter, value in options_pairs}

    ans_match = ANSWER_RE.search(body)
    answer = ans_match.group(1).lower() if ans_match else None

    # Build the clean question_text: body up to the first option marker
    # or the answer key, whichever comes first.
    cut_positions = []
    first_option = re.search(r"\([a-d]\)", body, re.IGNORECASE)
    if first_option:
        cut_positions.append(first_option.start())
    if ans_match:
        cut_positions.append(ans_match.start())
    if cut_positions:
        question_text = body[: min(cut_positions)].strip()
    else:
        question_text = body.strip()

    qid_counter[0] += 1
    qid = f"q{qid_counter[0]:03d}"

    qtype = "mcq" if len(options) >= 2 else "theory"
    if qtype == "theory":
        # Theory questions carry no options / no answer by definition.
        options = {}
        answer = None

    return ExtractedQuestion(
        qid=qid,
        type=qtype,
        question_text=question_text,
        options=options,
        answer=answer,
        module_chapter=None,
        page_num=page["page_num"],
        extraction_method="regex",
    )


def extract_mcqs_from_pages(pages: list[dict]) -> list[ExtractedQuestion]:
    """Extract every question (MCQ or theory) from a list of cleaned pages.

    Each ``page`` is a dict with the Stage 2.2 shape:
        {"page_num": int, "method": str, "text": str, "char_count": int}

    Returns a list of :class:`ExtractedQuestion` in document order, with
    qids assigned sequentially ("q001", "q002", ...).
    """
    questions: list[ExtractedQuestion] = []
    qid_counter = [0]  # mutable single-element list — clean idiom for a counter

    for page in pages:
        text = page.get("text", "") or ""
        # Preprocess: insert newlines before question-start patterns that
        # are NOT already at line beginnings. This handles PDFs where the
        # entire page is one line (common with `pdftotext` output on
        # textbooks). After this pass, the question-start regex (which
        # anchors on `^` or `\n`) can find every question.
        text = _insert_newlines_before_questions(text)
        # Collect every question-start match on this page.
        starts = list(QUESTION_START_RE.finditer(text))
        if not starts:
            continue

        for i, match in enumerate(starts):
            next_start = starts[i + 1].start() if i + 1 < len(starts) else None
            questions.append(
                _extract_question_for_page(page, text, match, next_start, qid_counter)
            )

    return questions


def regex_extraction_coverage(pages: list[dict]) -> float:
    """Return the fraction of pages that contain at least one detected question.

    Used by the orchestrator to decide whether to fall back to LLM-based
    extraction (Stage 2.3 / M3): if this fraction is < 0.5, regex likely
    missed a lot of questions and LLM is worth invoking.

    Returns 0.0 when ``pages`` is empty.
    """
    if not pages:
        return 0.0
    hits = sum(
        1 for page in pages if QUESTION_START_RE.search(page.get("text", "") or "")
    )
    return hits / len(pages)


# Match a SECTION letter header (e.g. "SECTION A", "Section B – Long Answer").
# OCR-garbled text often has the section header concatenated with the
# previous line AND the next word (e.g. "...Key:a SECTION BModified..."),
# so we don't anchor on ^ or use \b after the letter — both would fail
# when the next char is a letter (word char).
_SECTION_HEADER_RE = re.compile(
    r"(?:^|\s)section\s*([A-Z])(?=\s|$|[^a-z])",
    re.IGNORECASE,
)

# Match a marks indicator (e.g. "10 Marks", "5 marks", "10marks",
# "1 0 marks"). The digits may have a space between them due to OCR
# (e.g. "1 0" instead of "10"). We capture each group of digits and
# concatenate them at match time.
_MARKS_RE = re.compile(
    r"\b(\d{1,2}(?:\s+\d{1,2})?)\s*marks?\b",
    re.IGNORECASE,
)


def _parse_marks(s: str) -> int | None:
    """Parse a marks string like '10', '1 0', '5' into an int.

    Returns None if the string has no digits.
    """
    digits = "".join(c for c in s if c.isdigit())
    return int(digits) if digits else None


def detect_section_marks(pages: list[dict]) -> list[dict]:
    """Walk the pages and return per-page {section, marks} context.

    The detector uses two regexes:

    - ``_SECTION_HEADER_RE`` finds "SECTION A", "Section B – Long Answer"
      etc. and updates the current section letter. OCR-garbled text
      concatenates section headers with surrounding text (e.g.
      "Key:a SECTION BModified..."), so we use a non-consuming
      approach: find all "section" positions, then look at the next
      non-space char.
    - ``_MARKS_RE`` finds "10 marks" / "5 marks" in the same line as the
      section header and updates the current marks value.

    The function is tolerant of OCR garbage and missing markers: if a
    page has no markers, the previously-seen section/marks is used.

    Args:
        pages: list of Stage 2.2 page dicts (page_num, text, ...).

    Returns:
        list of dicts, one per page, with keys:
            - ``page_num``: int
            - ``section``: str | None  (e.g. "A", "B", "C", "D")
            - ``marks``: int | None    (e.g. 5, 10)
    """
    out: list[dict] = []
    cur_section: str | None = None
    cur_marks: int | None = None
    for page in pages:
        text = page.get("text", "") or ""
        # Update section: find all "section" substrings and look at the
        # next non-space char for the section letter.
        for m in re.finditer(r"section", text, re.IGNORECASE):
            rest = text[m.end():].lstrip()
            if rest and rest[0].isalpha() and rest[0].isupper():
                cur_section = rest[0]
                # Don't break — continue looking for more section headers
                # in the same page (unusual but possible).
        # Update marks if a marks indicator is found anywhere in the page.
        # (Most modules list the marks next to the section header, but some
        # put it in the section description like "Long Answer — 10 marks".)
        marks_matches = _MARKS_RE.findall(text)
        if marks_matches:
            # Take the LAST marks value on the page (most specific to the
            # current section, since later paragraphs describe the current
            # section's questions). Each match may be "10" or "1 0" (OCR-
            # garbled) — _parse_marks concatenates the digits.
            for m in reversed(marks_matches):
                parsed = _parse_marks(m)
                if parsed:
                    cur_marks = parsed
                    break
        out.append({
            "page_num": page.get("page_num", 0),
            "section": cur_section,
            "marks": cur_marks,
        })
    return out


def annotate_questions_with_marks(
    questions: list[ExtractedQuestion],
    page_context: list[dict],
) -> list[ExtractedQuestion]:
    """Set each question's ``marks`` and ``section`` from the page context.

    The ``page_context`` is the output of :func:`detect_section_marks`. For
    each question, we look up the context for its ``page_num`` and copy
    the ``marks`` and ``section`` onto the question.

    MCQ questions (no options, or ``type == "mcq"``) get ``marks=None``
    even if the page context has marks — the marks apply only to theory
    questions on the same page.
    """
    ctx_by_page = {ctx["page_num"]: ctx for ctx in page_context}
    for q in questions:
        ctx = ctx_by_page.get(q.page_num)
        if ctx is None:
            continue
        q.section = ctx.get("section")
        if q.type == "mcq":
            q.marks = None
        else:
            q.marks = ctx.get("marks")
    return questions
