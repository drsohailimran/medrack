"""Structured medical metadata for textbook chunks (Phase 6).

This module is the schema and the *interface* for metadata extraction. It
contains:

  - Three grouped metadata dataclasses: ``StructureMetadata``,
    ``MedicalMetadata``, ``ExamMetadata`` — together they form
    ``ChunkMetadata``.
  - A ``MetadataExtractor`` abstract base class defining the pluggable
    extractor interface.
  - A ``MetadataFilter`` dataclass for typed retrieval-time filtering.
  - A ``flatten_for_chroma`` helper that converts the grouped metadata
    into the scalar-only dict ChromaDB requires.

Design principles
-----------------
- The application never depends on ChromaDB's scalar-only metadata
  limitation. Internally, metadata is grouped into typed dataclasses with
  rich Python types (lists, ints, bools). The flat dict is computed only
  at the persistence boundary (in ``medrack.ingest.index``).
- Extraction is pluggable. v1 ships a deterministic regex/heuristic
  implementation (``medrack.ingest.extractors.regex_extractor``). Future
  LLM-based or hybrid extractors can be added without changing the
  ingestion pipeline — they just need to subclass ``MetadataExtractor``
  and return a ``ChunkMetadata`` instance.
- Metadata is **additive**. The original chunk text is never read or
  modified by the extractor. Extractors receive the chunk text as input
  and return metadata alongside it.
- Section-based naming (``section_management``, not ``has_management``).
  Each field describes the section the chunk *represents*, not a boolean
  property of the chunk. This is the language retrieval will use.

Excluded from Phase 6
---------------------
- ``previous_university_question`` — belongs to the question-bank layer,
  not textbook ingestion.
- ``frequently_asked`` — same; question-bank layer.

These will be addressed in a later phase when the question-bank layer is
designed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ----------------------------------------------------------------------
# Grouped metadata dataclasses
# ----------------------------------------------------------------------

@dataclass
class StructureMetadata:
    """What kind of structural element does this chunk represent?

    These are mutually non-exclusive (a chunk can be a table AND a
    diagram, for example). All fields are bools for v1 because the
    heuristic extractor only classifies the *presence* of a structural
    element. Future extractors may add richer typing.
    """

    section_definition: bool = False
    section_classification: bool = False
    section_flowchart: bool = False
    section_table: bool = False
    section_diagram: bool = False
    section_formula: bool = False
    section_conclusion: bool = False


@dataclass
class MedicalMetadata:
    """Which medical-section keywords are present in this chunk.

    Field names follow the *section* convention: ``section_management``
    means "this chunk contains management content", not "this chunk has
    a boolean property called management".
    """

    section_epidemiology: bool = False
    section_etiology: bool = False
    section_pathogenesis: bool = False
    section_risk_factors: bool = False
    section_clinical_features: bool = False
    section_diagnosis: bool = False
    section_differential_diagnosis: bool = False
    section_investigations: bool = False
    section_management: bool = False
    section_prevention: bool = False
    section_national_programme: bool = False
    section_medicolegal: bool = False
    section_statistics: bool = False


@dataclass
class ExamMetadata:
    """Exam-relevance signals extracted from the chunk.

    These are the *factual* exam-relevance signals that can be derived
    from textbook text alone. Per the Phase 6 directive,
    ``previous_university_question`` and ``frequently_asked`` are
    *excluded* — they belong to the question-bank layer, not textbook
    ingestion.
    """

    important_years: List[int] = field(default_factory=list)
    important_numbers: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class ChunkMetadata:
    """All metadata for a single chunk, grouped.

    This is the type every extractor returns. The retrieval layer reads
    it; the index layer flattens it. Nothing else in the application
    needs to know about ChromaDB's scalar constraint.
    """

    structure: StructureMetadata = field(default_factory=StructureMetadata)
    medical: MedicalMetadata = field(default_factory=MedicalMetadata)
    exam: ExamMetadata = field(default_factory=ExamMetadata)

    def to_dict(self) -> Dict[str, Any]:
        """Flat dict form. Useful for tests and debugging; the index
        layer uses its own ``flatten_for_chroma`` for the Chroma
        persistence contract."""
        d: Dict[str, Any] = {}
        d.update(asdict(self.structure))
        d.update(asdict(self.medical))
        d.update(asdict(self.exam))
        return d


# ----------------------------------------------------------------------
# Pluggable extractor interface
# ----------------------------------------------------------------------

class MetadataExtractor(ABC):
    """Abstract base class for metadata extractors.

    Subclasses must implement :meth:`extract`. The interface is
    deliberately tiny so LLM-based, hybrid, or rule-based extractors can
    be swapped without changing the ingestion workflow.

    The extractor receives the chunk text plus the surrounding context
    (chapter title, subject, book id, page numbers) and returns a
    :class:`ChunkMetadata`. The extractor **must not modify the chunk
    text** — it only inspects it.
    """

    @abstractmethod
    def extract(
        self,
        text: str,
        *,
        subject: str,
        book_id: str,
        chapter_title: str,
        page_start: int,
        page_end: int,
    ) -> ChunkMetadata:
        """Extract metadata from a single chunk.

        Parameters
        ----------
        text:
            The chunk's text. Treated as read-only by the extractor.
        subject, book_id, chapter_title, page_start, page_end:
            Provenance context, available to the extractor for context-
            aware decisions (e.g. a future LLM extractor could condition
            on the chapter title).

        Returns
        -------
        ChunkMetadata
            The extracted metadata. The default ``ChunkMetadata()`` is a
            valid (all-empty) result.
        """


# ----------------------------------------------------------------------
# Typed retrieval filter
# ----------------------------------------------------------------------

@dataclass
class MetadataFilter:
    """Typed filter for metadata-targeted retrieval.

    Each field is a list of section names to *include*. A chunk matches
    if any of its section flags in that group is True. Empty list = no
    constraint for that group.

    Example: ``MetadataFilter(structure=["section_table"])`` matches
    only chunks that are tables. ``MetadataFilter(medical=
    ["section_management", "section_treatment"])`` matches management or
    treatment chunks. An all-empty ``MetadataFilter()`` matches every
    chunk (i.e. no filter).

    The retrieval layer (``medrack.ingest.index.query``) translates this
    into the ChromaDB ``where`` clause. The rest of the application does
    not need to know about Chroma's filter syntax.
    """

    structure: List[str] = field(default_factory=list)
    medical: List[str] = field(default_factory=list)
    # Exam filters not exposed in v1: lists of years/numbers are hard to
    # express as a Chroma "where" clause without an index on every value.
    # Future phases can add exam filtering when the question-bank layer
    # is built.

    def is_empty(self) -> bool:
        return not self.structure and not self.medical


# ----------------------------------------------------------------------
# ChromaDB persistence boundary
# ----------------------------------------------------------------------

def flatten_for_chroma(meta: ChunkMetadata) -> Dict[str, Any]:
    """Convert grouped :class:`ChunkMetadata` into ChromaDB-safe scalars.

    ChromaDB requires metadata values to be JSON-compatible scalars
    (int, float, str, bool) or None. Lists must be comma-joined strings.
    This helper is the *only* place that knows about that constraint.
    All other code in the application uses the typed grouped form.
    """
    out: Dict[str, Any] = {}
    # Structure: all bools — pass through
    for k, v in asdict(meta.structure).items():
        out[k] = bool(v)
    # Medical: all bools — pass through
    for k, v in asdict(meta.medical).items():
        out[k] = bool(v)
    # Exam: lists → comma-joined strings; empty list → "" (a valid scalar)
    years = ",".join(str(y) for y in meta.exam.important_years)
    numbers = ",".join(meta.exam.important_numbers)
    keywords = ",".join(meta.exam.keywords)
    out["important_years"] = years
    out["important_numbers"] = numbers
    out["keywords"] = keywords
    return out


def filter_to_chroma_where(filt: MetadataFilter) -> Optional[Dict[str, Any]]:
    """Translate a :class:`MetadataFilter` into a ChromaDB ``where`` dict.

    Returns ``None`` for an empty filter (Chroma treats ``None`` as "no
    filter"). Otherwise returns a ``$or`` of ``$or``s across the
    requested section flags.

    Each individual section flag is itself a bool, so the inner clause
    is ``{"section_management": True}`` etc.
    """
    if filt.is_empty():
        return None

    groups: List[Dict[str, Any]] = []
    for name in filt.structure:
        groups.append({name: True})
    for name in filt.medical:
        groups.append({name: True})
    if len(groups) == 1:
        return groups[0]
    return {"$or": groups}


__all__ = [
    "StructureMetadata",
    "MedicalMetadata",
    "ExamMetadata",
    "ChunkMetadata",
    "MetadataExtractor",
    "MetadataFilter",
    "flatten_for_chroma",
    "filter_to_chroma_where",
]
