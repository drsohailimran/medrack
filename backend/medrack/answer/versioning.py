"""medrack.answer.versioning — answer cache staleness checks.

This module owns the *layered answer versioning* layer introduced in
Phase 3 (directive v1.0). A cached answer records the per-component
versions it was generated with; on load, we compare against the
current versions in ``medrack.config.PIPELINE_VERSIONS`` and mark the
answer stale if anything has changed.

The cache file is NEVER deleted by the version check — the operator's
directive is explicit:

    "Never permanently invalidate cached answers solely because prompt
     templates, word counts or schema evolve. Mark the answer as
     stale instead of deleting it. Support both selective regeneration
     and batch regeneration."

Public API:
    is_stale(cached_answer)         -> tuple[bool, list[str]]
    mark_stale(cached_answer)       -> dict  (returns the answer with
                                              stale=True and
                                              stale_reasons=[...])
    find_stale_answers(module=None) -> list[dict]  (each dict: module,
                                              chapter, qid, reasons)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from medrack import config

logger = logging.getLogger(__name__)


# Staleness reasons (string constants for stable serialisation)
REASON_SCHEMA_DRIFT = "schema_version_drift"
REASON_PROMPT_DRIFT = "prompt_version_drift"
REASON_RETRIEVAL_DRIFT = "retrieval_version_drift"
REASON_RENDERER_DRIFT = "renderer_version_drift"
REASON_PLANNER_DRIFT = "planner_version_drift"
REASON_VALIDATOR_DRIFT = "validator_version_drift"
REASON_RERANKER_DRIFT = "reranker_version_drift"
REASON_WORD_COUNT_DRIFT = "target_word_count_drift"
REASON_EMBEDDING_MODEL_DRIFT = "embedding_model_drift"
REASON_MISSING_VERSIONS = "missing_versions_field"
REASON_KB_REINDEXED = "kb_reindexed"


def _safe_get(d: dict, *keys: str, default: Any = None) -> Any:
    """Get a value from a nested dict, returning default if any key is missing."""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def is_stale(cached: dict) -> tuple[bool, list[str]]:
    """Return (stale, reasons) for a cached answer dict.

    Reasons is a list of stable string constants from the REASON_*
    names above. Empty list means the answer is fresh.

    The check is defensive: a cached answer with no ``versions`` field
    at all (the pre-Phase-3 schema) is treated as stale with reason
    ``missing_versions_field``. This is the case for every existing
    cached answer on disk (q022, q053, q062, etc.) — they were
    generated before the versioning layer existed.
    """
    reasons: list[str] = []

    # Missing versions field = pre-Phase-3 schema. Mark with the most
    # specific reason we can: missing_versions_field PLUS every
    # individual drift reason, so the operator sees a complete picture.
    cached_versions = cached.get("versions")
    if not isinstance(cached_versions, dict):
        reasons.append(REASON_MISSING_VERSIONS)
        # Fall through: compare each current version against the
        # implicit "unknown" (None) value so individual drifts are
        # reported even on old caches.
        for component, current in config.PIPELINE_VERSIONS.items():
            if current != 0:  # 0 means "not implemented yet"; don't flag
                reasons.append(f"{component}_version_drift")
        return (True, reasons) if reasons else (False, [])

    # Per-component version checks
    for component, current in config.PIPELINE_VERSIONS.items():
        cached_value = cached_versions.get(component)
        # If the component didn't exist when this cache was written
        # (e.g. validator is now in versions but wasn't in v1), treat
        # as drift.
        if cached_value is None:
            if current != 0:
                reasons.append(f"{component}_version_drift")
            continue
        if cached_value != current:
            reasons.append(f"{component}_version_drift")

    # Note: we do NOT drift-check target_word_count here. The word count
    # is a derived value of (question.marks, prompt_version) — when the
    # prompt template is updated, the prompt_version bumps, which IS
    # checked above. Including target_word_count as an independent
    # check would double-flag every cache and would also be wrong for
    # MCQ answers (whose target_word_count is the MCQ explanation
    # count, not a theory value).

    # embedding_model check — but only if cached_emb is non-None. A
    # pre-Phase-3 cache has no embedding_model field at all; the
    # missing_versions branch above already flags it.
    cached_emb = cached.get("embedding_model")
    if cached_emb is not None and cached_emb != config.EMBEDDING_MODEL:
        reasons.append(REASON_EMBEDDING_MODEL_DRIFT)

    # P0: per-subject KB revision. When a book for this subject is
    # re-ingested, bump_kb_revision(subject) runs; answers generated
    # against an older revision are stale (grounding corpus changed).
    subject = cached.get("module_subject")
    if subject:
        try:
            from medrack.answer.kb_revision import get_kb_revision

            current_rev = get_kb_revision(str(subject))
            cached_rev = cached.get("kb_revision")
            if cached_rev is None:
                # Pre-P0 cache: only stale if the subject has been
                # re-indexed at least once after P0 landed.
                if current_rev > 0:
                    reasons.append(REASON_KB_REINDEXED)
            else:
                try:
                    if int(cached_rev) != int(current_rev):
                        reasons.append(REASON_KB_REINDEXED)
                except (TypeError, ValueError):
                    reasons.append(REASON_KB_REINDEXED)
        except Exception:  # noqa: BLE001 — never break load_answer
            logger.debug("kb_revision check failed", exc_info=True)

    return (bool(reasons), reasons)


def mark_stale(cached: dict) -> dict:
    """Return a copy of the cached answer with stale=True and stale_reasons set.

    Does not mutate the input dict. Does not delete the cache file.
    """
    stale, reasons = is_stale(cached)
    if not stale:
        # No-op for fresh answers; still return a copy so callers can
        # safely mutate.
        return dict(cached)
    out = dict(cached)
    out["stale"] = True
    out["stale_reasons"] = list(reasons)
    return out


def find_stale_answers(
    module_name: str | None = None,
    answers_root: Path | None = None,
) -> list[dict]:
    """Scan the answers directory and return a list of stale entries.

    Each result dict has:
        - module: module slug
        - chapter: chapter slug
        - qid: question id
        - path: absolute path to the cache file
        - reasons: list of staleness reasons

    If ``module_name`` is given, only that module is scanned. Otherwise
    all modules under ``answers_root`` are scanned.

    Does not modify or delete any cache files. The file scan is read-only.
    """
    from medrack.answer.cache import _answers_root  # avoid circular import

    if answers_root is None:
        answers_root = _answers_root()
    if not answers_root.exists():
        return []

    results: list[dict] = []
    modules = [module_name] if module_name else [
        p.name for p in answers_root.iterdir() if p.is_dir()
    ]

    for mod in modules:
        mod_path = answers_root / mod
        if not mod_path.is_dir():
            continue
        for chapter_path in mod_path.iterdir():
            if not chapter_path.is_dir():
                continue
            chapter = chapter_path.name
            for answer_file in chapter_path.glob("*.json"):
                try:
                    cached = json.loads(answer_file.read_text())
                except (json.JSONDecodeError, OSError) as exc:
                    # Corrupt file — surface as a "stale" entry with a
                    # distinct reason. Don't delete.
                    results.append({
                        "module": mod,
                        "chapter": chapter,
                        "qid": answer_file.stem,
                        "path": str(answer_file),
                        "reasons": [f"corrupt_file: {type(exc).__name__}"],
                    })
                    continue
                stale, reasons = is_stale(cached)
                if stale:
                    results.append({
                        "module": mod,
                        "chapter": chapter,
                        "qid": answer_file.stem,
                        "path": str(answer_file),
                        "reasons": reasons,
                    })
    return results


__all__ = [
    "is_stale",
    "mark_stale",
    "find_stale_answers",
    "REASON_SCHEMA_DRIFT",
    "REASON_PROMPT_DRIFT",
    "REASON_RETRIEVAL_DRIFT",
    "REASON_RENDERER_DRIFT",
    "REASON_PLANNER_DRIFT",
    "REASON_VALIDATOR_DRIFT",
    "REASON_RERANKER_DRIFT",
    "REASON_WORD_COUNT_DRIFT",
    "REASON_EMBEDDING_MODEL_DRIFT",
    "REASON_MISSING_VERSIONS",
    "REASON_KB_REINDEXED",
]
