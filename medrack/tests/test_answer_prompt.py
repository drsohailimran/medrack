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


# ---------------------------------------------------------------------------
# Phase 2 (directive v1.0) — subject-aware prompt tests
# ---------------------------------------------------------------------------


def test_build_theory_prompt_uses_psm_context_by_default():
    """Default subject='psm' embeds PSM-specific language."""
    result = build_theory_prompt(
        question_text="What is the IMR in India?",
        retrieved_chunks=[],
        word_count_target=775,
    )
    assert result.subject == "psm"
    assert "PSM / Community Medicine" in result.prompt
    assert "K. Park" in result.prompt
    # PSM-specific framework
    assert "Park's framework" in result.prompt
    # PSM-specific data sources
    assert "NFHS" in result.prompt


def test_build_theory_prompt_uses_fmt_context_when_subject_fmt():
    """subject='fmt' embeds Forensic Medicine-specific language."""
    result = build_theory_prompt(
        question_text="Discuss the procedure for conducting a magisterial inquest.",
        retrieved_chunks=[],
        word_count_target=775,
        subject="fmt",
    )
    assert result.subject == "fmt"
    assert "Forensic Medicine" in result.prompt
    assert "Narayan Reddy" in result.prompt
    # FMT-specific legislation
    assert "CrPC" in result.prompt or "IPC" in result.prompt
    # FMT-specific framework (no PSM-specific framework words)
    assert "Park's framework" not in result.prompt
    # FMT-specific data sources
    assert "ICMR" in result.prompt


def test_build_mcq_prompt_uses_fmt_context_when_subject_fmt():
    """MCQ prompt also subject-aware."""
    result = build_mcq_prompt(
        question_text="Best preservative for viscera?",
        options={"a": "Formalin", "b": "Sodium chloride", "c": "Alcohol", "d": "Refrigeration"},
        retrieved_chunks=[],
        subject="fmt",
    )
    assert result.subject == "fmt"
    assert "Forensic Medicine" in result.prompt
    assert "Narayan Reddy" in result.prompt
    assert "Park's framework" not in result.prompt


def test_build_theory_prompt_falls_back_to_generic_for_unknown_subject():
    """Unknown subjects fall back to the 'generic' context, not PSM."""
    result = build_theory_prompt(
        question_text="Discuss a topic from medicine.",
        retrieved_chunks=[],
        word_count_target=775,
        subject="medicine",  # not yet in SUBJECT_CONTEXTS
    )
    # subject is reported as the *requested* key, not the fallback key
    assert result.subject == "medicine"
    # The generic context doesn't include "Park" or "Narayan Reddy"
    assert "K. Park" not in result.prompt
    assert "Narayan Reddy" not in result.prompt
    # It uses the generic reference text
    assert "standard MBBS textbook" in result.prompt


def test_build_theory_prompt_word_count_matches_config_for_marks_5():
    """marks=5 should use THEORY_SHORT_TARGET_WORDS (475)."""
    result = build_theory_prompt(
        question_text="Briefly discuss the role of ASHA.",
        retrieved_chunks=[],
        marks=5,
    )
    from medrack import config
    assert str(config.THEORY_SHORT_TARGET_WORDS) in result.prompt
    assert "5-mark" in result.prompt


def test_build_theory_prompt_word_count_matches_config_for_marks_10():
    """marks=10 should use THEORY_LONG_TARGET_WORDS (775)."""
    result = build_theory_prompt(
        question_text="Discuss the epidemiology of tuberculosis in India.",
        retrieved_chunks=[],
        marks=10,
    )
    from medrack import config
    assert str(config.THEORY_LONG_TARGET_WORDS) in result.prompt
    assert "10-mark" in result.prompt


def test_build_result_subject_field_is_set():
    """BuildResult.subject should be set so callers can log/audit it."""
    r_psm = build_theory_prompt("Q?", [], subject="psm")
    r_fmt = build_theory_prompt("Q?", [], subject="fmt")
    assert r_psm.subject == "psm"
    assert r_fmt.subject == "fmt"


def test_subject_contexts_psm_and_fmt_are_distinct():
    """Defensive: PSM and FMT contexts must be visibly different."""
    from medrack.config import SUBJECT_CONTEXTS
    psm = SUBJECT_CONTEXTS["psm"]
    fmt = SUBJECT_CONTEXTS["fmt"]
    assert psm["display"] != fmt["display"]
    assert psm["reference_text"] != fmt["reference_text"]
    assert psm["framework"] != fmt["framework"]
    # Both share at least one source (ICMR) but differ in dominant context
    assert "ICMR" in psm["key_sources"]
    assert "ICMR" in fmt["key_sources"]
    # PSM has NFHS (an Indian survey), FMT doesn't
    assert "NFHS" in psm["key_sources"]
    assert "NFHS" not in fmt["key_sources"]
