"""Tests for the bot CLI command."""
import subprocess

MEDRACK_BIN = "/home/sohail/.hermes/hermes-agent/venv/bin/medrack"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, r.stdout, r.stderr


def test_bot_help_exits_0():
    rc, _, _ = run([MEDRACK_BIN, "bot", "--help"], timeout=15)
    assert rc == 0


def test_bot_subcommand_registered():
    rc, out, _ = run([MEDRACK_BIN, "--help"], timeout=15)
    assert "bot" in out


def test_bot_without_token_exits_nonzero():
    import os
    env = {k: v for k, v in os.environ.items() if k != "TELEGRAM_BOT_TOKEN"}
    rc, _, _ = run([MEDRACK_BIN, "bot"], env=env, timeout=10)
    assert rc != 0
