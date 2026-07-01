"""Tests for medrack.ingest.clean."""
from medrack.ingest.clean import clean_text, clean_pages


def test_collapses_letter_spacing():
    assert clean_text("D E P A R T M E N T") == "DEPARTMENT"
    assert clean_text("Def i n i t i o n") == "Definition"
    assert clean_text("a b c d e f g") == "a b c d e f g"  # all single letters, collapses


def test_does_not_collapse_normal_sentences():
    assert clean_text("This is a normal sentence.") == "This is a normal sentence."
    assert clean_text("I am a doctor.") == "I am a doctor."


def test_strips_pure_number_lines():
    text = "First paragraph.\n\n42\n\nSecond paragraph."
    assert "42" not in clean_text(text).split("\n\n")[1]


def test_strips_page_x_of_y_lines():
    text = "Content here.\n\nPage 1 of 50\n\nMore content."
    cleaned = clean_text(text)
    assert "Page 1 of 50" not in cleaned


def test_collapses_multiple_newlines():
    text = "Para 1.\n\n\n\n\nPara 2."
    assert clean_text(text) == "Para 1.\n\nPara 2."


def test_collapses_multiple_spaces():
    assert clean_text("Too    many    spaces.") == "Too many spaces."


def test_strips_trailing_whitespace_per_line():
    text = "Line 1   \nLine 2  \nLine 3"
    assert clean_text(text) == "Line 1\nLine 2\nLine 3"


def test_strips_outer_whitespace():
    assert clean_text("   \n\n  content  \n\n   ") == "content"


def test_clean_pages_updates_char_count():
    pages = [
        {"page_num": 1, "method": "text", "text": "D E P A R T M E N T", "char_count": 17},
        {"page_num": 2, "method": "text", "text": "  spaces  ", "char_count": 10},
    ]
    cleaned = clean_pages(pages)
    assert cleaned[0]["text"] == "DEPARTMENT"
    assert cleaned[0]["char_count"] == len(cleaned[0]["text"])
    assert cleaned[1]["text"] == "spaces"
    assert cleaned[1]["char_count"] == len(cleaned[1]["text"])


def test_handles_empty_text():
    assert clean_text("") == ""
    assert clean_text("\n\n\n") == ""
