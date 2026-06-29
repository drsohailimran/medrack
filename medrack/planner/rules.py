"""Deterministic rules for blueprint generation (Phase 8).

The :class:`RulesEngine` is the v1 deterministic core of the Planner.
It takes a :class:`PlannerInput` and produces a :class:`Blueprint`
through a fixed sequence of rule applications.

Why a separate rules engine (not just methods on the Planner)?
---------------------------------------------------------------
The rules are pure functions with no shared state. Splitting them
out makes them independently testable, individually replaceable, and
easy to reason about. Future LLM-based planners can replace the
whole engine; future hybrid planners can replace individual rules.

The rules in v1
----------------
1. **Question classification** — does the question text mention any of
   the 13 medical sections or 7 structural sections? If so, those
   sections are candidates for the blueprint.
2. **Section selection** — from the candidates, pick the ones that
   should be in the answer. The :class:`SectionSelector` applies:
   - ``introduction`` and ``conclusion`` are always included.
   - Detected sections are included if they pass the
     ``MAX_SECTIONS_FOR_5MARK`` / ``MAX_SECTIONS_FOR_10MARK`` cap.
   - If the question is too broad (many candidates), the
     most-confident ones win (priority order of the rule bank).
3. **Section ordering** — fixed canonical order so the answer is
   always structured the same way: ``introduction`` -> detected
   sections in canonical order -> ``conclusion``.
4. **Word allocation** — equal share among non-framing sections, with
   conclusion getting 10%, introduction getting 15%.

The rules engine is **deterministic and I/O-free**. No LLM, no API,
no randomness. Same input -> same output. This is critical for
cache stability and for the future ability to persist blueprints.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from medrack.planner.blueprint import Blueprint, Section, SectionCategory


# ----------------------------------------------------------------------
# Section catalog
# ----------------------------------------------------------------------

# Canonical order of medical sections. Used both for blueprint
# ordering and for priority when too many sections match.
# This is the standard medical-answer ordering: definition first,
# epidemiology next, then etiology, pathogenesis, risk factors,
# classification, clinical features, diagnosis, differential,
# investigations, management, prevention, programme, medicolegal,
# statistics.
MEDICAL_SECTION_ORDER: List[str] = [
    "section_definition",
    "section_epidemiology",
    "section_etiology",
    "section_pathogenesis",
    "section_risk_factors",
    "section_classification",
    "section_clinical_features",
    "section_diagnosis",
    "section_differential_diagnosis",
    "section_investigations",
    "section_management",
    "section_prevention",
    "section_national_programme",
    "section_medicolegal",
    "section_statistics",
]

STRUCTURE_SECTION_ORDER: List[str] = [
    "section_flowchart",
    "section_table",
    "section_diagram",
    "section_formula",
]

# Display names: section_* -> "Definition" / "Epidemiology" / etc.
SECTION_DISPLAY_NAMES: dict = {
    "section_definition": "definition",
    "section_epidemiology": "epidemiology",
    "section_etiology": "etiology",
    "section_pathogenesis": "pathogenesis",
    "section_risk_factors": "risk factors",
    "section_classification": "classification",
    "section_clinical_features": "clinical features",
    "section_diagnosis": "diagnosis",
    "section_differential_diagnosis": "differential diagnosis",
    "section_investigations": "investigations",
    "section_management": "management",
    "section_prevention": "prevention",
    "section_national_programme": "national programme",
    "section_medicolegal": "medicolegal",
    "section_statistics": "statistics",
    "section_flowchart": "flowchart",
    "section_table": "table",
    "section_diagram": "diagram",
    "section_formula": "formula",
}


# ----------------------------------------------------------------------
# Detection patterns (mirror the analyzer/extractor's vocabulary)
# ----------------------------------------------------------------------

# Patterns are intentionally a *superset* of the analyzer's: the
# planner is the source of truth for "what does this question ask?",
# so it can afford to be more permissive here. The analyzer is the
# *retrieval* signal and needs to be conservative; the planner is the
# *answer-structure* signal and can be liberal.
_SECTION_PATTERNS: List[Tuple[str, str, str]] = [
    # (regex, group, section_name)
    (r"\b(management|treatment|therapy|therapeutic|regimen|intervention|drug(s)?)\b", "medical", "section_management"),
    (r"\b(etiology|aetiology|caus(es?|e|ation)|caused by|risk factor)\b", "medical", "section_etiology"),
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
    (r"\b(defined as|definition of|refers to|is a\s+(?:disease|disorder|condition|syndrome))\b", "structure", "section_definition"),
    (r"\b(classification|classified|grading|stage[s]? (I{1,3}V?|IV|V)|type\s+[1-4]|category)\b", "structure", "section_classification"),
    (r"(?:→|->|⇒|-->)|\b(flow ?chart|algorithm|decision tree)\b", "structure", "section_flowchart"),
    (r"\b(table\s+\d+|tab\.?\s+\d+|see table|as shown in table|in the table)\b", "structure", "section_table"),
    (r"\b(fig\.?\s+\d+|figure\s+\d+|see figure|as shown in figure|illustration|diagram)\b", "structure", "section_diagram"),
    (r"\b(formula|equation|calculation:|[=±×÷∑∫√π])\b", "structure", "section_formula"),
]


@dataclass
class PlannerInput:
    """The Planner's input.

    Attributes
    ----------
    question_text:
        The question text. Required.
    subject:
        The subject (e.g. ``"psm"``). Used in the blueprint's
        ``subject`` field; not used for section detection.
    marks:
        ``5`` or ``10`` for theory questions; ``None`` for MCQ.
    question_type:
        ``"theory"`` or ``"mcq"``. Determines target word count and
        section caps.
    metadata_summary:
        Optional summary of available corpus metadata (e.g. a list of
        metadata section names the corpus has). The v1 rules engine
        does not consume this; it is reserved for future phases
        where the planner may skip a section because the corpus has
        no chunks for it.
    """

    question_text: str
    subject: str
    marks: int | None
    question_type: str
    metadata_summary: list | None = None


class RulesEngine:
    """v1 deterministic rules engine.

    Pure: no I/O, no LLM, no randomness. Same input -> same output.

    The engine exposes a single method, :meth:`plan`, that returns a
    :class:`Blueprint`.
    """

    # Target word counts by question type and marks. The writer
    # honors these targets; the v1 prompt templates (Phase 2) are
    # already aware of 5-mark and 10-mark targets.
    TARGET_WORD_COUNTS = {
        ("theory", 5): 475,
        ("theory", 10): 775,
    }

    # Maximum number of detected (non-framing) sections per marks
    # value. Beyond this, the question is too broad and we drop the
    # lowest-priority detections.
    MAX_SECTIONS_FOR_5MARK = 3
    MAX_SECTIONS_FOR_10MARK = 7

    # Word allocation: framing sections get a fixed share of the
    # total target. The remainder is split equally among detected
    # sections.
    INTRODUCTION_SHARE = 0.15
    CONCLUSION_SHARE = 0.10

    # MCQ blueprint: just the question (no structured answer).
    MCQ_MIN_SECTIONS = 1  # "answer" section
    MCQ_TARGET_WORDS = 0

    def plan(self, inp: PlannerInput) -> Blueprint:
        """Produce a blueprint for the given input."""
        if inp.question_type == "mcq":
            return self._plan_mcq(inp)
        return self._plan_theory(inp)

    # ------------------------------------------------------------------
    # Theory blueprints
    # ------------------------------------------------------------------

    def _plan_theory(self, inp: PlannerInput) -> Blueprint:
        target = self._target_word_count(inp)
        detected = self._detect_sections(inp.question_text)
        detected = self._cap_sections(detected, inp.marks)
        sections = self._build_sections(detected, target)
        metadata_categories = sorted(
            {s.metadata_section for s in sections if s.metadata_section}
        )
        return Blueprint(
            subject=inp.subject,
            marks=inp.marks,
            question_type="theory",
            target_word_count=target,
            sections=sections,
            required_metadata_categories=metadata_categories,
        )

    def _plan_mcq(self, inp: PlannerInput) -> Blueprint:
        # MCQ blueprints are minimal: just the answer. The writer
        # is expected to render the MCQ choice, not a structured
        # essay. This is a placeholder for Phase 8; the v1 writer
        # handles MCQs separately.
        return Blueprint(
            subject=inp.subject,
            marks=inp.marks,
            question_type="mcq",
            target_word_count=self.MCQ_TARGET_WORDS,
            sections=[
                Section(
                    name="answer",
                    category=SectionCategory.FRAMING,
                    target_word_count=0,
                    required=True,
                    metadata_section=None,
                ),
            ],
            required_metadata_categories=[],
        )

    # ------------------------------------------------------------------
    # Section detection + selection
    # ------------------------------------------------------------------

    def _detect_sections(self, text: str) -> List[str]:
        """Return matched section names in canonical priority order."""
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
        # Reorder by canonical order (so the blueprint is stable
        # regardless of which pattern matched first).
        canonical = MEDICAL_SECTION_ORDER + STRUCTURE_SECTION_ORDER
        return sorted(ordered, key=lambda n: canonical.index(n) if n in canonical else 999)

    def _cap_sections(self, sections: List[str], marks: int | None) -> List[str]:
        """Cap to the maximum for this marks value, priority by canonical order."""
        if marks == 5:
            cap = self.MAX_SECTIONS_FOR_5MARK
        elif marks == 10:
            cap = self.MAX_SECTIONS_FOR_10MARK
        else:
            cap = max(self.MAX_SECTIONS_FOR_5MARK, self.MAX_SECTIONS_FOR_10MARK)
        return sections[:cap]

    def _build_sections(self, detected: List[str], target: int) -> List[Section]:
        """Construct the ordered Section list with word allocations.

        Layout: [introduction] + detected sections + [conclusion].
        Word allocation: introduction = 15%, conclusion = 10% of
        target; remainder is split equally among detected sections.

        If there are no detected sections, all the "body" word
        allocation goes to the introduction (so the writer still
        writes a sensible-length intro) and the conclusion stays at
        10%.
        """
        # Always-required framing sections
        intro_words = round(target * self.INTRODUCTION_SHARE)
        conclusion_words = round(target * self.CONCLUSION_SHARE)
        body_words = target - intro_words - conclusion_words

        if detected:
            per_section = body_words // len(detected)
            extras = body_words - per_section * len(detected)
            # If only framing sections, fold the body into intro
        else:
            per_section = 0
            extras = 0
            # No detected sections -> the body words go to intro
            # so the writer produces a sensible-length intro.
            intro_words = intro_words + body_words
            body_words = 0

        sections: List[Section] = [
            Section(
                name="introduction",
                category=SectionCategory.FRAMING,
                target_word_count=intro_words,
                required=True,
                metadata_section=None,
            ),
        ]

        for i, sec_name in enumerate(detected):
            is_structure = sec_name in STRUCTURE_SECTION_ORDER
            category = SectionCategory.STRUCTURE if is_structure else SectionCategory.MEDICAL
            words = per_section + (1 if i < extras else 0)
            sections.append(
                Section(
                    name=SECTION_DISPLAY_NAMES.get(sec_name, sec_name),
                    category=category,
                    target_word_count=int(words),
                    required=True,
                    metadata_section=sec_name,
                )
            )

        sections.append(
            Section(
                name="conclusion",
                category=SectionCategory.FRAMING,
                target_word_count=conclusion_words,
                required=True,
                metadata_section=None,
            )
        )
        return sections

    # ------------------------------------------------------------------
    # Word count targets
    # ------------------------------------------------------------------

    def _target_word_count(self, inp: PlannerInput) -> int:
        if inp.marks is None:
            return self.TARGET_WORD_COUNTS[("theory", 10)]
        return self.TARGET_WORD_COUNTS.get(
            (inp.question_type, inp.marks),
            self.TARGET_WORD_COUNTS[("theory", 10)],
        )


__all__ = [
    "PlannerInput",
    "RulesEngine",
    "MEDICAL_SECTION_ORDER",
    "STRUCTURE_SECTION_ORDER",
    "SECTION_DISPLAY_NAMES",
]
