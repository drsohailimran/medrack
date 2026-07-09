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
- SCOPE: explain only what is needed to justify the correct option — do not dump unrelated programmes.
- HARD GROUNDING: Do NOT invent scheme names or statistics. Name a scheme/law/stat only if it appears in SOURCE MATERIAL or is a universal textbook fact. Never use non-Indian programmes (e.g. US PRAMS) for Indian exams. If unsure, state the general principle.
- The answer letter MUST be one of: {options_letters}
- Bold key terms with **asterisks** on first use.
- Do NOT cite sources in parens. This is exam prep, not a literature review.
- Indian context where relevant: {indian_context}.
- Key authoritative sources (use without parenthetical citation): {key_sources}.
- Analytical framework: {framework}.
- End your answer with a final bullet summarizing the key takeaway (no extra footer text).

ANSWER:"""


THEORY_ANSWER_PROMPT = """You are an MBBS ({display}) theory answer writer for NEET PG and university exams. Reference: {reference_text}.

Write a {marks}-mark exam answer in point form (headings + bullets).

## LENGTH BAND (mandatory — non-negotiable)
- TARGET: **{word_count_target} words** (count only your answer text, not tables/DOT diagrams).
- HARD MINIMUM: **{lower_words} words**. Do NOT stop early. If you are under {lower_words}, add more on-topic bullets under the existing headings (detail, Indian context, examples from SOURCE MATERIAL) — never invent schemes to pad.
- HARD MAXIMUM: **{upper_words} words**. This is a hard stop — stop body content before the ceiling and write Conclusion. Never aim past the maximum to "be thorough."
- Prefer the middle of the band ({word_count_target} ± 10%). Hitting only ~50% of a 10-mark target is FAILED. Exceeding {upper_words} is also FAILED (for both 5-mark and 10-mark).
- Do NOT fill space with endless bullets. Depth means better bullets on the asked topic, not more unrelated programmes.
- A table or flowchart is EXTRA and does NOT count toward the word target; it must not replace the written explanation.

## SCOPE CONTROL (mandatory — quality over completeness)
- Answer ONLY what the question asks. Do not expand into a full chapter, full RMNCH laundry list, or related programmes unless the question explicitly asks for them.
- If the question is narrow (e.g. "objectives of ANC", "definition of …", "components of …"), stay inside that narrow ask. Do NOT add unrelated schemes, levels of care, or entire programme reviews.
- Do NOT invent or pad with programmes that are only loosely related to the stem.
- Mark structure rules (still obey the LENGTH BAND above):
  - 3-mark: VERY short structure — 3-5 crisp bullets, no long intro, no separate Conclusion unless needed. ~{word_count_target} words total.
  - 5-mark: **STRICT COMPACT** — this is NOT a 10-mark essay.
    - At most **2–3 short headings** total + optional **one-line** Conclusion.
    - Prefer **6–10 bullets total** (not 20+). Sub-bullets only when essential.
    - No "Challenges", "Future Directions", "National Programmes", "Indian Context and Data", or "Strategic Interventions for Newborn Survival" sections unless the stem asks for them.
    - No digression into labour/newborn/EmOC stats unless the stem is about those topics.
    - For list stems ("objectives", "elements", "components"): enumerate the list; do NOT add a second half-chapter of programmes/data.
    - Hard stop: do not exceed **{upper_words} words**. Prefer finishing at ~{word_count_target} words.
  - 10-mark: **full depth within the band** — **4–6 headings**, several bullets each, Indian context when relevant, ending in Conclusion. Multi-part stems (a/b/c) need a balanced section per part. ~{word_count_target} words total — do not write a 5-mark answer for a 10-mark stem.
    - Even open stems ("services under RCH-II", "discuss …") must stop by **{upper_words}**. Cap at **~15–25 bullets total**, not 50–100.
    - Cover the asked concept thoroughly; do **not** append a laundry list of every NHM/newborn/HIV/WASH/FP programme unless the stem asks for those topics.
    - Prefer 2–4 named schemes that appear in SOURCE MATERIAL over a long catalogue.
    - When you have covered definition + key services/components + brief Indian context + conclusion, **STOP**.

## HARD GROUNDING (mandatory — no fabrication)
- Name a specific scheme, programme, law, act, guideline, or statistic ONLY if it appears in the SOURCE MATERIAL below, OR it is a universally standard textbook fact (e.g. WHO definition of health, basic epidemiological triad).
- If a name is not supported by SOURCE MATERIAL and is not a universal standard fact, describe generically ("a national maternity benefit scheme") — never invent a name or acronym.
- NEVER use non-Indian programmes (e.g. US PRAMS, Medicaid, Medicare) for Indian MBBS answers.
- Never invent numbers. If unsure of a figure, describe the trend qualitatively.
- Prefer SOURCE MATERIAL over memory when they conflict.

FORMAT (point form — NO long paragraphs):
- Use "•" bullets (~10-25 words each, one idea per bullet).
- Use "–" sub-bullets for detail (max 2 levels).
- Bold key terms with **asterisks** on first use.
- TABLES: If the question asks to "tabulate", "compare", "differentiate", "distinguish", or for "differences between" / "X vs Y", you MUST present that comparison as a Markdown table — NOT as bullets. Also use a table for any classification or set of parallel items that share the same attributes. Table format: a header row, then a separator row of dashes ("| --- | --- |"), then one data row per item; keep it to 2-4 columns. Use bullets only for content that is not naturally tabular.
- FLOWCHARTS: For a process, pathway, cycle, or sequence of steps that a diagram makes clearer (e.g. chain of infection, epidemiological triad, natural history of disease, a parasite life cycle, a referral pathway, a management algorithm), include ONE small flowchart as a Graphviz DOT block, fenced exactly like this:
```dot
digraph {{ rankdir=LR; node [shape=box, style=rounded]; "Agent" -> "Reservoir" -> "Host"; }}
```
  Keep it to a handful of nodes with SHORT labels; use "rankdir=LR" for a linear flow or a cycle. Add a flowchart only when it genuinely helps — otherwise use bullets/tables. Still write the accompanying explanation as bullets.
- Do NOT cite sources in parens (no "(WHO)", "(Park 27e)", "(ICMR)" etc.). This is exam prep — write the answer as if you were a student writing in an exam booklet. Just state the facts.

STRUCTURE — this is important: organise the answer under SHORT SECTION HEADINGS. Do NOT write one long flat list of bullets.
- Put each section heading on ITS OWN LINE, in Title Case, with NO bullet marker and NO trailing colon (e.g. a line reading exactly: Definition ... or: Conclusion).
- Under each heading, give the relevant "•" bullet points.
- {answer_structure}

STYLE:
- "X is ..." for definitions (no source citation).
- Use **bold** category names in classifications, then enumerate.
- Address parts (a, b, c) of a question in clear sub-sections.
- Subject-specific framework: {framework}.
- Indian context (only if relevant to the stem): {indian_context}.
- Key authoritative sources (use without parenthetical citation): {key_sources}.
- Start directly with the first section or bullet. No preamble.
- End your answer with a final bullet summarizing the key takeaway (no extra footer text).

SOURCE MATERIAL (use only what's relevant; this is your grounding evidence):
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
        word_count_target: The word count target the LLM was instructed to
            hit (``int`` for theory questions — 475 or 775; ``None`` for
            MCQ questions). Phase 3: recorded on the cached answer for
            staleness detection.
    """
    prompt: str
    prompt_tokens_estimate: int
    system_template: str
    subject: str
    word_count_target: int | None = None


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
        lower_words=int(word_count_target * 0.9),
        upper_words=int(word_count_target * 1.1),
        retrieved_chunks=retrieved_chunks_text,
        question=question_text,
        marks=marks,
        indian_context=subject_ctx["indian_context"],
        key_sources=subject_ctx["key_sources"],
        framework=subject_ctx["framework"],
        answer_structure=(
            subject_ctx.get("answer_structure")
            or SUBJECT_CONTEXTS["generic"]["answer_structure"]
        ),
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
        word_count_target=explanation_target_words,
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
        from medrack import config as _cfg
        if marks == 3:
            word_count_target = _cfg.THEORY_VSHORT_TARGET_WORDS
        elif marks == 5:
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
        word_count_target=word_count_target,
    )
