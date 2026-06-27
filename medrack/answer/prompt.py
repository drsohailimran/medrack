"""Prompt templates for MCQ and Theory answer generation.

The MCQ and Theory templates are LOCKED — see preview-answer-brief.md,
sections "Prompt template — MCQ" and "Prompt template — Theory".
"""
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from medrack.config import MCQ_EXPLANATION_TARGET_WORDS, THEORY_LONG_TARGET_WORDS


MCQ_ANSWER_PROMPT = """You are an MBBS (PSM/Community Medicine) MCQ answer writer for NEET PG and university exams. Reference: K. Park's "Preventive & Social Medicine" 27th edition.

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
- Indian context where relevant: national programmes, NFHS data, SRS, IMR/MMR.
- End with: "Exam-prep study notes — write in your own hand. Verify current Indian data against your edition."

ANSWER:"""


THEORY_ANSWER_PROMPT = """You are an MBBS (PSM/Community Medicine) theory answer writer for NEET PG and university exams. Reference: K. Park's "Preventive & Social Medicine" 27th edition.

Write ~{word_count_target} words (±25%) in point form. This is the length expected for a {marks}-mark exam answer — long enough to cover all key points, short enough to be written by hand in the exam time allotted.

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
• Indian context (national programmes, NFHS data, IMR/MMR)
• Conclusion

For 5-mark questions: keep it tight — Definition + 3-5 key bullets + Indian context.
For 10-mark questions: include Definition + 2-3 sections with multiple bullets each + Indian context + Conclusion.

STYLE:
- "X is ..." for definitions (no source citation).
- Use **bold** category names in classifications, then enumerate.
- For statistics: cite the year and source naturally ("IMR is 28/1000 live births (SRS 2020)").
- Address parts (a, b, c) of a question in clear sub-sections.
- Mention primary/secondary/tertiary prevention (Park's framework) where relevant.
- Indian context: use Indian data and programmes (NHM, NVBDCP, RNTCP, Ayushman Bharat, NFHS, SRS, IMR, MMR, U5MR, TFR).
- Start directly with the first bullet. No preamble.

SOURCE MATERIAL (use only what's relevant):
---
{retrieved_chunks}
---

QUESTION: {question}

End with: "Exam-prep study notes — write in your own hand. Verify current Indian data against your edition."

ANSWER:"""


@dataclass
class BuildResult:
    """The result of building a prompt.
    
    Attributes:
        prompt: The fully formatted prompt string.
        prompt_tokens_estimate: Rough token count estimate (tiktoken cl100k_base).
        system_template: Which template was used — "mcq" or "theory".
    """
    prompt: str
    prompt_tokens_estimate: int
    system_template: str


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


def build_mcq_prompt(
    question_text: str,
    options: dict[str, str],
    retrieved_chunks: list[str],
    explanation_target_words: int = MCQ_EXPLANATION_TARGET_WORDS,
) -> BuildResult:
    """Build the MCQ answer prompt.
    
    Args:
        question_text: The full MCQ question text.
        options: Mapping of option letter ("a", "b", ...) to option text.
        retrieved_chunks: List of chunk text strings retrieved from the KB.
        explanation_target_words: Target word count for the explanation section.
            Defaults to `medrack.config.MCQ_EXPLANATION_TARGET_WORDS` (300).
    
    Returns:
        BuildResult with the formatted prompt, token estimate, and
        system_template="mcq".
    """
    options_formatted = format_options_for_prompt(options)
    options_letters = ", ".join(sorted(options.keys()))
    retrieved_chunks_text = _build_chunks_text(retrieved_chunks)

    prompt = MCQ_ANSWER_PROMPT.format(
        question=question_text,
        options_formatted=options_formatted,
        retrieved_chunks=retrieved_chunks_text,
        explanation_target_words=explanation_target_words,
        options_letters=options_letters,
    )
    return BuildResult(
        prompt=prompt,
        prompt_tokens_estimate=estimate_tokens(prompt),
        system_template="mcq",
    )


def build_theory_prompt(
    question_text: str,
    retrieved_chunks: list[str],
    marks: int = 10,
    word_count_target: int | None = None,
) -> BuildResult:
    """Build the Theory answer prompt.

    Args:
        question_text: The full theory question text.
        retrieved_chunks: List of chunk text strings retrieved from the KB.
        marks: Target marks value (5 or 10). If 5, uses
            ``medrack.config.THEORY_SHORT_TARGET_WORDS`` (900). If 10 (or
            anything else), uses ``THEORY_LONG_TARGET_WORDS`` (1500).
        word_count_target: Override the target word count. If None, it is
            derived from ``marks``.
    
    Returns:
        BuildResult with the formatted prompt, token estimate, and
        system_template="theory".
    """
    retrieved_chunks_text = _build_chunks_text(retrieved_chunks)

    # Determine the target word count from the marks value. If
    # word_count_target is explicitly provided, use it; otherwise pick
    # based on the marks (5 → 900 words, 10 → 1500 words).
    if word_count_target is None:
        if marks == 5:
            from medrack import config as _cfg
            word_count_target = _cfg.THEORY_SHORT_TARGET_WORDS
        else:
            word_count_target = THEORY_LONG_TARGET_WORDS

    prompt = THEORY_ANSWER_PROMPT.format(
        word_count_target=word_count_target,
        retrieved_chunks=retrieved_chunks_text,
        question=question_text,
        marks=marks,
    )
    return BuildResult(
        prompt=prompt,
        prompt_tokens_estimate=estimate_tokens(prompt),
        system_template="theory",
    )
