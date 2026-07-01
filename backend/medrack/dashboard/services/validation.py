"""ValidationService — Validation reports (Phase 12).

The :class:`ValidationService` is the stable interface for running
the Validation Pipeline against a single answer and returning the
structured :class:`ValidationReport`.

This is the "Validation" feature requested in the Phase 12 directive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from medrack.validation import ValidationPipeline, ValidationReport, DEFAULT_RULES


class ValidationService:
    """Service for validation reports.

    The service is stateless; it delegates to the existing
    :class:`medrack.validation.ValidationPipeline`.
    """

    SCHEMA_VERSION = 1

    def validate(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
        disabled_rules: Optional[list] = None,
    ) -> ValidationReport:
        """Run the validation pipeline on an answer.

        Parameters
        ----------
        answer:
            The generated answer text.
        blueprint:
            Optional blueprint (duck-typed).
        disabled_rules:
            Optional list of rule names to disable before running.

        Returns
        -------
        ValidationReport
            The structured report (pass/fail, score, per-rule
            results).
        """
        rules = [rule_class() for rule_class in DEFAULT_RULES]
        pipeline = ValidationPipeline(rules=rules)
        if disabled_rules:
            for name in disabled_rules:
                pipeline.disable_rule(name)
        return pipeline.validate(answer, blueprint)

    def summarize(self, report: ValidationReport) -> Dict[str, Any]:
        """Return a dashboard-friendly summary of a report."""
        return {
            "pass": report.pass_,
            "score": report.score,
            "failed_rules": list(report.failed_rules),
            "warnings": list(report.warnings),
            "informational_message_count": len(report.informational_messages),
            "rule_count": len(report.results),
        }


__all__ = ["ValidationService"]
