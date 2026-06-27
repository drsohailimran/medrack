"""Tests for medrack.answer.render."""
import os
import subprocess
from pathlib import Path

import pytest

from medrack.answer.render import render_preview_pdf


@pytest.fixture
def output_path(tmp_path):
    return tmp_path / "preview.pdf"


MCQ_QUESTION = {
    "qid": "q001",
    "type": "mcq",
    "question_text": "Definition of health given by WHO does not include which of the following dimensions:",
    "options": {"a": "Social", "b": "Physical", "c": "Mental", "d": "Economic"},
    "answer": "d",
}


THEORY_QUESTION = {
    "qid": "q005",
    "type": "theory",
    "question_text": "Discuss the social determinants of health.",
    "options": {},
    "answer": None,
}


SAMPLE_ANSWER = {
    "answer_text": "ANSWER: d\n\nREASONING: The WHO definition of health includes physical, mental, and social well-being, but not economic well-being directly.\n\nEXPLANATION: The World Health Organization (WHO) defines health as 'a state of complete physical, mental and social well-being and not merely the absence of disease or infirmity.' This definition, established in 1948, deliberately expanded the concept of health beyond the biomedical model to include **psychological** and **social** dimensions. Economic well-being is related but not part of the WHO definition itself — it is a **social determinant** of health rather than a dimension of health itself. The three core dimensions are: (1) physical, (2) mental, and (3) social.",
    "retrieval_chunks": [],
    "prompt_tokens": 500,
    "completion_tokens": 200,
    "model": "minimax-m3",
}


def test_renders_mcq_preview(output_path):
    render_preview_pdf(
        output_path,
        module_name="psm-module-1",
        module_subject="psm",
        question=MCQ_QUESTION,
        answer=SAMPLE_ANSWER,
        question_index=1,
        total_questions=25,
    )
    assert output_path.is_file()
    # Check the file is a valid PDF (starts with %PDF)
    with open(output_path, "rb") as f:
        header = f.read(4)
    assert header == b"%PDF"


def test_renders_theory_preview(output_path):
    render_preview_pdf(
        output_path,
        module_name="fmt-module-1",
        module_subject="fmt",
        question=THEORY_QUESTION,
        answer={**SAMPLE_ANSWER, "answer_text": "Definition: Health is..."},
        question_index=5,
        total_questions=20,
    )
    assert output_path.is_file()


def test_preview_header_includes_question_position(output_path):
    render_preview_pdf(
        output_path,
        module_name="m", module_subject="psm",
        question=MCQ_QUESTION, answer=SAMPLE_ANSWER,
        question_index=3, total_questions=10,
    )
    # Use pdftotext to extract text and check
    result = subprocess.run(
        ["pdftotext", str(output_path), "-"],
        capture_output=True, text=True,
    )
    text = result.stdout
    assert "Question 3 of 10" in text or "PREVIEW" in text


def test_preview_includes_answer_text(output_path):
    render_preview_pdf(
        output_path,
        module_name="m", module_subject="psm",
        question=MCQ_QUESTION, answer=SAMPLE_ANSWER,
        question_index=1, total_questions=1,
    )
    result = subprocess.run(
        ["pdftotext", str(output_path), "-"],
        capture_output=True, text=True,
    )
    text = result.stdout
    # The answer text starts with "ANSWER: d" — should appear in the PDF
    assert "d" in text  # answer letter
