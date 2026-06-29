"""Tests for the Phase 5 benchmark framework.

These tests cover:
  - medrack.benchmarks.engine (BenchmarkRecord, BenchmarkRun, run_benchmark)
  - medrack.benchmarks.report (write_json_report, write_markdown_report)
  - medrack.benchmarks.run (CLI entry point)

The actual run.py CLI is exercised via subprocess in test_benchmarks_cli.py.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

MEDRACK = Path("/file_user_file") if False else Path("/home/sohail/.hermes/medrack")
VENV = Path("/home/sohail/.hermes/hermes-agent/venv")
PY = VENV / "bin/python"

# Make the medrack package importable
sys.path.insert(0, str(MEDRACK))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Isolate $MEDRACK_HOME to a temp dir so cache I/O doesn't pollute."""
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "answers").mkdir(parents=True, exist_ok=True)
    yield tmp_path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


def test_benchmark_record_constructs_with_defaults():
    from medrack.benchmarks.engine import BenchmarkRecord
    r = BenchmarkRecord(module="m", qid="q001", subject="psm",
                         marks=10, path="cold", success=True)
    assert r.module == "m"
    assert r.cache_hit is False
    assert r.prompt_tokens == 0
    assert r.total_latency_seconds == 0.0


def test_benchmark_run_constructs_with_defaults():
    from medrack.benchmarks.engine import BenchmarkRun
    r = BenchmarkRun(timestamp="2026-06-29T00:00:00Z", suite_name="v1",
                      suite_path="<inline>", model="mock", subject_filter=None)
    assert r.n_questions == 0
    assert r.cache_hit_rate == 0.0
    assert r.records == []


# ---------------------------------------------------------------------------
# run_benchmark end-to-end (with mock LLM)
# ---------------------------------------------------------------------------


def test_run_benchmark_single_qid_mock(temp_home):
    """A single-qid run with MockLLMClient produces 2 records (cold + warm)."""
    from medrack.answer.llm import MockLLMClient
    from medrack.benchmarks.engine import run_benchmark
    from medrack.tests.regression_datasets import load_regression_dataset

    ds = load_regression_dataset(1)
    suite = [q for q in ds["questions"] if q["qid"] == "q022" and q["module"] == "psm-module-1"]
    assert len(suite) == 1

    run = run_benchmark(
        suite=suite,
        module_sources=ds["_module_sources"],
        llm_client=MockLLMClient(),
        medrack_root=MEDRACK,
        qid_filter="q022",
    )

    assert run.n_questions == 1
    assert run.n_cold == 1
    assert run.n_warm == 1
    assert run.n_success == 2  # both cold and warm succeed
    assert run.n_failure == 0
    # Cold path: cache miss, then save
    cold = [r for r in run.records if r.path == "cold"][0]
    assert cold.cache_hit is False
    # Warm path: cache hit
    warm = [r for r in run.records if r.path == "warm"][0]
    assert warm.cache_hit is True
    assert run.cache_hit_rate == 0.5  # 1 hit out of 2 records


def test_run_benchmark_records_token_counts(temp_home):
    """The cold path records prompt/completion/total tokens from the LLM response."""
    from medrack.answer.llm import MockLLMClient
    from medrack.benchmarks.engine import run_benchmark
    from medrack.tests.regression_datasets import load_regression_dataset

    ds = load_regression_dataset(1)
    suite = [q for q in ds["questions"] if q["qid"] == "q022" and q["module"] == "psm-module-1"]

    run = run_benchmark(
        suite=suite,
        module_sources=ds["_module_sources"],
        llm_client=MockLLMClient(),
        medrack_root=MEDRACK,
        qid_filter="q022",
    )
    cold = [r for r in run.records if r.path == "cold"][0]
    # MockLLMClient returns fixed 500/100/600 token counts
    assert cold.prompt_tokens == 500
    assert cold.completion_tokens == 100
    assert cold.total_tokens == 600
    assert run.total_tokens == 600


def test_run_benchmark_records_pdf_generation_time(temp_home):
    """Both cold and warm paths record PDF generation latency."""
    from medrack.answer.llm import MockLLMClient
    from medrack.benchmarks.engine import run_benchmark
    from medrack.tests.regression_datasets import load_regression_dataset

    ds = load_regression_dataset(1)
    suite = [q for q in ds["questions"] if q["qid"] == "q022" and q["module"] == "psm-module-1"]

    run = run_benchmark(
        suite=suite,
        module_sources=ds["_module_sources"],
        llm_client=MockLLMClient(),
        medrack_root=MEDRACK,
        qid_filter="q022",
    )
    for r in run.records:
        assert r.pdf_generation_seconds > 0


def test_run_benchmark_subject_filter(temp_home):
    """The subject_filter limits the run to one subject."""
    from medrack.answer.llm import MockLLMClient
    from medrack.benchmarks.engine import run_benchmark
    from medrack.tests.regression_datasets import load_regression_dataset

    ds = load_regression_dataset(1)
    run = run_benchmark(
        suite=ds["questions"],
        module_sources=ds["_module_sources"],
        llm_client=MockLLMClient(),
        medrack_root=MEDRACK,
        subject_filter="fmt",
    )
    # Only 8 FMT questions in v1
    assert run.n_questions == 8
    for r in run.records:
        assert r.subject == "fmt"


def test_run_benchmark_no_warm_path(temp_home):
    """Setting run_warm=False produces only cold-path records."""
    from medrack.answer.llm import MockLLMClient
    from medrack.benchmarks.engine import run_benchmark
    from medrack.tests.regression_datasets import load_regression_dataset

    ds = load_regression_dataset(1)
    suite = [q for q in ds["questions"] if q["qid"] == "q022" and q["module"] == "psm-module-1"]
    run = run_benchmark(
        suite=suite, module_sources=ds["_module_sources"],
        llm_client=MockLLMClient(), medrack_root=MEDRACK,
        qid_filter="q022", run_warm=False,
    )
    assert run.n_cold == 1
    assert run.n_warm == 0
    assert all(r.path == "cold" for r in run.records)


# ---------------------------------------------------------------------------
# Report layer
# ---------------------------------------------------------------------------


def test_write_json_report_creates_file_with_metadata(temp_home):
    """The JSON report contains metadata + summary + records."""
    from medrack.answer.llm import MockLLMClient
    from medrack.benchmarks.engine import run_benchmark
    from medrack.benchmarks.report import write_json_report
    from medrack.tests.regression_datasets import load_regression_dataset

    ds = load_regression_dataset(1)
    suite = [q for q in ds["questions"] if q["qid"] == "q022" and q["module"] == "psm-module-1"]
    run = run_benchmark(
        suite=suite, module_sources=ds["_module_sources"],
        llm_client=MockLLMClient(), medrack_root=MEDRACK,
        qid_filter="q022",
    )
    out_dir = temp_home / "reports"
    out_path = write_json_report(run, out_dir)
    assert out_path.exists()
    payload = json.loads(out_path.read_text())
    assert payload["suite_name"] == "v1"
    assert payload["model"] == "mock"
    assert "summary" in payload
    assert payload["summary"]["n_questions"] == 1
    assert "records" in payload
    assert len(payload["records"]) == 2


def test_write_markdown_report_creates_file_with_table(temp_home):
    """The Markdown report contains a header, summary table, and per-question table."""
    from medrack.answer.llm import MockLLMClient
    from medrack.benchmarks.engine import run_benchmark
    from medrack.benchmarks.report import write_markdown_report
    from medrack.tests.regression_datasets import load_regression_dataset

    ds = load_regression_dataset(1)
    suite = [q for q in ds["questions"] if q["qid"] == "q022" and q["module"] == "psm-module-1"]
    run = run_benchmark(
        suite=suite, module_sources=ds["_module_sources"],
        llm_client=MockLLMClient(), medrack_root=MEDRACK,
        qid_filter="q022",
    )
    out_dir = temp_home / "reports"
    out_path = write_markdown_report(run, out_dir)
    content = out_path.read_text()
    assert "# MedRack Benchmark Report" in content
    assert "## Summary" in content
    assert "## Per-question records" in content
    assert "psm-module-1" in content
    assert "q022" in content
    # Per-question table has both paths
    assert "| cold |" in content
    assert "| warm |" in content


def test_markdown_report_includes_failures_section(temp_home):
    """Failures are listed in a dedicated section."""
    from medrack.benchmarks.engine import BenchmarkRecord, BenchmarkRun
    from medrack.benchmarks.report import write_markdown_report
    from datetime import datetime, timezone
    r = BenchmarkRecord(module="m", qid="q001", subject="psm",
                        marks=10, path="cold", success=False,
                        error="LLMUnavailableError: all models failed")
    run = BenchmarkRun(
        timestamp=datetime.now(timezone.utc).isoformat(),
        suite_name="v1", suite_path="<inline>", model="mock",
        subject_filter=None,
    )
    run.records = [r]
    run.n_questions = 1
    run.n_cold = 1
    run.n_success = 0
    run.n_failure = 1
    out = write_markdown_report(run, temp_home)
    text = out.read_text()
    assert "## Failures" in text
    assert "LLMUnavailableError" in text


def test_filename_safe_timestamp_handles_iso():
    from medrack.benchmarks.report import _filename_safe_timestamp
    assert _filename_safe_timestamp("2026-06-29T16:00:00+00:00") == "20260629T160000Z"
    assert _filename_safe_timestamp("2026-06-29T16:00:00") == "20260629T160000Z"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_module_entry_point_help():
    """python -m medrack.benchmarks.run --help works and lists options."""
    r = subprocess.run(
        [str(PY), "-m", "medrack.benchmarks.run", "--help"],
        capture_output=True, text=True, cwd=str(MEDRACK), timeout=30,
    )
    assert r.returncode == 0
    assert "medrack benchmark" in r.stdout
    assert "--suite" in r.stdout
    assert "--llm" in r.stdout


def test_cli_via_medrack_benchmark_in_help():
    """The medrack binary lists the 'benchmark' subcommand in --help."""
    medrack_bin = VENV / "bin/medrack"
    r = subprocess.run(
        [str(medrack_bin), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
    assert "benchmark" in r.stdout


def test_module_entry_point_qid_filter_mock(temp_home):
    """End-to-end: module entry point with --qid and --llm mock produces valid report."""
    r = subprocess.run(
        [str(PY), "-m", "medrack.benchmarks.run",
         "--qid", "q022", "--llm", "mock",
         "--output-dir", str(temp_home / "out")],
        capture_output=True, text=True, cwd=str(MEDRACK), timeout=120,
        env={**os.environ, "MEDRACK_HOME": str(temp_home)},
    )
    assert r.returncode == 0, f"stderr={r.stderr[-500:]}"
    # Reports were written
    out_dir = temp_home / "out"
    assert any(out_dir.glob("*_run.json"))
    assert any(out_dir.glob("*_report.md"))


def test_module_entry_point_no_warm_path(temp_home):
    """--no-warm-path produces only cold-path records."""
    r = subprocess.run(
        [str(PY), "-m", "medrack.benchmarks.run",
         "--qid", "q022", "--llm", "mock", "--no-warm-path",
         "--output-dir", str(temp_home / "out")],
        capture_output=True, text=True, cwd=str(MEDRACK), timeout=120,
        env={**os.environ, "MEDRACK_HOME": str(temp_home)},
    )
    assert r.returncode == 0
    # Find the run.json
    runs = list((temp_home / "out").glob("*_run.json"))
    assert len(runs) == 1
    payload = json.loads(runs[0].read_text())
    assert payload["summary"]["n_cold"] == 1
    assert payload["summary"]["n_warm"] == 0
