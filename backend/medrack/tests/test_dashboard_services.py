"""Tests for Phase 12: Operator Console & API Integration.

Coverage:
  - services: each of the 8 v1 services
  - api: v1 FastAPI routes (TestClient)
  - isolation: services do not duplicate backend logic
  - public interface stability
  - JSON serialization
"""
from __future__ import annotations

import os
import tempfile

import pytest


# ----------------------------------------------------------------------
# Service: LibraryService
# ----------------------------------------------------------------------

def test_library_service_importable():
    from medrack.dashboard.services import LibraryService, BookInfo
    svc = LibraryService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "list_books")
    assert hasattr(svc, "list_question_banks")
    assert hasattr(svc, "get_ingestion_status")
    assert hasattr(svc, "add_book")
    assert hasattr(svc, "remove_book")
    assert hasattr(svc, "reindex")


def test_library_service_list_books_empty():
    from medrack.dashboard.services import LibraryService
    svc = LibraryService()
    books = svc.list_books()
    assert isinstance(books, list)


def test_library_service_list_question_banks_returns_list():
    from medrack.dashboard.services import LibraryService
    svc = LibraryService()
    banks = svc.list_question_banks()
    assert isinstance(banks, list)


def test_library_service_get_ingestion_status_unknown():
    from medrack.dashboard.services import LibraryService
    svc = LibraryService()
    status = svc.get_ingestion_status("nonexistent-book-id")
    assert status.status == "unknown"


def test_book_info_to_dict_has_schema_version():
    from medrack.dashboard.services import BookInfo
    b = BookInfo(
        book_id="x", title="X", subject="psm", path="/x.pdf",
        indexed=False, indexed_at=None, chunk_count=0,
    )
    d = b.to_dict()
    assert d["schema_version"] == 1
    assert d["book_id"] == "x"


# ----------------------------------------------------------------------
# Service: QuestionService
# ----------------------------------------------------------------------

def test_question_service_importable():
    from medrack.dashboard.services import QuestionService, GenerationRequest
    svc = QuestionService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "generate")
    assert hasattr(svc, "generate_batch")
    assert hasattr(svc, "revise")
    assert hasattr(svc, "re_answer_stale")


def test_generation_request_to_dict():
    from medrack.dashboard.services.questions import GenerationResult
    r = GenerationResult(
        qid="q001", ok=True, answer_text="x", pdf_path="/x.pdf",
        cache_hit=False, token_count=100, latency_seconds=0.5,
    )
    d = r.to_dict()
    assert d["schema_version"] == 1
    assert d["qid"] == "q001"
    assert d["ok"] is True


def test_question_service_re_answer_stale_dry_run():
    from medrack.dashboard.services import QuestionService
    svc = QuestionService()
    result = svc.re_answer_stale(module_name=None, dry_run=True)
    assert "ok" in result
    assert "dry_run" in result
    assert result["dry_run"] is True


def test_question_service_generate_propagates_question_type():
    """Runtime regression: the question dict passed to
    ``generate_answer`` must include ``type`` (``"mcq"`` or
    ``"theory"``), or the pipeline raises ValueError. The
    service must forward ``request.question_type`` into that
    field, regardless of the caller (API or batch).
    """
    from medrack.dashboard.services import QuestionService, GenerationRequest
    from unittest.mock import patch

    svc = QuestionService()
    req = GenerationRequest(
        qid="rt_q001",
        question_text="Discuss the management of diabetes mellitus.",
        subject="psm",
        marks=5,
        question_type="theory",
    )
    captured: dict = {}

    def fake_generate_answer(*, module_name, subject, chapter, question, llm_client,
                            force_regenerate=False, marks=None, word_count_target=None):
        captured["question"] = dict(question)
        captured["module_name"] = module_name
        captured["subject"] = subject
        captured["chapter"] = chapter
        captured["marks"] = marks
        return {
            "ok": True,
            "answer_text": "MOCK",
            "pdf_path": "/tmp/mock.pdf",
            "tokens": 0,
        }

    with patch("medrack.answer.generate.generate_answer", side_effect=fake_generate_answer):
        result = svc.generate(req)

    assert result.ok is True
    assert captured["question"]["type"] == "theory", (
        f"Runtime bug: question_type was not propagated. "
        f"Got question={captured['question']!r}"
    )
    assert captured["question"]["qid"] == "rt_q001"
    assert captured["question"]["question_text"].startswith("Discuss")
    # Backward-compat: defaults still work.
    assert captured["module_name"] == "psm-default"
    assert captured["subject"] == "psm"


def test_question_service_generate_default_question_type_is_theory():
    """When the caller does not set ``question_type`` (e.g. an
    older API client that omits it), the service must default
    to ``"theory"`` so the pipeline does not raise.
    """
    from medrack.dashboard.services import QuestionService, GenerationRequest
    from unittest.mock import patch

    svc = QuestionService()
    # Build a request the old way: question_type is the
    # dataclass default ("theory"). We don't override it.
    req = GenerationRequest(
        qid="rt_q002",
        question_text="Old-style call without question_type.",
        subject="fmt",
        marks=10,
    )
    assert req.question_type == "theory"  # dataclass default

    captured: dict = {}

    def fake_generate_answer(*, module_name, subject, chapter, question, llm_client,
                            force_regenerate=False, marks=None, word_count_target=None):
        captured["type"] = question.get("type")
        return {"ok": True, "answer_text": "OK", "pdf_path": None, "tokens": 0}

    with patch("medrack.answer.generate.generate_answer", side_effect=fake_generate_answer):
        svc.generate(req)

    assert captured["type"] == "theory"


# ----------------------------------------------------------------------
# Service: PipelineService
# ----------------------------------------------------------------------

def test_pipeline_service_importable():
    from medrack.dashboard.services import PipelineService, PipelineTrace
    svc = PipelineService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "inspect_planner")
    assert hasattr(svc, "inspect_blueprint")
    assert hasattr(svc, "inspect")


def test_pipeline_service_inspect_returns_six_stages():
    from medrack.dashboard.services import PipelineService
    svc = PipelineService()
    trace = svc.inspect(
        qid="q001",
        question_text="Discuss the management of diabetes.",
        subject="psm",
        marks=10,
    )
    assert len(trace.stages) == 6
    stage_names = [s.stage for s in trace.stages]
    assert stage_names == [
        "planner", "blueprint", "retrieval",
        "reranker", "writer", "validator",
    ]


def test_pipeline_trace_to_dict_has_schema_version():
    from medrack.dashboard.services import PipelineService
    svc = PipelineService()
    trace = svc.inspect(qid="q001", question_text="x", subject="psm")
    d = trace.to_dict()
    assert d["schema_version"] == 1
    assert d["qid"] == "q001"
    assert len(d["stages"]) == 6


# ----------------------------------------------------------------------
# Service: ValidationService
# ----------------------------------------------------------------------

def test_validation_service_importable():
    from medrack.dashboard.services import ValidationService
    svc = ValidationService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "validate")
    assert hasattr(svc, "summarize")


def test_validation_service_validate_clean_answer():
    from medrack.dashboard.services import ValidationService
    svc = ValidationService()
    report = svc.validate("Management: real content here\nEpidemiology: more content")
    assert report.pass_ is True
    assert report.score >= 0.0


def test_validation_service_summarize():
    from medrack.dashboard.services import ValidationService
    svc = ValidationService()
    report = svc.validate("x")
    summary = svc.summarize(report)
    assert "pass" in summary
    assert "score" in summary
    assert "failed_rules" in summary
    assert "warnings" in summary


# ----------------------------------------------------------------------
# Service: BenchmarkService
# ----------------------------------------------------------------------

def test_benchmark_service_importable():
    from medrack.dashboard.services import BenchmarkService, BenchmarkSummary
    svc = BenchmarkService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "list_runs")
    assert hasattr(svc, "get_run")
    assert hasattr(svc, "compare")


def test_benchmark_service_list_runs_returns_list():
    from medrack.dashboard.services import BenchmarkService
    svc = BenchmarkService()
    runs = svc.list_runs()
    assert isinstance(runs, list)


def test_benchmark_service_compare_handles_missing_runs():
    from medrack.dashboard.services import BenchmarkService
    svc = BenchmarkService()
    result = svc.compare("nonexistent_a", "nonexistent_b")
    assert result["ok"] is False


# ----------------------------------------------------------------------
# Service: CacheService
# ----------------------------------------------------------------------

def test_cache_service_importable():
    from medrack.dashboard.services import CacheService, CacheEntry
    svc = CacheService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "list_entries")
    assert hasattr(svc, "get_status")
    assert hasattr(svc, "reanswer")


def test_cache_service_get_status():
    from medrack.dashboard.services import CacheService
    svc = CacheService()
    status = svc.get_status()
    assert "total_entries" in status
    assert "by_subject" in status
    assert "stale_by_subject" in status
    assert "schema_version" in status


def test_cache_entry_to_dict_has_schema_version():
    from medrack.dashboard.services import CacheEntry
    e = CacheEntry(qid="q001", subject="psm", is_stale=False)
    d = e.to_dict()
    assert d["schema_version"] == 1
    assert d["qid"] == "q001"
    assert "versions" in d


# ----------------------------------------------------------------------
# Service: VersionService
# ----------------------------------------------------------------------

def test_version_service_importable():
    from medrack.dashboard.services import VersionService, VersionInfo
    svc = VersionService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "get_info")


def test_version_service_get_info():
    from medrack.dashboard.services import VersionService
    svc = VersionService()
    info = svc.get_info()
    assert info.package_version is not None
    assert "schema" in info.pipeline_versions
    assert "prompt" in info.pipeline_versions
    assert info.benchmark_baseline_tag == "phase-5-baseline"


def test_version_info_to_dict_has_schema_version():
    from medrack.dashboard.services import VersionService
    svc = VersionService()
    info = svc.get_info()
    d = info.to_dict()
    assert d["schema_version"] == 1


# ----------------------------------------------------------------------
# Service: LogService
# ----------------------------------------------------------------------

def test_log_service_importable():
    from medrack.dashboard.services import LogService
    svc = LogService()
    assert svc.SCHEMA_VERSION == 1
    assert hasattr(svc, "tail")
    assert hasattr(svc, "search")


def test_log_service_tail_empty():
    from medrack.dashboard.services import LogService
    svc = LogService()
    entries = svc.tail("ingestion", n=10)
    assert isinstance(entries, list)


def test_log_service_tail_nonexistent_log():
    from medrack.dashboard.services import LogService
    svc = LogService()
    entries = svc.tail("ingestion", n=10)
    assert entries == []


# ----------------------------------------------------------------------
# API: v1 FastAPI
# ----------------------------------------------------------------------

def test_api_v1_importable():
    from medrack.dashboard.api.v1 import make_app, make_router, app
    assert app is not None
    assert make_app() is not None
    assert make_router() is not None


def test_api_v1_routes_registered():
    from medrack.dashboard.api.v1 import make_app
    app = make_app()
    # Use the generated OpenAPI schema as the source of truth for which
    # paths are actually served. Newer FastAPI versions include sub-routers
    # lazily, so iterating ``app.routes`` for ``.path`` no longer surfaces
    # included-router paths — but the OpenAPI schema always reflects what
    # is reachable over HTTP.
    routes = list(app.openapi()["paths"].keys())
    expected = [
        "/api/v1/library/books",
        "/api/v1/library/question-banks",
        "/api/v1/library/ingestion-status/{book_id}",
        "/api/v1/questions/generate",
        "/api/v1/questions/batch",
        "/api/v1/pipeline/inspect",
        "/api/v1/validation/validate",
        "/api/v1/benchmarks/runs",
        "/api/v1/cache/entries",
        "/api/v1/cache/status",
        "/api/v1/version",
        "/api/v1/logs/{name}",
    ]
    for r in expected:
        assert r in routes, f"missing route: {r}"


def test_api_v1_root():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "MedRack Operator API"
    assert data["version"] == "1.0.0"


def test_api_v1_version_endpoint():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == 1
    assert "package_version" in data
    assert "pipeline_versions" in data


def test_api_v1_library_books_endpoint():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.get("/api/v1/library/books")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_v1_validation_endpoint():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.post(
        "/api/v1/validation/validate",
        json={"answer": "Management: real content here"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pass" in data
    assert "score" in data


def test_api_v1_pipeline_inspect_endpoint():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/pipeline/inspect",
        params={
            "qid": "q001",
            "question_text": "Discuss the management of diabetes.",
            "subject": "psm",
            "marks": 10,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == 1
    assert len(data["stages"]) == 6


def test_api_v1_logs_invalid_name():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.get("/api/v1/logs/badname")
    assert resp.status_code == 400


def test_api_v1_logs_valid_name():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.get("/api/v1/logs/ingestion")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_v1_cache_status_endpoint():
    from medrack.dashboard.api.v1 import make_app
    from fastapi.testclient import TestClient
    app = make_app()
    client = TestClient(app)
    resp = client.get("/api/v1/cache/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_entries" in data
    assert "schema_version" in data


# ----------------------------------------------------------------------
# Public API stability
# ----------------------------------------------------------------------

def test_all_services_in_dunder_all():
    import medrack.dashboard.services as svcs
    expected = [
        "LibraryService", "BookInfo", "QuestionBankInfo", "IngestionStatus",
        "QuestionService", "GenerationRequest", "GenerationResult",
        "PipelineService", "PipelineStageOutput", "PipelineTrace",
        "ValidationService",
        "BenchmarkService", "BenchmarkSummary",
        "CacheService", "CacheEntry",
        "VersionService", "VersionInfo",
        "LogService",
    ]
    for name in expected:
        assert name in svcs.__all__, f"{name} not in services.__all__"


def test_service_methods_are_stable():
    """The v1 service method names are frozen (Phase 12 API stability)."""
    from medrack.dashboard.services import (
        LibraryService, QuestionService, PipelineService,
        ValidationService, BenchmarkService, CacheService,
        VersionService, LogService,
    )
    # LibraryService
    lib_methods = {"list_books", "list_question_banks", "get_ingestion_status",
                   "add_book", "remove_book", "reindex"}
    assert lib_methods.issubset(set(dir(LibraryService)))
    # QuestionService
    qs_methods = {"generate", "generate_batch", "revise", "re_answer_stale"}
    assert qs_methods.issubset(set(dir(QuestionService)))
    # PipelineService
    ps_methods = {"inspect_planner", "inspect_blueprint", "inspect"}
    assert ps_methods.issubset(set(dir(PipelineService)))
    # ValidationService
    vs_methods = {"validate", "summarize"}
    assert vs_methods.issubset(set(dir(ValidationService)))
    # BenchmarkService
    bs_methods = {"list_runs", "get_run", "compare"}
    assert bs_methods.issubset(set(dir(BenchmarkService)))
    # CacheService
    cs_methods = {"list_entries", "get_status", "reanswer"}
    assert cs_methods.issubset(set(dir(CacheService)))
    # VersionService
    v_methods = {"get_info"}
    assert v_methods.issubset(set(dir(VersionService)))
    # LogService
    ls_methods = {"tail", "search"}
    assert ls_methods.issubset(set(dir(LogService)))


# ----------------------------------------------------------------------
# JSON serialization
# ----------------------------------------------------------------------

def test_all_dataclasses_to_dict_is_json_serializable():
    """All service dataclasses serialize to JSON."""
    import json
    from medrack.dashboard.services import (
        BookInfo, QuestionBankInfo, IngestionStatus,
        GenerationResult, PipelineStageOutput, PipelineTrace,
        BenchmarkSummary, CacheEntry, VersionInfo,
    )
    # Build each dataclass and verify JSON roundtrip
    book = BookInfo(book_id="x", title="X", subject="psm", path="/x.pdf", indexed=False)
    json.dumps(book.to_dict())  # must not raise
    qb = QuestionBankInfo(name="v1", version="v1", subject="psm", path="/x.json", question_count=10)
    json.dumps(qb.to_dict())
    ist = IngestionStatus(book_id="x", status="ok", started_at="2025-01-01T00:00:00")
    json.dumps(ist.to_dict())
    gr = GenerationResult(qid="q001", ok=True)
    json.dumps(gr.to_dict())
    pso = PipelineStageOutput(stage="planner", output={"k": "v"})
    json.dumps(pso.to_dict())
    pt = PipelineTrace(qid="q001", stages=[pso])
    json.dumps(pt.to_dict())
    bs = BenchmarkSummary(
        run_id="x", timestamp="2025", llm_mode="mock",
        n_questions=20, n_success=40, n_failure=0,
        cache_hit_rate=0.5, total_tokens=12000,
        avg_total_latency_seconds=0.17,
        avg_pdf_generation_seconds=0.005,
        json_report_path="/x.json",
    )
    json.dumps(bs.to_dict())
    ce = CacheEntry(qid="q001", subject="psm", is_stale=False)
    json.dumps(ce.to_dict())
    vi = VersionInfo(package_version="0.2.0", pipeline_versions={"schema": 2}, benchmark_baseline_tag="x")
    json.dumps(vi.to_dict())
