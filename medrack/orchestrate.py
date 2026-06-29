"""medrack.orchestrate — core pipeline orchestration logic.

Extracted from ``medrack.cli`` to keep argument parsing and CLI shell distinct
from the actual functional pipelines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .config import Subject
from .ingest import chunk as chunk_mod
from .ingest import chapter as chapter_mod
from .ingest import clean as clean_mod
from .ingest import embed as embed_mod
from .ingest import format_detect
from .ingest import index as index_mod
from .ingest import manifest
from .ingest import ocr as ocr_mod
from .ingest import quality as quality_mod
from .ingest import text_extract as text_extract_mod
from .module import extract as module_extract_mod
from .module import format as module_format_mod
from .module import llm_extract as module_llm_mod
from .module import mcq as module_mcq_mod
from .module import storage as module_storage_mod
from .utils.logger import get_logger
from .state import (
    load_preview_state,
    save_preview_state,
    clear_preview_state,
    append_revision,
    get_llm_client,
    atomic_write_json,
)

logger = get_logger(__name__)

_OCR_FALLBACK_CHAR_THRESHOLD = 100
_KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_LLM_FALLBACK_COVERAGE = 0.5


def _extract_pages(pdf_path: Path) -> list[dict]:
    """Run the T2/T3 hybrid extraction across all pages of ``pdf_path``."""
    pages: list[dict] = []
    for text_page in text_extract_mod.extract_text_pages(pdf_path):
        if text_page["char_count"] >= _OCR_FALLBACK_CHAR_THRESHOLD:
            pages.append(text_page)
            continue
        try:
            ocr_page = ocr_mod.ocr_page(pdf_path, page_num=text_page["page_num"])
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "OCR fallback failed for %s page %d: %s",
                pdf_path.name,
                text_page["page_num"],
                exc,
            )
            pages.append(text_page)
            continue

        if ocr_page["char_count"] > text_page["char_count"]:
            pages.append(ocr_page)
        else:
            pages.append(text_page)

    return pages


def cmd_ingest_book(args: argparse.Namespace) -> int:
    """Orchestrate the T1-T9 KB ingest pipeline on a single PDF."""
    start_time = time.perf_counter()

    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        subject = config.Subject.from_str(args.subject)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    book_id = str(uuid.uuid4())
    title = args.book

    print(f"Hashing {pdf_path.name}...", file=sys.stderr)
    sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    existing = manifest.get_book(sha256)
    if existing is not None and not existing.get("archived_at"):
        if not args.replace:
            print(
                f"ERROR: book with sha256 {sha256} already indexed "
                f"(use --replace to archive the old one and re-ingest)",
                file=sys.stderr,
            )
            return 4
        archived = manifest.archive_book(sha256)
        logger.info("Archived previous book with sha256 %s (archived=%s)", sha256, archived)

    print(f"Detecting format...", file=sys.stderr)
    try:
        format_report = format_detect.detect_format(pdf_path, sample_pages=5)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    logger.info(
        "Format: %s (text=%d image=%d blank=%d, inspected=%d)",
        format_report.format,
        format_report.text_pages,
        format_report.image_pages,
        format_report.blank_pages,
        format_report.pages_inspected,
    )
    print(
        f"Format: {format_report.format} "
        f"(text={format_report.text_pages} image={format_report.image_pages} "
        f"blank={format_report.blank_pages})",
        file=sys.stderr,
    )

    print(f"Extracting pages (T2 text + T3 OCR fallback)...", file=sys.stderr)
    try:
        pages = _extract_pages(pdf_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Page extraction failed for %s", pdf_path)
        print(f"ERROR: page extraction failed: {exc}", file=sys.stderr)
        return 5

    text_pages_count = sum(1 for p in pages if p["method"] == "text")
    ocr_pages_count = sum(1 for p in pages if p["method"] == "ocr")
    print(
        f"  extracted {len(pages)} pages ({text_pages_count} text, {ocr_pages_count} OCR)",
        file=sys.stderr,
    )

    print(f"Cleaning...", file=sys.stderr)
    cleaned_pages = clean_mod.clean_pages(pages)

    print(f"Segmenting chapters...", file=sys.stderr)
    chapters = chapter_mod.segment_chapters(cleaned_pages, book_title=title)
    print(f"  found {len(chapters)} chapter(s)", file=sys.stderr)

    print(f"Chunking...", file=sys.stderr)
    chunks = chunk_mod.chunk_pages(
        cleaned_pages,
        chapters,
        subject=subject.value,
        book_id=book_id,
    )
    print(f"  produced {len(chunks)} chunks", file=sys.stderr)

    print(f"Embedding {len(chunks)} chunks (loading model on first call)...", file=sys.stderr)
    try:
        embed_mod.embed_chunks(chunks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Embedding failed for %s", pdf_path)
        print(f"ERROR: embedding failed: {exc}", file=sys.stderr)
        return 5

    print(f"Indexing into kb_{subject.value}...", file=sys.stderr)
    try:
        index_mod.index_chunks(chunks, subject=subject.value)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Indexing failed for %s", pdf_path)
        print(f"ERROR: indexing failed: {exc}", file=sys.stderr)
        return 5

    print(f"Running OCR quality gate...", file=sys.stderr)
    quality_report = quality_mod.check_ocr_quality(cleaned_pages)

    elapsed = time.perf_counter() - start_time
    book_record = {
        "book_id": book_id,
        "subject": subject.value,
        "title": title,
        "filename": pdf_path.name,
        "sha256": sha256,
        "pages": len(cleaned_pages),
        "chunks": len(chunks),
        "embedding_model": config.EMBEDDING_MODEL,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "replaced_by": None,
        "archived_at": None,
        "ocr_pages": ocr_pages_count,
        "ocr_suspect_pages": quality_report.suspect_pages,
    }
    try:
        manifest.add_book(book_record)
    except ValueError as exc:
        print(f"ERROR: manifest rejected book: {exc}", file=sys.stderr)
        return 5

    print(f"Indexed {book_record['chunks']} chunks from {book_record['pages']} pages")
    print(
        f"Suspect pages: {len(quality_report.suspect_pages)} "
        f"({quality_report.suspect_pages[:10]}{'...' if len(quality_report.suspect_pages) > 10 else ''})"
    )
    print(f"Total time: {elapsed:.1f}s")
    print(f"Book: {book_record['title']} [{book_record['subject']}] sha256={sha256[:12]}...")

    logger.info(
        "Ingest complete: book_id=%s subject=%s pages=%d chunks=%d "
        "suspect=%d elapsed=%.1fs",
        book_id,
        subject.value,
        book_record["pages"],
        book_record["chunks"],
        len(quality_report.suspect_pages),
        elapsed,
    )
    return 0


def _resolve_chapter_from_questions(
    questions: list[dict], chapter_arg: str
) -> dict:
    """Pick a question from the module given the (prototype) chapter filter."""
    if not questions:
        return {}
    for q in questions:
        if q.get("type") != "mcq":
            return q
    return {}


def cmd_preview(args: argparse.Namespace) -> int:
    """Generate a preview answer for the first question in the module."""
    module_name = args.module
    chapter_arg = args.chapter

    from medrack.answer.generate import generate_answer
    from medrack.answer.render import render_preview_pdf
    from medrack.module.storage import load_extracted

    subject = args.subject
    if not subject:
        modules_root = config.get_medrack_home() / "modules"
        candidates: list[str] = []
        if modules_root.exists():
            for subj_dir in modules_root.iterdir():
                if subj_dir.is_dir() and (subj_dir / module_name / "extracted.json").exists():
                    candidates.append(subj_dir.name)
        if not candidates:
            print(
                f"ERROR: cannot find module {module_name!r} in any subject "
                f"(set --subject explicitly or run `medrack init` first)",
                file=sys.stderr,
            )
            return 2
        if len(candidates) > 1:
            print(
                f"ERROR: module {module_name!r} exists under multiple subjects "
                f"({', '.join(candidates)}); pass --subject explicitly",
                file=sys.stderr,
            )
            return 2
        subject = candidates[0]

    data = load_extracted(subject, module_name)
    if data is None:
        print(
            f"ERROR: module {module_name!r} not found for subject {subject!r} "
            f"(run `medrack ingest-module ... --name {module_name}` first)",
            file=sys.stderr,
        )
        return 2

    questions = data.get("questions", [])
    if not questions:
        print(
            f"ERROR: module {module_name!r} has no extracted questions",
            file=sys.stderr,
        )
        return 5

    if chapter_arg and chapter_arg != "all":
        print(
            f"Using first question in module (chapter filter "
            f"{chapter_arg!r} is informational in Stage 2.4 prototype)"
        )
    question = _resolve_chapter_from_questions(questions, chapter_arg)
    if not question:
        print(
            f"ERROR: no theory (5-mark / 10-mark) questions found in module "
            f"{module_name!r}. Re-ingest with `medrack ingest-module` to "
            f"pick up the long/short answer sections.",
            file=sys.stderr,
            )
        return 2
    chapter_name = chapter_arg if chapter_arg else "all"

    if question.get("type") == "mcq":
        print(
            f"ERROR: '{question['qid']}' is an MCQ; preview only supports "
            f"5-mark/10-mark theory questions. Run `medrack ingest-module` "
            f"again if the extraction missed the theory sections.",
            file=sys.stderr,
        )
        return 2

    client = get_llm_client()
    try:
        marks = question.get("marks")
        if marks is None:
            marks = 10
        answer_dict = generate_answer(
            module_name=module_name,
            subject=subject,
            chapter=chapter_name,
            question=question,
            llm_client=client,
            force_regenerate=args.reanswer,
            marks=marks,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_answer failed for %s/%s", subject, module_name)
        print(f"ERROR: answer generation failed: {exc}", file=sys.stderr)
        return 5

    output_dir = config.get_medrack_home() / "output" / module_name
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{timestamp}_preview_{question['qid']}.pdf"
    try:
        render_preview_pdf(
            output_path,
            module_name=module_name,
            module_subject=subject,
            question=question,
            answer=answer_dict,
            question_index=1,
            total_questions=len(questions),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("render_preview_pdf failed for %s", module_name)
        print(f"ERROR: PDF rendering failed: {exc}", file=sys.stderr)
        return 5

    state = {
        "last_preview": {
            "module": module_name,
            "subject": subject,
            "chapter": chapter_name,
            "qid": question["qid"],
            "pdf_path": str(output_path),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    try:
        save_preview_state(state)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save preview state: %s", exc)

    print(f"Preview rendered: {output_path}")
    print()
    print(f"Question ({question['qid']}): {question.get('question_text', '')}")
    print()
    answer_text = answer_dict.get("answer_text", "")
    if len(answer_text) > 500:
        answer_preview = answer_text[:500] + "..."
    else:
        answer_preview = answer_text
    print(f"Answer:\n{answer_preview}")
    print()
    print(
        f"Reply with `medrack approve` to generate the rest, or "
        f"`medrack revise wordcount 1500` to change the format."
    )
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    """Approve the last preview and generate the full batch (Stage 2.5 B3)."""
    state = load_preview_state()
    if not state or "last_preview" not in state:
        print(
            "ERROR: no preview to approve (run `medrack preview ...` first)",
            file=sys.stderr,
        )
        return 2

    last = state["last_preview"]
    module_name = last.get("module")
    subject = last.get("subject")
    chapter_from_preview = last.get("chapter", "all")

    if not module_name or not subject:
        print(
            "ERROR: preview state is missing module/subject — "
            "re-run `medrack preview ...` to refresh it",
            file=sys.stderr,
        )
        return 2

    from medrack.answer.batch import generate_full_batch
    from medrack.answer.render_full import render_full_module_pdf
    from medrack.module.storage import load_extracted

    data = load_extracted(subject, module_name)
    if data is None:
        print(
            f"ERROR: module {module_name!r} not found for subject {subject!r} "
            f"(re-run `medrack ingest-module ... --name {module_name}` first)",
            file=sys.stderr,
        )
        return 5
    questions: list[dict] = data.get("questions", [])
    if not questions:
        print(
            f"ERROR: module {module_name!r} has no extracted questions",
            file=sys.stderr,
        )
        return 5

    client = get_llm_client()

    chapter_filter = (
        None
        if not chapter_from_preview or chapter_from_preview == "all"
        else chapter_from_preview
    )
    try:
        batch = generate_full_batch(
            module_name=module_name,
            subject=subject,
            questions=questions,
            llm_client=client,
            chapter_filter=chapter_filter,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_full_batch failed for %s/%s", subject, module_name)
        print(f"ERROR: batch generation failed: {exc}", file=sys.stderr)
        return 5

    output_dir = config.DATA_DIRS["output"] / module_name
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{timestamp}_full.pdf"

    try:
        render_full_module_pdf(
            output_path,
            module_name=module_name,
            subject=subject,
            batch_result=batch,
            answers=batch.answers,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("render_full_module_pdf failed for %s", module_name)
        print(f"ERROR: full PDF rendering failed: {exc}", file=sys.stderr)
        return 5

    per_question: list[dict] = []
    for ans in batch.answers:
        per_question.append({
            "qid": ans.get("qid"),
            "cache_hit": bool(ans.get("cache_hit", False)),
            "tokens": int(ans.get("total_tokens", 0) or 0),
            "latency": float(ans.get("latency_seconds", 0.0) or 0.0),
        })

    batch_state = {
        "module": module_name,
        "subject": subject,
        "chapters": list(batch.chapters) if batch.chapters else (
            [chapter_from_preview] if chapter_from_preview else ["all"]
        ),
        "questions_total": batch.questions_total,
        "questions_generated": batch.questions_generated,
        "questions_cached": batch.questions_cached,
        "questions_failed": batch.questions_failed,
        "total_tokens": batch.total_tokens,
        "total_latency_seconds": batch.total_latency_seconds,
        "elapsed_seconds": batch.elapsed_seconds,
        "output_pdf": str(output_path),
        "per_question": per_question,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    state_dir = config.get_medrack_home() / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "batch_state.json"
    try:
        atomic_write_json(state_path, batch_state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not write batch state to %s", state_path)
        print(
            f"ERROR: could not write batch state: {exc}",
            file=sys.stderr,
        )
        return 5

    print(f"Batch complete for {module_name} [{subject}]")
    print(
        f"  questions_total:      {batch.questions_total}"
    )
    print(
        f"  questions_generated:  {batch.questions_generated}  "
        f"(cached: {batch.questions_cached}, failed: {batch.questions_failed})"
    )
    print(
        f"  total_tokens:         {batch.total_tokens}  "
        f"(elapsed: {batch.elapsed_seconds:.1f}s)"
    )
    print(f"  output_pdf:           {output_path}")
    print(f"  batch_state:          {state_path}")

    clear_preview_state()
    return 0


def cmd_revise(args: argparse.Namespace) -> int:
    """Record a revision request for the last preview."""
    state = load_preview_state()
    if not state or "last_preview" not in state:
        print("ERROR: no preview to revise (run `medrack preview ...` first)", file=sys.stderr)
        return 2

    axis = args.axis
    notes = args.notes
    last = state["last_preview"]
    record = {
        "module": last.get("module"),
        "qid": last.get("qid"),
        "axis": axis,
        "notes": notes,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        append_revision(record)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not append revision")
        print(f"ERROR: could not record revision: {exc}", file=sys.stderr)
        return 2

    module = last.get("module", "<module>")
    print(
        f"Revision recorded: {axis} = {notes}. "
        f"Re-run `medrack preview {module}` with `--reanswer` to apply."
    )
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    """Cancel the current preview by clearing the preview state."""
    clear_preview_state()
    print("Preview cancelled.")
    return 0


def cmd_ingest_module(args: argparse.Namespace) -> int:
    """Orchestrate the M1-M5 module question ingest pipeline on a single PDF."""
    start_time = time.perf_counter()

    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        subject = config.Subject.from_str(args.subject)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    module_name = args.name
    if not _KEBAB_CASE_RE.match(module_name):
        print(
            f"ERROR: module name {module_name!r} is not kebab-case "
            f"(allowed: lowercase letters, digits, hyphens; "
            f"e.g. 'psm-module-1')",
            file=sys.stderr,
        )
        return 5

    print(f"Extracting pages from {pdf_path.name}...", file=sys.stderr)
    try:
        pages = module_extract_mod.extract_module_pages(pdf_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        logger.exception("Page extraction failed for %s", pdf_path)
        print(f"ERROR: page extraction failed: {exc}", file=sys.stderr)
        return 5
    print(f"  extracted {len(pages)} cleaned page(s)", file=sys.stderr)

    forced_format = args.format
    if forced_format == "auto":
        format_str = module_format_mod.detect_module_format(pages[:5])  # type: ignore[arg-type]
    else:
        format_str = forced_format
    print(f"Format: {format_str} (forced={forced_format})", file=sys.stderr)

    questions = module_mcq_mod.extract_mcqs_from_pages(pages)
    coverage = module_mcq_mod.regex_extraction_coverage(pages)

    page_context = module_mcq_mod.detect_section_marks(pages)
    module_mcq_mod.annotate_questions_with_marks(questions, page_context)
    n_5 = sum(1 for q in questions if q.marks == 5)
    n_10 = sum(1 for q in questions if q.marks == 10)
    print(
        f"Extracted {len(questions)} question(s) via regex "
        f"(coverage {coverage:.0%}; {n_5} x 5-mark, {n_10} x 10-mark, "
        f"{len(questions) - n_5 - n_10} MCQ)",
        file=sys.stderr,
    )

    if coverage < _LLM_FALLBACK_COVERAGE and format_str == "mcq":
        try:
            llm_results = module_llm_mod.extract_questions_with_llm(
                [p.get("text", "") or "" for p in pages],
                subject=subject.value,
                llm_client=None,
            )
        except NotImplementedError:
            llm_results = []
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM fallback failed: %s", exc)
            llm_results = []
        if llm_results:
            print(
                f"LLM fallback produced {len(llm_results)} additional question(s)",
                file=sys.stderr,
            )

    data = {
        "questions": [asdict(q) for q in questions],
        "metadata": {
            "module_name": module_name,
            "subject": subject.value,
            "title": module_name,
            "format": format_str,
            "total_pages": len(pages),
            "questions_extracted": len(questions),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    try:
        module_storage_mod.save_extracted(subject.value, module_name, data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("save_extracted failed for %s/%s", subject.value, module_name)
        print(f"ERROR: save failed: {exc}", file=sys.stderr)
        return 5

    elapsed = time.perf_counter() - start_time
    extracted_path = module_storage_mod.extracted_json_path(
        subject.value, module_name
    )
    print(
        f"Extracted {len(questions)} questions from {len(pages)} pages "
        f"(format={format_str}, coverage={coverage:.0%})"
    )
    print(f"Saved: {extracted_path}")
    print(f"Total time: {elapsed:.1f}s")
    print(f"Module: {module_name} [{subject.value}]")

    logger.info(
        "Module ingest complete: name=%s subject=%s pages=%d questions=%d "
        "format=%s coverage=%.2f elapsed=%.1fs",
        module_name,
        subject.value,
        len(pages),
        len(questions),
        format_str,
        coverage,
        elapsed,
    )
    return 0
