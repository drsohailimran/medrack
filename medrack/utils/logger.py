"""
medrack.utils.logger — centralised logging for ingest pipeline.

Provides get_logger(name) returning a configured logger that writes to
~/.hermes/medrack/logs/ingest.log AND stderr.

Format: %(asctime)s [%(levelname)s] %(name)s: %(message)s

Loggers are cached: calling get_logger("foo") twice returns the same instance.
Stderr handler is attached only once (idempotent across re-imports).
Stdlib-only — no extra deps.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Where the ingest log lives. Honour MEDRACK_HOME so tests / dev can override.
_LOG_DIR: Path = Path(
    os.environ.get("MEDRACK_HOME", str(Path.home() / ".hermes" / "medrack"))
) / "logs"
_LOG_FILE: Path = _LOG_DIR / "ingest.log"

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Module-level flag so the stderr handler is attached at most once even if
# multiple callers race to initialise the first logger.
_stderr_handler_attached = False


def _ensure_log_dir() -> Path:
    """Create the log directory if missing. Returns the directory path."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def _attach_stderr_handler() -> None:
    """Attach a single stderr StreamHandler to the root logger (idempotent)."""
    global _stderr_handler_attached
    if _stderr_handler_attached:
        return
    root = logging.getLogger()
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    # Avoid duplicating stderr output when the root already has a stderr handler.
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
        for h in root.handlers
    ):
        root.addHandler(handler)
    _stderr_handler_attached = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger named `name` with file + stderr handlers configured.

    The file handler writes to ~/.hermes/medrack/logs/ingest.log; the
    stderr handler writes to sys.stderr. Both use the format
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s".

    Loggers are cached by name (standard logging behaviour), so repeated
    calls with the same name return the same Logger instance. The file
    handler is attached only on the first call per process to avoid
    duplicate log lines.
    """
    _ensure_log_dir()
    _attach_stderr_handler()

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Attach a file handler only if this logger doesn't already have one
    # pointing at our ingest.log. (We check the resolved path so we don't
    # double-attach on repeat calls.)
    has_file_handler = any(
        isinstance(h, logging.FileHandler)
        and Path(getattr(h, "baseFilename", "")).resolve() == _LOG_FILE.resolve()
        for h in logger.handlers
    )
    if not has_file_handler:
        file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(file_handler)

    # Don't propagate: root already gets stderr via _attach_stderr_handler.
    # If we let propagate=True, every log line appears twice on stderr.
    logger.propagate = False
    return logger


__all__ = ["get_logger"]
