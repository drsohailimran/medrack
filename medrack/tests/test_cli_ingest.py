"""Tests for medrack.cli ingest-book."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

MEDRACK_BIN = "/home/sohail/.hermes/hermes-agent/venv/bin/medrack"

TEXT_PDF = "/home/sohail/medrack-samples/kb-chunks/Essentials_of_Forensic_Medicine(KS_Naray_chunk001_pages1-50.pdf"
SCAN_PDF = "/home/sohail/medrack-samples/kb-chunks/parks-textbook-of-preventive-and-social-_chunk001_pages1-50.pdf"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, r.stdout, r.stderr


def test_ingest_book_nonexistent_file_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, err = run([MEDRACK_BIN, "ingest-book", "/nonexistent.pdf",
                      "--subject", "psm", "--book", "Test"], env=env)
    assert rc != 0


def test_ingest_book_invalid_subject_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, err = run([MEDRACK_BIN, "ingest-book", TEXT_PDF,
                      "--subject", "biology", "--book", "Test"], env=env)
    assert rc != 0


def test_ingest_book_text_pdf_succeeds(tmp_path):
    """Happy path: text PDF → ingest → book in manifest."""
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, out, err = run([MEDRACK_BIN, "init"], env=env)
    assert rc == 0

    rc, out, err = run([MEDRACK_BIN, "ingest-book", TEXT_PDF,
                        "--subject", "fmt", "--book", "Narayan Reddy FMT"], env=env)
    assert rc == 0, f"ingest failed: {err}"
    assert "chunks" in out.lower() or "indexed" in out.lower()

    # Book should be in manifest
    rc, status, _ = run([MEDRACK_BIN, "status"], env=env)
    assert "Narayan Reddy FMT" in status or "1 active" in status
