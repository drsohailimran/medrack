"""medrack.dashboard.services — Stable service interfaces (Phase 12).

The dashboard and any future frontend (Lovable, custom React app,
CLI client) consume MedRack's backend through these services.

The services are the **stable application interface** for MedRack.
They:

  - Encapsulate backend logic (no business logic in the dashboard).
  - Return typed, JSON-serializable data structures.
  - Are independently testable.
  - Are versioned (each service has a ``schema_version``).
  - Never mutate backend state without an explicit action method
    (e.g. ``add_book``, ``reindex``).

Service catalog
---------------

- :class:`LibraryService` — textbook and question-bank management.
- :class:`QuestionService` — generate, batch, revise, re-answer.
- :class:`PipelineService` — inspect each pipeline stage.
- :class:`ValidationService` — validation reports.
- :class:`BenchmarkService` — history, reports, comparison.
- :class:`CacheService` — stale answers, versions, selective regen.
- :class:`VersionService` — package, pipeline, baseline versions.
- :class:`LogService` — ingestion, generation, validation, benchmark
  logs.

All services:

  - Are stateless (except for the backend they delegate to).
  - Return data, never HTML or UI affordances.
  - Never directly import from the dashboard (one-way dependency:
    dashboard -> services -> backend).

The services can be consumed by:

  - The existing Gradio dashboard (additive).
  - A new JSON HTTP API (``medrack.dashboard.api``).
  - Future frontends (Lovable, custom React, CLI, etc.).

Stability contract
------------------
- Public method signatures are frozen.
- Return types are JSON-serializable dataclasses with
  ``schema_version``.
- Removing a method is a breaking change; adding a method is not.
- Changing a return type's *shape* is a breaking change; adding
  optional fields is not.
"""
from medrack.dashboard.services.library import (
    BookInfo,
    IngestionStatus,
    LibraryService,
    QuestionBankInfo,
)
from medrack.dashboard.services.questions import (
    GenerationRequest,
    GenerationResult,
    QuestionService,
)
from medrack.dashboard.services.pipeline import (
    PipelineService,
    PipelineStageOutput,
    PipelineTrace,
)
from medrack.dashboard.services.validation import ValidationService
from medrack.dashboard.services.benchmarks import (
    BenchmarkService,
    BenchmarkSummary,
)
from medrack.dashboard.services.cache import (
    CacheEntry,
    CacheService,
)
from medrack.dashboard.services.version import (
    VersionInfo,
    VersionService,
)
from medrack.dashboard.services.logs import LogService

__all__ = [
    "LibraryService",
    "BookInfo",
    "QuestionBankInfo",
    "IngestionStatus",
    "QuestionService",
    "GenerationRequest",
    "GenerationResult",
    "PipelineService",
    "PipelineStageOutput",
    "PipelineTrace",
    "ValidationService",
    "BenchmarkService",
    "BenchmarkSummary",
    "CacheService",
    "CacheEntry",
    "VersionService",
    "VersionInfo",
    "LogService",
]
