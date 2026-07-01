"""Tests for medrack.module.extract."""
from pathlib import Path

from medrack.module.extract import extract_module_pages

TEXT_PDF = Path("/home/sohail/medrack-samples/modules/MODULE 1-1.pdf")
SCAN_PDF = Path("/home/sohail/medrack-samples/modules/solved_singi_fmt_260331_204237_260618_174727.pdf")


def test_text_module_yields_all_pages():
    pages = extract_module_pages(TEXT_PDF)
    assert len(pages) == 55


def test_each_page_has_required_fields():
    pages = extract_module_pages(TEXT_PDF)
    for p in pages[:5]:
        assert "page_num" in p
        assert "method" in p
        assert "text" in p
        assert "char_count" in p


def test_scan_module_yields_all_pages_via_ocr():
    """The scanned FMT module should fall back to OCR for all pages."""
    pages = extract_module_pages(SCAN_PDF)
    assert len(pages) == 24
    ocr_pages = [p for p in pages if p["method"] == "ocr"]
    assert len(ocr_pages) >= 20  # most pages need OCR


def test_pages_are_cleaned():
    """Letter-spacing artifacts from MODULE 1-1 should be collapsed by the cleaner."""
    pages = extract_module_pages(TEXT_PDF)
    # The first MCQ has 'Definition of health given by WHO'
    # After cleaning, 'D e f i n i t i o n' should be 'Definition'
    first_page_text = pages[0]["text"]
    # Check that we don't have pathological letter-spacing in the first page
    if "D e f" in first_page_text or "D  e" in first_page_text:
        # This would mean the cleaner didn't run
        raise AssertionError("Letter-spacing artifact survived cleaning")


def test_nonexistent_file_raises():
    import pytest
    with pytest.raises(FileNotFoundError):
        extract_module_pages(Path("/nonexistent/file.pdf"))
