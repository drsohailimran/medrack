"""Tests for medrack.cli preview."""
import os
import subprocess

MEDRACK_BIN = "/home/sohail/.hermes/hermes-agent/venv/bin/medrack"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, r.stdout, r.stderr


def test_preview_nonexistent_module_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, _ = run([MEDRACK_BIN, "preview", "nonexistent",
                    "--chapter", "1"], env=env)
    assert rc != 0


def test_preview_invalid_chapter_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, _ = run([MEDRACK_BIN, "preview", "x", "--chapter", "abc"], env=env)
    assert rc != 0


def test_approve_without_preview_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, _ = run([MEDRACK_BIN, "approve"], env=env)
    assert rc != 0


def test_revise_without_preview_exits_nonzero(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, _ = run([MEDRACK_BIN, "revise", "wordcount", "1500"], env=env)
    assert rc != 0


def test_cancel_always_succeeds(tmp_path):
    env = {**os.environ, "MEDRACK_HOME": str(tmp_path)}
    rc, _, _ = run([MEDRACK_BIN, "cancel"], env=env)
    assert rc == 0


def test_preview_help_shows_options():
    rc, out, _ = run([MEDRACK_BIN, "preview", "--help"])
    assert rc == 0
    assert "--chapter" in out
    assert "--reanswer" in out
