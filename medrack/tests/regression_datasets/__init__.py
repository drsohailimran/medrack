"""Permanent regression dataset for MedRack (Phase 4, directive v1.0).

Loads the curated 20-question benchmark set used to measure
architectural changes. The dataset itself lives in
``medrack/tests/regression_datasets/v1.json`` and is NEVER MODIFIED.
To extend the benchmark suite, add a ``v2.json`` (or higher) and
update the loader's fallback list.

The dataset is intentionally placed in ``tests/`` (not in
``benchmarks/``) because it is treated as test data — read-only,
versioned with the code, and validated by the test suite.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Path to the datasets directory (relative to this file's location).
# __file__ = medrack/tests/regression_datasets/__init__.py, so
# Path(__file__).parent = medrack/tests/regression_datasets/
_DATASETS_DIR = Path(__file__).parent

# The active dataset version. Bump when adding a new dataset file.
ACTIVE_VERSION = 1


def load_regression_dataset(version: int = ACTIVE_VERSION) -> dict[str, Any]:
    """Load the regression dataset for the given version.

    Returns the parsed JSON dict. The schema is:
        {
            "_doc": str (operator notes about the dataset),
            "_version": int,
            "_created": str (ISO date),
            "_module_sources": dict[str, str]  (module -> extracted.json path),
            "questions": list[dict]  (each: module, qid, subject, marks, ...)
        }

    Raises:
        FileNotFoundError: if the requested version's JSON file does not exist.
    """
    path = _DATASETS_DIR / f"v{version}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Regression dataset v{version} not found at {path}. "
            f"Available versions: {list_available_versions()}"
        )
    return json.loads(path.read_text())


def list_available_versions() -> list[int]:
    """Return a sorted list of available dataset versions."""
    versions = []
    for p in _DATASETS_DIR.glob("v*.json"):
        try:
            versions.append(int(p.stem[1:]))  # strip 'v' prefix
        except ValueError:
            continue
    return sorted(versions)


def get_regression_questions(version: int = ACTIVE_VERSION) -> list[dict[str, Any]]:
    """Return the list of question entries from the dataset."""
    return load_regression_dataset(version)["questions"]


__all__ = [
    "load_regression_dataset",
    "list_available_versions",
    "get_regression_questions",
    "ACTIVE_VERSION",
]
