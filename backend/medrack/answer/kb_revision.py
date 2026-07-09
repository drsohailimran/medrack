"""Per-subject knowledge-base revision stamps (P0 stale-on-reindex).

When a textbook for a subject is ingested/re-indexed, the revision for
that subject is bumped. Cached answers record the revision they were
generated against; ``versioning.is_stale`` flags a mismatch so the
orchestrator regenerates instead of serving outdated grounding.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from medrack import config

logger = logging.getLogger(__name__)

REASON_KB_REINDEXED = "kb_reindexed"


def _state_path() -> Path:
    p = config.get_medrack_home() / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p / "kb_revisions.json"


def _load() -> dict[str, int]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read kb_revisions.json: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in data.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def _save(data: dict[str, int]) -> None:
    path = _state_path()
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def get_kb_revision(subject: str) -> int:
    """Return the current KB revision for ``subject`` (0 if never bumped)."""
    return int(_load().get(subject, 0))


def bump_kb_revision(subject: str) -> int:
    """Increment and persist the KB revision for ``subject``. Return new value."""
    data = _load()
    new_val = int(data.get(subject, 0)) + 1
    data[subject] = new_val
    _save(data)
    logger.info("Bumped kb_revision for subject=%s to %s", subject, new_val)
    return new_val


def all_kb_revisions() -> dict[str, int]:
    """Return a copy of all subject → revision mappings."""
    return dict(_load())


__all__ = [
    "REASON_KB_REINDEXED",
    "get_kb_revision",
    "bump_kb_revision",
    "all_kb_revisions",
]
