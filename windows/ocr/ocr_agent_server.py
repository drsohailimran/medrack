"""
MedRack unified OCR agent (single process for full UI integration).

Started automatically by **Start MedRack**. Does two things:

1. **HTTP push API** on :8090 — Ubuntu POSTs a PDF when user clicks Ingest
2. **Pull loop** (background) — also claims queued jobs if push is blocked

On each job: stop Qwopus → RapidOCR → validate → text PDF → start Qwopus.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
import httpx
import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

JOBS_DIR = ROOT / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

API = os.environ.get("MEDRACK_API_BASE", "http://192.168.29.82:8010/api/v1").rstrip("/")
TOKEN = os.environ.get("MEDRACK_OCR_TOKEN", "medrack-ocr")
HEADERS = {"X-OCR-Token": TOKEN}
ENABLE_PULL = os.environ.get("MEDRACK_OCR_PULL", "1").strip() not in ("0", "false", "no")

app = FastAPI(title="MedRack OCR Agent", version="1.3.1")
_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}
# Only one OCR job at a time — never stack OCR while previous still holds GPU/RAM
_pipeline_lock = threading.Lock()


def _job_dir(job_id: str) -> Path:
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _set_job(job_id: str, **kwargs: Any) -> None:
    with _lock:
        j = _jobs.setdefault(
            job_id,
            {
                "job_id": job_id,
                "status": "pending",
                "percent": 0.0,
                "message": "",
                "error": None,
                "result": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            },
        )
        j.update(kwargs)
        j["updated_at"] = time.time()
        (_job_dir(job_id) / "status.json").write_text(
            json.dumps(j, indent=2), encoding="utf-8"
        )


def _run_pipeline(job_id: str, src: Path, use_marker: bool) -> None:
    from pipeline import model_control
    from pipeline.hybrid_ocr import run_hybrid_pipeline

    got = _pipeline_lock.acquire(blocking=False)
    if not got:
        _set_job(
            job_id,
            status="error",
            error="Another OCR job is already running",
            message="error: OCR agent busy — wait for current job to finish",
        )
        return

    _set_job(
        job_id,
        status="running",
        percent=0.2,
        message="Stopping Qwopus and freeing RAM before OCR…",
    )

    def progress(pct: float, msg: str = "") -> None:
        _set_job(job_id, status="running", percent=float(pct), message=msg or "")

    try:
        # Explicit pre-stop in the agent so UI shows phase early and we never
        # load RapidOCR while llama still holds mlock + VRAM.
        stop = model_control.stop_model(timeout_sec=120.0)
        if not stop.get("ok"):
            raise RuntimeError(
                "Qwopus stop/RAM free failed — OCR not started (prevents system crash). "
                + str(stop.get("error") or stop)
            )
        _set_job(
            job_id,
            status="running",
            percent=3.0,
            message=(
                "Qwopus stopped; RAM free "
                f"{stop.get('free_ram_mb_after')} MiB — starting OCR"
            ),
            model_stop=stop,
        )

        result = run_hybrid_pipeline(
            src,
            _job_dir(job_id) / "work",
            use_marker=use_marker,
            progress=progress,
            restart_model=True,
        )
        if isinstance(result, dict) and "model_stop" not in result:
            result["model_stop"] = stop
        clean = Path(result["clean_pdf"])
        dest = _job_dir(job_id) / "clean_text.pdf"
        if clean.is_file():
            dest.write_bytes(clean.read_bytes())
            result["clean_pdf"] = str(dest)
        _set_job(
            job_id,
            status="done",
            percent=100.0,
            message="Done — model restarted",
            result=result,
        )
    except Exception as exc:  # noqa: BLE001
        try:
            model_control.stop_model(timeout_sec=15.0)
        except Exception:  # noqa: BLE001
            pass
        _set_job(job_id, status="error", error=str(exc), message=f"error: {exc}")
    finally:
        _pipeline_lock.release()


@app.get("/v1/health")
def health():
    from pipeline import model_control

    return {
        "ok": True,
        "service": "medrack-ocr-agent",
        "version": "1.3.1",
        "auto_marker": True,
        "pull_loop": ENABLE_PULL,
        "pipeline_busy": _pipeline_lock.locked(),
        "model": model_control.model_status(),
    }


@app.get("/v1/model")
def model_get():
    from pipeline import model_control

    return model_control.model_status()


@app.post("/v1/model/stop")
def model_stop():
    from pipeline import model_control

    return model_control.stop_model()


@app.post("/v1/model/start")
def model_start():
    from pipeline import model_control

    return model_control.start_model()


@app.post("/v1/jobs")
async def create_job(
    file: UploadFile = File(...),
    use_marker: str = Form("0"),
    title: str = Form(""),
):
    """Push mode: Ubuntu uploads PDF; agent runs stop→OCR→validate→start."""
    job_id = uuid.uuid4().hex
    work = _job_dir(job_id)
    src = work / (file.filename or "book.pdf")
    src.write_bytes(await file.read())
    use_m = use_marker.strip().lower() in ("1", "true", "yes", "on")
    _set_job(
        job_id,
        status="pending",
        percent=0.0,
        message="queued",
        source_pdf=str(src),
        use_marker=use_m,
        title=title or src.stem,
    )
    threading.Thread(
        target=_run_pipeline,
        args=(job_id, src, use_m),
        daemon=True,
        name=f"ocr-push-{job_id[:8]}",
    ).start()
    return {"job_id": job_id, "status": "pending", "mode": "push"}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str):
    with _lock:
        j = _jobs.get(job_id)
    if j is None:
        sf = _job_dir(job_id) / "status.json"
        if sf.is_file():
            return json.loads(sf.read_text(encoding="utf-8"))
        raise HTTPException(404, f"job not found: {job_id}")
    return j


@app.get("/v1/jobs/{job_id}/pdf")
def get_job_pdf(job_id: str):
    pdf = _job_dir(job_id) / "clean_text.pdf"
    if not pdf.is_file():
        alt = _job_dir(job_id) / "work" / "clean_text.pdf"
        if alt.is_file():
            pdf = alt
        else:
            raise HTTPException(404, "clean PDF not ready")
    return FileResponse(str(pdf), media_type="application/pdf", filename="clean_text.pdf")


def _pull_loop() -> None:
    """Background: claim Ubuntu-queued jobs if UI used queue fallback."""
    print(f"[pull] enabled — polling {API}/ocr/agent/claim", flush=True)
    while True:
        try:
            r = httpx.get(f"{API}/ocr/agent/claim", headers=HEADERS, timeout=30.0)
            if r.status_code == 401:
                time.sleep(15)
                continue
            r.raise_for_status()
            job = (r.json() or {}).get("job")
            if not job:
                time.sleep(3)
                continue
            jid = job["job_id"]
            print(f"[pull] claimed {jid[:8]}", flush=True)
            work = _job_dir(jid)
            src = work / "source.pdf"
            httpx.post(
                f"{API}/ocr/agent/jobs/{jid}/progress",
                headers=HEADERS,
                json={"percent": 2, "message": "Downloading source", "status": "running"},
                timeout=30,
            )
            with httpx.Client(timeout=600.0) as client:
                sr = client.get(f"{API}/ocr/agent/jobs/{jid}/source", headers=HEADERS)
                sr.raise_for_status()
                src.write_bytes(sr.content)

            def progress(pct: float, msg: str = "") -> None:
                try:
                    httpx.post(
                        f"{API}/ocr/agent/jobs/{jid}/progress",
                        headers=HEADERS,
                        json={
                            "percent": min(95.0, float(pct) * 0.95),
                            "message": msg or "OCR",
                            "status": "running",
                        },
                        timeout=30,
                    )
                except Exception:  # noqa: BLE001
                    pass

            from pipeline.hybrid_ocr import run_hybrid_pipeline

            result = run_hybrid_pipeline(
                src,
                work / "work",
                use_marker=bool(job.get("use_marker")),
                progress=progress,
                restart_model=True,
            )
            clean = Path(result["clean_pdf"])
            with open(clean, "rb") as fh:
                up = httpx.post(
                    f"{API}/ocr/agent/jobs/{jid}/result",
                    headers=HEADERS,
                    files={"file": ("clean_text.pdf", fh, "application/pdf")},
                    timeout=600.0,
                )
                up.raise_for_status()
            print(f"[pull] done {jid[:8]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[pull] error: {exc}", flush=True)
            time.sleep(5)


def _try_open_firewall() -> None:
    """Best-effort allow :8090 (works if process is elevated)."""
    import subprocess

    try:
        subprocess.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                "name=MedRack OCR Agent 8090",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                "localport=8090",
            ],
            capture_output=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    _try_open_firewall()
    if ENABLE_PULL:
        threading.Thread(target=_pull_loop, daemon=True, name="ocr-pull").start()
    print("MedRack OCR Agent on 0.0.0.0:8090 (push + pull)", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="info")


if __name__ == "__main__":
    main()
