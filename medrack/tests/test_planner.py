"""Tests for Phase 8: Planner / Blueprint.

Coverage:
  - blueprint.py: Section, Blueprint, JSON serialization, schema versioning
  - rules.py: section detection, ordering, capping, word allocation
  - planner.py: Planner ABC, DeterministicPlanner, plan_for_question,
    determinism, isolation, input validation
"""
from __future__ import annotations

import ast
import inspect
import json

from medrack.planner import (
    Blueprint,
    Section,
    SectionCategory,
    BlueprintEncoder,
    BlueprintDecoder,
    Planner,
    DeterministicPlanner,
    PlannerInput,
    plan_for_question,
)
from medrack.planner.rules import (
    MEDICAL_SECTION_ORDER,
    RulesEngine,
    SECTION_DISPLAY_NAMES,
    STRUCTURE_SECTION_ORDER,
)


# ----------------------------------------------------------------------
# blueprint.py: Section, Blueprint, JSON
# ----------------------------------------------------------------------

def test_section_to_from_dict_roundtrip():
    s = Section(
        name="management",
        category=SectionCategory.MEDICAL,
        target_word_count=200,
        required=True,
        metadata_section="section_management",
    )
    d = s.to_dict()
    s2 = Section.from_dict(d)
    assert s2.name == s.name
    assert s2.category == s.category
    assert s2.target_word_count == s.target_word_count
    assert s2.required == s.required
    assert s2.metadata_section == s.metadata_section


def test_section_category_serializes_as_string():
    s = Section(
        name="intro", category=SectionCategory.FRAMING,
        target_word_count=50, required=True, metadata_section=None,
    )
    d = s.to_dict()
    assert d["category"] == "framing"  # string, not enum
    # Round-trip
    s2 = Section.from_dict(d)
    assert s2.category == SectionCategory.FRAMING


def test_blueprint_to_from_dict_roundtrip():
    bp = Blueprint(
        subject="psm",
        marks=10,
        question_type="theory",
        target_word_count=775,
        sections=[
            Section(name="intro", category=SectionCategory.FRAMING,
                    target_word_count=100, required=True, metadata_section=None),
            Section(name="management", category=SectionCategory.MEDICAL,
                    target_word_count=500, required=True,
                    metadata_section="section_management"),
            Section(name="conclusion", category=SectionCategory.FRAMING,
                    target_word_count=175, required=True, metadata_section=None),
        ],
        required_metadata_categories=["section_management"],
    )
    d = bp.to_dict()
    bp2 = Blueprint.from_dict(d)
    assert bp2.subject == bp.subject
    assert bp2.marks == bp.marks
    assert len(bp2.sections) == len(bp.sections)
    assert bp2.required_metadata_categories == bp.required_metadata_categories


def test_blueprint_to_json_is_deterministic():
    """Same input -> identical JSON (sorted keys)."""
    bp = plan_for_question(
        question_text="Discuss management of TB.",
        subject="psm", marks=10, question_type="theory",
    )
    j1 = bp.to_json()
    j2 = bp.to_json()
    assert j1 == j2


def test_blueprint_json_includes_schema_version():
    bp = plan_for_question(
        question_text="Discuss management of TB.",
        subject="psm", marks=10, question_type="theory",
    )
    d = json.loads(bp.to_json())
    assert d["schema_version"] == 1


def test_blueprint_from_json_rejects_unknown_schema():
    d = {
        "schema_version": 99,
        "subject": "psm",
        "marks": 10,
        "question_type": "theory",
        "target_word_count": 775,
        "sections": [],
        "required_metadata_categories": [],
    }
    try:
        Blueprint.from_dict(d)
        assert False, "should have raised"
    except ValueError as e:
        assert "schema_version" in str(e)


def test_blueprint_encoder_handles_mixed_types():
    """BlueprintEncoder is the JSON-serializable form for any blueprint."""
    bp = plan_for_question(
        question_text="Discuss management of TB.",
        subject="psm", marks=10, question_type="theory",
    )
    s = json.dumps(bp, cls=BlueprintEncoder, indent=2)
    d = json.loads(s)
    assert d["schema_version"] == 1


# ----------------------------------------------------------------------
# rules.py: section detection + ordering + capping + word allocation
# ----------------------------------------------------------------------

def test_rules_engine_detects_management():
    e = RulesEngine()
    sections = e._detect_sections("Discuss the management of diabetes.")
    assert "section_management" in sections


def test_rules_engine_detects_multiple_sections():
    e = RulesEngine()
    sections = e._detect_sections(
        "Discuss the management, etiology, and epidemiology of TB."
    )
    assert "section_management" in sections
    assert "section_etiology" in sections
    assert "section_epidemiology" in sections


def test_rules_engine_no_sections_for_generic_question():
    e = RulesEngine()
    sections = e._detect_sections("What is health?")
    assert sections == []


def test_rules_engine_canonical_order():
    """Detection results are in canonical medical-answer order, not match order."""
    e = RulesEngine()
    # Management and etiology both match. Etiology matches first in
    # pattern order, but canonical medical-answer order puts
    # etiology (the cause) before management (the treatment).
    sections = e._detect_sections(
        "Discuss the management and etiology of diabetes."
    )
    # Both should be present
    assert "section_etiology" in sections
    assert "section_management" in sections
    # Etiology should come before management (canonical medical order:
    # cause first, then treatment)
    assert sections.index("section_etiology") < sections.index("section_management")


def test_rules_engine_5mark_caps_at_3():
    e = RulesEngine()
    # 5 sections detected, but 5-mark cap is 3
    sections = e._cap_sections(
        ["section_a", "section_b", "section_c", "section_d", "section_e"],
        marks=5,
    )
    assert len(sections) == 3


def test_rules_engine_10mark_caps_at_7():
    e = RulesEngine()
    # 9 sections, 10-mark cap is 7
    sections = e._cap_sections(
        [f"section_{i}" for i in range(9)],
        marks=10,
    )
    assert len(sections) == 7


def test_rules_engine_no_cap_for_unknown_marks():
    e = RulesEngine()
    # 9 sections, unknown marks -> max of (3, 7) = 7
    sections = e._cap_sections(
        [f"section_{i}" for i in range(9)],
        marks=None,
    )
    assert len(sections) == 7


def test_rules_engine_word_allocation_sums_to_target():
    """Sum of section target_word_counts equals target_word_count."""
    e = RulesEngine()
    target = 775
    sections = e._build_sections(
        ["section_management", "section_epidemiology", "section_etiology"],
        target,
    )
    assert sum(s.target_word_count for s in sections) == target


def test_rules_engine_word_allocation_5mark():
    e = RulesEngine()
    target = 475
    sections = e._build_sections(
        ["section_management", "section_etiology"],
        target,
    )
    assert sum(s.target_word_count for s in sections) == target
    # Introduction + conclusion are 15% + 10% = 25% of 475 = 118
    intro = next(s for s in sections if s.name == "introduction")
    conclusion = next(s for s in sections if s.name == "conclusion")
    assert intro.target_word_count == round(target * 0.15)
    assert conclusion.target_word_count == round(target * 0.10)


def test_rules_engine_word_allocation_with_no_sections():
    """Even with no detected sections, intro + conclusion get their share."""
    e = RulesEngine()
    target = 775
    sections = e._build_sections([], target)
    assert sum(s.target_word_count for s in sections) == target
    # Only intro and conclusion
    assert len(sections) == 2


def test_rules_engine_target_word_counts():
    e = RulesEngine()
    inp = PlannerInput(
        question_text="x", subject="psm", marks=10, question_type="theory",
    )
    assert e._target_word_count(inp) == 775
    inp.marks = 5
    assert e._target_word_count(inp) == 475


# ----------------------------------------------------------------------
# planner.py: Planner ABC, DeterministicPlanner, plan_for_question
# ----------------------------------------------------------------------

def test_planner_input_validation_empty_text():
    p = DeterministicPlanner()
    try:
        p.plan(PlannerInput(
            question_text="", subject="psm", marks=10, question_type="theory",
        ))
        assert False, "should have raised"
    except ValueError as e:
        assert "question_text" in str(e)


def test_planner_input_validation_empty_subject():
    p = DeterministicPlanner()
    try:
        p.plan(PlannerInput(
            question_text="x", subject="", marks=10, question_type="theory",
        ))
        assert False, "should have raised"
    except ValueError as e:
        assert "subject" in str(e)


def test_planner_input_validation_bad_question_type():
    p = DeterministicPlanner()
    try:
        p.plan(PlannerInput(
            question_text="x", subject="psm", marks=10,
            question_type="essay",  # not in VALID_QUESTION_TYPES
        ))
        assert False, "should have raised"
    except ValueError as e:
        assert "question_type" in str(e)


def test_planner_input_validation_bad_marks():
    p = DeterministicPlanner()
    try:
        p.plan(PlannerInput(
            question_text="x", subject="psm", marks=7, question_type="theory",
        ))
        assert False, "should have raised"
    except ValueError as e:
        assert "marks" in str(e)


def test_plan_for_question_5mark_management_question():
    bp = plan_for_question(
        question_text="Discuss the management of diabetes.",
        subject="psm", marks=5, question_type="theory",
    )
    assert bp.marks == 5
    assert bp.target_word_count == 475
    section_names = [s.name for s in bp.sections]
    assert "introduction" in section_names
    assert "conclusion" in section_names
    assert "management" in section_names
    assert "section_management" in bp.required_metadata_categories


def test_plan_for_question_10mark_complex_question():
    bp = plan_for_question(
        question_text=(
            "Discuss the management, etiology, and epidemiology of TB. "
            "Include classification and national programme."
        ),
        subject="psm", marks=10, question_type="theory",
    )
    assert bp.marks == 10
    assert bp.target_word_count == 775
    section_names = [s.name for s in bp.sections]
    assert "introduction" in section_names
    assert "conclusion" in section_names
    # Should include detected sections
    for expected in ["management", "etiology", "epidemiology",
                     "classification", "national programme"]:
        assert expected in section_names, f"missing {expected}"
    # All word counts sum to target
    assert sum(s.target_word_count for s in bp.sections) == 775


def test_plan_for_question_mcq_produces_minimal_blueprint():
    bp = plan_for_question(
        question_text="What is the treatment for X?",
        subject="psm", marks=None, question_type="mcq",
    )
    assert bp.question_type == "mcq"
    assert len(bp.sections) == 1
    assert bp.sections[0].name == "answer"


def test_planner_is_deterministic():
    """Same input -> same output. Critical for cache stability."""
    inp_kwargs = {
        "question_text": "Discuss the management and epidemiology of TB.",
        "subject": "psm",
        "marks": 10,
        "question_type": "theory",
    }
    bp1 = plan_for_question(**inp_kwargs)
    bp2 = plan_for_question(**inp_kwargs)
    assert bp1.to_dict() == bp2.to_dict()


def test_planner_does_not_call_llm():
    """The planner must not import or call any LLM."""
    import medrack.planner as p
    src = inspect.getsource(p)
    # Strip docstrings
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    cleaned = ast.unparse(tree)
    # The planner must not import from medrack.answer (which has the LLM client)
    assert "medrack.answer" not in cleaned
    # And must not import medrack.retrieval (retrieval implementation)
    assert "medrack.retrieval" not in cleaned


def test_planner_isolated_from_other_layers():
    """The planner must not import from answer/retrieval/ingest/bot/dashboard/benchmarks."""
    import medrack.planner as p
    src = inspect.getsource(p)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    cleaned = ast.unparse(tree)
    for forbidden in ["medrack.answer", "medrack.retrieval", "medrack.ingest",
                       "medrack.bot", "medrack.dashboard", "medrack.benchmarks"]:
        assert forbidden not in cleaned, f"planner imports from {forbidden}"


def test_planner_abc_subclassable():
    """A custom planner can subclass Planner and replace the implementation."""
    class CustomPlanner(Planner):
        def plan(self, inp):
            return Blueprint(
                subject=inp.subject,
                marks=inp.marks,
                question_type="theory",
                target_word_count=100,
                sections=[],
                required_metadata_categories=[],
            )
    bp = CustomPlanner().plan(PlannerInput(
        question_text="x", subject="psm", marks=10, question_type="theory",
    ))
    assert bp.target_word_count == 100
    assert bp.sections == []


def test_planner_includes_intro_and_conclusion_for_broad_question():
    """A question with no detected sections still gets intro + conclusion."""
    bp = plan_for_question(
        question_text="What is health?",
        subject="psm", marks=10, question_type="theory",
    )
    section_names = [s.name for s in bp.sections]
    assert "introduction" in section_names
    assert "conclusion" in section_names
    # And the word counts sum to target
    assert sum(s.target_word_count for s in bp.sections) == bp.target_word_count
