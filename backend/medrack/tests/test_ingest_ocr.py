"""Tests for medrack.ingest.ocr."""
from pathlib import Path

import pytest

from medrack.ingest.ocr import ocr_page

SCAN_PDF = Path("/home/sohail/medrack-samples/kb-chunks/parks-textbook-of-preventive-and-social-_chunk001_pages1-50.pdf")
TEXT_PDF = Path("/home/sohail/medrack-samples/kb-chunks/Essentials_of_Forensic_Medicine(KS_Naray_chunk001_pages1-50.pdf")


def test_ocr_page_returns_required_fields():
    page = ocr_page(SCAN_PDF, page_num=1, dpi=300)
    for field in ("page_num", "method", "text", "char_count"):
        assert field in page
    assert page["page_num"] == 1
    assert page["method"] == "ocr"


def test_ocr_on_image_pdf_returns_nonzero_text():
    """OCR should produce some text from an image-based PDF page."""
    page = ocr_page(SCAN_PDF, page_num=1, dpi=300)
    assert page["char_count"] > 0
    # Park's PSM page 1 should have something medical in it


def test_ocr_on_text_pdf_also_works():
    """OCR on a text PDF still produces text (just slower)."""
    page = ocr_page(TEXT_PDF, page_num=1, dpi=300)
    assert page["char_count"] > 0
    assert page["method"] == "ocr"


def test_ocr_page_invalid_page_raises():
    with pytest.raises((ValueError, IndexError)):
        ocr_page(SCAN_PDF, page_num=99999)


def test_ocr_cleans_up_temp_files():
    """After OCR, no temp PNG should be left in cwd or /tmp."""
    import os
    import tempfile
    before = set(os.listdir(tempfile.gettempdir()))
    ocr_page(SCAN_PDF, page_num=2, dpi=300)
    after = set(os.listdir(tempfile.gettempdir()))
    # Allow new files from OTHER processes, just check no new medrack-ocr-*.png
    new_pngs = [f for f in after - before if f.startswith("medrack-ocr-") and f.endswith(".png")]
    assert new_pngs == [], f"OCR leaked temp files: {new_pngs}"
