"""medrack.retrieval.blueprint_retrieval — Blueprint Retrieval spec (Phase 9).

This module is the retrieval-aware enrichment of the Planner's
Blueprint. The Planner decides *which sections*; this module
decides *what evidence to retrieve for each section* and *in what
priority*.

Architecture (per the Phase 9 directive):

    Planner -> Blueprint -> [Blueprint Retrieval] -> Retrieval -> Writer -> Validator

The Blueprint Retrieval sits between the Planner's output and the
Retrieval layer. It consumes a Planner Blueprint and produces a
:class:`BlueprintRetrieval` spec that downstream retrieval strategies
can use to fetch section-specific evidence.

What this module does
---------------------
For each Planner section, it produces a :class:`SectionRetrievalSpec`
that says:

  - what :class:`MetadataFilter` to use when retrieving chunks
    for this section
  - the priority (lower = more important; 0 = must retrieve,
    1 = should, 2 = nice-to-have)
  - the minimum and maximum number of chunks to allocate
  - the evidence categories this section needs (e.g. "definition",
    "epidemiology data", "treatment protocol")

What this module does NOT do
----------------------------
- It does not perform retrieval (no ChromaDB calls, no LLM).
- It does not generate prose (the writer's job).
- It does not modify the Planner's section list (per the directive:
  "The Blueprint must not modify the Planner's section list").
- It does not perform validation (the validator's job).

v1 rules
--------
The v1 implementation is deterministic and pure. For each Planner
section:

  1. If the section has a ``metadata_section`` (e.g.
     ``section_management``), build a single-section
     :class:`MetadataFilter` for that section. Otherwise, the filter
     is empty (framing sections like introduction/conclusion have no
     chunk-metadata equivalent).
  2. ``priority`` = 0 if the section is ``required``, else 2.
  3. ``min_chunks`` = 1 (every section needs at least one chunk to
     be grounded).
  4. ``max_chunks`` = 3 (the v1 budget per section; future phases
     can tune this).
  5. ``evidence_categories`` = list of distinct ``metadata_section``
     values across all sections (the union).

The aggregate :class:`MetadataFilter` is the union of all per-section
filters. Future retrieval strategies can use this to bias retrieval
in one call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from medrack.ingest.metadata import MetadataFilter


# v1 budget constants
DEFAULT_MIN_CHUNKS = 1
DEFAULT_MAX_CHUNKS = 3

# Priority values
PRIORITY_REQUIRED = 0
PRIORITY_RECOMMENDED = 1
PRIORITY_OPTIONAL = 2


@dataclass
class SectionRetrievalSpec:
    """Retrieval specification for a single Planner section.

    Attributes
    ----------
    section_name:
        The Planner section's ``name`` (e.g. ``"management"``,
        ``"introduction"``). Echoed back for traceability.
    metadata_filter:
        :class:`MetadataFilter` to apply when retrieving chunks
        for this section. Empty filter = no filter.
    priority:
        Lower = more important. ``0`` = must retrieve (required
        section); ``1`` = should retrieve (recommended); ``2`` =
        nice-to-have (optional). The v1 implementation uses 0 for
        required, 2 for optional; 1 is reserved for future use.
    min_chunks:
        Minimum number of chunks to retrieve for this section.
    max_chunks:
        Maximum number of chunks to allocate to this section.
    evidence_category:
        The Planner section's ``metadata_section`` (e.g.
        ``"section_management"``) or ``None`` for framing sections.
    """

    section_name: str
    metadata_filter: MetadataFilter
    priority: int
    min_chunks: int
    max_chunks: int
    evidence_category: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_name": self.section_name,
            "metadata_filter": {
                "structure": list(self.metadata_filter.structure),
                "medical": list(self.metadata_filter.medical),
            },
            "priority": self.priority,
            "min_chunks": self.min_chunks,
            "max_chunks": self.max_chunks,
            "evidence_category": self.evidence_category,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SectionRetrievalSpec":
        return cls(
            section_name=d["section_name"],
            metadata_filter=MetadataFilter(
                structure=list(d["metadata_filter"].get("structure", [])),
                medical=list(d["metadata_filter"].get("medical", [])),
            ),
            priority=d["priority"],
            min_chunks=d["min_chunks"],
            max_chunks=d["max_chunks"],
            evidence_category=d.get("evidence_category"),
        )


@dataclass
class BlueprintRetrieval:
    """The retrieval-aware enrichment of a Planner Blueprint.

    The Planner produces a :class:`Blueprint` (what sections to write).
    This class produces a :class:`BlueprintRetrieval` (what evidence
    to retrieve for each section, in what priority).

    Attributes
    ----------
    subject:
        Echoed from the Planner blueprint.
    marks:
        Echoed from the Planner blueprint.
    question_type:
        Echoed from the Planner blueprint.
    target_word_count:
        Echoed from the Planner blueprint. Used by downstream
        retrieval strategies to scale chunk allocation.
    section_specs:
        Ordered list of :class:`SectionRetrievalSpec`, one per
        Planner section, in the same order as the Planner blueprint's
        sections list.
    aggregate_metadata_filter:
        Union of all per-section :class:`MetadataFilter`s. Useful for
        retrieval strategies that want a single filter to apply
        across the whole query.
    evidence_categories:
        Distinct list of ``metadata_section`` values across all
        sections. Equivalent to the Planner's
        ``required_metadata_categories`` but computed independently
        by the Blueprint spec.
    """

    subject: str
    marks: Optional[int]
    question_type: str
    target_word_count: int
    section_specs: List[SectionRetrievalSpec] = field(default_factory=list)
    aggregate_metadata_filter: MetadataFilter = field(default_factory=MetadataFilter)
    evidence_categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "subject": self.subject,
            "marks": self.marks,
            "question_type": self.question_type,
            "target_word_count": self.target_word_count,
            "section_specs": [s.to_dict() for s in self.section_specs],
            "aggregate_metadata_filter": {
                "structure": list(self.aggregate_metadata_filter.structure),
                "medical": list(self.aggregate_metadata_filter.medical),
            },
            "evidence_categories": list(self.evidence_categories),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BlueprintRetrieval":
        v = d.get("schema_version", 1)
        if v != 1:
            raise ValueError(
                f"Unsupported blueprint_retrieval schema_version: {v} (expected 1)"
            )
        agg = d.get("aggregate_metadata_filter", {})
        return cls(
            subject=d["subject"],
            marks=d.get("marks"),
            question_type=d["question_type"],
            target_word_count=d["target_word_count"],
            section_specs=[
                SectionRetrievalSpec.from_dict(s)
                for s in d.get("section_specs", [])
            ],
            aggregate_metadata_filter=MetadataFilter(
                structure=list(agg.get("structure", [])),
                medical=list(agg.get("medical", [])),
            ),
            evidence_categories=list(d.get("evidence_categories", [])),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "BlueprintRetrieval":
        return cls.from_dict(json.loads(s))


# ----------------------------------------------------------------------
# Construction (v1 deterministic rules)
# ----------------------------------------------------------------------

def build_blueprint_retrieval(
    planner_blueprint: Any,
    *,
    min_chunks: int = DEFAULT_MIN_CHUNKS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> BlueprintRetrieval:
    """Build a :class:`BlueprintRetrieval` from a Planner Blueprint.

    Parameters
    ----------
    planner_blueprint:
        Any object with the following attributes (duck-typed; in
        practice this is a :class:`medrack.planner.blueprint.Blueprint`):

        - ``subject: str``
        - ``marks: int | None``
        - ``question_type: str``
        - ``target_word_count: int``
        - ``sections: list`` of section objects with attributes
          ``name``, ``required``, ``metadata_section``
        - ``required_metadata_categories: list[str]`` (optional; the
          v1 implementation recomputes this from sections)

    min_chunks, max_chunks:
        Default chunk allocation per section. The v1 budget is
        ``min_chunks=1, max_chunks=3``.

    Returns
    -------
    BlueprintRetrieval
        A retrieval-aware spec ready for downstream consumption.
    """
    section_specs: List[SectionRetrievalSpec] = []
    agg_structure: List[str] = []
    agg_medical: List[str] = []
    seen_metadata: set = set()
    evidence_categories: List[str] = []

    for section in planner_blueprint.sections:
        # Per-section filter: a single-section filter if the section
        # has a metadata_section, else empty (framing sections have
        # no chunk-metadata equivalent).
        if section.metadata_section is not None:
            # Classify into structure vs medical
            from medrack.ingest.metadata import (
                StructureMetadata, MedicalMetadata,
            )
            structure_fields = {f for f in StructureMetadata.__dataclass_fields__}
            medical_fields = {f for f in MedicalMetadata.__dataclass_fields__}
            if section.metadata_section in structure_fields:
                filt = MetadataFilter(structure=[section.metadata_section])
                agg_structure.append(section.metadata_section)
            elif section.metadata_section in medical_fields:
                filt = MetadataFilter(medical=[section.metadata_section])
                agg_medical.append(section.metadata_section)
            else:
                filt = MetadataFilter()
            evidence_category = section.metadata_section
            if evidence_category not in seen_metadata:
                seen_metadata.add(evidence_category)
                evidence_categories.append(evidence_category)
        else:
            filt = MetadataFilter()
            evidence_category = None

        priority = PRIORITY_REQUIRED if section.required else PRIORITY_OPTIONAL

        section_specs.append(
            SectionRetrievalSpec(
                section_name=section.name,
                metadata_filter=filt,
                priority=priority,
                min_chunks=min_chunks,
                max_chunks=max_chunks,
                evidence_category=evidence_category,
            )
        )

    # Dedupe the aggregate filter while preserving order
    agg_filter = MetadataFilter(
        structure=list(dict.fromkeys(agg_structure)),
        medical=list(dict.fromkeys(agg_medical)),
    )

    return BlueprintRetrieval(
        subject=planner_blueprint.subject,
        marks=planner_blueprint.marks,
        question_type=planner_blueprint.question_type,
        target_word_count=planner_blueprint.target_word_count,
        section_specs=section_specs,
        aggregate_metadata_filter=agg_filter,
        evidence_categories=evidence_categories,
    )


__all__ = [
    "SectionRetrievalSpec",
    "BlueprintRetrieval",
    "build_blueprint_retrieval",
    "PRIORITY_REQUIRED",
    "PRIORITY_RECOMMENDED",
    "PRIORITY_OPTIONAL",
    "DEFAULT_MIN_CHUNKS",
    "DEFAULT_MAX_CHUNKS",
]
