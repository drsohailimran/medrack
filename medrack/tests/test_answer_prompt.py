"""Tests for medrack.answer.prompt."""
import tiktoken

from medrack.answer.prompt import (
    build_mcq_prompt, build_theory_prompt, format_options_for_prompt, estimate_tokens
)


def test_format_options_for_prompt():
    opts = {"a": "Social", "b": "Physical", "c": "Mental", "d": "Economic"}
    formatted = format_options_for_prompt(opts)
    lines = formatted.split("\n")
    assert lines == ["a) Social", "b) Physical", "c) Mental", "d) Economic"]


def test_build_mcq_prompt_includes_question():
    result = build_mcq_prompt(
        question_text="What is the capital of France?",
        options={"a": "London", "b": "Paris", "c": "Berlin", "d": "Madrid"},
        retrieved_chunks=["Geography is the study of land..."],
    )
    assert "What is the capital of France?" in result.prompt
    assert "London" in result.prompt
    assert "Paris" in result.prompt


def test_build_mcq_prompt_includes_chunks():
    chunks = [
        "The capital of France is Paris, a major European city.",
        "Geography covers the study of landforms and populations.",
    ]
    result = build_mcq_prompt(
        question_text="Q?",
        options={"a": "A", "b": "B"},
        retrieved_chunks=chunks,
    )
    for chunk in chunks:
        assert chunk in result.prompt


def test_build_mcq_prompt_includes_correct_letters():
    result = build_mcq_prompt(
        question_text="Q?",
        options={"a": "A", "b": "B", "c": "C", "d": "D"},
        retrieved_chunks=[],
    )
    assert "a, b, c, d" in result.prompt


def test_build_mcq_prompt_system_template_is_mcq():
    result = build_mcq_prompt("Q?", {"a": "A"}, [])
    assert result.system_template == "mcq"


def test_build_mcq_prompt_token_estimate_positive():
    result = build_mcq_prompt("Q?", {"a": "A"}, ["chunk text"])
    assert result.prompt_tokens_estimate > 0


def test_build_theory_prompt_includes_question():
    result = build_theory_prompt(
        question_text="Discuss the impact of poverty on health.",
        retrieved_chunks=["Poverty is a major social determinant..."],
        word_count_target=1500,
    )
    assert "Discuss the impact of poverty on health." in result.prompt
    assert "1500" in result.prompt  # word target
    assert "Definition" in result.prompt  # section heading


def test_build_theory_prompt_includes_chunks():
    chunks = ["Poverty is a major social determinant.", "Health is a state of complete well-being."]
    result = build_theory_prompt("Q?", chunks)
    for chunk in chunks:
        assert chunk in result.prompt


def test_build_theory_prompt_system_template_is_theory():
    result = build_theory_prompt("Q?", [])
    assert result.system_template == "theory"


def test_estimate_tokens_uses_tiktoken():
    n = estimate_tokens("Hello, world!")
    enc = tiktoken.get_encoding("cl100k_base")
    assert n == len(enc.encode("Hello, world!"))
