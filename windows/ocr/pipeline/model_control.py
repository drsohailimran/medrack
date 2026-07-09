"""Start/stop Qwopus llama-server for MedRack OCR windows (free the GPU)."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

# Match launcher + run-qwopus-medrack.bat
STOP_FLAG = Path(r"C:\ai models\qwopus.stop")
MODEL_TASK = "MedRack Qwopus Server"
LLAMA_NAME = "llama-server"


def stop_model(timeout_sec: float = 30.0) -> dict:
    """Drop stop flag and kill llama-server so OCR can use the GPU."""
    try:
        STOP_FLAG.parent.mkdir(parents=True, exist_ok=True)
        STOP_FLAG.write_text("stop\n", encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": f"stop_flag: {exc}"}

    killed = 0
    try:
        # taskkill is reliable on Windows even if Process API is restricted
        r = subprocess.run(
            ["taskkill", "/F", "/IM", f"{LLAMA_NAME}.exe"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            killed = 1
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "stop_flag": str(STOP_FLAG)}

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not _llama_running():
            break
        time.sleep(0.5)

    return {
        "ok": not _llama_running(),
        "killed": killed,
        "stop_flag": str(STOP_FLAG),
        "still_running": _llama_running(),
    }


def start_model() -> dict:
    """Clear stop flag and launch Qwopus via Scheduled Task (elevated)."""
    try:
        if STOP_FLAG.exists():
            STOP_FLAG.unlink()
    except OSError:
        pass

    # Prefer the elevated Scheduled Task used by Start MedRack
    r = subprocess.run(
        ["schtasks", "/Run", "/TN", MODEL_TASK],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode == 0:
        return {"ok": True, "method": "schtasks", "task": MODEL_TASK, "stdout": r.stdout.strip()}

    # Fallback: start the bat non-elevated (may lack mlock)
    bat = Path(r"C:\ai models\run-qwopus-medrack.bat")
    if bat.is_file():
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(bat)],
            cwd=str(bat.parent),
            shell=False,
        )
        return {"ok": True, "method": "bat", "path": str(bat), "schtasks_error": r.stderr.strip()}

    return {
        "ok": False,
        "error": f"schtasks failed ({r.stderr.strip()}) and bat missing",
    }


def model_status() -> dict:
    return {
        "llama_running": _llama_running(),
        "stop_flag_present": STOP_FLAG.exists(),
    }


def _llama_running() -> bool:
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {LLAMA_NAME}.exe"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return f"{LLAMA_NAME}.exe".lower() in (r.stdout or "").lower()
    except Exception:  # noqa: BLE001
        return False
