"""Prompt templates for MCQ and Theory answer generation.

The MCQ and Theory templates are LOCKED — see preview-answer-brief.md,
sections "Prompt template — MCQ" and "Prompt template — Theory".
"""
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from medrack.config import MCQ_EXPLANATION_TARGET_WORDS, THEORY_LONG_TARGET_WORDS


MCQ_ANSWER_PROMPT = """You are an MBBS (PSM/Community Medicine) MCQ answer writer for NEET PG, university exams, and PSM viva. Reference: K. Park's "Preventive & Social Medicine" 27th edition.

QUESTION: {question}

OPTIONS:
{options_formatted}

SOURCE MATERIAL (use only what's relevant):
---
{retrieved_chunks}
---

RESPOND IN THIS EXACT FORMAT:
1. ANSWER: <single letter a/b/c/d>
2. REASONING: <one sentence citing the source (WHO, Park 27e, ICMR, etc.)>
3. EXPLANATION: <{explanation_target_words} words in point form, • bullets, sub-bullets –, **bold** key terms, cite sources>

RULES:
- Point form only. NO paragraphs.
- The answer letter MUST be one of: {options_letters}
- Bold key terms with **asterisks** on first use.
- Cite sources in parens: (WHO), (Park 27e), (ICMR), (NFHS-5), (SRS 2020), (Ottawa Charter), (Alma-Ata).
- Indian context where relevant: national programmes, ICMR, NFHS data, SRS, IMR/MMR.
- End with: "Exam-prep study notes — write in your own hand. Verify current Indian data against your edition."

ANSWER:"""


THEORY_ANSWER_PROMPT = """You are an MBBS (PSM/Community Medicine) theory answer writer for NEET PG, university exams, and PSM viva. Reference: K. Park's "Preventive & Social Medicine" 27th edition.

Write ~{word_count_target} words (±20%) in point form.

FORMAT (point form only — NO paragraphs):
- Use "•" bullets (~10-25 words each, one idea per bullet).
- Use "–" sub-bullets for detail (max 2 levels).
- Bold key terms with **asterisks** on first use.
- Cite sources in parens: (WHO), (Park 27e), (ICMR), (NFHS-5), (SRS 2020), (Ottawa Charter), (Alma-Ata).

SECTION HEADINGS (adapt to the question; use what fits):
• Definition
• Uses / Importance / Justification
• Classification (or Components / Types)
• Specific explanations or sub-points
• Indian context (national programmes, ICMR, NFHS data)
• Conclusion

For short-answer (5-mark) questions: just Definition + 3-5 key bullets + Indian context.

STYLE:
- "X (source) is ..." for definitions.
- Use **bold** category names in classifications, then enumerate.
- For statistics: cite year and source ("IMR 28/1000 (SRS 2020)").
- Address parts (a, b, c) of a question in clear sub-sections.
- Mention primary/secondary/tertiary prevention (Park's framework) where relevant.
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
    word_count_target: int = THEORY_LONG_TARGET_WORDS,
) -> BuildResult:
    """Build the Theory answer prompt.
    
    Args:
        question_text: The full theory question text.
        retrieved_chunks: List of chunk text strings retrieved from the KB.
        word_count_target: Target word count for the answer. Defaults to
            `medrack.config.THEORY_LONG_TARGET_WORDS` (1500).
    
    Returns:
        BuildResult with the formatted prompt, token estimate, and
        system_template="theory".
    """
    retrieved_chunks_text = _build_chunks_text(retrieved_chunks)

    prompt = THEORY_ANSWER_PROMPT.format(
        word_count_target=word_count_target,
        retrieved_chunks=retrieved_chunks_text,
        question=question_text,
    )
    return BuildResult(
        prompt=prompt,
        prompt_tokens_estimate=estimate_tokens(prompt),
        system_template="theory",
    )
