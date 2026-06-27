"""LLM HTTP client with retry + fallback chain.

Wraps the OpenCode Go (Anthropic-format) messages API. Each call to
`complete(prompt)` tries the primary model, then the configured fallbacks
in order, with exponential backoff per model.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx

from medrack import config
from medrack.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Result of a successful LLM call."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    latency_seconds: float


class LLMUnavailableError(Exception):
    """All LLM attempts (primary + fallbacks + retries) failed."""

    pass


class MockLLMClient:
    """Deterministic LLM client for tests and offline runs.

    Mirrors the ``LLMClient`` surface (``complete(prompt) -> LLMResponse``)
    but never touches the network — every prompt gets a canned response.
    Used when ``$MEDRACK_LLM_MODE=mock`` (selected by the CLI in
    ``cmd_approve`` and the test fixtures) so end-to-end flows can run
    without a real ``OPENCODE_ZEN_API_KEY``.
    """

    def __init__(self) -> None:
        # No state needed — the response is purely a function of the
        # prompt (deterministic) and the canned token/latency constants
        # below.
        pass

    def complete(self, prompt: str) -> LLMResponse:
        """Return a deterministic canned response for any prompt.

        The answer text embeds the first 50 chars of the prompt so the
        output is traceable back to the question (helpful in test
        assertions and PDF debugging). Token counts and latency are
        fixed so total-tokens / total-latency accounting in the batch
        orchestrator stays predictable.
        """
        return LLMResponse(
            text=f"MOCK ANSWER ({prompt[:50]})",
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            model="mock",
            latency_seconds=0.1,
        )


class LLMClient:
    """Thin wrapper over the LLM HTTP API with retry + fallback."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        max_retries: int | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url if base_url is not None else config.LLM_BASE_URL
        self.model = model if model is not None else config.LLM_DEFAULT_MODEL
        self.fallback_models = (
            fallback_models if fallback_models is not None else config.LLM_FALLBACK_CHAIN
        )
        self.max_retries = max_retries if max_retries is not None else config.LLM_MAX_RETRIES
        self.timeout = timeout
        # Lazily created on first request. Tests inject a mock by patching
        # `httpx.Client` BEFORE `complete()` runs (the client constructor is
        # called inside complete, not __init__), so this attribute stays
        # None until the first call. Created once and reused thereafter.
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            # The OpenCode Go API expects `x-api-key: $OPENCODE_ZEN_API_KEY`.
            # Read it from the env at client-init time (not at __init__ time,
            # so MEDRACK_HOME / load_dotenv() hooks work).
            headers = {"Content-Type": "application/json"}
            api_key = os.environ.get("OPENCODE_ZEN_API_KEY")
            if api_key:
                headers["x-api-key"] = api_key
            self._client = httpx.Client(timeout=self.timeout, headers=headers)
        return self._client

    def _try_once(self, model: str, prompt: str) -> LLMResponse:
        """Single attempt against one model. Raises on HTTP error."""
        # base_url is `https://opencode.ai/zen/go/v1` (already includes /v1),
        # so the messages endpoint is just `/messages`.
        url = f"{self.base_url}/messages"
        body = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        start = time.perf_counter()
        response = self._get_client().post(url, json=body)
        response.raise_for_status()
        data = response.json()
        latency = time.perf_counter() - start

        text = data["content"][0]["text"]
        usage = data["usage"]
        prompt_tokens = usage["input_tokens"]
        completion_tokens = usage["output_tokens"]
        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=data.get("model", model),
            latency_seconds=latency,
        )

    def complete(self, prompt: str) -> LLMResponse:
        """Call the LLM with retry + fallback chain.

        Try the primary model up to `max_retries` times with exponential
        backoff. If all attempts fail, move to the next model in the fallback
        chain. Raise `LLMUnavailableError` if every model exhausts retries.
        """
        models: list[str] = [self.model] + (self.fallback_models or [])
        last_error: Exception | None = None

        for model in models:
            for attempt in range(self.max_retries):
                try:
                    return self._try_once(model, prompt)
                except Exception as exc:  # httpx errors + raise_for_status HTTPError
                    last_error = exc
                    logger.warning(
                        "LLM call failed (model=%s, attempt=%d/%d): %s",
                        model,
                        attempt + 1,
                        self.max_retries,
                        exc,
                    )
                    # Exponential backoff between retries: 1s, 2s, 4s, ...
                    # Skip the sleep after the last attempt of a model — the
                    # next model will start immediately.
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
            logger.warning(
                "Model %s exhausted %d retries, moving to next model in chain.",
                model,
                self.max_retries,
            )

        raise LLMUnavailableError(
            f"All {len(models)} model(s) failed after {self.max_retries} retries each. "
            f"Last error: {last_error}"
        )
