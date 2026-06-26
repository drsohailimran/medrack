"""Tests for medrack.module.mcq."""
from medrack.module.mcq import extract_mcqs_from_pages, regex_extraction_coverage


def make_page(num, text):
    return {"page_num": num, "method": "text", "text": text, "char_count": len(text)}


def test_extracts_simple_mcq():
    page = make_page(1, "1. The sky is (a) green (b) blue (c) red (d) yellow. Key:b")
    qs = extract_mcqs_from_pages([page])
    assert len(qs) == 1
    assert qs[0].type == "mcq"
    assert qs[0].question_text.startswith("The sky is")
    assert qs[0].options == {"a": "green", "b": "blue", "c": "red", "d": "yellow"}
    assert qs[0].answer == "b"
    assert qs[0].qid == "q001"
    assert qs[0].page_num == 1


def test_extracts_multiple_mcqs_on_same_page():
    text = (
        "1. The sky is (a) green (b) blue. Key:a\n"
        "2. Grass is (a) green (b) blue. Key:a\n"
        "3. Fire is (a) cold (b) hot. Key:b"
    )
    page = make_page(1, text)
    qs = extract_mcqs_from_pages([page])
    assert len(qs) == 3
    assert [q.qid for q in qs] == ["q001", "q002", "q003"]
    assert [q.answer for q in qs] == ["a", "a", "b"]


def test_extracts_from_real_psm_module():
    """End-to-end on the real PSM Module 1 PDF (text-extractable)."""
    from pathlib import Path
    from medrack.module.extract import extract_module_pages
    pages = extract_module_pages(Path("/home/sohail/medrack-samples/modules/MODULE 1-1.pdf"))
    qs = extract_mcqs_from_pages(pages)
    # The first question is "Definition of health given by WHO does not include..."
    assert len(qs) >= 10  # at least 10 MCQs across 55 pages
    assert any("health" in q.question_text.lower() for q in qs)
    # All questions should have at least 2 options
    for q in qs:
        assert q.type == "mcq"
        assert len(q.options) >= 2


def test_options_extracted_with_different_separators():
    """Options may be separated by spaces, not just by `)(`."""
    page = make_page(1, "1. Pick (a) one (b) two (c) three (d) four. Key:c")
    qs = extract_mcqs_from_pages([page])
    assert qs[0].options == {"a": "one", "b": "two", "c": "three", "d": "four"}


def test_answer_extracted_with_key_prefix():
    page = make_page(1, "1. Q? (a) A (b) B. Key:b")
    assert extract_mcqs_from_pages([page])[0].answer == "b"


def test_answer_extracted_with_answer_prefix():
    page = make_page(1, "1. Q? (a) A (b) B. Answer: a")
    assert extract_mcqs_from_pages([page])[0].answer == "a"


def test_no_answer_returns_none():
    page = make_page(1, "1. Q? (a) A (b) B. No key here.")
    assert extract_mcqs_from_pages([page])[0].answer is None


def test_question_with_no_options_becomes_theory_type():
    page = make_page(1, "1. Discuss the impact of X on Y.")
    qs = extract_mcqs_from_pages([page])
    assert qs[0].type == "theory"
    assert qs[0].options == {}


def test_qids_are_sequential():
    text = "1. Q1? (a) A (b) B. Key:a\n" * 5
    qs = extract_mcqs_from_pages([make_page(1, text)])
    assert [q.qid for q in qs] == ["q001", "q002", "q003", "q004", "q005"]


def test_coverage_returns_fraction():
    page_with_qs = make_page(1, "1. Q? (a) A (b) B. Key:a")
    page_without = make_page(2, "Just some text without questions here.")
    coverage = regex_extraction_coverage([page_with_qs, page_without])
    assert coverage == 0.5


def test_coverage_empty_pages():
    assert regex_extraction_coverage([]) == 0.0
