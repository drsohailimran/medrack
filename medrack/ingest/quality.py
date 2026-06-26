"""OCR quality gate — flag suspect pages in an OCR'd (or mixed) page stream.

Pure analysis. No I/O, no LLM. Operates on the page dicts produced by
``medrack.ingest.text_extract`` and ``medrack.ingest.ocr`` (each page has
``page_num``, ``method``, ``text``, ``char_count``).

A page is considered "suspect" (likely failed OCR) if any of:
  - char_count is below ``min_chars`` (likely blank or near-blank)
  - ratio of non-alphanumeric characters exceeds ``max_non_alnum_ratio``
    (lots of punctuation/symbols ⇒ garble)
  - ratio of single-character "words" exceeds 0.4 (Tesseract failed to
    group letters into words, a common failure mode)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from medrack.config import OCR_MIN_CHARS_PER_PAGE

# Type alias mirrors medrack.ingest.text_extract.Page (kept as a dict there
# for json-friendliness). Using a local alias keeps the signature readable
# without forcing an import cycle.
Page = dict


@dataclass
class QualityReport:
    total_pages: int
    suspect_pages: list[int]          # 1-indexed page numbers
    low_char_pages: list[int]         # char_count < min_chars
    high_garble_pages: list[int]      # non_alnum_ratio > max_non_alnum_ratio
    avg_chars_per_page: float


def _non_alnum_ratio(text: str, char_count: int) -> float:
    """Fraction of chars that are not alphanumeric per str.isalnum().

    Empty text → 0.0 (we special-case to avoid ZeroDivisionError; the page
    is then flagged via the low_char path, not here).
    """
    if char_count == 0:
        return 0.0
    non_alnum = sum(1 for c in text if not c.isalnum())
    return non_alnum / char_count


def _single_char_word_ratio(text: str) -> float:
    """Fraction of whitespace-separated tokens that are exactly 1 char long.

    Empty / whitespace-only text → 0.0 (no tokens at all). Per the spec we
    would normally use ``1`` as the denominator when there are no tokens, but
    for an empty page the low_char path will already flag it; returning 0.0
    here keeps the high_garble/single_char flags from spuriously firing on
    blanks.
    """
    tokens = text.split()
    if not tokens:
        return 0.0
    single = sum(1 for t in tokens if len(t) == 1)
    return single / len(tokens)


def check_ocr_quality(
    pages: Iterable[Page],
    min_chars: int = OCR_MIN_CHARS_PER_PAGE,
    max_non_alnum_ratio: float = 0.30,
) -> QualityReport:
    """Identify pages that may have failed OCR.

    A page is "suspect" if ANY of:
      - char_count < min_chars (likely blank or garbled)
      - non-alphanumeric ratio > max_non_alnum_ratio (garbled symbols)
      - ratio of "single character words" > 0.4 (Tesseract failed to read)

    A page is "low_char" if char_count < min_chars.
    A page is "high_garble" if non-alnum ratio > max_non_alnum_ratio.
    """
    pages = list(pages)  # so we can compute total + avg + iterate twice safely
    total = len(pages)

    suspect: list[int] = []
    low_char: list[int] = []
    high_garble: list[int] = []

    total_chars = 0
    for page in pages:
        page_num = int(page["page_num"])
        char_count = int(page.get("char_count", len(page.get("text", ""))))
        text = page.get("text", "") or ""

        total_chars += char_count

        is_low_char = char_count < min_chars
        non_alnum_ratio = _non_alnum_ratio(text, char_count)
        is_high_garble = non_alnum_ratio > max_non_alnum_ratio
        single_char_ratio = _single_char_word_ratio(text)
        is_single_char_bombed = single_char_ratio > 0.4

        if is_low_char:
            low_char.append(page_num)
        if is_high_garble:
            high_garble.append(page_num)
        if is_low_char or is_high_garble or is_single_char_bombed:
            suspect.append(page_num)

    avg = (total_chars / total) if total else 0.0

    return QualityReport(
        total_pages=total,
        suspect_pages=sorted(suspect),
        low_char_pages=sorted(low_char),
        high_garble_pages=sorted(high_garble),
        avg_chars_per_page=avg,
    )
