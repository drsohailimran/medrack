"""Question analyzer (Phase 7).

The :class:`QuestionAnalyzer` inspects a question dict and produces a
:class:`QuestionAnalysis` — a small typed object that captures what the
retrieval layer needs to know: the marks value (5 or 10) and the list
of medical / structural sections the question is about.

The v1 analyzer is deterministic: it reuses the same regex patterns
the v1 metadata extractor uses (so a question that matches
"Management:" and a chunk that matches "Management:" agree on the
vocabulary). Future LLM-based analyzers can subclass and produce the
same :class:`QuestionAnalysis` shape.

The analyzer does not parse the *answer*; it only inspects the
*question text*. This is the v1 contract: we never look at a cached
answer to decide what to retrieve for a new question.

Section vocabulary
------------------
The analyzer's ``target_sections`` field uses the same names as the
:class:`ChunkMetadata` fields: ``section_management``,
``section_etiology``, ``section_table``, etc. This means the
:class:`MetadataFilter` produced downstream maps 1:1 to the metadata
flags on the indexed chunks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class QuestionAnalysis:
    """The retrieval layer's view of a question.

    Attributes
    ----------
    marks:
        ``5`` or ``10`` for theory questions; ``None`` if unknown or
        not applicable (e.g. MCQ).
    target_sections:
        List of ``section_*`` names that the question is about. Empty
        list means "no specific topic detected — use generic
        retrieval". The list is ordered by detection confidence (most
        confident first).
    raw_text:
        The original question text, kept for downstream debugging /
        logging. Not used by the strategy or reranker.
    """

    marks: int | None
    target_sections: List[str] = field(default_factory=list)
    raw_text: str = ""


# ----------------------------------------------------------------------
# Section detection patterns
# ----------------------------------------------------------------------

# Map: regex pattern -> (group, section_name). The group is "structure"
# or "medical"; the section name matches the ChunkMetadata field name.
# Patterns are intentionally conservative: prefer missing a section
# over falsely flagging one (false positives cause over-restricted
# retrieval, which is worse than over-broad).
_SECTION_PATTERNS: list = [
    # ---- Medical sections (priority-ordered) ----
    (r"\b(management|treatment|therapy|therapeutic|regimen|intervention)\b", "medical", "section_management"),
    (r"\b(etiology|aetiology|caus(es?|e|ation)|caused by)\b", "medical", "section_etiology"),
    (r"\b(pathogenesis|pathophysiology|mechanism)\b", "medical", "section_pathogenesis"),
    (r"\b(epidemiology|epidemiological|prevalence|incidence)\b", "medical", "section_epidemiology"),
    (r"\b(risk factor(s)?|high[- ]risk|low[- ]risk)\b", "medical", "section_risk_factors"),
    (r"\b(clinical feature(s)?|clinical presentation|signs? and symptoms?|symptom(s)?|presenting feature)\b", "medical", "section_clinical_features"),
    (r"\b(diagnos(e|is|ed|ing)|diagnostic criteria|diagnostic workup)\b", "medical", "section_diagnosis"),
    (r"\b(differential diagnos(e|is)|ddx|differentials)\b", "medical", "section_differential_diagnosis"),
    (r"\b(investigation(s)?|laboratory|laboratory findings|lab test(s)?|radiolog(y|ical)|imaging|ECG|EKG|X[- ]?ray|MRI|CT scan)\b", "medical", "section_investigations"),
    (r"\b(prevention|preventive|prophyla(xis|ctic)|immun(isz)?ation|vaccin(e|ation)|screening)\b", "medical", "section_prevention"),
    (r"\b(national programme|national program|NHP|NRHM|NHM|RCH|ICDS|NACO|NVBDCP|NTCP|RNTCP)\b", "medical", "section_national_programme"),
    (r"\b(medicolegal|medico[- ]legal|legal aspect|forensic|court|testimony|evidence act)\b", "medical", "section_medicolegal"),
    (r"\b(statistic(s|al)|incidence rate|prevalence rate|odds ratio|relative risk|standard deviation)\b", "medical", "section_statistics"),
    # ---- Structural sections ----
    (r"\b(defined as|definition of|refers to|is a\s+(?:disease|disorder|condition|syndrome))\b", "structure", "section_definition"),
    (r"\b(classification|classified|grading|stage[s]? (I{1,3}V?|IV|V)|type\s+[1-4]|category)\b", "structure", "section_classification"),
    (r"(?:→|->|⇒|-->)|\b(flow ?chart|algorithm|decision tree)\b", "structure", "section_flowchart"),
    (r"\b(table\s+\d+|tab\.?\s+\d+|see table|as shown in table|in the table)\b", "structure", "section_table"),
    (r"\b(fig\.?\s+\d+|figure\s+\d+|see figure|as shown in figure|illustration|diagram)\b", "structure", "section_diagram"),
    (r"\b(formula|equation|calculation:|[=±×÷∑∫√π])\b", "structure", "section_formula"),
    (r"\b(conclusi(on|ons?)|summary:|in summary|to summarise|key (?:point|message|learning)|take[- ]home (?:point|message))\b", "structure", "section_conclusion"),
]


class QuestionAnalyzer:
    """v1 deterministic analyzer.

    Detects marks from the question dict (the
    :func:`medrack.answer.prompt.build_theory_prompt` convention is
    that the marks are passed alongside the question). Detects
    sections by matching the question text against the same pattern
    bank the v1 chunk metadata extractor uses.

    Future LLM-based analyzers can subclass and override
    :meth:`detect_sections` to use a model call.
    """

    # If this many or more sections match, the question is too broad
    # to filter on — same heuristic as the strategy.
    MAX_SECTIONS = 4

    def analyze(
        self,
        question: dict,
        marks: int | None = None,
    ) -> QuestionAnalysis:
        """Analyze a question dict.

        Parameters
        ----------
        question:
            Question dict (from ``extracted.json``). Must have
            ``question_text``.
        marks:
            Explicit marks value. If None, the analyzer looks at the
            question dict for a ``marks`` field. The
            :func:`medrack.answer.prompt.build_theory_prompt`
            convention is that the orchestrator passes marks
            separately; we accept both forms for flexibility.

        Returns
        -------
        QuestionAnalysis
        """
        text = question.get("question_text", "") or ""
        if marks is None:
            raw_marks = question.get("marks")
            marks = raw_marks if isinstance(raw_marks, int) else None

        sections = self._detect_sections(text)
        # If too many sections match, drop the lower-priority ones
        # (priority is the order in _SECTION_PATTERNS).
        if len(sections) > self.MAX_SECTIONS:
            sections = sections[: self.MAX_SECTIONS]

        return QuestionAnalysis(
            marks=marks,
            target_sections=sections,
            raw_text=text,
        )

    def _detect_sections(self, text: str) -> List[str]:
        """Return matched section names in priority order, deduplicated.

        Priority is the order in :data:`_SECTION_PATTERNS`. The first
        match wins; later matches for the same section name are
        ignored. This means a question that mentions "Management"
        early and "Diagnosis" later returns ``["section_management",
        "section_diagnosis"]`` in that order.
        """
        if not text:
            return []
        seen = set()
        ordered: List[str] = []
        for pattern, _group, name in _SECTION_PATTERNS:
            if name in seen:
                continue
            if re.search(pattern, text, re.IGNORECASE):
                seen.add(name)
                ordered.append(name)
        return ordered


__all__ = ["QuestionAnalysis", "QuestionAnalyzer"]
