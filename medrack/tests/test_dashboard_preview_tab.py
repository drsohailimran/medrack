"""Tests for the Preview tab handler."""
from unittest.mock import MagicMock, patch


def test_run_preview_with_no_module_returns_error():
    from medrack.dashboard.app import _run_preview_handler
    status, pdf = _run_preview_handler("", "all")
    assert "ERROR" in status
    assert pdf is None


def test_run_preview_with_placeholder_module_returns_error():
    from medrack.dashboard.app import _run_preview_handler
    status, pdf = _run_preview_handler("<no modules>", "all")
    assert "ERROR" in status


def test_run_preview_dispatches_to_cli(tmp_path):
    from medrack.dashboard.app import _run_preview_handler
    captured = {}
    def mock_preview(args):
        captured["args"] = args
        return 0
    state_data = {"module": "psm-module-1", "pdf_path": "/tmp/test.pdf"}
    with patch("medrack.dashboard.app.cli.cmd_preview", mock_preview):
        with patch("medrack.dashboard.app.cli._load_preview_state", return_value=state_data):
            status, pdf = _run_preview_handler("psm-module-1", "chapter 1")
    assert "test.pdf" in status
    assert pdf == "/tmp/test.pdf"
    assert captured["args"].module == "psm-module-1"
    assert captured["args"].chapter == "chapter 1"
