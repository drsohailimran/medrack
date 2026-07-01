"""Tests for medrack.module.llm_extract."""
from unittest.mock import MagicMock

from medrack.module.llm_extract import extract_questions_with_llm


SAMPLE_PAGES = [
    "1. Define health. (a) WHO definition (b) Lay definition. Key:a",
    "2. List dimensions of health. (a) Physical (b) Mental (c) Social (d) Spiritual. Key:d",
]


def test_extracts_questions_from_mocked_llm_response():
    mock_client = MagicMock()
    mock_client.complete.return_value = """[
        {"qid": "q001", "type": "mcq", "question_text": "Define health.",
         "options": {"a": "WHO definition", "b": "Lay definition"},
         "answer": "a", "page_num": 1},
        {"qid": "q002", "type": "mcq", "question_text": "List dimensions of health.",
         "options": {"a": "Physical", "b": "Mental", "c": "Social", "d": "Spiritual"},
         "answer": "d", "page_num": 2}
    ]"""
    result = extract_questions_with_llm(SAMPLE_PAGES, "psm", llm_client=mock_client)
    assert len(result) == 2
    assert result[0]["question_text"] == "Define health."
    assert result[1]["options"]["d"] == "Spiritual"
    assert mock_client.complete.called


def test_returns_empty_list_on_llm_failure():
    mock_client = MagicMock()
    mock_client.complete.side_effect = Exception("API down")
    result = extract_questions_with_llm(SAMPLE_PAGES, "psm", llm_client=mock_client)
    assert result == []


def test_returns_empty_list_on_invalid_json():
    mock_client = MagicMock()
    mock_client.complete.return_value = "not valid json"
    result = extract_questions_with_llm(SAMPLE_PAGES, "psm", llm_client=mock_client)
    assert result == []


def test_prompt_includes_subject():
    """The LLM prompt should mention the subject for context."""
    mock_client = MagicMock()
    mock_client.complete.return_value = "[]"
    extract_questions_with_llm(SAMPLE_PAGES, "fmt", llm_client=mock_client)
    call_args = mock_client.complete.call_args
    prompt = call_args[0][0] if call_args[0] else call_args.kwargs.get("prompt", "")
    assert "fmt" in prompt.lower()
