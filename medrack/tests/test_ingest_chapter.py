"""Tests for medrack.ingest.chapter."""
from medrack.ingest.chapter import segment_chapters, Chapter


def pages_with_titles(*titles: str):
    """Build a list of fake pages, one per title, each page just contains the title."""
    return [
        {"page_num": i + 1, "method": "text",
         "text": f"Some body text.\n\n{t}\n\nMore body text.", "char_count": 50}
        for i, t in enumerate(titles)
    ]


def test_no_headings_returns_single_chapter():
    pages = pages_with_titles("Just some text.", "More text here.", "Even more text.")
    chapters = segment_chapters(pages, book_title="Untitled Book")
    assert len(chapters) == 1
    assert chapters[0].title == "Untitled Book"
    assert chapters[0].start_page == 1
    assert chapters[0].end_page == 3
    assert chapters[0].confidence == 0.5


def test_chapter_keyword_detected():
    pages = pages_with_titles("CHAPTER 1: Introduction", "intro body", "more intro")
    chapters = segment_chapters(pages, book_title="Test Book")
    assert len(chapters) == 1
    assert "CHAPTER 1" in chapters[0].title or "Introduction" in chapters[0].title


def test_numbered_chapter_detected():
    pages = pages_with_titles(
        "1. Introduction", "intro body",
        "2. Methods", "methods body",
        "3. Results", "results body",
    )
    chapters = segment_chapters(pages, book_title="Test Book")
    assert len(chapters) == 3
    assert chapters[0].start_page == 1
    assert chapters[1].start_page == 3
    assert chapters[2].start_page == 5
    assert chapters[2].end_page == 6


def test_chapter_end_pages_are_contiguous():
    pages = pages_with_titles(
        "1. A", "a body",
        "2. B", "b body",
        "3. C", "c body",
    )
    chapters = segment_chapters(pages, book_title="Test Book")
    for i in range(len(chapters) - 1):
        assert chapters[i].end_page + 1 == chapters[i + 1].start_page


def test_all_caps_heading_detected():
    pages = pages_with_titles("INTRODUCTION", "body", "METHODS", "body")
    chapters = segment_chapters(pages, book_title="Test Book")
    assert len(chapters) == 2


def test_confidence_increases_with_more_headings():
    few = segment_chapters(pages_with_titles("1. A", "body", "2. B", "body"), "Test")
    many = segment_chapters(pages_with_titles(*(sum([[f"{i}. Ch{i}", "body"] for i in range(1, 11)], []))), "Test")
    assert many[-1].confidence >= few[-1].confidence


def test_single_heading_has_low_confidence():
    pages = pages_with_titles("1. Only Chapter", "body", "body", "body")
    chapters = segment_chapters(pages, book_title="Test")
    assert chapters[0].confidence <= 0.5
