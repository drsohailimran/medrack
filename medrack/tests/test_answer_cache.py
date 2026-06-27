"""Tests for medrack.answer.cache."""
import json

import pytest

from medrack.answer.cache import (
    save_answer, load_answer, answer_path, cache_key_for_question
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "answers").mkdir(parents=True, exist_ok=True)
    yield tmp_path


SAMPLE_ANSWER = {
    "qid": "q001",
    "module_name": "test-mod",
    "module_subject": "psm",
    "question_text": "Q?",
    "question_type": "mcq",
    "module_chapter": "chapter 1",
    "answer_text": "The answer is X.",
    "retrieval_chunks": [],
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "model": "minimax-m3",
    "latency_seconds": 1.0,
    "cache_hit": False,
    "used_general_fallback": False,
    "kb_chunks_retrieved": 8,
    "generated_at": "2026-06-26T18:00:00Z"
}


def test_save_and_load_roundtrip(temp_home):
    save_answer("test-mod", "chapter 1", "q001", SAMPLE_ANSWER)
    loaded = load_answer("test-mod", "chapter 1", "q001")
    assert loaded == SAMPLE_ANSWER


def test_load_nonexistent_returns_none(temp_home):
    assert load_answer("test-mod", "chapter 1", "q999") is None


def test_atomic_write(temp_home):
    save_answer("test-mod", "chapter 1", "q001", SAMPLE_ANSWER)
    # No .tmp file left
    assert not (temp_home / "answers" / "test-mod" / "chapter 1" / "q001.json.tmp").exists()


def test_answer_path_creates_dirs(temp_home):
    p = answer_path("nested", "subdir", "q001")
    assert p.parent.is_dir()


def test_cache_key_is_deterministic():
    k1 = cache_key_for_question("mod", "q001", "Q?", "mcq", "minimax-m3")
    k2 = cache_key_for_question("mod", "q001", "Q?", "mcq", "minimax-m3")
    assert k1 == k2


def test_cache_key_changes_with_question_text():
    k1 = cache_key_for_question("mod", "q001", "Q1?", "mcq", "m")
    k2 = cache_key_for_question("mod", "q001", "Q2?", "mcq", "m")
    assert k1 != k2


def test_cache_key_changes_with_template():
    k1 = cache_key_for_question("mod", "q001", "Q?", "mcq", "m")
    k2 = cache_key_for_question("mod", "q001", "Q?", "theory", "m")
    assert k1 != k2


def test_cache_key_changes_with_model():
    k1 = cache_key_for_question("mod", "q001", "Q?", "mcq", "m1")
    k2 = cache_key_for_question("mod", "q001", "Q?", "mcq", "m2")
    assert k1 != k2
