# MedRack Service Layer

This document describes the 8 service classes in
`medrack.dashboard.services`. These are the stable Python
interfaces for backend operations. They are the contract for
in-process Python consumers (notebooks, custom scripts, CLIs).

The HTTP API (`medrack.dashboard.api`) is a thin wrapper around
these services. The services are the **stable contract**; the
HTTP API is one of multiple transports.

## Service catalog

| Service | Purpose | Schema version |
|---------|---------|----------------|
| `LibraryService` | Textbook & question-bank management | 1 |
| `QuestionService` | Generate / batch / revise / re-answer | 1 |
| `PipelineService` | Inspect each pipeline stage | 1 |
| `ValidationService` | Run validation, return report | (uses ValidationReport) |
| `BenchmarkService` | History, reports, comparison | 1 |
| `CacheService` | Cache status, stale entries, re-answer | 1 |
| `VersionService` | Package/pipeline/baseline versions | 1 |
| `LogService` | Tail/search logs | (returns raw entries) |

Every service has a `SCHEMA_VERSION` constant. Every dataclass
has a `schema_version` field in `to_dict()`.

## LibraryService

```python
from medrack.dashboard.services import LibraryService

svc = LibraryService()  # uses $MEDRACK_HOME

# List books (read)
books = svc.list_books()
for book in books:
    print(book.to_dict())
# {"schema_version": 1, "book_id": "...", "title": "...", ...}

# List question banks (read)
banks = svc.list_question_banks()

# Get ingestion status (read)
status = svc.get_ingestion_status("park_psm_v4")
print(status.to_dict())

# Action: add a book
result = svc.add_book(
    pdf_path="/path/to/book.pdf",
    subject="psm",
    book_title="Park PSM V4",
)
# {"ok": true, "book_id": "...", "path": "...", "subject": "psm"}

# Action: remove a book (soft delete)
result = svc.remove_book("park_psm_v4")
# {"ok": true, "book_id": "...", "moved_to": "/path/to/trash"}

# Action: re-index
result = svc.reindex("park_psm_v4")
```

## QuestionService

```python
from medrack.dashboard.services import QuestionService, GenerationRequest

svc = QuestionService()

# Generate a single answer
req = GenerationRequest(
    qid="q001",
    question_text="Discuss the management of diabetes.",
    subject="psm",
    marks=10,
    question_type="theory",
    book_id="park_psm_v4",
    chapter="diabetes",
)
result = svc.generate(req)
print(result.to_dict())
# {"schema_version": 1, "qid": "q001", "ok": true, ...}

# Generate a batch
results = svc.generate_batch([req1, req2, req3])

# Revise an existing answer
result = svc.revise(
    qid="q001",
    subject="psm",
    revised_question_text="...",
)

# Re-answer stale answers (dry-run by default)
result = svc.re_answer_stale(module_name="psm-module-1", dry_run=True)
# {"ok": true, "dry_run": true, "stale_count": 5, "stale_qids": [...]}
```

## PipelineService

```python
from medrack.dashboard.services import PipelineService

svc = PipelineService()

# Inspect a single stage
planner_output = svc.inspect_planner(
    question_text="Discuss the management of diabetes.",
    subject="psm",
    marks=10,
)
print(planner_output.to_dict())

# Inspect all 6 stages
trace = svc.inspect(
    qid="q001",
    question_text="Discuss the management of diabetes.",
    subject="psm",
    marks=10,
)
for stage in trace.stages:
    print(f"{stage.stage}: {stage.latency_seconds:.4f}s")
# planner: 0.0010s
# blueprint: 0.0008s
# retrieval: 0.0000s
# reranker: 0.0000s
# writer: 0.0000s
# validator: 0.0000s
```

The `PipelineService.inspect` is **read-only**; it does NOT
trigger real generation. It returns configuration and
*computed-but-not-executed* stage outputs. For real generation,
use `QuestionService`.

## ValidationService

```python
from medrack.dashboard.services import ValidationService

svc = ValidationService()

# Validate an answer (no blueprint)
report = svc.validate("Management: real content here")
print(report.to_dict())
# {"schema_version": 1, "pass": true, "score": 0.778, "results": [...], ...}

# Validate with a blueprint (duck-typed)
report = svc.validate(
    answer="Management: real content here",
    blueprint=bp,  # any object with .sections and .target_word_count
    disabled_rules=["FormattingRule"],
)

# Summarize a report (dashboard-friendly)
summary = svc.summarize(report)
# {"pass": true, "score": 0.778, "failed_rules": [], "warnings": [...], ...}
```

## BenchmarkService

```python
from medrack.dashboard.services import BenchmarkService, BenchmarkSummary

svc = BenchmarkService()  # uses $MEDRACK_HOME/benchmarks/runs/

# List runs
runs = svc.list_runs()
for run in runs:
    print(run.to_dict())

# Get a full run report
data = svc.get_run("phase-5-baseline")
print(data["summary"])

# Compare two runs
comparison = svc.compare("run_a", "run_b")
print(comparison["delta"])
```

## CacheService

```python
from medrack.dashboard.services import CacheService

svc = CacheService()  # uses $MEDRACK_HOME/cache/

# List all cache entries
entries = svc.list_entries()
for entry in entries:
    print(entry.to_dict())

# Filter by subject
psm_entries = svc.list_entries(subject="psm")

# List only stale entries
stale = svc.list_entries(stale_only=True)

# Get cache status
status = svc.get_status()
# {"total_entries": 100, "by_subject": {...}, "stale_by_subject": {...}, ...}

# Mark a cache entry as stale (for re-generation)
result = svc.reanswer("q001")
# {"ok": true, "qid": "q001", "marked_stale": true}
```

## VersionService

```python
from medrack.dashboard.services import VersionService

svc = VersionService()
info = svc.get_info()
print(info.to_dict())
# {"schema_version": 1, "package_version": "0.3.0-backend-freeze",
#  "pipeline_versions": {"schema": 2, "prompt": 1, ...},
#  "benchmark_baseline_tag": "phase-5-baseline"}
```

## LogService

```python
from medrack.dashboard.services import LogService

svc = LogService()  # uses $MEDRACK_HOME/logs/

# Tail the last N entries
entries = svc.tail("ingestion", n=100)
for entry in entries:
    print(entry)

# Search across entries
matches = svc.search("ingestion", "error", n=1000)
```

Valid log names: `ingestion`, `generation`, `validation`,
`benchmark`.

## Stability contract

Public service method signatures are frozen. Removing a method
or changing a return-type shape is a breaking change and
requires a new ADR + schema_version bump.

Adding a new method, or adding optional fields to an existing
return type, is **not** a breaking change.
