"""Tests for medrack.module.storage."""
import json

import pytest

from medrack.module.storage import (
    save_extracted, load_extracted, list_modules, module_dir, extracted_json_path
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "modules").mkdir(parents=True, exist_ok=True)
    yield tmp_path


SAMPLE_DATA = {
    "questions": [
        {"qid": "q001", "type": "mcq", "question_text": "Q?",
         "options": {"a": "A", "b": "B"}, "answer": "a",
         "page_num": 1, "extraction_method": "regex"}
    ],
    "metadata": {
        "module_name": "test-mod",
        "subject": "psm",
        "title": "Test Module",
        "format": "mcq",
        "total_pages": 10,
        "questions_extracted": 1,
        "extracted_at": "2026-06-26T16:00:00Z"
    }
}


def test_module_dir_creates_directory(temp_home):
    d = module_dir("psm", "test-mod")
    assert d.is_dir()
    assert d == temp_home / "modules" / "psm" / "test-mod"


def test_save_and_load_roundtrip(temp_home):
    save_extracted("psm", "test-mod", SAMPLE_DATA)
    loaded = load_extracted("psm", "test-mod")
    assert loaded == SAMPLE_DATA


def test_load_nonexistent_returns_none(temp_home):
    assert load_extracted("psm", "nonexistent") is None


def test_atomic_write_does_not_leave_tmp(temp_home):
    save_extracted("psm", "test-mod", SAMPLE_DATA)
    assert not (temp_home / "modules" / "psm" / "test-mod" / "extracted.json.tmp").exists()


def test_list_modules_returns_metadata(temp_home):
    save_extracted("psm", "mod-a", SAMPLE_DATA)
    save_extracted("psm", "mod-b", SAMPLE_DATA)
    save_extracted("fmt", "mod-c", SAMPLE_DATA)
    all_mods = list_modules()
    assert len(all_mods) == 3
    names = {m["name"] for m in all_mods}
    assert names == {"mod-a", "mod-b", "mod-c"}


def test_list_modules_filters_by_subject(temp_home):
    save_extracted("psm", "mod-a", SAMPLE_DATA)
    save_extracted("fmt", "mod-b", SAMPLE_DATA)
    psm_mods = list_modules(subject="psm")
    assert len(psm_mods) == 1
    assert psm_mods[0]["name"] == "mod-a"
    assert psm_mods[0]["subject"] == "psm"


def test_extracted_json_path(temp_home):
    p = extracted_json_path("psm", "test-mod")
    assert p.name == "extracted.json"
    assert p.parent.name == "test-mod"
