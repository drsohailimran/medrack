"""medrack.validation.result — Validation result types (Phase 11).

The Validation Pipeline returns structured results. The result types
are pure data — no I/O, no mutation, no LLM calls.

Three types:

  - :class:`Severity` — enum of PASS / WARN / FAIL.
  - :class:`ValidationResult` — a single rule's verdict.
  - :class:`ValidationReport` — the aggregate report for an answer.

The report is the *only* thing the validation pipeline returns.
The pipeline NEVER mutates the answer; it only inspects and reports.

JSON contract
-------------
Both :class:`ValidationResult` and :class:`ValidationReport` are
JSON-serializable so they can be persisted alongside cached
answers for auditing and benchmarking (per the Phase 11 directive:
"Validation results should be stored alongside cached answers for
auditing and benchmarking but must never become part of the
generated answer itself.").
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Severity of a validation result.

    - ``PASS`` — the rule passed; no issue.
    - ``WARN`` — the rule noted a soft issue; the answer may still
      be acceptable.
    - ``FAIL`` — the rule noted a hard issue; the answer fails
      validation.
    """

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class ValidationResult:
    """A single validation rule's verdict.

    Attributes
    ----------
    rule_name:
        The rule's stable identifier (e.g. ``"WordCountRule"``).
    severity:
        PASS, WARN, or FAIL.
    message:
        Human-readable explanation of the verdict.
    details:
        Optional structured details (e.g. a list of offending
        sections for a section-presence rule).
    """

    rule_name: str
    severity: Severity
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "severity": self.severity.value
            if isinstance(self.severity, Severity)
            else self.severity,
            "message": self.message,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidationResult":
        return cls(
            rule_name=d["rule_name"],
            severity=Severity(d["severity"]) if not isinstance(d["severity"], Severity) else d["severity"],
            message=d["message"],
            details=d.get("details"),
        )

    def __bool__(self) -> bool:  # convenience: a result is truthy iff it passes
        return self.severity == Severity.PASS


@dataclass
class ValidationReport:
    """The aggregate report for a single answer.

    Attributes
    ----------
    pass_:
        True iff no rule produced a FAIL verdict.
    score:
        A float in [0.0, 1.0] summarising the report. The default
        computation is ``(PASS + 0.5 * WARN) / total_rules``,
        but custom pipelines can override.
    results:
        The list of per-rule verdicts, in pipeline order.
    failed_rules:
        Names of rules that produced FAIL verdicts. Convenience
        for cache-write logic.
    warnings:
        Names of rules that produced WARN verdicts. Convenience for
        the dashboard / observability layer.
    informational_messages:
        Human-readable notes from rules that did not fail or warn
        but wanted to record something (e.g. "section ordering is
        non-canonical but acceptable").
    """

    pass_: bool
    score: float
    results: List[ValidationResult] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    informational_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "pass": self.pass_,
            "score": self.score,
            "results": [r.to_dict() for r in self.results],
            "failed_rules": list(self.failed_rules),
            "warnings": list(self.warnings),
            "informational_messages": list(self.informational_messages),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidationReport":
        v = d.get("schema_version", 1)
        if v != 1:
            raise ValueError(
                f"Unsupported ValidationReport schema_version: {v} (expected 1)"
            )
        return cls(
            pass_=d["pass"],
            score=d["score"],
            results=[ValidationResult.from_dict(r) for r in d.get("results", [])],
            failed_rules=list(d.get("failed_rules", [])),
            warnings=list(d.get("warnings", [])),
            informational_messages=list(d.get("informational_messages", [])),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "ValidationReport":
        return cls.from_dict(json.loads(s))

    def __bool__(self) -> bool:  # convenience: a report is truthy iff it passes
        return self.pass_


__all__ = [
    "Severity",
    "ValidationResult",
    "ValidationReport",
]
