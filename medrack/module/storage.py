"""
medrack.module.storage — read/write ``extracted.json`` for ingested modules.

Public interface:
    module_dir(subject, module_name) -> Path
    extracted_json_path(subject, module_name) -> Path
    save_extracted(subject, module_name, data) -> None
    load_extracted(subject, module_name) -> dict | None
    list_modules(subject=None) -> list[dict]

Design notes:
- The modules root path is re-evaluated on every call via
  ``config.get_medrack_home() / "modules"`` so the ``$MEDRACK_HOME``
  environment variable override works in tests (the module-level
  ``config.DATA_DIRS["modules"]`` constant is frozen at first import
  and would not honour the override). This mirrors the pattern used in
  ``medrack.ingest.manifest``.
- ``save_extracted`` performs an atomic write: it serialises to a
  sibling ``.tmp`` file first and then renames it over the target with
  ``Path.replace()`` (POSIX-atomic on the same filesystem, which is
  always the case here — both paths live under the modules root).
- ``list_modules`` walks the modules tree, reads each ``extracted.json``,
  and returns a list of per-module metadata dicts. Corrupt or missing
  ``extracted.json`` files are logged and skipped — they do not crash
  the listing.
"""
from __future__ import annotations

import json
from pathlib import Path

from medrack import config
from medrack.utils.logger import get_logger

log = get_logger(__name__)


def _modules_root() -> Path:
    """Re-evaluate the modules root so ``$MEDRACK_HOME`` overrides work."""
    return config.get_medrack_home() / "modules"


def module_dir(subject: str, module_name: str) -> Path:
    """Return the path to the module's directory, creating it if needed.

    The returned path is ``<MEDRACK_HOME>/modules/<subject>/<module_name>``.
    Parent directories are created with ``parents=True, exist_ok=True``,
    so this is safe to call before the very first write.
    """
    d = _modules_root() / subject / module_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def extracted_json_path(subject: str, module_name: str) -> Path:
    """Return the path to the module's ``extracted.json``.

    The parent directory is created (idempotent) so callers can pass the
    path straight to a writer without an extra ``module_dir`` call.
    """
    return module_dir(subject, module_name) / "extracted.json"


def save_extracted(subject: str, module_name: str, data: dict) -> None:
    """Atomically write the extracted questions JSON for a module.

    The write goes to a sibling ``.tmp`` file first, then is renamed over
    the target with :py:meth:`pathlib.Path.replace`. On POSIX this rename
    is atomic when both paths are on the same filesystem — which they
    always are here, since both live under ``<MEDRACK_HOME>/modules/``.
    A crash mid-write therefore never leaves a half-written
    ``extracted.json`` on disk.
    """
    path = extracted_json_path(subject, module_name)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False))
    tmp.replace(path)


def load_extracted(subject: str, module_name: str) -> dict | None:
    """Load extracted questions for a module, or ``None`` if not found.

    Returns ``None`` (not an exception) when the file is missing — that
    is the normal "not yet ingested" case. JSON parse errors propagate
    to the caller, since a corrupt ``extracted.json`` is a real bug
    worth surfacing.
    """
    path = extracted_json_path(subject, module_name)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def list_modules(subject: str | None = None) -> list[dict]:
    """List ingested modules under the modules root.

    Walks ``<MEDRACK_HOME>/modules/`` and, for every directory that
    contains an ``extracted.json``, returns a summary dict with the
    following keys:

    - ``name``: the module slug (directory name)
    - ``subject``: the subject directory
    - ``path``: the full path to the module directory
    - ``total_questions``: ``metadata.questions_extracted`` (default 0)
    - ``format``: ``metadata.format`` (may be ``None``)
    - ``extracted_at``: ``metadata.extracted_at`` (may be ``None``)

    If ``subject`` is given, results are filtered to that subject.

    Missing or corrupt ``extracted.json`` files are logged at WARNING
    level and skipped — a single bad module never breaks the listing.
    """
    root = _modules_root()
    if not root.exists():
        return []

    out: list[dict] = []
    for extracted in root.glob("*/*/extracted.json"):
        # extracted is e.g. <root>/<subject>/<name>/extracted.json
        mod_dir = extracted.parent
        subj = mod_dir.parent.name
        name = mod_dir.name
        if subject is not None and subj != subject:
            continue
        try:
            data = json.loads(extracted.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(
                "list_modules: skipping %s (cannot read extracted.json: %s)",
                mod_dir, exc,
            )
            continue
        meta = data.get("metadata", {}) if isinstance(data, dict) else {}
        out.append({
            "name": name,
            "subject": subj,
            "path": str(mod_dir),
            "total_questions": meta.get("questions_extracted", 0),
            "format": meta.get("format"),
            "extracted_at": meta.get("extracted_at"),
        })

    # Stable order — sort by (subject, name) so callers get deterministic output
    out.sort(key=lambda m: (m["subject"], m["name"]))
    return out


__all__ = [
    "module_dir",
    "extracted_json_path",
    "save_extracted",
    "load_extracted",
    "list_modules",
]
