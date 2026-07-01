"""Planner (Phase 8).

The :class:`Planner` is the public entry point for the planning layer.
It is a thin facade over the :class:`RulesEngine`: the engine does
the actual work, the planner handles input validation and provides a
stable interface for future implementations (LLM-based, hybrid).

The Planner is **not** an autonomous agent. It does not:
  - retrieve documents
  - generate prose
  - perform validation
  - call any LLM

It takes a :class:`PlannerInput` and returns a :class:`Blueprint`.

Architecture (per directive):

    Planner -> Blueprint -> Retrieval -> Writer -> Validator

The Planner is the first stage. It is independent of all later
stages. Future phases can swap in different planners (LLM-based,
hybrid) without changing the downstream contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from medrack.planner.blueprint import Blueprint
from medrack.planner.rules import PlannerInput, RulesEngine


class Planner(ABC):
    """Abstract base class for planners.

    A planner is a pure function: ``(PlannerInput) -> Blueprint``.
    It has no I/O, no side effects, no LLM. Future LLM-based
    planners can subclass and call out to a model.
    """

    @abstractmethod
    def plan(self, inp: PlannerInput) -> Blueprint:
        """Produce a blueprint for the given input."""


class DeterministicPlanner(Planner):
    """v1 deterministic planner.

    Wraps :class:`RulesEngine` with input validation. The v1
    implementation is a pure deterministic rules engine; future
    versions can add LLM-based or hybrid logic without changing
    the caller's interface.
    """

    VALID_QUESTION_TYPES = ("theory", "mcq")
    VALID_MARKS = (5, 10)

    def __init__(self, rules_engine: RulesEngine | None = None) -> None:
        self.rules = rules_engine or RulesEngine()

    def plan(self, inp: PlannerInput) -> Blueprint:
        # Validate input. Failures raise ValueError; the caller is
        # responsible for catching and reporting.
        self._validate(inp)
        return self.rules.plan(inp)

    def _validate(self, inp: PlannerInput) -> None:
        if not inp.question_text:
            raise ValueError("PlannerInput.question_text is required")
        if not inp.subject:
            raise ValueError("PlannerInput.subject is required")
        if inp.question_type not in self.VALID_QUESTION_TYPES:
            raise ValueError(
                f"PlannerInput.question_type must be one of "
                f"{self.VALID_QUESTION_TYPES}; got {inp.question_type!r}"
            )
        if inp.marks is not None and inp.marks not in self.VALID_MARKS:
            raise ValueError(
                f"PlannerInput.marks must be one of {self.VALID_MARKS} "
                f"or None; got {inp.marks!r}"
            )


def plan_for_question(
    *,
    question_text: str,
    subject: str,
    marks: int | None,
    question_type: str = "theory",
    metadata_summary: list | None = None,
) -> Blueprint:
    """Module-level convenience: default planner, default config.

    The v1 entry point. Replaces the implicit "no blueprint" call
    site in the answer pipeline. Future phases can wrap this with
    a caching layer or a different planner.
    """
    inp = PlannerInput(
        question_text=question_text,
        subject=subject,
        marks=marks,
        question_type=question_type,
        metadata_summary=metadata_summary,
    )
    return DeterministicPlanner().plan(inp)


__all__ = ["Planner", "DeterministicPlanner", "plan_for_question"]


# Re-export PlannerInput for convenience
__all__.append("PlannerInput")
