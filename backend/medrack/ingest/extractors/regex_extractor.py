"""v1 deterministic metadata extractor (Phase 6).

This is the *default* extractor. It uses only regex patterns and
heuristics — no LLM, no external API, no random behaviour. It is fully
reproducible: the same chunk text always produces the same
:class:`ChunkMetadata`.

Implementation notes
--------------------
- Pattern coverage is intentionally broad but conservative. We prefer
  *missing* a section flag to *falsely* flagging one. False positives
  waste prompt tokens (the whole point of metadata is to cut context);
  false negatives are recoverable (the retriever will fall back to
  vector similarity).
- Patterns are compiled once at module load (avoid per-chunk recompile).
- The medical-section patterns target section headings like
  "Management:", "Treatment:", "Etiology:", "Pathogenesis:" — both
  colon-suffixed headings and standalone bold-style headings.
- The structure patterns look for explicit text artefacts ("Figure 1",
  "Table 2", arrow chains, "Definition:", numerical formulas).
- Important years are extracted as 4-digit numbers in the range
  1900-2100. Important numbers are larger numeric values (>1000) that
  often represent population or epidemiological quantities.
- Keywords are the most-frequent content-bearing lemmas; for v1 we use
  a simple unigram-frequency filter with a small stopword list.

This extractor deliberately does not attempt:
- Layout analysis (it cannot tell if a number is in a table cell)
- OCR correction (it trusts the text it is given)
- Synonym expansion (it matches literal substrings)

A future LLM or hybrid extractor can fill those gaps.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List

from medrack.ingest.metadata import (
    ChunkMetadata,
    ExamMetadata,
    MedicalMetadata,
    MetadataExtractor,
    StructureMetadata,
)


# ----------------------------------------------------------------------
# Pattern banks (compiled once)
# ----------------------------------------------------------------------

# Medical section headings — case-insensitive, allow both colon-suffixed
# ("Management:") and bare ("MANAGEMENT OF DIABETES").
_MEDICAL_PATTERNS: dict = {
    "section_epidemiology": re.compile(
        r"\b(epidemiology|epidemiological|prevalence|incidence)\b", re.I
    ),
    "section_etiology": re.compile(
        r"\b(etiology|aetiology|caus(es?|e|ation)|caused by|risk factor)\b", re.I
    ),
    "section_pathogenesis": re.compile(
        r"\b(pathogenesis|pathophysiology|mechanism)\b", re.I
    ),
    "section_risk_factors": re.compile(
        r"\b(risk factor(s)?|high[- ]risk|low[- ]risk)\b", re.I
    ),
    "section_clinical_features": re.compile(
        r"\b(clinical feature(s)?|clinical presentation|signs? and symptoms?|symptom(s)?|presenting complaint|presenting feature)\b", re.I
    ),
    "section_diagnosis": re.compile(
        r"\b(diagnos(e|is|ed|ing)|diagnostic criteria|diagnostic workup)\b", re.I
    ),
    "section_differential_diagnosis": re.compile(
        r"\b(differential diagnos(e|is)|ddx|differentials)\b", re.I
    ),
    "section_investigations": re.compile(
        r"\b(investigation(s)?|laboratory|lab test(s)?|biochemical|haematolog(y|ical)|radiolog(y|ical)|imaging|ECG|EKG|X[- ]?ray|MRI|CT scan)\b", re.I
    ),
    "section_management": re.compile(
        r"\b(management|treatment|therapy|therapeutic|therapeutic regimen|regimen|intervention|prescrib(e|ed|ing)|dosage|drug(s)?)\b", re.I
    ),
    "section_prevention": re.compile(
        r"\b(prevention|preventive|prophyla(xis|ctic)|immun(isz)?ation|vaccin(e|ation)|screening)\b", re.I
    ),
    "section_national_programme": re.compile(
        r"\b(national programme|national program|national health programme|NHP|NRHM|NHM|RCH|ICDS|NACO|NVBDCP|NTCP|RNTCP)\b", re.I
    ),
    "section_medicolegal": re.compile(
        r"\b(medicolegal|medico[- ]legal|legal aspect|forensic|court|testimony|evidence act)\b", re.I
    ),
    "section_statistics": re.compile(
        r"\b(statistic(s|al)|incidence rate|prevalence rate|per\s?\d+|% ?CI|confidence interval|p\s?[<>=]?\s?0?\.\d+|odds ratio|relative risk|standard deviation|mean\s?[±\+\-])\b", re.I
    ),
}


# Structural element patterns
_STRUCTURE_PATTERNS: dict = {
    "section_definition": re.compile(
        r"\b(defined as|definition:|is defined|refers to|is a\s+(?:disease|disorder|condition|syndrome|procedure|test|investigation))\b", re.I
    ),
    "section_classification": re.compile(
        r"\b(classification|classified|grading|stage[s]? (I{1,3}V?|IV|V|0|1|2|3|4)|type\s+[1-4]|category)\b", re.I
    ),
    "section_flowchart": re.compile(
        r"(?:→|->|⇒|-->)"  # arrow chain — basic heuristic
        r"|\b(flow ?chart|algorithm|decision tree|step\s+\d+[:.)])\b",
        re.I,
    ),
    "section_table": re.compile(
        r"\b(table\s+\d+[:.]|tab\.?\s+\d+|see table|in table|as shown in table)\b", re.I
    ),
    "section_diagram": re.compile(
        r"\b(fig\.?\s+\d+|figure\s+\d+|see figure|as shown in figure|illustration|diagram)\b", re.I
    ),
    "section_formula": re.compile(
        r"[=±×÷∑∫√π]"  # math symbols
        r"|\b(formula|equation|calculation:)\b",
    ),
    "section_conclusion": re.compile(
        r"\b(conclusi(on|ons?)|summary:|in summary|to summarise|key (?:point|message|learning)|take[- ]home (?:point|message))\b", re.I
    ),
}


# Important years: 4-digit numbers in 1900-2100, word-boundary matched
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|2100)\b")

# Important numbers: integers >= 1000, with optional comma-separated
# thousands (e.g. "1000", "1,200,000", "10,500"). We match the *whole*
# number including commas, which requires a non-word-boundary pattern.
# The pattern captures the entire run of digits and commas that begins
# with 1-9 (to avoid leading zeros) and has at least 4 digits total.
_NUMBER_RE = re.compile(r"(?<!\d)([1-9]\d{0,2}(?:,\d{3})+|\d{4,})(?!\d)")


# Stopwords for keyword extraction
_STOPWORDS = frozenset(
    "the a an and or of in on at to for with by from as is are was were be been "
    "being have has had do does did will would shall should may might can could "
    "this that these those it its their there which who whom whose what when where "
    "why how also such only just more most other into over under between through "
    "during before after above below up down out off per each both either neither "
    "very much many few some any all no not nor only own same than too very s t d "
    "re et al fig table".split()
)

# Token: letters and digits (incl. hyphenated), length >= 4
_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9-]{3,}\b")


# ----------------------------------------------------------------------
# Extractor
# ----------------------------------------------------------------------

class RegexMetadataExtractor(MetadataExtractor):
    """Deterministic v1 extractor.

    Uses compiled regex patterns and a simple unigram-frequency keyword
    ranker. No LLM. No external API. No randomness. Two runs on the same
    input always produce the same :class:`ChunkMetadata`.
    """

    # Maximum number of keywords to record per chunk
    MAX_KEYWORDS = 12
    # Maximum number of important years / numbers to record per chunk
    MAX_YEARS = 8
    MAX_NUMBERS = 8

    def extract(
        self,
        text: str,
        *,
        subject: str,
        book_id: str,
        chapter_title: str,
        page_start: int,
        page_end: int,
    ) -> ChunkMetadata:
        if not text:
            return ChunkMetadata()

        # ---- Medical sections ----
        medical_kwargs: dict = {}
        for name, pattern in _MEDICAL_PATTERNS.items():
            medical_kwargs[name] = bool(pattern.search(text))
        medical = MedicalMetadata(**medical_kwargs)

        # ---- Structural sections ----
        structure_kwargs: dict = {}
        for name, pattern in _STRUCTURE_PATTERNS.items():
            structure_kwargs[name] = bool(pattern.search(text))
        structure = StructureMetadata(**structure_kwargs)

        # ---- Exam metadata ----
        # Important years
        year_matches = _YEAR_RE.findall(text)
        try:
            years_int = sorted({int(y) for y in year_matches})
        except ValueError:
            years_int = []
        important_years: List[int] = years_int[: self.MAX_YEARS]

        # Important numbers: integers >= 1000, excluding years.
        # Allow comma-separated thousands (e.g. "1,200,000") by stripping
        # commas before parsing. Chroma stores them as strings; we
        # preserve the raw match (with commas) in the output.
        year_set = set(important_years)
        important_numbers: List[str] = []
        seen_nums: set = set()
        for raw in _NUMBER_RE.findall(text):
            try:
                # Parse the comma-stripped form to get the integer value
                iv = int(raw.replace(",", ""))
            except ValueError:
                continue
            if iv < 1000:
                continue
            if iv in year_set:
                continue
            if iv in seen_nums:
                continue
            seen_nums.add(iv)
            important_numbers.append(raw)
            if len(important_numbers) >= self.MAX_NUMBERS:
                break

        # Keywords: top unigrams by frequency, stopword-filtered
        tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
        filtered = [t for t in tokens if t not in _STOPWORDS and not t.isdigit()]
        if filtered:
            counts = Counter(filtered)
            # Take the top N; ties broken by alphabetical order for determinism
            top = sorted(counts.most_common(), key=lambda kv: (-kv[1], kv[0]))
            keywords: List[str] = [w for w, _c in top[: self.MAX_KEYWORDS]]
        else:
            keywords = []

        exam = ExamMetadata(
            important_years=important_years,
            important_numbers=important_numbers,
            keywords=keywords,
        )

        return ChunkMetadata(structure=structure, medical=medical, exam=exam)


__all__ = ["RegexMetadataExtractor"]
