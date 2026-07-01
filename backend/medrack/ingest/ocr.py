"""
medrack.ingest.ocr — OCR wrapper for image-based PDF pages.

Renders a single page of a PDF to a PNG via `pdftoppm` and runs Tesseract
OCR on it via `pytesseract`. Used as the fallback path for pages where text
extraction (T2) yields <500 chars.

Public interface:
    ocr_page(pdf_path, page_num, dpi=300) -> Page

The function:
  1. Renders the requested 1-indexed page to a PNG in a temp dir.
  2. OCRs the PNG with Tesseract (eng, --psm 6 = assume single uniform block).
  3. Returns a Page dict compatible with the text-extract output.
  4. Cleans up the temp dir (full rmtree, not just unlink — there are
     pdftoppm side files sometimes).
  5. Logs timing via medrack.utils.logger (the T1 logger).

Raises:
    ValueError: page_num is out of range, pdftoppm fails, or no PNG produced.
    FileNotFoundError: pdf_path does not exist.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image
import pytesseract

from medrack.utils.logger import get_logger

logger = get_logger(__name__)


def _find_rendered_png(tmp_dir: Path) -> Path:
    """Find the single PNG that pdftoppm wrote into tmp_dir.

    pdftoppm names outputs as {stem}-{page}.png, zero-padding the page number
    to the width of the document's last page number. We don't try to predict
    the padding — we just glob the dir for the only PNG.
    """
    pngs = sorted(tmp_dir.glob("*.png"))
    if not pngs:
        raise ValueError(
            f"pdftoppm produced no PNG in {tmp_dir} "
            f"(check that page_num is in range and pdf_path is a valid PDF)"
        )
    if len(pngs) > 1:
        # Shouldn't happen with -f == -l, but be defensive.
        raise ValueError(
            f"pdftoppm produced {len(pngs)} PNGs in {tmp_dir}, expected exactly 1"
        )
    return pngs[0]


def ocr_page(pdf_path: Path, page_num: int, dpi: int = 300) -> dict[str, Any]:
    """Render page `page_num` (1-indexed) of the PDF to an image and OCR it.

    Args:
        pdf_path: Path to the source PDF.
        page_num: 1-indexed page number.
        dpi: Resolution for rendering (default 300, recommended for OCR).

    Returns:
        Page = {
            "page_num": int,   # echoed from input
            "method": "ocr",
            "text": str,
            "char_count": int,
        }

    Raises:
        FileNotFoundError: pdf_path does not exist.
        ValueError: page_num is out of range, pdftoppm fails, or no PNG produced.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if page_num < 1:
        raise ValueError(f"page_num must be >= 1, got {page_num}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="medrack-ocr-"))
    tmp_stem = tmp_dir / "page"  # path-stem for pdftoppm output

    start = time.perf_counter()
    try:
        # Render the single page to PNG. -f and -l both set to page_num
        # restrict output to that one page.
        proc = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r", str(dpi),
                "-f", str(page_num),
                "-l", str(page_num),
                str(pdf_path),
                str(tmp_stem),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            # pdftoppm prints "Wrong page range given..." for out-of-range
            # pages (exit 99). Anything non-zero means we don't have a PNG.
            stderr_tail = (proc.stderr or "").strip().splitlines()[-1] if proc.stderr else ""
            raise ValueError(
                f"pdftoppm failed (rc={proc.returncode}) for "
                f"{pdf_path.name} page {page_num}: {stderr_tail}"
            )

        png_path = _find_rendered_png(tmp_dir)

        image = Image.open(png_path)
        try:
            text = pytesseract.image_to_string(image, lang="eng", config="--psm 6")
        finally:
            try:
                image.close()
            except Exception:
                pass
    finally:
        # Always rmtree — the test_ocr_cleans_up_temp_files test inspects
        # /tmp before and after the call, and a stray medrack-ocr-* dir
        # with the PNG still inside would fail the assertion.
        shutil.rmtree(tmp_dir, ignore_errors=True)

    elapsed = time.perf_counter() - start
    text = text or ""
    char_count = len(text)
    logger.info(
        f"OCR page {page_num} of {pdf_path.name} "
        f"({char_count} chars, dpi={dpi}, {elapsed:.2f}s)"
    )

    return {
        "page_num": int(page_num),
        "method": "ocr",
        "text": text,
        "char_count": char_count,
    }


__all__ = ["ocr_page"]
