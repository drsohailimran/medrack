"""Tests for medrack.ingest.format_detect."""
from pathlib import Path

import pytest

from medrack.ingest.format_detect import detect_format, FormatReport

# Real samples
TEXT_PDF = Path("/home/sohail/medrack-samples/kb-chunks/Essentials_of_Forensic_Medicine(KS_Naray_chunk001_pages1-50.pdf")
SCAN_PDF = Path("/home/sohail/medrack-samples/kb-chunks/parks-textbook-of-preventive-and-social-_chunk001_pages1-50.pdf")


def test_text_pdf_detected_as_text_or_mixed():
    """A text-extractable PDF should return text or mixed format."""
    report = detect_format(TEXT_PDF, sample_pages=5)
    assert report.format in ("text", "mixed")
    assert report.pages_inspected == 5
    assert report.text_pages >= 1


def test_scan_pdf_detected_as_scan_or_mixed():
    """An image-based PDF should return scan or mixed format."""
    report = detect_format(SCAN_PDF, sample_pages=5)
    assert report.format in ("scan", "mixed")
    assert report.pages_inspected == 5


def test_report_includes_per_page_counts():
    report = detect_format(TEXT_PDF, sample_pages=3)
    total = report.text_pages + report.image_pages + report.blank_pages
    assert total == report.pages_inspected


def test_format_report_is_a_dataclass_or_typed_class():
    """FormatReport must have the exact fields downstream code expects."""
    report = detect_format(TEXT_PDF, sample_pages=2)
    for field in ("format", "pages_inspected", "text_pages", "image_pages", "blank_pages"):
        assert hasattr(report, field), f"FormatReport missing field: {field}"


def test_nonexistent_path_raises():
    with pytest.raises(FileNotFoundError):
        detect_format(Path("/nonexistent/file.pdf"), sample_pages=1)


def test_sample_pages_clamped_to_total():
    """If sample_pages > total pages, only inspect what's there."""
    report = detect_format(TEXT_PDF, sample_pages=999)
    assert report.pages_inspected <= 50  # the sample has 50 pages
