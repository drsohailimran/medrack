"""Module format detector: MCQ vs theory, by pattern density on the first 5 pages."""

from __future__ import annotations

import re
from typing import TypedDict


class Page(TypedDict, total=False):
    """Minimal page shape used by format detection."""
    page_num: int
    method: str
    text: str
    char_count: int


# MCQ signal patterns. We compile once at import time.
_MCQ_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\(a\)"),
    re.compile(r"\(b\)"),
    re.compile(r"\(c\)"),
    re.compile(r"\(d\)"),
    re.compile(r"\bKey:"),
    # Question start: "1.", "25.", etc. (line-anchored)
    re.compile(r"^\s*\d+\.", re.MULTILINE),
)


# Theory signal patterns. Case-insensitive verbs / essay-style headers.
_THEORY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bDiscuss\b", re.IGNORECASE),
    re.compile(r"\bDescribe\b", re.IGNORECASE),
    re.compile(r"\bExplain\b", re.IGNORECASE),
    re.compile(r"\bWrite\s+about\b", re.IGNORECASE),
    re.compile(r"\bElaborate\b", re.IGNORECASE),
    re.compile(r"\bWrite\s+short\s+notes\b", re.IGNORECASE),
)


# How many leading pages to scan for a format signal.
_SCAN_PAGE_LIMIT = 5


def _count_patterns(text: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    """Return the total number of matches for all patterns in `text`."""
    return sum(len(p.findall(text)) for p in patterns)


def detect_module_format(pages: list[Page]) -> str:
    """Return "mcq" or "theory" based on pattern density in the first 5 pages.

    Heuristic:
    - For each of the first 5 pages, count MCQ signals: `(a)`, `(b)`, `(c)`,
      `(d)`, `Key:`, or a line-anchored `^\\d+\\.` question start.
    - For each of the first 5 pages, count theory signals: `Discuss`,
      `Describe`, `Explain`, `Write about`, `Elaborate`, `Write short notes`
      (case-insensitive).
    - If MCQ count > 5x theory count -> "mcq"
    - If theory count > 5x MCQ count -> "theory"
    - Else -> "mcq" (default; most MBBS modules are MCQ)

    If `pages` is empty, return "mcq" (default).
    """
    if not pages:
        return "mcq"

    sample = pages[:_SCAN_PAGE_LIMIT]

    mcq_count = 0
    theory_count = 0
    for page in sample:
        text = page.get("text", "") or ""
        mcq_count += _count_patterns(text, _MCQ_PATTERNS)
        theory_count += _count_patterns(text, _THEORY_PATTERNS)

    if mcq_count > 5 * theory_count:
        return "mcq"
    if theory_count > 5 * mcq_count:
        return "theory"
    return "mcq"


def is_mcq_module(pages: list[Page]) -> bool:
    """Convenience: True iff `detect_module_format(pages) == "mcq"`."""
    return detect_module_format(pages) == "mcq"
