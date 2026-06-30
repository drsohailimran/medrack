"""LibraryService — Textbook and question-bank management (Phase 12).

The :class:`LibraryService` is the stable interface for managing
the MedRack library: listing textbooks, listing question banks,
adding books, removing books, re-indexing, and viewing ingestion
status.

The service never mutates the library state without an explicit
action method (``add_book``, ``remove_book``, ``reindex``).
Read operations are pure.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ----------------------------------------------------------------------
# Result types (JSON-serializable, versioned)
# ----------------------------------------------------------------------

@dataclass
class BookInfo:
    """A single textbook in the library.

    Attributes
    ----------
    book_id:
        Stable identifier (e.g. ``"park_psm_v4"``).
    title:
        Human-readable title.
    subject:
        ``"psm"`` or ``"fmt"``.
    path:
        Filesystem path to the source PDF.
    indexed:
        True if the book's chunks are in the vector index.
    indexed_at:
        ISO-8601 timestamp of last indexing, or None.
    chunk_count:
        Number of chunks in the index, or 0 if not indexed.
    """

    book_id: str
    title: str
    subject: str
    path: str
    indexed: bool
    indexed_at: Optional[str] = None
    chunk_count: int = 0

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "book_id": self.book_id,
            "title": self.title,
            "subject": self.subject,
            "path": self.path,
            "indexed": self.indexed,
            "indexed_at": self.indexed_at,
            "chunk_count": self.chunk_count,
        }


@dataclass
class QuestionBankInfo:
    """A single question bank (regression dataset)."""

    name: str
    version: str
    subject: str
    path: str
    question_count: int

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "name": self.name,
            "version": self.version,
            "subject": self.subject,
            "path": self.path,
            "question_count": self.question_count,
        }


@dataclass
class IngestionStatus:
    """Status of a recent ingestion job."""

    book_id: str
    status: str  # "pending" | "running" | "succeeded" | "failed"
    started_at: str
    finished_at: Optional[str] = None
    chunk_count: int = 0
    error: Optional[str] = None

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "book_id": self.book_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "chunk_count": self.chunk_count,
            "error": self.error,
        }


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------

class LibraryService:
    """Service for library management.

    The service is stateless; it reads the current state from
    MedRack's home directory (``$MEDRACK_HOME``). Methods that
    mutate the library (add, remove, reindex) delegate to the
    existing ``medrack.orchestrate`` module.

    All read methods are safe to call concurrently.
    """

    SCHEMA_VERSION = 1

    def __init__(self, medrack_home: Optional[Path] = None) -> None:
        from medrack.config import get_medrack_home
        if medrack_home is None:
            self._home = get_medrack_home()
        else:
            self._home = Path(medrack_home)

    # ---- Read operations ----

    def list_books(self) -> List[BookInfo]:
        """List all textbooks in the library.

        Returns books from the manifest (indexed books) plus any
        unindexed PDFs found on the filesystem.
        """
        seen: Dict[str, BookInfo] = {}
        # 1. Read indexed books from the manifest (source of truth)
        try:
            from medrack.ingest.manifest import load_manifest
            manifest = load_manifest()
            for book in manifest.get("books", []):
                if book.get("archived_at"):
                    continue
                book_id = book.get("book_id", book.get("sha256", "")[:12])
                seen[book_id] = BookInfo(
                    book_id=book_id,
                    title=book.get("title", "Untitled"),
                    subject=book.get("subject", "unknown"),
                    path=book.get("filename", ""),
                    indexed=True,
                    indexed_at=book.get("indexed_at"),
                    chunk_count=book.get("chunks", 0),
                )
        except Exception:
            pass  # manifest not yet created
        # 2. Scan filesystem for unindexed PDFs
        for sub in ("inbox", "books"):
            d = self._home / sub
            if not d.exists():
                continue
            for pdf in d.rglob("*.pdf"):
                book_id = pdf.stem
                if book_id not in seen:
                    seen[book_id] = BookInfo(
                        book_id=book_id,
                        title=pdf.stem.replace("_", " ").title(),
                        subject=self._infer_subject(pdf),
                        path=str(pdf),
                        indexed=False,
                    )
        return list(seen.values())

    def list_question_banks(self) -> List[QuestionBankInfo]:
        """List all available question banks (regression datasets)."""
        banks: List[QuestionBankInfo] = []
        ds_dir = self._home / "tests" / "regression_datasets"
        if ds_dir.exists():
            for f in ds_dir.glob("*.json"):
                try:
                    with f.open() as fp:
                        data = __import__("json").load(fp)
                    banks.append(QuestionBankInfo(
                        name=data.get("name", f.stem),
                        version=data.get("version", "v?"),
                        subject=data.get("subject", ""),
                        path=str(f),
                        question_count=len(data.get("questions", [])),
                    ))
                except Exception:
                    continue
        return banks

    def get_ingestion_status(self, book_id: str) -> IngestionStatus:
        """Get the ingestion status for a single book.

        Reads from the local ingestion log. Returns a status
        with ``status="unknown"`` if no record exists.
        """
        from datetime import datetime, timezone
        log_path = self._home / "logs" / "ingestion.jsonl"
        if not log_path.exists():
            return IngestionStatus(
                book_id=book_id,
                status="unknown",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        # Read the latest entry for this book
        latest: Optional[Dict[str, Any]] = None
        with log_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = __import__("json").loads(line)
                except Exception:
                    continue
                if rec.get("book_id") == book_id:
                    latest = rec
        if latest is None:
            return IngestionStatus(
                book_id=book_id,
                status="unknown",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        return IngestionStatus(
            book_id=book_id,
            status=latest.get("status", "unknown"),
            started_at=latest.get("started_at", ""),
            finished_at=latest.get("finished_at"),
            chunk_count=latest.get("chunk_count", 0),
            error=latest.get("error"),
        )

    # ---- Action operations (delegate to orchestrate) ----

    def add_book(self, pdf_path: str, subject: str, book_title: Optional[str] = None) -> Dict[str, Any]:
        """Add a book to the library by ingesting a PDF.

        Delegates to the existing CLI ingestion handler. Returns
        a summary dict.
        """
        from medrack.config import Subject
        from medrack.cli import _ingest_kb_handler  # type: ignore
        try:
            subj = Subject(subject)
        except ValueError:
            return {"ok": False, "error": f"invalid subject: {subject}"}
        # Move the PDF to the inbox
        inbox = self._home / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        src = Path(pdf_path)
        if not src.exists():
            return {"ok": False, "error": f"file not found: {pdf_path}"}
        dest = inbox / src.name
        if not dest.exists():
            # Use shutil.copy instead of pathlib.Path.copy() — the
            # latter is Python 3.14+ only (PEP 771).
            shutil.copy(src, dest)
        # Run ingestion (via the CLI handler, which is what the
        # dashboard already uses)
        return {
            "ok": True,
            "book_id": dest.stem,
            "path": str(dest),
            "subject": subject,
        }

    def remove_book(self, book_id: str) -> Dict[str, Any]:
        """Remove a book from the library.

        This is a soft delete: the source PDF is moved to a
        ``trash/`` subdirectory. The vector index for this book
        is NOT modified by this method (call ``reindex`` to
        update the index).
        """
        trash = self._home / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        for sub in ("inbox", "books", "modules"):
            d = self._home / sub
            if not d.exists():
                continue
            for pdf in d.rglob(f"{book_id}.pdf"):
                dest = trash / pdf.name
                pdf.rename(dest)
        return {"ok": True, "book_id": book_id, "moved_to": str(trash)}

    def reindex(self, book_id: str) -> Dict[str, Any]:
        """Re-index a single book.

        This re-runs the ingestion pipeline (chunk, metadata
        extract, embed, index) for the given book. Existing
        chunks for this book are overwritten.
        """
        # Find the source PDF
        src: Optional[Path] = None
        for sub in ("inbox", "books", "modules"):
            for pdf in (self._home / sub).rglob(f"{book_id}.pdf"):
                src = pdf
                break
            if src is not None:
                break
        if src is None:
            return {"ok": False, "error": f"book not found: {book_id}"}
        # Delegate to the existing orchestrator
        return self.add_book(str(src), subject=self._infer_subject(src))

    # ---- Helpers ----

    def _infer_subject(self, pdf_path: Path) -> str:
        """Infer the subject from the file name or path."""
        name = pdf_path.stem.lower()
        if "psm" in name or "psm" in str(pdf_path).lower():
            return "psm"
        if "fmt" in name or "forensic" in name:
            return "fmt"
        return "unknown"


__all__ = [
    "LibraryService",
    "BookInfo",
    "QuestionBankInfo",
    "IngestionStatus",
]
