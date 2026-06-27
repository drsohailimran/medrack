"""Prompt templates for MCQ and Theory answer generation.

The MCQ and Theory templates are LOCKED — see preview-answer-brief.md,
sections "Prompt template — MCQ" and "Prompt template — Theory".
"""
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from medrack.config import MCQ_EXPLANATION_TARGET_WORDS, THEORY_LONG_TARGET_WORDS


MCQ_ANSWER_PROMPT = """You are an exam answer writer for an MBBS (or relevant field) theory paper.
The student is preparing for NEET PG and needs an MCQ-style answer with explanation.

QUESTION: {question}

OPTIONS:
{options_formatted}

SOURCE MATERIAL (use only what is relevant, ignore the rest):
---
{retrieved_chunks}
---

Write your response as:
1. ANSWER: <single letter a/b/c/d> — one line, the correct option
2. REASONING: <one sentence explaining why this option is correct>
3. EXPLANATION: <{explanation_target_words} word detailed explanation with high-yield facts, classifications, or tables>

Rules:
- The answer letter MUST be one of: {options_letters}
- Use precise medical terminology, not lay terms.
- Bold key terms on first use (use **asterisks** for markdown).
- Do NOT use markdown headings (#) — the renderer applies them.
- Do NOT begin with phrases like 'This is a question about...'. Start directly.
- If the source material contradicts your knowledge, prefer the source.

ANSWER:"""


THEORY_ANSWER_PROMPT = """You are an exam answer writer for an MBBS theory paper.
Write a structured, exam-ready answer of approximately {word_count_target} words (±20%).

FORMAT (use exactly these section headings in this order, each on its own line):
- Definition
- Etiology
- Pathogenesis
- Clinical features
- Investigations
- Treatment
(Add/remove sections only if a section is genuinely irrelevant to the question.)

STYLE RULES:
- Use precise medical terminology, not lay terms.
- Include a classification or table where it aids recall.
- Bold key terms on first use (use **asterisks** for markdown).
- No page numbers, no source citations in the body.
- Do NOT use markdown headings (#) — the renderer will apply them.
- Do NOT begin with phrases like 'This is a question about...'. Start directly with the answer.

SOURCE MATERIAL (use only what is relevant, ignore the rest):
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
