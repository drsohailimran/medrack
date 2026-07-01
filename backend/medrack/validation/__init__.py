"""medrack.validation — Validation Pipeline (Phase 11).

The validation layer is the final quality gate in the MedRack
pipeline. It receives the generated answer (and optionally the
blueprint) and decides whether the answer is acceptable for the
canonical cache.

Architecture (per the Phase 11 directive):

    Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator

The Validator is independent of all upstream layers. It consumes
the answer and the blueprint (duck-typed) and returns a structured
:class:`ValidationReport`. It NEVER mutates the answer, NEVER
retrieves documents, NEVER performs prompt engineering.

If validation fails, the pipeline returns a structured report with
``pass_=False`` and a list of per-rule verdicts. The cache-write
logic uses the report to decide whether to store the answer.

Public API
----------
- :class:`Severity` — enum of PASS / WARN / FAIL.
- :class:`ValidationResult` — a single rule's verdict.
- :class:`ValidationReport` — the aggregate report for an answer.
- :class:`Rule` — abstract base class for validation rules.
- 9 v1 rule classes (see :mod:`medrack.validation.rules`).
- :class:`ValidationPipeline` — the orchestrator.

Isolation
---------
``medrack.validation`` imports nothing from:

  - ``medrack.answer.*`` (writer)
  - ``medrack.bot.*`` (Telegram bot)
  - ``medrack.dashboard.*`` (Web UI)
  - ``medrack.benchmarks.*`` (benchmark framework)
  - ``medrack.ingest.*`` (vector index, metadata extractor)
  - ``medrack.retrieval.*`` (retrieval layer)
  - ``medrack.rerankers`` / ``medrack.reranker`` (reranking)

The validator is **duck-typed**: it accepts any object with the
right shape (``.sections``, ``.target_word_count``) as a blueprint.
It does not need to import from ``medrack.planner``.

This keeps the validator independent of the planner (per the
directive) while still allowing blueprint-aware rules.
"""
from medrack.validation.result import (
    Severity,
    ValidationReport,
    ValidationResult,
)
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
from medrack.validation.pipeline import ValidationPipeline, DEFAULT_RULES

__all__ = [
    "Severity",
    "ValidationResult",
    "ValidationReport",
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
    "ValidationPipeline",
    "DEFAULT_RULES",
]
