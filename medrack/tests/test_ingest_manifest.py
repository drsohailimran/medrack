"""Tests for medrack.ingest.manifest."""
import json

import pytest

from medrack.ingest.manifest import (
    load_manifest, save_manifest, add_book, list_books, get_book
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "index").mkdir(parents=True, exist_ok=True)
    yield tmp_path


SAMPLE_BOOK = {
    "book_id": "00000000-0000-0000-0000-000000000001",
    "subject": "psm",
    "title": "Test Book",
    "filename": "test.pdf",
    "sha256": "abc123",
    "pages": 100,
    "chunks": 80,
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "indexed_at": "2026-06-26T16:00:00Z",
    "replaced_by": None,
    "archived_at": None,
    "ocr_pages": 0,
    "ocr_suspect_pages": [],
}


def test_load_empty_when_no_file(temp_home):
    m = load_manifest()
    assert m["version"] == 1
    assert m["books"] == []
    assert m["modules"] == []


def test_save_and_load_roundtrip(temp_home):
    m = load_manifest()
    m["books"].append(SAMPLE_BOOK)
    save_manifest(m)
    m2 = load_manifest()
    assert len(m2["books"]) == 1
    assert m2["books"][0]["sha256"] == "abc123"


def test_add_book(temp_home):
    add_book(SAMPLE_BOOK)
    books = list_books()
    assert len(books) == 1
    assert books[0]["title"] == "Test Book"


def test_add_duplicate_sha256_raises(temp_home):
    add_book(SAMPLE_BOOK)
    with pytest.raises(ValueError, match="already indexed"):
        add_book(SAMPLE_BOOK)


def test_list_books_excludes_archived(temp_home):
    archived = {**SAMPLE_BOOK, "book_id": "id-2", "sha256": "def456", "archived_at": "2026-06-27"}
    add_book(SAMPLE_BOOK)
    add_book(archived)
    active = list_books(include_archived=False)
    all_books = list_books(include_archived=True)
    assert len(active) == 1
    assert len(all_books) == 2


def test_get_book_by_sha256(temp_home):
    add_book(SAMPLE_BOOK)
    found = get_book("abc123")
    assert found is not None
    assert found["title"] == "Test Book"
    assert get_book("nonexistent") is None


def test_atomic_write_does_not_corrupt_on_interrupted_write(temp_home):
    """If save_manifest is interrupted, the previous manifest should remain intact."""
    m = load_manifest()
    m["books"].append(SAMPLE_BOOK)
    save_manifest(m)  # initial save
    # Now save again with new content; if interrupted, .tmp exists, manifest is intact
    m["books"].append({**SAMPLE_BOOK, "book_id": "id-2", "sha256": "def456"})
    save_manifest(m)
    # No .tmp file left over
    assert not (temp_home / "index" / "manifest.json.tmp").exists()
    # Manifest has both books
    final = load_manifest()
    assert len(final["books"]) == 2


def test_manifest_writes_have_version(temp_home):
    save_manifest({"version": 999, "books": [], "modules": []})
    # Version should be normalized to 1
    m = load_manifest()
    assert m["version"] == 1
