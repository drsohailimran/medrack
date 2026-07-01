"""medrack.module.extract — module-level PDF page extractor.

Wraps Stage 2.2's ingest pipeline (format_detect + text_extract + ocr +
clean) behind a single function so downstream question/chapter parsers
can work on a uniform list of cleaned ``Page`` dicts.

Algorithm (per module PDF):
    1. format_report = format_detect.detect_format(pdf_path, sample_pages=5)
       (informational only — the extract-then-OCR-if-low-chars policy
       below handles both text and scan PDFs uniformly).
    2. Always run text_extract.extract_text_pages first.
    3. For any page with char_count < 100, re-OCR with ocr.ocr_page.
    4. clean.clean_pages(all_pages) — collapses letter-spacing, strips
       page numbers, normalises whitespace.
    5. Return the cleaned pages.

The returned ``Page`` is the same dict shape used everywhere else in
Stage 2.2::

    {"page_num": int, "method": str, "text": str, "char_count": int}

``method`` is one of:
    - ``"text"`` — pypdf gave us usable text
    - ``"ocr"``  — text was too short, OCR was used
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from medrack.ingest import clean, format_detect, ocr, text_extract
from medrack.utils.logger import get_logger

logger = get_logger(__name__)

# Below this many characters per page, text extraction is considered
# to have failed and the page is sent to OCR. 100 is intentionally
# generous — a single MCQ's stem is typically ~150–300 chars, so a
# sub-100 page is almost certainly an image-only page that pypdf
# couldn't read.
OCR_FALLBACK_CHAR_THRESHOLD = 100


def _to_path(pdf_path: Path | str) -> Path:
    """Coerce to Path and verify the file exists.

    Raises:
        FileNotFoundError: if the file is missing.
    """
    p = Path(pdf_path)
    if not p.is_file():
        raise FileNotFoundError(f"PDF not found: {p}")
    return p


def extract_module_pages(pdf_path: Path) -> list[dict[str, Any]]:
    """Extract pages from a module PDF, cleaned and ready for question extraction.

    Args:
        pdf_path: Path to the module PDF.

    Returns:
        A list of cleaned Page dicts (see module docstring for shape),
        one per page, in document order.

    Raises:
        FileNotFoundError: if ``pdf_path`` does not exist.
    """
    pdf_path = _to_path(pdf_path)

    # Step 1: detect format (informational; we still try text first regardless).
    format_report = format_detect.detect_format(pdf_path, sample_pages=5)
    logger.info(
        "extract_module_pages: %s format=%s inspected=%d text=%d image=%d blank=%d",
        pdf_path.name,
        format_report.format,
        format_report.pages_inspected,
        format_report.text_pages,
        format_report.image_pages,
        format_report.blank_pages,
    )

    # Step 2: text-extract first.
    pages: list[dict[str, Any]] = list(text_extract.extract_text_pages(pdf_path))

    # Step 3: re-OCR any page that's too short to be useful.
    ocr_count = 0
    for page in pages:
        if page["char_count"] < OCR_FALLBACK_CHAR_THRESHOLD:
            try:
                ocr_page = ocr.ocr_page(pdf_path, page["page_num"])
            except Exception as exc:  # noqa: BLE001 - OCR can fail in many ways
                logger.warning(
                    "OCR fallback failed for %s page %d: %s; keeping text extraction",
                    pdf_path.name,
                    page["page_num"],
                    exc,
                )
                continue
            # Replace the text-extracted page in place.
            page["text"] = ocr_page["text"]
            page["char_count"] = ocr_page["char_count"]
            page["method"] = ocr_page["method"]
            ocr_count += 1

    logger.info(
        "extract_module_pages: %s pages=%d ocr_fallback=%d",
        pdf_path.name,
        len(pages),
        ocr_count,
    )

    # Step 4 + 5: clean and return.
    return clean.clean_pages(pages)


__all__ = ["extract_module_pages"]
