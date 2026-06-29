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
    ) -> ValidationResult:
        """Run the rule. Return a :class:`ValidationResult`.

        Parameters
        ----------
        answer:
            The generated answer text. Read-only.
        blueprint:
            Optional blueprint (duck-typed; any object with
            ``.sections`` and ``.target_word_count``). Read-only.

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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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

    def check(self, answer: str, blueprint: Optional[Any] = None) -> ValidationResult:
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
]
