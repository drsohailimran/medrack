"""Tests for Phase 9: Blueprint Retrieval spec.

Coverage:
  - SectionRetrievalSpec: dataclass, to_dict/from_dict roundtrip
  - BlueprintRetrieval: dataclass, to_dict/from_dict, JSON roundtrip
  - build_blueprint_retrieval: deterministic, per-section specs, aggregate
    filter, evidence categories
  - Isolation: the blueprint_retrieval module imports nothing from
    answer/bot/dashboard/benchmarks (allowed: planner/ingest)
"""
from __future__ import annotations

import ast
import inspect
import json
from dataclasses import dataclass, field
from typing import List, Optional

from medrack.ingest.metadata import MetadataFilter, filter_to_chroma_where
from medrack.planner import (
    Blueprint,
    Section,
    SectionCategory,
    plan_for_question,
)
from medrack.retrieval import (
    BlueprintRetrieval,
    SectionRetrievalSpec,
    build_blueprint_retrieval,
    PRIORITY_REQUIRED,
    PRIORITY_RECOMMENDED,
    PRIORITY_OPTIONAL,
    DEFAULT_MIN_CHUNKS,
    DEFAULT_MAX_CHUNKS,
)


# ----------------------------------------------------------------------
# SectionRetrievalSpec: dataclass
# ----------------------------------------------------------------------

def test_section_retrieval_spec_to_from_dict_roundtrip():
    spec = SectionRetrievalSpec(
        section_name="management",
        metadata_filter=MetadataFilter(medical=["section_management"]),
        priority=PRIORITY_REQUIRED,
        min_chunks=1,
        max_chunks=3,
        evidence_category="section_management",
    )
    d = spec.to_dict()
    spec2 = SectionRetrievalSpec.from_dict(d)
    assert spec2.section_name == spec.section_name
    assert spec2.metadata_filter.medical == ["section_management"]
    assert spec2.priority == spec.priority
    assert spec2.min_chunks == spec.min_chunks
    assert spec2.max_chunks == spec.max_chunks
    assert spec2.evidence_category == spec.evidence_category


def test_section_retrieval_spec_framing_section_has_no_filter():
    """introduction/conclusion have no chunk-metadata equivalent."""
    spec = SectionRetrievalSpec(
        section_name="introduction",
        metadata_filter=MetadataFilter(),
        priority=PRIORITY_REQUIRED,
        min_chunks=1,
        max_chunks=3,
        evidence_category=None,
    )
    d = spec.to_dict()
    assert d["metadata_filter"] == {"structure": [], "medical": []}
    assert d["evidence_category"] is None


# ----------------------------------------------------------------------
# BlueprintRetrieval: dataclass + JSON
# ----------------------------------------------------------------------

def _make_blueprint_retrieval() -> BlueprintRetrieval:
    return BlueprintRetrieval(
        subject="psm",
        marks=10,
        question_type="theory",
        target_word_count=775,
        section_specs=[
            SectionRetrievalSpec(
                section_name="introduction",
                metadata_filter=MetadataFilter(),
                priority=PRIORITY_REQUIRED,
                min_chunks=1, max_chunks=3,
                evidence_category=None,
            ),
            SectionRetrievalSpec(
                section_name="management",
                metadata_filter=MetadataFilter(medical=["section_management"]),
                priority=PRIORITY_REQUIRED,
                min_chunks=1, max_chunks=3,
                evidence_category="section_management",
            ),
            SectionRetrievalSpec(
                section_name="conclusion",
                metadata_filter=MetadataFilter(),
                priority=PRIORITY_REQUIRED,
                min_chunks=1, max_chunks=3,
                evidence_category=None,
            ),
        ],
        aggregate_metadata_filter=MetadataFilter(medical=["section_management"]),
        evidence_categories=["section_management"],
    )


def test_blueprint_retrieval_to_from_dict_roundtrip():
    br = _make_blueprint_retrieval()
    d = br.to_dict()
    br2 = BlueprintRetrieval.from_dict(d)
    assert br2.subject == br.subject
    assert br2.marks == br.marks
    assert br2.question_type == br.question_type
    assert br2.target_word_count == br.target_word_count
    assert len(br2.section_specs) == len(br.section_specs)
    assert br2.evidence_categories == br.evidence_categories


def test_blueprint_retrieval_json_roundtrip():
    br = _make_blueprint_retrieval()
    j = br.to_json()
    d = json.loads(j)
    assert d["schema_version"] == 1
    br2 = BlueprintRetrieval.from_json(j)
    assert br2.to_dict() == br.to_dict()


def test_blueprint_retrieval_rejects_unknown_schema():
    d = {
        "schema_version": 99,
        "subject": "psm",
        "marks": 10,
        "question_type": "theory",
        "target_word_count": 775,
        "section_specs": [],
        "aggregate_metadata_filter": {"structure": [], "medical": []},
        "evidence_categories": [],
    }
    try:
        BlueprintRetrieval.from_dict(d)
        assert False, "should have raised"
    except ValueError as e:
        assert "schema_version" in str(e)


def test_blueprint_retrieval_to_json_is_deterministic():
    br = _make_blueprint_retrieval()
    assert br.to_json() == br.to_json()


# ----------------------------------------------------------------------
# build_blueprint_retrieval: construction
# ----------------------------------------------------------------------

def test_build_from_planner_blueprint_management():
    """A management question gets a per-section management filter."""
    bp = plan_for_question(
        question_text="Discuss the management of diabetes.",
        subject="psm", marks=10, question_type="theory",
    )
    br = build_blueprint_retrieval(bp)
    section_names = [s.section_name for s in br.section_specs]
    # Same order as the Planner blueprint
    assert section_names == [s.name for s in bp.sections]
    # Management section has a management filter
    mgmt_spec = next(s for s in br.section_specs if s.section_name == "management")
    assert mgmt_spec.metadata_filter.medical == ["section_management"]
    assert mgmt_spec.evidence_category == "section_management"
    assert mgmt_spec.priority == PRIORITY_REQUIRED
    assert mgmt_spec.min_chunks == DEFAULT_MIN_CHUNKS
    assert mgmt_spec.max_chunks == DEFAULT_MAX_CHUNKS


def test_build_from_planner_blueprint_aggregate_filter_unions_sections():
    """Aggregate filter is the union of all per-section medical filters."""
    bp = plan_for_question(
        question_text=(
            "Discuss the management, etiology, and epidemiology of TB. "
            "Include classification."
        ),
        subject="psm", marks=10, question_type="theory",
    )
    br = build_blueprint_retrieval(bp)
    # Aggregate filter should have all detected medical sections
    detected = bp.required_metadata_categories
    for cat in detected:
        assert cat in br.aggregate_metadata_filter.medical or \
               cat in br.aggregate_metadata_filter.structure, \
               f"missing {cat} in aggregate filter"
    # Evidence categories = the same set
    assert set(br.evidence_categories) == set(detected)


def test_build_from_planner_blueprint_evidence_categories_deduplicated():
    """Evidence categories are deduplicated."""
    bp = plan_for_question(
        question_text=(
            "Discuss the management and prevention of TB. "
            "Also discuss the management of complications."
        ),
        subject="psm", marks=10, question_type="theory",
    )
    br = build_blueprint_retrieval(bp)
    # 'section_management' should appear at most once
    assert br.evidence_categories.count("section_management") <= 1


def test_build_from_planner_blueprint_framing_sections_have_no_filter():
    """introduction/conclusion sections have no metadata filter."""
    bp = plan_for_question(
        question_text="What is health?",
        subject="psm", marks=10, question_type="theory",
    )
    br = build_blueprint_retrieval(bp)
    for spec in br.section_specs:
        if spec.section_name in ("introduction", "conclusion"):
            assert spec.metadata_filter.is_empty()
            assert spec.evidence_category is None


def test_build_preserves_planner_section_order():
    """The Blueprint retrieval spec preserves the Planner's section order."""
    bp = plan_for_question(
        question_text=(
            "Discuss the management, etiology, and epidemiology of TB."
        ),
        subject="psm", marks=10, question_type="theory",
    )
    br = build_blueprint_retrieval(bp)
    assert [s.section_name for s in br.section_specs] == [s.name for s in bp.sections]


def test_build_does_not_modify_planner_blueprint():
    """The Planner's Blueprint is not mutated by build_blueprint_retrieval."""
    bp = plan_for_question(
        question_text="Discuss the management of diabetes.",
        subject="psm", marks=10, question_type="theory",
    )
    snapshot = bp.to_dict()
    _ = build_blueprint_retrieval(bp)
    assert bp.to_dict() == snapshot


def test_build_is_deterministic():
    """Same Planner blueprint -> same Blueprint retrieval spec."""
    bp = plan_for_question(
        question_text="Discuss the management of diabetes.",
        subject="psm", marks=10, question_type="theory",
    )
    br1 = build_blueprint_retrieval(bp)
    br2 = build_blueprint_retrieval(bp)
    assert br1.to_dict() == br2.to_dict()


# ----------------------------------------------------------------------
# Duck typing: build_blueprint_retrieval accepts any compatible object
# ----------------------------------------------------------------------

def test_build_accepts_duck_typed_blueprint():
    """The function accepts any object with the right shape, not just Blueprint."""

    @dataclass
    class FakeSection:
        name: str
        required: bool
        metadata_section: Optional[str]

    @dataclass
    class FakeBlueprint:
        subject: str = "psm"
        marks: int = 10
        question_type: str = "theory"
        target_word_count: int = 775
        sections: List[FakeSection] = field(default_factory=lambda: [
            FakeSection(name="introduction", required=True, metadata_section=None),
            FakeSection(name="management", required=True, metadata_section="section_management"),
            FakeSection(name="conclusion", required=True, metadata_section=None),
        ])
        required_metadata_categories: List[str] = field(default_factory=lambda: ["section_management"])

    br = build_blueprint_retrieval(FakeBlueprint())
    assert br.subject == "psm"
    assert len(br.section_specs) == 3
    assert br.evidence_categories == ["section_management"]


def test_build_handles_no_sections():
    """A blueprint with only framing sections produces a valid empty spec."""

    @dataclass
    class FakeBlueprint:
        subject: str = "psm"
        marks: int = 10
        question_type: str = "theory"
        target_word_count: int = 775
        sections: List = field(default_factory=list)
        required_metadata_categories: List[str] = field(default_factory=list)

    br = build_blueprint_retrieval(FakeBlueprint())
    assert br.section_specs == []
    assert br.evidence_categories == []
    assert br.aggregate_metadata_filter.is_empty()


# ----------------------------------------------------------------------
# Integration with the Planner + JSON pipeline
# ----------------------------------------------------------------------

def test_full_pipeline_planner_to_blueprint_retrieval_to_json():
    """End-to-end: planner -> blueprint retrieval -> JSON -> reload."""
    bp = plan_for_question(
        question_text=(
            "Discuss the management, etiology, and epidemiology of TB. "
            "Include classification."
        ),
        subject="psm", marks=10, question_type="theory",
    )
    br = build_blueprint_retrieval(bp)
    j = br.to_json()
    br2 = BlueprintRetrieval.from_json(j)
    assert br2.to_dict() == br.to_dict()


# ----------------------------------------------------------------------
# Aggregate filter translates to Chroma where clause correctly
# ----------------------------------------------------------------------

def test_aggregate_filter_translates_to_chroma_where():
    """The aggregate filter is usable as a Chroma where-clause filter."""
    bp = plan_for_question(
        question_text="Discuss the management and epidemiology of TB.",
        subject="psm", marks=10, question_type="theory",
    )
    br = build_blueprint_retrieval(bp)
    where = filter_to_chroma_where(br.aggregate_metadata_filter)
    # Should be a $or clause since there are 2 medical sections
    assert where is not None
    assert "$or" in where
    cats_in_or = [list(d.keys())[0] for d in where["$or"]]
    assert "section_management" in cats_in_or
    assert "section_epidemiology" in cats_in_or


# ----------------------------------------------------------------------
# Isolation (the spec is independent of the retrieval engine)
# ----------------------------------------------------------------------

def test_blueprint_retrieval_isolated_from_forbidden_layers():
    """The blueprint_retrieval module does not import from answer/bot/dashboard/benchmarks."""
    src = inspect.getsource(__import__("medrack.retrieval.blueprint_retrieval", fromlist=["*"]))
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    cleaned = ast.unparse(tree)
    for forbidden in ["medrack.answer", "medrack.bot", "medrack.dashboard", "medrack.benchmarks"]:
        assert forbidden not in cleaned, (
            f"blueprint_retrieval imports from {forbidden}"
        )


def test_blueprint_retrieval_does_not_perform_retrieval():
    """The blueprint_retrieval module must not call ingest.index or any retrieval fn."""
    src = inspect.getsource(__import__("medrack.retrieval.blueprint_retrieval", fromlist=["*"]))
    # No references to query() or vector index
    assert "ingest.index" not in src or "ingest.index" in "from medrack.ingest.metadata import"
    # The only ingest import should be for metadata
    assert "from medrack.ingest.metadata" in src
    # The only retrieval import should be local
    assert "from medrack.retrieval" not in src
