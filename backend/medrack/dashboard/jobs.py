"""In-process async job registry with progress reporting.

Long-running API operations (book ingest, question-bank extraction,
solving a whole bank) can take minutes, which is far longer than a
browser will hold a single HTTP request open. Instead of blocking the
request, the API kicks off a background thread and returns a ``job_id``;
the frontend then polls ``GET /api/v1/jobs/{job_id}`` for a live
percentage and, when finished, the result (including a PDF download
where applicable).

The registry is a simple thread-safe in-memory dict. The API runs as a
single uvicorn process, so a module-level singleton is sufficient — no
Redis/Celery needed. Jobs are ephemeral; they live for the lifetime of
the process (a completed job's PDF is persisted on disk under
``$MEDRACK_HOME/output`` regardless).
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from medrack.utils.logger import get_logger

logger = get_logger(__name__)

# A progress callback: progress(percent: float, message: str) -> None
ProgressFn = Callable[[float, str], None]
# A job body: target(job, progress) -> result dict
JobBody = Callable[["Job", ProgressFn], Optional[dict]]


@dataclass
class Job:
    """A single background job with live progress."""

    id: str
    kind: str
    status: str = "pending"  # pending | running | done | error
    percent: float = 0.0
    message: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            # Two-decimal precision, as the frontend progress bar expects.
            "percent": round(self.percent, 2),
            "message": self.message,
            "result": self.result,
            "error": self.error,
        }


class JobRegistry:
    """Thread-safe registry of background jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, kind: str) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def run(self, kind: str, target: JobBody) -> Job:
        """Create a job and run ``target`` on a daemon thread.

        ``target`` receives ``(job, progress)`` and returns a result
        dict. It should call ``progress(percent, message)`` to report
        live progress. Exceptions are captured onto the job.
        """
        job = self.create(kind)

        def progress(percent: float, message: str = "") -> None:
            job.percent = max(0.0, min(100.0, float(percent)))
            if message:
                job.message = message
            job.updated_at = time.time()

        def runner() -> None:
            job.status = "running"
            job.updated_at = time.time()
            try:
                result = target(job, progress)
                job.result = result or {}
                job.percent = 100.0
                job.status = "done"
                job.message = job.message or "Done"
            except Exception as exc:  # noqa: BLE001 - surface any failure to the client
                logger.exception("Job %s (%s) failed", job.id, kind)
                job.error = str(exc)
                job.status = "error"
            job.updated_at = time.time()

        threading.Thread(
            target=runner, daemon=True, name=f"job-{kind}-{job.id[:8]}"
        ).start()
        return job


# Module-level singleton shared by all endpoints.
registry = JobRegistry()

__all__ = ["Job", "JobRegistry", "registry", "ProgressFn"]
