"""Tests for medrack.answer.generate."""
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from medrack.answer.generate import generate_answer
from medrack.answer.llm import LLMResponse


MCQ_QUESTION = {
    "qid": "q001",
    "type": "mcq",
    "question_text": "Definition of health given by WHO does not include which of the following dimensions:",
    "options": {"a": "Social", "b": "Physical", "c": "Mental", "d": "Economic"},
    "answer": "d",
    "module_chapter": "chapter 1",
    "page_num": 1,
    "extraction_method": "regex",
}


MOCK_LLM_RESPONSE = LLMResponse(
    text="ANSWER: d\n\nREASONING: ...\n\nEXPLANATION: ...",
    prompt_tokens=500,
    completion_tokens=200,
    total_tokens=700,
    model="minimax-m3",
    latency_seconds=2.5,
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "index" / "chroma").mkdir(parents=True, exist_ok=True)
    (tmp_path / "answers").mkdir(parents=True, exist_ok=True)
    yield tmp_path


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.complete.return_value = MOCK_LLM_RESPONSE
    return client


def test_generate_mcq_answer_calls_llm(temp_home, mock_llm):
    answer = generate_answer(
        module_name="psm-module-1",
        subject="psm",
        chapter="chapter 1",
        question=MCQ_QUESTION,
        llm_client=mock_llm,
    )
    assert answer["qid"] == "q001"
    assert answer["module_name"] == "psm-module-1"
    assert answer["module_subject"] == "psm"
    assert "ANSWER: d" in answer["answer_text"]
    assert answer["model"] == "minimax-m3"
    assert answer["cache_hit"] is False
    assert mock_llm.complete.called


def test_generate_uses_mcq_prompt_for_mcq_question(temp_home, mock_llm):
    generate_answer(
        module_name="mod", subject="psm", chapter="ch1",
        question=MCQ_QUESTION, llm_client=mock_llm,
    )
    call_args = mock_llm.complete.call_args
    prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
    # MCQ prompt has "ANSWER:" and "OPTIONS:" sections
    assert "OPTIONS:" in prompt
    assert "a) Social" in prompt


def test_generate_uses_theory_prompt_for_theory_question(temp_home, mock_llm):
    from medrack import config
    theory_q = {**MCQ_QUESTION, "type": "theory", "options": {}, "answer": None}
    theory_q["question_text"] = "Discuss the social determinants of health."
    generate_answer(
        module_name="mod", subject="psm", chapter="ch1",
        question=theory_q, llm_client=mock_llm,
    )
    call_args = mock_llm.complete.call_args
    prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
    # Theory prompt has "Definition" section
    assert "Definition" in prompt
    # 10-mark (default) target is THEORY_LONG_TARGET_WORDS words (operator-set
    # via medrack.config; was 500, currently 775 per directive v1.0).
    assert str(config.THEORY_LONG_TARGET_WORDS) in prompt


def test_generate_returns_from_cache_on_second_call(temp_home, mock_llm):
    # First call: populates cache.
    answer1 = generate_answer(
        module_name="psm-module-1", subject="psm", chapter="ch1",
        question=MCQ_QUESTION, llm_client=mock_llm,
    )
    # Second call: should hit cache, NOT call LLM.
    mock_llm.reset_mock()
    answer2 = generate_answer(
        module_name="psm-module-1", subject="psm", chapter="ch1",
        question=MCQ_QUESTION, llm_client=mock_llm,
    )
    assert answer2["cache_hit"] is True
    assert not mock_llm.complete.called
    assert answer1["answer_text"] == answer2["answer_text"]


def test_generate_force_regenerate_bypasses_cache(temp_home, mock_llm):
    generate_answer(
        module_name="psm-module-1", subject="psm", chapter="ch1",
        question=MCQ_QUESTION, llm_client=mock_llm,
    )
    mock_llm.reset_mock()
    generate_answer(
        module_name="psm-module-1", subject="psm", chapter="ch1",
        question=MCQ_QUESTION, llm_client=mock_llm,
        force_regenerate=True,
    )
    assert mock_llm.complete.called


def test_generate_retrieval_chunks_populated(temp_home, mock_llm):
    # If we index a chunk, retrieval_chunks should be populated.
    # Phase 7: the chunk must have metadata matching the question's
    # detected section filter, otherwise the adaptive strategy's
    # filter would exclude it.
    from medrack.ingest.chunk import Chunk
    from medrack.ingest.metadata import ChunkMetadata, StructureMetadata
    chunk = Chunk(
        chunk_id="test-chunk-1",
        text="The WHO definition of health includes physical, mental, and social well-being.",
        subject="psm", book_id="b1", chapter_title="Concept of Health",
        page_start=12, page_end=14, token_count=15,
        metadata=ChunkMetadata(structure=StructureMetadata(section_definition=True)),
    )
    from medrack.ingest.embed import embed_chunks
    from medrack.ingest.index import index_chunks
    embed_chunks([chunk])
    index_chunks([chunk], subject="psm")

    answer = generate_answer(
        module_name="psm-module-1", subject="psm", chapter="ch1",
        question=MCQ_QUESTION, llm_client=mock_llm,
    )
    assert len(answer["retrieval_chunks"]) > 0
    assert answer["kb_chunks_retrieved"] > 0


def test_generate_handles_empty_retrieval(temp_home, mock_llm):
    """If no KB chunks are found, set used_general_fallback=True."""
    # Don't index any chunks. The kb_psm collection is empty (or just doesn't exist).
    answer = generate_answer(
        module_name="psm-module-1", subject="psm", chapter="ch1",
        question=MCQ_QUESTION, llm_client=mock_llm,
    )
    assert answer["used_general_fallback"] is True
    assert answer["kb_chunks_retrieved"] == 0
    assert answer["retrieval_chunks"] == []
