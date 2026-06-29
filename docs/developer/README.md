# MedRack Developer Documentation

This directory contains developer documentation for the MedRack
backend. It is intended for engineers building frontends, custom
integrations, or extensions on top of MedRack.

## Audience

- Frontend developers (Lovable, React, mobile, CLI)
- Engineers integrating MedRack into a larger system
- Engineers extending the backend with new services or rules

## What you should read first

1. **[architecture.md](architecture.md)** — the MedRack pipeline
   architecture (Planner → Blueprint → Retrieval → Reranker →
   Writer → Validator) and the module layout.
2. **[api.md](api.md)** — the v1 HTTP API (21 endpoints, error
   shape, request/response models).
3. **[services.md](services.md)** — the 8 service classes that
   expose backend operations as a stable Python interface.
4. **[pipeline.md](pipeline.md)** — how a question flows through
   the pipeline, with examples.
5. **[cache.md](cache.md)** — the answer cache and versioning
   system.
6. **[benchmarks.md](benchmarks.md)** — the benchmark framework
   and how to interpret results.

## Backend freeze status

As of the Backend Freeze v1.0 (this document), the backend
architecture is **frozen**. No new AI pipeline stages will be
introduced. The 12 ADRs in `docs/architecture/` are the
authoritative source for architectural decisions.

Future work should focus on:
- Frontend integration
- Answer quality improvements based on real user feedback
- Bug fixes
- Performance improvements
- Compatibility improvements

## Versioning

- **Package version**: see `medrack/__init__.py` (`__version__`).
- **Pipeline versions**: see `medrack/config.py` (`PIPELINE_VERSIONS`).
- **Benchmark baseline**: tagged at `phase-5-baseline`.

The HTTP API has a `schema_version` field in every response to
support forward-compatible evolution.

## Stability contract

Public APIs (service method signatures, HTTP endpoints, response
shapes) are **frozen**. Breaking changes require:
1. A new ADR explaining the breaking change
2. A new schema_version (e.g. v2)
3. Backward compatibility for at least one release

See `docs/architecture/0001-layered-module-architecture.md` and
`docs/architecture/0012-operator-console-and-api-integration.md`
for the full stability contract.

## Quick start

```python
# In-process Python (notebook, custom script, CLI)
from medrack.dashboard.services import (
    LibraryService, QuestionService, ValidationService,
    PipelineService, BenchmarkService, CacheService,
    VersionService, LogService,
)
from medrack.answer.generate import generate_answer

# List books
books = LibraryService().list_books()

# Inspect a pipeline
trace = PipelineService().inspect(
    qid="q001",
    question_text="Discuss the management of diabetes.",
    subject="psm",
    marks=10,
)
print(trace.to_dict())
```

```bash
# HTTP API (any frontend)
curl http://localhost:8000/api/v1/version
curl http://localhost:8000/api/v1/pipeline/inspect?qid=q001&question_text=...&subject=psm
curl -X POST http://localhost:8000/api/v1/validation/validate \
  -H "Content-Type: application/json" \
  -d '{"answer": "Management: ..."}'
```

## Running the API server

```bash
# Install dependencies (fastapi, pydantic, uvicorn)
pip install fastapi pydantic uvicorn

# Run the API server
uvicorn medrack.dashboard.api.v1:app --host 0.0.0.0 --port 8000
```

The interactive API docs are at `http://localhost:8000/docs`.

## License

Personal Edition. Single operator. No SaaS.
