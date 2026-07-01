"""
medrack.ingest.format_detect — classify a PDF as text / scan / mixed.

Detection runs on the first `sample_pages` pages (clamped to actual page count).
For each page we extract text via pypdf and count rendered images via
`pdfimages -list`. Per-page classification:

    text   — extracted text > 500 chars
    image  — <= 500 chars AND at least one image on the page
    blank  — 0 chars AND 0 images

The three categories are mutually exclusive and together sum to
`pages_inspected`, so downstream code can rely on the invariant

    text_pages + image_pages + blank_pages == pages_inspected.

Overall format is the dominant class over the sample:

    > 80% text → "text"
    > 80% image → "scan"
    else → "mixed"
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pypdf import PdfReader

from medrack.utils.logger import get_logger

logger = get_logger(__name__)

# A page is "text" if extracted text exceeds this many characters.
TEXT_CHAR_THRESHOLD = 500

# Dominant-format thresholds (fraction of pages in the sample).
TEXT_DOMINANCE = 0.80
IMAGE_DOMINANCE = 0.80

Format = Literal["text", "scan", "mixed"]


@dataclass
class FormatReport:
    """Result of format detection on a sample of pages of one PDF."""

    format: Format
    pages_inspected: int
    text_pages: int
    image_pages: int
    blank_pages: int


def _count_images_on_page(pdf_path: Path, page_num: int) -> int:
    """Return the number of images `pdfimages -list` reports for one page.

    `pdfimages -list` emits two header lines (a column-name row and a dashed
    separator), then one row per image. We count rows whose first whitespace-
    delimited token equals the requested 1-indexed page number. This is
    robust to the "1-indexed or 0-indexed?" question because we filter by
    the page column explicitly.
    """
    pdfimages = shutil.which("pdfimages")
    if pdfimages is None:
        logger.warning("pdfimages not on PATH; assuming 0 images for page %d", page_num)
        return 0

    proc = subprocess.run(
        [pdfimages, "-list", "-f", str(page_num), "-l", str(page_num), str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        logger.warning(
            "pdfimages returned %d for %s page %d: %s",
            proc.returncode,
            pdf_path,
            page_num,
            proc.stderr.strip(),
        )
        return 0

    count = 0
    for line in proc.stdout.splitlines():
        stripped = line.lstrip()
        # Image rows start with "<page>  <num>  <type>  ...". The page
        # column is the first whitespace-delimited token.
        parts = stripped.split()
        if not parts:
            continue
        if parts[0].isdigit() and int(parts[0]) == page_num:
            count += 1
    return count


def _classify_page(pdf_path: Path, page_num: int, text: str, image_count: int) -> str:
    """Return one of: 'text', 'image', 'blank'."""
    char_count = len(text or "")
    if char_count > TEXT_CHAR_THRESHOLD:
        return "text"
    if char_count == 0 and image_count == 0:
        return "blank"
    return "image"


def detect_format(pdf_path: Path, sample_pages: int = 5) -> FormatReport:
    """Inspect the first `sample_pages` pages and return the dominant format.

    Args:
        pdf_path: Path to a PDF file. Must exist.
        sample_pages: How many pages from the start to inspect. Clamped to
            the actual page count of the PDF.

    Returns:
        FormatReport with the dominant format and per-class counts.

    Raises:
        FileNotFoundError: if `pdf_path` does not exist.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    n = max(0, min(sample_pages, total_pages))

    text_pages = 0
    image_pages = 0
    blank_pages = 0

    for i in range(n):
        page_num_1indexed = i + 1
        try:
            page = reader.pages[i]
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 — pypdf can raise many types
            logger.warning("Failed to extract text from %s page %d: %s", pdf_path, page_num_1indexed, exc)
            text = ""

        image_count = _count_images_on_page(pdf_path, page_num_1indexed)
        kind = _classify_page(pdf_path, page_num_1indexed, text, image_count)
        if kind == "text":
            text_pages += 1
        elif kind == "image":
            image_pages += 1
        else:
            blank_pages += 1

    # Dominant format.
    if n == 0:
        dominant: Format = "text"  # degenerate, but pick something sane
    else:
        text_ratio = text_pages / n
        image_ratio = image_pages / n
        if text_ratio > TEXT_DOMINANCE:
            dominant = "text"
        elif image_ratio > IMAGE_DOMINANCE:
            dominant = "scan"
        else:
            dominant = "mixed"

    return FormatReport(
        format=dominant,
        pages_inspected=n,
        text_pages=text_pages,
        image_pages=image_pages,
        blank_pages=blank_pages,
    )


__all__ = ["detect_format", "FormatReport"]
