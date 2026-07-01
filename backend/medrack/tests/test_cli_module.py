"""Tests for medrack.cli ingest-module."""
import os
import subprocess

import sys as _sys
from pathlib import Path as _Path

# Resolve the installed `medrack` console script next to the active
# interpreter so these CLI tests run on any machine, not just the author's.
MEDRACK_BIN = str(_Path(_sys.executable).parent / ("medrack.exe" if os.name == "nt" else "medrack"))
MODULE_PDF = "/home/sohail/medrack-samples/modules/MODULE 1-1.pdf"
SCAN_PDF = "/home/sohail/medrack-samples/modules/solved_singi_fmt_260331_204237_260618_174727.pdf"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, r.stdout, r.stderr


def test_ingest_module_nonexistent_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, _ = run([MEDRACK_BIN, "ingest-module", "/nonexistent.pdf",
                    "--subject", "psm", "--name", "x"], env=env)
    assert rc != 0


def test_ingest_module_invalid_subject_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, _ = run([MEDRACK_BIN, "ingest-module", MODULE_PDF,
                    "--subject", "biology", "--name", "x"], env=env)
    assert rc != 0


def test_ingest_module_psm_succeeds(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, out, err = run([MEDRACK_BIN, "ingest-module", MODULE_PDF,
                        "--subject", "psm", "--name", "psm-module-1"], env=env)
    assert rc == 0, f"ingest-module failed: {err}"
    # Output should mention questions
    assert "questions" in out.lower()

    # extracted.json should exist
    extracted = tmp_path / "modules" / "psm" / "psm-module-1" / "extracted.json"
    assert extracted.is_file()
    import json
    data = json.loads(extracted.read_text())
    assert data["metadata"]["subject"] == "psm"
    assert data["metadata"]["format"] == "mcq"
    assert len(data["questions"]) >= 10
    # First question is the WHO health definition
    assert any("health" in q["question_text"].lower() for q in data["questions"])


def test_ingest_module_explicit_theory_format(tmp_path):
    """Forcing --format theory should still succeed (just no MCQ options expected)."""
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, out, _ = run([MEDRACK_BIN, "ingest-module", MODULE_PDF,
                      "--subject", "psm", "--name", "psm-mod-theory",
                      "--format", "theory"], env=env)
    assert rc == 0
    extracted = tmp_path / "modules" / "psm" / "psm-mod-theory" / "extracted.json"
    import json
    data = json.loads(extracted.read_text())
    assert data["metadata"]["format"] == "theory"
