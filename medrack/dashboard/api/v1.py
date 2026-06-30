"""HTTP API v1 — JSON API for future frontends (Phase 12).

The v1 API is a thin FastAPI wrapper around the dashboard
services. Each endpoint corresponds to a service method.

API surface (mirrors the services):

- ``GET  /api/v1/library/books`` -> LibraryService.list_books
- ``GET  /api/v1/library/question-banks`` -> LibraryService.list_question_banks
- ``GET  /api/v1/library/ingestion-status/{book_id}`` -> LibraryService.get_ingestion_status
- ``POST /api/v1/library/books`` -> LibraryService.add_book
- ``DELETE /api/v1/library/books/{book_id}`` -> LibraryService.remove_book
- ``POST /api/v1/library/books/{book_id}/reindex`` -> LibraryService.reindex
- ``POST /api/v1/questions/generate`` -> QuestionService.generate
- ``POST /api/v1/questions/batch`` -> QuestionService.generate_batch
- ``POST /api/v1/questions/{qid}/revise`` -> QuestionService.revise
- ``GET  /api/v1/pipeline/inspect`` -> PipelineService.inspect
- ``POST /api/v1/validation/validate`` -> ValidationService.validate
- ``GET  /api/v1/benchmarks/runs`` -> BenchmarkService.list_runs
- ``GET  /api/v1/benchmarks/runs/{run_id}`` -> BenchmarkService.get_run
- ``GET  /api/v1/benchmarks/compare`` -> BenchmarkService.compare
- ``GET  /api/v1/cache/entries`` -> CacheService.list_entries
- ``GET  /api/v1/cache/status`` -> CacheService.get_status
- ``POST /api/v1/cache/reanswer`` -> CacheService.reanswer
- ``GET  /api/v1/version`` -> VersionService.get_info
- ``GET  /api/v1/logs/{name}`` -> LogService.tail

The API is implemented as a FastAPI ``APIRouter``. It can be
mounted into a larger FastAPI app or run standalone.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# Error response shape (consistent across all endpoints)
# ----------------------------------------------------------------------

def error_response(
    status_code: int,
    error_code: str,
    message: str,
) -> JSONResponse:
    """Build a consistent error response.

    All API errors use this shape so frontends can rely on a
    stable contract:

    ``{"error_code": "RUN_NOT_FOUND", "detail": "run not found"}``

    The ``error_code`` is a stable, machine-readable identifier
    (uppercase snake_case). The ``detail`` is a human-readable
    message suitable for display.

    This wraps FastAPI's default HTTPException so the error
    shape is uniform across the API.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "detail": message,
        },
    )


# ----------------------------------------------------------------------
# Pydantic request/response models
# ----------------------------------------------------------------------

class GenerateRequest(BaseModel):
    qid: str
    question_text: str
    subject: str
    marks: int = 10
    question_type: Literal["mcq", "theory"] = "theory"
    book_id: Optional[str] = None
    chapter: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    requests: List[GenerateRequest]


class ReviseRequest(BaseModel):
    subject: str
    revised_question_text: str


class ValidateRequest(BaseModel):
    answer: str
    blueprint: Optional[Dict[str, Any]] = None
    disabled_rules: Optional[List[str]] = None


class InspectRequest(BaseModel):
    qid: str
    question_text: str
    subject: str
    marks: int = 10
    question_type: str = "theory"


class ReanswerRequest(BaseModel):
    qid: str


# ----------------------------------------------------------------------
# Router factory
# ----------------------------------------------------------------------

def make_router() -> APIRouter:
    """Build the v1 API router.

    The router is created fresh on each call so callers can mount
    it into their own FastAPI app.
    """
    from medrack.dashboard.services import (
        LibraryService,
        QuestionService,
        PipelineService,
        ValidationService,
        BenchmarkService,
        CacheService,
        VersionService,
        LogService,
    )

    router = APIRouter(prefix="/api/v1", tags=["medrack"])
    library = LibraryService()
    questions = QuestionService()
    pipeline = PipelineService()
    validation = ValidationService()
    benchmarks = BenchmarkService()
    cache = CacheService()
    version = VersionService()
    logs = LogService()

    # ---- Library ----

    @router.get("/library/books")
    def list_books():
        return [b.to_dict() for b in library.list_books()]

    @router.get("/library/question-banks")
    def list_question_banks():
        return [b.to_dict() for b in library.list_question_banks()]

    @router.get("/library/ingestion-status/{book_id}")
    def ingestion_status(book_id: str):
        return library.get_ingestion_status(book_id).to_dict()

    @router.post("/library/books")
    def add_book(pdf_path: str, subject: str, book_title: Optional[str] = None):
        return library.add_book(pdf_path, subject, book_title)

    @router.delete("/library/books/{book_id}")
    def remove_book(book_id: str):
        return library.remove_book(book_id)

    @router.post("/library/books/{book_id}/reindex")
    def reindex(book_id: str):
        return library.reindex(book_id)

    @router.post("/library/question-banks/upload")
    def upload_question_bank(
        file: UploadFile = File(...),
        name: str = Form(...),
        subject: str = Form(...),
        version: str = Form("v1"),
    ):
        """Upload a question-bank PDF. The backend extracts the questions
        and saves the resulting bank as JSON in
        ``$MEDRACK_HOME/tests/regression_datasets/{name}.json``. The bank
        then appears in ``GET /library/question-banks``.
        """
        return library.upload_question_bank(
            pdf_bytes=file.file.read(),
            filename=file.filename or f"{name}.pdf",
            name=name,
            subject=subject,
            version=version,
        )

    # ---- Questions ----

    @router.post("/questions/generate")
    def generate_answer(req: GenerateRequest):
        from medrack.dashboard.services.questions import GenerationRequest
        result = questions.generate(GenerationRequest(
            qid=req.qid,
            question_text=req.question_text,
            subject=req.subject,
            marks=req.marks,
            question_type=req.question_type,
            book_id=req.book_id,
            chapter=req.chapter,
        ))
        return result.to_dict()

    @router.post("/questions/batch")
    def generate_batch(req: BatchGenerateRequest):
        from medrack.dashboard.services.questions import GenerationRequest
        gen_reqs = [GenerationRequest(
            qid=r.qid, question_text=r.question_text, subject=r.subject,
            marks=r.marks, question_type=r.question_type,
            book_id=r.book_id, chapter=r.chapter,
        ) for r in req.requests]
        return [r.to_dict() for r in questions.generate_batch(gen_reqs)]

    @router.post("/questions/{qid}/revise")
    def revise(qid: str, req: ReviseRequest):
        result = questions.revise(qid, req.subject, req.revised_question_text)
        return result.to_dict()

    @router.get("/questions/stale")
    def re_answer_stale(module_name: Optional[str] = None, dry_run: bool = True):
        return questions.re_answer_stale(module_name, dry_run=dry_run)

    # ---- Pipeline ----

    @router.get("/pipeline/inspect")
    def pipeline_inspect(
        qid: str = Query(...),
        question_text: str = Query(...),
        subject: str = Query(...),
        marks: int = 10,
        question_type: str = "theory",
    ):
        trace = pipeline.inspect(
            qid=qid,
            question_text=question_text,
            subject=subject,
            marks=marks,
            question_type=question_type,
        )
        return trace.to_dict()

    # ---- Validation ----

    @router.post("/validation/validate")
    def validate(req: ValidateRequest):
        from medrack.planner import plan_for_question
        bp = None
        if req.blueprint:
            # Reconstruct the blueprint from a flat dict (duck-typed)
            bp = plan_for_question(
                question_text=req.blueprint.get("question_text", "x"),
                subject=req.blueprint.get("subject", "psm"),
                marks=req.blueprint.get("marks", 10),
                question_type=req.blueprint.get("question_type", "theory"),
            )
        report = validation.validate(req.answer, bp, req.disabled_rules)
        return report.to_dict()

    # ---- Benchmarks ----

    @router.get("/benchmarks/runs")
    def list_benchmark_runs():
        return [r.to_dict() for r in benchmarks.list_runs()]

    @router.get("/benchmarks/runs/{run_id}")
    def get_benchmark_run(run_id: str):
        data = benchmarks.get_run(run_id)
        if data is None:
            return error_response(
                status_code=404,
                error_code="RUN_NOT_FOUND",
                message=f"benchmark run not found: {run_id}",
            )
        return data

    @router.get("/benchmarks/compare")
    def compare_benchmarks(
        run_a: str = Query(...),
        run_b: str = Query(...),
    ):
        return benchmarks.compare(run_a, run_b)

    # ---- Cache ----

    @router.get("/cache/entries")
    def list_cache_entries(
        subject: Optional[str] = None,
        stale_only: bool = False,
    ):
        return [e.to_dict() for e in cache.list_entries(subject, stale_only)]

    @router.get("/cache/entries/{qid}")
    def get_cache_entry(qid: str):
        """Fetch a single cache entry by qid.

        Returns the raw cached dict (answer_text, pdf_path,
        stale flag, etc.) so a frontend can display the
        cached answer without re-generating.

        Errors:
          404 CACHE_ENTRY_NOT_FOUND if no entry exists.
        """
        data = cache.get_entry(qid)
        if data is None:
            return error_response(
                status_code=404,
                error_code="CACHE_ENTRY_NOT_FOUND",
                message=f"cache entry not found: {qid}",
            )
        return data

    @router.get("/cache/status")
    def cache_status():
        return cache.get_status()

    @router.post("/cache/reanswer")
    def cache_reanswer(req: ReanswerRequest):
        return cache.reanswer(req.qid)

    # ---- Version ----

    @router.get("/version")
    def version_info():
        return version.get_info().to_dict()

    # ---- Logs ----

    @router.get("/logs/{name}")
    def tail_log(name: str, n: int = 100):
        if name not in ("ingestion", "generation", "validation", "benchmark"):
            return error_response(
                status_code=400,
                error_code="UNKNOWN_LOG",
                message=(
                    f"unknown log: {name}. "
                    f"Valid: ingestion, generation, validation, benchmark"
                ),
            )
        return logs.tail(name, n)

    @router.get("/logs/{name}/search")
    def search_log(name: str, query: str = Query(...), n: int = 100):
        if name not in ("ingestion", "generation", "validation", "benchmark"):
            return error_response(
                status_code=400,
                error_code="UNKNOWN_LOG",
                message=(
                    f"unknown log: {name}. "
                    f"Valid: ingestion, generation, validation, benchmark"
                ),
            )
        return logs.search(name, query, n)

    return router


def make_app():
    """Build a standalone FastAPI app for the v1 API.

    This is the entry point for ``python -m medrack.dashboard.api.v1``.
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    app = FastAPI(
        title="MedRack Operator API",
        description="Stable JSON API for MedRack's backend services.",
        version="1.0.0",
    )
    # Allow cross-origin requests from the Lovable frontend (port 5173)
    # and any other local/network frontend that may call this API.
    # Without this, every fetch() from the browser is silently blocked.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(make_router())

    @app.get("/")
    def root():
        return {
            "name": "MedRack Operator API",
            "version": "1.0.0",
            "docs": "/docs",
            "api": "/api/v1",
        }

    return app


# Module-level app for `uvicorn medrack.dashboard.api.v1:app`
app = make_app()


__all__ = ["make_router", "make_app", "app"]
