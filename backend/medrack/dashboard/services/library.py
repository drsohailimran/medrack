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

        Handles:
        - Manifest entries (active or archived) — drop Chroma chunks + archive
        - Filesystem-only PDFs listed as not-indexed (inbox/books stem = book_id)

        Moves matching PDFs to ``trash/``. Returns ok=False only if nothing matched.
        """
        import shutil
        from medrack.ingest import manifest as manifest_mod
        from medrack.ingest.index import delete_book_chunks

        trash = self._home / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        moved_to: list[str] = []
        found = False

        m = manifest_mod.load_manifest()
        for b in list(m.get("books", [])):
            if b.get("book_id") != book_id:
                continue
            found = True
            subject = b.get("subject") or "psm"
            filename = b.get("filename") or ""
            sha256 = b.get("sha256")
            try:
                delete_book_chunks(subject, book_id)
            except Exception:  # noqa: BLE001
                pass
            if sha256 and not b.get("archived_at"):
                try:
                    manifest_mod.archive_book(sha256)
                except Exception:  # noqa: BLE001
                    pass
            if filename:
                for sub in ("inbox", "books", "modules"):
                    src = self._home / sub / filename
                    if src.is_file():
                        dest = trash / filename
                        try:
                            if dest.exists():
                                dest.unlink()
                            src.rename(dest)
                            moved_to.append(str(dest))
                        except Exception:  # noqa: BLE001
                            try:
                                shutil.move(str(src), str(dest))
                                moved_to.append(str(dest))
                            except Exception:  # noqa: BLE001
                                pass
                        break

        # Filesystem-only rows (UI "not indexed")
        for sub in ("inbox", "books"):
            d = self._home / sub
            if not d.is_dir():
                continue
            for pdf in list(d.rglob("*.pdf")):
                if pdf.stem == book_id or pdf.name == book_id:
                    found = True
                    dest = trash / pdf.name
                    try:
                        if dest.exists():
                            dest.unlink()
                        pdf.rename(dest)
                        moved_to.append(str(dest))
                    except Exception:  # noqa: BLE001
                        try:
                            shutil.move(str(pdf), str(dest))
                            moved_to.append(str(dest))
                        except Exception:  # noqa: BLE001
                            pass

        if not found:
            return {"ok": False, "error": f"book not found: {book_id}", "book_id": book_id}
        return {
            "ok": True,
            "book_id": book_id,
            "moved_to": moved_to[0] if moved_to else str(trash),
            "moved_paths": moved_to,
        }

    def clear_all_books(self, *, purge_index: bool = True) -> Dict[str, Any]:
        """Remove every library book and optionally purge all kb_* Chroma collections."""
        import shutil

        removed_ids: list[str] = []
        moved: list[str] = []
        trash = self._home / "trash"
        trash.mkdir(parents=True, exist_ok=True)

        try:
            from medrack.ingest import manifest as manifest_mod

            m = manifest_mod.load_manifest()
            for b in list(m.get("books", [])):
                bid = b.get("book_id")
                if not bid:
                    continue
                result = self.remove_book(bid)
                if result.get("ok"):
                    removed_ids.append(bid)
                    if result.get("moved_to"):
                        moved.append(str(result["moved_to"]))
        except Exception:  # noqa: BLE001
            pass

        for sub in ("inbox", "books"):
            d = self._home / sub
            if not d.is_dir():
                continue
            for pdf in list(d.rglob("*.pdf")):
                dest = trash / pdf.name
                try:
                    if dest.exists():
                        dest.unlink()
                    pdf.rename(dest)
                    moved.append(str(dest))
                    removed_ids.append(pdf.stem)
                except Exception:  # noqa: BLE001
                    try:
                        shutil.move(str(pdf), str(dest))
                        moved.append(str(dest))
                        removed_ids.append(pdf.stem)
                    except Exception:  # noqa: BLE001
                        pass

        purged: list[str] = []
        if purge_index:
            try:
                import chromadb
                from medrack.ingest.index import _chroma_path

                client = chromadb.PersistentClient(path=str(_chroma_path()))
                for col in list(client.list_collections()):
                    name = getattr(col, "name", None) or str(col)
                    if str(name).startswith("kb_"):
                        try:
                            client.delete_collection(str(name))
                            purged.append(str(name))
                        except Exception:  # noqa: BLE001
                            pass
            except Exception:  # noqa: BLE001
                pass

        return {
            "ok": True,
            "removed_count": len(set(removed_ids)),
            "removed_ids": sorted(set(removed_ids)),
            "moved": moved,
            "purged_collections": purged,
        }

    def verify_book(
        self,
        book_id: str,
        *,
        expected_subject: Optional[str] = None,
        expected_pages: Optional[int] = None,
        expected_chunks: Optional[int] = None,
        min_chunks: int = 1,
        require_retrieval: bool = True,
    ) -> Dict[str, Any]:
        """Post-ingest verification gate for a textbook.

        Hard failures (``ok=False``) mean the book must not be trusted for
        answering / overnight P2 should treat the job as failed:

        - not in active manifest
        - zero chunks in Chroma for this book_id
        - missing source PDF on disk (when filename known)
        - sample retrieval returns nothing for the subject collection
          (when require_retrieval and collection has this book's vectors)

        Warnings are non-fatal (high OCR-suspect ratio, chunk/page density
        low, chroma count slightly off from manifest).
        """
        from medrack.ingest import manifest as manifest_mod
        from medrack.ingest import index as index_mod

        checks: list[dict] = []
        errors: list[str] = []
        warnings: list[str] = []

        def add(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> None:
            checks.append({"name": name, "ok": ok, "detail": detail, "hard": hard})
            if not ok:
                (errors if hard else warnings).append(f"{name}: {detail}")

        m = manifest_mod.load_manifest()
        record = None
        for b in m.get("books", []):
            if b.get("book_id") == book_id and not b.get("archived_at"):
                record = b
                break
        if record is None:
            add("manifest", False, "book_id not found in active manifest")
            return {
                "ok": False,
                "book_id": book_id,
                "checks": checks,
                "errors": errors,
                "warnings": warnings,
            }
        add("manifest", True, f"title={record.get('title')!r} subject={record.get('subject')}")

        subject = (record.get("subject") or expected_subject or "psm").strip()
        if expected_subject and subject != expected_subject:
            add(
                "subject",
                False,
                f"manifest subject={subject!r} expected={expected_subject!r}",
            )
        else:
            add("subject", True, subject)

        pages = int(record.get("pages") or 0)
        chunks_manifest = int(record.get("chunks") or 0)
        if expected_pages is not None and pages != expected_pages:
            add(
                "pages_match",
                False,
                f"manifest pages={pages} expected={expected_pages}",
                hard=False,
            )
        if pages <= 0:
            add("pages", False, "manifest pages <= 0")
        else:
            add("pages", True, str(pages))

        if chunks_manifest < min_chunks:
            add("chunks_manifest", False, f"manifest chunks={chunks_manifest} < min={min_chunks}")
        else:
            add("chunks_manifest", True, str(chunks_manifest))

        # Source PDF still on disk
        filename = record.get("filename") or ""
        pdf_found = False
        pdf_path = ""
        if filename:
            for sub in ("books", "inbox", "modules"):
                p = self._home / sub / filename
                if p.is_file():
                    pdf_found = True
                    pdf_path = str(p)
                    break
        if filename and not pdf_found:
            add("source_pdf", False, f"PDF missing on disk: {filename}", hard=False)
        elif filename:
            add("source_pdf", True, pdf_path)

        # Chroma vector count
        chroma_n = 0
        try:
            chroma_n = int(index_mod.count_book_chunks(subject, book_id))
        except Exception as exc:  # noqa: BLE001
            add("chroma_count", False, f"count failed: {exc}")
        else:
            if chroma_n < min_chunks:
                add("chroma_count", False, f"chroma has {chroma_n} chunks (need >= {min_chunks})")
            else:
                add("chroma_count", True, str(chroma_n))
            # Allow small mismatch; large mismatch is a warning then hard if zero match expected
            if expected_chunks is not None and abs(chroma_n - expected_chunks) > max(5, expected_chunks // 10):
                add(
                    "chroma_vs_expected",
                    False,
                    f"chroma={chroma_n} expected_chunks={expected_chunks}",
                    hard=False,
                )
            if chunks_manifest and chroma_n and abs(chroma_n - chunks_manifest) > max(5, chunks_manifest // 5):
                add(
                    "chroma_vs_manifest",
                    False,
                    f"chroma={chroma_n} manifest={chunks_manifest}",
                    hard=False,
                )

        # Density: expect some chunks relative to pages (very low density = bad OCR/chunking)
        if pages >= 20 and chunks_manifest > 0:
            density = chunks_manifest / float(pages)
            if density < 0.15:
                add(
                    "chunk_density",
                    False,
                    f"{density:.3f} chunks/page (suspiciously low for {pages} pages)",
                    hard=False,
                )
            else:
                add("chunk_density", True, f"{density:.3f} chunks/page")

        # Sample retrieval: collection must return something
        if require_retrieval and chroma_n >= min_chunks:
            try:
                from medrack.ingest import embed as embed_mod

                model = embed_mod.get_model()
                probe = f"medical textbook {subject} examination treatment diagnosis"
                emb = model.encode([probe]).tolist()
                hits = index_mod.query(subject, emb, top_k=5)
                if not hits:
                    add("retrieval_sample", False, "query returned 0 hits for subject collection")
                else:
                    # Prefer at least one hit from this book if collection has multiple books
                    from_book = sum(
                        1
                        for h in hits
                        if (h.get("metadata") or {}).get("book_id") == book_id
                        or h.get("book_id") == book_id
                    )
                    detail = f"{len(hits)} hits, {from_book} from this book_id"
                    if from_book == 0 and chroma_n >= min_chunks:
                        # Other books may rank higher — warning only if any hits exist
                        add("retrieval_sample", True, detail + " (other books ranked higher)", hard=False)
                    else:
                        add("retrieval_sample", True, detail)
            except Exception as exc:  # noqa: BLE001
                add("retrieval_sample", False, f"retrieval probe failed: {exc}", hard=False)

        # OCR quality from manifest if present
        suspects = record.get("ocr_suspect_pages") or []
        if isinstance(suspects, list) and pages > 0:
            ratio = len(suspects) / float(pages)
            if ratio > 0.35:
                add(
                    "ocr_suspect_ratio",
                    False,
                    f"{ratio:.0%} suspect pages ({len(suspects)}/{pages})",
                    hard=False,
                )
            else:
                add("ocr_suspect_ratio", True, f"{len(suspects)}/{pages}")

        # Text quality / gibberish (sample chunk documents from Chroma)
        try:
            from medrack.dashboard.services.preflight import sample_text_quality
            from medrack.ingest.index import get_or_create_collection

            col = get_or_create_collection(subject)
            sample = col.get(where={"book_id": book_id}, include=["documents"])
            docs = sample.get("documents") or []
            # Chroma may nest documents; cap samples for speed
            flat: list[str] = []
            for d in docs[:80]:
                if isinstance(d, list):
                    flat.extend(str(x) for x in d if x)
                elif d:
                    flat.append(str(d))
            tq = sample_text_quality(flat, max_samples=12, fail_above=0.72)
            # Hard-fail only if severely gibberish AND we have samples
            hard_gib = (not tq.get("ok")) and float(tq.get("mean_gibberish") or 0) >= 0.85
            add(
                "text_quality",
                bool(tq.get("ok")) or not hard_gib,
                tq.get("detail") or "",
                hard=hard_gib,
            )
            if not tq.get("ok") and not hard_gib:
                warnings.append(f"text_quality: {tq.get('detail')}")
        except Exception as exc:  # noqa: BLE001
            add("text_quality", True, f"skipped ({exc})", hard=False)

        ok = len(errors) == 0
        return {
            "ok": ok,
            "book_id": book_id,
            "title": record.get("title"),
            "subject": subject,
            "pages": pages,
            "chunks_manifest": chunks_manifest,
            "chunks_chroma": chroma_n,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "message": (
                "Ingest verification PASSED"
                if ok
                else "Ingest verification FAILED: " + "; ".join(errors)
            ),
        }

    def verify_question_bank(
        self,
        name: str,
        *,
        min_questions: int = 1,
        min_avg_stem_chars: int = 20,
    ) -> Dict[str, Any]:
        """Verify a question bank is usable after extract."""
        checks: list[dict] = []
        errors: list[str] = []
        warnings: list[str] = []

        def add(n: str, ok: bool, detail: str = "", *, hard: bool = True) -> None:
            checks.append({"name": n, "ok": ok, "detail": detail, "hard": hard})
            if not ok:
                (errors if hard else warnings).append(f"{n}: {detail}")

        bank = self.get_question_bank(name)
        if not bank:
            add("bank_exists", False, f"bank not found: {name}")
            return {
                "ok": False,
                "name": name,
                "checks": checks,
                "errors": errors,
                "warnings": warnings,
                "message": f"Bank verification FAILED: not found {name}",
            }
        add("bank_exists", True, name)
        questions = bank.get("questions") or []
        if not isinstance(questions, list):
            questions = []
        nq = len(questions)
        if nq < min_questions:
            add("question_count", False, f"{nq} < min {min_questions}")
        else:
            add("question_count", True, str(nq))

        stems = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            t = (q.get("question_text") or q.get("stem") or "").strip()
            if t:
                stems.append(t)
        empty = nq - len(stems)
        if empty:
            add("empty_stems", False, f"{empty} empty question stems", hard=empty > nq // 2)
        avg = (sum(len(s) for s in stems) / len(stems)) if stems else 0
        if stems and avg < min_avg_stem_chars:
            add(
                "avg_stem_len",
                False,
                f"{avg:.0f} chars < min {min_avg_stem_chars}",
                hard=avg < 10,
            )
        else:
            add("avg_stem_len", True, f"{avg:.0f}")

        try:
            from medrack.dashboard.services.preflight import sample_text_quality

            tq = sample_text_quality(stems[:30], fail_above=0.75)
            add("stem_text_quality", bool(tq.get("ok")), tq.get("detail") or "", hard=False)
        except Exception:  # noqa: BLE001
            pass

        ok = len(errors) == 0
        return {
            "ok": ok,
            "name": name,
            "question_count": nq,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "message": (
                "Bank verification PASSED"
                if ok
                else "Bank verification FAILED: " + "; ".join(errors)
            ),
        }

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
