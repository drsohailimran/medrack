"""Tests for medrack.answer.batch."""
import time
from unittest.mock import MagicMock

import pytest

from medrack.answer.batch import generate_full_batch, BatchResult
from medrack.answer.llm import LLMResponse


def make_question(qid="q001", qtype="mcq", chapter="chapter 1"):
    return {
        "qid": qid,
        "type": qtype,
        "question_text": f"What is the answer to question {qid}?",
        "options": {"a": "Yes", "b": "No", "c": "Maybe", "d": "Unknown"} if qtype == "mcq" else {},
        "answer": "a" if qtype == "mcq" else None,
        "module_chapter": chapter,
        "page_num": 1,
        "extraction_method": "regex",
    }


def make_mock_llm():
    """Mock LLM that returns a deterministic answer per question."""
    client = MagicMock()
    def complete_side_effect(prompt, max_output_tokens=None):
        # Extract qid from prompt to make answer identifiable
        import re
        m = re.search(r"QUESTION:.*?(q\d+)", prompt, re.DOTALL)
        qid = m.group(1) if m else "q000"
        return LLMResponse(
            text=f"MOCK ANSWER for {qid}",
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            model="minimax-m3",
            latency_seconds=0.5,
        )
    client.complete.side_effect = complete_side_effect
    return client


def test_generates_answer_for_each_question(tmp_path):
    """Each question gets an answer (from cache or LLM)."""
    from medrack.answer.cache import save_answer
    llm = make_mock_llm()
    questions = [make_question(f"q{i:03d}") for i in range(1, 4)]
    result = generate_full_batch(
        module_name="mod", subject="psm",
        questions=questions, llm_client=llm,
    )
    assert result.questions_total == 3
    assert result.questions_generated == 3
    assert result.questions_cached == 0
    assert result.questions_failed == 0
    assert len(result.answers) == 3


def test_uses_cache_for_already_generated_questions(tmp_path):
    """If an answer is cached, don't call the LLM for it."""
    from medrack.answer.cache import save_answer
    from medrack.answer.generate import generate_answer
    llm = make_mock_llm()
    questions = [make_question(f"q{i:03d}") for i in range(1, 4)]

    # Pre-populate the cache for q001 only (calls the LLM once)
    generate_answer(
        module_name="mod", subject="psm", chapter="chapter 1",
        question=questions[0], llm_client=llm,
    )
    llm.complete.reset_mock()

    # Now run the batch — only q002 and q003 should hit the LLM
    result = generate_full_batch(
        module_name="mod", subject="psm",
        questions=questions, llm_client=llm,
    )
    assert result.questions_cached == 1
    assert result.questions_generated == 2
    assert llm.complete.call_count == 2


def test_force_regenerate_bypasses_cache(tmp_path):
    llm = make_mock_llm()
    questions = [make_question(f"q{i:03d}") for i in range(1, 3)]
    generate_full_batch(
        module_name="mod", subject="psm",
        questions=questions, llm_client=llm,
    )
    llm.complete.reset_mock()
    result = generate_full_batch(
        module_name="mod", subject="psm",
        questions=questions, llm_client=llm, force_regenerate=True,
    )
    assert result.questions_cached == 0
    assert result.questions_generated == 2


def test_chapter_filter_processes_only_matching_questions(tmp_path):
    llm = make_mock_llm()
    questions = [
        make_question("q001", chapter="chapter 1"),
        make_question("q002", chapter="chapter 2"),
        make_question("q003", chapter="chapter 1"),
    ]
    result = generate_full_batch(
        module_name="mod", subject="psm",
        questions=questions, llm_client=llm, chapter_filter="chapter 1",
    )
    assert result.questions_total == 2
    assert {a["qid"] for a in result.answers} == {"q001", "q003"}


def test_batch_records_token_usage_and_timing(tmp_path):
    llm = make_mock_llm()
    questions = [make_question(f"q{i:03d}") for i in range(1, 3)]
    result = generate_full_batch(
        module_name="mod", subject="psm",
        questions=questions, llm_client=llm,
    )
    assert result.total_tokens == 600 * 2  # 2 questions × 600 tokens
    assert result.total_latency_seconds == 0.5 * 2
    assert result.elapsed_seconds > 0
