"""Preflight checks before long-running jobs (disk, subject, etc.)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


# Known subjects (must match medrack.config.Subject)
KNOWN_SUBJECTS = frozenset(
    {
        "psm",
        "fmt",
        "medicine",
        "surgery",
        "obgyn",
        "pediatrics",
        "ortho",
        "ent",
        "ophthalmology",
        "anesthesia",
    }
)


def assert_disk_space(
    path: Path | str,
    *,
    min_free_gb: float = 5.0,
    label: str = "data",
) -> Dict[str, Any]:
    """Raise RuntimeError if free disk under ``path`` is below ``min_free_gb``."""
    p = Path(path)
    # Walk up until path exists
    probe = p if p.exists() else p.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    usage = shutil.disk_usage(str(probe))
    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)
    info = {
        "path": str(probe),
        "label": label,
        "free_gb": round(free_gb, 2),
        "total_gb": round(total_gb, 2),
        "min_free_gb": min_free_gb,
        "ok": free_gb >= min_free_gb,
    }
    if free_gb < min_free_gb:
        raise RuntimeError(
            f"Low disk space on {label} ({probe}): "
            f"{free_gb:.1f} GB free < {min_free_gb:.1f} GB required. "
            "Free space before continuing overnight ingest."
        )
    return info


def validate_subject(subject: str) -> str:
    """Normalize and validate subject; raise ValueError if unknown."""
    s = (subject or "").strip().lower()
    if not s:
        raise ValueError("subject is required")
    if s not in KNOWN_SUBJECTS:
        known = ", ".join(sorted(KNOWN_SUBJECTS))
        raise ValueError(
            f"unknown subject {subject!r}. Use one of: {known}"
        )
    return s


def text_gibberish_score(text: str) -> float:
    """Return 0..1 how 'gibberish' the text looks (1 = unusable).

    Heuristic: low alpha ratio, few vowels, many repeated symbols,
    very short words-only noise from bad OCR.
    """
    if not text or not text.strip():
        return 1.0
    raw = text.strip()
    n = len(raw)
    if n < 20:
        return 0.85
    alpha = sum(ch.isalpha() for ch in raw)
    digit = sum(ch.isdigit() for ch in raw)
    alpha_ratio = alpha / n
    vowels = sum(ch.lower() in "aeiou" for ch in raw if ch.isalpha())
    vowel_ratio = vowels / max(1, alpha)
    # Weird symbol density
    weird = sum(1 for ch in raw if not (ch.isalnum() or ch.isspace() or ch in ".,;:()[]-%/'\""))
    weird_ratio = weird / n
    # Average word length
    words = [w for w in raw.split() if w]
    avg_w = (sum(len(w) for w in words) / len(words)) if words else 0.0
    realish = sum(1 for w in words if len(w) >= 3 and w.isalpha()) / max(1, len(words))

    score = 0.0
    if alpha_ratio < 0.30:
        score += 0.55
    elif alpha_ratio < 0.45:
        score += 0.40
    elif alpha_ratio < 0.55:
        score += 0.18
    if alpha > 20 and vowel_ratio < 0.22:
        score += 0.25
    if weird_ratio > 0.25:
        score += 0.35
    elif weird_ratio > 0.12:
        score += 0.22
    if avg_w > 0 and (avg_w < 2.2 or avg_w > 18):
        score += 0.15
    if realish < 0.25 and n > 40:
        score += 0.25
    if digit / n > 0.45 and alpha_ratio < 0.3:
        score += 0.1  # not always bad (tables) — mild
    return max(0.0, min(1.0, score))


def sample_text_quality(
    texts: List[str],
    *,
    max_samples: int = 12,
    fail_above: float = 0.72,
) -> Dict[str, Any]:
    """Average gibberish over samples; ok=False if mean too high."""
    samples = [t for t in texts if (t or "").strip()]
    if not samples:
        return {
            "ok": False,
            "mean_gibberish": 1.0,
            "samples": 0,
            "detail": "no text samples",
        }
    # Evenly sample across the book
    if len(samples) > max_samples:
        step = max(1, len(samples) // max_samples)
        samples = samples[::step][:max_samples]
    scores = [text_gibberish_score(t) for t in samples]
    mean = sum(scores) / len(scores)
    return {
        "ok": mean < fail_above,
        "mean_gibberish": round(mean, 3),
        "max_gibberish": round(max(scores), 3),
        "samples": len(scores),
        "fail_above": fail_above,
        "detail": f"mean_gibberish={mean:.3f} (fail if >= {fail_above})",
    }
