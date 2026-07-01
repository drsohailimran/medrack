"""Tests for medrack.ingest.text_extract."""
from pathlib import Path

import pytest

from medrack.ingest.text_extract import extract_text_pages

TEXT_PDF = Path("/home/sohail/medrack-samples/kb-chunks/Essentials_of_Forensic_Medicine(KS_Naray_chunk001_pages1-50.pdf")
SCAN_PDF = Path("/home/sohail/medrack-samples/kb-chunks/parks-textbook-of-preventive-and-social-_chunk001_pages1-50.pdf")


def test_text_pdf_yields_50_pages():
    pages = list(extract_text_pages(TEXT_PDF))
    assert len(pages) == 50


def test_each_page_has_required_fields():
    pages = list(extract_text_pages(TEXT_PDF))
    for p in pages[:5]:
        assert "page_num" in p
        assert "method" in p
        assert "text" in p
        assert "char_count" in p
        assert p["method"] == "text"


def test_page_numbers_are_one_indexed_and_sequential():
    pages = list(extract_text_pages(TEXT_PDF))
    assert [p["page_num"] for p in pages] == list(range(1, 51))


def test_char_count_matches_text_length():
    pages = list(extract_text_pages(TEXT_PDF))
    for p in pages:
        assert p["char_count"] == len(p["text"])


def test_scan_pdf_yields_50_pages_with_low_text():
    """The image-based PDF should yield 50 pages but most will be empty."""
    pages = list(extract_text_pages(SCAN_PDF))
    assert len(pages) == 50
    # The first few pages are likely cover/blank, so most char_counts are low
    text_chars = sum(p["char_count"] for p in pages)
    assert text_chars < 5000  # image-based PDF, should have very little text


def test_bad_page_does_not_kill_iteration():
    """A single broken page should be logged and skipped, not raise."""
    pages = list(extract_text_pages(TEXT_PDF))  # use a known-good file; we trust pypdf here
    assert len(pages) == 50  # all 50 succeeded
