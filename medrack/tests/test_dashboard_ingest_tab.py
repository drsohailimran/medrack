"""Tests for the Ingest tab handlers."""
import argparse
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_ingest_kb_handler_with_no_file_returns_error():
    from medrack.dashboard.app import _ingest_kb_handler
    result = _ingest_kb_handler(None, "psm", "Book title", False)
    assert "ERROR" in result
    assert "no file" in result.lower()


def test_ingest_kb_handler_with_invalid_subject_returns_error():
    from medrack.dashboard.app import _ingest_kb_handler
    fake_file = MagicMock()
    fake_file.name = "/tmp/fake.pdf"
    result = _ingest_kb_handler(fake_file, "not_a_subject", "Book", False)
    assert "ERROR" in result
    assert "invalid subject" in result.lower()


def test_ingest_kb_handler_calls_cmd_ingest_book(tmp_path):
    from medrack.dashboard.app import _ingest_kb_handler
    from medrack.config import Subject
    fake_file = MagicMock()
    fake_file.name = str(tmp_path / "fake.pdf")
    (tmp_path / "fake.pdf").write_bytes(b"%PDF-1.4 fake")

    captured = {}
    def mock_ingest_book(args):
        captured["args"] = args
        return 0  # success

    with patch("medrack.dashboard.app.cli.cmd_ingest_book", mock_ingest_book):
        result = _ingest_kb_handler(fake_file, "psm", "My Book", True)
    assert result == "done"
    assert captured["args"].subject == "psm"
    assert captured["args"].book == "My Book"
    assert captured["args"].replace is True


def test_ingest_module_handler_with_no_file_returns_error():
    from medrack.dashboard.app import _ingest_module_handler
    result = _ingest_module_handler(None, "psm", "test-mod", "auto")
    assert "ERROR" in result
    assert "no file" in result.lower()


def test_ingest_module_handler_validates_kebab_case_name():
    from medrack.dashboard.app import _ingest_module_handler
    fake_file = MagicMock()
    fake_file.name = "/tmp/fake.pdf"
    result = _ingest_module_handler(fake_file, "psm", "BadName", "auto")
    assert "ERROR" in result
    assert "kebab" in result.lower()


def test_ingest_module_handler_calls_cmd_ingest_module():
    from medrack.dashboard.app import _ingest_module_handler
    fake_file = MagicMock()
    fake_file.name = "/tmp/fake.pdf"
    captured = {}
    def mock_ingest_module(args):
        captured["args"] = args
        return 0
    with patch("medrack.dashboard.app.cli.cmd_ingest_module", mock_ingest_module):
        result = _ingest_module_handler(fake_file, "psm", "good-name", "mcq")
    assert result == "done"
    assert captured["args"].subject == "psm"
    assert captured["args"].name == "good-name"
    assert captured["args"].format == "mcq"
