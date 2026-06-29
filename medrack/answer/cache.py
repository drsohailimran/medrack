"""
medrack.answer.cache — read/write cached answers.

Public interface:
    answer_path(module_name, chapter, qid) -> Path
    save_answer(module_name, chapter, qid, data) -> None
    load_answer(module_name, chapter, qid) -> dict | None
    cache_key_for_question(module_name, qid, question_text,
                           prompt_template, model, *,
                           subject, target_word_count) -> str

Design notes:
- The answers root is re-evaluated on every call via
  ``config.get_medrack_home() / "answers"`` so the ``$MEDRACK_HOME``
  environment variable override works in tests (the module-level
  ``config.DATA_DIRS["answers"]`` constant is frozen at first import and
  would not honour the override).
- ``save_answer`` is atomic: writes to ``<path>.json.tmp`` first, then
  ``Path.replace()`` (POSIX-atomic on the same filesystem) so a crash
  mid-write never produces a half-written answer file.
- The cache itself is keyed by ``qid`` (the on-disk file is
  ``<module>/<chapter>/<qid>.json``). The ``cache_key_for_question`` hash
  is *not* used as the filename — it exists so the orchestrator can decide
  if a cached answer is still semantically valid (e.g. if the question
  text was edited, or the prompt template / model changed, treat the
  cached answer as a miss even when the file is present).
- **Phase 3 (directive v1.0) — layered answer versioning:**
  ``load_answer`` now also calls ``medrack.answer.versioning.is_stale``
  on the loaded dict. If the cached answer's versions don't match the
  current ``PIPELINE_VERSIONS``, the returned dict is annotated with
  ``stale: True`` and ``stale_reasons: [...]``. The cache FILE is never
  modified or deleted by the version check. The caller (the
  orchestrator) decides whether to surface the stale answer, regenerate
  it, or both.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from medrack import config


def _answers_root() -> Path:
    """Re-evaluate the answers root so ``$MEDRACK_HOME`` overrides work."""
    return config.get_medrack_home() / "answers"


def answer_path(module_name: str, chapter: str, qid: str) -> Path:
    """Return the path to a cached answer JSON. Creates intermediate
    directories (``<answers>/<module>/<chapter>``) on demand.
    """
    d = _answers_root() / module_name / chapter
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{qid}.json"


def save_answer(module_name: str, chapter: str, qid: str, data: dict) -> None:
    """Atomically write the answer JSON to ``<answers>/<module>/<chapter>/<qid>.json``.

    Writes to a sibling ``.json.tmp`` first, then ``Path.replace()`` so a
    crash mid-write never produces a half-written file.
    """
    path = answer_path(module_name, chapter, qid)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False))
    tmp.replace(path)


def load_answer(module_name: str, chapter: str, qid: str) -> dict | None:
    """Load the cached answer, or ``None`` if the file is missing.

    Phase 3: also annotates the returned dict with ``stale: True`` and
    ``stale_reasons: [...]`` if the cached answer's versions don't match
    the current ``PIPELINE_VERSIONS``. The cache file on disk is never
    modified or deleted — the orchestrator decides what to do with the
    stale annotation.
    """
    from medrack.answer.versioning import mark_stale

    path = answer_path(module_name, chapter, qid)
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    return mark_stale(raw)


def cache_key_for_question(
    module_name: str,
    qid: str,
    question_text: str,
    prompt_template: str,
    model: str,
    *,
    subject: str = "psm",
    target_word_count: int | None = None,
) -> str:
    """Return a deterministic 16-character SHA-256 hex digest for the
    canonical concatenation of the inputs.

    Phase 3: the key now also includes the current ``PIPELINE_VERSIONS``
    dict (as a compact string), the ``subject`` (so FMT and PSM
    questions with identical text don't collide), the
    ``target_word_count`` (so a 500-word answer and a 775-word answer
    for the same question are distinct cache keys), and the
    ``EMBEDDING_MODEL`` (so a re-embedding invalidates cache).

    The first five positional parameters keep their old names for
    backward compatibility with existing call sites — the new
    parameters are keyword-only.
    """
    from medrack import config as _config

    # Compact serialisation of the versions dict. Sorting keys makes
    # the digest stable across Python versions and dict ordering.
    versions_str = ",".join(
        f"{k}={_config.PIPELINE_VERSIONS[k]}"
        for k in sorted(_config.PIPELINE_VERSIONS.keys())
    )
    wc = target_word_count if target_word_count is not None else 0
    canonical = (
        f"{module_name}|{qid}|{question_text}|{prompt_template}|{model}"
        f"|subject={subject}|versions={versions_str}"
        f"|target_word_count={wc}"
        f"|embedding_model={_config.EMBEDDING_MODEL}"
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
