"""medrack.validation.pipeline — Validation Pipeline orchestrator (Phase 11).

The :class:`ValidationPipeline` is the public entry point for the
validation layer. It composes a list of independent rules, runs them
against an answer (and optionally a blueprint), and aggregates their
results into a single :class:`ValidationReport`.

Architecture (per the Phase 11 directive):

    Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator

The Validator is the final quality gate. It receives the generated
answer (and optionally the blueprint) and decides whether the
answer is acceptable for the canonical cache.

Guarantees
----------
The Validation Pipeline:

  - NEVER rewrites the answer.
  - NEVER generates additional text.
  - NEVER retrieves documents.
  - NEVER modifies the planner's output.
  - NEVER modifies the blueprint.
  - NEVER modifies metadata.
  - NEVER modifies reranking.
  - NEVER performs prompt engineering.

If validation fails, the pipeline returns a structured report with
``pass_=False`` and a list of :class:`ValidationResult` records. The
cache-write logic uses the report to decide whether to store the
answer as canonical.

The pipeline is **deterministic** and **side-effect-free**: same
input -> same report, no I/O, no LLM.

Pluggable rules
---------------
The pipeline accepts a list of :class:`Rule` instances. Rules can
be individually enabled/disabled via the ``enabled`` flag. The
v1 ships 9 rules (see :mod:`medrack.validation.rules`):

  - WordCountRule
  - RequiredSectionsRule
  - BlueprintComplianceRule
  - DuplicateSectionRule
  - HeadingStructureRule
  - EvidenceCoverageRule
  - FormattingRule
  - EmptySectionRule
  - ReferenceConsistencyRule

Custom rules can be added by subclassing :class:`Rule` and passing
the new rule to the pipeline.
"""
from __future__ import annotations

from typing import Any, List, Optional, Type

from medrack.validation.result import Severity, ValidationReport, ValidationResult
from medrack.validation.rules import (
    BlueprintComplianceRule,
    DuplicateSectionRule,
    EmptySectionRule,
    EvidenceCoverageRule,
    FormattingRule,
    HeadingStructureRule,
    ReferenceConsistencyRule,
    RequiredSectionsRule,
    Rule,
    WordCountRule,
)


# Default v1 rule set: 9 rules in a sensible order.
# NOTE: these are class references, not instances. The pipeline
# instantiates them at construction time so each pipeline gets
# fresh rule instances (avoids test isolation issues where one
# test mutates a rule's state and the next test sees the mutation).
DEFAULT_RULES: List[type] = [
    FormattingRule,
    HeadingStructureRule,
    DuplicateSectionRule,
    EmptySectionRule,
    WordCountRule,
    RequiredSectionsRule,
    BlueprintComplianceRule,
    EvidenceCoverageRule,
    ReferenceConsistencyRule,
]


class ValidationPipeline:
    """Validation pipeline orchestrator.

    The pipeline runs a list of rules against an answer (and
    optionally a blueprint) and aggregates the results into a
    single :class:`ValidationReport`.

    The pipeline is **deterministic** and **side-effect-free**:
    same input -> same report, no I/O, no LLM.

    The pipeline NEVER mutates the answer. If validation fails, it
    returns a structured report; the cache-write logic uses the
    report to decide whether to store the answer.
    """

    def __init__(self, rules: Optional[List[Rule]] = None) -> None:
        # If no rules provided, instantiate fresh copies of the
        # default rule set. This ensures each pipeline has
        # independent rule instances (avoids test isolation issues
        # where one pipeline's disable_rule mutates shared state).
        if rules is not None:
            self.rules: List[Rule] = list(rules)
        else:
            self.rules = [rule_class() for rule_class in DEFAULT_RULES]

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the pipeline (appended)."""
        self.rules.append(rule)

    def remove_rule(self, rule_name: str) -> None:
        """Remove a rule by name. No-op if not present."""
        self.rules = [r for r in self.rules if r.name != rule_name]

    def enable_rule(self, rule_name: str) -> None:
        """Enable a rule by name. No-op if not present."""
        for r in self.rules:
            if r.name == rule_name:
                r.enabled = True

    def disable_rule(self, rule_name: str) -> None:
        """Disable a rule by name. No-op if not present."""
        for r in self.rules:
            if r.name == rule_name:
                r.enabled = False

    def validate(
        self,
        answer: str,
        blueprint: Optional[Any] = None,
    ) -> ValidationReport:
        """Run the pipeline against an answer.

        Parameters
        ----------
        answer:
            The generated answer text. Read-only.
        blueprint:
            Optional blueprint (duck-typed; any object with
            ``.sections`` and ``.target_word_count``). Read-only.

        Returns
        -------
        ValidationReport
            The aggregate report. Contains:
              - ``pass_``: True iff no rule produced a FAIL verdict.
              - ``score``: a float in [0.0, 1.0] summarising the
                report.
              - ``results``: the list of per-rule verdicts.
              - ``failed_rules``, ``warnings``,
                ``informational_messages``: convenience lists.
        """
        results: List[ValidationResult] = []
        failed: List[str] = []
        warnings: List[str] = []
        info: List[str] = []

        for rule in self.rules:
            if not rule.enabled:
                continue
            result = rule.check(answer, blueprint)
            results.append(result)
            if result.severity == Severity.FAIL:
                failed.append(rule.name)
            elif result.severity == Severity.WARN:
                warnings.append(rule.name)
            # Pass is informational only at the rule level;
            # we don't add a per-pass message to info (would be noisy).
            # If the rule has a message and it's PASS, we can include
            # it as informational (caller can filter).
            if result.severity == Severity.PASS and result.message:
                info.append(f"[{rule.name}] {result.message}")

        # Score: (PASS + 0.5 * WARN) / total enabled rules
        n_total = len(results)
        if n_total == 0:
            # No rules ran — degenerate; treat as PASS with score 1.0
            return ValidationReport(
                pass_=True,
                score=1.0,
                results=[],
                failed_rules=[],
                warnings=[],
                informational_messages=info,
            )
        n_pass = sum(1 for r in results if r.severity == Severity.PASS)
        n_warn = sum(1 for r in results if r.severity == Severity.WARN)
        score = (n_pass + 0.5 * n_warn) / n_total

        return ValidationReport(
            pass_=len(failed) == 0,
            score=score,
            results=results,
            failed_rules=failed,
            warnings=warnings,
            informational_messages=info,
        )


__all__ = [
    "ValidationPipeline",
    "DEFAULT_RULES",
]
