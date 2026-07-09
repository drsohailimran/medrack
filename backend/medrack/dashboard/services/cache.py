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
    # The module the answer belongs to (the bank's safe stem for bank
    # answers, or a book_id / "<subject>-default" for single generations)
    # and the question text — used to group + label answers in the UI.
    module: str = ""
    question_text: str = ""

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
            "module": self.module,
            "question_text": self.question_text,
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
        cache_root = self._home / "answers"
        if not cache_root.exists():
            return entries
        for cache_file in cache_root.rglob("*.json"):
            try:
                with cache_file.open(encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            qid = data.get("qid", cache_file.stem)
            # Answer dicts persist the subject under ``module_subject``;
            # fall back to it (and finally "") for older cache layouts.
            subj = data.get("subject", data.get("module_subject", ""))
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
                module=data.get("module_name", data.get("module", "")),
                question_text=data.get("question_text", ""),
            ))
        return entries

    def delete_entry(self, qid: str, module: Optional[str] = None) -> Dict[str, Any]:
        """Delete the cached answer file(s) for ``qid``.

        ``module`` scopes the search to one bank/module directory — important
        because plain qids like ``q001`` are NOT unique across banks, so an
        unscoped delete would remove same-named answers from other banks.

        Safety: only unlinks files under ``MEDRACK_HOME/answers/``. Never
        touches question-bank modules under ``modules/``.
        """
        cache_root = (self._home / "answers").resolve()
        search_root = cache_root
        if module:
            safe = "".join(c for c in module if c.isalnum() or c in ("-", "_", ".")).strip()
            search_root = (cache_root / safe).resolve()
            try:
                search_root.relative_to(cache_root)
            except ValueError:
                return {"ok": False, "qid": qid, "removed": 0, "error": "refusing path outside answers/"}
        removed = 0
        if search_root.exists():
            for cache_file in search_root.rglob(f"{qid}.json"):
                try:
                    resolved = cache_file.resolve()
                    resolved.relative_to(cache_root)
                except ValueError:
                    continue
                try:
                    cache_file.unlink()
                    removed += 1
                except Exception:  # noqa: BLE001
                    pass
        return {"ok": removed > 0, "qid": qid, "removed": removed}

    def delete_module(self, module: str) -> Dict[str, Any]:
        """Delete every cached answer under a module directory (i.e. all
        answers for one question bank).

        Safety: only ever deletes under ``MEDRACK_HOME/answers/<module>/``.
        Never touches ``modules/`` (question banks) or other data dirs.
        """
        import shutil

        safe = "".join(c for c in module if c.isalnum() or c in ("-", "_", ".")).strip()
        if not safe or safe in (".", ".."):
            return {"ok": False, "module": module, "error": "invalid module name"}
        removed = 0
        cache_root = (self._home / "answers").resolve()
        mod_dir = (cache_root / safe).resolve()
        # Path-traversal / wrong-tree guard
        try:
            mod_dir.relative_to(cache_root)
        except ValueError:
            return {"ok": False, "module": module, "error": "refusing path outside answers/"}
        if mod_dir == cache_root:
            return {"ok": False, "module": module, "error": "refusing to delete entire answers root"}
        if mod_dir.is_dir():
            # Count files before removing for a useful response.
            removed = sum(1 for _ in mod_dir.rglob("*.json"))
            try:
                shutil.rmtree(mod_dir)
            except Exception:  # noqa: BLE001
                return {"ok": False, "module": module, "error": "delete failed"}
        return {"ok": True, "module": module, "removed": removed}

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
        cache_root = self._home / "answers"
        for cache_file in cache_root.rglob(f"{qid}.json"):
            try:
                with cache_file.open(encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            from medrack.answer.versioning import mark_stale
            marked = mark_stale(data)
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(marked, f, indent=2, sort_keys=True)
            return {"ok": True, "qid": qid, "marked_stale": True}
        return {"ok": False, "qid": qid, "error": "cache entry not found"}

    def get_entry(self, qid: str) -> Optional[Dict[str, Any]]:
        """Fetch a single cache entry by qid, normalized to the
        ``CacheEntryFull`` contract used by the frontend.

        This returns the full ``CacheEntry`` shape (computed
        ``is_stale``/``stale_reasons`` and the nested ``versions`` object)
        plus the single-entry detail fields (``module``, ``chapter``,
        ``question_text``, ``answer_text``, ``pdf_path``, ``stale``,
        ``embedding_model``, ``package_version``). Returns ``None`` if no
        entry exists.

        This is a read-only operation. It does not modify the cache file.
        """
        from medrack.answer.versioning import is_stale
        cache_root = self._home / "answers"
        for cache_file in cache_root.rglob(f"{qid}.json"):
            try:
                with cache_file.open(encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            is_st, reasons = is_stale(data)
            versions = data.get("versions", {})
            # Answer dicts persist the subject under ``module_subject``;
            # fall back to ``subject`` for older cache layouts.
            subject = data.get("subject", data.get("module_subject", ""))
            entry = CacheEntry(
                qid=data.get("qid", cache_file.stem),
                subject=subject,
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
                cached_at=data.get("cached_at", data.get("generated_at")),
                last_validated_at=data.get("last_validated_at"),
                validation_score=data.get("validation_score"),
            ).to_dict()
            # Augment with the CacheEntryFull single-entry detail fields.
            entry.update({
                "module": data.get("module_name", data.get("module", "")),
                "chapter": data.get("module_chapter", data.get("chapter", "")),
                "question_text": data.get("question_text", ""),
                "answer_text": data.get("answer_text", ""),
                "pdf_path": data.get("pdf_path") or "",
                "stale": bool(data.get("stale", is_st)),
                "embedding_model": data.get("embedding_model", ""),
                "package_version": data.get("package_version", ""),
            })
            return entry
        return None


__all__ = ["CacheService", "CacheEntry"]
