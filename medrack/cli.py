"""
medrack CLI — entry point for the `medrack` command.

Stage 2.1 added `init`, `status`, `version`. Stage 2.2 / T10 adds
`ingest-book`, the end-to-end orchestrator for the KB ingest pipeline
(T1 format detection → T9 quality gate).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
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

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
