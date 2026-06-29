# MedRack Frontend Handoff Package

**Backend version**: v0.3.0-backend-freeze
**Handoff version**: v1.0
**Date**: 2026-06-29
**For**: Lovable frontend team (zero backend access)

---

## What is MedRack?

MedRack is a local medical AI system that generates
publication-quality MBBS (Indian medical school) theory-exam
answers from trusted medical textbooks. It runs on a single
machine, owned by a single operator (the user — an MBBS
student preparing for NEET PG exams).

The user provides a question (e.g. "Discuss the management of
diabetes mellitus"). MedRack returns a structured answer with
section headings (Definition, Epidemiology, Etiology,
Clinical Features, Management, etc.), evidence references, and
a downloadable PDF.

## Project goals

1. **Quality** — answers must be at the level a student could
   submit in a university exam.
2. **Trust** — every claim is grounded in a specific textbook
   chunk the user can verify.
3. **Local-first** — no data leaves the machine. No SaaS. No
   cloud dependency.
4. **Operator-driven** — one user, one machine, one source of
   truth (the textbook library).

## High-level architecture (what the frontend sees)

```
Frontend (this app)
      │
      ↓ HTTPS / JSON
      │
Backend (frozen, do not modify)
  ┌──────────────────────────────────────┐
  │ Ingestion                            │
  │ ↓                                    │
  │ Metadata extraction                  │
  │ ↓                                    │
  │ Adaptive Retrieval (vector search)   │
  │ ↓                                    │
  │ Planner (blueprint the answer)       │
  │ ↓                                    │
  │ Blueprint (retrieval spec)           │
  │ ↓                                    │
  │ Reranker (re-order evidence)         │
  │ ↓                                    │
  │ Writer (LLM synthesises prose)       │
  │ ↓                                    │
  │ Validator (9 quality rules)          │
  │ ↓                                    │
  │ Versioned Cache                      │
  │ ↓                                    │
  │ PDF Export                           │
  └──────────────────────────────────────┘
```

The frontend is **not** part of this pipeline. The frontend is
the user's window into the backend. The backend produces
canonical answers and stores them; the frontend lets the user
see, manage, and trigger them.

## Typical user workflow

1. **Import a textbook** (PDF). Wait for ingestion to complete.
2. **Ask a question**. Wait for generation to complete.
3. **Review the answer** (with the validation report).
4. **Download the PDF** or revise the answer.
5. **Browse the cache** of past answers. Re-generate stale
   ones.
6. **Run benchmarks** to compare pipeline configurations.
7. **Inspect the pipeline** (Planner, Blueprint, Retrieval,
   Reranker, Validator) for any question.

## Backend capabilities (what the backend can do)

The backend exposes **22 HTTP API endpoints** under
`/api/v1/*` and **8 stable Python service classes**. The
frontend should consume the HTTP API; the Python services are
for in-process consumers (notebooks, scripts).

The API supports:

- **Library management** — list, add, remove, re-index
  textbooks; list question banks; check ingestion status.
- **Question generation** — single answer, batch, revise,
  re-answer stale.
- **Pipeline inspection** — see the Planner, Blueprint,
  Retrieval, Reranker, Writer, Validator stages for any
  question.
- **Validation** — run the 9 validation rules against an
  answer.
- **Benchmark** — list runs, get a run, compare two runs.
- **Cache** — list entries, get a single entry, get status,
  mark as stale.
- **Version** — get package, pipeline, and baseline version.
- **Logs** — tail or search the ingestion, generation,
  validation, benchmark logs.

## Frontend responsibilities

The frontend is responsible for:

1. **UI** — every screen, button, dialog, table, chart.
2. **State** — what data the user sees right now.
3. **API calls** — calling `/api/v1/*` at the right time.
4. **Error handling** — showing errors in a human-readable
   way.
5. **Loading states** — showing progress while the backend
   works.
6. **Polling** — for long-running operations (ingestion,
   generation, benchmarks).
7. **Polling intervals** — see `WORKFLOW.md` for the
   recommended intervals.
8. **Retry logic** — see `FRONTEND_INTEGRATION.md` for the
   policy.
9. **PDF download** — opening the cached PDF in a new tab.
10. **Caching** — caching API responses client-side (React
    Query) to avoid round-trips.

The frontend is **not** responsible for:

1. **Backend logic** — never call the Python service classes
   directly; use the HTTP API.
2. **LLM calls** — the backend does this.
3. **Validation rules** — the backend does this; the frontend
   displays the results.
4. **Cache management** — the backend does this; the
   frontend can mark entries as stale.
5. **Benchmark execution** — the backend does this; the
   frontend displays results.

## Quick start (for the Lovable team)

1. Read `ARCHITECTURE.md` (10 minutes).
2. Skim `API_REFERENCE.md` (15 minutes).
3. Read `WORKFLOW.md` (15 minutes).
4. Read `DATA_MODELS.md` (15 minutes).
5. Read `FRONTEND_INTEGRATION.md` (10 minutes).
6. Read `COMPONENT_GUIDE.md` (15 minutes).
7. Read `STATE_MANAGEMENT.md` (10 minutes).
8. Read `DESIGN_SYSTEM.md` (10 minutes).
9. Use `MOCK_DATA.json` to prototype the UI without the
   backend.
10. Use `POSTMAN_COLLECTION.json` to explore the API.
11. Use `openapi.yaml` to generate a typed client.

**Total reading time**: ~2 hours.

## File index

| File | Purpose |
|------|---------|
| `README.md` (this file) | High-level orientation |
| `ARCHITECTURE.md` | The complete backend pipeline (no impl details) |
| `API_REFERENCE.md` | Every API endpoint, request/response, status codes |
| `openapi.yaml` | OpenAPI 3.0 spec for client generation |
| `POSTMAN_COLLECTION.json` | Postman collection for testing |
| `.env.example` | Required environment variables |
| `DATA_MODELS.md` | Every data model exchanged with the backend |
| `WORKFLOW.md` | Every user workflow |
| `STATE_MANAGEMENT.md` | React Query / TanStack Query recommendations |
| `COMPONENT_GUIDE.md` | Every frontend screen |
| `DESIGN_SYSTEM.md` | UX guidance (no code) |
| `MOCK_DATA.json` | Realistic mock responses for prototyping |
| `FRONTEND_INTEGRATION.md` | API integration reference |

## What the backend is **not**

The backend is **not**:

- A multi-tenant SaaS. It serves one operator.
- A real-time system. It uses HTTP request/response, not
  WebSocket or SSE.
- Authenticated. v1 is open. Add network-level access
  control if needed.
- Versioned beyond `schema_version: 1`. Future versions will
  be added in parallel.
- Designed for mobile. The API is HTTP+JSON; a mobile client
  can consume it but the dashboard is desktop-first.

## What to do if the API doesn't do what you need

If a frontend requirement cannot be satisfied by the current
API:

1. **Document the gap** in your integration report. Be
   specific: which endpoint, which field, what's missing.
2. **Do not invent backend logic** to work around the gap.
3. **The backend team will add a backward-compatible
   endpoint** if the gap is real.

The backend is frozen. The API is the contract. If the
contract is wrong, the contract is updated — not the
backend.

## Contact

For questions, refer to `docs/architecture/0001-0013` in the
backend repository. These ADRs are the authoritative source
for architectural decisions.
