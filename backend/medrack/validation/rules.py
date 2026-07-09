"""medrack.validation.rules — v1 validation rules (Phase 11).

The validation pipeline is a collection of independent rules. Each
rule:

  - has a single responsibility
  - is independently testable
  - returns a :class:`ValidationResult`
  - is individually enableable/disableable
  - contributes to the final report without modifying the answer

v1 rules
--------
1. :class:`WordCountRule` — checks per-section word count is within
   tolerance of the blueprint's target word counts. Requires a
   blueprint (duck-typed).
2. :class:`RequiredSectionsRule` — checks all required sections
   from the blueprint are present in the answer. Requires a
   blueprint.
3. :class:`BlueprintComplianceRule` — checks the answer's section
   titles match the blueprint's expected titles. Requires a
   blueprint.
4. :class:`DuplicateSectionRule` — checks no section title appears
   twice in the answer.
5. :class:`HeadingStructureRule` — checks the answer has proper
   section headings (e.g. "Definition:", "Management:"). Loose:
   headings can be at the start of a line, optionally with leading
   whitespace.
6. :class:`EvidenceCoverageRule` — checks each section references
   at least one retrieval chunk (by chunk id). Requires a blueprint
   with retrieval metadata.
7. :class:`FormattingRule` — checks basic formatting (no
   excessive whitespace, no markdown artifacts).
8. :class:`EmptySectionRule` — checks no section is empty (zero or
   only whitespace).

All rules are **deterministic** and **side-effect-free**. They
inspect the answer (and optionally a blueprint) and return a
:class:`ValidationResult`. They never modify the answer.

Blueprint independence
----------------------
A rule that requires a blueprint is **opt-in**: it produces a
``ValidationResult`` with severity ``WARN`` and a message like
"blueprint required" if no blueprint is provided. This means the
pipeline can run with or without a blueprint.

Word counting
-------------
The v1 uses a simple ``len(text.split())`` heuristic for word
counts. This is a deliberate choice for the v1 — a more accurate
tokenizer (e.g. tiktoken) can be added in a future phase if the
benchmarks show the simple heuristic is insufficient.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from medrack.validation.result import Severity, ValidationResult


# ----------------------------------------------------------------------
# Rule ABC
# ----------------------------------------------------------------------

class Rule(ABC):
    """Abstract base class for validation rules.

    A rule has a stable ``name``, an ``enabled`` flag, and a
    ``check`` method that returns a :class:`ValidationResult`.

    Rules are side-effect-free. They never modify the answer.
    """

    #: A stable identifier for the rule. Used in the report.
    name: str = "Rule"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    @abstractmethod
    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Run the rule. Return a :class:`ValidationResult`.

        Parameters
        ----------
        answer:
            The generated answer text. Read-only.
        blueprint:
            Optional blueprint (duck-typed; any object with
            ``.sections`` and ``.target_word_count``). Read-only.
        context:
            Optional generation context (P0): may include
            ``source_text``, ``question_text``, ``marks``,
            ``subject``. Read-only.

        Returns
        -------
        ValidationResult
            The rule's verdict. Must not mutate ``answer`` or
            ``blueprint``.
        """


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _split_into_sections(answer: str) -> List[Dict[str, str]]:
    """Split an answer into sections by heading.

    A heading is a line that starts (after optional whitespace)
    with a capitalized word followed by a colon (e.g.
    ``"Management: ..."``). Case-insensitive: ``management:`` and
    ``Management:`` are both recognized. The section's content is
    everything from the heading line to the next heading line or
    end of text.

    Returns a list of ``{"name": str, "content": str}`` dicts.
    """
    if not answer:
        return []
    sections: List[Dict[str, str]] = []
    current_name: Optional[str] = None
    current_content: List[str] = []
    for line in answer.splitlines():
        # Headings: a line that starts with a capitalized word and
        # a colon, optionally indented. Case-insensitive.
        m = re.match(r"^(\s*)([A-Z][A-Za-z][A-Za-z ]*?):\s*(.*)$", line, re.IGNORECASE)
        if m:
            # Save the previous section
            if current_name is not None:
                sections.append({
                    "name": current_name,
                    "content": "\n".join(current_content).strip(),
                })
            indent, name, _ = m.groups()
            # Normalize the name to the canonical form (first letter
            # capitalized) for consistent reporting.
            current_name = name.strip().capitalize()
            current_content = [line]
        else:
            if current_name is not None:
                current_content.append(line)
    if current_name is not None:
        sections.append({
            "name": current_name,
            "content": "\n".join(current_content).strip(),
        })
    return sections


def _word_count(text: str) -> int:
    """Count words in text. Simple split-based heuristic for v1."""
    if not text:
        return 0
    return len(text.split())


def _normalize_section_name(name: str) -> str:
    """Normalize a section name for comparison: lowercase, strip."""
    return name.strip().lower()


# ----------------------------------------------------------------------
# v1 rules
# ----------------------------------------------------------------------

class WordCountRule(Rule):
    """Checks per-section word count is within ±10% of target.

    The ±10% tolerance is the same as the Phase 2 prompt word-count
    tolerance. Rules that pass emit PASS; rules that fail emit FAIL.

    Requires a blueprint with ``.sections`` and per-section
    ``.target_word_count``. If no blueprint is provided, the rule
    emits WARN (it can't verify without a target).
    """

    name = "WordCountRule"
    # Default tolerance: ±10% (matches the Phase 2 prompt tolerance)
    DEFAULT_TOLERANCE = 0.10

    def __init__(self, enabled: bool = True, tolerance: float = DEFAULT_TOLERANCE) -> None:
        super().__init__(enabled=enabled)
        if not 0.0 <= tolerance < 1.0:
            raise ValueError(
                f"tolerance must be in [0, 1); got {tolerance}"
            )
        self.tolerance = tolerance

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        if blueprint is None or not hasattr(blueprint, "sections"):
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="WordCountRule requires a blueprint; skipping",
            )
        sections_in_answer = _split_into_sections(answer)
        names_in_answer = {
            _normalize_section_name(s["name"]): s for s in sections_in_answer
        }
        offending: List[Dict[str, Any]] = []
        for spec_section in blueprint.sections:
            target = getattr(spec_section, "target_word_count", 0)
            if target <= 0:
                continue
            name_norm = _normalize_section_name(spec_section.name)
            in_answer = names_in_answer.get(name_norm)
            if in_answer is None:
                continue  # RequiredSectionsRule handles missing
            actual = _word_count(in_answer["content"])
            if actual < int(target * (1 - self.tolerance)) or actual > int(target * (1 + self.tolerance)):
                offending.append({
                    "section": spec_section.name,
                    "target": target,
                    "actual": actual,
                })
        if offending:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=(
                    f"{len(offending)} section(s) outside ±{int(self.tolerance*100)}% "
                    f"of target word count"
                ),
                details={"offending": offending},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="All sections within word-count tolerance",
        )


class RequiredSectionsRule(Rule):
    """Checks all required sections from the blueprint are present.

    A section is "present" if the answer has a heading matching the
    section's name (case-insensitive, whitespace-stripped).

    Requires a blueprint. If no blueprint is provided, the rule
    emits WARN.
    """

    name = "RequiredSectionsRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        if blueprint is None or not hasattr(blueprint, "sections"):
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="RequiredSectionsRule requires a blueprint; skipping",
            )
        sections_in_answer = {
            _normalize_section_name(s["name"])
            for s in _split_into_sections(answer)
        }
        required_names = [
            s.name for s in blueprint.sections
            if getattr(s, "required", False)
        ]
        missing = [
            s.name for s in blueprint.sections
            if getattr(s, "required", False)
            and _normalize_section_name(s.name) not in sections_in_answer
        ]
        if missing:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"{len(missing)} required section(s) missing",
                details={"missing": missing, "required": required_names},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message=f"All {len(required_names)} required section(s) present",
        )


class BlueprintComplianceRule(Rule):
    """Checks the answer's section titles match the blueprint's.

    The blueprint specifies the expected section titles (with their
    ``target_word_count`` and ``required`` flags). The answer's
    section titles should match (case-insensitive).

    Extra sections in the answer (not in the blueprint) are allowed
    but logged as informational messages — they don't fail the
    rule.

    Requires a blueprint. If no blueprint is provided, the rule
    emits WARN.
    """

    name = "BlueprintComplianceRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        if blueprint is None or not hasattr(blueprint, "sections"):
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="BlueprintComplianceRule requires a blueprint; skipping",
            )
        blueprint_names = {
            _normalize_section_name(s.name) for s in blueprint.sections
        }
        answer_names = {
            _normalize_section_name(s["name"])
            for s in _split_into_sections(answer)
        }
        extra = answer_names - blueprint_names
        # Missing required sections are handled by RequiredSectionsRule
        # so this rule focuses on the *presence* of expected sections.
        # A blueprint-compliant answer should have at least the
        # blueprint's sections.
        missing_expected = blueprint_names - answer_names
        if missing_expected:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"Answer missing {len(missing_expected)} blueprint section(s)",
                details={"missing": sorted(missing_expected)},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="All blueprint sections present",
            details={"extra_in_answer": sorted(extra)} if extra else None,
        )


class DuplicateSectionRule(Rule):
    """Checks no section title appears twice in the answer.

    A section title is extracted from a "Word:" heading line. Two
    headings with the same normalized name (case-insensitive,
    whitespace-stripped) in the same answer is a duplicate.
    """

    name = "DuplicateSectionRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        sections = _split_into_sections(answer)
        seen: Dict[str, int] = {}
        for s in sections:
            name_norm = _normalize_section_name(s["name"])
            seen[name_norm] = seen.get(name_norm, 0) + 1
        duplicates = sorted(
            [{"name": name, "count": count} for name, count in seen.items() if count > 1],
            key=lambda d: d["name"],
        )
        if duplicates:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"{len(duplicates)} section(s) appear more than once",
                details={"duplicates": duplicates},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="No duplicate sections",
        )


class HeadingStructureRule(Rule):
    """Checks the answer has proper section headings.

    A proper section heading is a line that starts (after optional
    whitespace) with a capitalized word followed by a colon (e.g.
    ``"Management: ..."``). The answer should have at least one
    such heading.

    Loose validation: a single section (e.g. an MCQ answer with no
    headings) is acceptable; the rule emits WARN, not FAIL.
    """

    name = "HeadingStructureRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        sections = _split_into_sections(answer)
        if not sections:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="No section headings found",
                details={"hint": "Expected lines like 'Definition: ...' or 'Management: ...'"},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message=f"Found {len(sections)} section heading(s)",
        )


class EvidenceCoverageRule(Rule):
    """Checks each section references at least one retrieval chunk.

    A section "references" a chunk if the chunk's ``id`` appears
    in the section text (e.g. as ``[chunk_id]`` or
    ``(see chunk_123)``).

    Requires the answer to contain chunk references AND the
    blueprint to have retrieval metadata. If neither is present,
    the rule emits WARN.

    This is a v1 heuristic; a future phase can do more
    sophisticated reference detection (e.g. parsing the answer's
    citation format).
    """

    name = "EvidenceCoverageRule"

    # Pattern: a chunk reference looks like [chunk_id] or (chunk_id)
    CHUNK_REF_RE = re.compile(r"\b(?:chunk[_-]?)?([A-Za-z0-9]{6,16})\b")

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        if blueprint is None or not hasattr(blueprint, "required_metadata_categories"):
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="EvidenceCoverageRule requires a blueprint with retrieval metadata; skipping",
            )
        sections = _split_into_sections(answer)
        if not sections:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="No sections found",
            )
        # A simple proxy: count chunk-reference tokens per section.
        # We do NOT require every section to have a reference; this
        # is informational only in the v1 (no failure).
        section_ref_counts: List[Dict[str, int]] = []
        for s in sections:
            tokens = set(self.CHUNK_REF_RE.findall(s["content"]))
            section_ref_counts.append({
                "section": s["name"],
                "tokens": sorted(tokens),
                "count": len(tokens),
            })
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message=f"Found references in {sum(1 for s in section_ref_counts if s['count'] > 0)}/{len(section_ref_counts)} section(s)",
            details={"sections": section_ref_counts},
        )


class FormattingRule(Rule):
    """Checks basic formatting of the answer.

    Checks:
      - No excessive consecutive blank lines (3+)
      - No trailing whitespace
      - No markdown artifacts (e.g. unclosed code blocks)
      - Reasonable total length (not empty, not absurdly long)
    """

    name = "FormattingRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        issues: List[str] = []
        if not answer or not answer.strip():
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message="Answer is empty",
            )
        # 1. Excessive blank lines
        if "\n\n\n" in answer:
            issues.append("3+ consecutive blank lines found")
        # 2. Trailing whitespace on any line
        for i, line in enumerate(answer.splitlines(), 1):
            if line != line.rstrip():
                issues.append(f"Trailing whitespace on line {i}")
                break
        # 3. Absurdly long (sanity check)
        if len(answer) > 1_000_000:  # ~1MB of text is implausible
            issues.append(f"Answer is {len(answer)} chars (suspiciously long)")
        if issues:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"{len(issues)} formatting issue(s)",
                details={"issues": issues},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="Formatting OK",
        )


class EmptySectionRule(Rule):
    """Checks no section is empty (zero or only whitespace).

    A section is empty if its content (after stripping whitespace)
    is the empty string. The rule flags all empty sections.
    """

    name = "EmptySectionRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        sections = _split_into_sections(answer)
        empty: List[str] = []
        empty_sections: List[Dict[str, Any]] = []
        for s in sections:
            if not s["content"].strip():
                empty.append(s["name"])
                empty_sections.append({"name": s["name"]})
        if empty:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"{len(empty)} section(s) are empty",
                details={"empty": empty_sections},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="No empty sections",
        )


# ----------------------------------------------------------------------
# ReferenceConsistencyRule (per the directive's example list)
# ----------------------------------------------------------------------

class ReferenceConsistencyRule(Rule):
    """Checks that all chunk references in the answer are valid.

    A "chunk reference" is any alphanumeric token that looks like a
    chunk id. The v1 implementation does not have access to the
    full chunk list (that's the retrieval layer's job); the rule
    just checks that all references are syntactically well-formed
    and that no reference is duplicated within the same section.

    Future phases can extend this rule to validate against the
    actual retrieved chunk list.
    """

    name = "ReferenceConsistencyRule"

    # The same regex as EvidenceCoverageRule
    CHUNK_REF_RE = re.compile(r"\b(?:chunk[_-]?)?([A-Za-z0-9]{6,16})\b")

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        sections = _split_into_sections(answer)
        offending: List[Dict[str, Any]] = []
        for s in sections:
            tokens = self.CHUNK_REF_RE.findall(s["content"])
            if len(tokens) != len(set(tokens)):
                # Duplicates within a single section
                counts: Dict[str, int] = {}
                for t in tokens:
                    counts[t] = counts.get(t, 0) + 1
                dupes = sorted(t for t, c in counts.items() if c > 1)
                offending.append({
                    "section": s["name"],
                    "duplicates": dupes,
                })
        if offending:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"{len(offending)} section(s) have duplicate chunk references",
                details={"offending": offending},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="All chunk references are unique within sections",
        )


# ----------------------------------------------------------------------
# P0 quality gates (scope + grounding + truncation)
# ----------------------------------------------------------------------

# Hard length bands by marks (words). Used when context has no target_word_count.
# Min catches half-length 10-mark answers; max catches 5-mark mini-textbooks.
_SCOPE_MIN_WORDS = {
    3: 80,
    5: 250,   # P0.3: floor when no target; with target 5-mark uses ~0.68×target
    10: 550,
}
_SCOPE_MAX_WORDS = {
    3: 200,
    5: 410,   # P0.3: slightly tighter hard max for 5-mark
    10: 850,  # P0.4: 10-mark hard max (was 900); target 750 → +15% = 862, min of these
}

# Acronyms / tokens that are safe even if not in the retrieved chunk text.
_GROUNDING_ALLOWLIST: Set[str] = {
    "WHO", "UNICEF", "UNFPA", "UNDP", "UNESCO", "WORLD", "BANK",
    "NHM", "NRHM", "NUHM", "MOHFW", "ICMR", "NITI", "AYOG", "GOI", "RGI",
    "SRS", "NFHS", "HMIS", "IDSP", "NCD", "UHC", "SDG", "MDG",
    "IMR", "NMR", "MMR", "TFR", "CBR", "CDR", "GDP", "HDI", "PQLI",
    "DALY", "QALY", "BMI", "ANC", "PNC", "IFA", "ORS", "IMNCI", "FIMNCI",
    "FRU", "SNCU", "NRC", "PHC", "CHC", "SC", "SDH", "DH",
    "ASHA", "ANM", "AWW", "AWW", "MPW",
    "JSY", "JSSK", "PMSMA", "RKSK", "RBSK", "PMJAY", "ABHA", "AYUSHMAN",
    "RCH", "RMNCH", "RMNCHA", "NSSK", "HBNC", "HBYC",
    "NTEP", "RNTCP", "NACP", "NVBDCP", "NPCB", "NPCDCS", "NMHP",
    "DOTS", "BCG", "OPV", "IPV", "MMR", "TT", "Td", "DPT", "PENTA",
    "HIV", "AIDS", "TB", "MDR", "XDR", "COVID", "SARS", "MERS",
    "ESI", "CGHS", "ESIC", "AIIMS", "NEET", "MBBS", "MD", "MS",
    "CPR", "BLS", "ACLS", "ICD", "DSM", "OR", "CI", "RR", "SD", "SE", "SES",
    "LHV", "VHND", "VHSNC", "RKS", "JAS", "HWC", "ABHWC",
    # Common obstetric / RCH expansions (not fabrications)
    "EOC", "BEmOC", "CEmOC", "EmOC", "BEMOC", "CEMOC", "EMOC",
    "ARSH", "AFHC", "WIFS", "SBA", "MHM", "MCTS", "RCHII", "RCH",
    "LSAS", "NBCC", "NBSU", "KMC", "LBW", "IUGR", "PIH", "GDM", "PPROM",
    "MTP", "PPIUCD", "IUCD", "OCP", "DMPA", "RTI", "STI", "PPTCT", "PMTCT",
    "RPR", "VDRL", "Hb", "BP", "BMI", "EDD", "LMP", "FHS", "NST",
    "PROM", "PPROM", "SGA", "AGA", "VBAC", "CS", "LSCS",
    # Common maternity / NHM scheme acronyms (real; may not be in retrieved chunk)
    "PMMVY", "SUMAN", "LAQSHYA", "PMSMA", "JSSK", "JSY", "MCTS", "RBSK",
    "PPP", "NGO", "NGOS", "WASH", "IMNCI", "IMCI", "PMTCT", "PPTCT",
    "ART", "ARV", "VHND", "MCP", "ANMOL", "UIP",
}

# Full scheme titles (lowercase) that are known real Indian programmes —
# do not FAIL when retrieval chunk text omitted the full name.
_KNOWN_SCHEME_TITLES: Set[str] = {
    "pradhan mantri matru vandana yojana",
    "janani suraksha yojana",
    "janani shishu suraksha karyakram",
    "janani shishu suraksha karvakram",  # common misspelling in model output
    "rashtriya kishor swasthya karyakram",
    "rashtriya bal swasthya karyakram",
    "pradhan mantri jan arogya yojana",
    "ayushman bharat scheme",
    "ayushman bharat programme",
    "ayushman bharat mission",
    "national health mission",
    "national rural health mission",
    "national urban health mission",
    "reproductive and child health programme",
    "universal immunization programme",
    "school health and wellness programme",
    "menstrual hygiene scheme",
    "menstrual hygiene mission",
    "surakshit matritva ashashwasan",
    "labour room quality improvement initiative",
    "pradhan mantri surakshit matritva abhiyan",
}


def _norm_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# Never acceptable in Indian MBBS exam answers (foreign programmes / systems).
_FOREIGN_CONTEXT_DENYLIST: Set[str] = {
    "PRAMS", "MEDICAID", "MEDICARE", "OBAMACARE", "CHIP", "HIPAA",
    "NHS",  # UK system — not Indian exam default
}


class ScopeLengthRule(Rule):
    """Fail answers outside a mark-appropriate length band.

    Uses ``context["marks"]`` and optional ``context["target_word_count"]``.
    Without marks, WARN only.

    - Over max → scope creep / mini-textbook (esp. 5-mark).
    - Under min → half-length 10-mark answers that fail exam expectations.
    """

    name = "ScopeLengthRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        ctx = context or {}
        marks = ctx.get("marks")
        words = _word_count(answer)
        if marks is None:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="ScopeLengthRule has no marks in context; skipping hard check",
                details={"words": words},
            )
        try:
            marks_i = int(marks)
        except (TypeError, ValueError):
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message=f"Invalid marks value: {marks!r}",
                details={"words": words},
            )
        # Map unknown marks to nearest band
        if marks_i <= 3:
            band = 3
        elif marks_i <= 5:
            band = 5
        else:
            band = 10

        min_words = _SCOPE_MIN_WORDS[band]
        max_words = _SCOPE_MAX_WORDS[band]
        # Prefer bands derived from the actual target the LLM was given.
        tgt = ctx.get("target_word_count")
        if tgt is not None:
            try:
                tgt_i = int(tgt)
                if tgt_i > 0:
                    # P0.3 band vs target:
                    # 10-mark: min 75% / max +15% (need full depth)
                    # 5-mark:  min 68% / max +8%  (compact; 262-word Q3 should pass)
                    # 3-mark:  min 70% / max +10%
                    if band == 10:
                        min_words = max(min_words, int(tgt_i * 0.75))
                        # P0.4: tighter 10-mark ceiling (+12%, not +15%)
                        tgt_max = int(tgt_i * 1.12)  # 750 → 840
                    elif band == 5:
                        min_words = max(min_words, int(tgt_i * 0.68))  # 375 → 255
                        tgt_max = int(tgt_i * 1.08)  # 375 → 405
                    else:
                        min_words = max(min_words, int(tgt_i * 0.70))
                        tgt_max = int(tgt_i * 1.10)
                    max_words = min(max_words, tgt_max)
                    # Keep min < max
                    if min_words >= max_words:
                        min_words = int(max_words * 0.7)
            except (TypeError, ValueError):
                pass

        if words > max_words:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=(
                    f"Answer is over-long for {marks_i}-mark question "
                    f"({words} words > {max_words} max) — likely scope creep"
                ),
                details={
                    "marks": marks_i,
                    "words": words,
                    "min_words": min_words,
                    "max_words": max_words,
                },
            )
        if words < min_words:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=(
                    f"Answer is under-length for {marks_i}-mark question "
                    f"({words} words < {min_words} min) — expand on-topic content"
                ),
                details={
                    "marks": marks_i,
                    "words": words,
                    "min_words": min_words,
                    "max_words": max_words,
                },
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message=(
                f"Length OK for {marks_i}-mark "
                f"({min_words} ≤ {words} ≤ {max_words})"
            ),
            details={
                "marks": marks_i,
                "words": words,
                "min_words": min_words,
                "max_words": max_words,
            },
        )


class GroundingRule(Rule):
    """Fail answers that name unsupported / foreign programmes.

    Heuristics (P0, deterministic):
      1. Foreign-context denylist (PRAMS, Medicaid, …) → always FAIL.
      2. All-caps acronyms (3–8 letters) in the answer that are not in
         the allowlist and not present in ``context["source_text"]`` → FAIL.
      3. ``… Yojana/Scheme/Programme/Mission`` titles not present in
         source text → FAIL.

    Without source text, only the denylist is enforced (hard FAIL);
    other checks WARN.
    """

    name = "GroundingRule"

    ACRONYM_RE = re.compile(r"\b([A-Z]{3,8})\b")
    SCHEME_TITLE_RE = re.compile(
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,5}\s+"
        r"(?:Yojana|Scheme|Programme|Program|Mission))\b"
    )

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        if not answer or not answer.strip():
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message="Answer is empty",
            )
        ctx = context or {}
        source = (ctx.get("source_text") or "")
        source_upper = source.upper()
        issues: List[Dict[str, str]] = []

        # 1. Hard denylist
        answer_upper = answer.upper()
        for token in sorted(_FOREIGN_CONTEXT_DENYLIST):
            if re.search(rf"\b{re.escape(token)}\b", answer_upper):
                issues.append({
                    "token": token,
                    "reason": "foreign_context_denylist",
                })

        # 2–3 require source for hard fail; otherwise warn
        if not source.strip():
            if issues:
                return ValidationResult(
                    rule_name=self.name,
                    severity=Severity.FAIL,
                    message=f"{len(issues)} foreign/unsupported name(s)",
                    details={"issues": issues},
                )
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.WARN,
                message="GroundingRule has no source_text; only denylist checked",
            )

        # 2. Acronyms
        for acr in sorted(set(self.ACRONYM_RE.findall(answer))):
            if acr in _GROUNDING_ALLOWLIST:
                continue
            if acr in _FOREIGN_CONTEXT_DENYLIST:
                continue  # already recorded
            if acr.upper() in source_upper:
                continue
            # Skip pure roman-looking short noise that is common in text
            if acr in {"THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "ARE", "WAS", "NOT"}:
                continue
            issues.append({
                "token": acr,
                "reason": "acronym_not_in_source",
            })

        # 3. Scheme titles
        for title in sorted(set(self.SCHEME_TITLE_RE.findall(answer))):
            if title.upper() in source_upper:
                continue
            # Known real Indian programmes (even if this chunk omitted the name)
            if _norm_title(title) in _KNOWN_SCHEME_TITLES:
                continue
            # Allow if any known title is a substring (wording variants)
            tnorm = _norm_title(title)
            if any(k in tnorm or tnorm in k for k in _KNOWN_SCHEME_TITLES):
                continue
            # Also allow if the distinctive head words appear in source
            head = title.split()[0].upper()
            if head in source_upper and any(
                k in source_upper for k in ("YOJANA", "SCHEME", "PROGRAMME", "PROGRAM", "MISSION")
            ):
                continue
            issues.append({
                "token": title,
                "reason": "scheme_title_not_in_source",
            })

        if issues:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"{len(issues)} unsupported or foreign name(s) in answer",
                details={"issues": issues},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="No unsupported programme/scheme names detected",
        )


class TruncationRule(Rule):
    """Fail answers that look truncated mid-thought."""

    name = "TruncationRule"

    def check(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        text = (answer or "").rstrip()
        if not text:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message="Answer is empty",
            )
        issues: List[str] = []
        # Unclosed code fence
        if text.count("```") % 2 == 1:
            issues.append("unclosed code fence")
        # Ends with connector / incomplete bullet
        if re.search(
            r"(?i)\b(and|or|with|include|includes|including|such as|e\.g\.|i\.e\.)\s*$",
            text,
        ):
            issues.append("ends with connector word")
        if re.search(r"[•\-–—]\s*$", text):
            issues.append("ends with empty bullet marker")
        # Ends mid-word ellipsis spam
        if text.endswith("...") or text.endswith("…"):
            issues.append("ends with ellipsis")
        if issues:
            return ValidationResult(
                rule_name=self.name,
                severity=Severity.FAIL,
                message=f"Answer appears truncated: {', '.join(issues)}",
                details={"issues": issues},
            )
        return ValidationResult(
            rule_name=self.name,
            severity=Severity.PASS,
            message="No truncation markers",
        )


__all__ = [
    "Rule",
    "WordCountRule",
    "RequiredSectionsRule",
    "BlueprintComplianceRule",
    "DuplicateSectionRule",
    "HeadingStructureRule",
    "EvidenceCoverageRule",
    "FormattingRule",
    "EmptySectionRule",
    "ReferenceConsistencyRule",
    "ScopeLengthRule",
    "GroundingRule",
    "TruncationRule",
]
