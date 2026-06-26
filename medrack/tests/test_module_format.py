"""Tests for medrack.module.format."""
from medrack.module.format import detect_module_format, is_mcq_module


def make_page(num, text):
    return {"page_num": num, "method": "text", "text": text, "char_count": len(text)}


def test_mcq_module_detected():
    pages = [
        make_page(1, "1. Q? (a) A (b) B (c) C (d) D. Key:a"),
        make_page(2, "2. Q? (a) A (b) B (c) C (d) D. Key:b"),
        make_page(3, "3. Q? (a) A (b) B (c) C (d) D. Key:c"),
    ]
    assert detect_module_format(pages) == "mcq"
    assert is_mcq_module(pages) is True


def test_theory_module_detected():
    pages = [
        make_page(1, "Discuss the impact of poverty on health."),
        make_page(2, "Describe the role of WHO in global health."),
        make_page(3, "Explain the concept of primary health care."),
    ]
    assert detect_module_format(pages) == "theory"


def test_empty_pages_default_to_mcq():
    assert detect_module_format([]) == "mcq"


def test_real_psm_module_is_mcq():
    """PSM Module 1 is the MCQ format we've seen."""
    from pathlib import Path
    from medrack.module.extract import extract_module_pages
    pages = extract_module_pages(Path("/home/sohail/medrack-samples/modules/MODULE 1-1.pdf"))
    assert detect_module_format(pages[:5]) == "mcq"


def test_ambiguous_content_defaults_to_mcq():
    """When neither pattern is dominant, default to MCQ (most MBBS modules)."""
    pages = [make_page(1, "Some text with one (a) reference.")]
    assert detect_module_format(pages) == "mcq"
