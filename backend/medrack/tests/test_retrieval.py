"""Tests for Phase 7: adaptive retrieval layer.

Coverage:
  - strategy.py: IdentityStrategy, AdaptiveStrategy, RetrievalPlan
  - analyzer.py: QuestionAnalyzer, QuestionAnalysis
  - reranker.py: MetadataBoostReranker
  - engine.py: RetrievalEngine, end-to-end pipeline
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, "/home/sohail/.hermes/medrack")

from medrack.ingest.chapter import Chapter
from medrack.ingest.chunk import chunk_pages
from medrack.ingest.extractors import RegexMetadataExtractor
from medrack.ingest.index import index_chunks
from medrack.ingest.metadata import (
    ChunkMetadata, MedicalMetadata, StructureMetadata,
    MetadataFilter,
)
from medrack.retrieval.analyzer import QuestionAnalysis, QuestionAnalyzer
from medrack.retrieval.engine import RetrievalEngine, retrieve_for_question
from medrack.retrieval.reranker import MetadataBoostReranker
from medrack.retrieval.strategy import (
    AdaptiveStrategy, IdentityStrategy, RetrievalPlan, RetrievalStrategy,
)


# ----------------------------------------------------------------------
# analyzer.py
# ----------------------------------------------------------------------

def test_analyzer_extracts_marks_from_question_dict():
    a = QuestionAnalyzer()
    analysis = a.analyze({"question_text": "Discuss diabetes.", "marks": 10})
    assert analysis.marks == 10


def test_analyzer_uses_explicit_marks_parameter():
    a = QuestionAnalyzer()
    analysis = a.analyze({"question_text": "Discuss diabetes."}, marks=5)
    assert analysis.marks == 5


def test_analyzer_marks_none_when_missing():
    a = QuestionAnalyzer()
    analysis = a.analyze({"question_text": "X"})
    assert analysis.marks is None


def test_analyzer_detects_management_section():
    a = QuestionAnalyzer()
    analysis = a.analyze({
        "question_text": "Discuss the management of diabetes mellitus.",
        "marks": 10,
    })
    assert "section_management" in analysis.target_sections


def test_analyzer_detects_multiple_sections():
    a = QuestionAnalyzer()
    analysis = a.analyze({
        "question_text": "Discuss the management and epidemiology of TB.",
        "marks": 10,
    })
    assert "section_management" in analysis.target_sections
    assert "section_epidemiology" in analysis.target_sections


def test_analyzer_detects_structural_sections():
    a = QuestionAnalyzer()
    analysis = a.analyze({
        "question_text": "Describe the classification of diabetes.",
        "marks": 10,
    })
    assert "section_classification" in analysis.target_sections


def test_analyzer_no_sections_detected():
    a = QuestionAnalyzer()
    analysis = a.analyze({"question_text": "What is diabetes?"})
    assert analysis.target_sections == []


def test_analyzer_caps_too_many_sections():
    a = QuestionAnalyzer()
    text = (
        "Discuss the management, etiology, pathogenesis, epidemiology, "
        "prevention, and diagnosis of diabetes."
    )
    analysis = a.analyze({"question_text": text})
    assert len(analysis.target_sections) <= a.MAX_SECTIONS


def test_analyzer_preserves_raw_text():
    a = QuestionAnalyzer()
    analysis = a.analyze({"question_text": "What is diabetes?"})
    assert analysis.raw_text == "What is diabetes?"


# ----------------------------------------------------------------------
# strategy.py
# ----------------------------------------------------------------------

def test_identity_strategy_returns_top_k_8():
    s = IdentityStrategy()
    plan = s.plan(QuestionAnalysis(marks=10, target_sections=["section_management"]))
    assert plan.top_k == 8
    assert plan.metadata_filter.is_empty()


def test_identity_strategy_ignores_marks():
    """Identity strategy preserves v0 behavior regardless of marks."""
    s = IdentityStrategy()
    for marks in (5, 10, None, 0):
        plan = s.plan(QuestionAnalysis(marks=marks))
        assert plan.top_k == 8


def test_adaptive_strategy_5_mark_returns_top_k_5():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(marks=5))
    assert plan.top_k == 5


def test_adaptive_strategy_10_mark_returns_top_k_8():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(marks=10))
    assert plan.top_k == 8


def test_adaptive_strategy_unknown_marks_defaults_to_8():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(marks=None))
    assert plan.top_k == 8


def test_adaptive_strategy_no_sections_no_filter():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(marks=10, target_sections=[]))
    assert plan.metadata_filter.is_empty()


def test_adaptive_strategy_single_medical_section_filter():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(marks=10, target_sections=["section_management"]))
    assert plan.metadata_filter.medical == ["section_management"]
    assert plan.metadata_filter.structure == []


def test_adaptive_strategy_two_sections_kept():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(
        marks=10,
        target_sections=["section_management", "section_epidemiology"],
    ))
    assert "section_management" in plan.metadata_filter.medical
    assert "section_epidemiology" in plan.metadata_filter.medical


def test_adaptive_strategy_too_many_sections_drops_filter():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(
        marks=10,
        target_sections=["section_a", "section_b", "section_c"],
    ))
    assert plan.metadata_filter.is_empty()


def test_adaptive_strategy_splits_structure_and_medical():
    s = AdaptiveStrategy()
    plan = s.plan(QuestionAnalysis(
        marks=10,
        target_sections=["section_management", "section_table"],
    ))
    assert "section_management" in plan.metadata_filter.medical
    assert "section_table" in plan.metadata_filter.structure


# ----------------------------------------------------------------------
# reranker.py
# ----------------------------------------------------------------------

def test_reranker_no_analysis_returns_input_unchanged():
    r = MetadataBoostReranker()
    out = r.rerank([{"id": "a", "text": "x", "metadata": {}, "distance": 1.0}], QuestionAnalysis(marks=10))
    assert out == [{"id": "a", "text": "x", "metadata": {}, "distance": 1.0}]


def test_reranker_boosts_matching_chunk():
    r = MetadataBoostReranker(boost_factor=0.5)  # 2x boost
    out = r.rerank(
        [
            {"id": "match", "text": "x", "metadata": {"section_management": True}, "distance": 1.0},
            {"id": "none",  "text": "y", "metadata": {"section_management": False}, "distance": 0.9},
        ],
        QuestionAnalysis(marks=10, target_sections=["section_management"]),
    )
    # Matching chunk's distance was halved (1.0 * 0.5 = 0.5), so it ranks first
    assert out[0]["id"] == "match"
    assert out[0]["distance"] == 0.5
    assert out[1]["id"] == "none"
    assert out[1]["distance"] == 0.9


def test_reranker_multi_match_compound_boost():
    """A chunk matching 2 sections should get a stronger boost than 1 match."""
    r = MetadataBoostReranker(boost_factor=0.5)
    out = r.rerank(
        [
            {"id": "double", "text": "x", "metadata": {
                "section_management": True, "section_epidemiology": True,
            }, "distance": 1.0},
            {"id": "single", "text": "y", "metadata": {
                "section_management": True, "section_epidemiology": False,
            }, "distance": 1.0},
        ],
        QuestionAnalysis(marks=10, target_sections=[
            "section_management", "section_epidemiology",
        ]),
    )
    # double: 1.0 * 0.5^2 = 0.25; single: 1.0 * 0.5 = 0.5
    assert out[0]["id"] == "double"
    assert out[0]["distance"] == 0.25
    assert out[1]["id"] == "single"
    assert out[1]["distance"] == 0.5


def test_reranker_does_not_mutate_input():
    r = MetadataBoostReranker()
    inp = [
        {"id": "a", "text": "x", "metadata": {"section_management": True}, "distance": 1.0},
    ]
    snapshot = list(inp)
    r.rerank(inp, QuestionAnalysis(marks=10, target_sections=["section_management"]))
    assert inp == snapshot


def test_reranker_handles_none_distance():
    """A chunk with no distance (Chroma without distance fn) still gets reordered."""
    r = MetadataBoostReranker()
    out = r.rerank(
        [
            {"id": "match", "text": "x", "metadata": {"section_management": True}, "distance": None},
            {"id": "none",  "text": "y", "metadata": {"section_management": False}, "distance": None},
        ],
        QuestionAnalysis(marks=10, target_sections=["section_management"]),
    )
    # Matching chunk should rank first even with no distance
    assert out[0]["id"] == "match"


def test_reranker_rejects_invalid_boost_factor():
    import pytest
    with pytest.raises(ValueError):
        MetadataBoostReranker(boost_factor=1.5)  # > 1.0
    with pytest.raises(ValueError):
        MetadataBoostReranker(boost_factor=0.0)  # == 0.0


# ----------------------------------------------------------------------
# engine.py
# ----------------------------------------------------------------------

def _build_corpus_chunks():
    """Build a small corpus of chunks with varied metadata."""
    ext = RegexMetadataExtractor()

    # Chunk about management
    mgmt_text = "Management: Diabetes is treated with metformin. Lifestyle modification is key. The standard drug regimen is metformin 500mg."
    mgmt_chunks = chunk_pages(
        [{"page_num": 1, "method": "text", "text": mgmt_text, "char_count": len(mgmt_text)}],
        [Chapter("DM", 1, 1, 0.5)],
        "psm", "b1", extractor=ext,
    )

    # Chunk about epidemiology
    epi_text = "Epidemiology: The prevalence of diabetes is 8% in India. The incidence rate has been rising since 2000. The standard incidence is 1,200,000 per year."
    epi_chunks = chunk_pages(
        [{"page_num": 2, "method": "text", "text": epi_text, "char_count": len(epi_text)}],
        [Chapter("DM", 2, 2, 0.5)],
        "psm", "b2", extractor=ext,
    )

    # Chunk about classification
    class_text = "Classification: Diabetes is classified into Type 1 and Type 2. Stage I is insulin-dependent. The categories are well-defined."
    class_chunks = chunk_pages(
        [{"page_num": 3, "method": "text", "text": class_text, "char_count": len(class_text)}],
        [Chapter("DM", 3, 3, 0.5)],
        "psm", "b3", extractor=ext,
    )

    # Unrelated chunk
    other_text = "Definition: Diabetes is a chronic condition. " + ("X " * 800)
    other_chunks = chunk_pages(
        [{"page_num": 4, "method": "text", "text": other_text, "char_count": len(other_text)}],
        [Chapter("DM", 4, 4, 0.5)],
        "psm", "b4", extractor=ext,
    )

    return mgmt_chunks + epi_chunks + class_chunks + other_chunks


def test_engine_end_to_end_5_mark():
    """5-mark question should retrieve fewer chunks than 10-mark."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        chunks = _build_corpus_chunks()
        for c in chunks:
            c.embedding = [float(i) / 10 for i in range(8)]  # uniform embedding
        index_chunks(chunks, "psm")

        engine = RetrievalEngine()
        result = engine.retrieve(
            question={
                "qid": "q001",
                "question_text": "Discuss the management of diabetes.",
            },
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=5,
        )
        # 5-mark -> top_k=5
        assert result.top_k == 5
        assert len(result.chunks) <= 5


def test_engine_end_to_end_10_mark():
    """10-mark question should retrieve 8 chunks."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        chunks = _build_corpus_chunks()
        for c in chunks:
            c.embedding = [float(i) / 10 for i in range(8)]
        index_chunks(chunks, "psm")

        engine = RetrievalEngine()
        result = engine.retrieve(
            question={
                "qid": "q001",
                "question_text": "Discuss the management of diabetes.",
            },
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        # 10-mark -> top_k=8
        assert result.top_k == 8


def test_engine_reranker_boosts_matching_chunk():
    """A management question should put the management chunk first."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        chunks = _build_corpus_chunks()
        # Use unique embeddings to control ranking deterministically
        for i, c in enumerate(chunks):
            c.embedding = [float(i)] + [0.0] * 7
        index_chunks(chunks, "psm")

        engine = RetrievalEngine()
        result = engine.retrieve(
            question={
                "qid": "q001",
                "question_text": "Discuss the management of diabetes.",
            },
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        # The management chunk (b1) should be boosted to the top
        top_book = result.chunks[0]["metadata"]["book_id"]
        assert top_book == "b1", f"expected b1, got {top_book}"


def test_engine_module_helper():
    """retrieve_for_question is a thin wrapper around the default engine."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        chunks = _build_corpus_chunks()
        for c in chunks:
            c.embedding = [0.0] * 8
        index_chunks(chunks, "psm")

        result = retrieve_for_question(
            question={
                "qid": "q001",
                "question_text": "Discuss the management of diabetes.",
            },
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        assert result.top_k == 8
        assert result.analysis.marks == 10


def test_engine_returns_retrieval_result_with_diagnostics():
    """The result includes retrieval_latency and rerank_latency for benchmarking."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        chunks = _build_corpus_chunks()
        for c in chunks:
            c.embedding = [0.0] * 8
        index_chunks(chunks, "psm")

        result = retrieve_for_question(
            question={"qid": "q001", "question_text": "X"},
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        assert result.retrieval_latency_seconds >= 0
        assert result.rerank_latency_seconds >= 0
        assert isinstance(result.analysis, QuestionAnalysis)


def test_engine_too_many_sections_uses_no_filter():
    """A question matching many sections should not over-constrain the filter."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        chunks = _build_corpus_chunks()
        for c in chunks:
            c.embedding = [0.0] * 8
        index_chunks(chunks, "psm")

        engine = RetrievalEngine()
        result = engine.retrieve(
            question={
                "qid": "q001",
                "question_text": (
                    "Discuss the management, etiology, pathogenesis, "
                    "epidemiology, prevention, and diagnosis of diabetes."
                ),
            },
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        # The analyzer caps to MAX_SECTIONS, so the filter may or may
        # not be empty depending on the cap. The strategy's
        # MAX_SECTIONS_FOR_FILTER is 2, so 4+ sections -> no filter.
        assert result.metadata_filter_active is False


def test_engine_isolated_from_answer_pipeline():
    """The retrieval layer must not import from answer/bot/dashboard/benchmarks."""
    import medrack.retrieval as r
    import ast
    import inspect
    for name in ["strategy", "analyzer", "reranker", "engine"]:
        mod = getattr(r, name)
        src = inspect.getsource(mod)
        # Strip docstrings (which can mention future phases)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    node.body = node.body[1:] or [ast.Pass()]
        cleaned_src = ast.unparse(tree)
        for forbidden in ["medrack.answer", "medrack.bot", "medrack.dashboard", "medrack.benchmarks"]:
            assert forbidden not in cleaned_src, (
                f"{name} imports from {forbidden}"
            )
