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
import time
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


def _ocr_agent_url() -> str:
    import os

    return (
        os.environ.get("MEDRACK_OCR_AGENT_URL")
        or "http://192.168.29.89:8090"
    ).rstrip("/")


def run_hybrid_ingest_book(
    job,
    progress: Progress,
    *,
    pdf_path: str,
    subject: str,
    title: str,
    replace: bool = False,
    use_marker: bool = False,
) -> Dict[str, Any]:
    """P1 single-UI hybrid ingest.

    Prefer **push** to Windows OCR agent (started with Start MedRack):
      stop Qwopus → RapidOCR → validate → text PDF → start Qwopus
    then Ubuntu indexes the clean PDF.

    If the agent is not reachable on :8090, fall back to **queue + pull**
    (agent's background pull loop claims the job).
    """
    import httpx
    from medrack.config import get_medrack_home
    from medrack.dashboard.services import ocr_bridge

    pdf = Path(pdf_path).expanduser()
    if not pdf.is_file():
        raise FileNotFoundError(f"uploaded file not found: {pdf}")

    agent = _ocr_agent_url()
    mode = "push"
    ocr_job_id: Optional[str] = None
    clean_bytes: Optional[bytes] = None

    # ---- Prefer push (agent started by Start MedRack) ----
    progress(1, "Contacting Windows OCR agent (integrated with Start MedRack)…")
    agent_up = False
    try:
        with httpx.Client(timeout=5.0) as client:
            hr = client.get(f"{agent}/v1/health")
            agent_up = hr.status_code == 200
    except Exception:  # noqa: BLE001
        agent_up = False

    if agent_up:
        progress(2, "Stopping Qwopus + starting hybrid OCR on Windows…")
        with httpx.Client(timeout=120.0) as client:
            with open(pdf, "rb") as fh:
                resp = client.post(
                    f"{agent}/v1/jobs",
                    files={"file": (pdf.name, fh, "application/pdf")},
                    data={
                        "use_marker": "1" if use_marker else "0",
                        "title": title or pdf.stem,
                    },
                )
                resp.raise_for_status()
                ocr_job_id = resp.json().get("job_id")
        if not ocr_job_id:
            raise RuntimeError("OCR agent returned no job_id")

        progress(3, "Windows: stop model → OCR → validate → restart model…")
        deadline = time.time() + 6 * 3600
        last_msg = ""
        while time.time() < deadline:
            with httpx.Client(timeout=30.0) as client:
                st = client.get(f"{agent}/v1/jobs/{ocr_job_id}")
                st.raise_for_status()
                body = st.json()
            status = body.get("status")
            apct = float(body.get("percent") or 0.0)
            msg = body.get("message") or status or "OCR"
            overall = 3.0 + 0.67 * apct
            if msg != last_msg:
                progress(overall, msg)
                last_msg = msg
            if status == "done":
                break
            if status == "error":
                raise RuntimeError(f"Hybrid OCR failed: {body.get('error') or body}")
            time.sleep(2.0)
        else:
            raise TimeoutError("Hybrid OCR timed out (6h)")

        progress(72, "Downloading clean text PDF…")
        with httpx.Client(timeout=300.0) as client:
            pr = client.get(f"{agent}/v1/jobs/{ocr_job_id}/pdf")
            pr.raise_for_status()
            clean_bytes = pr.content
    else:
        # ---- Fallback: queue for agent pull loop ----
        mode = "pull"
        progress(
            2,
            "OCR agent not on :8090 — queueing job. "
            "Use Start MedRack so the OCR agent is running.",
        )
        ocr_job_id = ocr_bridge.create_ocr_job(
            source_pdf=pdf,
            title=title or pdf.stem,
            subject=subject,
            use_marker=use_marker,
        )
        progress(
            3,
            f"Waiting for Windows agent to claim job {ocr_job_id[:8]}… "
            "(agent starts with Start MedRack)",
        )
        deadline = time.time() + 6 * 3600
        last_msg = ""
        while time.time() < deadline:
            meta = ocr_bridge.load_meta(ocr_job_id) or {}
            status = meta.get("status") or "unknown"
            apct = float(meta.get("percent") or 0.0)
            msg = meta.get("message") or status
            overall = 3.0 + 0.67 * apct
            if msg != last_msg:
                progress(overall, f"Windows OCR: {msg}")
                last_msg = msg
            if status == "done":
                break
            if status == "error":
                raise RuntimeError(f"Hybrid OCR failed: {meta.get('error') or meta}")
            time.sleep(2.0)
        else:
            raise TimeoutError(
                "Timed out waiting for OCR agent. Click Start MedRack on Windows "
                "so the OCR agent is running, then try again."
            )
        clean_src = ocr_bridge.result_path(ocr_job_id)
        if not clean_src or not clean_src.is_file():
            raise FileNotFoundError("OCR finished but clean_text.pdf missing")
        clean_bytes = clean_src.read_bytes()

    home = get_medrack_home()
    books = home / "books"
    books.mkdir(parents=True, exist_ok=True)
    safe = "".join(
        c for c in (title or pdf.stem) if c.isalnum() or c in ("-", "_", " ")
    )[:80].strip()
    clean_path = books / f"{safe or 'book'}_hybrid_ocr.pdf"
    clean_path.write_bytes(clean_bytes or b"")
    progress(
        75,
        f"OCR validated — clean PDF {clean_path.stat().st_size // 1024} KB — indexing…",
    )

    def sub_progress(pct: float, message: str = "") -> None:
        progress(75.0 + 0.25 * float(pct), message or "Indexing clean OCR PDF")

    result = run_ingest_book(
        job,
        sub_progress,
        pdf_path=str(clean_path),
        subject=subject,
        title=title,
        replace=replace,
    )
    result["hybrid_ocr"] = True
    result["ocr_mode"] = mode
    result["clean_pdf"] = str(clean_path)
    result["ocr_job_id"] = ocr_job_id
    result["use_marker"] = use_marker
    progress(100, "Done — book indexed; Qwopus should be back online")
    return result


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
    marks: int = 10, words_3: Optional[int] = None, words_5: Optional[int] = None,
    words_10: Optional[int] = None, marks_filter: Optional[list] = None,
    chapters: Optional[list] = None,
) -> Dict[str, Any]:
    from medrack import config
    from medrack.answer.batch import generate_full_batch
    from medrack.answer.render_full import render_full_module_pdf
    from medrack.state import get_llm_client

    home = config.get_medrack_home()
    safe = _safe_stem(bank_name)
    # Resolve bank from regression_datasets OR modules/*/extracted.json
    # (CLI-ingested modules live under modules/ and were invisible when
    # this only looked at regression_datasets).
    bank_path = home / "tests" / "regression_datasets" / f"{safe}.json"
    data: Dict[str, Any]
    if bank_path.is_file():
        data = json.loads(bank_path.read_text(encoding="utf-8"))
    else:
        data = {}
        modules_root = home / "modules"
        extracted: Optional[Path] = None
        if modules_root.is_dir():
            for p in modules_root.rglob("extracted.json"):
                if p.parent.name == safe or p.parent.name == bank_name:
                    extracted = p
                    break
        if extracted is None:
            raise FileNotFoundError(f"question bank not found: {bank_name}")
        data = json.loads(extracted.read_text(encoding="utf-8"))
        if "subject" not in data:
            # modules/<subject>/<name>/extracted.json
            data["subject"] = extracted.parent.parent.name
        data.setdefault("name", bank_name)
    raw_questions = data.get("questions", [])
    subj = data.get("subject", subject) or subject

    # Filters: which marks and which chapters to include (None = all).
    sel_marks = set(marks_filter) if marks_filter else None
    sel_chapters = {(c or "").strip().lower() for c in chapters} if chapters else None

    questions: List[dict] = []
    for i, q in enumerate(raw_questions):
        qtext = (q.get("question_text") or q.get("stem") or "").strip()
        if not qtext:
            continue
        q_marks = q.get("marks")
        resolved_marks = q_marks if q_marks in (3, 5, 10) else marks
        chap = (q.get("chapter") or q.get("module_chapter") or "").strip()
        if sel_marks is not None and resolved_marks not in sel_marks:
            continue
        if sel_chapters is not None and chap.lower() not in sel_chapters:
            continue
        questions.append(
            {
                "qid": q.get("qid") or f"{safe}::q{i + 1:03d}",
                "type": q.get("type") or "theory",
                "question_text": qtext,
                "module_chapter": chap or "unknown",
                "options": q.get("options", {}) or {},
                "marks": q_marks,
            }
        )
    total = len(questions)
    if total == 0:
        if sel_marks is not None or sel_chapters is not None:
            raise ValueError(
                "No questions match the selected marks/chapters. Adjust the filters."
            )
        raise ValueError("This question bank has no answerable questions.")

    progress(3, f"Solving {total} question(s)")
    llm = get_llm_client()

    def batch_progress(done: int, tot: int) -> None:
        frac = (done / tot) if tot else 1.0
        msg = f"Answered {done}/{tot}"
        if getattr(job, "cancel_requested", False):
            msg = f"Stopping… {done}/{tot} so far"
        progress(3 + 88 * frac, msg)

    def cancel_check() -> bool:
        return bool(getattr(job, "cancel_requested", False))

    # Per-marks answer length from the UI's two length boxes.
    word_targets: dict = {}
    if words_3:
        word_targets[3] = words_3
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
        cancel_check=cancel_check,
    )

    # Review payload: which answers this run produced (for keep/delete UI).
    answer_summaries = []
    for a in batch.answers:
        answer_summaries.append(
            {
                "qid": a.get("qid"),
                "question_text": (a.get("question_text") or "")[:240],
                "module": a.get("module_name") or safe,
                "chapter": a.get("module_chapter") or a.get("chapter") or "",
                "cache_hit": bool(a.get("cache_hit")),
                "needs_review": bool(a.get("needs_review")),
                "word_count": len((a.get("answer_text") or "").split()),
            }
        )

    out_dir = home / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{safe}_solved.pdf"
    pdf_ready = False
    if batch.answers:
        progress(93, "Rendering solved PDF" if not batch.cancelled else "Rendering partial PDF")
        render_full_module_pdf(
            pdf_path,
            module_name=bank_name,
            subject=subj,
            batch_result=batch,
            answers=batch.answers,
        )
        pdf_ready = True

    result: Dict[str, Any] = {
        "pdf_path": str(pdf_path) if pdf_ready else None,
        "download_name": f"{safe}-solved.pdf" if pdf_ready else None,
        "questions_total": batch.questions_total,
        "answered": len(batch.answers),
        "failed": batch.questions_failed,
        "skipped": batch.questions_skipped,
        "cancelled": bool(batch.cancelled),
        "module": safe,
        "bank_name": bank_name,
        "answers": answer_summaries,
        "failed_qids": list(batch.failed_qids),
    }
    if batch.cancelled:
        progress(
            3 + 88 * (len(batch.answers) / total if total else 1.0),
            f"Stopped — kept {len(batch.answers)} of {total} (review keep/delete)",
        )
    else:
        progress(100, "Solved")
    return result


__all__ = [
    "run_ingest_book",
    "run_hybrid_ingest_book",
    "run_extract_bank",
    "run_solve_bank",
]
