# User Workflows

This document describes every complete user workflow. Each
workflow is a sequence of API calls that the frontend makes.

---

## 1. First-time setup

**User intent**: Set up MedRack for the first time.

**API calls**:
1. `GET /api/v1/version` — confirm the backend is running
2. `GET /api/v1/library/books` — see the empty library

**UI**:
1. Welcome screen
2. "Import your first book" CTA
3. Settings page shows version info

**Errors**:
- If `GET /api/v1/version` fails: show "Backend not reachable"
  banner with the API URL.

---

## 2. Import a book

**User intent**: Add a textbook to the library.

**API calls**:
1. (UI) User picks a PDF file via file-upload widget
2. (UI) User selects subject (psm/fmt)
3. `POST /api/v1/library/books?pdf_path=...&subject=...&book_title=...`
4. **Poll** `GET /api/v1/library/ingestion-status/{book_id}`
   every 5s until `status="succeeded"` or `status="failed"`

**Polling logic**:
- Start polling 1s after the POST returns
- Poll every 5s
- Stop polling when `status` is `succeeded` or `failed`
- Timeout after 10 minutes (fail gracefully with a
  "Reindex" button)

**UI**:
1. File upload dialog
2. Progress indicator with the current status
3. Success: book appears in the library list
4. Failure: show the `error` field

**Errors**:
- 400 if `subject` is invalid: show "Subject must be 'psm' or
  'fmt'"

---

## 3. Build knowledge base

**User intent**: Import multiple books and verify they're all
indexed.

**API calls**:
1. `GET /api/v1/library/books` — see all books
2. Filter to show only `indexed=false` (frontend logic)
3. For each non-indexed book, follow workflow 2

**UI**:
- Library page with a status badge per book (indexed, indexing,
  failed)
- "Build KB" CTA if any book is not indexed

---

## 4. Import question bank

**User intent**: Load a regression dataset.

**API calls**:
1. `GET /api/v1/library/question-banks` — see available banks

**UI**:
- Question Banks page with a table of banks
- No "upload" button — banks are pre-loaded by the operator

---

## 5. Generate an answer

**User intent**: Get a structured answer to a question.

**API calls**:
1. `POST /api/v1/questions/generate` (5-30s with real LLM)

**Loading state**:
- Show a spinner with "Generating answer..." text
- The frontend should NOT show a "Cancel" button in v1 (the
  API doesn't support cancellation)

**UI on success**:
1. Show the answer text in a sectioned view (preserving the
   heading structure: Introduction, Definition, Management,
   etc.)
2. Show the validation report (if attached)
3. Provide a "Download PDF" link using `pdf_path`
4. Provide a "View in cache" link

**UI on failure**:
- Show the `error` field
- Provide a "Retry" button

**Cache behavior**:
- If `cache_hit=true`, show "Loaded from cache" badge
- If `cache_hit=false`, show "Generated fresh" badge

---

## 6. Generate a batch

**User intent**: Generate answers for multiple questions at
once (e.g. for benchmarking).

**API calls**:
1. `POST /api/v1/questions/batch` (100-600s with real LLM
   for 20 questions)

**Loading state**:
- Show a long-running spinner
- Optionally: stream progress (NOT supported in v1; the API
  returns the entire response when done)
- For 20 questions, the user should expect ~3-10 minutes
  with a real LLM

**UI on completion**:
- Show a results table: qid, status, cache_hit, token_count
- Provide a "Download all PDFs" button (frontend iterates
  the response and downloads each PDF)

**UI on failure**:
- Show which questions failed and which succeeded
- Allow per-question retry

---

## 7. Revise an answer

**User intent**: Edit a question and regenerate the answer.

**API calls**:
1. (UI) User edits the question text
2. `POST /api/v1/questions/{qid}/revise`

**UI**:
- Modal with a text area for the new question
- "Save & Regenerate" button
- On success, show the new answer
- The old answer is preserved (marked as stale)

---

## 8. Re-answer a stale cached answer

**User intent**: Regenerate an answer that was marked stale
(e.g. because the validator bumped its version).

**API calls**:
1. `GET /api/v1/questions/stale?module_name=...&dry_run=true`
   — preview which answers are stale
2. (UI) User confirms
3. `GET /api/v1/questions/stale?module_name=...&dry_run=false`
   — re-generate

**UI**:
- Cache page shows stale entries
- "Re-answer all stale" button (with confirmation)
- Per-entry "Re-answer" button

---

## 9. Inspect the pipeline

**User intent**: See what the Planner, Blueprint, Retrieval,
Reranker, Writer, and Validator produce for a question.

**API calls**:
1. `GET /api/v1/pipeline/inspect?qid=...&question_text=...&subject=...&marks=...`

**UI**:
- A tabbed view with 6 tabs (one per stage)
- Each tab shows the stage's `output` as a JSON tree
- Latency is shown as a small badge in each tab

**Note**: This is a **read-only** inspection. The actual
retrieval chunks are not returned (use the cache to see
actual chunks).

---

## 10. View a cached answer

**User intent**: Open a previously-generated answer.

**API calls**:
1. `GET /api/v1/cache/entries` — list all entries
2. (UI) User clicks an entry
3. `GET /api/v1/cache/entries/{qid}` — get the full entry

**UI**:
- Cache page with a paginated table
- Click row to expand and show the answer text
- If `is_stale=true`, show a warning badge
- "Re-answer" button for stale entries
- "Download PDF" link

---

## 11. View cache status

**User intent**: See the overall cache health.

**API calls**:
1. `GET /api/v1/cache/status`

**UI**:
- Cache page header shows: total entries, entries by
  subject, stale entries by subject
- "Re-answer stale" button (if any are stale)

---

## 12. View benchmark history

**User intent**: See past benchmark runs.

**API calls**:
1. `GET /api/v1/benchmarks/runs`

**UI**:
- Benchmarks page with a table of runs
- Click a row to see the full report
- "Compare" button (select 2 runs)

---

## 13. Compare two benchmark runs

**User intent**: See the delta between two runs.

**API calls**:
1. `GET /api/v1/benchmarks/compare?run_a=...&run_b=...`

**UI**:
- Side-by-side table: metric, run_a, run_b, delta
- Green for improvements, red for regressions

---

## 14. View logs

**User intent**: See recent log entries.

**API calls**:
1. `GET /api/v1/logs/ingestion?n=50` — last 50 ingestion log
   entries
2. `GET /api/v1/logs/generation?n=50` — last 50 generation
3. `GET /api/v1/logs/validation?n=50` — last 50 validation
4. `GET /api/v1/logs/benchmark?n=50` — last 50 benchmark

**UI**:
- Logs page with 4 tabs (one per log type)
- Each tab shows the last N entries in a scrollable list
- Search box (calls `GET /api/v1/logs/{name}/search?query=...`)

**Note**: v1 does not support real-time log streaming. The
frontend polls periodically if it wants real-time updates.

---

## 15. Settings

**User intent**: View the backend version.

**API calls**:
1. `GET /api/v1/version`

**UI**:
- Settings page shows: package version, pipeline versions,
  benchmark baseline tag

---

## Recommended polling intervals

| Operation | Interval | Timeout |
|-----------|----------|---------|
| Ingestion status | 5s | 10 min |
| Question generation | (single call) | 60s |
| Batch generation | (single call) | 600s |
| Pipeline inspect | (single call) | 30s |
| Validation | (single call) | 30s |
| Benchmark | (single call) | 600s |
| Cache status | (no polling; refresh on action) | n/a |
| Log tail | (no polling; manual refresh) | n/a |
| Stale list | (no polling; refresh on action) | n/a |
| Re-answer | (single call) | 60s per answer |

## Recommended error handling per workflow

| Workflow | Recoverable errors | User action |
|----------|---------------------|-------------|
| Import book | 400 invalid subject | Fix subject, retry |
| Generate answer | 5xx server error | Retry with backoff |
| Batch | 5xx server error | Show partial results, allow retry of failed |
| Inspect pipeline | 5xx | Retry |
| Validate | 422 missing answer | Fix request, retry |
| Cache ops | 404 not found | Show "Entry not found", refresh list |
| Benchmark | 404 not found | Show "Run not found" |
| Logs | 400 unknown log | Show "Invalid log name" |
| Version | (no errors expected) | n/a |

See `FRONTEND_INTEGRATION.md` for the retry policy and
timeout strategy.
