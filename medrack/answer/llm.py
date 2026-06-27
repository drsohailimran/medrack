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
        # 90s per attempt: long enough for qwen3.7-max at max_tokens=2048
        # (~30-60s typical), short enough to fail fast and move to fallback.
        timeout: float = 90.0,
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
        """Single attempt against one model. Raises on HTTP error.

        Returns ``LLMUnavailableError`` (not a regular exception) when:
          - the model responds 200 but only emits ``thinking`` blocks
            (no ``text`` block) — common with qwen3.7-max when it gets
            confused. We treat this as a failure so the chain moves on.
          - the model responds with a 400 about empty messages (the
            DeepSeek/Moonshot providers reject our Anthropic-format
            payload — we should not retry 3 times on the same bad request).
        """
        # base_url is `https://opencode.ai/zen/go/v1` (already includes /v1),
        # so the messages endpoint is just `/messages`.
        url = f"{self.base_url}/messages"
        body = {
            "model": model,
            # 2048 is enough for a 1500-word answer (~1800 tokens) and
            # keeps qwen3.7-max within its responsive range. 4096 caused
            # 120s+ timeouts on the OpenCode Go endpoint.
            "max_tokens": 2048,
            # Anthropic-native content format (list of {type, text}) so
            # providers that proxy to OpenAI-style endpoints (DeepSeek,
            # Moonshot) don't reject the payload as "empty input".
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        }
        start = time.perf_counter()
        response = self._get_client().post(url, json=body)
        # 400 with "empty input messages" means this provider can't accept
        # our payload format. Treat as LLMUnavailableError so the chain
        # moves on immediately (no point retrying).
        if response.status_code == 400:
            try:
                err_msg = response.json().get("error", {}).get("message", "")
            except Exception:
                err_msg = response.text[:200]
            if "empty" in err_msg.lower():
                raise LLMUnavailableError(
                    f"Model {model} rejected payload (400): {err_msg!r}"
                )
        response.raise_for_status()
        data = response.json()
        latency = time.perf_counter() - start

        # Extract text. Some models (qwen3.7-max, GLM-5.2) emit a
        # `thinking` block but no `text` block — treat that as no answer.
        text_parts = [
            c.get("text", "")
            for c in data.get("content", [])
            if c.get("type") == "text" and c.get("text")
        ]
        text = "".join(text_parts).strip()
        if not text:
            # No text content — model returned only thinking. Move to
            # the next model in the chain.
            raise LLMUnavailableError(
                f"Model {model} returned only thinking blocks, no text."
            )
        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
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
