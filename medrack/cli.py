"""
medrack CLI — entry point for the `medrack` command.

Stage 2.1 added `init`, `status`, `version`. Stage 2.2 / T10 adds
`ingest-book`, the end-to-end orchestrator for the KB ingest pipeline
(T1 format detection → T9 quality gate). Stage 2.3 / M6 adds
`ingest-module`, the end-to-end orchestrator for the module question
ingest pipeline (M1 module text extract → M5 module storage).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
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

logger = get_logger(__name__)


# Threshold below which a text-extracted page is considered to have
# "missed" the content and should be re-OCR'd. Kept low (100 chars) because
# legitimate text pages of a textbook rarely fall below it, but cover
# pages, blank pages, and image-only pages reliably do.
_OCR_FALLBACK_CHAR_THRESHOLD = 100


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the medrack data directory structure."""
    print(f"medrack init: home = {config.HOME}")
    for name, path in config.DATA_DIRS.items():
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {name:<12} {path}")

    # Initialize manifest if missing
    if not config.MANIFEST_PATH.exists():
        config.MANIFEST_PATH.write_text(json.dumps(
            {"version": config.MANIFEST_VERSION, "books": [], "modules": []},
            indent=2
        ))
        print(f"  ✓ manifest   {config.MANIFEST_PATH}")
    else:
        print(f"  · manifest   {config.MANIFEST_PATH} (already exists)")

    # Initialize empty ChromaDB dir
    config.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ chroma     {config.CHROMA_PATH}")

    print(f"\nmedrack {__version__} initialized.")
    print(f"Subjects: {', '.join(config.Subject.values())}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show system status: dirs, deps, indexed counts."""
    print(f"medrack {__version__}  (home: {config.HOME})\n")

    # Directory check
    print("Directories:")
    for name, path in config.DATA_DIRS.items():
        exists = "✓" if path.exists() else "✗"
        print(f"  {exists} {name:<12} {path}")

    # Dependency check
    print("\nDependencies:")
    for mod, label in [
        ("pypdf", "PDF reading"),
        ("pytesseract", "Tesseract wrapper"),
        ("PIL", "Pillow (image)"),
        ("chromadb", "ChromaDB"),
        ("sentence_transformers", "Embeddings"),
        ("reportlab", "PDF rendering"),
        ("gradio", "Dashboard"),
    ]:
        try:
            __import__(mod)
            print(f"  ✓ {label:<20} ({mod})")
        except ImportError:
            print(f"  ✗ {label:<20} ({mod}) — run: pip install {mod}")

    # External tools
    import shutil
    print("\nExternal tools:")
    for tool in ["tesseract", "pdftotext", "pdftoppm"]:
        path = shutil.which(tool)
        print(f"  {'✓' if path else '✗'} {tool:<12} {path or '(not found)'}")

    # Manifest summary
    print("\nIndexed:")
    if config.MANIFEST_PATH.exists():
        m = json.loads(config.MANIFEST_PATH.read_text())
        books = m.get("books", [])
        modules = m.get("modules", [])
        active_books = [b for b in books if not b.get("archived_at")]
        active_modules = [m for m in modules if not m.get("archived_at")]
        print(f"  Books:   {len(active_books)} active, {len(books) - len(active_books)} archived")
        print(f"  Modules: {len(active_modules)} active, {len(modules) - len(active_modules)} archived")
    else:
        print("  (no manifest — run `medrack init`)")

    print(f"\nSubjects ({len(Subject)}): {', '.join(Subject.values())}")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    print(f"medrack {__version__}")
    return 0


def _extract_pages(pdf_path: Path) -> list[dict]:
    """Run the T2/T3 hybrid extraction across all pages of ``pdf_path``.

    Strategy:
        1. Run T2 (text extraction) on every page — cheap.
        2. For any page where text extraction yielded < 100 chars
           (i.e. probably a blank / image-only page), re-run with T3
           (OCR) and keep the OCR result.

    The hybrid per-page char_count rule is more reliable than trusting
    the format detector on a per-page basis (the detector only inspects
    the first ``sample_pages`` pages).
    """
    pages: list[dict] = []
    for text_page in text_extract_mod.extract_text_pages(pdf_path):
        if text_page["char_count"] >= _OCR_FALLBACK_CHAR_THRESHOLD:
            pages.append(text_page)
            continue
        # Text extraction was poor — fall back to OCR for this page.
        try:
            ocr_page = ocr_mod.ocr_page(pdf_path, page_num=text_page["page_num"])
        except Exception as exc:  # noqa: BLE001 — never fail the whole ingest
            logger.warning(
                "OCR fallback failed for %s page %d: %s",
                pdf_path.name,
                text_page["page_num"],
                exc,
            )
            # Keep the text-extracted page (likely empty) so we still
            # have a record for downstream chunking.
            pages.append(text_page)
            continue

        # If OCR actually produced more text, use it. Otherwise stick
        # with the (empty) text result so we don't store a near-empty
        # OCR result that just adds noise.
        if ocr_page["char_count"] > text_page["char_count"]:
            pages.append(ocr_page)
        else:
            pages.append(text_page)

    return pages


def cmd_ingest_book(args: argparse.Namespace) -> int:
    """Orchestrate the T1-T9 KB ingest pipeline on a single PDF.

    Pipeline:
        1. Validate PDF path
        2. Validate subject
        3. Allocate book_id, compute sha256
        4. Dedup check against the manifest (archive on --replace)
        5. Format detection (T1)
        6. Per-page extraction: text (T2) with OCR (T3) fallback
        7. Cleaning (T4)
        8. Chapter segmentation (T5)
        9. Chunking (T6)
       10. Embedding (T7)
       11. Indexing (T7 / ChromaDB)
       12. Quality gate (T9)
       13. Manifest write (T8)
       14. Summary

    Exit codes:
        0 — success
        2 — file not found
        3 — invalid subject
        4 — duplicate sha256 and not --replace
        5 — ingest pipeline failure (logged with traceback)
    """
    start_time = time.perf_counter()

    # 1. PDF path validation.
    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    # 2. Subject validation.
    try:
        subject = config.Subject.from_str(args.subject)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    # 3. Book identity.
    book_id = str(uuid.uuid4())
    title = args.book

    # 4. sha256 + dedup.
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
        # Archive the old one so the dedup check in manifest.add_book passes.
        archived = manifest.archive_book(sha256)
        logger.info("Archived previous book with sha256 %s (archived=%s)", sha256, archived)

    # 5. Format detection (T1).
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

    # 6. Extract pages (T2 + T3).
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

    # 7. Cleaning (T4).
    print(f"Cleaning...", file=sys.stderr)
    cleaned_pages = clean_mod.clean_pages(pages)

    # 8. Chapter segmentation (T5).
    print(f"Segmenting chapters...", file=sys.stderr)
    chapters = chapter_mod.segment_chapters(cleaned_pages, book_title=title)
    print(f"  found {len(chapters)} chapter(s)", file=sys.stderr)

    # 9. Chunking (T6).
    print(f"Chunking...", file=sys.stderr)
    chunks = chunk_mod.chunk_pages(
        cleaned_pages,
        chapters,
        subject=subject.value,
        book_id=book_id,
    )
    print(f"  produced {len(chunks)} chunks", file=sys.stderr)

    # 10. Embedding (T7).
    print(f"Embedding {len(chunks)} chunks (loading model on first call)...", file=sys.stderr)
    try:
        embed_mod.embed_chunks(chunks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Embedding failed for %s", pdf_path)
        print(f"ERROR: embedding failed: {exc}", file=sys.stderr)
        return 5

    # 11. Indexing (T7 → ChromaDB).
    print(f"Indexing into kb_{subject.value}...", file=sys.stderr)
    try:
        index_mod.index_chunks(chunks, subject=subject.value)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Indexing failed for %s", pdf_path)
        print(f"ERROR: indexing failed: {exc}", file=sys.stderr)
        return 5

    # 12. Quality gate (T9).
    print(f"Running OCR quality gate...", file=sys.stderr)
    quality_report = quality_mod.check_ocr_quality(cleaned_pages)

    # 13. Manifest write (T8).
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
        # Should be impossible because we archive-first when --replace,
        # but surface a clear error if we ever hit it.
        print(f"ERROR: manifest rejected book: {exc}", file=sys.stderr)
        return 5

    # 14. Summary to stdout (so test assertions on "chunks"/"indexed" work).
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


# Kebab-case slug pattern: only lowercase letters, digits, and hyphens,
# must start and end with an alphanumeric. Mirrors the brief's
# "kebab-case (only lowercase, digits, hyphens)" rule.
_KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Coverage threshold below which the LLM-fallback extractor is invoked.
# Mirrors M2's documentation: < 0.5 means regex probably missed a lot.
_LLM_FALLBACK_COVERAGE = 0.5


# ---------------------------------------------------------------------------
# Preview state machine (Stage 2.4 / Task A6)
#
# The preview flow is a 4-state interaction between the user and the LLM:
#
#     [no state]  -- preview -->  [previewing]
#     [previewing] -- approve -->  [approved]  (clears state)
#     [previewing] -- revise  -->  [previewing] (records revision)
#     [previewing] -- cancel  -->  [no state]  (clears state)
#     [*]         -- cancel  -->  [no state]  (always succeeds)
#
# The state lives in ``<HOME>/state/preview_state.json`` (atomic JSON
# write) and the revision log in ``<HOME>/state/revisions.json`` (atomic
# JSON list, append-only). Both paths are re-evaluated on every call via
# ``config.get_medrack_home()`` so ``$MEDRACK_HOME`` overrides work in
# tests, mirroring the pattern in ``medrack.ingest.manifest``.
# ---------------------------------------------------------------------------

def _state_path() -> Path:
    """Return the path to the preview state JSON file (parent dir created)."""
    p = config.get_medrack_home() / "state" / "preview_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _revisions_path() -> Path:
    """Return the path to the revisions log JSON file (parent dir created)."""
    p = config.get_medrack_home() / "state" / "revisions.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _atomic_write_json(path: Path, data) -> None:
    """Write ``data`` to ``path`` atomically (tmp + replace)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False))
    tmp.replace(path)


def _load_preview_state() -> dict | None:
    """Load the preview state file, or ``None`` if missing."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # Treat a corrupt state file as "no preview" — safer than crashing
        # the user-facing CLI.
        return None


def _clear_preview_state() -> None:
    """Delete the preview state file if it exists. Silent no-op otherwise."""
    path = _state_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _append_revision(record: dict) -> None:
    """Append a revision record to revisions.json (atomic, list-of-dicts)."""
    path = _revisions_path()
    if path.exists():
        try:
            current = json.loads(path.read_text())
        except json.JSONDecodeError:
            current = []
    else:
        current = []
    if not isinstance(current, list):
        current = []
    current.append(record)
    _atomic_write_json(path, current)


def _resolve_chapter_from_questions(
    questions: list[dict], chapter_arg: str
) -> dict:
    """Pick a question from the module given the (prototype) chapter filter.

    For Stage 2.4 the brief accepts a simplified contract: any
    ``--chapter`` value falls back to "first question in the module".
    This keeps the prototype working while the real per-chapter
    scoping lands in Stage 2.5.
    """
    if not questions:
        return {}
    return questions[0]


def cmd_preview(args: argparse.Namespace) -> int:
    """Generate a preview answer for the first question in the module.

    Pipeline (Stage 2.4 / Task A6):
        1. Resolve subject (from --subject or from extracted.json metadata).
        2. Load the module's extracted.json.
        3. Pick the first question in the module (prototype behaviour).
        4. Build an LLMClient and call generate_answer().
        5. Render the preview PDF to <output>/<module>/<ts>_preview_<qid>.pdf.
        6. Save preview state atomically.
        7. Print the PDF path, the question, a truncated answer, and a
           reminder of the approve/revise workflow.

    Exit codes:
        0 — preview PDF rendered successfully
        2 — module not found / subject not provided and not in metadata
        5 — downstream failure (LLM, renderer, etc.)
    """
    module_name = args.module
    chapter_arg = args.chapter  # e.g. "chapter 1" or "all"

    # Lazy imports so that this module can be imported (and CLI loaded)
    # even when A5 (generate.py) has not yet landed. The error-path tests
    # only need argparse rejection — they never reach the imports.
    from medrack.answer.generate import generate_answer
    from medrack.answer.render import render_preview_pdf
    from medrack.answer.llm import LLMClient
    from medrack.module.storage import load_extracted

    # 1. Subject — either explicit or read from extracted.json metadata.
    subject = args.subject
    if not subject:
        # Try to find the module under any subject directory.
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

    # 2. Load the module.
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

    # 3. Pick the first question (prototype behaviour for Stage 2.4).
    if chapter_arg and chapter_arg != "all":
        # The real per-chapter scoping lands in Stage 2.5. For now, just
        # signal that we're falling back to "first question" so the
        # operator knows the chapter filter is informational only.
        print(
            f"Using first question in module (chapter filter "
            f"{chapter_arg!r} is informational in Stage 2.4 prototype)"
        )
    question = _resolve_chapter_from_questions(questions, chapter_arg)
    chapter_name = chapter_arg if chapter_arg else "all"

    # 4. LLM client + answer generation.
    client = LLMClient()
    try:
        answer_dict = generate_answer(
            module_name=module_name,
            subject=subject,
            chapter=chapter_name,
            question=question,
            llm_client=client,
            force_regenerate=args.reanswer,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_answer failed for %s/%s", subject, module_name)
        print(f"ERROR: answer generation failed: {exc}", file=sys.stderr)
        return 5

    # 5. Render the preview PDF.
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

    # 6. Save preview state atomically.
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
        _atomic_write_json(_state_path(), state)
    except Exception as exc:  # noqa: BLE001
        # State persistence is best-effort; the PDF is the actual deliverable.
        logger.warning("Could not save preview state: %s", exc)

    # 7. Print the result and the workflow reminder.
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
    """Approve the last preview and (in Stage 2.5) generate the rest.

    For Stage 2.4 / Task A6 this only records the approval and clears
    the preview state. The full batch generation arrives in Stage 2.5.

    Exit codes:
        0 — approval recorded (or already cleared; idempotent)
        2 — no preview state to approve
    """
    state = _load_preview_state()
    if not state or "last_preview" not in state:
        print("ERROR: no preview to approve (run `medrack preview ...` first)", file=sys.stderr)
        return 2

    last = state["last_preview"]
    module = last.get("module", "?")
    qid = last.get("qid", "?")
    print(
        f"Approval recorded for {module} / {qid}. "
        f"Full batch generation will be implemented in Stage 2.5."
    )
    _clear_preview_state()
    return 0


def cmd_revise(args: argparse.Namespace) -> int:
    """Record a revision request for the last preview.

    The revision is appended to revisions.json (atomic, list-of-dicts).
    The full "re-run with feedback" flow lands in Stage 2.5; for now
    this just records the request and prints a reminder.

    Exit codes:
        0 — revision recorded
        2 — no preview state to revise
    """
    state = _load_preview_state()
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
        _append_revision(record)
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
    """Cancel the current preview by clearing the preview state.

    Always returns 0 — cancel is idempotent and safe to run with no
    pending preview.
    """
    _clear_preview_state()
    print("Preview cancelled.")
    return 0


def cmd_ingest_module(args: argparse.Namespace) -> int:
    """Orchestrate the M1-M5 module question ingest pipeline on a single PDF.

    Pipeline:
        1. Validate PDF path (exit 2 if missing).
        2. Validate subject via config.Subject.from_str (exit 3 on failure).
        3. Validate module name is kebab-case (exit 5 on failure).
        4. Extract pages with M1 (`extract_module_pages`).
        5. Determine format: forced (`mcq`/`theory`) or M4 auto-detect.
        6. Extract questions with M2 (`extract_mcqs_from_pages`).
        7. If regex coverage < 50% AND format is MCQ, try M3 LLM fallback
           (gracefully degrades to [] in Stage 2.3 — no real LLM client).
        8. Build the data dict (questions + metadata) and save with M5.
        9. Print summary to stdout (so test assertions on "questions" work).

    Exit codes:
        0 — success
        2 — file not found
        3 — invalid subject
        5 — invalid module name (kebab-case) or downstream failure
    """
    start_time = time.perf_counter()

    # 1. PDF path validation.
    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    # 2. Subject validation.
    try:
        subject = config.Subject.from_str(args.subject)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    # 3. Module-name validation (kebab-case slug).
    module_name = args.name
    if not _KEBAB_CASE_RE.match(module_name):
        print(
            f"ERROR: module name {module_name!r} is not kebab-case "
            f"(allowed: lowercase letters, digits, hyphens; "
            f"e.g. 'psm-module-1')",
            file=sys.stderr,
        )
        return 5

    # 4. Page extraction (M1).
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

    # 5. Format determination (M4).
    forced_format = args.format  # "auto" | "mcq" | "theory"
    if forced_format == "auto":
        format_str = module_format_mod.detect_module_format(pages[:5])  # type: ignore[arg-type]
    else:
        format_str = forced_format
    print(f"Format: {format_str} (forced={forced_format})", file=sys.stderr)

    # 6. Question extraction (M2).
    questions = module_mcq_mod.extract_mcqs_from_pages(pages)
    coverage = module_mcq_mod.regex_extraction_coverage(pages)
    print(
        f"Extracted {len(questions)} question(s) via regex "
        f"(coverage {coverage:.0%})",
        file=sys.stderr,
    )

    # 7. LLM fallback (M3) — safety net when regex coverage is poor.
    # In Stage 2.3 there is no real LLM client wired, so this just
    # degrades to []; we still call it through the path so Stage 2.4
    # can drop in a real client without changes to the orchestrator.
    if coverage < _LLM_FALLBACK_COVERAGE and format_str == "mcq":
        try:
            llm_results = module_llm_mod.extract_questions_with_llm(
                [p.get("text", "") or "" for p in pages],
                subject=subject.value,
                llm_client=None,  # Stage 2.4 will pass a real client
            )
        except NotImplementedError:
            # No real LLM client in Stage 2.3 — fall back to regex results.
            llm_results = []
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM fallback failed: %s", exc)
            llm_results = []
        if llm_results:
            print(
                f"LLM fallback produced {len(llm_results)} additional question(s)",
                file=sys.stderr,
            )

    # 8. Build the data dict and save (M5).
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

    # 9. Summary to stdout (so tests can assert on it).
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="medrack",
        description="Local RAG system for MBBS theory-exam answer generation.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="Initialize medrack data directories")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("status", help="Show system status")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("version", help="Print version")
    sp.set_defaults(func=cmd_version)

    sp = sub.add_parser("ingest-book", help="Ingest a KB textbook PDF (T1-T9 pipeline)")
    sp.add_argument("pdf", help="Path to the PDF file")
    sp.add_argument("--subject", required=True, help="Subject (psm, fmt, medicine, ...)")
    sp.add_argument("--book", required=True, help="Book title")
    sp.add_argument(
        "--replace",
        action="store_true",
        help="If a book with the same SHA-256 is already indexed, archive it first.",
    )
    sp.set_defaults(func=cmd_ingest_book)

    sp = sub.add_parser(
        "ingest-module", help="Ingest a question-bank module PDF (M1-M5 pipeline)"
    )
    sp.add_argument("pdf", help="Path to the module PDF")
    sp.add_argument(
        "--subject", required=True, help="Subject (psm, fmt, medicine, ...)"
    )
    sp.add_argument(
        "--name",
        required=True,
        help="Module name (kebab-case slug, e.g. 'psm-module-1')",
    )
    sp.add_argument(
        "--format",
        default="auto",
        choices=["auto", "mcq", "theory"],
        help="Module format (default: auto-detect from first 5 pages)",
    )
    sp.set_defaults(func=cmd_ingest_module)

    # Preview flow (Stage 2.4)
    sp = sub.add_parser(
        "preview",
        help="Generate a preview answer for a question (Stage 2.4)",
    )
    sp.add_argument("module", help="Module name (kebab-case slug)")
    sp.add_argument("--chapter", default="all", help="Chapter (e.g. 'chapter 1')")
    sp.add_argument(
        "--subject",
        default=None,
        help="Subject (psm, fmt, ...). If not given, read from extracted.json",
    )
    sp.add_argument(
        "--reanswer",
        action="store_true",
        help="Force regenerate, bypass cache",
    )
    sp.set_defaults(func=cmd_preview)

    sp = sub.add_parser(
        "approve",
        help="Approve the last preview, generate the rest (Stage 2.5)",
    )
    sp.set_defaults(func=cmd_approve)

    sp = sub.add_parser(
        "revise",
        help="Record a revision request for the last preview",
    )
    sp.add_argument("axis", choices=["wordcount", "format", "quality"])
    sp.add_argument("notes", help="Revision notes")
    sp.set_defaults(func=cmd_revise)

    sp = sub.add_parser("cancel", help="Cancel the current preview")
    sp.set_defaults(func=cmd_cancel)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
