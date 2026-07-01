"""VersionService — Version information (Phase 12).

The :class:`VersionService` is the stable interface for viewing
the package version, pipeline component versions, and the
benchmark baseline version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class VersionInfo:
    """All version information for MedRack."""

    package_version: str
    pipeline_versions: Dict[str, int]
    benchmark_baseline_tag: str | None

    SCHEMA_VERSION = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "package_version": self.package_version,
            "pipeline_versions": dict(self.pipeline_versions),
            "benchmark_baseline_tag": self.benchmark_baseline_tag,
        }


class VersionService:
    """Service for version information."""

    SCHEMA_VERSION = 1

    def get_info(self) -> VersionInfo:
        """Return the current version info."""
        from medrack import __version__
        from medrack.config import PIPELINE_VERSIONS
        # The baseline tag is `phase-5-baseline` per the
        # benchmark framework (ADR 0005). We hard-code the
        # reference here; future phases may change this.
        baseline_tag = "phase-5-baseline"
        return VersionInfo(
            package_version=__version__,
            pipeline_versions=dict(PIPELINE_VERSIONS),
            benchmark_baseline_tag=baseline_tag,
        )


__all__ = ["VersionService", "VersionInfo"]
