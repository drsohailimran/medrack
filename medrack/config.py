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

# ----- Answer targets (operator-set 2026-06-29, directive v1.0) -----
# 10-mark theory: 700-850 words (midpoint 775, ±10% = 697-852)
# 5-mark theory:  450-500 words (midpoint 475, ±10% = 427-522)
# MCQ explanation: 250-300 words (midpoint 275, ±10% = 247-302)
# The prompt template says "~{N} words (±10%)" so the LLM gets a
# midpoint target with a tight tolerance band. If the LLM interprets
# the target as a *minimum* (observed behaviour with qwen3.7-max),
# answers tend to come in 5-10% over the midpoint, which is fine.
THEORY_LONG_TARGET_WORDS = 775   # 10-mark question
THEORY_SHORT_TARGET_WORDS = 475  # 5-mark question
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
