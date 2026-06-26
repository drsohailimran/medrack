"""
medrack CLI — entry point for the `medrack` command.

Stage 2.1 scope: just `init`, `status`, and `version`. Other subcommands
are added in later stages (see plan section 13.5).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import config
from .config import Subject


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

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
