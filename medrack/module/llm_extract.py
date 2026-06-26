"""LLM-fallback question extractor for MedRack module ingest.

Stage 2.3 / Task M3 of the MedRack module ingest pipeline.

Public API:
    extract_questions_with_llm — when the regex extractor (M2) has poor
                                  coverage, ask an LLM to extract
                                  structured MCQ questions from a sample
                                  of the module's cleaned page text.

Design notes:
    * The LLM client is injectable (default ``None``). Stage 2.4 will wire
      a real client; tests pass a ``unittest.mock.MagicMock`` whose
      ``complete(prompt) -> str`` method returns a JSON string.
    * When no client is supplied we raise ``NotImplementedError`` with a
      clear "wire Stage 2.4" message — better to fail loudly during dev
      than silently fall through with empty results.
    * The prompt asks for a JSON array of question dicts; we only feed
      the LLM the first 10 pages, capped at 4000 characters total, to
      keep the prompt well within typical context windows.
    * Any failure — exception from the client, malformed JSON — is
      swallowed and ``[]`` is returned. The caller (M2's coverage gate
      or M6's orchestrator) is then expected to fall back to whatever
      the regex extractor managed to produce.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Cap how much text we hand to the LLM in one call. Keeps the prompt
# small enough for any model and matches the brief's spec.
_MAX_PAGES = 10
_MAX_CHARS = 4000


def _build_prompt(subject: str, pages_text: list[str]) -> str:
    """Assemble the LLM prompt: subject + truncated page context.

    The first ``_MAX_PAGES`` pages are joined; if the joined text would
    exceed ``_MAX_CHARS`` characters, it is sliced at that boundary.
    """
    truncated_pages = list(pages_text[:_MAX_PAGES])
    body = "\n\n".join(truncated_pages)
    if len(body) > _MAX_CHARS:
        # Slice at the cap, then strip any trailing partial separator
        # (e.g. a lone "\n" from the "\n\n" join) so the body fits
        # within _MAX_CHARS *strictly* when the join would otherwise
        # have pushed it one byte over.
        body = body[:_MAX_CHARS].rstrip()
    return (
        f"Subject: {subject}\n\n"
        "You are extracting MCQ exam questions from a medical textbook "
        "module. Read the page text below and return a JSON array of "
        "question objects. Each object must have these keys:\n"
        '  "question_text": the full question text,\n'
        '  "options": an object mapping "a"/"b"/"c"/"d" to option text '
        "(omit keys for options that are absent),\n"
        '  "answer": the correct option letter (e.g. "a") or null if '
        "no answer key is visible,\n"
        '  "page_num": 1-indexed page number where the question appears.\n'
        "Return ONLY the JSON array, no prose, no markdown fences.\n\n"
        f"--- BEGIN PAGES ---\n{body}\n--- END PAGES ---"
    )


def _parse_response(response: str) -> list[dict[str, Any]]:
    """Parse the LLM's response string into a list of question dicts.

    Robust to a couple of common model slips: a markdown-fenced code
    block surrounding the JSON, or leading/trailing prose.
    """
    text = response.strip()
    # Strip ```json ... ``` fences if the model added them.
    if text.startswith("```"):
        # Drop the opening fence line (e.g. "```json" or "```")
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        # Drop a trailing ``` if present
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("LLM response is not a JSON array")
    return parsed


def extract_questions_with_llm(
    pages_text: list[str],
    subject: str,
    llm_client: object = None,
) -> list[dict]:
    """Use the LLM to extract structured questions from page text.

    Args:
        pages_text: list of cleaned page texts (the first 10 are used).
        subject:    subject slug (e.g. "psm", "fmt") — included in the
                    prompt for context.
        llm_client: object exposing ``complete(prompt: str) -> str``.
                    Required; defaults to ``None`` and raises
                    ``NotImplementedError`` to surface the missing
                    Stage 2.4 wiring during development.

    Returns:
        A list of question dicts with keys ``question_text``,
        ``options``, ``answer``, ``page_num``. Returns ``[]`` on any
        failure (LLM exception, malformed JSON, wrong shape) so the
        caller can degrade gracefully back to the regex extractor.
    """
    if llm_client is None:
        raise NotImplementedError(
            "extract_questions_with_llm() requires an llm_client; "
            "the default real client is not yet wired (Stage 2.4)."
        )

    prompt = _build_prompt(subject, pages_text)

    try:
        response = llm_client.complete(prompt)
        return _parse_response(response)
    except Exception as exc:  # noqa: BLE001 — graceful degradation is the contract
        logger.warning(
            "LLM question extraction failed for subject=%r: %s; returning []",
            subject,
            exc,
        )
        return []
