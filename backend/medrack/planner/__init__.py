"""medrack.planner — deterministic answer blueprinting (Phase 8).

The Planner is a deterministic component whose only responsibility is to
convert a question into a structured answer blueprint. It is **not** an
autonomous agent: it does not retrieve documents, does not write
prose, and does not perform validation.

Architecture (per the Phase 8 directive):

    Planner -> Blueprint -> Retrieval -> Writer -> Validator

Each layer has a single responsibility. The Planner's contract is:

  Input:  question, subject, marks, metadata_summary, question_type
  Output: Blueprint (JSON-serializable, deterministic, machine-readable)

The Planner's output is consumed downstream by:

  - Retrieval (Phase 9: blueprint retrieval) — uses
    Blueprint.required_metadata_categories to bias retrieval.
  - Writer (Phase 10: prompt generation) — uses Blueprint.sections and
    Blueprint.target_word_counts to organize the answer.

The Planner has no coupling to either of those layers. It is pure
logic.

Isolation
---------
``medrack.planner`` imports nothing from:

  - ``medrack.answer.*``     (writer)
  - ``medrack.retrieval.*``  (retrieval implementation)
  - ``medrack.ingest.*``     (vector index, metadata extractor)
  - ``medrack.bot.*``        (Telegram bot)
  - ``medrack.dashboard.*``  (Web UI)
  - ``medrack.benchmarks.*`` (benchmark framework)

It does import the standard library and ``re`` (for section detection).
Future LLM-based planners can subclass :class:`Planner` and add their
own imports without changing this module.
"""
from medrack.planner.blueprint import (
    Blueprint,
    Section,
    SectionCategory,
    BlueprintEncoder,
    BlueprintDecoder,
)
from medrack.planner.planner import (
    Planner,
    DeterministicPlanner,
    PlannerInput,
    plan_for_question,
)

__all__ = [
    "Blueprint",
    "Section",
    "SectionCategory",
    "BlueprintEncoder",
    "BlueprintDecoder",
    "Planner",
    "DeterministicPlanner",
    "PlannerInput",
    "plan_for_question",
]
