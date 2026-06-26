"""Tests for medrack.ingest.quality."""
from medrack.ingest.quality import check_ocr_quality


def make_page(num, text):
    return {"page_num": num, "method": "ocr", "text": text, "char_count": len(text)}


def test_good_page_not_suspect():
    good = "This is a well-OCR'd page with plenty of real text. " * 20
    report = check_ocr_quality([make_page(1, good)])
    assert report.suspect_pages == []


def test_blank_page_is_suspect():
    report = check_ocr_quality([make_page(1, "")])
    assert 1 in report.suspect_pages
    assert 1 in report.low_char_pages


def test_garbled_page_is_suspect():
    # High non-alnum ratio
    garbled = "@#$%^&*()!@#$%^&*()!@#$%^&*()!@#$%^&*()" * 10
    report = check_ocr_quality([make_page(1, garbled)])
    assert 1 in report.suspect_pages


def test_single_char_words_flagged():
    # OCR fail pattern: a b c d e f g h i j
    garbled = " ".join(["a"] * 100)
    report = check_ocr_quality([make_page(1, garbled)])
    assert 1 in report.suspect_pages


def test_mixed_pages():
    good = "This is a perfectly fine page with lots of normal text. " * 20  # ~1040 chars, above 500 threshold
    pages = [
        make_page(1, good),       # good
        make_page(2, ""),         # blank
        make_page(3, good),       # good
        make_page(4, "a b c d"),  # garbled
    ]
    report = check_ocr_quality(pages)
    assert report.total_pages == 4
    assert sorted(report.suspect_pages) == [2, 4]


def test_avg_chars_per_page():
    pages = [make_page(1, "x" * 100), make_page(2, "y" * 200)]
    report = check_ocr_quality(pages)
    assert report.avg_chars_per_page == 150.0


def test_custom_thresholds():
    # With a higher threshold, more pages are suspect
    pages = [make_page(1, "Short text.")]
    report_strict = check_ocr_quality(pages, min_chars=100)
    report_loose = check_ocr_quality(pages, min_chars=1)
    assert 1 in report_strict.suspect_pages
    assert 1 not in report_loose.suspect_pages
