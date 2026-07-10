"""Start/stop Qwopus llama-server for MedRack OCR windows (free GPU + RAM).

Qwopus runs as an *elevated* Scheduled Task (RunLevel Highest / mlock).
A normal taskkill from a non-elevated agent gets **Access is denied**.

Stop sequence (required order):
  1. Write ``qwopus.stop`` so the bat watchdog will NOT restart
  2. ``schtasks /End`` on ``MedRack Qwopus Server`` (elevated tree kill)
  3. Best-effort taskkill fallback
  4. Wait until process is gone AND free RAM / GPU look free
  5. Return ok=True only then — OCR must not start otherwise
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

STOP_FLAG = Path(r"C:\ai models\qwopus.stop")
MODEL_TASK = "MedRack Qwopus Server"
LLAMA_NAME = "llama-server"


def _run(cmd: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )


def _llama_running() -> bool:
    try:
        r = _run(["tasklist", "/FI", f"IMAGENAME eq {LLAMA_NAME}.exe"], timeout=15)
        out = (r.stdout or "").lower()
        # tasklist prints the image name even in "INFO: No tasks" locale variants;
        # require a CSV/list line that looks like a real process hit.
        if f"{LLAMA_NAME}.exe" not in out:
            return False
        if "no tasks" in out or "no session" in out:
            return False
        return True
    except Exception:  # noqa: BLE001
        return False


def _llama_pids() -> List[int]:
    pids: List[int] = []
    try:
        r = _run(
            [
                "tasklist",
                "/FI",
                f"IMAGENAME eq {LLAMA_NAME}.exe",
                "/FO",
                "CSV",
                "/NH",
            ],
            timeout=15,
        )
        for line in (r.stdout or "").splitlines():
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) >= 2 and parts[0].lower().startswith("llama-server"):
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    pass
    except Exception:  # noqa: BLE001
        pass
    return pids


def _free_ram_mb() -> Optional[float]:
    try:
        r = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory",
            ],
            timeout=20,
        )
        raw = (r.stdout or "").strip().splitlines()
        if not raw:
            return None
        # FreePhysicalMemory is KB
        return float(raw[-1].strip()) / 1024.0
    except Exception:  # noqa: BLE001
        return None


def _gpu_memory() -> Dict[str, Any]:
    out: Dict[str, Any] = {"available": False}
    try:
        r = _run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ],
            timeout=15,
        )
        line = (r.stdout or "").strip().splitlines()
        if not line:
            return out
        parts = [p.strip() for p in line[0].split(",")]
        if len(parts) >= 3:
            out = {
                "available": True,
                "used_mib": float(parts[0]),
                "free_mib": float(parts[1]),
                "total_mib": float(parts[2]),
            }
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def _write_stop_flag() -> Optional[str]:
    try:
        STOP_FLAG.parent.mkdir(parents=True, exist_ok=True)
        STOP_FLAG.write_text("stop\n", encoding="utf-8")
        return None
    except OSError as exc:
        return str(exc)


def _kill_llama_elevated() -> Dict[str, Any]:
    """Stop elevated Qwopus using scheduled-task End + taskkill fallback."""
    info: Dict[str, Any] = {
        "pids_before": _llama_pids(),
        "schtasks_end": None,
        "taskkill": None,
    }

    # 1) End the elevated Scheduled Task (kills bat + children when possible)
    try:
        r = _run(["schtasks", "/End", "/TN", MODEL_TASK], timeout=30)
        info["schtasks_end"] = {
            "returncode": r.returncode,
            "stdout": (r.stdout or "").strip()[:400],
            "stderr": (r.stderr or "").strip()[:400],
        }
    except Exception as exc:  # noqa: BLE001
        info["schtasks_end_error"] = str(exc)

    time.sleep(0.5)

    # 2) taskkill (works if agent shares elevation; may Access Denied otherwise)
    try:
        r = _run(
            ["taskkill", "/F", "/T", "/IM", f"{LLAMA_NAME}.exe"],
            timeout=30,
        )
        info["taskkill"] = {
            "returncode": r.returncode,
            "stdout": (r.stdout or "").strip()[:500],
            "stderr": (r.stderr or "").strip()[:500],
        }
    except Exception as exc:  # noqa: BLE001
        info["taskkill_error"] = str(exc)

    # 3) Per-PID taskkill
    for pid in list(info["pids_before"] or []) + _llama_pids():
        try:
            _run(["taskkill", "/F", "/T", "/PID", str(pid)], timeout=15)
        except Exception:  # noqa: BLE001
            pass

    # 4) wmic fallback (sometimes works when taskkill UAC-blocks)
    try:
        r = _run(
            [
                "wmic",
                "process",
                "where",
                f"name='{LLAMA_NAME}.exe'",
                "call",
                "terminate",
            ],
            timeout=30,
        )
        info["wmic"] = {
            "returncode": r.returncode,
            "stdout": (r.stdout or "").strip()[:300],
            "stderr": (r.stderr or "").strip()[:300],
        }
    except Exception as exc:  # noqa: BLE001
        info["wmic_error"] = str(exc)

    info["pids_after_kill"] = _llama_pids()
    return info


def stop_model(
    timeout_sec: float = 120.0,
    *,
    min_free_ram_mb: float = 4096.0,
    min_ram_gain_mb: float = 1024.0,
    min_gpu_free_mib: float = 3500.0,
) -> dict:
    """Stop Qwopus and wait until process is dead and memory is free enough for OCR.

    Returns ok=True only when llama-server is gone. Never start OCR otherwise.
    """
    err = _write_stop_flag()
    if err:
        return {"ok": False, "error": f"stop_flag: {err}", "phase": "write_flag"}

    free_before = _free_ram_mb()
    gpu_before = _gpu_memory()

    # Already down?
    if not _llama_running():
        free_now = _free_ram_mb()
        gpu_now = _gpu_memory()
        return {
            "ok": True,
            "phase": "already_stopped",
            "stop_flag": str(STOP_FLAG),
            "free_ram_mb_before": free_before,
            "free_ram_mb_after": free_now,
            "gpu_before": gpu_before,
            "gpu_after": gpu_now,
            "still_running": False,
            "kill": {"skipped": True},
        }

    kill_info = _kill_llama_elevated()
    # Hammer again a few times while waiting (watchdog races)
    deadline = time.time() + timeout_sec
    process_dead_at: Optional[float] = None
    last_free = free_before
    last_gpu = gpu_before
    phase = "wait_process"
    attempts = 1

    while time.time() < deadline:
        running = _llama_running()
        last_free = _free_ram_mb()
        last_gpu = _gpu_memory()

        if running:
            phase = "wait_process"
            # Re-assert stop flag (watchdog / start race)
            _write_stop_flag()
            if attempts % 3 == 0:
                kill_info = _kill_llama_elevated()
            attempts += 1
            time.sleep(0.8)
            continue

        if process_dead_at is None:
            process_dead_at = time.time()
            phase = "wait_memory"

        # Settle: mlock pages return to the OS after process exit
        if time.time() - process_dead_at < 2.5:
            time.sleep(0.4)
            continue

        # Re-check process — watchdog must not have restarted
        if _llama_running():
            process_dead_at = None
            phase = "wait_process"
            _write_stop_flag()
            kill_info = _kill_llama_elevated()
            continue

        ram_ok = False
        if last_free is not None:
            gain = (last_free - free_before) if free_before is not None else 0.0
            ram_ok = (last_free >= min_free_ram_mb) or (gain >= min_ram_gain_mb)
            if free_before is not None and free_before >= min_free_ram_mb:
                if last_free >= min_free_ram_mb * 0.85:
                    ram_ok = True
        else:
            ram_ok = (time.time() - process_dead_at) >= 5.0

        gpu_ok = True
        if last_gpu.get("available"):
            free_mib = float(last_gpu.get("free_mib") or 0)
            used_mib = float(last_gpu.get("used_mib") or 0)
            gpu_ok = free_mib >= min_gpu_free_mib or used_mib <= 1500

        if ram_ok and gpu_ok and not _llama_running():
            return {
                "ok": True,
                "phase": "ready",
                "stop_flag": str(STOP_FLAG),
                "kill": kill_info,
                "free_ram_mb_before": free_before,
                "free_ram_mb_after": last_free,
                "gpu_before": gpu_before,
                "gpu_after": last_gpu,
                "waited_sec": round(time.time() - (deadline - timeout_sec), 1),
                "still_running": False,
                "attempts": attempts,
            }

        time.sleep(0.6)

    still = _llama_running()
    deny = ""
    tk = (kill_info or {}).get("taskkill") or {}
    if "denied" in (tk.get("stderr") or "").lower():
        deny = " (Access denied killing elevated llama — schtasks /End used; if still running, end 'MedRack Qwopus Server' in Task Scheduler)"
    return {
        "ok": False,
        "error": (
            "Qwopus did not fully stop for OCR: "
            + ("llama-server STILL RUNNING; " if still else "memory not freed; ")
            + f"free_ram_mb={last_free}, gpu={last_gpu}."
            + deny
            + " Free RAM/VRAM and retry hybrid ingest."
        ),
        "phase": phase,
        "stop_flag": str(STOP_FLAG),
        "kill": kill_info,
        "free_ram_mb_before": free_before,
        "free_ram_mb_after": last_free,
        "gpu_before": gpu_before,
        "gpu_after": last_gpu,
        "still_running": still,
        "pids": _llama_pids(),
    }


def assert_ready_for_ocr() -> dict:
    """Final gate immediately before loading OCR models."""
    if _llama_running():
        info = stop_model(timeout_sec=90.0)
        if not info.get("ok") or _llama_running():
            raise RuntimeError(
                info.get("error")
                or "llama-server still running — cannot start OCR (would crash the PC)"
            )
        return info
    free = _free_ram_mb()
    gpu = _gpu_memory()
    if free is not None and free < 2048:
        raise RuntimeError(
            f"Only {free:.0f} MiB free RAM — too low for large-book OCR. "
            "Ensure Qwopus fully exited, then retry."
        )
    return {
        "ok": True,
        "free_ram_mb": free,
        "gpu": gpu,
        "llama_running": False,
    }


def start_model() -> dict:
    """Clear stop flag and launch Qwopus via Scheduled Task (elevated)."""
    try:
        if STOP_FLAG.exists():
            STOP_FLAG.unlink()
    except OSError:
        pass

    r = _run(["schtasks", "/Run", "/TN", MODEL_TASK], timeout=30)
    if r.returncode == 0:
        return {
            "ok": True,
            "method": "schtasks",
            "task": MODEL_TASK,
            "stdout": (r.stdout or "").strip(),
        }

    bat = Path(r"C:\ai models\run-qwopus-medrack.bat")
    if bat.is_file():
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(bat)],
            cwd=str(bat.parent),
            shell=False,
        )
        return {
            "ok": True,
            "method": "bat",
            "path": str(bat),
            "schtasks_error": (r.stderr or "").strip(),
        }

    return {
        "ok": False,
        "error": f"schtasks failed ({(r.stderr or '').strip()}) and bat missing",
    }


def model_status() -> dict:
    return {
        "llama_running": _llama_running(),
        "stop_flag_present": STOP_FLAG.exists(),
        "pids": _llama_pids(),
        "free_ram_mb": _free_ram_mb(),
        "gpu": _gpu_memory(),
    }
