# API Reference

Complete reference for every public API endpoint.

**Base URL**: `http://localhost:8000/api/v1`

**Response shape**:
- Success: JSON with `schema_version: 1`
- Error: `{"error_code": "...", "detail": "..."}`

**Status codes**:
- `200` — Success
- `400` — Bad request
- `404` — Not found
- `422` — Validation error (missing/invalid query parameter)
- `500` — Server error

**Content-Type**: All requests and responses use
`application/json`. The PDF endpoint (not in v1; the PDF is
referenced by `pdf_path`) returns `application/pdf`.

**Authentication**: v1 has no authentication. Add
network-level access control in production.

---

## Table of contents

1. [Root](#root)
2. [Version](#version)
3. [Library Management](#library-management) (6 endpoints)
4. [Question Generation](#question-generation) (4 endpoints)
5. [Pipeline Inspection](#pipeline-inspection) (1 endpoint)
6. [Validation](#validation) (1 endpoint)
7. [Benchmarks](#benchmarks) (3 endpoints)
8. [Cache](#cache) (4 endpoints)
9. [Logs](#logs) (2 endpoints)

**Total**: 22 endpoints

---

## Root

### `GET /`

Returns API metadata.

**Response**:
```json
{
  "name": "MedRack Operator API",
  "version": "1.0.0",
  "docs": "/docs",
  "api": "/api/v1"
}
```

**Status codes**: 200

---

## Version

### `GET /api/v1/version`

Returns the current package, pipeline, and baseline version.

**Response**:
```json
{
  "schema_version": 1,
  "package_version": "0.3.0-backend-freeze",
  "pipeline_versions": {
    "schema": 2,
    "prompt": 1,
    "retrieval": 1,
    "planner": 0,
    "validator": 0,
    "reranker": 0,
    "renderer": 1
  },
  "benchmark_baseline_tag": "phase-5-baseline"
}
```

**Status codes**: 200

**Frontend notes**:
- Display `package_version` prominently in the Settings page.
- Display `benchmark_baseline_tag` so the user knows the
  reference point.
- The `pipeline_versions` map can be used to show "schema v2,
  prompt v1, ..." in a debug panel.

---

## Library Management

### `GET /api/v1/library/books`

List all textbooks in the library.

**Response**: `[BookInfo, ...]`

```json
[
  {
    "schema_version": 1,
    "book_id": "park_psm_v4",
    "title": "Park PSM V4",
    "subject": "psm",
    "path": "/home/.../inbox/park_psm_v4.pdf",
    "indexed": true,
    "indexed_at": "2025-01-01T00:00:00",
    "chunk_count": 1234
  }
]
```

**Status codes**: 200

---

### `POST /api/v1/library/books`

Add a book to the library by ingesting a PDF.

**Query parameters**:
- `pdf_path` (string, required) — absolute path to the PDF
- `subject` (string, required) — `psm` or `fmt`
- `book_title` (string, optional)

**Response**:
```json
{
  "ok": true,
  "book_id": "park_psm_v4",
  "path": "/home/.../inbox/park_psm_v4.pdf",
  "subject": "psm"
}
```

**Status codes**: 200

**Errors**: 400 if `subject` is invalid (not "psm" or "fmt").

**Frontend notes**:
- The frontend typically uses a file-upload widget that
  returns the local file path. The path is passed to this
  endpoint.
- The ingestion is **long-running** (minutes). After this
  call returns, the frontend should poll
  `GET /api/v1/library/ingestion-status/{book_id}` until
  `status="succeeded"`.

---

### `GET /api/v1/library/question-banks`

List all question banks (regression datasets).

**Response**: `[QuestionBankInfo, ...]`

```json
[
  {
    "schema_version": 1,
    "name": "v1",
    "version": "v1",
    "subject": "psm",
    "path": "/home/.../tests/regression_datasets/v1.json",
    "question_count": 20
  }
]
```

**Status codes**: 200

---

### `GET /api/v1/library/ingestion-status/{book_id}`

Get the ingestion status for a single book.

**Path parameters**:
- `book_id` (string, required)

**Response**: `IngestionStatus`

```json
{
  "schema_version": 1,
  "book_id": "park_psm_v4",
  "status": "succeeded",
  "started_at": "2025-01-01T00:00:00",
  "finished_at": "2025-01-01T01:00:00",
  "chunk_count": 1234,
  "error": null
}
```

**Status values**:
- `unknown` — no record exists (book never ingested)
- `pending` — ingestion is queued
- `running` — ingestion is in progress
- `succeeded` — ingestion completed
- `failed` — ingestion failed; see `error` field

**Status codes**: 200

**Frontend notes**:
- Poll this endpoint every 5 seconds while a book is
  ingesting.
- Stop polling when `status` is `succeeded` or `failed`.
- If `status="failed"`, show the `error` field in the UI.

---

### `DELETE /api/v1/library/books/{book_id}`

Remove a book from the library (soft delete; moves PDF to
trash).

**Path parameters**:
- `book_id` (string, required)

**Response**:
```json
{
  "ok": true,
  "book_id": "park_psm_v4",
  "moved_to": "/home/.../trash"
}
```

**Status codes**: 200

**Frontend notes**:
- The vector index is **not** modified by this endpoint.
  Call `POST /api/v1/library/books/{book_id}/reindex` to
  update the index.
- This is a soft delete; the PDF is moved to `trash/`, not
  permanently deleted.

---

### `POST /api/v1/library/books/{book_id}/reindex`

Re-index a single book (re-runs the ingestion pipeline).

**Path parameters**:
- `book_id` (string, required)

**Response**:
```json
{
  "ok": true,
  "book_id": "park_psm_v4"
}
```

**Status codes**: 200

**Frontend notes**:
- Reindexing is long-running. After this call returns, poll
  `GET /api/v1/library/ingestion-status/{book_id}` until
  `status="succeeded"`.

---

## Question Generation

### `POST /api/v1/questions/generate`

Generate a single answer.

**Request body**:
```json
{
  "qid": "q001",
  "question_text": "Discuss the management of diabetes mellitus.",
  "subject": "psm",
  "marks": 10,
  "question_type": "theory",
  "book_id": "park_psm_v4",
  "chapter": "diabetes"
}
```

**Field reference**:
- `qid` (string, required) — stable question identifier
- `question_text` (string, required) — the question
- `subject` (string, required) — `psm` or `fmt`
- `marks` (int, default 10) — 5 or 10
- `question_type` (string, default "theory") — `theory` or
  `mcq`
- `book_id` (string, optional) — limit retrieval to a single
  book
- `chapter` (string, optional) — limit retrieval to a single
  chapter

**Response**: `GenerationResult`

```json
{
  "schema_version": 1,
  "qid": "q001",
  "ok": true,
  "answer_text": "Introduction: Diabetes mellitus is...\nManagement: ...",
  "pdf_path": "/home/.../cache/.../q001.pdf",
  "cache_hit": false,
  "error": null,
  "token_count": 1234,
  "latency_seconds": 5.6
}
```

**Field reference**:
- `qid` (string) — echo of the input qid
- `ok` (bool) — True if generation succeeded
- `answer_text` (string|null) — the answer prose
- `pdf_path` (string|null) — absolute path to the PDF
- `cache_hit` (bool) — True if served from the cache
- `error` (string|null) — error message if `ok=false`
- `token_count` (int) — total tokens consumed
- `latency_seconds` (float) — total wall-clock time

**Status codes**: 200

**Errors**: 422 if any required field is missing or invalid.

**Frontend notes**:
- The response can be slow (5-30s with real LLM). The
  frontend should show a loading indicator.
- If `cache_hit=true`, the answer is in the cache and was
  served immediately.
- If `ok=false`, show the `error` field in the UI.
- The frontend should open the PDF using `pdf_path` (e.g. via
  a download link or iframe).

---

### `POST /api/v1/questions/batch`

Generate answers for a batch of questions.

**Request body**:
```json
{
  "requests": [
    {
      "qid": "q001",
      "question_text": "Discuss the management of diabetes.",
      "subject": "psm",
      "marks": 10
    },
    {
      "qid": "q002",
      "question_text": "Describe the epidemiology of TB.",
      "subject": "psm",
      "marks": 5
    }
  ]
}
```

**Response**: `[GenerationResult, ...]`

**Status codes**: 200

**Frontend notes**:
- Batch is sequential (one at a time, not parallel).
- For 20 questions, expect 100-600 seconds with a real LLM.
- The frontend should NOT block on this endpoint. Use
  background generation and stream results as they arrive
  (but v1 does not support streaming; poll for results).
- For now, the frontend should call this endpoint and
  process the entire response when it returns.

---

### `POST /api/v1/questions/{qid}/revise`

Revise an existing answer with a new question text.

**Path parameters**:
- `qid` (string, required) — the qid to revise

**Request body**:
```json
{
  "subject": "psm",
  "revised_question_text": "Discuss the management and prevention of diabetes."
}
```

**Response**: `GenerationResult` (same shape as generate)

**Status codes**: 200

**Frontend notes**:
- The old answer is marked as stale.
- A new answer is generated with the new question text.

---

### `GET /api/v1/questions/stale`

List (or re-answer) stale cached answers.

**Query parameters**:
- `module_name` (string, required) — e.g. `psm-module-1`
- `dry_run` (bool, default `true`) — if true, return the
  list without regenerating

**Response** (dry_run=true):
```json
{
  "ok": true,
  "dry_run": true,
  "stale_count": 5,
  "stale_qids": ["q001", "q002", "q003", "q004", "q005"]
}
```

**Response** (dry_run=false):
```json
{
  "ok": true,
  "dry_run": false,
  "reanswered_count": 5,
  "results": [GenerationResult, ...]
}
```

**Status codes**: 200

**Frontend notes**:
- The frontend should always call with `dry_run=true` first
  to show the user a preview of which answers would be
  re-generated.
- Then the user can confirm and call with `dry_run=false`.

---

## Pipeline Inspection

### `GET /api/v1/pipeline/inspect`

Inspect all 6 pipeline stages for a question.

**Query parameters**:
- `qid` (string, required) — the question identifier
- `question_text` (string, required) — the question
- `subject` (string, required) — `psm` or `fmt`
- `marks` (int, default 10) — 5 or 10
- `question_type` (string, default "theory") — `theory` or
  `mcq`

**Response**: `PipelineTrace`

```json
{
  "schema_version": 1,
  "qid": "q001",
  "stages": [
    {
      "schema_version": 1,
      "stage": "planner",
      "output": { "sections": [...], "target_word_count": 775 },
      "latency_seconds": 0.001
    },
    {
      "schema_version": 1,
      "stage": "blueprint",
      "output": { "section_specs": [...], "aggregate_metadata_filter": {...} },
      "latency_seconds": 0.001
    },
    {
      "schema_version": 1,
      "stage": "retrieval",
      "output": { "strategy": "AdaptiveStrategy", "top_k_by_marks": {"5": 5, "10": 8} },
      "latency_seconds": 0.0
    },
    {
      "schema_version": 1,
      "stage": "reranker",
      "output": { "metadata_reranker": "MetadataBoostReranker", "default_semantic_reranker": "IdentityReranker" },
      "latency_seconds": 0.0
    },
    {
      "schema_version": 1,
      "stage": "writer",
      "output": { "theory_long_target_words": 775, "theory_short_target_words": 475 },
      "latency_seconds": 0.0
    },
    {
      "schema_version": 1,
      "stage": "validator",
      "output": { "rule_count": 9, "rule_names": [...] },
      "latency_seconds": 0.0
    }
  ],
  "total_latency_seconds": 0.005
}
```

**Status codes**: 200

**Frontend notes**:
- The 6 stages are: planner, blueprint, retrieval, reranker,
  writer, validator. The frontend should display them in
  this order.
- This is a **read-only** inspection. It does not trigger
  real generation. For real generation, use
  `POST /api/v1/questions/generate`.
- The output of each stage is the **configuration**, not
  the result of running the stage. For example, the
  retrieval stage shows the strategy and top_k, not the
  actual retrieved chunks.

---

## Validation

### `POST /api/v1/validation/validate`

Run the validation pipeline against an answer.

**Request body**:
```json
{
  "answer": "Management: real content here...",
  "blueprint": null,
  "disabled_rules": ["FormattingRule"]
}
```

**Field reference**:
- `answer` (string, required) — the answer text
- `blueprint` (object|null, optional) — a blueprint; if
  provided, blueprint-aware rules will run
- `disabled_rules` (string[], optional) — list of rule names
  to disable

**Response**: `ValidationReport`

```json
{
  "schema_version": 1,
  "pass": true,
  "score": 0.778,
  "results": [
    {
      "rule_name": "WordCountRule",
      "severity": "pass",
      "message": "All sections within word-count tolerance",
      "details": null
    }
  ],
  "failed_rules": [],
  "warnings": [],
  "informational_messages": [
    "[FormattingRule] Formatting OK",
    "[HeadingStructureRule] Found 5 section heading(s)"
  ]
}
```

**Field reference**:
- `pass` (bool) — True iff no rule produced a FAIL
- `score` (float, 0-1) — PASS=1, WARN=0.5, FAIL=0
- `results` (array) — per-rule verdicts
- `failed_rules` (string[]) — names of rules that failed
- `warnings` (string[]) — names of rules that warned
- `informational_messages` (string[]) — human-readable
  notes from passing rules

**Status codes**: 200

**Errors**: 422 if `answer` is missing.

**Frontend notes**:
- The validation report is auto-attached to generated
  answers. The frontend can also call this endpoint to
  re-validate an answer (e.g. after the user edits it
  client-side).
- The 9 rules are: FormattingRule, HeadingStructureRule,
  DuplicateSectionRule, EmptySectionRule, WordCountRule,
  RequiredSectionsRule, BlueprintComplianceRule,
  EvidenceCoverageRule, ReferenceConsistencyRule.

---

## Benchmarks

### `GET /api/v1/benchmarks/runs`

List all benchmark runs.

**Response**: `[BenchmarkSummary, ...]`

```json
[
  {
    "schema_version": 1,
    "run_id": "20250629T193408Z",
    "timestamp": "20250629T193408Z",
    "llm_mode": "mock",
    "n_questions": 20,
    "n_success": 40,
    "n_failure": 0,
    "cache_hit_rate": 0.5,
    "total_tokens": 12000,
    "avg_total_latency_seconds": 0.169,
    "avg_pdf_generation_seconds": 0.005,
    "json_report_path": "/home/.../benchmarks/runs/.../run.json",
    "markdown_report_path": "/home/.../benchmarks/runs/.../report.md"
  }
]
```

**Field reference**:
- `run_id` (string) — the run identifier
- `timestamp` (string) — ISO-8601 timestamp
- `llm_mode` (string) — `mock` or `real`
- `n_questions` (int) — number of unique questions
- `n_success` (int) — number of successful operations
  (typically 2 × n_questions: one for the answer, one for
  the PDF)
- `n_failure` (int) — number of failed operations
- `cache_hit_rate` (float, 0-1) — fraction of cache hits
- `total_tokens` (int) — total tokens consumed
- `avg_total_latency_seconds` (float) — average end-to-end
  latency
- `avg_pdf_generation_seconds` (float) — average PDF render
  time
- `json_report_path` (string) — path to the full JSON report
- `markdown_report_path` (string|null) — path to the markdown
  summary

**Status codes**: 200

---

### `GET /api/v1/benchmarks/runs/{run_id}`

Get a full benchmark run report.

**Path parameters**:
- `run_id` (string, required)

**Response**: full JSON report

**Status codes**: 200, 404 if run not found

**Errors**:
- 404 `RUN_NOT_FOUND` — `benchmark run not found: {run_id}`

---

### `GET /api/v1/benchmarks/compare`

Compare two benchmark runs.

**Query parameters**:
- `run_a` (string, required) — first run id
- `run_b` (string, required) — second run id

**Response**:
```json
{
  "ok": true,
  "run_a": "20250629T193408Z",
  "run_b": "20250629T200221Z",
  "delta": {
    "n_questions": 0,
    "n_success": 0,
    "n_failure": 0,
    "cache_hit_rate": 0.0,
    "total_tokens": 0,
    "avg_total_latency_seconds": 0.001
  }
}
```

**Status codes**: 200, 404 if either run is not found

**Errors**:
- 404 `RUN_NOT_FOUND` — one or both runs not found
- 422 if `run_a` or `run_b` is missing

---

## Cache

### `GET /api/v1/cache/entries`

List cache entries, optionally filtered.

**Query parameters**:
- `subject` (string, optional) — `psm` or `fmt`
- `stale_only` (bool, default `false`)

**Response**: `[CacheEntry, ...]`

```json
[
  {
    "schema_version": 1,
    "qid": "q001",
    "subject": "psm",
    "is_stale": false,
    "stale_reasons": [],
    "versions": {
      "schema": 2,
      "prompt": 1,
      "retrieval": 1,
      "planner": 0,
      "validator": 0,
      "reranker": 0,
      "renderer": 1,
      "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
    },
    "target_word_count": 775,
    "cached_at": "2025-01-01T00:00:00",
    "last_validated_at": "2025-01-01T00:00:00",
    "validation_score": 0.778
  }
]
```

**Field reference**:
- `qid` (string) — the question identifier
- `subject` (string) — `psm` or `fmt`
- `is_stale` (bool) — True if the entry is stale
- `stale_reasons` (string[]) — reasons for staleness
- `versions` (object) — version of each pipeline component
  when this entry was generated
- `target_word_count` (int) — the blueprint's target word
  count
- `cached_at` (string|null) — ISO-8601 timestamp of cache
  write
- `last_validated_at` (string|null) — ISO-8601 timestamp of
  last validation
- `validation_score` (float|null) — score from the last
  validation (0-1)

**Status codes**: 200

---

### `GET /api/v1/cache/entries/{qid}`

Get a single cache entry by qid.

**Path parameters**:
- `qid` (string, required) — the question identifier

**Response**: full cache entry dict (includes `answer_text`,
`pdf_path`, etc.)

```json
{
  "qid": "q001",
  "subject": "psm",
  "module": "psm-module-1",
  "chapter": "diabetes",
  "question_text": "Discuss the management of diabetes.",
  "answer_text": "Introduction: ...",
  "pdf_path": "/home/.../cache/.../q001.pdf",
  "stale": false,
  "stale_reasons": [],
  "versions": {...},
  "target_word_count": 775,
  "embedding_model": "...",
  "package_version": "0.3.0-backend-freeze",
  "cached_at": "2025-01-01T00:00:00",
  "last_validated_at": "2025-01-01T00:00:00",
  "validation_score": 0.778
}
```

**Status codes**: 200, 404 if entry not found

**Errors**:
- 404 `CACHE_ENTRY_NOT_FOUND` — `cache entry not found: {qid}`

**Frontend notes**:
- This is the endpoint to call when the user clicks a
  cached entry to view its full content.
- The `answer_text` is the full prose; the `pdf_path` is
  the path to the rendered PDF.
- If the entry is stale, the frontend should show a
  warning and offer a "Re-answer" button.

---

### `GET /api/v1/cache/status`

Get overall cache status.

**Response**:
```json
{
  "total_entries": 100,
  "by_subject": {
    "psm": 80,
    "fmt": 20
  },
  "stale_by_subject": {
    "psm": 5,
    "fmt": 0
  },
  "schema_version": 1
}
```

**Status codes**: 200

**Frontend notes**:
- Display this on the Cache page header.
- If `stale_by_subject.psm > 0`, show a "Re-answer stale"
  button.

---

### `POST /api/v1/cache/reanswer`

Mark a cache entry as stale (for re-generation).

**Request body**:
```json
{
  "qid": "q001"
}
```

**Response**:
```json
{
  "ok": true,
  "qid": "q001",
  "marked_stale": true
}
```

**Status codes**: 200

**Frontend notes**:
- This marks the entry as stale. The actual re-generation
  is the question service's job.
- The frontend should also display the entry as stale in
  the cache list (refetch `GET /api/v1/cache/entries`).

---

## Logs

### `GET /api/v1/logs/{name}`

Tail a log file.

**Path parameters**:
- `name` (string, required) — one of `ingestion`,
  `generation`, `validation`, `benchmark`

**Query parameters**:
- `n` (int, default 100) — number of entries to return

**Response**: `[log entry, ...]`

Each log entry is a JSON object. The shape depends on the
log:
- `ingestion` — `{"book_id": "...", "status": "...", ...}`
- `generation` — `{"qid": "...", "subject": "...", ...}`
- `validation` — `{"qid": "...", "passed": true, ...}`
- `benchmark` — `{"n_questions": 20, ...}`

**Status codes**: 200, 400 if log name is unknown

**Errors**:
- 400 `UNKNOWN_LOG` — `unknown log: {name}. Valid:
  ingestion, generation, validation, benchmark`

**Frontend notes**:
- This returns the **last N entries** (tail). It's a
  rolling window, not a full log.
- For real-time log streaming, the operator would need to
  add WebSocket/SSE support (future).

---

### `GET /api/v1/logs/{name}/search`

Search a log file.

**Path parameters**:
- `name` (string, required) — same as above

**Query parameters**:
- `query` (string, required) — search string
- `n` (int, default 100) — max entries to return

**Response**: `[log entry, ...]`

**Status codes**: 200, 400 if log name is unknown

**Errors**:
- 400 `UNKNOWN_LOG` — same as above
- 422 if `query` is missing

---

## Error response shape (consistent)

All errors use this shape:

```json
{
  "error_code": "RUN_NOT_FOUND",
  "detail": "benchmark run not found: my-run-id"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error_code` | string | Stable, machine-readable identifier (uppercase snake_case) |
| `detail` | string | Human-readable message |

### Error code reference

| Code | Status | When |
|------|--------|------|
| `RUN_NOT_FOUND` | 404 | Benchmark run not found |
| `CACHE_ENTRY_NOT_FOUND` | 404 | Cache entry not found |
| `UNKNOWN_LOG` | 400 | Unknown log name |
| (FastAPI default) | 422 | Validation error (missing/invalid parameter) |
| (FastAPI default) | 500 | Server error |

## Future API versions

If the API needs to change in a breaking way, a new version
(v2) will be added in parallel. v1 endpoints will remain
unchanged. The frontend should always pin to v1.
