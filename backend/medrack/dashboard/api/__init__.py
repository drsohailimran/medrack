"""medrack.dashboard.api — JSON API for future frontends (Phase 12).

The :mod:`medrack.dashboard.api` module provides a thin HTTP wrapper
around the :mod:`medrack.dashboard.services` package. The JSON API
is designed for **future frontend integration** (Lovable, custom
React app, CLI client, etc.).

API surface
-----------
- ``GET  /api/v1/library/books`` — list all books.
- ``POST /api/v1/library/books`` — add a book (multipart upload).
- ``GET  /api/v1/library/question-banks`` — list question banks.
- ``GET  /api/v1/library/ingestion-status/<book_id>`` — ingestion status.
- ``POST /api/v1/questions/generate`` — generate a single answer.
- ``POST /api/v1/questions/batch`` — generate a batch.
- ``GET  /api/v1/pipeline/inspect?qid=...&question=...&...`` — pipeline trace.
- ``POST /api/v1/validation/validate`` — validate an answer.
- ``GET  /api/v1/benchmarks/runs`` — list benchmark runs.
- ``GET  /api/v1/benchmarks/runs/<run_id>`` — get a run report.
- ``GET  /api/v1/benchmarks/compare?run_a=...&run_b=...`` — compare two runs.
- ``GET  /api/v1/cache/entries`` — list cache entries.
- ``GET  /api/v1/cache/status`` — cache status summary.
- ``POST /api/v1/cache/reanswer`` — re-answer a cached entry.
- ``GET  /api/v1/version`` — version information.
- ``GET  /api/v1/logs/<name>?n=100`` — tail a log.

The API is implemented as a thin FastAPI app. It can be run
standalone (``python -m medrack.dashboard.api.v1``) or mounted
into an existing FastAPI/Gradio/Flask app.

Future Lovable integration
--------------------------
A future React frontend (built with Lovable or otherwise) consumes
this JSON API. The service layer is the contract; the API is one
of multiple transports (HTTP, in-process Python, gRPC, etc.).
"""
