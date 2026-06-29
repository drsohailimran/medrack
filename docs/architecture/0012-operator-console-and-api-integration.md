# ADR 0012 — Operator Console & API Integration

- Status: Accepted
- Date: 2026-06-29
- Phase: 12 (Operator Console & API Integration)
- Depends on: ADR 0001-0011 (the established MedRack backend)

## Context

Phases 1-11 produced a complete, stable MedRack backend with the
pipeline:

```
Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator
```

The backend is now considered mature. Phase 12 is **not** a UI
beautification phase. It is an engineering/operational interface
that exposes the complete backend through stable service interfaces
that future frontends (including Lovable) can consume without
requiring backend changes.

## Decision

### Two layers, one backend

Phase 12 introduces two new layers between the backend and any
frontend:

1. **Service layer** (`medrack.dashboard.services`) — stable
   application interfaces (Python classes) that encapsulate
   backend logic. The existing Gradio dashboard and any future
   frontend (Lovable, custom React, CLI) consume these services.
2. **HTTP API layer** (`medrack.dashboard.api.v1`) — a thin
   FastAPI wrapper around the service layer. 21 endpoints under
   `/api/v1/` expose the service methods as JSON HTTP endpoints.

The backend is **not** redesigned. The existing modules
(`medrack.answer`, `medrack.planner`, `medrack.retrieval`,
`medrack.validation`, etc.) are unchanged. The service layer is
a thin facade that delegates to the existing modules.

### Service catalog (8 services)

Each service is stateless and returns JSON-serializable dataclasses
with `schema_version=1`:

1. **LibraryService** — list/add/remove/reindex textbooks, list
   question banks, view ingestion status.
2. **QuestionService** — generate single answer, generate batch,
   revise, re-answer stale.
3. **PipelineService** — inspect each pipeline stage
   (Planner, Blueprint, Retrieval, Reranker, Writer, Validator).
4. **ValidationService** — run the Validation Pipeline against
   an answer; return a structured report.
5. **BenchmarkService** — list benchmark runs, get run report,
   compare two runs.
6. **CacheService** — list cache entries (with staleness filter),
   get cache status, re-answer a cached entry.
7. **VersionService** — get package version, pipeline versions,
   baseline tag.
8. **LogService** — tail ingestion/generation/validation/
   benchmark logs; search logs.

### API surface (21 endpoints)

```
GET    /api/v1/library/books
POST   /api/v1/library/books
GET    /api/v1/library/question-banks
GET    /api/v1/library/ingestion-status/{book_id}
DELETE /api/v1/library/books/{book_id}
POST   /api/v1/library/books/{book_id}/reindex
POST   /api/v1/questions/generate
POST   /api/v1/questions/batch
POST   /api/v1/questions/{qid}/revise
GET    /api/v1/questions/stale
GET    /api/v1/pipeline/inspect
POST   /api/v1/validation/validate
GET    /api/v1/benchmarks/runs
GET    /api/v1/benchmarks/runs/{run_id}
GET    /api/v1/benchmarks/compare
GET    /api/v1/cache/entries
GET    /api/v1/cache/status
POST   /api/v1/cache/reanswer
GET    /api/v1/version
GET    /api/v1/logs/{name}
GET    /api/v1/logs/{name}/search
```

Each endpoint corresponds 1:1 to a service method. The API is a
thin transport layer; all business logic lives in the service
layer.

### Future Lovable integration

The API is designed for a future React frontend built with
Lovable. The contract is:

- JSON in / JSON out
- Pydantic models for request validation
- `schema_version=1` in every response
- Stable method signatures (removing a method is a breaking
  change; adding a method is not)
- Stable return-type *shapes* (adding optional fields is not
  breaking; changing a shape is)

A future Lovable frontend consumes `/api/v1/*` directly. The
service layer is also available for in-process Python
consumption (e.g. Jupyter notebooks, custom scripts).

### Dashboard integration

The existing Gradio dashboard (`medrack.dashboard.app`) is
**untouched**. The new service layer is available for the
dashboard to consume in a future minor revision, but Phase 12
does not migrate the dashboard UI to the services (that would
be a breaking UI change). The services are additive.

### What the Operator Console does NOT do (per directive)

- Does not redesign completed backend modules.
- Does not duplicate backend logic inside the dashboard.
- Does not silently delete cache.
- Does not modify answers from the dashboard.
- Does not introduce new AI pipeline stages.

The dashboard is a presentation layer. Business logic remains in
backend services.

## Architecture guarantee

```
+-------------------+     +--------------------+     +--------+
| Future Frontend   |     | Existing Dashboard |     | CLI    |
| (Lovable, React)  |     | (Gradio)           |     |        |
+-------------------+     +--------------------+     +--------+
         |                          |                    |
         v                          v                    v
+------------------------------------------------------------+
|              medrack.dashboard.api.v1 (FastAPI)           |
|              medrack.dashboard.services (Python)          |
+------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------+
|              MedRack Backend (Phases 1-11, frozen)        |
|  Planner -> Blueprint -> Retrieval -> Reranker ->          |
|  Writer -> Validator                                       |
+------------------------------------------------------------+
```

The service layer is the **stable application interface**. The
HTTP API is one of multiple transports. Future frontends can
choose any transport (HTTP, in-process Python, gRPC).

## Stability contract

- Public service method signatures are frozen.
- Service dataclasses are versioned (`schema_version=1`).
- Return-type *shapes* are frozen (adding optional fields is OK).
- The HTTP API is the public contract for future frontends.
- Removing a method or changing a return-type shape is a
  breaking change.

## Compatibility

- **No changes to existing backend modules.** The 11 phases of
  work (ADR 0001-0011) are unchanged.
- **No changes to the existing Gradio dashboard.** The dashboard
  remains functional; the service layer is available for
  future migration.
- **No changes to the benchmark framework.** Phase 5's framework
  still produces the same numbers.
- **No changes to cached answers.** The services are read-mostly;
  mutations go through explicit action methods.
- **Backward compat**: existing tests pass unchanged.

## Benchmark comparison (mock, vs Phase 5 baseline)

| Metric | Phase 5 | Phase 12 | Delta |
|---|---|---|---|
| n_questions | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.169s | -0.004s |
| avg_pdf_generation | 0.005s | 0.005s | 0 |

**No regression.** Phase 12 is a pure presentation/API addition;
the answer pipeline does not consume it; the benchmark runs the
v0-v11 pipeline and gets the same numbers.

## Out of scope for Phase 12

- **Migrating the existing Gradio dashboard to the services.**
  The dashboard remains on the existing internal API; future
  minor revisions can migrate individual tabs.
- **Lovable frontend.** Phase 12 prepares the API; the actual
  frontend is a future project.
- **Real-time updates (WebSocket/SSE).** v1 is HTTP request/
  response only. Future phases can add streaming.
- **Authentication / authorization.** v1 is open; future phases
  can add OAuth/PKCE (per the existing `oauth-pkce-over-ssh`
  skill).
- **Multi-tenant support.** v1 is single-operator. Multi-tenant
  is a future project.
- **Dashboard visual redesign.** Per the directive: "Do not
  optimize visual appearance. Optimize workflow, maintainability,
  backend separation, API stability."
- **Real LLM benchmark.** Same blocker as Phase 5/6/7/8/9/10/11
  (real-LLM API hang); the operator can re-run
  `medrack.benchmarks.run --llm real` in a quiet session.

## Future direction

The service layer is the foundation for **frontend
independence**. Future phases can:

- Migrate the Gradio dashboard to the services tab-by-tab.
- Build a React frontend (Lovable or otherwise) that consumes
  `/api/v1/*` directly.
- Add WebSocket/SSE for real-time updates (e.g. live ingestion
  progress).
- Add authentication (OAuth/PKCE) for multi-operator use.
- Add per-frontend API surface (e.g. `/api/v2/` if breaking
  changes are needed).
