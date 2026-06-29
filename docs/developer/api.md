# MedRack API v1

This document describes the v1 HTTP API. The API is a stable
contract for frontend integration. It is implemented as a
FastAPI router at `medrack.dashboard.api.v1`.

## Base URL

```
http://localhost:8000/api/v1
```

For production deployments, replace `localhost:8000` with the
operator's host/port.

## Error response shape

All API errors use a consistent shape:

```json
{
  "error_code": "RUN_NOT_FOUND",
  "detail": "benchmark run not found: my-run-id"
}
```

- `error_code`: stable, machine-readable identifier
  (uppercase snake_case)
- `detail`: human-readable message suitable for display

| Status code | When |
|-------------|------|
| 200 | Success |
| 400 | Bad request (e.g. unknown log name) |
| 404 | Not found (e.g. unknown benchmark run) |
| 422 | Validation error (FastAPI's default; missing/invalid query parameter) |
| 500 | Server error |

## Success response shape

Success responses are JSON. Dataclasses include a
`schema_version` field for forward compatibility:

```json
{
  "schema_version": 1,
  ...
}
```

## Endpoints

### Library

#### `GET /api/v1/library/books`

List all textbooks in the library.

**Response:** `[BookInfo]`

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

#### `POST /api/v1/library/books`

Add a book by ingesting a PDF.

**Query parameters:**
- `pdf_path` (required)
- `subject` (required: "psm" or "fmt")
- `book_title` (optional)

**Response:** `{"ok": true, "book_id": "...", "path": "...", "subject": "..."}`

#### `GET /api/v1/library/question-banks`

List all question banks (regression datasets).

**Response:** `[QuestionBankInfo]`

#### `GET /api/v1/library/ingestion-status/{book_id}`

Get ingestion status for a single book.

**Response:** `IngestionStatus`

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

#### `DELETE /api/v1/library/books/{book_id}`

Remove a book (soft delete; moves PDF to trash).

**Response:** `{"ok": true, "book_id": "...", "moved_to": "..."}`

#### `POST /api/v1/library/books/{book_id}/reindex`

Re-index a single book.

**Response:** `{"ok": true, ...}`

### Questions

#### `POST /api/v1/questions/generate`

Generate a single answer.

**Request body:**
```json
{
  "qid": "q001",
  "question_text": "Discuss the management of diabetes.",
  "subject": "psm",
  "marks": 10,
  "question_type": "theory",
  "book_id": "park_psm_v4",
  "chapter": "diabetes"
}
```

**Response:** `GenerationResult`

```json
{
  "schema_version": 1,
  "qid": "q001",
  "ok": true,
  "answer_text": "...",
  "pdf_path": "/home/.../q001.pdf",
  "cache_hit": false,
  "error": null,
  "token_count": 1234,
  "latency_seconds": 5.6
}
```

#### `POST /api/v1/questions/batch`

Generate a batch of answers.

**Request body:**
```json
{
  "requests": [GenerationRequest, ...]
}
```

**Response:** `[GenerationResult, ...]`

#### `POST /api/v1/questions/{qid}/revise`

Revise an existing answer.

**Request body:**
```json
{
  "subject": "psm",
  "revised_question_text": "..."
}
```

**Response:** `GenerationResult`

#### `GET /api/v1/questions/stale?module_name=...&dry_run=true`

List (or re-answer) stale cached answers.

**Response:** `{"ok": true, "dry_run": true, "stale_count": N, "stale_qids": [...]}`

### Pipeline

#### `GET /api/v1/pipeline/inspect`

Inspect each pipeline stage for a given question.

**Query parameters:**
- `qid` (required)
- `question_text` (required)
- `subject` (required)
- `marks` (default: 10)
- `question_type` (default: "theory")

**Response:** `PipelineTrace` (6 stages: planner, blueprint, retrieval, reranker, writer, validator)

```json
{
  "schema_version": 1,
  "qid": "q001",
  "stages": [
    {
      "schema_version": 1,
      "stage": "planner",
      "output": {"sections": [...], "target_word_count": 775, ...},
      "latency_seconds": 0.001
    },
    ...
  ],
  "total_latency_seconds": 0.005
}
```

### Validation

#### `POST /api/v1/validation/validate`

Run the validation pipeline against an answer.

**Request body:**
```json
{
  "answer": "Management: real content here...",
  "blueprint": null,
  "disabled_rules": ["FormattingRule"]
}
```

**Response:** `ValidationReport`

```json
{
  "schema_version": 1,
  "pass": true,
  "score": 0.778,
  "results": [
    {"rule_name": "WordCountRule", "severity": "pass", "message": "...", "details": null},
    ...
  ],
  "failed_rules": [],
  "warnings": [],
  "informational_messages": [...]
}
```

### Benchmarks

#### `GET /api/v1/benchmarks/runs`

List all benchmark runs.

**Response:** `[BenchmarkSummary]`

#### `GET /api/v1/benchmarks/runs/{run_id}`

Get a full benchmark run report.

**Errors:** 404 if run not found (see Error response shape)

**Response:** full JSON report (n_questions, n_success, n_failure, cache_hit_rate, total_tokens, latencies, etc.)

#### `GET /api/v1/benchmarks/compare?run_a=...&run_b=...`

Compare two benchmark runs.

**Response:** `{"ok": true, "run_a": "...", "run_b": "...", "delta": {...}}`

### Cache

#### `GET /api/v1/cache/entries?subject=psm&stale_only=false`

List cache entries, optionally filtered by subject and staleness.

**Response:** `[CacheEntry]`

#### `GET /api/v1/cache/status`

Cache status summary.

**Response:**
```json
{
  "total_entries": 100,
  "by_subject": {"psm": 80, "fmt": 20},
  "stale_by_subject": {"psm": 5, "fmt": 0},
  "schema_version": 1
}
```

#### `POST /api/v1/cache/reanswer`

Mark a cache entry as stale (for re-generation).

**Request body:** `{"qid": "q001"}`

**Response:** `{"ok": true, "qid": "q001", "marked_stale": true}`

### Version

#### `GET /api/v1/version`

Get version information.

**Response:**
```json
{
  "schema_version": 1,
  "package_version": "0.3.0-backend-freeze",
  "pipeline_versions": {
    "schema": 2, "prompt": 1, "retrieval": 1,
    "planner": 0, "validator": 0, "reranker": 0, "renderer": 1
  },
  "benchmark_baseline_tag": "phase-5-baseline"
}
```

### Logs

#### `GET /api/v1/logs/{name}?n=100`

Tail a log file. Valid names: `ingestion`, `generation`,
`validation`, `benchmark`.

**Errors:** 400 if name is unknown

**Response:** `[{...log entry...}, ...]`

#### `GET /api/v1/logs/{name}/search?query=...&n=100`

Search a log file for entries containing the query.

**Response:** `[{...matching entries...}, ...]`

## Running the API

```bash
# Install
pip install fastapi pydantic uvicorn

# Run
uvicorn medrack.dashboard.api.v1:app --host 0.0.0.0 --port 8000
```

The interactive OpenAPI docs are at `http://localhost:8000/docs`.

## Stability

The v1 API is **frozen** as of the Backend Freeze v1.0. Future
APIs (v2) will be added in parallel; v1 will not change.

For new functionality:
- Extend existing endpoints
- Add new endpoints
- Never replace existing contracts
- Preserve backward compatibility
