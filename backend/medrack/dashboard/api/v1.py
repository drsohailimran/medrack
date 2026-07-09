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

from fastapi import APIRouter, Body, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from medrack.dashboard.jobs import registry


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
    # Optional explicit answer length in words (overrides the marks default).
    word_count_target: Optional[int] = None


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


class SolveBankRequest(BaseModel):
    name: str
    subject: str = "psm"
    book_id: Optional[str] = None
    marks: int = 10
    # Per-marks answer length (words). Each question uses the target for its
    # own marks; unset -> derived from marks by the prompt builder.
    words_3: Optional[int] = None
    words_5: Optional[int] = None
    words_10: Optional[int] = None
    # Filters. marks_filter: only solve questions with these marks (None = all).
    # chapters: only solve questions in these chapters (None/empty = all).
    marks_filter: Optional[list[int]] = None
    chapters: Optional[list[str]] = None


class RenderPdfRequest(BaseModel):
    qid: str
    subject: str
    question_text: str
    answer_text: str
    marks: int = 10
    question_type: str = "theory"


class GraphvizRequest(BaseModel):
    dot: str


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

    @router.get("/library/question-banks/{name}/questions")
    def get_bank_questions(name: str):
        """Return the full question list for a bank (for the 'view bank'
        UI and the preview flow)."""
        data = library.get_question_bank(name)
        if data is None:
            return error_response(
                status_code=404,
                error_code="BANK_NOT_FOUND",
                message=f"question bank not found: {name}",
            )
        return {
            "name": data.get("name", name),
            "subject": data.get("subject", ""),
            "version": data.get("version", "v1"),
            "questions": data.get("questions", []),
        }

    @router.delete("/library/question-banks/{name}")
    def delete_question_bank(name: str):
        result = library.delete_question_bank(name)
        if not result.get("ok"):
            return error_response(
                status_code=404,
                error_code="BANK_NOT_FOUND",
                message=result.get("error", f"question bank not found: {name}"),
            )
        return result

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

    @router.post("/library/books/upload")
    def upload_book(
        file: UploadFile = File(...),
        subject: str = Form(...),
        title: str = Form(...),
        replace: bool = Form(False),
        hybrid_ocr: bool = Form(False),
        use_marker: bool = Form(False),
    ):
        """Upload a book PDF and ingest it into the knowledge base.

        Runs the full T1-T9 pipeline (extract -> chunk -> embed -> index
        into ChromaDB) on a background thread and returns a ``job_id``.
        Poll ``GET /jobs/{job_id}`` for live progress.

        P1 hybrid_ocr=True: send the PDF to the Windows OCR agent first
        (stop Qwopus → RapidOCR [+ optional Marker] → full text PDF →
        start Qwopus), then ingest the clean PDF on Ubuntu.
        """
        from medrack.config import get_medrack_home
        from medrack.dashboard.services.tasks import (
            run_hybrid_ingest_book,
            run_ingest_book,
        )

        home = get_medrack_home()
        inbox = home / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        dest = inbox / (file.filename or f"{title}.pdf")
        dest.write_bytes(file.file.read())
        if hybrid_ocr:
            job = registry.run(
                "hybrid_ingest_book",
                lambda job, progress: run_hybrid_ingest_book(
                    job,
                    progress,
                    pdf_path=str(dest),
                    subject=subject,
                    title=title,
                    replace=replace,
                    use_marker=use_marker,
                ),
            )
            return {
                "job_id": job.id,
                "kind": "hybrid_ingest_book",
                "book_title": title,
                "hybrid_ocr": True,
            }
        job = registry.run(
            "ingest_book",
            lambda job, progress: run_ingest_book(
                job, progress, pdf_path=str(dest), subject=subject, title=title, replace=replace
            ),
        )
        return {"job_id": job.id, "kind": "ingest_book", "book_title": title}

    @router.post("/library/question-banks/upload")
    def upload_question_bank(
        file: UploadFile = File(...),
        name: str = Form(...),
        subject: str = Form(...),
        version: str = Form("v1"),
    ):
        """Upload a question-bank PDF. Extraction runs on a background
        thread (it can OCR/parse many pages); returns a ``job_id``. Poll
        ``GET /jobs/{job_id}`` for progress; on completion the result holds
        the saved bank. The bank then appears in
        ``GET /library/question-banks``.
        """
        from medrack.dashboard.services.tasks import run_extract_bank

        data = file.file.read()
        filename = file.filename or f"{name}.pdf"
        job = registry.run(
            "extract_bank",
            lambda job, progress: run_extract_bank(
                job, progress, pdf_bytes=data, filename=filename, name=name, subject=subject, version=version
            ),
        )
        return {"job_id": job.id, "kind": "extract_bank"}

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
            word_count_target=req.word_count_target,
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

    @router.post("/questions/render-pdf")
    def render_answer_pdf(req: RenderPdfRequest):
        """Render a SINGLE answer to a real PDF and return it for download.

        Used by the "download this sample answer" button. Synchronous —
        one answer renders in well under a second.
        """
        from pathlib import Path
        from medrack.config import get_medrack_home
        from medrack.answer.render import render_preview_pdf

        out_dir = get_medrack_home() / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_qid = "".join(c for c in req.qid if c.isalnum() or c in ("-", "_")) or "sample"
        out_path = out_dir / f"preview_{safe_qid}.pdf"
        render_preview_pdf(
            out_path,
            module_name=f"{req.subject}-sample",
            module_subject=req.subject,
            question={
                "qid": req.qid,
                "type": req.question_type,
                "question_text": req.question_text,
                "options": {},
            },
            answer={"answer_text": req.answer_text, "retrieval_chunks": []},
            question_index=1,
            total_questions=1,
            marks=req.marks,
        )
        return FileResponse(
            str(out_path), media_type="application/pdf", filename=f"medrack-{safe_qid}.pdf"
        )

    @router.post("/render/graphviz")
    def render_graphviz(req: GraphvizRequest):
        """Render Graphviz DOT source to a PNG (used by the on-screen preview
        to show flowchart diagrams). 422 if the DOT is invalid."""
        from fastapi.responses import Response
        from medrack.answer.render import render_dot_to_png

        png = render_dot_to_png(req.dot)
        if not png:
            return error_response(
                status_code=422,
                error_code="DOT_RENDER_FAILED",
                message="could not render the diagram",
            )
        return Response(content=png, media_type="image/png")

    # ---- Banks (solve whole bank -> one PDF) ----

    @router.post("/banks/solve")
    def solve_bank(req: SolveBankRequest):
        """Solve every question in a bank and render one combined PDF.

        Runs on a background thread; returns a ``job_id``. Poll
        ``GET /jobs/{job_id}``; when done, download the solved PDF from
        ``GET /jobs/{job_id}/pdf``.
        """
        from medrack.dashboard.services.tasks import run_solve_bank

        job = registry.run(
            "solve_bank",
            lambda job, progress: run_solve_bank(
                job, progress, bank_name=req.name, subject=req.subject, book_id=req.book_id,
                marks=req.marks, words_3=req.words_3, words_5=req.words_5, words_10=req.words_10,
                marks_filter=req.marks_filter, chapters=req.chapters,
            ),
        )
        return {"job_id": job.id, "kind": "solve_bank"}

    # ---- Jobs (async progress) ----

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str):
        job = registry.get(job_id)
        if job is None:
            return error_response(404, "JOB_NOT_FOUND", f"job not found: {job_id}")
        return job.to_dict()

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        """Request cooperative cancel of a running job (P3).

        The current question finishes; remaining questions are skipped.
        For solve_bank, partial answers stay on disk for keep/delete review.
        """
        job = registry.request_cancel(job_id)
        if job is None:
            return error_response(404, "JOB_NOT_FOUND", f"job not found: {job_id}")
        return {
            "ok": True,
            "job_id": job.id,
            "status": job.status,
            "cancel_requested": job.cancel_requested,
            "message": (
                "Cancel requested — will stop after the current question."
                if job.status == "running"
                else f"Job already {job.status}."
            ),
        }

    @router.get("/jobs/{job_id}/pdf")
    def get_job_pdf(job_id: str):
        job = registry.get(job_id)
        if job is None:
            return error_response(404, "JOB_NOT_FOUND", f"job not found: {job_id}")
        result = job.result or {}
        pdf_path = result.get("pdf_path")
        # Partial PDF after cancel is also downloadable.
        if job.status not in ("done", "cancelled") or not pdf_path or not os.path.exists(pdf_path):
            return error_response(409, "PDF_NOT_READY", "the PDF for this job is not ready")
        return FileResponse(
            pdf_path, media_type="application/pdf", filename=result.get("download_name", "medrack.pdf")
        )

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
        # Return the flat BenchmarkSummary shape (matching the frontend
        # contract and GET /benchmarks/runs), not the raw nested run file.
        data = benchmarks.get_run_summary(run_id)
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

    @router.delete("/cache/entries/{qid}")
    def delete_cache_entry(qid: str, module: Optional[str] = None):
        """Delete a single cached answer by qid, scoped to ``module`` (bank)
        so same-named qids in other banks aren't affected."""
        return cache.delete_entry(qid, module)

    @router.delete("/cache/module/{module}")
    def delete_cache_module(module: str):
        """Delete every cached answer for one module / question bank."""
        return cache.delete_module(module)

    # ---- Version ----

    @router.get("/version")
    def version_info():
        return version.get_info().to_dict()

    # ---- LLM live status (P3 indicator) ----

    @router.get("/llm/status")
    def llm_status():
        """Live LLM indicator: provider, model, endpoint, reachability."""
        import os
        from medrack import config as cfg

        mode = os.environ.get("MEDRACK_LLM_MODE", "real").lower()
        provider = getattr(cfg, "LLM_PROVIDER", "unknown")
        model = getattr(cfg, "LLM_DEFAULT_MODEL", "unknown")
        base_url = getattr(cfg, "LLM_BASE_URL", "")
        online = False
        detail = ""
        latency_ms: Optional[float] = None

        if mode == "mock":
            online = True
            detail = "mock client (no network)"
        else:
            # Probe endpoint: llama.cpp /health, OpenAI-compat /v1/models, else base URL.
            probes = []
            if base_url:
                probes = [
                    f"{base_url.rstrip('/')}/health",
                    f"{base_url.rstrip('/')}/v1/models",
                    base_url.rstrip("/"),
                ]
            try:
                import httpx
                import time as _time

                t0 = _time.perf_counter()
                with httpx.Client(timeout=2.5) as client:
                    last_err = "unreachable"
                    for url in probes:
                        try:
                            r = client.get(url)
                            # Any HTTP response means the server is up.
                            if r.status_code < 500:
                                online = True
                                detail = f"HTTP {r.status_code} from {url}"
                                break
                            last_err = f"HTTP {r.status_code} from {url}"
                        except Exception as exc:  # noqa: BLE001
                            last_err = str(exc)
                    if not online:
                        detail = last_err
                latency_ms = round((_time.perf_counter() - t0) * 1000.0, 1)
            except Exception as exc:  # noqa: BLE001
                detail = str(exc)

        return {
            "schema_version": 1,
            "mode": mode,
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "online": online,
            "detail": detail,
            "latency_ms": latency_ms,
        }

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

    # ---- P1 OCR agent bridge (Windows pull worker) ----

    def _ocr_auth(x_ocr_token: Optional[str] = Header(default=None, alias="X-OCR-Token")):
        from medrack.dashboard.services import ocr_bridge

        if not ocr_bridge.check_token(x_ocr_token):
            return error_response(
                status_code=401,
                error_code="OCR_UNAUTHORIZED",
                message="invalid or missing X-OCR-Token",
            )
        return None

    @router.get("/ocr/agent/claim")
    def ocr_agent_claim(x_ocr_token: Optional[str] = Header(default=None, alias="X-OCR-Token")):
        """Windows agent claims the next queued hybrid-OCR job (or null)."""
        from medrack.dashboard.services import ocr_bridge

        if not ocr_bridge.check_token(x_ocr_token):
            return error_response(401, "OCR_UNAUTHORIZED", "invalid or missing X-OCR-Token")
        claimed = ocr_bridge.claim_next()
        return {"job": claimed}

    @router.get("/ocr/agent/jobs/{job_id}/source")
    def ocr_agent_source(
        job_id: str,
        x_ocr_token: Optional[str] = Header(default=None, alias="X-OCR-Token"),
    ):
        from medrack.dashboard.services import ocr_bridge

        if not ocr_bridge.check_token(x_ocr_token):
            return error_response(401, "OCR_UNAUTHORIZED", "invalid or missing X-OCR-Token")
        path = ocr_bridge.source_path(job_id)
        if path is None:
            return error_response(404, "OCR_JOB_NOT_FOUND", f"no source for {job_id}")
        return FileResponse(str(path), media_type="application/pdf", filename="source.pdf")

    @router.post("/ocr/agent/jobs/{job_id}/progress")
    def ocr_agent_progress(
        job_id: str,
        body: dict,
        x_ocr_token: Optional[str] = Header(default=None, alias="X-OCR-Token"),
    ):
        from medrack.dashboard.services import ocr_bridge

        if not ocr_bridge.check_token(x_ocr_token):
            return error_response(401, "OCR_UNAUTHORIZED", "invalid or missing X-OCR-Token")
        try:
            ocr_bridge.update_progress(
                job_id,
                percent=float(body.get("percent") or 0),
                message=str(body.get("message") or ""),
                status=str(body.get("status") or "running"),
            )
        except FileNotFoundError:
            return error_response(404, "OCR_JOB_NOT_FOUND", job_id)
        return {"ok": True}

    @router.post("/ocr/agent/jobs/{job_id}/result")
    async def ocr_agent_result(
        job_id: str,
        file: UploadFile = File(...),
        x_ocr_token: Optional[str] = Header(default=None, alias="X-OCR-Token"),
    ):
        from medrack.dashboard.services import ocr_bridge

        if not ocr_bridge.check_token(x_ocr_token):
            return error_response(401, "OCR_UNAUTHORIZED", "invalid or missing X-OCR-Token")
        dest = ocr_bridge.ocr_jobs_root() / job_id / "clean_upload.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(await file.read())
        try:
            ocr_bridge.mark_done(job_id, dest)
        except Exception as exc:  # noqa: BLE001
            ocr_bridge.mark_error(job_id, str(exc))
            return error_response(500, "OCR_RESULT_FAILED", str(exc))
        return {"ok": True}

    @router.post("/ocr/agent/jobs/{job_id}/error")
    def ocr_agent_error(
        job_id: str,
        body: dict,
        x_ocr_token: Optional[str] = Header(default=None, alias="X-OCR-Token"),
    ):
        from medrack.dashboard.services import ocr_bridge

        if not ocr_bridge.check_token(x_ocr_token):
            return error_response(401, "OCR_UNAUTHORIZED", "invalid or missing X-OCR-Token")
        ocr_bridge.mark_error(job_id, str(body.get("error") or "unknown"))
        return {"ok": True}

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
