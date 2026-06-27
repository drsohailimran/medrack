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
    # Use pdftotext to extract text and check the new layout has the
    # question number rendered ("Q1." since MCQ_QUESTION.qid = "q001").
    result = subprocess.run(
        ["pdftotext", str(output_path), "-"],
        capture_output=True, text=True,
    )
    text = result.stdout
    # The qid in MCQ_QUESTION is "q001" so the displayed number is Q1.
    assert "Q1." in text or "Question:" in text


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


# ---------------------------------------------------------------------------
# Block parser tests (for the v2 fix that splits bullets / headings /
# sub-bullets instead of squashing everything into one Paragraph).
# ---------------------------------------------------------------------------

from medrack.answer.render import _classify_line, _split_answer_blocks


def test_classify_main_bullet():
    kind, content = _classify_line("\u2022 Some bullet text (Park 27e)")
    assert kind == "main_bullet"
    assert "Some bullet text" in content
    assert "(Park 27e)" in content


def test_classify_sub_bullet_en_dash():
    kind, content = _classify_line("  \u2013 Limitations: inapplicable to NCDs.")
    assert kind == "sub_bullet"
    assert "Limitations" in content


def test_classify_sub_bullet_ascii_dash():
    # Some LLMs emit ASCII "-" for sub-bullets; treat as sub-bullet too.
    kind, content = _classify_line("- Limitation: small sample size.")
    assert kind == "sub_bullet"


def test_classify_heading_strips_markdown_hashes():
    kind, content = _classify_line("### Bradford Hill's Criteria for Causality")
    assert kind == "heading"
    assert "Bradford Hill" in content
    assert "#" not in content


def test_classify_heading_plain():
    kind, content = _classify_line("Definition")
    assert kind == "heading"


def test_classify_paragraph_long():
    kind, content = _classify_line(
        "This is a long sentence that should be treated as a paragraph, not a heading."
    )
    assert kind == "paragraph"


def test_classify_blank():
    kind, content = _classify_line("   ")
    assert kind == "blank"
    assert content == ""


def test_split_blocks_preserves_order():
    text = (
        "\u2022 First bullet.\n"
        "\u2022 Second bullet.\n"
        "\n"
        "Definition\n"
        "\u2022 A definition here.\n"
        "\n"
        "### Evolution\n"
        "\u2022 Henle-Koch.\n"
    )
    blocks = _split_answer_blocks(text)
    kinds = [k for k, _ in blocks]
    assert kinds == [
        "main_bullet", "main_bullet",
        "heading",
        "main_bullet",
        "heading",
        "main_bullet",
    ]
    # Headings should not contain "###"
    assert "###" not in blocks[2][1]
    assert "###" not in blocks[4][1]


def test_split_blocks_sub_bullet_indented():
    text = "\u2022 Top bullet.\n  \u2013 Sub bullet one.\n  \u2013 Sub bullet two.\n"
    blocks = _split_answer_blocks(text)
    assert [k for k, _ in blocks] == ["main_bullet", "sub_bullet", "sub_bullet"]


def test_render_preview_handles_markdown_heading_in_answer(tmp_path):
    """End-to-end: an answer that includes ### headings should render
    the heading without the ### prefix."""
    answer_with_hash = {
        "answer_text": (
            "\u2022 First bullet (Park 27e).\n"
            "\n"
            "### Sub Topic\n"
            "\u2022 Second bullet (WHO).\n"
        )
    }
    out = tmp_path / "test_hash.pdf"
    render_preview_pdf(
        out, module_name="test", module_subject="psm",
        question=MCQ_QUESTION, answer=answer_with_hash,
        question_index=1, total_questions=1,
    )
    result = subprocess.run(
        ["pdftotext", str(out), "-"], capture_output=True, text=True
    )
    assert "###" not in result.stdout, f"### leaked into PDF: {result.stdout!r}"
    assert "Sub Topic" in result.stdout
