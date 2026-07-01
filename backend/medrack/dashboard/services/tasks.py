"""Background task bodies for the async API jobs (Phase 13).

Each function here is a job body run by ``medrack.dashboard.jobs.registry``
on a daemon thread. They receive ``(job, progress)`` and call
``progress(percent, message)`` frequently so the frontend progress bar
moves smoothly (2-decimal precision). They reuse the existing, tested
pipeline functions rather than reimplementing them.

Jobs:
  - run_ingest_book:  upload PDF -> full KB ingest (extract/chunk/embed/index)
  - run_extract_bank: upload question-bank PDF -> extract questions -> JSON
  - run_solve_bank:   generate answers for every question -> one solved PDF
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from medrack.utils.logger import get_logger

logger = get_logger(__name__)

Progress = Callable[[float, str], None]

_OCR_FALLBACK_CHAR_THRESHOLD = 100


def _safe_stem(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_", ".")).strip() or "bank"


def _total_pages(pdf: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(pdf)).pages)
    except Exception:  # noqa: BLE001
        return 0


def _extract_pages_with_progress(
    pdf: Path, progress: Progress, lo: float, hi: float
) -> List[dict]:
    """T2/T3 hybrid extraction (text, OCR fallback) with per-page progress.

    Mirrors ``medrack.orchestrate._extract_pages`` but reports progress in
    the ``[lo, hi]`` percentage band as pages are processed.
    """
    from medrack.ingest import ocr as ocr_mod
    from medrack.ingest import text_extract as text_extract_mod

    total = _total_pages(pdf)
    pages: List[dict] = []
    span = max(hi - lo, 0.0)
    for i, text_page in enumerate(text_extract_mod.extract_text_pages(pdf)):
        if text_page["char_count"] >= _OCR_FALLBACK_CHAR_THRESHOLD:
            pages.append(text_page)
        else:
            try:
                ocr_page = ocr_mod.ocr_page(pdf, page_num=text_page["page_num"])
                pages.append(
                    ocr_page
                    if ocr_page["char_count"] > text_page["char_count"]
                    else text_page
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("OCR fallback failed on page %d: %s", text_page["page_num"], exc)
                pages.append(text_page)
        if total:
            progress(lo + span * ((i + 1) / total), f"Reading page {i + 1}/{total}")
    return pages


# ---------------------------------------------------------------------------
# Job: ingest a book into the KB
# ---------------------------------------------------------------------------

def run_ingest_book(
    job, progress: Progress, *, pdf_path: str, subject: str, title: str, replace: bool = False
) -> Dict[str, Any]:
    from medrack import config
    from medrack.ingest import chapter as chapter_mod
    from medrack.ingest import chunk as chunk_mod
    from medrack.ingest import clean as clean_mod
    from medrack.ingest import embed as embed_mod
    from medrack.ingest import format_detect
    from medrack.ingest import index as index_mod
    from medrack.ingest import manifest
    from medrack.ingest import quality as quality_mod
    from medrack.ingest.extractors import RegexMetadataExtractor

    pdf = Path(pdf_path).expanduser()
    if not pdf.is_file():
        raise FileNotFoundError(f"uploaded file not found: {pdf}")
    subj = config.Subject.from_str(subject)
    book_id = str(uuid.uuid4())

    progress(2, "Hashing PDF")
    sha256 = hashlib.sha256(pdf.read_bytes()).hexdigest()
    existing = manifest.get_book(sha256)
    if existing is not None and not existing.get("archived_at"):
        if not replace:
            raise ValueError(
                "This book is already in the knowledge base. "
                "Enable 'Replace' to archive the old copy and re-ingest."
            )
        manifest.archive_book(sha256)

    progress(4, "Detecting format")
    format_detect.detect_format(pdf, sample_pages=5)

    pages = _extract_pages_with_progress(pdf, progress, 5.0, 45.0)
    ocr_pages_count = sum(1 for p in pages if p.get("method") == "ocr")

    progress(46, "Cleaning text")
    cleaned = clean_mod.clean_pages(pages)
    progress(48, "Segmenting chapters")
    chapters = chapter_mod.segment_chapters(cleaned, book_title=title)
    progress(50, "Chunking")
    chunks = chunk_mod.chunk_pages(
        cleaned, chapters, subject=subj.value, book_id=book_id, extractor=RegexMetadataExtractor()
    )
    total_chunks = len(chunks)
    if total_chunks == 0:
        raise ValueError("No text could be extracted from this PDF (0 chunks).")

    # Embed in batches so the (dominant) embedding phase reports smooth progress.
    batch = 64
    for i in range(0, total_chunks, batch):
        embed_mod.embed_chunks(chunks[i : i + batch])
        done = min(i + batch, total_chunks)
        progress(50 + 40 * (done / total_chunks), f"Embedding {done}/{total_chunks} chunks")

    progress(92, f"Indexing into kb_{subj.value}")
    index_mod.index_chunks(chunks, subject=subj.value)

    progress(96, "Quality gate")
    quality_report = quality_mod.check_ocr_quality(cleaned)

    book_record = {
        "book_id": book_id,
        "subject": subj.value,
        "title": title,
        "filename": pdf.name,
        "sha256": sha256,
        "pages": len(cleaned),
        "chunks": total_chunks,
        "embedding_model": config.EMBEDDING_MODEL,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "replaced_by": None,
        "archived_at": None,
        "ocr_pages": ocr_pages_count,
        "ocr_suspect_pages": quality_report.suspect_pages,
    }
    manifest.add_book(book_record)
    progress(100, "Ingested")
    return {
        "book_id": book_id,
        "subject": subj.value,
        "title": title,
        "pages": len(cleaned),
        "chunks": total_chunks,
        "ocr_pages": ocr_pages_count,
        "suspect_pages": len(quality_report.suspect_pages),
    }


# ---------------------------------------------------------------------------
# Job: extract a question bank from a PDF
# ---------------------------------------------------------------------------

class _StrLLM:
    """Adapter so ``extract_questions_with_llm`` (which expects
    ``complete(prompt) -> str``) works with the real client whose
    ``complete`` returns an ``LLMResponse``."""

    def __init__(self, client: Any) -> None:
        self._c = client

    def complete(self, prompt: str, max_output_tokens: int | None = None) -> str:
        r = self._c.complete(prompt, max_output_tokens=max_output_tokens)
        return getattr(r, "text", r)


def _merge_questions(llm_questions: list, regex_questions: list, name: str, subject: str) -> List[dict]:
    combined: List[dict] = list(llm_questions or []) + [
        {
            "section": getattr(q, "section", "") or "",
            "topic": getattr(q, "topic", "") or "",
            "marks": getattr(q, "marks", 0) or 0,
            "difficulty": "",
            "notes": "",
            "question_text": getattr(q, "stem", "") or "",
            "options": getattr(q, "options", {}) or {},
            "type": "mcq" if (getattr(q, "options", None)) else "theory",
        }
        for q in (regex_questions or [])
    ]
    merged: List[dict] = []
    seen: set[str] = set()
    for q in combined:
        qt = (q.get("question_text") or "").strip()
        if not qt:
            continue
        # De-duplicate across the LLM and regex sources (and within each)
        # by full normalised question text so the same question isn't
        # counted twice. LLM questions come first, so they win on a
        # collision. Full text (not a prefix) avoids merging distinct
        # questions that share a long opening phrase.
        key = " ".join(qt.lower().split())
        if key in seen:
            continue
        seen.add(key)
        merged.append(q)
    # Assign clean, unique, sequential qids namespaced to the bank.
    for i, q in enumerate(merged):
        q["qid"] = f"{_safe_stem(name)}::q{i + 1:03d}"
        q.setdefault("module", name)
        q.setdefault("subject", subject)
        q.setdefault("type", "theory")
    return merged


def run_extract_bank(
    job, progress: Progress, *, pdf_bytes: bytes, filename: str, name: str, subject: str, version: str = "v1"
) -> Dict[str, Any]:
    from medrack import config
    from medrack.ingest import clean as clean_mod
    from medrack.module.llm_extract import extract_questions_with_llm
    from medrack.module.mcq import extract_mcqs_from_pages
    from medrack.state import get_llm_client

    home = config.get_medrack_home()
    # Save question-bank PDFs under modules/ (not inbox/), so they are not
    # mistaken for un-indexed *books* by LibraryService.list_books.
    modules_dir = home / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_stem(name)
    dest = modules_dir / f"{safe}.pdf"
    progress(2, "Saving upload")
    dest.write_bytes(pdf_bytes)

    raw_pages = _extract_pages_with_progress(dest, progress, 4.0, 70.0)
    pages = clean_mod.clean_pages(raw_pages)
    if not pages:
        raise ValueError("The PDF had no extractable text pages.")

    progress(74, "Extracting questions (patterns)")
    regex_questions = extract_mcqs_from_pages(pages) or []

    progress(80, "Extracting questions (LLM)")
    llm_questions: list = []
    warning: Optional[str] = None

    def _llm_progress(i: int, n: int) -> None:
        # Map batch progress across the 80-93% band.
        pct = 80 + int(13 * i / max(n, 1))
        progress(min(pct, 93), f"Extracting questions (LLM) — batch {i}/{n}")

    try:
        llm_questions = extract_questions_with_llm(
            pages_text=[p.get("text", "") for p in pages],
            subject=subject,
            llm_client=_StrLLM(get_llm_client()),
            progress_cb=_llm_progress,
        ) or []
    except Exception as exc:  # noqa: BLE001
        warning = f"LLM question extraction skipped: {exc}"

    merged = _merge_questions(llm_questions, regex_questions, name, subject)

    progress(94, "Saving question bank")
    ds_dir = home / "tests" / "regression_datasets"
    ds_dir.mkdir(parents=True, exist_ok=True)
    bank_path = ds_dir / f"{safe}.json"
    payload = {
        "name": name,
        "version": version,
        "subject": subject,
        "path": str(bank_path),
        "questions": merged,
        "_created": "API run_extract_bank",
    }
    bank_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    progress(100, f"{len(merged)} questions extracted")
    return {
        "bank": {
            "name": name,
            "version": version,
            "subject": subject,
            "path": str(bank_path),
            "question_count": len(merged),
            "source_pdf": str(dest),
        },
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# Job: solve an entire question bank -> one PDF
# ---------------------------------------------------------------------------

def run_solve_bank(
    job, progress: Progress, *, bank_name: str, subject: str, book_id: Optional[str] = None,
    marks: int = 10, words_5: Optional[int] = None, words_10: Optional[int] = None,
) -> Dict[str, Any]:
    from medrack import config
    from medrack.answer.batch import generate_full_batch
    from medrack.answer.render_full import render_full_module_pdf
    from medrack.state import get_llm_client

    home = config.get_medrack_home()
    safe = _safe_stem(bank_name)
    bank_path = home / "tests" / "regression_datasets" / f"{safe}.json"
    if not bank_path.is_file():
        raise FileNotFoundError(f"question bank not found: {bank_name}")
    data = json.loads(bank_path.read_text(encoding="utf-8"))
    raw_questions = data.get("questions", [])
    subj = data.get("subject", subject) or subject

    questions: List[dict] = []
    for i, q in enumerate(raw_questions):
        qtext = (q.get("question_text") or q.get("stem") or "").strip()
        if not qtext:
            continue
        questions.append(
            {
                "qid": q.get("qid") or f"{safe}::q{i + 1:03d}",
                "type": q.get("type") or "theory",
                "question_text": qtext,
                "module_chapter": q.get("section") or q.get("module_chapter") or "unknown",
                "options": q.get("options", {}) or {},
                "marks": q.get("marks"),
            }
        )
    total = len(questions)
    if total == 0:
        raise ValueError("This question bank has no answerable questions.")

    progress(3, f"Solving {total} question(s)")
    llm = get_llm_client()

    def batch_progress(done: int, tot: int) -> None:
        frac = (done / tot) if tot else 1.0
        progress(3 + 88 * frac, f"Answered {done}/{tot}")

    # Per-marks answer length from the UI's two length boxes.
    word_targets: dict = {}
    if words_5:
        word_targets[5] = words_5
    if words_10:
        word_targets[10] = words_10

    batch = generate_full_batch(
        module_name=safe,
        subject=subj,
        questions=questions,
        llm_client=llm,
        progress=batch_progress,
        marks=marks,
        word_targets=word_targets or None,
    )

    progress(93, "Rendering solved PDF")
    out_dir = home / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{safe}_solved.pdf"
    render_full_module_pdf(
        pdf_path,
        module_name=bank_name,
        subject=subj,
        batch_result=batch,
        answers=batch.answers,
    )
    progress(100, "Solved")
    return {
        "pdf_path": str(pdf_path),
        "download_name": f"{safe}-solved.pdf",
        "questions_total": batch.questions_total,
        "answered": len(batch.answers),
        "failed": batch.questions_failed,
    }


__all__ = ["run_ingest_book", "run_extract_bank", "run_solve_bank"]
