"""LogService — Access to backend logs (Phase 12).

The :class:`LogService` is the stable interface for reading the
ingestion, generation, validation, and benchmark logs.

The service is read-only; it never mutates log files.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


class LogService:
    """Service for reading backend logs."""

    SCHEMA_VERSION = 1

    def __init__(self, medrack_home: Optional[Path] = None) -> None:
        from medrack.config import get_medrack_home
        if medrack_home is None:
            self._home = get_medrack_home()
        else:
            self._home = Path(medrack_home)

    def tail(self, log_name: str, n: int = 100) -> List[Dict[str, Any]]:
        """Return the last N entries from a log file.

        log_name: ``"ingestion"``, ``"generation"``,
        ``"validation"``, or ``"benchmark"``.
        """
        # Map log_name to a path
        path = self._home / "logs" / f"{log_name}.jsonl"
        if not path.exists():
            return []
        # Read the last N lines
        try:
            with path.open() as f:
                # Read all and slice (simple; ok for small logs)
                lines = f.readlines()
        except Exception:
            return []
        recent = lines[-n:]
        out: List[Dict[str, Any]] = []
        for line in recent:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # Non-JSON line: return as raw
                out.append({"raw": line})
        return out

    def search(
        self,
        log_name: str,
        query: str,
        n: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search a log file for entries containing the query string."""
        entries = self.tail(log_name, n=10_000)  # search across more
        return [e for e in entries if query in json.dumps(e)]


__all__ = ["LogService"]
