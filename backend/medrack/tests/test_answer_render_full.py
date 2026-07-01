"""Tests for medrack.answer.render_full."""
import os
import subprocess
from pathlib import Path

import pytest

from medrack.answer.render_full import render_full_module_pdf


@pytest.fixture
def output_path(tmp_path):
    return tmp_path / "full.pdf"


SAMPLE_BATCH_RESULT = type("BatchResult", (), {
    "module_name": "psm-module-1",
    "subject": "psm",
    "chapters": ["chapter 1"],
    "questions_total": 3,
    "questions_generated": 3,
    "questions_cached": 0,
    "questions_failed": 0,
    "total_tokens": 1800,
    "total_latency_seconds": 1.5,
    "elapsed_seconds": 2.3,
})()


SAMPLE_ANSWERS = [
    {
        "qid": "q001", "module_name": "psm-module-1", "module_subject": "psm",
        "question_text": "Question 1?", "question_type": "mcq",
        "module_chapter": "chapter 1",
        "answer_text": "ANSWER: a\n\nEXPLANATION: ...", "page_num": 1,
        "options": {"a": "Yes", "b": "No", "c": "Maybe", "d": "Unknown"},
        "retrieval_chunks": [], "model": "minimax-m3", "latency_seconds": 0.5,
    },
    {
        "qid": "q002", "module_name": "psm-module-1", "module_subject": "psm",
        "question_text": "Question 2?", "question_type": "mcq",
        "module_chapter": "chapter 1",
        "answer_text": "ANSWER: b", "page_num": 2,
        "options": {"a": "Yes", "b": "No", "c": "Maybe", "d": "Unknown"},
        "retrieval_chunks": [], "model": "minimax-m3", "latency_seconds": 0.5,
    },
    {
        "qid": "q003", "module_name": "psm-module-1", "module_subject": "psm",
        "question_text": "Question 3?", "question_type": "theory",
        "module_chapter": "chapter 1",
        "answer_text": "Definition: ...", "page_num": 3,
        "options": {},
        "retrieval_chunks": [], "model": "minimax-m3", "latency_seconds": 0.5,
    },
]


def test_renders_full_module_pdf(output_path):
    render_full_module_pdf(
        output_path,
        module_name="psm-module-1",
        subject="psm",
        batch_result=SAMPLE_BATCH_RESULT,
        answers=SAMPLE_ANSWERS,
    )
    assert output_path.is_file()
    with open(output_path, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_full_pdf_contains_all_question_answers(output_path):
    render_full_module_pdf(
        output_path,
        module_name="psm-module-1", subject="psm",
        batch_result=SAMPLE_BATCH_RESULT, answers=SAMPLE_ANSWERS,
    )
    result = subprocess.run(
        ["pdftotext", str(output_path), "-"],
        capture_output=True, text=True,
    )
    text = result.stdout
    # Each question's identifier should appear
    assert "q001" in text or "Question 1?" in text
    assert "q002" in text or "Question 2?" in text
    assert "q003" in text or "Question 3?" in text
    # Module name in the cover
    assert "psm-module-1" in text


def test_full_pdf_contains_cover_page(output_path):
    render_full_module_pdf(
        output_path,
        module_name="psm-module-1", subject="psm",
        batch_result=SAMPLE_BATCH_RESULT, answers=SAMPLE_ANSWERS,
    )
    result = subprocess.run(
        ["pdftotext", str(output_path), "-"],
        capture_output=True, text=True,
    )
    text = result.stdout
    # Cover page text: subject, "psm-module-1", total questions
    assert "psm" in text
    assert "3" in text  # total_questions


def test_full_pdf_creates_parent_directories(output_path):
    """render_full_module_pdf should create parent dirs if missing."""
    nested = output_path.parent / "nested" / "deep" / "module.pdf"
    render_full_module_pdf(
        nested,
        module_name="mod", subject="psm",
        batch_result=SAMPLE_BATCH_RESULT, answers=SAMPLE_ANSWERS,
    )
    assert nested.is_file()
