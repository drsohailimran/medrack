# Frontend Integration Readiness Report

**Backend version**: v0.3.0-backend-freeze
**Backend tag**: `v0.3.0-backend-freeze` (commit `6079176`)
**Baseline tag**: `phase-5-baseline` (commit `afba43a`)
**Date**: 2026-06-29

> **Note**: This is a **Readiness Report** (what the backend is
> ready to serve). The operator must build the production
> frontend in Lovable and produce a separate **Integration
> Report** (the result of the integration). This report
> documents the backend's readiness and provides the
> information the operator needs to build the frontend.

---

## Backend status

The MedRack backend is **frozen** at v0.3.0-backend-freeze. The
12 phases of work (ADR 0001-0012) plus the backend freeze
(ADR 0013) define a stable, production-ready platform.

### What the backend provides

- **8 stable Python services** (`medrack.dashboard.services.*`)
  for in-process Python consumers.
- **22 stable HTTP API endpoints** (`/api/v1/*`) for any
  frontend (React, Lovable, CLI, mobile).
- **9 validation rules** with structured `ValidationReport`.
- **Pluggable retrieval layer** (AdaptiveStrategy +
  HeuristicReranker + IdentityReranker).
- **Versioned cache** with stale-while-revalidate semantics.
- **Benchmark framework** with frozen baseline.
- **Comprehensive developer documentation** in `docs/developer/`.

### What the backend does NOT provide

- A production frontend (the operator must build it in
  Lovable or otherwise).
- Authentication / authorization (v1 is open; a future
  project can add OAuth/PKCE).
- WebSocket / SSE for real-time updates (HTTP only).
- Multi-tenant support (single operator only).
- Rate limiting (the operator should add an HTTP reverse
  proxy for production deployments).

---

## API v1 surface (22 endpoints)

### Library management (6)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/v1/library/books` | List all textbooks |
| POST   | `/api/v1/library/books` | Add a book by ingesting a PDF |
| GET    | `/api/v1/library/question-banks` | List question banks |
| GET    | `/api/v1/library/ingestion-status/{book_id}` | Ingestion status for a book |
| DELETE | `/api/v1/library/books/{book_id}` | Remove a book (soft delete) |
| POST   | `/api/v1/library/books/{book_id}/reindex` | Re-index a single book |

### Question generation (4)

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/api/v1/questions/generate` | Generate a single answer |
| POST   | `/api/v1/questions/batch` | Generate a batch of answers |
| POST   | `/api/v1/questions/{qid}/revise` | Revise an existing answer |
| GET    | `/api/v1/questions/stale?module_name=...&dry_run=true` | List (or re-answer) stale answers |

### Pipeline inspection (1)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/v1/pipeline/inspect?qid=...&question_text=...&subject=...&marks=...` | Inspect all 6 pipeline stages |

### Validation (1)

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/api/v1/validation/validate` | Run the validation pipeline against an answer |

### Benchmarks (3)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/v1/benchmarks/runs` | List all benchmark runs |
| GET    | `/api/v1/benchmarks/runs/{run_id}` | Get a full run report |
| GET    | `/api/v1/benchmarks/compare?run_a=...&run_b=...` | Compare two runs |

### Cache (4)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/v1/cache/entries?subject=...&stale_only=...` | List cache entries |
| GET    | `/api/v1/cache/entries/{qid}` | **Get a single cache entry by qid** (added in commit `b35f7a8` for frontend integration) |
| GET    | `/api/v1/cache/status` | Cache status summary |
| POST   | `/api/v1/cache/reanswer` | Mark a cache entry as stale |

### Version (1)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/v1/version` | Get version information |

### Logs (2)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/v1/logs/{name}?n=100` | Tail a log file (ingestion, generation, validation, benchmark) |
| GET    | `/api/v1/logs/{name}/search?query=...&n=100` | Search a log file |

### Root (1)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/` | API metadata (name, version, docs URL) |

---

## Error response shape (consistent across all endpoints)

All API errors use the shape:

```json
{
  "error_code": "RUN_NOT_FOUND",
  "detail": "benchmark run not found: my-run-id"
}
```

- `error_code`: stable, machine-readable identifier (uppercase
  snake_case). Frontends can switch on this for i18n.
- `detail`: human-readable message suitable for display.

### Error codes

| Code | Status | When |
|------|--------|------|
| `RUN_NOT_FOUND` | 404 | Benchmark run not found |
| `CACHE_ENTRY_NOT_FOUND` | 404 | Cache entry not found |
| `UNKNOWN_LOG` | 400 | Unknown log name (valid: ingestion, generation, validation, benchmark) |
| (FastAPI default) | 422 | Validation error (missing/invalid query parameter) |
| (FastAPI default) | 500 | Server error |

---

## Success response shape

All service dataclasses include a `schema_version` field for
forward compatibility:

```json
{
  "schema_version": 1,
  ...
}
```

A future breaking change will bump `schema_version` to 2
**in parallel** (v1 endpoints remain unchanged). Frontends can
ignore `schema_version` for v1 endpoints.

---

## Frontend integration workflow

The operator's workflow for building the production frontend
in Lovable:

1. **Read the docs**: `docs/developer/README.md` first, then
   `api.md` (endpoints), `services.md` (Python services),
   `pipeline.md` (data flow), `cache.md` (cache/versioning).
2. **Build the UI in Lovable**: connect to
   `http://<backend-host>:8000/api/v1/*` (the FastAPI app).
3. **Test against real data**: ingest at least one book,
   generate a few answers, then use the cache/validation/
   pipeline endpoints to inspect.
4. **Verify all workflows**: see the "Frontend workflows" section
   below.
5. **Produce an Integration Report** documenting any issues
   found, fixes applied, and benchmark comparisons.

---

## Frontend workflows (operator's checklist)

When the operator builds the frontend, they should verify the
following end-to-end workflows:

### Workflow 1: First-time setup

1. Open the Library page.
2. See "no books yet" state.
3. Upload a PDF (PSM or FMT).
4. Wait for ingestion to complete (the `POST
   /api/v1/library/books` returns immediately, but ingestion
   takes minutes).
5. Poll `GET /api/v1/library/ingestion-status/{book_id}` until
   `status="succeeded"`.
6. See the book in the library list.

### Workflow 2: Generate a single answer

1. Open the Generate page.
2. Enter a question (e.g. "Discuss the management of diabetes").
3. Select subject (PSM) and marks (10).
4. Click "Generate".
5. Call `POST /api/v1/questions/generate`.
6. While waiting, show a progress indicator (the API takes
   5-30 seconds with a real LLM).
7. On success, show the answer text and a "View PDF" link.
8. Navigate to the answer view; show the validation report
   via `POST /api/v1/validation/validate` (the operator can
   re-validate the answer client-side).

### Workflow 3: View cached answer

1. Open the Cache page.
2. See all cached answers (paginated).
3. Filter by subject or staleness.
4. Click an entry to see the full answer (use `GET
   /api/v1/cache/entries/{qid}`).
5. If stale, show a "Re-answer" button.

### Workflow 4: Pipeline inspection

1. Open the Pipeline page.
2. Enter a question.
3. Click "Inspect Pipeline".
4. Call `GET /api/v1/pipeline/inspect`.
5. Show each of the 6 stages (Planner, Blueprint, Retrieval,
   Reranker, Writer, Validator) with its output and latency.

### Workflow 5: Benchmark comparison

1. Open the Benchmarks page.
2. See a list of past runs.
3. Select two runs.
4. Call `GET /api/v1/benchmarks/compare`.
5. Show the deltas (n_questions, n_success, total_tokens,
   avg_total_latency).

### Workflow 6: Operator dashboard

1. Open the Dashboard page.
2. Show the version info (`GET /api/v1/version`).
3. Show the cache status (`GET /api/v1/cache/status`).
4. Show recent logs (`GET /api/v1/logs/{name}`).

---

## Running the API server

The operator should run the API server in a production-like
configuration:

```bash
# Install
pip install fastapi pydantic uvicorn

# Run with a production ASGI server
uvicorn medrack.dashboard.api.v1:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level info
```

The interactive OpenAPI docs are at `http://localhost:8000/docs`.

### Production deployment notes

- The operator should put the API behind a reverse proxy
  (nginx, caddy) for TLS termination.
- The operator should add rate limiting at the proxy layer
  (MedRack v1 has no built-in rate limiting).
- The operator should configure `$MEDRACK_HOME` to a
  persistent directory (the API uses it for cache, logs,
  benchmarks).
- The operator should set up automatic restarts (systemd,
  supervisord, docker).

---

## Stability contract (for the frontend)

The frontend can rely on:

- **Endpoint stability**: the 22 v1 endpoints are frozen. No
  breaking changes to paths, methods, or response shapes.
- **Schema versioning**: every response includes
  `schema_version`; a v2 will be added in parallel.
- **Error shape**: all errors use `{"error_code", "detail"}`.
- **No authentication in v1**: any client can call any
  endpoint. The operator should add network-level access
  control for production.
- **HTTP only**: no WebSocket, SSE, or streaming in v1.
- **Single operator**: not multi-tenant.

If the operator needs something v1 doesn't provide:

- **Add a new endpoint** (backward-compatible).
- **Add a field to an existing response** (additive, doesn't
  break clients).
- **Bump schema_version to 2** (introduces v2 endpoints
  alongside v1).

---

## Verification

### Backend test suite
- **504/505 pass** in 6:20 (the 1 failure is the pre-existing
  `test_module_mcq::test_extracts_from_real_psm_module`,
  verified pre-Phase-1, not from this readiness change).
- **No regressions** introduced by the new endpoint
  (`b35f7a8`).

### Mock benchmark regression
| Metric | Phase 5 baseline | v0.3.0-backend-freeze | Delta |
|--------|-------------------|------------------------|-------|
| n_questions | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.172s | -0.001s |
| avg_pdf_generation | 0.005s | 0.005s | 0 |

**No regression.** The readiness change is purely additive.

---

## What the operator must do

1. **Build the production frontend** in Lovable or otherwise.
2. **Connect to the API** at `/api/v1/*`.
3. **Test all 6 workflows** (above).
4. **Document any issues** found during integration.
5. **Apply bug fixes** (per the directive: "fixing bugs
   discovered during frontend integration").
6. **Run the test suite** after any backend change.
7. **Run the benchmark suite** after any backend change.
8. **Produce a separate Integration Report** documenting:
   - Frontend stack (Lovable version, framework, etc.)
   - All 6 workflows verified end-to-end
   - Any issues found and their resolutions
   - Any backend changes made (with ADRs and benchmark
     evidence)
   - Final API compatibility verification

The operator should **not** introduce new AI pipeline stages
or change the public API contract (per the directive).

---

## What the operator must NOT do

Per the Frontend Integration Directive v1.0:

- Do NOT redesign backend modules.
- Do NOT introduce new AI pipeline stages.
- Do NOT change public API contracts unless absolutely
  necessary.
- Do NOT break benchmark compatibility.
- Do NOT break cache compatibility.
- Do NOT break version compatibility.

If a frontend requirement cannot be satisfied by the current
API, prefer adding a backward-compatible endpoint (like the
`/api/v1/cache/entries/{qid}` added in `b35f7a8`) rather than
modifying an existing one.

---

## References

- `docs/developer/README.md` — entry point for frontend devs
- `docs/developer/api.md` — full v1 API documentation
- `docs/developer/services.md` — 8 service classes
- `docs/developer/architecture.md` — pipeline architecture
- `docs/developer/pipeline.md` — end-to-end pipeline flow
- `docs/developer/cache.md` — cache and versioning
- `docs/developer/benchmarks.md` — benchmark framework
- `docs/architecture/0001-0013` — 13 ADRs
- `v0.3.0-backend-freeze` tag — release
- `phase-5-baseline` tag — frozen baseline

---

## Sign-off

The MedRack backend is **ready for frontend integration**.

- Backend tag: `v0.3.0-backend-freeze`
- Frontend readiness change: `b35f7a8` (additive endpoint)
- Test suite: 504/505 pass
- Mock benchmark: identical to baseline
- Developer documentation: 7 files in `docs/developer/`
- API: 22 stable endpoints, 13 ADRs

**The operator may now build the production frontend in
Lovable (or otherwise) and connect to `/api/v1/*`.**

The next deliverable is the operator's **Frontend Integration
Report**, not another backend change.
