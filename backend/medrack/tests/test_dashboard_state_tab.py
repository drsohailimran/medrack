"""Tests for the State tab handlers."""
import json
from pathlib import Path
from unittest.mock import patch


def test_load_manifest_returns_string(tmp_path):
    from medrack.dashboard.app import _load_manifest
    fake_manifest = tmp_path / "index" / "manifest.json"
    fake_manifest.parent.mkdir(parents=True)
    fake_manifest.write_text('{"books": []}')
    with patch("medrack.dashboard.app.get_manifest_path", return_value=fake_manifest):
        result = _load_manifest()
    assert "books" in result


def test_load_manifest_no_file_returns_placeholder():
    from medrack.dashboard.app import _load_manifest
    from pathlib import Path
    fake_manifest = Path("/tmp/does/not/exist/manifest.json")
    with patch("medrack.dashboard.app.get_manifest_path", return_value=fake_manifest):
        result = _load_manifest()
    assert "no manifest" in result.lower()


def test_load_batch_state_no_file_returns_placeholder():
    from medrack.dashboard.app import _load_batch_state
    with patch("medrack.dashboard.app.get_medrack_home") as mock_home:
        mock_home.return_value = Path("/tmp/does/not/exist")
        result = _load_batch_state()
    assert "no batch" in result.lower()


def test_list_cached_answers_empty_dir(tmp_path):
    from medrack.dashboard.app import _list_cached_answers
    with patch("medrack.dashboard.app.DATA_DIRS", {"answers": tmp_path}):
        rows = _list_cached_answers()
    assert "<no cached answers>" in rows[0][0]


def test_list_cached_answers_populated(tmp_path):
    from medrack.dashboard.app import _list_cached_answers
    # Create a fake cached answer
    ans_dir = tmp_path / "mod1" / "chapter 1"
    ans_dir.mkdir(parents=True)
    (ans_dir / "q001.json").write_text(json.dumps({
        "model": "minimax-m3", "total_tokens": 600,
    }))
    with patch("medrack.dashboard.app.DATA_DIRS", {"answers": tmp_path}):
        rows = _list_cached_answers()
    assert rows[0][0] == "mod1"
    assert rows[0][2] == "q001"
    assert rows[0][3] == "minimax-m3"
    assert rows[0][4] == "600"
