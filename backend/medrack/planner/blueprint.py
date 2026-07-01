"""Blueprint data model (Phase 8).

A :class:`Blueprint` is the structured output of the Planner. It is a
machine-readable contract between the Planner and the downstream
consumers (retrieval, writer). It is JSON-serializable so future
phases can pass it through APIs, persist it for debugging, or feed it
to a writer that wants a typed input.

The blueprint is *additive* with respect to the question: it does not
replace the question text, it annotates it. The writer still has the
question text; the blueprint tells the writer how to *organize* the
answer.

JSON contract
-------------
The :class:`BlueprintEncoder` produces a deterministic JSON string
(sorted keys, indent=2). The :class:`BlueprintDecoder` parses it
back. The format is versioned: ``schema_version: 1`` is the v1
contract. Future versions can be added by branching on
``schema_version`` in the decoder.

A blueprint serializes to::

    {
      "schema_version": 1,
      "subject": "psm",
      "marks": 10,
      "question_type": "theory",
      "target_word_count": 775,
      "sections": [
        {
          "name": "introduction",
          "category": "framing",
          "target_word_count": 115,
          "required": true,
          "metadata_section": null
        },
        ...
      ],
      "required_metadata_categories": ["section_management", ...]
    }

Design notes
------------
- Field names are lowercase, snake_case, no abbreviations. The schema
  is meant to be human-readable in logs and dashboards.
- ``required`` distinguishes sections that must be present (e.g.
  ``introduction``, ``conclusion``) from optional ones (e.g.
  ``classification`` — only included if relevant).
- ``metadata_section`` is the name of the :class:`ChunkMetadata`
  flag this section maps to (``section_management``,
  ``section_classification``, etc.) or ``None`` for framing sections
  (``introduction``, ``conclusion``) that have no chunk-metadata
  equivalent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = 1


class SectionCategory(str, Enum):
    """Coarse classification of blueprint sections.

    - ``STRUCTURE`` — chunk-level structural sections (table, diagram,
      flowchart, formula, definition, classification).
    - ``MEDICAL`` — medical-content sections (etiology, epidemiology,
      management, etc.).
    - ``FRAMING`` — sections that frame the answer (introduction,
      conclusion). These have no chunk-metadata equivalent.
    """

    STRUCTURE = "structure"
    MEDICAL = "medical"
    FRAMING = "framing"


@dataclass
class Section:
    """A single section in a blueprint.

    Attributes
    ----------
    name:
        Human-readable name: ``"introduction"``, ``"management"``,
        ``"conclusion"``, etc. Lowercase, snake_case.
    category:
        One of :class:`SectionCategory`. The Planner uses this to
        decide which chunks to retrieve and how to order the answer.
    target_word_count:
        The number of words the writer should aim for in this section.
        Sum of all sections' ``target_word_count`` equals
        ``Blueprint.target_word_count``.
    required:
        If True, the section must be present in the answer. The
        Planner marks ``introduction`` and ``conclusion`` as required;
        everything else is required only if included.
    metadata_section:
        The name of the :class:`ChunkMetadata` flag this section maps
        to (e.g. ``"section_management"``), or ``None`` for framing
        sections that have no chunk-metadata equivalent.
    """

    name: str
    category: SectionCategory
    target_word_count: int
    required: bool = False
    metadata_section: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Plain-dict form. Enums become their string value."""
        return {
            "name": self.name,
            "category": self.category.value
            if isinstance(self.category, SectionCategory)
            else self.category,
            "target_word_count": self.target_word_count,
            "required": self.required,
            "metadata_section": self.metadata_section,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Section":
        return cls(
            name=d["name"],
            category=SectionCategory(d["category"])
            if not isinstance(d["category"], SectionCategory)
            else d["category"],
            target_word_count=d["target_word_count"],
            required=d.get("required", False),
            metadata_section=d.get("metadata_section"),
        )


@dataclass
class Blueprint:
    """A structured answer plan for one question.

    The blueprint is the Planner's output. It is consumed downstream
    by retrieval (to bias section selection) and the writer (to
    organize the answer).

    Attributes
    ----------
    subject:
        The subject (e.g. ``"psm"``, ``"fmt"``). Same vocabulary as
        the ChromaDB collection names.
    marks:
        ``5`` or ``10`` for theory questions; ``None`` for MCQ.
    question_type:
        ``"theory"`` or ``"mcq"``. The Planner treats the two
        differently (MCQ blueprints have only one required section:
        the answer justification).
    target_word_count:
        Overall word count target. Sum of all section
        ``target_word_count`` should equal this value.
    sections:
        Ordered list of :class:`Section` objects. Order is the
        intended answer order.
    required_metadata_categories:
        Set of metadata section names the downstream retrieval
        should target. Computed by the Planner as the union of all
        sections' ``metadata_section`` fields (excluding ``None``).
    """

    subject: str
    marks: Optional[int]
    question_type: str
    target_word_count: int
    sections: List[Section] = field(default_factory=list)
    required_metadata_categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "subject": self.subject,
            "marks": self.marks,
            "question_type": self.question_type,
            "target_word_count": self.target_word_count,
            "sections": [s.to_dict() for s in self.sections],
            "required_metadata_categories": list(self.required_metadata_categories),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Blueprint":
        v = d.get("schema_version", 1)
        if v != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported blueprint schema_version: {v} "
                f"(expected {SCHEMA_VERSION})"
            )
        return cls(
            subject=d["subject"],
            marks=d.get("marks"),
            question_type=d["question_type"],
            target_word_count=d["target_word_count"],
            sections=[Section.from_dict(s) for s in d.get("sections", [])],
            required_metadata_categories=list(
                d.get("required_metadata_categories", [])
            ),
        )

    def to_json(self, indent: int = 2) -> str:
        """Deterministic JSON serialization (sorted keys)."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "Blueprint":
        return cls.from_dict(json.loads(s))


class BlueprintEncoder(json.JSONEncoder):
    """JSON encoder that knows about Blueprint, Section, SectionCategory.

    Use ``json.dumps(blueprint, cls=BlueprintEncoder)`` as an
    alternative to :meth:`Blueprint.to_json` when you need the full
    encoder for mixed-type data.
    """

    def default(self, o):
        if isinstance(o, Blueprint):
            return o.to_dict()
        if isinstance(o, Section):
            return o.to_dict()
        if isinstance(o, SectionCategory):
            return o.value
        return super().default(o)


def BlueprintDecoder(d: Dict[str, Any]) -> Blueprint:
    """Decode a Blueprint from a plain dict.

    The standard ``json.loads(...)`` returns plain dicts; this helper
    does the Blueprint-specific reconstruction. Equivalent to
    :meth:`Blueprint.from_dict`.
    """
    return Blueprint.from_dict(d)


__all__ = [
    "SCHEMA_VERSION",
    "Section",
    "SectionCategory",
    "Blueprint",
    "BlueprintEncoder",
    "BlueprintDecoder",
]
