"""Token-bounded chunking of cleaned pages, chapter-aware.

Stage 2.2, T6 of the KB ingest pipeline. Pure functions, no I/O. Uses
``tiktoken`` (``cl100k_base``) for token counting so chunk sizes are stable
across embedders and retriever tokenisers.

Algorithm per chapter (chapter boundaries are not crossed):
  1. Concatenate the chapter's pages' text into one string, recording
     ``(page_num, char_start, char_end)`` for each page.
  2. Encode the whole chapter with ``tiktoken``.
  3. Slide a window of ``chunk_size`` tokens forward by
     ``chunk_size - chunk_overlap`` tokens; emit a ``Chunk`` for each window.
  4. For each window, decode tokens back to text and figure out
     ``page_start`` / ``page_end`` from the chapter's char-position table.

``chunk_id`` is the first 16 hex chars of ``sha256(book_id|page_start|page_end|text[:200])``
— deterministic so re-ingest produces stable IDs (T7's indexer depends on this).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Sequence

import tiktoken

from medrack.ingest.chapter import Chapter

# Module-level encoding cache (cl100k_base loads a ~1MB BPE table; cache once).
_ENCODING = None


def _get_encoding():
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


@dataclass
class Chunk:
    """A token-bounded slice of a book, with chapter + provenance metadata."""

    chunk_id: str  # deterministic UUID from sha256 of (book_id, page_start, page_end, text)
    text: str
    subject: str
    book_id: str
    chapter_title: str
    page_start: int
    page_end: int
    token_count: int
    # embedding: list[float]  # filled in T7, not T6


def _build_chapter_spans(pages: Sequence[dict], chapter: Chapter) -> List[dict]:
    """Return only the pages that fall inside this chapter, in order.

    Each returned entry is a page dict (preserving original keys).
    Pages are filtered to ``chapter.start_page .. chapter.end_page`` (inclusive).
    """
    spans: List[dict] = []
    for p in pages:
        pn = p["page_num"]
        if chapter.start_page <= pn <= chapter.end_page:
            spans.append(p)
    # If a chapter range matches no pages (e.g. test data inconsistency),
    # return an empty list — the caller emits no chunks for that chapter.
    return spans


def _page_index_for_char(
    char_to_page: List[tuple], char_pos: int
) -> int:
    """Find the page that contains ``char_pos`` in the concatenated string.

    ``char_to_page`` is sorted by ``char_start`` ascending. Each entry is
    ``(page_num, char_start, char_end)``. We want the *last* entry whose
    ``char_start <= char_pos`` (i.e. the page currently being written).
    """
    page_num = char_to_page[0][0]
    for pn, cs, _ce in char_to_page:
        if cs <= char_pos:
            page_num = pn
        else:
            break
    return page_num


def _chunk_one_chapter(
    pages: Sequence[dict],
    chapter: Chapter,
    subject: str,
    book_id: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Chunk]:
    """Tokenize one chapter and slide a window across it."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must satisfy 0 <= overlap < chunk_size")

    spans = _build_chapter_spans(pages, chapter)
    if not spans:
        return []

    # Build the concatenation and the char-position table for page attribution.
    concat_parts: List[str] = []
    char_to_page: List[tuple] = []  # (page_num, char_start, char_end)
    cursor = 0
    for p in spans:
        text = p["text"] or ""
        char_start = cursor
        char_end = cursor + len(text)
        char_to_page.append((p["page_num"], char_start, char_end))
        concat_parts.append(text)
        cursor = char_end
    concat = "".join(concat_parts)

    if not concat.strip():
        return []  # nothing to chunk

    enc = _get_encoding()
    token_ids = enc.encode(concat)
    n_tokens = len(token_ids)
    if n_tokens == 0:
        return []

    # Sliding window over token ids.
    # First window starts at 0; subsequent windows step by (chunk_size - overlap).
    # The last window may be shorter than chunk_size; we still emit it
    # so that no tail content is dropped.
    step = chunk_size - chunk_overlap
    chunks: List[Chunk] = []
    start = 0
    while start < n_tokens:
        end = min(start + chunk_size, n_tokens)
        window_ids = token_ids[start:end]
        window_text = enc.decode(window_ids)

        # Locate the char range this window corresponds to within ``concat``.
        # Decode the prefix before this window to learn the absolute char
        # offset of the window's first character; the window's length in
        # characters gives the end offset. This is stable: re-decoding a
        # prefix always produces the same string, so two identical inputs
        # always yield the same offsets (and therefore the same chunk_id).
        prefix_ids = token_ids[:start]
        prefix_text = enc.decode(prefix_ids) if prefix_ids else ""
        decoded_char_start = len(prefix_text)
        decoded_char_end = decoded_char_start + len(window_text)

        page_start = _page_index_for_char(char_to_page, decoded_char_start)
        page_end = _page_index_for_char(char_to_page, max(decoded_char_end - 1, decoded_char_start))

        chunk_id = hashlib.sha256(
            f"{book_id}|{page_start}|{page_end}|{window_text[:200]}".encode()
        ).hexdigest()[:16]

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=window_text,
                subject=subject,
                book_id=book_id,
                chapter_title=chapter.title,
                page_start=page_start,
                page_end=page_end,
                token_count=len(window_ids),
            )
        )

        if end >= n_tokens:
            break  # exhausted the token stream
        start += step

    return chunks


def chunk_pages(
    pages: list,
    chapters: list,
    subject: str,
    book_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Chunk]:
    """Chunk the pages respecting chapter boundaries.

    Parameters
    ----------
    pages:
        List of page dicts (``page_num``, ``text``, ...). Order matters; we
        trust ``chapter.start_page``/``chapter.end_page`` to address into
        this list.
    chapters:
        List of ``Chapter`` objects. Each chapter is chunked independently;
        chunks never cross chapter boundaries.
    subject, book_id:
        Provenance metadata propagated to every chunk.
    chunk_size, chunk_overlap:
        Token counts (``tiktoken`` cl100k_base). Defaults match
        ``medrack.config.CHUNK_SIZE_TOKENS`` / ``CHUNK_OVERLAP_TOKENS``.
    """
    all_chunks: List[Chunk] = []
    for chapter in chapters:
        all_chunks.extend(
            _chunk_one_chapter(
                pages=pages,
                chapter=chapter,
                subject=subject,
                book_id=book_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return all_chunks


__all__ = ["Chunk", "chunk_pages"]
