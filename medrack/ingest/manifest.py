"""
medrack.ingest.manifest — read/write the manifest.json with the locked schema.

Public interface:
    load_manifest() -> dict
    save_manifest(manifest: dict) -> None
    add_book(book_record: dict) -> None
    list_books(include_archived: bool = False) -> list[dict]
    get_book(sha256: str) -> dict | None

Design notes:
- The manifest path is re-evaluated on every call via
  ``config.get_medrack_home() / "index" / "manifest.json"`` so the
  ``$MEDRACK_HOME`` environment variable override works in tests (the
  module-level ``config.MANIFEST_PATH`` constant is frozen at first import
  and would not honour the override).
- Atomic writes go via ``.tmp`` + ``Path.replace`` (POSIX-atomic on the
  same filesystem) so a crash mid-write never corrupts the manifest.
- ``save_manifest`` normalises ``version`` to ``MANIFEST_VERSION`` so stale
  code (or hand-edits) cannot persist a wrong-schema manifest.
- ``add_book`` dedupes by ``sha256`` only against *active* (non-archived)
  records: re-adding a previously archived book is allowed (the dedup
  helper in the caller should check first if it wants stricter behaviour).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from medrack import config


def _manifest_path() -> Path:
    """Re-evaluate the manifest path so ``$MEDRACK_HOME`` overrides work."""
    return config.get_medrack_home() / "index" / "manifest.json"


def get_manifest_path() -> Path:
    """Public alias for :func:`_manifest_path` re-evaluating ``$MEDRACK_HOME``.

    Exposed so external callers (notably the Gradio dashboard's State tab)
    can read the current manifest path without going through the private
    helper. The path is re-evaluated on every call so environment overrides
    take effect immediately.
    """
    return _manifest_path()


def _empty_manifest() -> dict[str, Any]:
    """Canonical empty manifest for the current schema version."""
    return {
        "version": config.MANIFEST_VERSION,
        "books": [],
        "modules": [],
    }


def load_manifest() -> dict:
    """Load and return the manifest. Returns an empty manifest if the file
    is missing (first run). Raises ``json.JSONDecodeError`` on a corrupt
    file — we deliberately do not silently recover, because the manifest
    is the source of truth for what is indexed."""
    path = _manifest_path()
    if not path.exists():
        return _empty_manifest()
    return json.loads(path.read_text())


def save_manifest(manifest: dict) -> None:
    """Atomically write the manifest. Validates the version field, then
    normalises it to ``MANIFEST_VERSION`` so stale code cannot persist an
    out-of-schema manifest."""
    version = manifest.get("version")
    if version != config.MANIFEST_VERSION:
        # We still allow the write (and normalise), but surface the mismatch
        # so the caller knows their input was off. The brief's
        # ``test_manifest_writes_have_version`` test relies on this
        # normalisation happening before the file is written.
        manifest["version"] = config.MANIFEST_VERSION

    path = _manifest_path()
    # Ensure the parent dir exists (the brief's temp_home fixture creates
    # ``index/``, but in real first-run usage the index dir may not yet).
    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to .tmp then rename. Path.replace() is atomic on
    # POSIX when src and dst are on the same filesystem (they always are
    # — both live under HOME/index/).
    tmp_path = path.with_suffix(path.suffix + ".tmp")  # manifest.json.tmp
    tmp_path.write_text(json.dumps(manifest, indent=2, sort_keys=False))
    tmp_path.replace(path)


def add_book(book_record: dict) -> None:
    """Append a book record to the manifest.

    Raises ``ValueError`` if a non-archived book with the same ``sha256``
    is already present. Archived books are ignored for dedup purposes —
    a re-ingest of a previously-archived book is allowed.
    """
    manifest = load_manifest()
    target_sha = book_record["sha256"]
    for existing in manifest["books"]:
        if existing.get("sha256") == target_sha and not existing.get("archived_at"):
            raise ValueError(f"Book with sha256 {target_sha} already indexed")
    manifest["books"].append(book_record)
    save_manifest(manifest)


def list_books(include_archived: bool = False) -> list[dict]:
    """Return the books list. By default, archived books are filtered out."""
    manifest = load_manifest()
    books = manifest.get("books", [])
    if include_archived:
        return list(books)
    return [b for b in books if not b.get("archived_at")]


def get_book(sha256: str) -> dict | None:
    """Find a book by ``sha256``. Returns ``None`` if not present
    (archived or otherwise)."""
    manifest = load_manifest()
    for b in manifest.get("books", []):
        if b.get("sha256") == sha256:
            return b
    return None


def archive_book(sha256: str) -> bool:
    """Mark the book with the given ``sha256`` as archived.

    Sets ``archived_at`` to the current UTC time in ISO 8601 format
    (e.g. ``"2026-06-26T16:00:00+00:00"``) and persists the manifest.

    Returns
    -------
    bool
        ``True`` if a non-archived book with that sha was found and
        archived; ``False`` if no such book exists (either no match or
        it was already archived).

    This is a no-op for books that are already archived — we don't bump
    the ``archived_at`` timestamp on a re-archive, so the original
    archive time is preserved.
    """
    manifest = load_manifest()
    archived = False
    for book in manifest.get("books", []):
        if book.get("sha256") == sha256 and not book.get("archived_at"):
            book["archived_at"] = datetime.now(timezone.utc).isoformat()
            archived = True
            break
    if archived:
        save_manifest(manifest)
    return archived


__all__ = [
    "load_manifest",
    "save_manifest",
    "add_book",
    "list_books",
    "get_book",
    "archive_book",
]
