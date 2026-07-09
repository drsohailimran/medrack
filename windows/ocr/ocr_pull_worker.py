"""
MedRack Windows OCR **pull worker** (P1).

Polls Ubuntu for queued hybrid-OCR jobs, downloads the source PDF, runs
Plan C hybrid OCR, uploads clean_text.pdf. No inbound Windows firewall port.

  set PYTHONPATH=C:\\medrack-ocr
  C:\\medrack-ocr\\venv\\Scripts\\python.exe C:\\medrack-ocr\\ocr_pull_worker.py

Env:
  MEDRACK_API_BASE   default http://192.168.29.82:8010/api/v1
  MEDRACK_OCR_TOKEN  default medrack-ocr  (must match Ubuntu .env)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

API = os.environ.get("MEDRACK_API_BASE", "http://192.168.29.82:8010/api/v1").rstrip("/")
TOKEN = os.environ.get("MEDRACK_OCR_TOKEN", "medrack-ocr")
HEADERS = {"X-OCR-Token": TOKEN}
POLL_SEC = float(os.environ.get("MEDRACK_OCR_POLL_SEC", "3"))


def report(job_id: str, percent: float, message: str, status: str = "running") -> None:
    try:
        httpx.post(
            f"{API}/ocr/agent/jobs/{job_id}/progress",
            headers=HEADERS,
            json={"percent": percent, "message": message, "status": status},
            timeout=30.0,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  progress report failed: {exc}", flush=True)


def process_job(meta: dict) -> None:
    from pipeline.hybrid_ocr import run_hybrid_pipeline

    job_id = meta["job_id"]
    use_marker = bool(meta.get("use_marker"))
    work = ROOT / "jobs" / job_id
    work.mkdir(parents=True, exist_ok=True)
    src = work / "source.pdf"

    print(f"[{job_id[:8]}] downloading source…", flush=True)
    report(job_id, 2, "downloading source PDF", "running")
    with httpx.Client(timeout=600.0) as client:
        r = client.get(f"{API}/ocr/agent/jobs/{job_id}/source", headers=HEADERS)
        r.raise_for_status()
        src.write_bytes(r.content)
    print(f"[{job_id[:8]}] source {src.stat().st_size // 1024} KB", flush=True)

    def progress(pct: float, msg: str = "") -> None:
        # keep some headroom; upload is final step
        report(job_id, min(95.0, float(pct) * 0.95), msg or "OCR", "running")
        print(f"[{job_id[:8]}] {pct:.1f}% {msg}", flush=True)

    try:
        result = run_hybrid_pipeline(
            src,
            work / "work",
            use_marker=use_marker,
            progress=progress,
        )
        clean = Path(result["clean_pdf"])
        report(job_id, 96, "uploading clean PDF", "running")
        with open(clean, "rb") as fh:
            files = {"file": ("clean_text.pdf", fh, "application/pdf")}
            up = httpx.post(
                f"{API}/ocr/agent/jobs/{job_id}/result",
                headers=HEADERS,
                files=files,
                timeout=600.0,
            )
            up.raise_for_status()
        print(f"[{job_id[:8]}] DONE → uploaded clean PDF", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[{job_id[:8]}] ERROR: {exc}", flush=True)
        try:
            httpx.post(
                f"{API}/ocr/agent/jobs/{job_id}/error",
                headers=HEADERS,
                json={"error": str(exc)},
                timeout=30.0,
            )
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    print(f"MedRack OCR pull worker", flush=True)
    print(f"  API={API}", flush=True)
    print(f"  Polling every {POLL_SEC}s — Ctrl+C to stop", flush=True)
    while True:
        try:
            r = httpx.get(f"{API}/ocr/agent/claim", headers=HEADERS, timeout=30.0)
            if r.status_code == 401:
                print("UNAUTHORIZED — check MEDRACK_OCR_TOKEN vs Ubuntu .env", flush=True)
                time.sleep(10)
                continue
            r.raise_for_status()
            body = r.json()
            job = body.get("job")
            if job:
                print(f"Claimed job {job.get('job_id','?')[:8]} title={job.get('title')}", flush=True)
                process_job(job)
            else:
                time.sleep(POLL_SEC)
        except KeyboardInterrupt:
            print("Stopped.", flush=True)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"poll error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
