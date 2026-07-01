# Data Models

This document describes every object exchanged between the
frontend and the backend. The models are also documented in
the OpenAPI spec (`openapi.yaml`).

## Conventions

- All models include a `schema_version: 1` field for forward
  compatibility.
- All optional fields are explicitly marked.
- Dates are ISO-8601 strings.
- Paths are absolute filesystem paths.

## Error response (used by all endpoints)

```typescript
interface ErrorResponse {
  error_code: string;   // e.g. "RUN_NOT_FOUND", "CACHE_ENTRY_NOT_FOUND", "UNKNOWN_LOG"
  detail: string;        // human-readable message
}
```

## BookInfo

A textbook in the library.

```typescript
interface BookInfo {
  schema_version: 1;
  book_id: string;          // e.g. "park_psm_v4"
  title: string;            // e.g. "Park PSM V4"
  subject: "psm" | "fmt" | "unknown";
  path: string;             // absolute path to the source PDF
  indexed: boolean;
  indexed_at: string | null;  // ISO-8601 timestamp
  chunk_count: number;
}
```

Example:
```json
{
  "schema_version": 1,
  "book_id": "park_psm_v4",
  "title": "Park PSM V4",
  "subject": "psm",
  "path": "/home/user/.medrack/inbox/park_psm_v4.pdf",
  "indexed": true,
  "indexed_at": "2025-01-01T00:00:00",
  "chunk_count": 1234
}
```

## QuestionBankInfo

A question bank (regression dataset).

```typescript
interface QuestionBankInfo {
  schema_version: 1;
  name: string;
  version: string;
  subject: "psm" | "fmt";
  path: string;
  question_count: number;
}
```

## IngestionStatus

The status of an ingestion job.

```typescript
interface IngestionStatus {
  schema_version: 1;
  book_id: string;
  status: "unknown" | "pending" | "running" | "succeeded" | "failed";
  started_at: string;
  finished_at: string | null;
  chunk_count: number;
  error: string | null;
}
```

## GenerateRequest

Request body for generating a single answer.

```typescript
interface GenerateRequest {
  qid: string;
  question_text: string;
  subject: "psm" | "fmt";
  marks: 5 | 10 | 15;
  question_type?: "theory" | "mcq";  // default: "theory"
  book_id?: string;
  chapter?: string;
}
```

## GenerationResult

The result of a single answer generation.

```typescript
interface GenerationResult {
  schema_version: 1;
  qid: string;
  ok: boolean;
  answer_text: string | null;
  pdf_path: string | null;     // absolute path to the PDF
  cache_hit: boolean;
  error: string | null;
  token_count: number;
  latency_seconds: number;
}
```

## BatchGenerateRequest

Request body for batch generation.

```typescript
interface BatchGenerateRequest {
  requests: GenerateRequest[];
}
```

## ReviseRequest

Request body for revising an answer.

```typescript
interface ReviseRequest {
  subject: "psm" | "fmt";
  revised_question_text: string;
}
```

## StaleResponse

Response for the stale-answers endpoint.

```typescript
interface StaleResponse {
  ok: boolean;
  dry_run: boolean;
  stale_count?: number;       // when dry_run=true
  stale_qids?: string[];      // when dry_run=true
  reanswered_count?: number;  // when dry_run=false
  results?: GenerationResult[]; // when dry_run=false
}
```

## PipelineTrace

The result of inspecting all 6 pipeline stages.

```typescript
interface PipelineTrace {
  schema_version: 1;
  qid: string;
  stages: PipelineStageOutput[];
  total_latency_seconds: number;
}

interface PipelineStageOutput {
  schema_version: 1;
  stage: "planner" | "blueprint" | "retrieval" | "reranker" | "writer" | "validator";
  output: object;             // stage-specific
  latency_seconds: number;
}
```

The 6 stages are returned in order: `planner`, `blueprint`,
`retrieval`, `reranker`, `writer`, `validator`.

## ValidateRequest

Request body for the validation endpoint.

```typescript
interface ValidateRequest {
  answer: string;
  blueprint?: object | null;
  disabled_rules?: string[];
}
```

## ValidationReport

The result of running the validation pipeline.

```typescript
interface ValidationReport {
  schema_version: 1;
  pass: boolean;
  score: number;              // 0-1
  results: ValidationResult[];
  failed_rules: string[];
  warnings: string[];
  informational_messages: string[];
}

interface ValidationResult {
  rule_name: string;
  severity: "pass" | "warn" | "fail";
  message: string;
  details: object | null;
}
```

The 9 rules are:
1. `FormattingRule`
2. `HeadingStructureRule`
3. `DuplicateSectionRule`
4. `EmptySectionRule`
5. `WordCountRule`
6. `RequiredSectionsRule`
7. `BlueprintComplianceRule`
8. `EvidenceCoverageRule`
9. `ReferenceConsistencyRule`

## BenchmarkSummary

A summary of a single benchmark run.

```typescript
interface BenchmarkSummary {
  schema_version: 1;
  run_id: string;
  timestamp: string;
  llm_mode: "mock" | "real";
  n_questions: number;
  n_success: number;
  n_failure: number;
  cache_hit_rate: number;     // 0-1
  total_tokens: number;
  avg_total_latency_seconds: number;
  avg_pdf_generation_seconds: number;
  json_report_path: string;
  markdown_report_path: string | null;
}
```

## BenchmarkCompareResponse

Response for the compare-runs endpoint.

```typescript
interface BenchmarkCompareResponse {
  ok: boolean;
  run_a: string;
  run_b: string;
  delta: {
    n_questions: number;
    n_success: number;
    n_failure: number;
    cache_hit_rate: number;
    total_tokens: number;
    avg_total_latency_seconds: number;
  };
  error?: string;
}
```

## CacheEntry

A cached answer entry (summary view).

```typescript
interface CacheEntry {
  schema_version: 1;
  qid: string;
  subject: "psm" | "fmt";
  is_stale: boolean;
  stale_reasons: string[];
  versions: {
    schema: number;
    prompt: number;
    retrieval: number;
    planner: number;
    validator: number;
    reranker: number;
    renderer: number;
    embedding_model: string;
  };
  target_word_count: number;
  cached_at: string | null;
  last_validated_at: string | null;
  validation_score: number | null;
}
```

## CacheStatus

Overall cache status.

```typescript
interface CacheStatus {
  total_entries: number;
  by_subject: {
    [subject: string]: number;
  };
  stale_by_subject: {
    [subject: string]: number;
  };
  schema_version: 1;
}
```

## ReanswerRequest / ReanswerResponse

```typescript
interface ReanswerRequest {
  qid: string;
}

interface ReanswerResponse {
  ok: boolean;
  qid: string;
  marked_stale: boolean;
  error?: string;
}
```

## VersionInfo

Version information.

```typescript
interface VersionInfo {
  schema_version: 1;
  package_version: string;       // e.g. "0.3.0-backend-freeze"
  pipeline_versions: {
    schema: number;
    prompt: number;
    retrieval: number;
    planner: number;
    validator: number;
    reranker: number;
    renderer: number;
  };
  benchmark_baseline_tag: string | null;  // e.g. "phase-5-baseline"
}
```

## Settings (frontend-only)

The frontend may want to maintain its own settings object
(client preferences). This is **not** exchanged with the
backend; it's purely a frontend concern.

```typescript
interface Settings {
  theme: "light" | "dark" | "system";
  default_subject: "psm" | "fmt";
  default_marks: 5 | 10 | 15;
  poll_interval_seconds: number;       // default: 5
  log_tail_size: number;               // default: 100
  enable_polling: boolean;             // default: true
}
```

## Project (frontend-only)

The "Project" concept in the directive is a frontend
abstraction that doesn't exist in the backend. The
backend has only `subject` (psm/fmt) and `module` (a
subject-scoped grouping of books). The frontend can
choose to model Projects or not.

## TypeScript types

The frontend team can copy the above interfaces into a
`types.ts` file. Better: use the OpenAPI spec
(`openapi.yaml`) with a code generator like
`openapi-typescript` to auto-generate the types.

## Backend-internal models (NOT exchanged with frontend)

These models exist in the backend but are not part of the
public API. The frontend should never see them.

- `Blueprint` (Planner output)
- `Section` (Planner output)
- `BlueprintRetrieval` (Blueprint Retrieval spec)
- `SectionRetrievalSpec` (per-section retrieval spec)
- `RetrievalResult` (Retrieval engine output)
- `PipelineStageOutput` (Pipeline inspect output; the
  `output` field is opaque to the frontend)

These are internal contracts. The frontend can see
"the Planner output is X" via `pipeline/inspect`, but
should not try to type-check the inner `output` field
beyond what the `pipeline/inspect` documentation says.
