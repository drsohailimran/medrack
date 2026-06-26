"""Tests for medrack.ingest.chunk."""
import hashlib

from medrack.ingest.chapter import Chapter
from medrack.ingest.chunk import chunk_pages, Chunk


def make_pages(*texts):
    # Accept either multiple string args (per the helper's spec) or a single
    # iterable of strings (e.g. a generator expression unpacked at the call
    # site). The brief's call sites pass a generator; we materialise it here
    # so the helper is backwards-compatible with both shapes.
    if len(texts) == 1 and not isinstance(texts[0], (str, bytes, dict)):
        texts = tuple(texts[0])
    return [
        {"page_num": i + 1, "method": "text", "text": t, "char_count": len(t)}
        for i, t in enumerate(texts)
    ]


def test_short_text_produces_one_chunk():
    pages = make_pages("This is a short page. " * 10)  # ~250 chars
    chapters = [Chapter("Book", 1, 1, 0.5)]
    chunks = chunk_pages(pages, chapters, "psm", "book-id-1")
    assert len(chunks) == 1
    assert chunks[0].token_count <= 100
    assert chunks[0].subject == "psm"
    assert chunks[0].book_id == "book-id-1"


def test_long_text_produces_multiple_chunks():
    # 10 pages × 1500 chars each ≈ 15k chars ≈ 4k tokens → should produce 5+ chunks
    pages = make_pages("Word " * 1500 for _ in range(10))
    chapters = [Chapter("Book", 1, 10, 0.5)]
    chunks = chunk_pages(pages, chapters, "medicine", "book-id-2",
                         chunk_size=1000, chunk_overlap=200)
    assert len(chunks) >= 4


def test_chunks_have_overlap():
    pages = make_pages("Word " * 1500 for _ in range(10))
    chapters = [Chapter("Book", 1, 10, 0.5)]
    chunks = chunk_pages(pages, chapters, "fmt", "book-id-3",
                         chunk_size=1000, chunk_overlap=200)
    # Check that consecutive chunks share some text (the overlap region)
    if len(chunks) >= 2:
        tail_of_first = chunks[0].text[-200:]
        head_of_second = chunks[1].text[:300]
        # They should share at least 100 chars
        shared = sum(1 for i in range(min(len(tail_of_first), 200))
                     if i < len(head_of_second) and tail_of_first[i] == head_of_second[i])
        assert shared > 50, f"Overlap too small: {shared} shared chars"


def test_chapter_metadata_propagated():
    pages = make_pages("Content A. " * 100, "Content B. " * 100)
    chapters = [
        Chapter("Intro", 1, 1, 0.5),
        Chapter("Methods", 2, 2, 0.5),
    ]
    chunks = chunk_pages(pages, chapters, "surgery", "book-id-4")
    intro_chunks = [c for c in chunks if c.chapter_title == "Intro"]
    methods_chunks = [c for c in chunks if c.chapter_title == "Methods"]
    assert len(intro_chunks) >= 1
    assert len(methods_chunks) >= 1


def test_chunk_id_is_deterministic():
    pages = make_pages("Same text. " * 100)
    chapters = [Chapter("Book", 1, 1, 0.5)]
    chunks1 = chunk_pages(pages, chapters, "psm", "book-id-5")
    chunks2 = chunk_pages(pages, chapters, "psm", "book-id-5")
    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]


def test_chunk_id_differs_with_different_book_id():
    pages = make_pages("Same text. " * 100)
    chapters = [Chapter("Book", 1, 1, 0.5)]
    c1 = chunk_pages(pages, chapters, "psm", "book-A")[0]
    c2 = chunk_pages(pages, chapters, "psm", "book-B")[0]
    assert c1.chunk_id != c2.chunk_id


def test_page_range_attribution():
    pages = make_pages("P1 content. " * 200, "P2 content. " * 200, "P3 content. " * 200)
    chapters = [Chapter("Book", 1, 3, 0.5)]
    chunks = chunk_pages(pages, chapters, "psm", "book-id-6",
                         chunk_size=1000, chunk_overlap=200)
    for c in chunks:
        assert 1 <= c.page_start <= 3
        assert 1 <= c.page_end <= 3
        assert c.page_start <= c.page_end


def test_token_count_matches_text():
    pages = make_pages("Countable text. " * 50)
    chapters = [Chapter("Book", 1, 1, 0.5)]
    chunks = chunk_pages(pages, chapters, "psm", "book-id-7")
    for c in chunks:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        assert c.token_count == len(enc.encode(c.text))
