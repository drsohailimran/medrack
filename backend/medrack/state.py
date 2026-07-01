"""medrack.state — preview & batch state machine.

Extracted from ``medrack.cli`` so that ``medrack.bot`` and
``medrack.dashboard`` can import state helpers without depending on
CLI-private functions (``cli._load_preview_state``, etc.).

Public API:
    load_preview_state()    — read preview_state.json (or None)
    save_preview_state(data) — atomic write to preview_state.json
    clear_preview_state()   — delete preview_state.json
    append_revision(record) — append to revisions.json
    get_llm_client()        — return LLMClient or MockLLMClient
    atomic_write_json(path, data) — general-purpose atomic JSON writer

Design notes:
- All paths are re-evaluated per call via ``config.get_medrack_home()``
  so ``$MEDRACK_HOME`` overrides work in tests (mirrors the pattern in
  ``medrack.ingest.manifest``).
- ``atomic_write_json`` writes to a sibling ``.tmp`` file first, then
  renames via ``Path.replace()`` (POSIX-atomic on the same filesystem).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from medrack import config


def _state_path() -> Path:
    """Return the path to the preview state JSON file (parent dir created)."""
    p = config.get_medrack_home() / "state" / "preview_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _revisions_path() -> Path:
    """Return the path to the revisions log JSON file (parent dir created)."""
    p = config.get_medrack_home() / "state" / "revisions.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write_json(path: Path, data) -> None:
    """Write ``data`` to ``path`` atomically (tmp + replace)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False))
    tmp.replace(path)


def load_preview_state() -> dict | None:
    """Load the preview state file, or ``None`` if missing."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # Treat a corrupt state file as "no preview" — safer than crashing
        # the user-facing CLI.
        return None


def save_preview_state(data: dict) -> None:
    """Atomically write the preview state."""
    atomic_write_json(_state_path(), data)


def clear_preview_state() -> None:
    """Delete the preview state file if it exists. Silent no-op otherwise."""
    path = _state_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def append_revision(record: dict) -> None:
    """Append a revision record to revisions.json (atomic, list-of-dicts)."""
    path = _revisions_path()
    if path.exists():
        try:
            current = json.loads(path.read_text())
        except json.JSONDecodeError:
            current = []
    else:
        current = []
    if not isinstance(current, list):
        current = []
    current.append(record)
    atomic_write_json(path, current)


def get_llm_client():
    """Return an LLM client honouring the ``$MEDRACK_LLM_MODE`` env var.

    - ``mock`` (or any value starting with ``mock``) → :class:`MockLLMClient`
      (deterministic, no network — used by the end-to-end tests and the
      Stage 2.5 B3 integration test that exercises the full
      ingest → preview → approve → PDF flow without an API key).
    - ``real`` or unset → :class:`LLMClient` (default production path).

    Return type is intentionally un-annotated (``object``) because
    ``MockLLMClient`` is a structural stand-in (same ``complete()``
    surface) rather than a subclass of ``LLMClient``; down-stream
    callers are duck-typed.
    """
    mode = os.environ.get("MEDRACK_LLM_MODE", "real").lower()
    if mode == "mock":
        from medrack.answer.llm import MockLLMClient
        return MockLLMClient()
    from medrack.answer.llm import LLMClient
    return LLMClient()


__all__ = [
    "load_preview_state",
    "save_preview_state",
    "clear_preview_state",
    "append_revision",
    "get_llm_client",
    "atomic_write_json",
]
