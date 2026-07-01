"""Tests for medrack.answer.cache."""
import json

import pytest

from medrack import config
from medrack.answer.cache import (
    save_answer, load_answer, answer_path, cache_key_for_question
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "answers").mkdir(parents=True, exist_ok=True)
    yield tmp_path


# Phase 3 (directive v1.0): a fresh-schema sample answer has the
# versions, target_word_count, and embedding_model fields set to the
# current config values. Such an answer is NOT stale on load.
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
    "generated_at": "2026-06-26T18:00:00Z",
    "package_version": "0.2.0",
    "versions": dict(config.PIPELINE_VERSIONS),
    "embedding_model": config.EMBEDDING_MODEL,
    "stale": False,
    "stale_reasons": [],
    "target_word_count": 275,
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


# ---------------------------------------------------------------------------
# Phase 3 (directive v1.0) — layered answer versioning tests
# ---------------------------------------------------------------------------


def test_load_marks_pre_phase3_cache_as_stale(temp_home):
    """A cache without versions/target_word_count is marked stale (not deleted)."""
    legacy = {
        "qid": "q001",
        "module_name": "test-mod",
        "answer_text": "old answer",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "model": "minimax-m3",
    }
    save_answer("test-mod", "chapter 1", "q001", legacy)
    loaded = load_answer("test-mod", "chapter 1", "q001")
    assert loaded is not None
    assert loaded["stale"] is True
    assert "missing_versions_field" in loaded["stale_reasons"]
    # Original data is still accessible
    assert loaded["answer_text"] == "old answer"


def test_load_marks_cache_with_old_embedding_model_as_stale(temp_home):
    """A cache with a different embedding model is marked stale."""
    legacy = dict(SAMPLE_ANSWER)
    legacy["embedding_model"] = "sentence-transformers/all-mpnet-base-v2"
    save_answer("test-mod", "chapter 1", "q001", legacy)
    loaded = load_answer("test-mod", "chapter 1", "q001")
    assert loaded is not None
    assert loaded["stale"] is True
    assert "embedding_model_drift" in loaded["stale_reasons"]


def test_load_does_not_drift_check_target_word_count(temp_home):
    """Phase 3: target_word_count is informational, not drift-checked.

    The drift is captured by the prompt_version field above; double-
    checking it would over-flag. This test pins the design decision.
    """
    legacy = dict(SAMPLE_ANSWER)
    legacy["target_word_count"] = 500  # old value
    save_answer("test-mod", "chapter 1", "q001", legacy)
    loaded = load_answer("test-mod", "chapter 1", "q001")
    assert loaded is not None
    # 500 != current 275, but the word count is NOT drift-checked
    # independently — the prompt_version field captures the drift.
    assert "target_word_count_drift" not in loaded["stale_reasons"]
    assert loaded["stale"] is False  # other fields are current


def test_load_does_not_modify_cache_file_on_disk(temp_home):
    """load_answer must not write back to the cache file (read-only operation)."""
    legacy = {
        "qid": "q001",
        "module_name": "test-mod",
        "answer_text": "x",
    }
    save_answer("test-mod", "chapter 1", "q001", legacy)
    path = temp_home / "answers" / "test-mod" / "chapter 1" / "q001.json"
    before = path.read_text()
    loaded = load_answer("test-mod", "chapter 1", "q001")
    assert loaded is not None
    after = path.read_text()
    # In-memory dict has stale annotation; on-disk file is unchanged.
    assert loaded["stale"] is True
    assert before == after


def test_cache_key_includes_subject():
    """Phase 3: cache_key_for_question separates PSM and FMT caches."""
    k_psm = cache_key_for_question("mod", "q001", "Q?", "theory", "m", subject="psm")
    k_fmt = cache_key_for_question("mod", "q001", "Q?", "theory", "m", subject="fmt")
    assert k_psm != k_fmt


def test_cache_key_includes_target_word_count():
    """Phase 3: cache_key_for_question separates 500-word and 775-word answers."""
    k_old = cache_key_for_question("mod", "q001", "Q?", "theory", "m", target_word_count=500)
    k_new = cache_key_for_question("mod", "q001", "Q?", "theory", "m", target_word_count=775)
    assert k_old != k_new


def test_cache_key_includes_pipeline_versions():
    """Phase 3: cache_key_for_question includes the PIPELINE_VERSIONS dict."""
    from medrack import config as _cfg
    original = dict(_cfg.PIPELINE_VERSIONS)
    try:
        k1 = cache_key_for_question("mod", "q001", "Q?", "theory", "m")
        # Bump schema version
        _cfg.PIPELINE_VERSIONS = {**original, "schema": original["schema"] + 1}
        k2 = cache_key_for_question("mod", "q001", "Q?", "theory", "m")
        assert k1 != k2
    finally:
        _cfg.PIPELINE_VERSIONS = original


def test_cache_key_default_subject_is_psm_for_backward_compat():
    """Phase 3: default subject='psm' keeps old call sites producing the same key prefix."""
    k_default = cache_key_for_question("mod", "q001", "Q?", "theory", "m")
    k_explicit = cache_key_for_question("mod", "q001", "Q?", "theory", "m", subject="psm")
    assert k_default == k_explicit


def test_cache_key_default_target_word_count_is_zero():
    """Phase 3: default target_word_count=None is encoded as 0 in the key."""
    k_default = cache_key_for_question("mod", "q001", "Q?", "theory", "m")
    k_explicit = cache_key_for_question("mod", "q001", "Q?", "theory", "m",
                                        target_word_count=0)
    assert k_default == k_explicit
