"""Tests for the Modules tab handlers."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_list_modules_returns_2d_list():
    from medrack.dashboard.app import _list_modules_handler
    with patch("medrack.dashboard.app.list_modules", return_value=[]):
        rows = _list_modules_handler()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    # Empty case: should have a placeholder row
    assert "<no modules" in rows[0][0]


def test_list_modules_populates_from_extracted_json(tmp_path):
    from medrack.dashboard.app import _list_modules_handler
    # Create a fake module
    module_dir = tmp_path / "modules" / "psm" / "psm-module-1"
    module_dir.mkdir(parents=True)
    (module_dir / "extracted.json").write_text(json.dumps({
        "questions": [],
        "metadata": {
            "module_name": "psm-module-1",
            "subject": "psm",
            "format": "mcq",
            "questions_extracted": 42,
            "chapters": ["chapter 1"],
        },
    }))
    with patch("medrack.config.get_medrack_home", return_value=tmp_path):
        with patch("medrack.dashboard.app.list_modules", return_value=[("psm", "psm-module-1")]):
            rows = _list_modules_handler()
    assert rows[0][0] == "psm-module-1"
    assert rows[0][1] == "psm"
    assert rows[0][2] == "mcq"
    assert rows[0][3] == "42"


def test_action_button_with_no_module_returns_error():
    from medrack.dashboard.app import _action_button_handler
    result = _action_button_handler("", "preview")
    assert "ERROR" in result
    result = _action_button_handler("<no modules>", "preview")
    assert "ERROR" in result


def test_action_button_dispatches_to_cli(tmp_path):
    from medrack.dashboard.app import _action_button_handler
    captured = {}
    def mock_preview(args):
        captured["args"] = args
        return 0
    with patch("medrack.dashboard.app.orchestrate.cmd_preview", mock_preview):
        result = _action_button_handler("psm-module-1", "preview")
    assert "preview" in result
    assert "rc=0" in result
    assert captured["args"].module == "psm-module-1"


def test_action_button_unknown_action_returns_error():
    from medrack.dashboard.app import _action_button_handler
    result = _action_button_handler("psm-module-1", "frobnicate")
    assert "ERROR" in result
    assert "unknown" in result.lower()
