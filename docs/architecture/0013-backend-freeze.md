# ADR 0013 — Backend Freeze v1.0 (Personal Edition)

- Status: Accepted
- Date: 2026-06-29
- Phase: Backend Freeze (transition)
- Depends on: ADR 0001-0012 (the established MedRack architecture)

## Context

Phases 1-12 produced a complete, stable MedRack backend with
the pipeline:

```
Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator
```

Phase 12 added the Operator Console (8 services + 21 HTTP API
endpoints) that exposes the complete backend through stable
service interfaces that future frontends (Lovable) can consume
without requiring backend changes.

The Backend Freeze Directive v1.0 marks the transition from
backend architecture to frontend product development. The
backend is now considered **feature complete** for the
Personal Edition. No new AI pipeline stages are to be
introduced. No architectural redesign is permitted unless
benchmark evidence demonstrates a measurable deficiency.

## Decision

### Backend components are FROZEN

The following components are frozen at the v0.3.0-backend-freeze
state:

- **Ingestion** (`medrack.ingest.*`)
- **Metadata** (`medrack.ingest.metadata`, `medrack.ingest.extractors`)
- **Adaptive Retrieval** (`medrack.retrieval.engine`,
  `medrack.retrieval.strategy`, `medrack.retrieval.analyzer`)
- **Planner** (`medrack.planner.*`)
- **Blueprint** (`medrack.retrieval.blueprint_retrieval`)
- **Reranker** (`medrack.retrieval.rerankers`)
- **Writer** (`medrack.answer.*`)
- **Validator** (`medrack.validation.*`)
- **Cache** (`medrack.answer.cache`, `medrack.answer.versioning`)
- **Benchmark Framework** (`medrack.benchmarks.*`)
- **Dashboard Services** (`medrack.dashboard.services.*`)
- **API v1** (`medrack.dashboard.api.v1`)

### Future work priorities

Future work should prioritize:

- **Bug fixes** (objectively demonstrable defects)
- **Performance improvements** (measurable via benchmarks)
- **Benchmark-driven optimizations** (only when benchmarks show
  a deficiency)
- **Compatibility improvements** (frontend integration)

### Feature expansion is FORBIDDEN

- No new AI pipeline stages.
- No architectural redesign without benchmark evidence.
- No new dependencies unless required for bug fixes.

### API stability

API v1 is **frozen**. Future APIs (v2) will be added in
parallel; v1 will not change. If new functionality is required:

- Extend existing endpoints
- Add new endpoints
- Never replace existing contracts
- Preserve backward compatibility

### Frontend readiness audit

The Phase 12 directive required a frontend-readiness audit. We
performed the audit and made the following normalizations
(while preserving backward compatibility):

1. **Consistent error response shape**: all API errors now use
   the shape `{"error_code": "...", "detail": "..."}`. The
   `error_code` is a stable, machine-readable identifier
   (uppercase snake_case). The `detail` is a human-readable
   message suitable for display. This wraps FastAPI's default
   HTTPException so the error shape is uniform across the API.

2. **Consistent success response shape**: all service
   dataclasses include a `schema_version` field in `to_dict()`
   for forward compatibility.

3. **Stable endpoint naming**: RESTful, kebab-case, plural
   (`/api/v1/library/books`, `/api/v1/benchmarks/runs`).

4. **Predictable status codes**: 200 (success), 400 (bad
   request), 404 (not found), 422 (validation error), 500
   (server error).

5. **Validation messages suitable for frontend display**: the
   ValidationReport's `message` field is human-readable; the
   `details` field is structured for programmatic access.

### Operator Console stays functional, not redesigned

The existing Operator Console (Gradio dashboard at
`medrack.dashboard.app`) is the engineering interface, not the
final production UI. It remains functional. The new service
layer (`medrack.dashboard.services`) is available for future
migration but the dashboard is not migrated in this freeze
(per the directive: "Do not invest time in visual redesign").

### Developer documentation

The Backend Freeze includes comprehensive developer
documentation for frontend developers:

- `docs/developer/README.md` — entry point, what to read first
- `docs/developer/architecture.md` — the pipeline architecture
- `docs/developer/api.md` — the v1 HTTP API
- `docs/developer/services.md` — the 8 service classes
- `docs/developer/pipeline.md` — end-to-end pipeline flow
- `docs/developer/cache.md` — the cache and versioning system
- `docs/developer/benchmarks.md` — the benchmark framework

The docs assume another developer could build an independent
frontend using only this documentation. They are the contract
for future frontends.

### Code quality audit

A one-time comprehensive audit was performed. Findings:

- 248 "unused imports" were flagged by a static scanner; the
  vast majority are false positives (e.g. `__future__
  annotations` is a feature, not an unused import) or
  intentional re-exports (e.g. `medrack.dashboard.services`
  re-exports service classes for public consumption). No
  objective engineering issues were found.
- The cache service had a latent bug where
  `CacheService.list_entries` called `find_stale_answers`
  with the wrong keyword argument. This was fixed in commit
  `5d0c75b` (the bug only manifested when `stale_only=True`
  was passed; no real cache entries existed in the test
  environment).
- The API error response shape was inconsistent (some
  endpoints used FastAPI's default `{"detail": "..."}`,
  others used bare strings). This was normalized in this
  freeze.

### Versioning

The package version is bumped to `0.3.0-backend-freeze`. A git
tag `v0.3.0-backend-freeze` is created at the freeze commit.

`PIPELINE_VERSIONS` is unchanged from Phase 12. The schema
version remains `2`; all component versions remain at their
Phase 12 values.

## Architecture guarantee

The backend architecture is **frozen** as of the
v0.3.0-backend-freeze tag. No new AI pipeline stages will be
introduced. The 13 ADRs in `docs/architecture/` are the
authoritative source for architectural decisions.

Future work focuses on:
- Frontend integration
- User experience
- Workflow refinement
- Answer quality improvements based on real user feedback

## Compatibility

- **No breaking changes** to the 12 phases of work.
- **No changes to existing tests.** 504/505 tests pass; the 1
  failure is the pre-existing `test_module_mcq` issue from
  before Phase 1, not introduced by this freeze.
- **No changes to the benchmark framework.** Phase 5's
  framework still produces the same numbers.
- **No changes to cached answers.** The cache format is
  unchanged.

## Benchmark comparison (mock, vs Phase 5 baseline)

| Metric | Phase 5 | Phase 12 (this freeze) | Delta |
|---|---|---|---|
| n_questions | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.169s | -0.004s |
| avg_pdf_generation | 0.005s | 0.005s | 0 |

**No regression.** The freeze is a pure documentation +
normalization + tagging step. The benchmark runs the v0-v12
pipeline and gets the same numbers.

## Out of scope for the freeze

- **Lovable / React frontend.** The freeze prepares the API;
  the actual frontend is a future project.
- **Real LLM benchmark.** Same blocker as Phase 5/6/7/8/9/10/11/12
  (real-LLM API hang); the operator can re-run
  `medrack.benchmarks.run --llm real` in a quiet session.
- **Migration of the existing Gradio dashboard to the
  service layer.** The dashboard remains on the internal API;
  this is a future minor revision.
- **WebSocket / SSE for real-time updates.** Future frontend
  project.
- **Authentication / authorization.** Future frontend project.

## Future direction

The freeze marks the end of the architecture phase. Future
phases focus on:

- **Frontend integration**: build the production frontend
  (Lovable / React), connect to the v1 API.
- **User experience**: refine the workflow based on real user
  feedback.
- **Answer quality**: collect user feedback on answer quality;
  iterate on prompt templates and rule weights (without
  changing the architecture).
- **Bug fixes**: address defects reported by users.
- **Performance**: optimize based on benchmark evidence.

The backend should now be treated as a **stable platform**
rather than an actively evolving architecture. The freeze tag
`v0.3.0-backend-freeze` is the reference point for all future
development.
