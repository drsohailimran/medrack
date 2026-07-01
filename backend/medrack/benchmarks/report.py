"""medrack.benchmarks.report — write JSON + Markdown reports from a BenchmarkRun.

The benchmark engine (medrack.benchmarks.engine) produces a
BenchmarkRun. This module takes a BenchmarkRun and writes it to
disk in a structured way:

  <output-dir>/<timestamp>_run.json     (machine-readable)
  <output-dir>/<timestamp>_report.md   (human-readable)

The reporting layer is intentionally separate from the engine so
that future HTML or dashboard visualisation can be added without
touching the engine. The Markdown writer is a thin function that
can be replaced or extended without breaking the JSON contract.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from medrack.benchmarks.engine import BenchmarkRun, BenchmarkRecord


def write_json_report(run: BenchmarkRun, output_dir: Path) -> Path:
    """Write a JSON-serialisable copy of the run to ``<output_dir>/<ts>_run.json``.

    Returns the path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _filename_safe_timestamp(run.timestamp)
    out_path = output_dir / f"{ts}_run.json"
    payload = {
        "timestamp": run.timestamp,
        "suite_name": run.suite_name,
        "suite_path": run.suite_path,
        "model": run.model,
        "subject_filter": run.subject_filter,
        "summary": _summary_dict(run),
        "records": [asdict(r) for r in run.records],
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return out_path


def write_markdown_report(run: BenchmarkRun, output_dir: Path) -> Path:
    """Write a Markdown report to ``<output_dir>/<ts>_report.md``.

    Returns the path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _filename_safe_timestamp(run.timestamp)
    out_path = output_dir / f"{ts}_report.md"

    lines: list[str] = []
    lines.append(f"# MedRack Benchmark Report — {run.suite_name}")
    lines.append("")
    lines.append(f"- **Timestamp:** {run.timestamp}")
    lines.append(f"- **Suite:** `{run.suite_name}` ({run.suite_path})")
    lines.append(f"- **Model:** `{run.model}`")
    if run.subject_filter:
        lines.append(f"- **Subject filter:** `{run.subject_filter}`")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    summary = _summary_dict(run)
    for key, value in summary.items():
        if isinstance(value, float):
            formatted = f"{value:.3f}"
        else:
            formatted = str(value)
        lines.append(f"| {key} | {formatted} |")
    lines.append("")

    # Per-question table
    lines.append("## Per-question records")
    lines.append("")
    lines.append("| Module | QID | Path | Success | Cache hit | Stale | Prompt tok | Compl tok | Total tok | Retr chunks | Avg dist | PDF sec | Total sec |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in run.records:
        lines.append(
            f"| {r.module} | {r.qid} | {r.path} | "
            f"{'✓' if r.success else '✗'} | "
            f"{'✓' if r.cache_hit else '·'} | "
            f"{'!' if r.cache_stale else '·'} | "
            f"{r.prompt_tokens} | {r.completion_tokens} | {r.total_tokens} | "
            f"{r.retrieval_chunks} | {r.avg_retrieval_distance:.3f} | "
            f"{r.pdf_generation_seconds:.2f} | {r.total_latency_seconds:.2f} |"
        )
    lines.append("")

    # Failures section (if any)
    failures = [r for r in run.records if not r.success]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for r in failures:
            lines.append(f"- **{r.module}/{r.qid}** ({r.path}): `{r.error}`")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _summary_dict(run: BenchmarkRun) -> dict[str, Any]:
    """Return the summary fields as a flat dict (suitable for JSON)."""
    return {
        "n_questions": run.n_questions,
        "n_success": run.n_success,
        "n_failure": run.n_failure,
        "n_cold": run.n_cold,
        "n_warm": run.n_warm,
        "n_cache_hits": run.n_cache_hits,
        "n_cache_misses": run.n_cache_misses,
        "cache_hit_rate": run.cache_hit_rate,
        "total_prompt_tokens": run.total_prompt_tokens,
        "total_completion_tokens": run.total_completion_tokens,
        "total_tokens": run.total_tokens,
        "avg_prompt_tokens": run.avg_prompt_tokens,
        "avg_completion_tokens": run.avg_completion_tokens,
        "avg_total_tokens": run.avg_total_tokens,
        "avg_retrieval_latency_seconds": run.avg_retrieval_latency_seconds,
        "avg_generation_latency_seconds": run.avg_generation_latency_seconds,
        "avg_pdf_generation_seconds": run.avg_pdf_generation_seconds,
        "avg_total_latency_seconds": run.avg_total_latency_seconds,
        "avg_answer_length_chars": run.avg_answer_length_chars,
        "avg_answer_length_words": run.avg_answer_length_words,
        "avg_retrieval_chunks": run.avg_retrieval_chunks,
        "avg_retrieval_distance": run.avg_retrieval_distance,
    }


def _filename_safe_timestamp(iso_ts: str) -> str:
    """Convert an ISO timestamp like '2026-06-29T16:00:00+00:00' to
    '20260629T160000Z' (filesystem-safe)."""
    # Parse the timestamp; strip timezone for the filename
    try:
        dt = datetime.fromisoformat(iso_ts)
    except ValueError:
        return iso_ts.replace(":", "").replace("-", "")
    return dt.strftime("%Y%m%dT%H%M%SZ")


__all__ = [
    "write_json_report",
    "write_markdown_report",
    "_summary_dict",
]
