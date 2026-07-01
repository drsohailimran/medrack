"""BenchmarkService — Benchmark history and reports (Phase 12).

The :class:`BenchmarkService` is the stable interface for viewing
benchmark history, individual reports, and comparing runs.

This is the "Benchmark Console" feature requested in the Phase 12
directive.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkSummary:
    """A summary of a single benchmark run."""

    run_id: str
    timestamp: str
    llm_mode: str  # "mock" | "real"
    n_questions: int
    n_success: int
    n_failure: int
    cache_hit_rate: float
    total_tokens: int
    avg_total_latency_seconds: float
    avg_pdf_generation_seconds: float
    json_report_path: str
    markdown_report_path: Optional[str] = None

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "llm_mode": self.llm_mode,
            "n_questions": self.n_questions,
            "n_success": self.n_success,
            "n_failure": self.n_failure,
            "cache_hit_rate": self.cache_hit_rate,
            "total_tokens": self.total_tokens,
            "avg_total_latency_seconds": self.avg_total_latency_seconds,
            "avg_pdf_generation_seconds": self.avg_pdf_generation_seconds,
            "json_report_path": self.json_report_path,
            "markdown_report_path": self.markdown_report_path,
        }


class BenchmarkService:
    """Service for benchmark history and reports."""

    SCHEMA_VERSION = 1

    def __init__(self, medrack_home: Optional[Path] = None) -> None:
        from medrack.config import get_medrack_home
        if medrack_home is None:
            self._home = get_medrack_home()
        else:
            self._home = Path(medrack_home)

    @staticmethod
    def _summary_from_file(json_path: Path, data: Dict[str, Any]) -> BenchmarkSummary:
        """Build a flat :class:`BenchmarkSummary` from a loaded run file.

        The on-disk run file nests its metrics under a ``summary`` key; this
        flattens them into the stable summary shape used by both
        ``list_runs`` and ``get_run_summary``.
        """
        s = data.get("summary", {})
        md_path = json_path.with_name(json_path.stem.replace("_run", "_report") + ".md")
        md_path_str = str(md_path) if md_path.exists() else None
        return BenchmarkSummary(
            run_id=json_path.stem.replace("_run", ""),
            timestamp=json_path.stem.split("_")[0] if "_" in json_path.stem else "",
            llm_mode=s.get("llm_mode", data.get("llm_mode", "unknown")),
            n_questions=s.get("n_questions", 0),
            n_success=s.get("n_success", 0),
            n_failure=s.get("n_failure", 0),
            cache_hit_rate=s.get("cache_hit_rate", 0.0),
            total_tokens=s.get("total_tokens", 0),
            avg_total_latency_seconds=s.get("avg_total_latency_seconds", 0.0),
            avg_pdf_generation_seconds=s.get("avg_pdf_generation_seconds", 0.0),
            json_report_path=str(json_path),
            markdown_report_path=md_path_str,
        )

    def list_runs(self) -> List[BenchmarkSummary]:
        """List all benchmark runs in the history."""
        runs: List[BenchmarkSummary] = []
        runs_dir = self._home / "benchmarks" / "runs"
        if not runs_dir.exists():
            return runs
        # Each run produces a `*_run.json` and an optional `*_report.md`
        for json_path in sorted(runs_dir.rglob("*_run.json")):
            try:
                with json_path.open(encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            runs.append(self._summary_from_file(json_path, data))
        return runs

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get the full (raw) JSON report for a single run.

        Returns the complete on-disk run file (with nested ``summary`` and
        per-question ``records``). Used by :meth:`compare`. The HTTP API
        exposes the flat summary via :meth:`get_run_summary` to match the
        frontend ``BenchmarkSummary`` contract.
        """
        runs_dir = self._home / "benchmarks" / "runs"
        if not runs_dir.exists():
            return None
        # Search for any *_run.json with this stem
        for json_path in runs_dir.rglob(f"*{run_id}*_run.json"):
            try:
                with json_path.open(encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
        return None

    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a single run as a flat ``BenchmarkSummary`` dict.

        This matches the frontend ``BenchmarkSummary`` contract (the same
        shape returned by :meth:`list_runs`), unlike :meth:`get_run` which
        returns the raw nested run file.
        """
        runs_dir = self._home / "benchmarks" / "runs"
        if not runs_dir.exists():
            return None
        for json_path in runs_dir.rglob(f"*{run_id}*_run.json"):
            try:
                with json_path.open(encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            return self._summary_from_file(json_path, data).to_dict()
        return None

    def compare(
        self,
        run_id_a: str,
        run_id_b: str,
    ) -> Dict[str, Any]:
        """Compare two benchmark runs side-by-side."""
        a = self.get_run(run_id_a)
        b = self.get_run(run_id_b)
        if a is None or b is None:
            return {
                "ok": False,
                "error": f"could not find one or both runs: {run_id_a}, {run_id_b}",
            }
        sa = a.get("summary", {})
        sb = b.get("summary", {})
        return {
            "ok": True,
            "run_a": run_id_a,
            "run_b": run_id_b,
            "delta": {
                "n_questions": sb.get("n_questions", 0) - sa.get("n_questions", 0),
                "n_success": sb.get("n_success", 0) - sa.get("n_success", 0),
                "n_failure": sb.get("n_failure", 0) - sa.get("n_failure", 0),
                "cache_hit_rate": sb.get("cache_hit_rate", 0.0) - sa.get("cache_hit_rate", 0.0),
                "total_tokens": sb.get("total_tokens", 0) - sa.get("total_tokens", 0),
                "avg_total_latency_seconds": sb.get("avg_total_latency_seconds", 0.0)
                - sa.get("avg_total_latency_seconds", 0.0),
            },
        }


__all__ = ["BenchmarkService", "BenchmarkSummary"]
