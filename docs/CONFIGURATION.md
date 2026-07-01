# Configuration

All runtime configuration is done through **environment variables**, normally
set in the repo-root `.env` file (copied from `.env.example` by `install.sh`).
`run.sh` sources `.env` before starting the services.

Defaults and the deeper (non-env) tunables live in
`backend/medrack/config.py`, which is the single source of truth.

---

## Core

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDRACK_HOME` | `~/.medrack` | Data root: books, ChromaDB index, question banks, cached answers, PDFs, logs. `.env.example` sets it to `$HOME/medrack-data`. |
| `API_PORT` | `8010` | Port for the FastAPI backend. |
| `FRONTEND_PORT` | `3010` | Port for the frontend node server. |
| `MEDRACK_API_BASE` | `http://localhost:8010/api/v1` | API URL **baked into the frontend at build time**. Change it and rebuild the frontend to access the UI from another device. |

---

## LLM provider

Select the provider with `MEDRACK_LLM_PROVIDER`; override its endpoint/model as
needed. Each provider is defined in `config.LLM_PROVIDERS`.

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDRACK_LLM_PROVIDER` | `llamacpp` | Active provider: `gemini`, `llamacpp`, `ollama`, `claude`, `opencode`. |
| `MEDRACK_LLM_BASE_URL` | provider-specific | Override the endpoint (e.g. point `llamacpp`/`ollama` at a GPU host on the LAN). |
| `MEDRACK_LLM_MODEL` | provider-specific | Override the model name. |
| `MEDRACK_LLM_TIMEOUT` | `120` (`600` for local) | Per-attempt timeout, seconds. Local models are slow — keep it generous. |
| `MEDRACK_LLM_MAX_OUTPUT_TOKENS` | provider-specific | Hard cap on response tokens (generation also computes a per-answer budget). |
| `MEDRACK_LLM_MODE` | `real` | `real` = call the LLM; `mock` = deterministic offline stub answers (UI testing). |

### Provider API keys (only for the one you use)

| Variable | For provider | Where to get it |
|----------|--------------|-----------------|
| `GEMINI_API_KEY` | `gemini` | https://aistudio.google.com/apikey (free tier) |
| `ANTHROPIC_API_KEY` | `claude` | https://console.anthropic.com |
| `OPENCODE_ZEN_API_KEY` | `opencode` | opencode.ai/zen |

`llamacpp` and `ollama` need **no key** — they're local.

### Recommended settings

**Gemini (easiest):**
```bash
MEDRACK_LLM_PROVIDER=gemini
MEDRACK_LLM_MODEL=gemini-2.0-flash    # high free daily quota
GEMINI_API_KEY=...
```
> `gemini-2.0-flash` has a much higher free daily quota than `gemini-2.5-flash`
> (which is limited to ~20 requests/day on the free tier). Use 2.5 only for
> occasional high-quality previews.

**Local llama.cpp (private, no quotas):**
```bash
MEDRACK_LLM_PROVIDER=llamacpp
MEDRACK_LLM_MODEL=qwopus
MEDRACK_LLM_BASE_URL=http://<gpu-host>:8080
MEDRACK_LLM_TIMEOUT=600
```
See [SETUP.md → Running a local model](SETUP.md#running-a-local-model).

### Adding a new provider

Add an entry to `LLM_PROVIDERS` in `config.py`:
```python
"myprovider": {
    "base_url": "https://api.example.com/v1",
    "model": "some-model",
    "api_format": "openai",        # "gemini" | "ollama" | "openai"
    "auth_header": "Authorization",
    "api_key_env": "MY_API_KEY",
    "extra_headers": {},
    "timeout": 120.0,
    "max_output_tokens": 4096,
},
```
Then set `MEDRACK_LLM_PROVIDER=myprovider`. The client in `answer/llm.py`
dispatches on `api_format`.

---

## Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDRACK_EMBED_DEVICE` | `cpu` | `cpu` or `cuda` for the sentence-transformers embedding model. |

The embedding model itself (`sentence-transformers/all-MiniLM-L6-v2`, 384-dim)
is set in `config.py`. Changing it invalidates the vector index and cached
answers (re-ingest required).

---

## Optional: Telegram operator bot

| Variable | Description |
|----------|-------------|
| `MEDRACK_TELEGRAM_BOT_TOKEN` | Enables the bot when set; `run.sh` starts it automatically. |
| `MEDRACK_OPERATOR_CHAT_ID` | Restrict operator commands to this chat ID (unset = allow all — dev only). |

---

## Non-env tunables (in `config.py`)

These are constants you can edit in `backend/medrack/config.py`:

| Constant | Value | Meaning |
|----------|-------|---------|
| `CHUNK_SIZE_TOKENS` / `CHUNK_OVERLAP_TOKENS` | 1000 / 200 | Knowledge-base chunking |
| retrieval `top_k` | 8 | Candidate chunks retrieved per question |
| `PROMPT_CONTEXT_MAX_CHUNKS` / `..._CHARS_PER_CHUNK` | 5 / 1500 | Context actually placed in the prompt |
| `THEORY_LONG_TARGET_WORDS` | 750 | 10-mark answer length |
| `THEORY_SHORT_TARGET_WORDS` | 375 | 5-mark answer length |
| cache versions | schema/prompt/retrieval/renderer/… | Bump to invalidate cached answers after a pipeline change |
