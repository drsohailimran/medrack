# MedRack Cache & Versioning

This document describes the MedRack answer cache and the
versioning system. The cache is the canonical store of
generated answers; the versioning system ensures that
configuration changes invalidate stale answers.

## Cache overview

The cache is a JSON file store at `$MEDRACK_HOME/cache/`. Each
cache entry corresponds to one generated answer. Entries are
keyed by `(qid, module_name, chapter)`.

```
$MEDRACK_HOME/cache/
├── psm-module-1/
│   ├── diabetes/
│   │   ├── q001.json
│   │   ├── q002.json
│   │   └── ...
│   └── epidemiology/
│       └── ...
└── fmt-module-1/
    └── ...
```

A cache entry contains:

```json
{
  "qid": "q001",
  "subject": "psm",
  "module": "psm-module-1",
  "chapter": "diabetes",
  "question_text": "Discuss the management of diabetes.",
  "answer_text": "Introduction: ...\nManagement: ...",
  "pdf_path": "/home/.../q001.pdf",
  "stale": false,
  "stale_reasons": [],
  "versions": {
    "schema": 2,
    "prompt": 1,
    "retrieval": 1,
    "planner": 0,
    "validator": 0,
    "reranker": 0,
    "renderer": 1
  },
  "target_word_count": 775,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "package_version": "0.3.0-backend-freeze",
  "cached_at": "2025-01-01T00:00:00",
  "last_validated_at": "2025-01-01T00:00:00",
  "validation_score": 0.778
}
```

## Stale-while-revalidate

A cache entry can be in one of two states:
- **Canonical (fresh)**: the answer is valid and current
- **Stale**: the answer is invalid or outdated

The cache is **never silently deleted**. Stale answers remain
on disk for inspection. The operator can:

- **Re-answer** a stale entry: marks the entry as stale and
  triggers a new generation
- **Revise** a stale entry: provides a new question text and
  re-generates

## Staleness rules

An answer is marked stale when ANY of the following is true:

1. **Version mismatch**: any of the `versions` fields (schema,
   prompt, retrieval, planner, validator, reranker, renderer)
   differs from the current `PIPELINE_VERSIONS` constant
2. **Embedding model mismatch**: the answer was generated with
   a different embedding model
3. **Package version mismatch**: the answer was generated with
   a different package version
4. **Word count mismatch**: the actual word count is outside
   ±10% of the target (Phase 2 tolerance)
5. **Validation failure**: the answer fails one or more
   validation rules (Phase 11)

The cache key is `(qid, module_name, chapter, schema_version,
prompt_version, retrieval_version, planner_version,
validator_version, reranker_version, renderer_version,
embedding_model)`. A version mismatch invalidates the cache
hit but preserves the entry on disk.

## Versioning constants

The `PIPELINE_VERSIONS` constant in `medrack/config.py` is the
source of truth for current versions:

```python
PIPELINE_VERSIONS = {
    "schema": 2,
    "prompt": 1,
    "retrieval": 1,
    "planner": 0,
    "validator": 0,
    "reranker": 0,
    "renderer": 1,
}
```

When any version is bumped, ALL existing cache entries for
that version become stale. The operator can then re-answer
selectively or in bulk.

## Version bumping policy

- **Patch bump** (e.g. 0.3.0 → 0.3.1): no version changes
- **Minor bump** (e.g. 0.3.0 → 0.4.0): bump one or more
  component versions (e.g. `prompt: 1 → 2`)
- **Major bump** (e.g. 0.3.0 → 1.0.0): bump the schema
  version, indicating a breaking cache format change

## API surface

The `CacheService` exposes the cache as a stable interface:

```python
from medrack.dashboard.services import CacheService

svc = CacheService()

# List all entries
entries = svc.list_entries()

# List only stale entries
stale = svc.list_entries(stale_only=True)

# Filter by subject
psm = svc.list_entries(subject="psm")

# Get status
status = svc.get_status()
# {"total_entries": 100, "by_subject": {...}, "stale_by_subject": {...}, ...}

# Mark as stale (for re-generation)
result = svc.reanswer("q001")
```

The HTTP API (`/api/v1/cache/*`) wraps these methods.

## Re-generation

The `QuestionService` provides the re-generation interface:

```python
from medrack.dashboard.services import QuestionService, GenerationRequest

svc = QuestionService()

# Re-answer a stale entry
result = svc.generate(GenerationRequest(
    qid="q001",
    question_text="...",
    subject="psm",
    marks=10,
))

# Bulk re-answer (dry-run by default)
dry_run_result = svc.re_answer_stale(module_name="psm-module-1", dry_run=True)
# {"ok": true, "dry_run": true, "stale_count": 5, "stale_qids": [...]}

# Bulk re-answer (actually re-generate)
result = svc.re_answer_stale(module_name="psm-module-1", dry_run=False)
```

## Stability

The cache format is **frozen** as of the Backend Freeze v1.0.
Future changes to the cache format require:
1. Bumping `PIPELINE_VERSIONS["schema"]`
2. A migration path for existing cache entries
3. A new ADR documenting the change

Failed/stale entries are **never silently deleted** (per the
Phase 11 directive). They remain on disk for inspection and
selective re-generation.
