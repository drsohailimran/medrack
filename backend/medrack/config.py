"""
medrack configuration — paths, subjects, model constants.

Single source of truth for tunable parameters. All hardcoded values in the
package read from here.
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

# ----- Paths -----

def get_medrack_home() -> Path:
    """Return the medrack root directory. Override with $MEDRACK_HOME."""
    env = os.environ.get("MEDRACK_HOME")
    return Path(env).expanduser() if env else Path.home() / ".hermes" / "medrack"

HOME: Path = get_medrack_home()

DATA_DIRS = {
    "books": HOME / "books",
    "index": HOME / "index",
    "modules": HOME / "modules",
    "answers": HOME / "answers",
    "output": HOME / "output",
    "logs": HOME / "logs",
    "scripts": HOME / "scripts",
    "references": HOME / "references",
    "package": HOME / "medrack",
    "state": HOME / "state",
}

# ----- Subjects (locked from the plan, 10 subjects, MBBS 3rd/final year) -----

class Subject(str, Enum):
    PSM = "psm"
    FMT = "fmt"
    MEDICINE = "medicine"
    SURGERY = "surgery"
    ORTHO = "ortho"
    OBGYN = "obgyn"
    ANESTHESIA = "anesthesia"
    PEDIATRICS = "pediatrics"
    ENT = "ent"
    OPHTHALMOLOGY = "ophthalmology"

    @classmethod
    def values(cls) -> list[str]:
        return [s.value for s in cls]

    @classmethod
    def from_str(cls, s: str) -> "Subject":
        s = s.lower().strip()
        for subj in cls:
            if subj.value == s or subj.name.lower() == s:
                return subj
        raise ValueError(f"Unknown subject: {s!r}. Valid: {[s.value for s in cls]}")

# ----- Module format (Path C: hybrid) -----

class ModuleFormat(str, Enum):
    AUTO = "auto"   # detect from first 5 pages
    MCQ = "mcq"     # generate MCQ-with-explanation answers
    THEORY = "theory"  # generate 1500-word structured theory answers

# ----- KB chunking -----

CHUNK_SIZE_TOKENS = 1000
CHUNK_OVERLAP_TOKENS = 200

# ----- Retrieval -----

RETRIEVAL_TOP_K = 8
SUBJECT_FILTER_MANDATORY = True   # never retrieve across subjects
CHAPTER_CONFIDENCE_THRESHOLD = 0.7  # below this, drop the chapter filter

# ----- LLM -----
# Note (2026-07-01): live benchmarking against the opencode.ai/zen
# endpoint (Define-health probe, 600 max_tokens):
#   kimi-k2.7-code  4.9s  (fast, minimal reasoning overhead)  <- primary
#   deepseek-v4-pro 6.8s  (real answers but 30-60s at 2048 tok; heavy thinking)
#   glm-5.2         9.2s
#   qwen3.7-max    17.2s  (very slow / historically hangs)     <- last resort
# `kimi-k2.7-code` returns real answer text fastest and with the least
# "thinking" token burn, so it is the primary; the rest are fallbacks.
#
# Provider selection (2026-07-01): MedRack's LLM client speaks the
# Anthropic-native messages format (POST /messages, `x-api-key`, content
# blocks, `usage.{input,output}_tokens`), so switching to the real
# Anthropic API is a base-URL + header + model swap — no code rewrite.
# Set MEDRACK_LLM_PROVIDER to pick one:
#   "opencode" (default) — opencode.ai/zen (OPENCODE_ZEN_API_KEY)
#   "claude"             — api.anthropic.com (ANTHROPIC_API_KEY), Haiku 4.5
# Each provider's model can be overridden via MEDRACK_LLM_MODEL.
LLM_PROVIDER = os.environ.get("MEDRACK_LLM_PROVIDER", "opencode").strip().lower()

# Each provider declares its wire format ("anthropic" or "gemini"), the auth
# header, the env var holding the key, and any extra headers. `api_format`
# selects request/response handling in medrack.answer.llm.LLMClient.
LLM_PROVIDERS = {
    "opencode": {
        "base_url": "https://opencode.ai/zen/go/v1",
        "model": "kimi-k2.7-code",
        "fallback_chain": ["deepseek-v4-pro", "glm-5.2", "qwen3.7-max"],
        "api_key_env": "OPENCODE_ZEN_API_KEY",
        "extra_headers": {},
        "api_format": "anthropic",
        "auth_header": "x-api-key",
        "max_output_tokens": 2048,
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1",
        # Haiku 4.5: excellent medical quality, ~1c/answer. Bump to
        # "claude-sonnet-4-6" for the highest quality (~3c/answer).
        "model": "claude-haiku-4-5",
        "fallback_chain": [],  # single reliable model; retries handle blips
        "api_key_env": "ANTHROPIC_API_KEY",
        "extra_headers": {"anthropic-version": "2023-06-01"},
        "api_format": "anthropic",
        "auth_header": "x-api-key",
        "max_output_tokens": 2048,
    },
    "gemini": {
        # Google AI Studio (free tier). Native generateContent API.
        # Default is gemini-2.0-flash: its free-tier DAILY request cap is
        # ~10x higher than gemini-2.5-flash's (which is only ~20/day, far
        # too low to solve a whole question bank). 2.0-flash is non-thinking
        # so maxOutputTokens bounds the answer length directly. Override via
        # MEDRACK_LLM_MODEL (e.g. gemini-2.5-flash for a few high-quality
        # previews).
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.0-flash",
        "fallback_chain": [],
        "api_key_env": "GEMINI_API_KEY",
        "extra_headers": {},
        "api_format": "gemini",
        "auth_header": "x-goog-api-key",
        "max_output_tokens": 8192,
    },
    "ollama": {
        # Local models via Ollama. No API key, no quotas, no rate limits.
        # Point MEDRACK_LLM_BASE_URL at the machine running Ollama if it is
        # not localhost, e.g. http://<gpu-host-lan-ip>:11434 (a separate
        # machine with the GPU). Default model is the Qwen3 30B-A3B MoE; override
        # with MEDRACK_LLM_MODEL (e.g. qwen3:14b, gemma3:27b).
        "base_url": "http://localhost:11434",
        "model": "qwen3:30b-a3b",
        "fallback_chain": [],
        "api_key_env": "",
        "extra_headers": {},
        "api_format": "ollama",
        "auth_header": "",
        "max_output_tokens": 8192,
        # Local generation is slower and the first call loads the model into
        # RAM, so allow a much longer per-attempt timeout.
        "timeout": 600.0,
    },
    "llamacpp": {
        # A local llama.cpp `llama-server` (OpenAI-compatible API). Faster
        # than Ollama for MoE models because the server can be launched with
        # --n-cpu-moe (keep expert tensors on CPU, attention on GPU). Point
        # MEDRACK_LLM_BASE_URL at the machine running llama-server.
        "base_url": "http://localhost:8080",
        "model": "qwopus",
        "fallback_chain": [],
        "api_key_env": "",
        "extra_headers": {},
        "api_format": "openai",
        "auth_header": "",
        "max_output_tokens": 8192,
        "timeout": 600.0,
    },
}

_active_provider = LLM_PROVIDERS.get(LLM_PROVIDER, LLM_PROVIDERS["opencode"])
# MEDRACK_LLM_BASE_URL overrides the endpoint (used to point the Ollama
# provider at the LAN machine running Ollama).
LLM_BASE_URL = os.environ.get("MEDRACK_LLM_BASE_URL", _active_provider["base_url"]).rstrip("/")
LLM_DEFAULT_MODEL = os.environ.get("MEDRACK_LLM_MODEL", _active_provider["model"])
LLM_FALLBACK_CHAIN = _active_provider["fallback_chain"]
# Read by medrack.answer.llm.LLMClient.
LLM_API_KEY_ENV = _active_provider["api_key_env"]
LLM_EXTRA_HEADERS = dict(_active_provider["extra_headers"])
LLM_API_FORMAT = _active_provider["api_format"]
LLM_AUTH_HEADER = _active_provider["auth_header"]
LLM_MAX_RETRIES = 2
LLM_RETRY_BASE_DELAY_SEC = 2.0   # exponential backoff base
# Note (2026-06-30): the opencode.ai/zen deepseek-v4-pro endpoint
# produces real answers but is slow: a 1958-char prompt + 2048 max_tokens
# takes ~30-60s end-to-end. With max_tokens=1024 the model exhausts
# the budget on thinking/reasoning and returns 0 chars of text. The
# 2048 cap is the smallest size that reliably returns the actual
# answer. Operators can bump if they switch providers. The active provider
# supplies its own budget (Gemini 2.5 needs more, to fit its thinking tokens).
LLM_MAX_OUTPUT_TOKENS = int(
    os.environ.get("MEDRACK_LLM_MAX_OUTPUT_TOKENS", _active_provider.get("max_output_tokens", 2048))
)
# A real capped-context answer takes ~30-60s against kimi-k2.7-code, so
# the per-attempt timeout must comfortably exceed that (a too-low value
# times out a healthy call and triggers a retry, compounding load). Local
# providers (Ollama) declare a longer timeout; override via MEDRACK_LLM_TIMEOUT.
LLM_PER_ATTEMPT_TIMEOUT_SEC = float(
    os.environ.get("MEDRACK_LLM_TIMEOUT", _active_provider.get("timeout", 120.0))
)

# Retrieval context fed into the prompt. Book chunks can be very large
# (~4k chars each); sending all top_k=8 in full produced ~35k-char
# (~8.7k-token) prompts that hung the opencode.ai/zen endpoint for
# 90s+ per attempt. Cap the number of chunks and per-chunk length so the
# prompt stays a few thousand tokens and the LLM responds quickly. These
# only affect the prompt context — the full chunks are still recorded in
# the answer's retrieval metadata.
PROMPT_CONTEXT_MAX_CHUNKS = 5
PROMPT_CONTEXT_MAX_CHARS_PER_CHUNK = 1500

# ----- Answer targets (operator-set 2026-06-29, directive v1.0) -----
# 10-mark theory: 700-850 words (midpoint 775, ±10% = 697-852)
# 5-mark theory:  450-500 words (midpoint 475, ±10% = 427-522)
# MCQ explanation: 250-300 words (midpoint 275, ±10% = 247-302)
# The prompt template says "~{N} words (±10%)" so the LLM gets a
# midpoint target with a tight tolerance band. If the LLM interprets
# the target as a *minimum* (observed behaviour with qwen3.7-max),
# answers tend to come in 5-10% over the midpoint, which is fine.
THEORY_LONG_TARGET_WORDS = 750   # 10-mark question (~750 words)
THEORY_SHORT_TARGET_WORDS = 375  # 5-mark question (~350-400 words)
THEORY_WORD_TOLERANCE = 0.10  # ±10% applied to both long and short
THEORY_DEFAULT_MARKS = 10  # used when a theory question has no explicit marks
MCQ_EXPLANATION_TARGET_WORDS = 275
MCQ_EXPLANATION_WORD_TOLERANCE = 0.10  # tightened from 0.33 in the same directive

# ----- Subject-aware prompt contexts (Phase 2, directive v1.0) -----
# Per-subject metadata that drives the prompt templates. The prompt
# builders (medrack.answer.prompt) read from this dict and substitute
# subject-specific language into the template. Adding a new subject
# means adding an entry here — the prompt builders do not need to
# change.
#
# Schema (all fields are str; missing fields fall back to a generic
# default at prompt-build time so a half-populated entry is safe):
#   display         : human-readable name used in the LLM system prompt
#   reference_text  : primary textbook citation
#   indian_context  : subject-specific Indian context the LLM should use
#   key_sources     : authoritative source names the LLM may reference
#                     (without parenthetical citation, per the
#                     exam-prep no-citation rule)
#   framework       : the dominant analytical framework for the subject
#   fallback        : (bool) if True, this is a generic fallback used
#                     when a subject has no entry in this dict. Only
#                     "generic" should have this set True.
SUBJECT_CONTEXTS: dict[str, dict[str, str]] = {
    "psm": {
        "display": "PSM / Community Medicine",
        "reference_text": "K. Park's \"Preventive & Social Medicine\" 27th edition",
        "indian_context": (
            "national programmes (NHM, NVBDCP, RNTCP, Ayushman Bharat, "
            "Pulse Polio, NACP, NVHCP, IDSP, NTEP, NLEP), NFHS-5 data, "
            "SRS, IMR, MMR, U5MR, TFR, CBR, CDR"
        ),
        "key_sources": "WHO, ICMR, MoHFW, NFHS, SRS, UNICEF India",
        "framework": "primary / secondary / tertiary prevention (Park's framework); levels of prevention; natural history of disease",
    },
    "fmt": {
        "display": "Forensic Medicine & Toxicology",
        "reference_text": "K.S. Narayan Reddy's \"Essentials of Forensic Medicine\" 34th edition",
        "indian_context": (
            "Indian Penal Code (IPC), Code of Criminal Procedure (CrPC), "
            "Indian Evidence Act (IEA), MTP Act 1971 (amended 2021), "
            "POCSO Act 2012, Mental Healthcare Act 2017, BNSS 2023, "
            "BNS 2023, NDPS Act, Consumer Protection Act 2019 (medical "
            "negligence), Transgender Persons Act 2019"
        ),
        "key_sources": "ICMR, Supreme Court of India guidelines, MoHFW, NIMHANS",
        "framework": "identification (race, age, sex, stature, DNA, fingerprints); forensic toxicology principles; medical jurisprudence; consent and negligence",
    },
    "generic": {
        "display": "MBBS",
        "reference_text": "standard MBBS textbook for the subject",
        "indian_context": "Indian epidemiological data, national health programmes, MCI/NMC curriculum",
        "key_sources": "WHO, ICMR, MoHFW",
        "framework": "subject-specific analytical framework",
        "fallback": "true",
    },
}

# ----- Embeddings (local, sentence-transformers) -----

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ----- Answer cache versioning (Phase 3, directive v1.0) -----
# Per-component version numbers, tracked independently. A cached
# answer records these in its ``versions`` dict; when ``load_answer``
# detects a mismatch against the current values, the answer is marked
# ``stale: true`` with the list of reasons — the cache file is NEVER
# deleted by the version check (per the operator's directive: "Mark
# answers stale instead of deleting them").
#
# When to bump a version:
#   schema       — the shape of the cache JSON changes (new required
#                  field, removed field, or new field is now mandatory).
#                  Old caches are still readable but are marked stale.
#   prompt       — the prompt template text changes (e.g. PSM-specific
#                  wording added, or the subject-context schema in
#                  SUBJECT_CONTEXTS changes). Re-renders produce
#                  different answers.
#   retrieval    — chunk size, overlap, top_k, distance threshold, or
#                  embedding model change. The retrieval step now
#                  returns different chunks for the same question.
#   planner      — when the planner module lands (Phase 7+), bump
#                  this. Default 0 (not yet implemented).
#   validator    — when the validator pipeline lands (Phase 7+), bump
#                  this. Default 0 (not yet implemented).
#   reranker     — when the cross-encoder reranker lands (Phase 7+),
#                  bump this. Default 0 (not yet implemented).
#   renderer     — the reportlab flowable builder / block classifier
#                  changes. Re-renders produce different PDFs even if
#                  the LLM text is identical.
PIPELINE_VERSIONS: dict[str, int] = {
    "schema": 2,     # Phase 3: added versions, target_word_count, package_version, embedding_model
    "prompt": 1,     # Phase 2: subject-aware prompt (K. Park vs Narayan Reddy etc.)
    "retrieval": 1,  # current retrieval config (top_k=8, MiniLM-L6-v2)
    "planner": 0,    # not yet implemented
    "validator": 0,  # not yet implemented
    "reranker": 0,   # not yet implemented
    "renderer": 1,   # current renderer (K. Park style, commit c668289)
}

# ----- OCR (Tesseract via pytesseract) -----

OCR_DPI = 300
OCR_MIN_CHARS_PER_PAGE = 500   # below this, flag page as suspect
OCR_PSM_DEFAULT = 6            # uniform block of text (good default for body)
OCR_PSM_SINGLE_COLUMN = 4      # for question pages
OCR_LANG = "eng"

# ----- Manifest schema (locked; do not change without migration) -----

MANIFEST_VERSION = 1
MANIFEST_PATH = DATA_DIRS["index"] / "manifest.json"
CHROMA_PATH = DATA_DIRS["index"] / "chroma"
