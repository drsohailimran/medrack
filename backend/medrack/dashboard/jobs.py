"""Async job registry with progress, cancel, SQLite persistence, and GPU lock.

Long-running API operations return a ``job_id``; the frontend polls
``GET /api/v1/jobs/{job_id}``.

Improvements (reliability):
- Jobs are **persisted to SQLite** under ``$MEDRACK_HOME/jobs.sqlite`` so status
  survives API process inspection; on restart, non-terminal jobs are marked
  ``error`` with ``interrupted_by_restart``.
- **GPU resource lock**: hybrid OCR and solve cannot run concurrently (shared
  Windows model / agent stops Qwopus during OCR).
- Cooperative cancel (P3): finishes current unit, then stops.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from medrack.utils.logger import get_logger

logger = get_logger(__name__)

ProgressFn = Callable[[float, str], None]
JobBody = Callable[["Job", ProgressFn], Optional[dict]]

# Job kinds that must not overlap (OCR stops model; solve needs model).
GPU_EXCLUSIVE_KINDS: Set[str] = {
    "hybrid_ingest_book",
    "extract_bank",
    "solve_bank",
}


def _jobs_db_path() -> Path:
    from medrack.config import get_medrack_home

    root = get_medrack_home()
    root.mkdir(parents=True, exist_ok=True)
    return root / "jobs.sqlite"


@dataclass
class Job:
    """A single background job with live progress."""

    id: str
    kind: str
    status: str = "pending"  # pending | running | done | error | cancelled
    percent: float = 0.0
    message: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None
    cancel_requested: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "percent": round(self.percent, 2),
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "cancel_requested": self.cancel_requested,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class _JobStore:
    """SQLite persistence for job snapshots."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _jobs_db_path()
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        status TEXT NOT NULL,
                        percent REAL NOT NULL DEFAULT 0,
                        message TEXT NOT NULL DEFAULT '',
                        result_json TEXT,
                        error TEXT,
                        cancel_requested INTEGER NOT NULL DEFAULT 0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def upsert(self, job: Job) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, kind, status, percent, message, result_json, error,
                        cancel_requested, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        kind=excluded.kind,
                        status=excluded.status,
                        percent=excluded.percent,
                        message=excluded.message,
                        result_json=excluded.result_json,
                        error=excluded.error,
                        cancel_requested=excluded.cancel_requested,
                        updated_at=excluded.updated_at
                    """,
                    (
                        job.id,
                        job.kind,
                        job.status,
                        float(job.percent),
                        job.message or "",
                        json.dumps(job.result) if job.result is not None else None,
                        job.error,
                        1 if job.cancel_requested else 0,
                        float(job.created_at),
                        float(job.updated_at),
                    ),
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("job store upsert failed: %s", exc)
            finally:
                conn.close()

    def load(self, job_id: str) -> Optional[Job]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        result = None
        if row["result_json"]:
            try:
                result = json.loads(row["result_json"])
            except Exception:  # noqa: BLE001
                result = None
        return Job(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],
            percent=float(row["percent"] or 0),
            message=row["message"] or "",
            result=result,
            error=row["error"],
            cancel_requested=bool(row["cancel_requested"]),
            created_at=float(row["created_at"] or time.time()),
            updated_at=float(row["updated_at"] or time.time()),
        )

    def mark_interrupted_running(self) -> int:
        """On API boot: any running/pending job is no longer executing."""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'error',
                        error = COALESCE(error, '') || CASE
                            WHEN error IS NULL OR error = '' THEN 'interrupted_by_api_restart'
                            ELSE ' | interrupted_by_api_restart'
                        END,
                        message = 'Interrupted by API restart',
                        updated_at = ?
                    WHERE status IN ('pending', 'running')
                    """,
                    (time.time(),),
                )
                conn.commit()
                return int(cur.rowcount or 0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("mark_interrupted failed: %s", exc)
                return 0
            finally:
                conn.close()


class JobRegistry:
    """Thread-safe registry of background jobs with disk backup + GPU lock."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._store = _JobStore()
        n = self._store.mark_interrupted_running()
        if n:
            logger.info("Marked %s interrupted job(s) after API start", n)
        # Exclusive lock for GPU-heavy work (OCR stops Qwopus; solve needs it).
        self._gpu_lock = threading.Lock()
        self._gpu_holder: Optional[str] = None  # job_id

    def _persist(self, job: Job) -> None:
        try:
            self._store.upsert(job)
        except Exception as exc:  # noqa: BLE001
            logger.warning("persist job %s failed: %s", job.id, exc)

    def create(self, kind: str) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None:
            return job
        # Fall back to disk (survives in-memory loss after restart for history)
        return self._store.load(job_id)

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent jobs from SQLite (for ops / P2 monitoring)."""
        conn = self._store._connect()
        try:
            rows = conn.execute(
                "SELECT id FROM jobs ORDER BY updated_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        out: List[Dict[str, Any]] = []
        for row in rows:
            j = self.get(row["id"])
            if j:
                out.append(j.to_dict())
        return out

    def gpu_status(self) -> Dict[str, Any]:
        """Whether the exclusive OCR/solve GPU lock is held."""
        holder = self._gpu_holder
        busy = holder is not None
        kind = None
        if holder:
            j = self.get(holder)
            if j:
                kind = j.kind
        return {
            "busy": busy,
            "holder_job_id": holder,
            "holder_kind": kind,
            "exclusive_kinds": sorted(GPU_EXCLUSIVE_KINDS),
        }

    def active_gpu_jobs(self) -> List[Dict[str, Any]]:
        """In-memory running/pending jobs that need the GPU lock."""
        with self._lock:
            jobs = list(self._jobs.values())
        out: List[Dict[str, Any]] = []
        for j in jobs:
            if j.kind in GPU_EXCLUSIVE_KINDS and j.status in ("pending", "running"):
                out.append(j.to_dict())
        return out

    def request_cancel(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                job = self._store.load(job_id)
                if job is not None:
                    self._jobs[job.id] = job
            if job is None:
                return None
            if job.status in ("done", "error", "cancelled"):
                return job
            job.cancel_requested = True
            job.message = job.message or "Stopping…"
            job.updated_at = time.time()
        self._persist(job)
        return job

    def run(self, kind: str, target: JobBody) -> Job:
        """Create a job and run ``target`` on a daemon thread."""
        job = self.create(kind)
        needs_gpu = kind in GPU_EXCLUSIVE_KINDS

        def progress(percent: float, message: str = "") -> None:
            job.percent = max(0.0, min(100.0, float(percent)))
            if message:
                job.message = message
            job.updated_at = time.time()
            self._persist(job)

        def runner() -> None:
            got_gpu = False
            try:
                if needs_gpu:
                    progress(0.5, "Waiting for GPU lock (OCR/solve exclusive)…")
                    # Block until free — sequential overnight is fine
                    while True:
                        if self._gpu_lock.acquire(timeout=2.0):
                            got_gpu = True
                            self._gpu_holder = job.id
                            break
                        if job.cancel_requested:
                            job.status = "cancelled"
                            job.message = "Cancelled while waiting for GPU"
                            job.result = {"cancelled": True}
                            job.updated_at = time.time()
                            self._persist(job)
                            return
                        # stay pending/running with message
                        job.status = "running"
                        job.updated_at = time.time()
                        self._persist(job)

                job.status = "running"
                job.updated_at = time.time()
                self._persist(job)
                result = target(job, progress)
                job.result = result or {}
                cancelled = bool(job.cancel_requested) or bool(
                    job.result.get("cancelled")
                )
                if cancelled:
                    job.result["cancelled"] = True
                    job.status = "cancelled"
                    job.message = job.message or "Stopped"
                else:
                    job.percent = 100.0
                    job.status = "done"
                    job.message = job.message or "Done"
            except Exception as exc:  # noqa: BLE001
                logger.exception("Job %s (%s) failed", job.id, kind)
                job.error = str(exc)
                job.status = "error"
                if not job.message:
                    job.message = "Error"
            finally:
                if got_gpu:
                    self._gpu_holder = None
                    try:
                        self._gpu_lock.release()
                    except Exception:  # noqa: BLE001
                        pass
                job.updated_at = time.time()
                self._persist(job)

        threading.Thread(
            target=runner, daemon=True, name=f"job-{kind}-{job.id[:8]}"
        ).start()
        return job


# Module-level singleton shared by all endpoints.
registry = JobRegistry()

__all__ = [
    "Job",
    "JobRegistry",
    "registry",
    "ProgressFn",
    "GPU_EXCLUSIVE_KINDS",
]
