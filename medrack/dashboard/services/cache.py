"""CacheService — Cache management (Phase 12).

The :class:`CacheService` is the stable interface for viewing cache
status, finding stale answers, viewing per-version metadata, and
selective regeneration.

The service is read-only for inspection; mutations go through
explicit action methods (``reanswer``, ``mark_stale``).

This is the "Cache Management" feature requested in the Phase 12
directive.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CacheEntry:
    """A single cached answer entry."""

    qid: str
    subject: str
    is_stale: bool
    stale_reasons: List[str] = field(default_factory=list)
    schema_version: int = 0
    prompt_version: int = 0
    retrieval_version: int = 0
    planner_version: int = 0
    validator_version: int = 0
    reranker_version: int = 0
    renderer_version: int = 0
    embedding_model: str = ""
    target_word_count: int = 0
    cached_at: Optional[str] = None
    last_validated_at: Optional[str] = None
    validation_score: Optional[float] = None

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "qid": self.qid,
            "subject": self.subject,
            "is_stale": self.is_stale,
            "stale_reasons": list(self.stale_reasons),
            "versions": {
                "schema": self.schema_version,
                "prompt": self.prompt_version,
                "retrieval": self.retrieval_version,
                "planner": self.planner_version,
                "validator": self.validator_version,
                "reranker": self.reranker_version,
                "renderer": self.renderer_version,
                "embedding_model": self.embedding_model,
            },
            "target_word_count": self.target_word_count,
            "cached_at": self.cached_at,
            "last_validated_at": self.last_validated_at,
            "validation_score": self.validation_score,
        }


class CacheService:
    """Service for cache management."""

    SCHEMA_VERSION = 1

    def __init__(self, medrack_home: Optional[Path] = None) -> None:
        from medrack.config import get_medrack_home
        if medrack_home is None:
            self._home = get_medrack_home()
        else:
            self._home = Path(medrack_home)

    def list_entries(
        self,
        subject: Optional[str] = None,
        stale_only: bool = False,
    ) -> List[CacheEntry]:
        """List cached answer entries, optionally filtered by subject or stale."""
        from medrack.answer.versioning import is_stale, find_stale_answers
        # Get the list of stale qids (if stale_only)
        stale_qids: set = set()
        if stale_only or subject is not None:
            for subj in ([subject] if subject else ["psm", "fmt"]):
                # find_stale_answers takes module_name (e.g. "psm-module-1")
                # but for the cache scan we want all modules. Pass None.
                for s in find_stale_answers(module_name=None):
                    stale_qids.add(s.get("qid"))
        entries: List[CacheEntry] = []
        cache_root = self._home / "cache"
        if not cache_root.exists():
            return entries
        for cache_file in cache_root.rglob("*.json"):
            try:
                with cache_file.open() as f:
                    data = json.load(f)
            except Exception:
                continue
            qid = data.get("qid", cache_file.stem)
            subj = data.get("subject", "")
            is_st, reasons = is_stale(data)
            if stale_only and not is_st:
                continue
            if subject is not None and subj != subject:
                continue
            versions = data.get("versions", {})
            entries.append(CacheEntry(
                qid=qid,
                subject=subj,
                is_stale=is_st,
                stale_reasons=list(reasons),
                schema_version=versions.get("schema", 0),
                prompt_version=versions.get("prompt", 0),
                retrieval_version=versions.get("retrieval", 0),
                planner_version=versions.get("planner", 0),
                validator_version=versions.get("validator", 0),
                reranker_version=versions.get("reranker", 0),
                renderer_version=versions.get("renderer", 0),
                embedding_model=data.get("embedding_model", ""),
                target_word_count=data.get("target_word_count", 0),
                cached_at=data.get("cached_at"),
                last_validated_at=data.get("last_validated_at"),
                validation_score=data.get("validation_score"),
            ))
        return entries

    def get_status(self) -> Dict[str, Any]:
        """Get overall cache status (counts by subject and staleness)."""
        all_entries = self.list_entries()
        by_subject: Dict[str, int] = {}
        stale_by_subject: Dict[str, int] = {}
        for e in all_entries:
            by_subject[e.subject] = by_subject.get(e.subject, 0) + 1
            if e.is_stale:
                stale_by_subject[e.subject] = stale_by_subject.get(e.subject, 0) + 1
        return {
            "total_entries": len(all_entries),
            "by_subject": by_subject,
            "stale_by_subject": stale_by_subject,
            "schema_version": self.SCHEMA_VERSION,
        }

    def reanswer(self, qid: str) -> Dict[str, Any]:
        """Re-answer a single cached entry.

        Marks the cache entry as stale. The actual regeneration
        is the question service's job.
        """
        # Find the cached entry
        cache_root = self._home / "cache"
        for cache_file in cache_root.rglob(f"{qid}.json"):
            try:
                with cache_file.open() as f:
                    data = json.load(f)
            except Exception:
                continue
            from medrack.answer.versioning import mark_stale
            marked = mark_stale(data)
            with cache_file.open("w") as f:
                json.dump(marked, f, indent=2, sort_keys=True)
            return {"ok": True, "qid": qid, "marked_stale": True}
        return {"ok": False, "qid": qid, "error": "cache entry not found"}

    def get_entry(self, qid: str) -> Optional[Dict[str, Any]]:
        """Fetch a single cache entry by qid.

        Returns the raw cached dict (answer_text, pdf_path,
        stale flag, etc.) or None if not found.

        This is a read-only operation. It does not modify the
        cache file.
        """
        cache_root = self._home / "cache"
        for cache_file in cache_root.rglob(f"{qid}.json"):
            try:
                with cache_file.open() as f:
                    return json.load(f)
            except Exception:
                continue
        return None


__all__ = ["CacheService", "CacheEntry"]
