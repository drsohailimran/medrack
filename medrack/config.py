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

LLM_BASE_URL = "https://opencode.ai/zen/go/v1"
LLM_DEFAULT_MODEL = "qwen3.7-max"
LLM_FALLBACK_CHAIN = ["deepseek-v4-pro", "kimi-k2.7-code", "glm-5.2"]   # tried in order on rate-limit/error
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY_SEC = 2.0   # exponential backoff base

# ----- Answer targets -----

THEORY_LONG_TARGET_WORDS = 1500
THEORY_SHORT_TARGET_WORDS = 900
THEORY_WORD_TOLERANCE = 0.20  # ±20%
THEORY_DEFAULT_MARKS = 10  # used when a theory question has no explicit marks
MCQ_EXPLANATION_TARGET_WORDS = 300
MCQ_EXPLANATION_WORD_TOLERANCE = 0.33  # ±33%

# ----- Embeddings (local, sentence-transformers) -----

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

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
