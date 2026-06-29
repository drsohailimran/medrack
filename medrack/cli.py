"""
medrack CLI — entry point for the `medrack` command.

Stage 2.1 added `init`, `status`, `version`. Stage 2.2 / T10 adds
`ingest-book`, the end-to-end orchestrator for the KB ingest pipeline
(T1 format detection → T9 quality gate). Stage 2.3 / M6 adds
`ingest-module`, the end-to-end orchestrator for the module question
ingest pipeline (M1 module text extract → M5 module storage).
Stage 2.5 / B3 wires `medrack approve` to the batch orchestrator and
full PDF renderer, and adds the ``$MEDRACK_LLM_MODE=mock`` toggle that
swaps in ``MockLLMClient`` for offline / test runs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from . import config
from .config import Subject
from .orchestrate import (
    cmd_ingest_book,
    cmd_ingest_module,
    cmd_preview,
    cmd_approve,
    cmd_revise,
    cmd_cancel,
)


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
    else:
        books, modules = [], []
    from medrack.module.storage import list_modules
    disk_modules = list_modules()
    modules_by_id = {mod.get("module_id") or mod.get("name"): mod
                     for mod in modules}
    for dmod in disk_modules:
        if dmod["name"] not in modules_by_id:
            modules.append(dmod)
    active_books = [b for b in books if not b.get("archived_at")]
    active_modules = [m for m in modules if not m.get("archived_at")]
    print(f"  Books:   {len(active_books)} active, {len(books) - len(active_books)} archived")
    print(f"  Modules: {len(active_modules)} active, {len(modules) - len(active_modules)} archived")
    if not config.MANIFEST_PATH.exists() and (books or modules):
        print("  (no manifest on disk — counts taken from filesystem scan)")

    print(f"\nSubjects ({len(Subject)}): {', '.join(Subject.values())}")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    print(f"medrack {__version__}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Launch the Gradio dashboard on 127.0.0.1:7860."""
    from medrack.dashboard.app import main as dashboard_main
    return dashboard_main()


def cmd_bot(args: argparse.Namespace) -> int:
    """Launch the Telegram bot."""
    from medrack.bot.app import main as bot_main
    return bot_main()


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

    # Gradio dashboard (Stage 2.6 / D5)
    sp = sub.add_parser(
        "dashboard", help="Launch the Gradio dashboard (http://127.0.0.1:7860)"
    )
    sp.set_defaults(func=cmd_dashboard)

    # Telegram bot (Stage 2.7 / T5)
    sp = sub.add_parser(
        "bot", help="Launch the Telegram bot (requires TELEGRAM_BOT_TOKEN env var)"
    )
    sp.set_defaults(func=cmd_bot)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
