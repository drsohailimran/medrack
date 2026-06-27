"""
medrack.answer.cache — read/write cached answers.

Public interface:
    answer_path(module_name, chapter, qid) -> Path
    save_answer(module_name, chapter, qid, data) -> None
    load_answer(module_name, chapter, qid) -> dict | None
    cache_key_for_question(module_name, qid, question_text, prompt_template, model) -> str

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
    """Load the cached answer, or ``None`` if the file is missing."""
    path = answer_path(module_name, chapter, qid)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def cache_key_for_question(
    module_name: str,
    qid: str,
    question_text: str,
    prompt_template: str,
    model: str,
) -> str:
    """Return a deterministic 16-character SHA-256 hex digest for the
    canonical concatenation of the inputs.

    Includes the question text (so editing the module invalidates cache),
    the prompt template id (so changing the template invalidates cache),
    and the model name (so upgrading the model invalidates cache). The
    ``qid`` is included so two distinct questions in the same module do
    not collide.
    """
    canonical = f"{module_name}|{qid}|{question_text}|{prompt_template}|{model}"
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
