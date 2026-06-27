"""Tests for the dashboard CLI command."""
import subprocess

MEDRACK_BIN = "/home/sohail/.hermes/hermes-agent/venv/bin/medrack"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, r.stdout, r.stderr


def test_dashboard_help_exits_0():
    rc, out, _ = run([MEDRACK_BIN, "dashboard", "--help"], timeout=15)
    assert rc == 0
    assert "dashboard" in out.lower()


def test_dashboard_subcommand_registered():
    rc, out, _ = run([MEDRACK_BIN, "--help"], timeout=15)
    assert "dashboard" in out
