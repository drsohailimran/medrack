"""Tests for the bot CLI command."""
import subprocess

import os as _os
import sys as _sys
from pathlib import Path as _Path

# Resolve the installed `medrack` console script next to the active
# interpreter so these CLI tests run on any machine, not just the author's.
MEDRACK_BIN = str(_Path(_sys.executable).parent / ("medrack.exe" if _os.name == "nt" else "medrack"))


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
    env = {k: v for k, v in os.environ.items() if k != "MEDRACK_TELEGRAM_BOT_TOKEN"}
    rc, _, _ = run([MEDRACK_BIN, "bot"], env=env, timeout=10)
    assert rc != 0
