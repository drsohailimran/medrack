"""Tests for medrack.answer.versioning (Phase 3 — layered answer versioning)."""
import json
import pytest

from medrack import config
from medrack.answer.cache import save_answer
from medrack.answer.versioning import (
    is_stale,
    mark_stale,
    find_stale_answers,
    REASON_SCHEMA_DRIFT,
    REASON_PROMPT_DRIFT,
    REASON_RETRIEVAL_DRIFT,
    REASON_RENDERER_DRIFT,
    REASON_MISSING_VERSIONS,
    REASON_EMBEDDING_MODEL_DRIFT,
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "answers").mkdir(parents=True, exist_ok=True)
    yield tmp_path


def _fresh_answer(qid: str = "q001", target_word_count: int = 775) -> dict:
    """A current-schema answer that should NOT be stale."""
    return {
        "qid": qid,
        "module_name": "test-mod",
        "module_subject": "psm",
        "question_text": "Q?",
        "question_type": "theory",
        "module_chapter": "chapter 1",
        "answer_text": "An answer.",
        "retrieval_chunks": [],
        "prompt_tokens": 7000,
        "completion_tokens": 1000,
        "total_tokens": 8000,
        "model": "qwen3.7-max",
        "latency_seconds": 5.0,
        "cache_hit": False,
        "used_general_fallback": False,
        "kb_chunks_retrieved": 8,
        "generated_at": "2026-06-29T16:00:00Z",
        "package_version": "0.2.0",
        "versions": dict(config.PIPELINE_VERSIONS),
        "embedding_model": config.EMBEDDING_MODEL,
        "stale": False,
        "stale_reasons": [],
        "target_word_count": target_word_count,
    }


# ---------------------------------------------------------------------------
# is_stale
# ---------------------------------------------------------------------------


def test_is_stale_returns_false_for_fresh_answer():
    fresh = _fresh_answer()
    stale, reasons = is_stale(fresh)
    assert stale is False
    assert reasons == []


def test_is_stale_flags_missing_versions_field():
    """Pre-Phase-3 cache: no versions dict at all."""
    legacy = {"qid": "q001", "answer_text": "old"}
    stale, reasons = is_stale(legacy)
    assert stale is True
    assert REASON_MISSING_VERSIONS in reasons


def test_is_stale_flags_schema_version_drift():
    answer = _fresh_answer()
    answer["versions"] = {**config.PIPELINE_VERSIONS, "schema": 1}
    stale, reasons = is_stale(answer)
    assert stale is True
    assert "schema_version_drift" in reasons


def test_is_stale_flags_prompt_version_drift():
    answer = _fresh_answer()
    answer["versions"] = {**config.PIPELINE_VERSIONS, "prompt": 0}
    stale, reasons = is_stale(answer)
    assert stale is True
    assert "prompt_version_drift" in reasons


def test_is_stale_flags_renderer_version_drift():
    answer = _fresh_answer()
    answer["versions"] = {**config.PIPELINE_VERSIONS, "renderer": 0}
    stale, reasons = is_stale(answer)
    assert stale is True
    assert "renderer_version_drift" in reasons


def test_is_stale_does_not_flag_unimplemented_components():
    """Components at version 0 (not yet implemented) should not be flagged."""
    answer = _fresh_answer()
    # planner/reranker remain at 0; validator is implemented (P0, v1).
    # Omitting still-zero components must not mark the answer stale.
    answer["versions"] = {
        k: v for k, v in config.PIPELINE_VERSIONS.items()
        if k not in ("planner", "reranker")
    }
    stale, reasons = is_stale(answer)
    assert stale is False, f"unexpectedly stale: {reasons}"


def test_is_stale_flags_embedding_model_drift():
    answer = _fresh_answer()
    answer["embedding_model"] = "sentence-transformers/all-mpnet-base-v2"
    stale, reasons = is_stale(answer)
    assert stale is True
    assert REASON_EMBEDDING_MODEL_DRIFT in reasons


def test_is_stale_collects_multiple_reasons():
    answer = _fresh_answer()
    answer["versions"] = {**config.PIPELINE_VERSIONS, "schema": 0, "prompt": 0}
    answer["embedding_model"] = "different-model"
    stale, reasons = is_stale(answer)
    assert stale is True
    assert "schema_version_drift" in reasons
    assert "prompt_version_drift" in reasons
    assert REASON_EMBEDDING_MODEL_DRIFT in reasons


# ---------------------------------------------------------------------------
# mark_stale
# ---------------------------------------------------------------------------


def test_mark_stale_returns_copy_with_annotation():
    fresh = _fresh_answer()
    marked = mark_stale(fresh)
    # Original is unchanged
    assert fresh["stale"] is False
    assert fresh["stale_reasons"] == []
    # Marked copy has the annotation
    assert marked["stale"] is False  # this one is still fresh
    assert marked["stale_reasons"] == []


def test_mark_stale_annotates_stale_answers():
    legacy = {"qid": "q001", "answer_text": "x"}
    marked = mark_stale(legacy)
    assert marked["stale"] is True
    assert REASON_MISSING_VERSIONS in marked["stale_reasons"]


def test_mark_stale_does_not_mutate_input():
    legacy = {"qid": "q001", "answer_text": "x"}
    snapshot = json.dumps(legacy, sort_keys=True)
    mark_stale(legacy)
    assert json.dumps(legacy, sort_keys=True) == snapshot


# ---------------------------------------------------------------------------
# find_stale_answers
# ---------------------------------------------------------------------------


def test_find_stale_answers_returns_empty_for_empty_dir(temp_home):
    assert find_stale_answers(answers_root=temp_home / "answers") == []


def test_find_stale_answers_returns_empty_for_missing_dir(temp_home):
    assert find_stale_answers(answers_root=temp_home / "nonexistent") == []


def test_find_stale_answers_returns_empty_when_all_fresh(temp_home):
    save_answer("mod-a", "ch1", "q001", _fresh_answer("q001"))
    save_answer("mod-a", "ch1", "q002", _fresh_answer("q002"))
    stale = find_stale_answers(answers_root=temp_home / "answers")
    assert stale == []


def test_find_stale_answers_finds_legacy_caches(temp_home):
    """Pre-Phase-3 caches are reported as stale (not deleted)."""
    save_answer("mod-a", "ch1", "q001", {"qid": "q001", "answer_text": "x"})
    save_answer("mod-a", "ch1", "q002", _fresh_answer("q002"))
    stale = find_stale_answers(answers_root=temp_home / "answers")
    assert len(stale) == 1
    entry = stale[0]
    assert entry["module"] == "mod-a"
    assert entry["chapter"] == "ch1"
    assert entry["qid"] == "q001"
    assert REASON_MISSING_VERSIONS in entry["reasons"]


def test_find_stale_answers_finds_version_drift(temp_home):
    answer = _fresh_answer()
    answer["versions"] = {**config.PIPELINE_VERSIONS, "prompt": 0}
    save_answer("mod-a", "ch1", "q001", answer)
    save_answer("mod-a", "ch1", "q002", _fresh_answer("q002"))
    stale = find_stale_answers(answers_root=temp_home / "answers")
    assert len(stale) == 1
    assert stale[0]["qid"] == "q001"
    assert "prompt_version_drift" in stale[0]["reasons"]


def test_find_stale_answers_scans_multiple_modules(temp_home):
    save_answer("mod-a", "ch1", "q001", _fresh_answer("q001"))
    save_answer("mod-b", "ch1", "q001", {"qid": "q001", "answer_text": "x"})
    save_answer("mod-b", "ch1", "q002", _fresh_answer("q002"))
    stale = find_stale_answers(answers_root=temp_home / "answers")
    assert len(stale) == 1
    assert stale[0]["module"] == "mod-b"


def test_find_stale_answers_filtered_by_module(temp_home):
    save_answer("mod-a", "ch1", "q001", {"qid": "q001", "answer_text": "x"})
    save_answer("mod-b", "ch1", "q001", {"qid": "q001", "answer_text": "y"})
    # Filter to mod-a only
    stale = find_stale_answers(module_name="mod-a", answers_root=temp_home / "answers")
    assert len(stale) == 1
    assert stale[0]["module"] == "mod-a"


def test_find_stale_answers_does_not_delete_files(temp_home):
    """The version check must be read-only — the cache file is preserved."""
    legacy = {"qid": "q001", "answer_text": "x"}
    save_answer("mod-a", "ch1", "q001", legacy)
    path = temp_home / "answers" / "mod-a" / "ch1" / "q001.json"
    assert path.exists()
    find_stale_answers(answers_root=temp_home / "answers")
    # File is still on disk with original content
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk == legacy  # not annotated; staleness is in-memory only


def test_find_stale_answers_handles_corrupt_files(temp_home):
    """A corrupt JSON file is reported as stale with a distinct reason, not deleted."""
    answer_dir = temp_home / "answers" / "mod-a" / "ch1"
    answer_dir.mkdir(parents=True, exist_ok=True)
    corrupt = answer_dir / "q001.json"
    corrupt.write_text("{ not valid json")
    stale = find_stale_answers(answers_root=temp_home / "answers")
    assert len(stale) == 1
    assert "corrupt_file" in stale[0]["reasons"][0]
    # Corrupt file is not deleted
    assert corrupt.exists()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_reason_constants_are_unique_strings():
    reasons = [
        REASON_SCHEMA_DRIFT, REASON_PROMPT_DRIFT, REASON_RETRIEVAL_DRIFT,
        REASON_RENDERER_DRIFT, REASON_MISSING_VERSIONS,
        REASON_EMBEDDING_MODEL_DRIFT,
    ]
    assert len(reasons) == len(set(reasons))  # all unique
    # All are non-empty strings
    for r in reasons:
        assert isinstance(r, str) and r
