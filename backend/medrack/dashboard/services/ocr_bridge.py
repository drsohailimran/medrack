"""P1 OCR bridge — Ubuntu-side job files for Windows pull-mode agent.

Windows home LANs often block inbound ports to the PC. Instead of Ubuntu
pushing PDFs to Windows:8090, the Windows agent **polls** Ubuntu and pulls
work. Shared secret: env ``MEDRACK_OCR_AGENT_TOKEN`` (default medrack-ocr).
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from medrack.config import get_medrack_home


def _token() -> str:
    return os.environ.get("MEDRACK_OCR_AGENT_TOKEN", "medrack-ocr")


def check_token(provided: Optional[str]) -> bool:
    return bool(provided) and provided == _token()


def ocr_jobs_root() -> Path:
    root = get_medrack_home() / "ocr_jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_ocr_job(
    *,
    source_pdf: Path,
    title: str,
    subject: str,
    use_marker: bool = False,
) -> str:
    job_id = uuid.uuid4().hex
    d = ocr_jobs_root() / job_id
    d.mkdir(parents=True, exist_ok=True)
    dest = d / "source.pdf"
    shutil.copy2(source_pdf, dest)
    meta = {
        "job_id": job_id,
        "status": "queued",  # queued | claimed | running | done | error
        "percent": 0.0,
        "message": "queued for Windows OCR agent",
        "title": title,
        "subject": subject,
        "use_marker": use_marker,
        "created_at": time.time(),
        "updated_at": time.time(),
        "error": None,
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return job_id


def _meta_path(job_id: str) -> Path:
    return ocr_jobs_root() / job_id / "meta.json"


def load_meta(job_id: str) -> Optional[Dict[str, Any]]:
    p = _meta_path(job_id)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_meta(job_id: str, meta: Dict[str, Any]) -> None:
    meta["updated_at"] = time.time()
    _meta_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def list_queued() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in sorted(ocr_jobs_root().iterdir()):
        if not d.is_dir():
            continue
        m = load_meta(d.name)
        if m and m.get("status") == "queued":
            out.append(m)
    return out


def claim_next() -> Optional[Dict[str, Any]]:
    for m in list_queued():
        jid = m["job_id"]
        m["status"] = "claimed"
        m["message"] = "claimed by Windows agent"
        m["percent"] = 1.0
        save_meta(jid, m)
        return m
    return None


def source_path(job_id: str) -> Optional[Path]:
    p = ocr_jobs_root() / job_id / "source.pdf"
    return p if p.is_file() else None


def result_path(job_id: str) -> Optional[Path]:
    p = ocr_jobs_root() / job_id / "clean_text.pdf"
    return p if p.is_file() else None


def update_progress(job_id: str, percent: float, message: str, status: str = "running") -> None:
    m = load_meta(job_id)
    if not m:
        raise FileNotFoundError(job_id)
    m["status"] = status
    m["percent"] = float(percent)
    m["message"] = message
    save_meta(job_id, m)


def mark_done(job_id: str, clean_pdf: Path) -> None:
    dest = ocr_jobs_root() / job_id / "clean_text.pdf"
    if Path(clean_pdf).resolve() != dest.resolve():
        shutil.copy2(clean_pdf, dest)
    m = load_meta(job_id) or {"job_id": job_id}
    m["status"] = "done"
    m["percent"] = 100.0
    m["message"] = "OCR complete"
    m["error"] = None
    save_meta(job_id, m)


def mark_error(job_id: str, error: str) -> None:
    m = load_meta(job_id) or {"job_id": job_id}
    m["status"] = "error"
    m["error"] = error
    m["message"] = "error"
    save_meta(job_id, m)
