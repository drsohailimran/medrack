# MedRack Architecture (Frontend View)

This document describes the complete backend pipeline from a
**frontend perspective only**. It explains what each layer
does, what it accepts, and what it returns. It does **not**
describe implementation details.

The frontend is **not** part of the pipeline. The frontend is
a window into the pipeline. Every layer below is owned by
the backend; the frontend only consumes its outputs.

## The complete pipeline

```
Ingestion
    ↓
Metadata
    ↓
Adaptive Retrieval
    ↓
Planner
    ↓
Blueprint
    ↓
Reranker
    ↓
Writer
    ↓
Validator
    ↓
Versioned Cache
    ↓
PDF Export
    ↓
Dashboard Services
    ↓
REST API
    ↓
[FRONTEND - this app]
```

Each layer has **exactly one responsibility**. The layers are
independent: any layer can be replaced without changing the
others (subject to the data contracts).

---

## 1. Ingestion

**Responsibility**: Convert a PDF textbook into chunks of
text suitable for vector search.

**Inputs**: A PDF file (in `inbox/`, `books/`, or `modules/`)
plus a subject (`psm` or `fmt`).

**Outputs**: Chunks of text (typically 200-500 words each) with
metadata (book_id, page, chapter).

**Boundaries**:
- Frontend triggers ingestion by calling
  `POST /api/v1/library/books` with a PDF path.
- Ingestion is **long-running** (minutes). The frontend polls
  `GET /api/v1/library/ingestion-status/{book_id}` until
  `status="succeeded"`.
- The frontend **never** directly triggers the underlying
  pipeline. It only calls the API.

---

## 2. Metadata

**Responsibility**: Extract structured medical metadata from
each chunk (e.g. "this chunk is about management", "this
chunk is about epidemiology").

**Outputs**: Per-chunk flags for medical sections
(Definition, Epidemiology, Etiology, Management, etc.) and
structural elements (Definition, Table, Figure, Formula,
Conclusion).

**Boundaries**:
- The frontend never reads metadata directly. It receives
  filtered results from the Retrieval layer.
- The metadata is used **inside** the pipeline to filter
  and rank chunks.

---

## 3. Adaptive Retrieval

**Responsibility**: Find the most relevant chunks for a
question, using vector similarity + metadata filters.

**Inputs**: A question embedding, the subject, and a
**Blueprint** (from the Planner).

**Outputs**: A ranked list of chunks (with metadata).

**Heuristics**:
- 5-mark questions retrieve ~5 chunks.
- 10-mark questions retrieve ~8 chunks.
- 15-mark questions retrieve ~10 chunks.
- Single-section questions get a metadata filter (e.g.
  "only management chunks").
- Multi-section questions get no filter (too broad).

**Boundaries**:
- The frontend never directly calls the retrieval layer. It
  receives results from the Writer.
- The frontend **can** inspect retrieval config via
  `GET /api/v1/pipeline/inspect`.

---

## 4. Planner

**Responsibility**: Convert a question into a structured
answer blueprint (list of sections, word allocations).

**Inputs**: Question text, subject, marks, question type
(theory or MCQ).

**Outputs**: A `Blueprint` object with:
- Ordered list of `Section` records (Introduction,
  Definition, Management, etc.)
- Per-section target word count
- Required vs optional sections
- Required metadata categories

**Determinism**: The Planner is **deterministic** — same
input always produces the same blueprint. No LLM calls.

**Boundaries**:
- The frontend never directly calls the Planner. It
  receives the blueprint via the Writer.
- The frontend **can** inspect the Planner output via
  `GET /api/v1/pipeline/inspect`.

---

## 5. Blueprint (Retrieval spec)

**Responsibility**: Enrich the Planner's blueprint with
retrieval-specific metadata (per-section filter, priority,
min/max chunks).

**Inputs**: A `Blueprint` from the Planner.

**Outputs**: A `BlueprintRetrieval` spec with per-section
filters and priorities.

**Boundaries**:
- This is an internal layer; the frontend never sees it
  directly.
- It exists to make retrieval **section-aware**.

---

## 6. Reranker

**Responsibility**: Re-order retrieved chunks by semantic
relevance.

**Inputs**: Question, retrieved chunks, Blueprint Retrieval
spec.

**Outputs**: Reranked chunks (same shape, different order).

**Default behavior**: The default reranker is a no-op
(IdentityReranker). The system functions correctly if
reranking is disabled.

**Optional**: An operator can enable a heuristic reranker or
a real cross-encoder reranker (future). The frontend never
configures this — it's a backend-side operator decision.

**Boundaries**:
- The frontend never directly calls the reranker.
- The frontend **can** inspect reranker config via
  `GET /api/v1/pipeline/inspect`.

---

## 7. Writer

**Responsibility**: Generate the answer prose from the
blueprint and retrieved evidence. Calls the LLM. Renders
the PDF.

**Inputs**: Question, subject, marks, question type, optional
book_id and chapter.

**Outputs**: An answer text (with section headings) and a PDF
file.

**Latency**:
- Cache hit: <1s
- Cache miss with mock LLM: <1s
- Cache miss with real LLM: 5-30s

**Boundaries**:
- The frontend triggers generation via
  `POST /api/v1/questions/generate`. It receives the answer
  text and the PDF path in the response.
- The frontend never directly calls the LLM.

---

## 8. Validator

**Responsibility**: Verify the generated answer satisfies 9
quality rules. Return a structured `ValidationReport`.

**Inputs**: Answer text, optional blueprint.

**Outputs**: A `ValidationReport` with:
- `pass` (True/False): True iff no rule produced a FAIL
- `score` (0-1): PASS=1, WARN=0.5, FAIL=0
- `results` (list of per-rule verdicts)
- `failed_rules`, `warnings`, `informational_messages`

**The 9 rules**:
1. **FormattingRule** — basic formatting checks
2. **HeadingStructureRule** — proper section headings
3. **DuplicateSectionRule** — no duplicate section titles
4. **EmptySectionRule** — no empty sections
5. **WordCountRule** — per-section word count within ±10% of
   blueprint target
6. **RequiredSectionsRule** — all required sections present
7. **BlueprintComplianceRule** — answer matches blueprint
8. **EvidenceCoverageRule** — each section references ≥1
   chunk
9. **ReferenceConsistencyRule** — chunk references are unique

**The validator NEVER mutates the answer.** It only reports.
If validation fails, the answer is cached as **stale**, not
deleted.

**Boundaries**:
- The frontend never directly calls the Validator on a
  generated answer (the backend does this automatically).
- The frontend **can** re-validate an answer (e.g. for a
  preview workflow) via `POST /api/v1/validation/validate`.
- The frontend **can** inspect Validator config via
  `GET /api/v1/pipeline/inspect`.

---

## 9. Versioned Cache

**Responsibility**: Store generated answers and PDFs on disk,
with versioning so that pipeline changes invalidate stale
answers.

**Format**: JSON files at
`$MEDRACK_HOME/cache/{module}/{chapter}/{qid}.json`.

**Cache entry contents**:
- `qid`, `subject`, `module`, `chapter`
- `question_text`, `answer_text`, `pdf_path`
- `stale` (True/False)
- `stale_reasons` (list)
- `versions` (schema, prompt, retrieval, planner, validator,
  reranker, renderer)
- `target_word_count`, `embedding_model`, `package_version`
- `cached_at`, `last_validated_at`, `validation_score`

**Staleness rules**:
- An entry is stale if any of its `versions` fields differ
  from the current `PIPELINE_VERSIONS`.
- An entry is stale if its embedding model differs.
- An entry is stale if its validation failed.
- Stale entries are **never silently deleted**.

**Boundaries**:
- The frontend never writes to the cache.
- The frontend can read cached entries via
  `GET /api/v1/cache/entries` and
  `GET /api/v1/cache/entries/{qid}`.
- The frontend can mark entries as stale via
  `POST /api/v1/cache/reanswer`.

---

## 10. PDF Export

**Responsibility**: Render the answer text to a PDF file.

**Inputs**: Answer text.

**Outputs**: A PDF file at `$MEDRACK_HOME/cache/.../{qid}.pdf`.

**Format**: A4, single-column, with section headings.

**Boundaries**:
- The frontend never directly renders PDFs.
- The frontend opens the cached PDF via its
  `pdf_path` URL.

---

## 11. Dashboard Services (Python)

**Responsibility**: Stable Python interface to all backend
operations. 8 services:
1. `LibraryService` — textbook and question-bank management
2. `QuestionService` — generate / batch / revise / re-answer
3. `PipelineService` — inspect each pipeline stage
4. `ValidationService` — run validation, return report
5. `BenchmarkService` — history, reports, comparison
6. `CacheService` — cache status, stale entries, re-answer
7. `VersionService` — package/pipeline/baseline versions
8. `LogService` — tail/search logs

**Boundaries**:
- The frontend **does not** consume these directly. These
  are for in-process Python consumers (notebooks, scripts).
- The frontend consumes the REST API instead.

---

## 12. REST API

**Responsibility**: Expose the services over HTTP/JSON for
the frontend.

**Endpoint count**: 22 endpoints under `/api/v1/*`.

**Base URL**: `http://localhost:8000/api/v1` (configurable in
production).

**Response shape**:
- Success: JSON with `schema_version: 1`
- Error: `{"error_code": "...", "detail": "..."}`

**Stability**: The API is **frozen** as of
v0.3.0-backend-freeze. No breaking changes.

**See**: `API_REFERENCE.md` for the complete list of
endpoints.

---

## 13. The Frontend (this app)

The frontend is the user's window into the pipeline. It
**only** calls the REST API. It never directly accesses the
backend's internal layers.

The frontend's responsibilities are:
- UI (screens, components, navigation)
- State management
- API calls
- Error handling
- Loading states
- Polling for long-running operations

The frontend is **not** part of the pipeline. It does not
process PDFs, call LLMs, or store answers. It is a pure
consumer of the API.

## End-to-end flow (what the user sees)

1. **User opens the Library page.** Sees the list of imported
   textbooks. (Calls `GET /api/v1/library/books`.)
2. **User imports a PDF.** Uploads, the frontend calls
   `POST /api/v1/library/books`. The frontend polls
   `GET /api/v1/library/ingestion-status/{book_id}` every 5s
   until `status="succeeded"`.
3. **User opens the Generate page.** Enters a question, calls
   `POST /api/v1/questions/generate`. Waits for the response
   (5-30s with real LLM, <1s with mock).
4. **User sees the answer** with the validation report
   (auto-attached by the backend).
5. **User opens the Cache page.** Sees all past answers,
   filtered by subject or staleness. Can re-answer stale
   entries. (Calls `GET /api/v1/cache/entries` and
   `GET /api/v1/cache/entries/{qid}`.)
6. **User opens the Pipeline page.** Enters a question, calls
   `GET /api/v1/pipeline/inspect`. Sees all 6 stages
   (Planner, Blueprint, Retrieval, Reranker, Writer,
   Validator) with their outputs and latencies.
7. **User opens the Benchmarks page.** Sees past runs, can
   compare two. (Calls `GET /api/v1/benchmarks/runs` and
   `GET /api/v1/benchmarks/compare`.)
8. **User opens the Settings page.** Sees version info.
   (Calls `GET /api/v1/version`.)

See `WORKFLOW.md` for the full detail of each workflow.
