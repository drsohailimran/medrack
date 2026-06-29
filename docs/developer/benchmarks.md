# MedRack Benchmark Framework

This document describes the MedRack benchmark framework. The
framework is the operator's tool for measuring answer quality,
retrieval relevance, latency, and token usage over time.

## Why benchmarks

Without a benchmark framework, "Phase X is faster" or "Phase
Y uses fewer tokens" are unfalsifiable claims. The benchmark
framework turns these into measurable comparisons against a
frozen baseline.

## Frozen baseline

The frozen baseline is tagged at `phase-5-baseline` (commit
`afba43a`). It represents the v0 architecture (no adaptive
retrieval, no metadata, no planner, no blueprint, no
reranker, no validator). All future benchmark comparisons
report their delta against this baseline.

| Metric | Phase 5 baseline (mock LLM) |
|--------|------------------------------|
| n_questions | 20 |
| n_success | 40/40 |
| n_failure | 0 |
| cache_hit_rate | 0.500 |
| total_tokens | 12,000 |
| avg_total_latency | 0.173s |
| avg_pdf_generation | 0.005s |

The mock LLM mode runs the full pipeline with a canned
response, so aggregate metrics measure the **infrastructure
overhead** (retrieval, render, cache, validation) without
LLM variance.

## Regression dataset

The regression dataset is at
`medrack/tests/regression_datasets/v1.json`. It contains 20
questions (12 PSM, 8 FMT; 14 10-mark, 6 5-mark; 5 easy, 10
moderate, 5 difficult).

The dataset is **frozen** as of Phase 4. Adding questions
requires a new dataset version (e.g. `v2.json`).

## Running a benchmark

```bash
# Mock LLM (deterministic, fast, infrastructure-only)
python -m medrack.benchmarks.run --llm mock --output-dir benchmarks/runs/v1-mock

# Real LLM (requires API keys configured in the environment)
python -m medrack.benchmarks.run --llm real --output-dir benchmarks/runs/v1-real

# Custom output dir
python -m medrack.benchmarks.run --llm mock --output-dir /path/to/runs
```

Each run produces:
- A `*_run.json` (full report, machine-readable)
- A `*_report.md` (human-readable summary)

## Reading a report

A typical mock report:

```json
{
  "n_questions": 20,
  "n_success": 40,
  "n_failure": 0,
  "cache_hit_rate": 0.500,
  "total_tokens": 12000,
  "avg_total_tokens": 600,
  "avg_total_latency_seconds": 0.169,
  "avg_pdf_generation_seconds": 0.005,
  "json_report": "benchmarks/runs/v1-mock/20250629T193408Z_run.json",
  "markdown_report": "benchmarks/runs/v1-mock/20250629T193408Z_report.md"
}
```

`n_questions` is the number of unique questions; `n_success` is
`2 * n_questions` because each question produces one answer and
one PDF. So 20 questions → 40 successes is the expected output.

## Comparing runs

The `BenchmarkService.compare` method returns a delta between
two runs:

```python
from medrack.dashboard.services import BenchmarkService
svc = BenchmarkService()
result = svc.compare("run_a_id", "run_b_id")
# {
#   "ok": true,
#   "run_a": "...",
#   "run_b": "...",
#   "delta": {
#     "n_questions": 0,
#     "n_success": 0,
#     "n_failure": 0,
#     "cache_hit_rate": 0.0,
#     "total_tokens": 0,
#     "avg_total_latency_seconds": 0.0,
#   }
# }
```

The HTTP API exposes this at `GET /api/v1/benchmarks/compare`.

## Service vs HTTP

```python
# Service
from medrack.dashboard.services import BenchmarkService
svc = BenchmarkService()
runs = svc.list_runs()  # [BenchmarkSummary, ...]
```

```bash
# HTTP
curl http://localhost:8000/api/v1/benchmarks/runs
```

## Real LLM benchmarks

Real LLM benchmarks are non-deterministic and may hang on
slow API calls. The operator should run them in a quiet
session. The benchmark framework includes timeouts and
retries (see `medrack/benchmarks/engine.py`).

When a real LLM benchmark hangs, the operator can:

1. Cancel the run
2. Re-run with the `--timeout` flag
3. Re-run with `--llm mock` to verify the infrastructure

## Stability

The benchmark framework is **frozen** as of Phase 5. Future
benchmark improvements (e.g. a new metric) are added as
additional fields, not by changing existing ones.

The regression dataset is **frozen** as of Phase 4 (v1).
Adding questions requires a new dataset version.

The frozen baseline tag (`phase-5-baseline`) is the reference
point for all future comparisons. Do not rebase it.
