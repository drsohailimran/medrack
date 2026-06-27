"""Tests for medrack.answer.llm."""
import time
from unittest.mock import MagicMock, patch

import pytest

from medrack.answer.llm import LLMClient, LLMResponse, LLMUnavailableError


SAMPLE_RESPONSE = {
    "content": [{"type": "text", "text": "The answer is 42."}],
    "usage": {"input_tokens": 100, "output_tokens": 50},
    "model": "minimax-m3",
}


def make_mock_client(responses, side_effects=None):
    """Build a mock httpx.Client that returns the given responses in order."""
    mock = MagicMock()
    if side_effects:
        mock.post.side_effect = side_effects
    else:
        mock.post.return_value.json.return_value = responses
        mock.post.return_value.status_code = 200
        mock.post.return_value.raise_for_status = MagicMock()
    return mock


def test_complete_returns_text_and_tokens():
    client = LLMClient()
    with patch("httpx.Client", return_value=make_mock_client(SAMPLE_RESPONSE)):
        resp = client.complete("What is the answer?")
    assert isinstance(resp, LLMResponse)
    assert resp.text == "The answer is 42."
    assert resp.prompt_tokens == 100
    assert resp.completion_tokens == 50
    assert resp.total_tokens == 150
    assert resp.model == "minimax-m3"
    assert resp.latency_seconds > 0


def test_complete_uses_default_model():
    client = LLMClient()
    with patch("httpx.Client", return_value=make_mock_client(SAMPLE_RESPONSE)) as mock_cls:
        client.complete("Q?")
    # The first call should use the default model
    call_args = mock_cls.return_value.post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["model"] == "minimax-m3"


def test_retry_on_429():
    """A 429 response should trigger retry, eventually succeed."""
    mock = MagicMock()
    # First call: 429. Second call: success.
    response_429 = MagicMock(status_code=429)
    response_429.raise_for_status = MagicMock(side_effect=Exception("429"))
    response_ok = MagicMock(status_code=200)
    response_ok.json.return_value = SAMPLE_RESPONSE
    response_ok.raise_for_status = MagicMock()
    mock.post.side_effect = [response_429, response_ok]
    with patch("httpx.Client", return_value=mock):
        with patch("time.sleep") as mock_sleep:  # don't actually sleep
            client = LLMClient(max_retries=2, timeout=10.0)
            resp = client.complete("Q?")
    assert resp.text == "The answer is 42."
    assert mock.post.call_count == 2
    # Should have slept once (between attempts)
    assert mock_sleep.call_count >= 1


def test_fallback_chain_on_persistent_failure():
    """If primary model fails 3 times, try the first fallback model."""
    mock = MagicMock()
    # Primary model: 3 failures. Fallback model: success.
    response_fail = MagicMock(status_code=500)
    response_fail.raise_for_status = MagicMock(side_effect=Exception("500"))
    response_ok = MagicMock(status_code=200)
    response_ok.json.return_value = {**SAMPLE_RESPONSE, "model": "kimi-k2.7-code"}
    response_ok.raise_for_status = MagicMock()
    mock.post.side_effect = [response_fail, response_fail, response_fail, response_ok]
    with patch("httpx.Client", return_value=mock):
        with patch("time.sleep"):
            client = LLMClient(
                model="primary",
                fallback_models=["kimi-k2.7-code"],
                max_retries=3,
                timeout=10.0,
            )
            resp = client.complete("Q?")
    assert resp.model == "kimi-k2.7-code"


def test_raises_when_all_models_fail():
    """If every model in the chain exhausts retries, raise LLMUnavailableError."""
    mock = MagicMock()
    response_fail = MagicMock(status_code=500)
    response_fail.raise_for_status = MagicMock(side_effect=Exception("500"))
    # 3 retries on primary + 3 on fallback = 6 failures
    mock.post.side_effect = [response_fail] * 6
    with patch("httpx.Client", return_value=mock):
        with patch("time.sleep"):
            client = LLMClient(
                model="primary",
                fallback_models=["fallback-1"],
                max_retries=3,
                timeout=10.0,
            )
            with pytest.raises(LLMUnavailableError):
                client.complete("Q?")


def test_llm_response_dataclass():
    resp = LLMResponse(
        text="x", prompt_tokens=1, completion_tokens=2, total_tokens=3,
        model="m", latency_seconds=0.1,
    )
    assert resp.text == "x"
    assert resp.total_tokens == 3
