r"""Chapter segmentation for cleaned page text.

Pure functions, no I/O. Used by the KB ingest pipeline (Stage 2.2, T5) to
split a book's pages into chapters by detecting heading lines with regex.

Detection rules (applied in order, first match wins per line):
    1. ``^CHAPTER\s+\d+``        e.g. "CHAPTER 1", "CHAPTER 12"
    2. ``^\d+\.\s+[A-Z]``       e.g. "1. Introduction"
    3. ``^[A-Z][A-Z\s]{4,}$``   all-caps line, >=5 chars, no lowercase
    4. ``^\d+\s+[A-Z][a-z]+``   e.g. "1 Introduction"

The first chapter always starts at page 1; if the first detected heading
is on page 5, pages 1-4 are prepended to it (title = book_title). When no
headings are found, the entire book is treated as a single chapter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A line is a "heading" if it matches one of these patterns. We check in
# the order listed; the first match per line wins. Line-stripped before
# matching so a stray leading space can't break detection.
_HEADING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^CHAPTER\s+\d+"),  # "CHAPTER 1", "CHAPTER 12"
    re.compile(r"^\d+\.\s+[A-Z]"),  # "1. Introduction", "12. Methods"
    re.compile(r"^[A-Z][A-Z\s]{4,}$"),  # all-caps, >=5 chars, no lowercase
    re.compile(r"^\d+\s+[A-Z][a-z]+"),  # "1 Introduction"
)


@dataclass
class Chapter:
    """A detected chapter span over the page list."""

    title: str
    start_page: int
    end_page: int
    confidence: float  # 0.0 to 1.0


def _find_first_heading(text: str) -> str | None:
    """Scan a page's text line by line; return the first heading line found.

    Returns ``None`` if no line matches any rule. Empty / blank lines are
    skipped. We match against the line stripped of leading/trailing
    whitespace, but we return the stripped heading text (a cleaner title).
    """
    if not text:
        return None
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        for pat in _HEADING_PATTERNS:
            if pat.match(line):
                return line
    return None


def _compute_confidence(heading_count: int, page_count: int) -> float:
    """Heuristic confidence for the segmentation.

    0 headings -> 0.5 (manual fallback, one chapter only).
    1 heading  -> 0.3 (we're not very confident we found them all).
    2+ headings -> min(1.0, headings / max(1, len(pages) // 20)).
    """
    if heading_count == 0:
        return 0.5
    if heading_count == 1:
        return 0.3
    return min(1.0, heading_count / max(1, page_count // 20))


def segment_chapters(
    pages: list[dict],
    book_title: str,
    min_confidence: float = 0.5,
) -> list[Chapter]:
    """Detect chapter boundaries from page text.

    Parameters
    ----------
    pages:
        List of page dicts (``page_num``, ``method``, ``text``, ``char_count``).
    book_title:
        Used as the chapter title when no headings are found, and as a
        fallback title if the first detected heading is past page 1.
    min_confidence:
        Reserved for future filtering; currently informational only. All
        chapters are returned regardless of confidence so the caller can
        decide what to do.

    Returns
    -------
    list[Chapter]
        Chapters are contiguous, sorted by ``start_page``, and cover the
        full page range ``[1, len(pages)]``. The first chapter's
        ``start_page`` is always 1.
    """
    del min_confidence  # accepted for API stability; unused for now
    page_count = len(pages)
    if page_count == 0:
        return []

    # 1. Walk pages in order; remember the first heading line on each page.
    chapter_starts: list[tuple[int, str]] = []  # (page_num_1based, heading_text)
    for page in pages:
        heading = _find_first_heading(page.get("text", ""))
        if heading is not None:
            chapter_starts.append((page["page_num"], heading))

    # 2. No headings -> single chapter, the whole book.
    if not chapter_starts:
        return [Chapter(
            title=book_title,
            start_page=1,
            end_page=page_count,
            confidence=0.5,
        )]

    # 3. Build chapters from chapter-start pages. If the first heading is
    #    past page 1, backfill chapter 0 starting at page 1 with the
    #    book's title so we always have something at the front.
    confidence = _compute_confidence(len(chapter_starts), page_count)

    chapters: list[Chapter] = []
    if chapter_starts[0][0] != 1:
        chapters.append(Chapter(
            title=book_title,
            start_page=1,
            end_page=chapter_starts[0][0] - 1,
            confidence=confidence,
        ))

    for i, (start_page, heading) in enumerate(chapter_starts):
        # The chapter runs from this start page up to one page before the
        # next chapter start, or to the end of the book for the last one.
        if i + 1 < len(chapter_starts):
            end_page = chapter_starts[i + 1][0] - 1
        else:
            end_page = page_count
        chapters.append(Chapter(
            title=heading,
            start_page=start_page,
            end_page=end_page,
            confidence=confidence,
        ))

    return chapters


__all__ = ["Chapter", "segment_chapters"]
