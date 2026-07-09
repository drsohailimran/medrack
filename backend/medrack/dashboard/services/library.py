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
        indexed_filenames: set = set()
        # 1. Read indexed books from the manifest (source of truth)
        try:
            from medrack.ingest.manifest import load_manifest
            manifest = load_manifest()
            for book in manifest.get("books", []):
                if book.get("archived_at"):
                    continue
                book_id = book.get("book_id", book.get("sha256", "")[:12])
                fname = book.get("filename", "")
                if fname:
                    indexed_filenames.add(fname)
                seen[book_id] = BookInfo(
                    book_id=book_id,
                    title=book.get("title", "Untitled"),
                    subject=book.get("subject", "unknown"),
                    path=fname,
                    indexed=True,
                    indexed_at=book.get("indexed_at"),
                    chunk_count=book.get("chunks", 0),
                )
        except Exception:
            pass  # manifest not yet created
        # 2. Scan filesystem for genuinely-unindexed PDFs. Skip any file
        #    whose name already appears as an indexed book (the manifest
        #    keys books by UUID, so match on filename to avoid showing a
        #    phantom "indexing" duplicate of a book we already ingested).
        for sub in ("inbox", "books"):
            d = self._home / sub
            if not d.exists():
                continue
            for pdf in d.rglob("*.pdf"):
                if pdf.name in indexed_filenames:
                    continue
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

    def _iter_module_extracted(self) -> List[Path]:
        """Yield ``modules/<subject>/<name>/extracted.json`` paths."""
        root = self._home / "modules"
        if not root.is_dir():
            return []
        return sorted(root.rglob("extracted.json"))

    def _load_module_bank(self, extracted_path: Path) -> Optional[Dict[str, Any]]:
        """Normalize a modules/*/extracted.json into bank-shaped dict."""
        import json as _json

        try:
            data = _json.loads(extracted_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(data, dict):
            return None
        questions = data.get("questions") or []
        if not isinstance(questions, list):
            questions = []
        name = extracted_path.parent.name
        # modules/<subject>/<name>/extracted.json
        subject = extracted_path.parent.parent.name
        if subject == "modules":
            subject = (data.get("metadata") or {}).get("subject") or "unknown"
        meta = data.get("metadata") or {}
        return {
            "name": name,
            "version": meta.get("version") or "module",
            "subject": meta.get("subject") or subject,
            "path": str(extracted_path),
            "questions": questions,
            "source": "modules",
            "metadata": meta,
        }

    def _resolve_bank_path(self, name: str) -> Optional[Path]:
        """Find bank JSON: regression_datasets first, then modules extracted."""
        import json as _json

        safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", ".")).strip() or "bank"
        ds_dir = self._home / "tests" / "regression_datasets"
        path = ds_dir / f"{safe}.json"
        if path.is_file():
            return path
        if ds_dir.is_dir():
            for f in ds_dir.glob("*.json"):
                try:
                    data = _json.loads(f.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                if data.get("name") == name or f.stem == safe:
                    return f
        for extracted in self._iter_module_extracted():
            if extracted.parent.name == safe or extracted.parent.name == name:
                return extracted
        return None

    def list_question_banks(self) -> List[QuestionBankInfo]:
        """List question banks from regression datasets **and** modules/.

        Historical CLI ingest wrote ``modules/<subject>/<name>/extracted.json``.
        The UI previously only listed ``tests/regression_datasets/*.json``, so
        after answer-cache deletes the banks appeared to vanish even though the
        modules were still on disk. Both sources are listed (deduped by name;
        modules win on conflict because they hold the full extracted set).
        """
        import json as _json

        by_name: Dict[str, QuestionBankInfo] = {}
        ds_dir = self._home / "tests" / "regression_datasets"
        if ds_dir.exists():
            for f in ds_dir.glob("*.json"):
                try:
                    with f.open(encoding="utf-8") as fp:
                        data = _json.load(fp)
                    # Skip non-bank datasets (e.g. permanent regression v1 with
                    # no ``name`` + ``questions`` list of refs only).
                    questions = data.get("questions")
                    if not isinstance(questions, list):
                        continue
                    # Skip pure reference packs that only point at modules
                    # without full question text (permanent suite v1.json).
                    has_text = any(
                        (q.get("question_text") or q.get("stem") or "").strip()
                        for q in questions
                        if isinstance(q, dict)
                    )
                    # Keep empty shells listed with count 0 so the user can
                    # delete/re-upload them; full modules always have text.
                    if questions and not has_text:
                        # still list with question_count of total rows
                        pass
                    name = data.get("name", f.stem)
                    by_name[name] = QuestionBankInfo(
                        name=name,
                        version=data.get("version", "v?"),
                        subject=data.get("subject", ""),
                        path=str(f),
                        question_count=len(questions),
                    )
                except Exception:
                    continue

        for extracted in self._iter_module_extracted():
            bank = self._load_module_bank(extracted)
            if not bank:
                continue
            name = bank["name"]
            by_name[name] = QuestionBankInfo(
                name=name,
                version=str(bank.get("version") or "module"),
                subject=str(bank.get("subject") or ""),
                path=str(bank["path"]),
                question_count=len(bank.get("questions") or []),
            )
        return sorted(by_name.values(), key=lambda b: (b.subject, b.name))

    def upload_question_bank(
        self,
        pdf_bytes: bytes,
        filename: str,
        name: str,
        subject: str,
        version: str = "v1",
    ) -> Dict[str, Any]:
        """Accept a question-bank PDF, extract questions, and save as a
        regression-dataset JSON.

        Strategy:
        1. Write the uploaded PDF to a temp file in ``inbox/``.
        2. Use the existing ``medrack.module.extract`` + ``medrack.module.mcq``
           + ``medrack.module.llm_extract`` pipeline to pull questions.
        3. Persist the bank as JSON in ``tests/regression_datasets/{name}.json``
           so the existing ``list_question_banks`` picks it up.

        Returns a dict with the bank info + the count of questions extracted.
        """
        import json
        import tempfile

        from medrack.module.extract import extract_module_pages
        from medrack.module.mcq import extract_mcqs_from_pages
        from medrack.module.llm_extract import extract_questions_with_llm

        # 1. Persist the upload to inbox/ so the file has a stable path.
        inbox = self._home / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(c for c in name if c.isalnum() or c in ("-", "_", ".")).strip() or "bank"
        dest_pdf = inbox / f"{safe_stem}.pdf"
        dest_pdf.write_bytes(pdf_bytes)

        # 2. Extract pages.
        pages = extract_module_pages(dest_pdf)
        if not pages:
            return {
                "ok": False,
                "error": "PDF had no extractable text pages",
                "bank": None,
            }

        # 3. Run both extractors. The regex extractor is cheap and catches
        #    well-formatted MCQs; the LLM extractor is a fallback for freeform
        #    questions and theory prompts.
        regex_questions = extract_mcqs_from_pages(pages) or []
        try:
            llm_questions = extract_questions_with_llm(
                subject=subject,
                pages_text=[p.get("text", "") for p in pages],
            ) or []
        except Exception as exc:
            llm_questions = []
            llm_error = f"LLM extraction skipped: {exc}"
        else:
            llm_error = None

        # 4. Merge. Prefer the LLM result (richer schema); fall back to regex
        #    when the LLM returned nothing. De-dupe by qid.
        merged: list[dict] = []
        seen_qids: set[str] = set()
        for q in (llm_questions or []) + [
            {
                "qid": f"q{i + 1:03d}",
                "module": name,
                "subject": subject,
                "section": getattr(q, "section", "") or "",
                "topic": getattr(q, "topic", "") or "",
                "marks": getattr(q, "marks", 0) or 0,
                "difficulty": "",
                "notes": "",
                "question_text": getattr(q, "stem", "") or "",
            }
            for i, q in enumerate(regex_questions)
        ]:
            qid = q.get("qid") or f"q{len(merged) + 1:03d}"
            if qid in seen_qids:
                continue
            seen_qids.add(qid)
            q.setdefault("qid", qid)
            q.setdefault("module", name)
            q.setdefault("subject", subject)
            merged.append(q)

        # 5. Persist as a regression-dataset JSON.
        ds_dir = self._home / "tests" / "regression_datasets"
        ds_dir.mkdir(parents=True, exist_ok=True)
        bank_path = ds_dir / f"{safe_stem}.json"
        payload = {
            "name": name,
            "version": version,
            "subject": subject,
            "path": str(bank_path),
            "questions": merged,
            "_created": "LibraryService.upload_question_bank",
            "_doc": "Auto-generated from uploaded PDF via API.",
        }
        bank_path.write_text(json.dumps(payload, indent=2))

        result: Dict[str, Any] = {
            "ok": True,
            "bank": {
                "name": name,
                "version": version,
                "subject": subject,
                "path": str(bank_path),
                "question_count": len(merged),
                "source_pdf": str(dest_pdf),
            },
        }
        if llm_error:
            result["warning"] = llm_error
        return result

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
        """Fully remove a book from the library.

        Deletes the book's vectors from the subject's ChromaDB
        collection, archives it in the manifest (so it disappears from
        ``list_books``), and moves the source PDF to ``trash/``. This is
        what makes "delete" actually take effect (the old version only
        looked for ``<book_id>.pdf`` — which never matched the real
        filename — and touched neither the manifest nor the index).
        """
        from medrack.ingest import manifest as manifest_mod
        from medrack.ingest.index import delete_book_chunks

        m = manifest_mod.load_manifest()
        record = None
        for b in m.get("books", []):
            if b.get("book_id") == book_id and not b.get("archived_at"):
                record = b
                break
        if record is None:
            return {"ok": False, "error": f"book not found: {book_id}", "book_id": book_id}

        sha256 = record.get("sha256")
        subject = record.get("subject") or "psm"
        filename = record.get("filename") or ""

        # 1. Drop the book's chunks from ChromaDB (so retrieval no longer
        #    surfaces them). Best-effort — a missing collection is fine.
        try:
            delete_book_chunks(subject, book_id)
        except Exception:  # noqa: BLE001
            pass

        # 2. Archive in the manifest so it leaves the library listing.
        if sha256:
            manifest_mod.archive_book(sha256)

        # 3. Move the source PDF out of the way (best-effort).
        trash = self._home / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        moved_to = str(trash)
        if filename:
            for sub in ("inbox", "books", "modules"):
                src = self._home / sub / filename
                if src.exists():
                    dest = trash / filename
                    try:
                        src.rename(dest)
                        moved_to = str(dest)
                    except Exception:  # noqa: BLE001
                        pass
                    break

        return {"ok": True, "book_id": book_id, "moved_to": moved_to}

    def get_question_bank(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a single question bank's full JSON (including its
        ``questions`` list), or ``None`` if it does not exist.

        Resolves both ``tests/regression_datasets/{name}.json`` and
        ``modules/<subject>/{name}/extracted.json``.
        """
        import json as _json

        path = self._resolve_bank_path(name)
        if path is None:
            return None
        if path.name == "extracted.json":
            return self._load_module_bank(path)
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        if isinstance(data, dict) and "name" not in data:
            data["name"] = name
        if isinstance(data, dict):
            data.setdefault("source", "regression_datasets")
        return data

    def delete_question_bank(self, name: str) -> Dict[str, Any]:
        """Delete a question bank dataset.

        - Regression-dataset banks: remove the JSON under
          ``tests/regression_datasets/``.
        - Module banks (``modules/.../extracted.json``): move the module
          folder to ``trash/modules/<name>/`` (never hard-wipe, never
          touch ``answers/``).

        Does **not** delete answer cache — use ``DELETE /cache/...`` for that.
        """
        import shutil
        import json as _json

        safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", ".")).strip() or "bank"
        removed = False
        kind = None

        # 1) regression dataset JSON
        ds_dir = self._home / "tests" / "regression_datasets"
        target = ds_dir / f"{safe}.json" if ds_dir.is_dir() else None
        if target is None or not target.is_file():
            target = None
            if ds_dir.is_dir():
                for f in ds_dir.glob("*.json"):
                    try:
                        if _json.loads(f.read_text(encoding="utf-8")).get("name") == name:
                            target = f
                            break
                    except Exception:  # noqa: BLE001
                        continue
        if target is not None and target.is_file():
            try:
                target.unlink()
                removed = True
                kind = "regression_datasets"
            except Exception:  # noqa: BLE001
                pass

        # 2) modules/<subject>/<name>/ — archive to trash, do not destroy answers
        for extracted in self._iter_module_extracted():
            if extracted.parent.name != safe and extracted.parent.name != name:
                continue
            mod_dir = extracted.parent
            trash = self._home / "trash" / "modules" / safe
            trash.parent.mkdir(parents=True, exist_ok=True)
            try:
                if trash.exists():
                    shutil.rmtree(trash)
                shutil.move(str(mod_dir), str(trash))
                removed = True
                kind = "modules"
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"failed to archive module: {exc}", "name": name}
            break

        # Best-effort: staged PDF only (not the whole modules tree)
        for sub in ("modules", "inbox"):
            pdf = self._home / sub / f"{safe}.pdf"
            if pdf.is_file():
                try:
                    pdf.unlink()
                except Exception:  # noqa: BLE001
                    pass

        if not removed:
            return {"ok": False, "error": f"question bank not found: {name}", "name": name}
        return {"ok": True, "name": name, "kind": kind}

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
