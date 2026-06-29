"""Prompt templates for MCQ and Theory answer generation.

The MCQ and Theory templates are LOCKED — see preview-answer-brief.md,
sections "Prompt template — MCQ" and "Prompt template — Theory".

Subject-awareness (Phase 2, directive v1.0):
  Both templates use ``{display}`` and ``{reference_text}`` placeholders
  that are filled from ``medrack.config.SUBJECT_CONTEXTS`` at build time.
  ``build_mcq_prompt`` and ``build_theory_prompt`` accept a ``subject``
  parameter; if the subject is not in the dict, the prompt builder falls
  back to the ``generic`` entry (and emits a debug-level log). This
  keeps the per-subject data out of the template strings — adding a new
  subject means adding a row to ``SUBJECT_CONTEXTS``, not editing this
  file.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import tiktoken

from medrack.config import (
    MCQ_EXPLANATION_TARGET_WORDS,
    SUBJECT_CONTEXTS,
    THEORY_LONG_TARGET_WORDS,
)


logger = logging.getLogger(__name__)


def _get_subject_context(subject: str) -> dict[str, str]:
    """Resolve a subject key to its context dict.

    Unknown subjects fall back to the ``generic`` entry (which has
    a ``fallback: true`` flag). A debug log is emitted so the operator
    can see when this happens — they should add a proper entry to
    ``SUBJECT_CONTEXTS`` for any subject they ingest regularly.
    """
    ctx = SUBJECT_CONTEXTS.get(subject)
    if ctx is not None:
        return ctx
    logger.debug(
        "Subject %r has no entry in SUBJECT_CONTEXTS; using 'generic' fallback. "
        "Add an entry to medrack.config.SUBJECT_CONTEXTS for this subject.",
        subject,
    )
    return SUBJECT_CONTEXTS["generic"]


MCQ_ANSWER_PROMPT = """You are an MBBS ({display}) MCQ answer writer for NEET PG and university exams. Reference: {reference_text}.

QUESTION: {question}

OPTIONS:
{options_formatted}

SOURCE MATERIAL (use only what's relevant):
---
{retrieved_chunks}
---

RESPOND IN THIS EXACT FORMAT:
1. ANSWER: <single letter a/b/c/d>
2. REASONING: <one sentence stating why this option is correct>
3. EXPLANATION: <{explanation_target_words} words in point form, • bullets, sub-bullets –, **bold** key terms>

RULES:
- Point form only. NO paragraphs.
- The answer letter MUST be one of: {options_letters}
- Bold key terms with **asterisks** on first use.
- Do NOT cite sources in parens. This is exam prep, not a literature review.
- Indian context where relevant: {indian_context}.
- Key authoritative sources (use without parenthetical citation): {key_sources}.
- Analytical framework: {framework}.
- End your answer with a final bullet summarizing the key takeaway (no extra footer text).

ANSWER:"""


THEORY_ANSWER_PROMPT = """You are an MBBS ({display}) theory answer writer for NEET PG and university exams. Reference: {reference_text}.

Write ~{word_count_target} words (±10%) in point form. This is the length expected for a {marks}-mark exam answer — long enough to cover all key points, short enough to be written by hand in the exam time allotted.

FORMAT (point form only — NO paragraphs):
- Use "•" bullets (~10-25 words each, one idea per bullet).
- Use "–" sub-bullets for detail (max 2 levels).
- Bold key terms with **asterisks** on first use.
- Do NOT cite sources in parens (no "(WHO)", "(Park 27e)", "(ICMR)" etc.). This is exam prep — write the answer as if you were a student writing in an exam booklet. Just state the facts.

SECTION HEADINGS (adapt to the question; use what fits):
• Definition
• Uses / Importance / Justification
• Classification (or Components / Types)
• Specific explanations or sub-points
• Indian context (key programmes, data, legislation)
• Conclusion

For 5-mark questions: keep it tight — Definition + 3-5 key bullets + Indian context.
For 10-mark questions: include Definition + 2-3 sections with multiple bullets each + Indian context + Conclusion.

STYLE:
- "X is ..." for definitions (no source citation).
- Use **bold** category names in classifications, then enumerate.
- For statistics: cite the year and source naturally ("IMR is 28/1000 live births (SRS 2020)").
- Address parts (a, b, c) of a question in clear sub-sections.
- Subject-specific framework: {framework}.
- Indian context: {indian_context}.
- Key authoritative sources (use without parenthetical citation): {key_sources}.
- Start directly with the first bullet. No preamble.
- End your answer with a final bullet summarizing the key takeaway (no extra footer text).

SOURCE MATERIAL (use only what's relevant):
---
{retrieved_chunks}
---

QUESTION: {question}

ANSWER:"""


@dataclass
class BuildResult:
    """The result of building a prompt.

    Attributes:
        prompt: The fully formatted prompt string.
        prompt_tokens_estimate: Rough token count estimate (tiktoken cl100k_base).
        system_template: Which template was used — "mcq" or "theory".
        subject: The subject the prompt was built for (after fallback resolution).
    """
    prompt: str
    prompt_tokens_estimate: int
    system_template: str
    subject: str


def format_options_for_prompt(options: dict[str, str]) -> str:
    """Format options as 'a) text\\nb) text\\n...'. Keys are sorted alphabetically.

    Args:
        options: Mapping of option letter to option text.

    Returns:
        Newline-joined string of "key) value" lines, keys sorted.
    """
    return "\n".join(f"{k}) {options[k]}" for k in sorted(options.keys()))


def estimate_tokens(text: str) -> int:
    """Estimate token count for the given text using tiktoken (cl100k_base).

    If tiktoken is unavailable, falls back to a rough heuristic of
    `len(text) // 4` (≈4 characters per token).

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated integer token count.
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback heuristic if tiktoken cannot be loaded (e.g. missing model).
        return len(text) // 4


def _build_chunks_text(retrieved_chunks: list[str]) -> str:
    """Join retrieved chunk strings with the locked separator."""
    return "\n\n---\n\n".join(retrieved_chunks)


def _format_mcq_prompt(
    question_text: str,
    options: dict[str, str],
    retrieved_chunks_text: str,
    options_letters: str,
    explanation_target_words: int,
    subject_ctx: dict[str, str],
) -> str:
    return MCQ_ANSWER_PROMPT.format(
        display=subject_ctx["display"],
        reference_text=subject_ctx["reference_text"],
        question=question_text,
        options_formatted=format_options_for_prompt(options),
        retrieved_chunks=retrieved_chunks_text,
        explanation_target_words=explanation_target_words,
        options_letters=options_letters,
        indian_context=subject_ctx["indian_context"],
        key_sources=subject_ctx["key_sources"],
        framework=subject_ctx["framework"],
    )


def _format_theory_prompt(
    question_text: str,
    retrieved_chunks_text: str,
    marks: int,
    word_count_target: int,
    subject_ctx: dict[str, str],
) -> str:
    return THEORY_ANSWER_PROMPT.format(
        display=subject_ctx["display"],
        reference_text=subject_ctx["reference_text"],
        word_count_target=word_count_target,
        retrieved_chunks=retrieved_chunks_text,
        question=question_text,
        marks=marks,
        indian_context=subject_ctx["indian_context"],
        key_sources=subject_ctx["key_sources"],
        framework=subject_ctx["framework"],
    )


def build_mcq_prompt(
    question_text: str,
    options: dict[str, str],
    retrieved_chunks: list[str],
    explanation_target_words: int = MCQ_EXPLANATION_TARGET_WORDS,
    subject: str = "psm",
) -> BuildResult:
    """Build the MCQ answer prompt.

    Args:
        question_text: The full MCQ question text.
        options: Mapping of option letter ("a", "b", ...) to option text.
        retrieved_chunks: List of chunk text strings retrieved from the KB.
        explanation_target_words: Target word count for the explanation section.
            Defaults to ``medrack.config.MCQ_EXPLANATION_TARGET_WORDS``.
        subject: Subject key for subject-aware prompt context. Defaults to
            ``"psm"`` for backward compatibility with existing callers.
            Unknown subjects fall back to the ``generic`` entry in
            ``medrack.config.SUBJECT_CONTEXTS``.

    Returns:
        BuildResult with the formatted prompt, token estimate,
        system_template="mcq", and resolved subject key.
    """
    subject_ctx = _get_subject_context(subject)
    options_letters = ", ".join(sorted(options.keys()))
    retrieved_chunks_text = _build_chunks_text(retrieved_chunks)

    prompt = _format_mcq_prompt(
        question_text=question_text,
        options=options,
        retrieved_chunks_text=retrieved_chunks_text,
        options_letters=options_letters,
        explanation_target_words=explanation_target_words,
        subject_ctx=subject_ctx,
    )
    return BuildResult(
        prompt=prompt,
        prompt_tokens_estimate=estimate_tokens(prompt),
        system_template="mcq",
        subject=subject,
    )


def build_theory_prompt(
    question_text: str,
    retrieved_chunks: list[str],
    marks: int = 10,
    word_count_target: int | None = None,
    subject: str = "psm",
) -> BuildResult:
    """Build the Theory answer prompt.

    Args:
        question_text: The full theory question text.
        retrieved_chunks: List of chunk text strings retrieved from the KB.
        marks: Target marks value (5 or 10). If 5, uses
            ``medrack.config.THEORY_SHORT_TARGET_WORDS``. If 10 (or
            anything else), uses ``THEORY_LONG_TARGET_WORDS``.
        word_count_target: Override the target word count. If None, it is
            derived from ``marks``.
        subject: Subject key for subject-aware prompt context. Defaults to
            ``"psm"`` for backward compatibility with existing callers.
            Unknown subjects fall back to the ``generic`` entry in
            ``medrack.config.SUBJECT_CONTEXTS``.

    Returns:
        BuildResult with the formatted prompt, token estimate,
        system_template="theory", and resolved subject key.
    """
    subject_ctx = _get_subject_context(subject)
    retrieved_chunks_text = _build_chunks_text(retrieved_chunks)

    # Determine the target word count from the marks value. If
    # word_count_target is explicitly provided, use it; otherwise pick
    # based on the marks (5 → SHORT, 10 → LONG).
    if word_count_target is None:
        if marks == 5:
            from medrack import config as _cfg
            word_count_target = _cfg.THEORY_SHORT_TARGET_WORDS
        else:
            word_count_target = THEORY_LONG_TARGET_WORDS

    prompt = _format_theory_prompt(
        question_text=question_text,
        retrieved_chunks_text=retrieved_chunks_text,
        marks=marks,
        word_count_target=word_count_target,
        subject_ctx=subject_ctx,
    )
    return BuildResult(
        prompt=prompt,
        prompt_tokens_estimate=estimate_tokens(prompt),
        system_template="theory",
        subject=subject,
    )
