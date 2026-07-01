"""LLM HTTP client with retry + fallback chain.

Wraps the OpenCode Go (Anthropic-format) messages API. Each call to
`complete(prompt)` tries the primary model, then the configured fallbacks
in order, with exponential backoff per model.
"""
from __future__ import annotations

import os
import re
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


class LLMRateLimitError(LLMUnavailableError):
    """The provider returned 429 (rate/usage limit).

    ``retry_after`` is the provider-suggested wait in seconds (if given),
    and ``daily`` is True when the violated quota is a *per-day* cap (which
    a short wait won't clear — so the caller should fail fast rather than
    burn time retrying). A per-minute cap (``daily=False``) is worth
    waiting out.
    """

    def __init__(self, message: str, retry_after: float | None = None, daily: bool = False):
        super().__init__(message)
        self.retry_after = retry_after
        self.daily = daily


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

    def complete(self, prompt: str, max_output_tokens: int | None = None) -> LLMResponse:
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
        # 90s per attempt: long enough for the configured LLM at
        # LLM_MAX_OUTPUT_TOKENS=1024 (~775-word MBBS answer). Bump
        # via config.LLM_PER_ATTEMPT_TIMEOUT_SEC if you switch providers.
        timeout: float = 90.0,
        max_output_tokens: int | None = None,
    ):
        self.base_url = base_url if base_url is not None else config.LLM_BASE_URL
        self.model = model if model is not None else config.LLM_DEFAULT_MODEL
        self.fallback_models = (
            fallback_models if fallback_models is not None else config.LLM_FALLBACK_CHAIN
        )
        self.max_retries = max_retries if max_retries is not None else config.LLM_MAX_RETRIES
        self.timeout = (
            timeout if timeout != 90.0 else config.LLM_PER_ATTEMPT_TIMEOUT_SEC
        )
        self.max_output_tokens = (
            max_output_tokens if max_output_tokens is not None
            else config.LLM_MAX_OUTPUT_TOKENS
        )
        # Lazily created on first request. Tests inject a mock by patching
        # `httpx.Client` BEFORE `complete()` runs (the client constructor is
        # called inside complete, not __init__), so this attribute stays
        # None until the first call. Created once and reused thereafter.
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            # Both OpenCode Go and the Anthropic API authenticate with
            # `x-api-key`; the key env var and any extra headers (e.g.
            # Anthropic's `anthropic-version`) come from the active provider
            # config. Read at client-init time (not __init__) so
            # MEDRACK_HOME / load_dotenv() hooks are honoured.
            headers = {"Content-Type": "application/json"}
            key_env = getattr(config, "LLM_API_KEY_ENV", "OPENCODE_ZEN_API_KEY")
            auth_header = getattr(config, "LLM_AUTH_HEADER", "x-api-key")
            api_key = os.environ.get(key_env)
            if api_key:
                headers[auth_header] = api_key
            extra = getattr(config, "LLM_EXTRA_HEADERS", None) or {}
            headers.update(extra)
            self._client = httpx.Client(timeout=self.timeout, headers=headers)
        return self._client

    def _try_once(
        self, model: str, prompt: str, max_output_tokens: int | None = None
    ) -> LLMResponse:
        """Single attempt against one model. Raises on HTTP error.

        Returns ``LLMUnavailableError`` (not a regular exception) when:
          - the model responds 200 but only emits ``thinking`` blocks
            (no ``text`` block) — common with qwen3.7-max when it gets
            confused. We treat this as a failure so the chain moves on.
          - the model responds with a 400 about empty messages (the
            DeepSeek/Moonshot providers reject our Anthropic-format
            payload — we should not retry 3 times on the same bad request).

        For the Gemini provider (different request/response shape), delegates
        to :meth:`_try_gemini`.
        """
        eff_max_tokens = max_output_tokens or self.max_output_tokens
        _fmt = getattr(config, "LLM_API_FORMAT", "anthropic")
        if _fmt == "gemini":
            return self._try_gemini(model, prompt, eff_max_tokens)
        if _fmt == "ollama":
            return self._try_ollama(model, prompt, eff_max_tokens)
        if _fmt == "openai":
            return self._try_openai(model, prompt, eff_max_tokens)
        # base_url is `https://opencode.ai/zen/go/v1` (already includes /v1),
        # so the messages endpoint is just `/messages`.
        url = f"{self.base_url}/messages"
        body = {
            "model": model,
            # 1024 by default (configurable via LLM_MAX_OUTPUT_TOKENS).
            # Enough for a 775-word MBBS answer + section markers, well
            # within the per-attempt timeout. 2048 caused 120s+ hangs
            # against the opencode.ai/zen endpoint.
            "max_tokens": eff_max_tokens,
            # Anthropic-native content format (list of {type, text}) so
            # providers that proxy to OpenAI-style endpoints (DeepSeek,
            # Moonshot) don't reject the payload as "empty input".
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        }
        start = time.perf_counter()
        response = self._get_client().post(url, json=body)
        # 429: usage/rate limit. All models share the account quota, so
        # abort the whole chain immediately with the provider's message
        # (retrying/falling back just burns more of a limited quota).
        if response.status_code == 429:
            try:
                msg = response.json().get("error", {}).get("message", "") or response.text[:300]
            except Exception:
                msg = response.text[:300]
            raise LLMRateLimitError(msg or "provider returned 429 (usage limit)")
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

    def _try_gemini(
        self, model: str, prompt: str, max_output_tokens: int | None = None
    ) -> LLMResponse:
        """Single attempt against the Gemini (Google AI Studio) API.

        Uses the native ``generateContent`` endpoint. A 429 raises
        :class:`LLMRateLimitError`; an empty or safety-blocked response
        raises :class:`LLMUnavailableError` so the caller can surface it.
        """
        url = f"{self.base_url}/models/{model}:generateContent"
        gen_config: dict = {"maxOutputTokens": max_output_tokens or self.max_output_tokens}
        # Gemini 2.5 models "think" by default, which consumes the output
        # budget unpredictably and makes answers run well over the requested
        # length. Disable thinking so maxOutputTokens bounds the answer
        # directly — grounded exam answers don't need it, and this is what
        # makes the word-count target actually hold.
        if "2.5" in model or "thinking" in model:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_config,
        }
        start = time.perf_counter()
        response = self._get_client().post(url, json=body)
        if response.status_code == 429:
            msg = ""
            retry_after: float | None = None
            daily = False
            try:
                err = response.json().get("error", {})
                msg = err.get("message", "") or response.text[:300]
                for det in err.get("details", []):
                    dtype = det.get("@type", "")
                    if dtype.endswith("RetryInfo"):
                        m = re.match(r"(\d+(?:\.\d+)?)", det.get("retryDelay", "") or "")
                        if m:
                            retry_after = float(m.group(1))
                    if dtype.endswith("QuotaFailure"):
                        for v in det.get("violations", []):
                            if "PerDay" in (v.get("quotaId", "") or ""):
                                daily = True
            except Exception:  # noqa: BLE001
                msg = response.text[:300]
            raise LLMRateLimitError(
                msg or "Gemini returned 429 (usage limit)",
                retry_after=retry_after,
                daily=daily,
            )
        response.raise_for_status()
        data = response.json()
        latency = time.perf_counter() - start

        candidates = data.get("candidates") or []
        text = ""
        finish = None
        if candidates:
            finish = candidates[0].get("finishReason")
            parts = candidates[0].get("content", {}).get("parts", []) or []
            text = "".join(p.get("text", "") for p in parts if p.get("text")).strip()
        if not text:
            reason = finish or (data.get("promptFeedback") or {}).get("blockReason") or "no content"
            raise LLMUnavailableError(f"Gemini returned no text (reason={reason}).")

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)
        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=model,
            latency_seconds=latency,
        )

    def _try_ollama(
        self, model: str, prompt: str, max_output_tokens: int | None = None
    ) -> LLMResponse:
        """Single attempt against a local Ollama server (no API key/quota).

        Uses the native ``/api/generate`` endpoint (non-streaming).
        ``think: false`` disables the reasoning phase on thinking models
        (e.g. Qwen3) so ``num_predict`` bounds the answer directly and the
        length target holds — same rationale as disabling Gemini 2.5's
        thinking. Connection errors propagate to the retry loop.
        """
        url = f"{self.base_url}/api/generate"
        body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "num_predict": max_output_tokens or self.max_output_tokens,
            },
        }
        start = time.perf_counter()
        response = self._get_client().post(url, json=body)
        response.raise_for_status()
        data = response.json()
        latency = time.perf_counter() - start

        text = (data.get("response") or "").strip()
        if not text:
            raise LLMUnavailableError("Ollama returned no text.")
        prompt_tokens = data.get("prompt_eval_count", 0) or 0
        completion_tokens = data.get("eval_count", 0) or 0
        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            latency_seconds=latency,
        )

    def _try_openai(
        self, model: str, prompt: str, max_output_tokens: int | None = None
    ) -> LLMResponse:
        """Single attempt against an OpenAI-compatible chat endpoint.

        Works with llama.cpp's ``llama-server`` (``/v1/chat/completions``,
        which applies the model's chat template when started with --jinja),
        LM Studio, vLLM, etc. No API key required for a local server.
        """
        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens or self.max_output_tokens,
            "stream": False,
            # Disable reasoning models' "thinking" phase (e.g. Qwen3) so the
            # token budget bounds the ANSWER, not a hidden <think> block, and
            # generation is faster. llama.cpp/vLLM read this jinja kwarg;
            # servers that don't understand it ignore it.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        start = time.perf_counter()
        response = self._get_client().post(url, json=body)
        response.raise_for_status()
        data = response.json()
        latency = time.perf_counter() - start

        choices = data.get("choices") or []
        text = ""
        if choices:
            text = (choices[0].get("message", {}).get("content") or "").strip()
        if not text:
            raise LLMUnavailableError("OpenAI-compatible server returned no text.")
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.get("total_tokens", prompt_tokens + completion_tokens),
            model=model,
            latency_seconds=latency,
        )

    def complete(self, prompt: str, max_output_tokens: int | None = None) -> LLMResponse:
        """Call the LLM with retry + fallback chain.

        Try the primary model up to `max_retries` times with exponential
        backoff. If all attempts fail, move to the next model in the fallback
        chain. Raise `LLMUnavailableError` if every model exhausts retries.

        ``max_output_tokens`` overrides the client default for this call —
        callers size it to the answer's word target so length is bounded
        (e.g. a 5-mark answer gets a smaller budget than a 10-mark one).
        """
        models: list[str] = [self.model] + (self.fallback_models or [])
        last_error: Exception | None = None

        # A per-MINUTE rate limit clears with a short wait, so we wait it out
        # (respecting the provider's suggested retry delay). A per-DAY cap
        # will not clear soon, so we fail fast on it instead of stalling.
        RATE_LIMIT_MAX_WAITS = 4
        RATE_LIMIT_MAX_SLEEP = 60.0

        for model in models:
            rate_limited = False
            rl_waits = 0
            attempt = 0
            while True:
                try:
                    return self._try_once(model, prompt, max_output_tokens)
                except LLMRateLimitError as exc:
                    last_error = exc
                    rate_limited = True
                    if getattr(exc, "daily", False) or rl_waits >= RATE_LIMIT_MAX_WAITS:
                        # Daily cap (or waited enough) — give up on this call.
                        break
                    rl_waits += 1
                    wait = getattr(exc, "retry_after", None) or (5 * rl_waits)
                    wait = min(float(wait) + 1.0, RATE_LIMIT_MAX_SLEEP)
                    logger.warning(
                        "LLM rate-limited (model=%s, waiting %.0fs, retry %d): %s",
                        model, wait, rl_waits, exc,
                    )
                    time.sleep(wait)
                    continue
                except Exception as exc:  # httpx errors + raise_for_status HTTPError
                    last_error = exc
                    rate_limited = False
                    attempt += 1
                    logger.warning(
                        "LLM call failed (model=%s, attempt=%d/%d): %s",
                        model, attempt, self.max_retries, exc,
                    )
                    if attempt >= self.max_retries:
                        break
                    time.sleep(2 ** (attempt - 1))
                    continue
            if rate_limited:
                # Every model shares the account quota, so cycling to
                # fallbacks just wastes calls — surface the provider message.
                raise last_error
            logger.warning(
                "Model %s exhausted %d retries, moving to next model in chain.",
                model,
                self.max_retries,
            )

        raise LLMUnavailableError(
            f"All {len(models)} model(s) failed after {self.max_retries} retries each. "
            f"Last error: {last_error}"
        )
