"""Text extractor — yields one Page per page of a PDF using pypdf.

Per-page text extraction with pypdf. Pages that fail to extract are logged
and yielded as empty pages (we will decide later whether to OCR them).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from pypdf import PdfReader

logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def extract_text_pages(pdf_path: Path) -> Iterator[dict]:
    """Yield one Page per page of the PDF, text method only.

    Each yielded page is a dict:
        {
            "page_num": int,   # 1-indexed
            "method": "text",
            "text": str,       # full text of the page
            "char_count": int, # == len(text)
        }

    Pages whose extraction raises are logged at WARNING and yielded as
    empty pages (text="", char_count=0) so downstream code can decide
    whether to OCR them. The iterator never aborts on a single bad page.
    """
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))

    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - we deliberately swallow per-page errors
            logger.warning(
                "pypdf failed to extract page %d of %s: %s", idx, pdf_path, exc
            )
            text = ""

        yield {
            "page_num": idx,
            "method": "text",
            "text": text,
            "char_count": len(text),
        }
