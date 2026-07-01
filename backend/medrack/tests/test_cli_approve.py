"""Tests for medrack.cli approve (full batch flow)."""
import os
import subprocess

import sys as _sys
from pathlib import Path as _Path

# Resolve the installed `medrack` console script next to the active
# interpreter so these CLI tests run on any machine, not just the author's.
MEDRACK_BIN = str(_Path(_sys.executable).parent / ("medrack.exe" if os.name == "nt" else "medrack"))


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, r.stdout, r.stderr


def test_approve_without_preview_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path),
           "MEDRACK_LLM_MODE": "mock"}
    rc, _, _ = run([MEDRACK_BIN, "approve"], env=env, timeout=60)
    assert rc != 0


def test_approve_with_mock_llm_generates_full_pdf(tmp_path):
    """Full batch flow: ingest a module, preview, approve, get full PDF."""
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path),
           "MEDRACK_LLM_MODE": "mock"}
    # init
    run([MEDRACK_BIN, "init"], env=env, timeout=15)
    # ingest the test module (3 questions, already in the chunks dir)
    run([MEDRACK_BIN, "ingest-module",
         "/home/sohail/medrack-samples/modules/MODULE 1-1.pdf",
         "--subject", "psm", "--name", "psm-module-1"],
        env=env, timeout=60)
    # preview the first question
    rc, out, _ = run([MEDRACK_BIN, "preview", "psm-module-1", "--chapter", "all"],
                     env=env, timeout=60)
    assert rc == 0
    # approve
    rc, out, _ = run([MEDRACK_BIN, "approve"], env=env, timeout=120)
    assert rc == 0
    # The full PDF should exist in output/<module>/
    output_dir = tmp_path / "output" / "psm-module-1"
    pdfs = list(output_dir.glob("*_full.pdf"))
    assert len(pdfs) == 1
    # The PDF should be non-empty
    assert pdfs[0].stat().st_size > 1000  # at least 1KB


def test_approve_saves_batch_state(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path),
           "MEDRACK_LLM_MODE": "mock"}
    run([MEDRACK_BIN, "init"], env=env, timeout=15)
    run([MEDRACK_BIN, "ingest-module",
         "/home/sohail/medrack-samples/modules/MODULE 1-1.pdf",
         "--subject", "psm", "--name", "psm-module-1"],
        env=env, timeout=60)
    run([MEDRACK_BIN, "preview", "psm-module-1", "--chapter", "all"],
        env=env, timeout=60)
    run([MEDRACK_BIN, "approve"], env=env, timeout=120)
    state_file = tmp_path / "state" / "batch_state.json"
    assert state_file.is_file()
    import json
    state = json.loads(state_file.read_text())
    assert state["module"] == "psm-module-1"
    assert state["subject"] == "psm"
    assert state["questions_total"] > 0
