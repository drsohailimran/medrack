"""Tests for medrack.cli — the `medrack` command entry point."""
import subprocess
import sys
from pathlib import Path

import pytest

from medrack.cli import build_parser, main


def test_parser_has_expected_subcommands():
    parser = build_parser()
    # Verify each subcommand is registered
    for cmd in ["init", "status", "version"]:
        # This will raise if not present
        try:
            args = parser.parse_args([cmd])
            assert args.command == cmd
        except SystemExit:
            pytest.fail(f"subcommand {cmd!r} not registered")


def test_version_command(capsys):
    import medrack
    rc = main(["version"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "medrack" in captured.out
    # Assert against the single source of truth (medrack.__version__) so the
    # test does not drift when the package version is bumped.
    assert medrack.__version__ in captured.out


def test_status_command_runs(capsys):
    """status should not crash even with no data."""
    rc = main(["status"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "medrack" in captured.out
    assert "Dependencies" in captured.out
