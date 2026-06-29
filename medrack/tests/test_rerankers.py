"""Tests for Phase 10: Reranker interface (generic) + HeuristicReranker (v1).

Coverage:
  - rerankers.py: Reranker ABC, HeuristicReranker (v1), IdentityReranker,
    truncate_top_n
  - engine.py: RetrievalEngine now has a semantic_reranker parameter
    (default IdentityReranker) and applies it after the metadata-boost
    reranker
  - isolation: no imports from answer/bot/dashboard/benchmarks
  - public interface stability: the Reranker ABC is future-proof for
    CrossEncoder, BGE, and other semantic rerankers
"""
from __future__ import annotations

import ast
import inspect
import os
import tempfile

from medrack.ingest.chunk import chunk_pages
from medrack.ingest.chapter import Chapter
from medrack.ingest.extractors import RegexMetadataExtractor
from medrack.ingest.index import index_chunks
from medrack.retrieval import (
    HeuristicReranker,
    IdentityReranker,
    RetrievalEngine,
    SemanticReranker as Reranker,  # Phase 10 generic Reranker interface
    retrieve_for_question,
    truncate_top_n,
)


def _make_chunk(id_: str, text: str, metadata: dict | None = None, distance: float | None = None):
    return {
        "id": id_,
        "text": text,
        "metadata": metadata or {},
        "distance": distance,
    }


# ----------------------------------------------------------------------
# rerankers.py: ABC
# ----------------------------------------------------------------------

def test_reranker_is_abstract():
    """Reranker is an ABC; instantiating it raises."""
    import pytest
    with pytest.raises(TypeError):
        Reranker()  # type: ignore


def test_subclass_implementation_works():
    """A custom implementation can subclass and implement rerank."""
    class MyReranker(Reranker):
        def rerank(self, *, question, chunks, blueprint_spec=None, top_n=None):
            return chunks[::-1]  # reverse

    rr = MyReranker()
    chunks = [_make_chunk("a", "x"), _make_chunk("b", "y")]
    out = rr.rerank(question="x", chunks=chunks)
    assert out[0]["id"] == "b"
    assert out[1]["id"] == "a"


# ----------------------------------------------------------------------
# HeuristicReranker
# ----------------------------------------------------------------------

def test_heuristic_reranker_empty_input():
    rr = HeuristicReranker()
    assert rr.rerank(question="x", chunks=[]) == []


def test_heuristic_reranker_preserves_chunk_ids():
    """The reranker must preserve chunk identities (no rewriting)."""
    rr = HeuristicReranker()
    chunks = [
        _make_chunk("a", "Management: diabetes is treated with metformin."),
        _make_chunk("b", "Epidemiology: prevalence is rising."),
    ]
    out = rr.rerank(question="Discuss the management of diabetes.", chunks=chunks)
    assert {c["id"] for c in out} == {"a", "b"}


def test_heuristic_reranker_does_not_modify_input():
    rr = HeuristicReranker()
    chunks = [
        _make_chunk("a", "Management: diabetes is treated with metformin."),
    ]
    snapshot = list(chunks)
    rr.rerank(question="Discuss the management of diabetes.", chunks=chunks)
    assert chunks == snapshot


def test_heuristic_reranker_never_modifies_chunk_contents():
    """The chunk text must be unchanged after reranking."""
    rr = HeuristicReranker()
    chunks = [
        _make_chunk("a", "Original text content.", {}),
        _make_chunk("b", "Different original text.", {}),
    ]
    out = rr.rerank(question="x", chunks=chunks)
    for orig, reranked in zip(chunks, out):
        assert orig["text"] == reranked["text"]


def test_heuristic_reranker_preserves_metadata():
    """The chunk metadata must be unchanged after reranking."""
    rr = HeuristicReranker()
    chunks = [
        _make_chunk("a", "x", {"section_management": True, "page": 1}),
        _make_chunk("b", "y", {"section_epidemiology": True, "page": 2}),
    ]
    out = rr.rerank(question="x", chunks=chunks)
    for orig, reranked in zip(chunks, out):
        for k, v in orig["metadata"].items():
            assert reranked["metadata"].get(k) == v


def test_heuristic_reranker_keyword_boost():
    """A chunk with more question keywords should rank higher."""
    rr = HeuristicReranker()
    chunks = [
        _make_chunk("no_match", "Lorem ipsum dolor sit amet.", {}),
        _make_chunk("two_kw", "Management: diabetes is treated.", {}),
    ]
    out = rr.rerank(question="Discuss the management of diabetes.", chunks=chunks)
    assert out[0]["id"] == "two_kw"
    assert out[1]["id"] == "no_match"


def test_heuristic_reranker_section_boost():
    """A chunk matching a required metadata category gets a section boost."""
    rr = HeuristicReranker()

    class MockBlueprint:
        required_metadata_categories = ["section_management"]

    chunks = [
        _make_chunk("no_meta", "Diabetes is a chronic condition.", {}),
        _make_chunk("with_meta", "Diabetes is treated with metformin.",
                    {"section_management": True}),
    ]
    out = rr.rerank(
        question="Discuss the management of diabetes.",
        chunks=chunks,
        blueprint_spec=MockBlueprint(),
    )
    # The chunk with the section_management flag should rank first
    assert out[0]["id"] == "with_meta"
    assert out[0]["_rerank_section_match"] is True
    assert out[1]["id"] == "no_meta"


def test_heuristic_reranker_combines_signals():
    """Section + keyword signals combine to boost a chunk."""
    rr = HeuristicReranker()

    class MockBlueprint:
        required_metadata_categories = ["section_management"]

    chunks = [
        # No signals
        _make_chunk("none", "Lorem ipsum.", {}),
        # Section only
        _make_chunk("section_only", "Lorem ipsum.", {"section_management": True}),
        # Keyword only
        _make_chunk("keyword_only", "Management: diabetes is treated.", {}),
        # Both
        _make_chunk("both", "Management: diabetes is treated.",
                    {"section_management": True}),
    ]
    out = rr.rerank(
        question="Discuss the management of diabetes.",
        chunks=chunks,
        blueprint_spec=MockBlueprint(),
    )
    # "both" should rank first, "none" should rank last
    assert out[0]["id"] == "both"
    assert out[-1]["id"] == "none"


def test_heuristic_reranker_annotates_score():
    """The reranker adds _rerank_score for observability."""
    rr = HeuristicReranker()
    chunks = [_make_chunk("a", "Management: diabetes is treated.")]
    out = rr.rerank(question="Discuss the management of diabetes.", chunks=chunks)
    assert "_rerank_score" in out[0]
    assert "_rerank_keyword_matches" in out[0]
    assert "_rerank_section_match" in out[0]
    assert out[0]["_rerank_keyword_matches"] >= 1


def test_heuristic_reranker_top_n_truncation():
    """top_n truncates the reranked output."""
    rr = HeuristicReranker()
    chunks = [_make_chunk(f"c{i}", f"text {i}") for i in range(5)]
    out = rr.rerank(question="x", chunks=chunks, top_n=3)
    assert len(out) == 3


def test_heuristic_reranker_top_n_zero_returns_empty():
    rr = HeuristicReranker()
    chunks = [_make_chunk("a", "x")]
    out = rr.rerank(question="x", chunks=chunks, top_n=0)
    assert out == []


def test_heuristic_reranker_is_neutral_when_no_signals():
    """Without keywords or section match, input order is preserved."""
    rr = HeuristicReranker()
    chunks = [
        _make_chunk("a", "Lorem ipsum.", {}),
        _make_chunk("b", "Dolor sit amet.", {}),
    ]
    out = rr.rerank(question="?", chunks=chunks)
    # All scores 0; original order preserved
    assert out[0]["id"] == "a"
    assert out[1]["id"] == "b"


def test_heuristic_reranker_is_deterministic():
    rr = HeuristicReranker()
    chunks = [
        _make_chunk("a", "Management: diabetes is treated."),
        _make_chunk("b", "Epidemiology: prevalence is rising."),
    ]
    out1 = rr.rerank(question="Discuss management.", chunks=chunks)
    out2 = rr.rerank(question="Discuss management.", chunks=chunks)
    assert [c["id"] for c in out1] == [c["id"] for c in out2]


def test_heuristic_reranker_does_not_implement_bm25():
    """Per the directive: avoid BM25-style retrieval inside the reranker.

    The v1 uses section boost + keyword count, NOT BM25 term-
    frequency normalization. We verify by reading the code (not
    docstrings/comments, which legitimately mention BM25 to explain
    what we are *not* doing).
    """
    # Get the source of just the rerank method (not the class docstring)
    import re
    src = inspect.getsource(HeuristicReranker.rerank)
    # No term-frequency normalization (BM25's core)
    assert "term_frequency" not in src.lower()
    # No BM25 constants like k1, b (BM25's tuning parameters)
    assert "k1" not in re.findall(r"\b\w+\b", src)
    assert not re.search(r"\bb\s*=\s*\d", src), "no BM25 b parameter"


# ----------------------------------------------------------------------
# IdentityReranker
# ----------------------------------------------------------------------

def test_identity_reranker_passes_through():
    """IdentityReranker preserves input order."""
    rr = IdentityReranker()
    chunks = [
        _make_chunk("a", "x"),
        _make_chunk("b", "y"),
        _make_chunk("c", "z"),
    ]
    out = rr.rerank(question="x", chunks=chunks)
    assert [c["id"] for c in out] == ["a", "b", "c"]


def test_identity_reranker_top_n_truncation():
    rr = IdentityReranker()
    chunks = [_make_chunk(f"c{i}", f"text {i}") for i in range(5)]
    out = rr.rerank(question="x", chunks=chunks, top_n=2)
    assert len(out) == 2
    assert [c["id"] for c in out] == ["c0", "c1"]


def test_identity_reranker_does_not_modify_input():
    rr = IdentityReranker()
    chunks = [_make_chunk("a", "x", {"section_management": True})]
    snapshot = list(chunks)
    rr.rerank(question="x", chunks=chunks)
    assert chunks == snapshot


def test_identity_reranker_system_works_if_reranking_disabled():
    """Per directive: system must function correctly if reranking is disabled."""
    # If the operator chooses IdentityReranker, the chunks pass through
    # in their retrieval-engine-determined order. The retrieval
    # engine's metadata-boost reranker (Phase 7) is still active;
    # IdentityReranker only disables the Phase 10 layer.
    rr = IdentityReranker()
    chunks = [
        _make_chunk("a", "Management: diabetes is treated."),
        _make_chunk("b", "Epidemiology: prevalence is rising."),
    ]
    out = rr.rerank(question="x", chunks=chunks)
    # Original order preserved (no reranking applied)
    assert [c["id"] for c in out] == ["a", "b"]


# ----------------------------------------------------------------------
# truncate_top_n helper
# ----------------------------------------------------------------------

def test_truncate_top_n_basic():
    chunks = [_make_chunk(f"c{i}", f"x{i}") for i in range(5)]
    out = truncate_top_n(chunks, 3)
    assert len(out) == 3


def test_truncate_top_n_zero_returns_empty():
    chunks = [_make_chunk("a", "x")]
    assert truncate_top_n(chunks, 0) == []


# ----------------------------------------------------------------------
# engine.py: semantic_reranker integration
# ----------------------------------------------------------------------

def test_retrieval_engine_default_uses_identity_semantic_reranker():
    """The default engine uses IdentityReranker (no-op semantic)."""
    engine = RetrievalEngine()
    assert isinstance(engine.semantic_reranker, IdentityReranker)


def test_retrieval_engine_accepts_custom_semantic_reranker():
    rr = HeuristicReranker()
    engine = RetrievalEngine(semantic_reranker=rr)
    assert engine.semantic_reranker is rr


def test_retrieval_engine_with_heuristic_reranker_runs():
    """End-to-end: engine with HeuristicReranker completes."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        ext = RegexMetadataExtractor()
        mgmt_text = "Management: Diabetes is treated with metformin. " + ("X " * 100)
        mgmt_chunks = chunk_pages(
            [{"page_num": 1, "method": "text", "text": mgmt_text, "char_count": len(mgmt_text)}],
            [Chapter("DM", 1, 1, 0.5)], "psm", "b1", extractor=ext,
        )
        epi_text = "Epidemiology: Prevalence is rising. " + ("Y " * 100)
        epi_chunks = chunk_pages(
            [{"page_num": 2, "method": "text", "text": epi_text, "char_count": len(epi_text)}],
            [Chapter("DM", 2, 2, 0.5)], "psm", "b2", extractor=ext,
        )
        for c in mgmt_chunks + epi_chunks:
            c.embedding = [0.0] * 8
        index_chunks(mgmt_chunks + epi_chunks, "psm")

        engine = RetrievalEngine(semantic_reranker=HeuristicReranker())
        result = engine.retrieve(
            question={"qid": "q001", "question_text": "Discuss the management of diabetes."},
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        assert len(result.chunks) >= 1
        # Each chunk should have the rerank score annotation
        for c in result.chunks:
            assert "_rerank_score" in c


def test_retrieval_engine_with_identity_reranker_preserves_order():
    """IdentityReranker in the engine preserves the metadata-boost order."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        ext = RegexMetadataExtractor()
        mgmt_text = "Management: Diabetes is treated with metformin. " + ("X " * 100)
        mgmt_chunks = chunk_pages(
            [{"page_num": 1, "method": "text", "text": mgmt_text, "char_count": len(mgmt_text)}],
            [Chapter("DM", 1, 1, 0.5)], "psm", "b1", extractor=ext,
        )
        for c in mgmt_chunks:
            c.embedding = [0.0] * 8
        index_chunks(mgmt_chunks, "psm")

        engine = RetrievalEngine(semantic_reranker=IdentityReranker())
        result = engine.retrieve(
            question={"qid": "q001", "question_text": "Discuss the management."},
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        # IdentityReranker should NOT add _rerank_score
        for c in result.chunks:
            assert "_rerank_score" not in c


def test_retrieval_engine_accepts_blueprint_spec():
    """The engine accepts a Blueprint Retrieval spec and passes it to the reranker."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        ext = RegexMetadataExtractor()
        mgmt_text = "Management: Diabetes is treated with metformin. " + ("X " * 100)
        mgmt_chunks = chunk_pages(
            [{"page_num": 1, "method": "text", "text": mgmt_text, "char_count": len(mgmt_text)}],
            [Chapter("DM", 1, 1, 0.5)], "psm", "b1", extractor=ext,
        )
        for c in mgmt_chunks:
            c.embedding = [0.0] * 8
        index_chunks(mgmt_chunks, "psm")

        # Build a blueprint spec
        from medrack.planner import plan_for_question
        from medrack.retrieval import build_blueprint_retrieval
        bp = plan_for_question(
            question_text="Discuss the management of diabetes.",
            subject="psm", marks=10, question_type="theory",
        )
        bp_spec = build_blueprint_retrieval(bp)

        engine = RetrievalEngine(semantic_reranker=HeuristicReranker())
        result = engine.retrieve(
            question={"qid": "q001", "question_text": "Discuss the management."},
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
            blueprint_spec=bp_spec,
        )
        assert result.blueprint_spec is bp_spec


def test_retrieval_engine_blueprint_spec_none_by_default():
    """Without an explicit blueprint_spec, the engine returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MEDRACK_HOME"] = tmp
        ext = RegexMetadataExtractor()
        text = "Diabetes is treated with metformin. " + ("X " * 100)
        chunks = chunk_pages(
            [{"page_num": 1, "method": "text", "text": text, "char_count": len(text)}],
            [Chapter("DM", 1, 1, 0.5)], "psm", "b1", extractor=ext,
        )
        for c in chunks:
            c.embedding = [0.0] * 8
        index_chunks(chunks, "psm")

        result = retrieve_for_question(
            question={"qid": "q001", "question_text": "x"},
            subject="psm",
            query_embedding=[0.0] * 8,
            marks=10,
        )
        assert result.blueprint_spec is None


# ----------------------------------------------------------------------
# Public interface stability (future rerankers can be swapped)
# ----------------------------------------------------------------------

def test_reranker_abc_signature_is_stable():
    """The Reranker ABC signature must be stable for future impls."""
    sig = inspect.signature(Reranker.rerank)
    # Expected signature: (self, *, question, chunks, blueprint_spec=None, top_n=None)
    params = list(sig.parameters.keys())
    assert "question" in params
    assert "chunks" in params
    assert "blueprint_spec" in params
    assert "top_n" in params
    # blueprint_spec and top_n have defaults
    assert sig.parameters["blueprint_spec"].default is None
    assert sig.parameters["top_n"].default is None


def test_reranker_abc_subclassable_for_future_implementations():
    """A future CrossEncoder, BGE, or other semantic reranker can subclass."""
    # Simulate a future cross-encoder reranker (placeholder; no model load)
    class FutureCrossEncoderReranker(Reranker):
        def rerank(self, *, question, chunks, blueprint_spec=None, top_n=None):
            # In a real impl, this would call a cross-encoder model.
            # For testing, just defer to the heuristic.
            return HeuristicReranker().rerank(
                question=question, chunks=chunks,
                blueprint_spec=blueprint_spec, top_n=top_n,
            )

    rr = FutureCrossEncoderReranker()
    chunks = [_make_chunk("a", "Management: diabetes is treated.")]
    out = rr.rerank(
        question="Discuss the management of diabetes.",
        chunks=chunks,
    )
    assert len(out) == 1


# ----------------------------------------------------------------------
# Isolation
# ----------------------------------------------------------------------

def test_rerankers_isolated_from_forbidden_layers():
    """The rerankers module does not import from forbidden layers."""
    src = inspect.getsource(__import__("medrack.retrieval.rerankers", fromlist=["*"]))
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    cleaned = ast.unparse(tree)
    for forbidden in ["medrack.answer", "medrack.bot", "medrack.dashboard",
                       "medrack.benchmarks", "medrack.planner"]:
        assert forbidden not in cleaned, (
            f"rerankers imports from {forbidden}"
        )


def test_rerankers_does_not_perform_retrieval():
    """The rerankers module must not call the vector index."""
    src = inspect.getsource(__import__("medrack.retrieval.rerankers", fromlist=["*"]))
    assert "from medrack.ingest.index" not in src
    assert "medrack.ingest.index.query" not in src


def test_rerankers_does_not_generate_text():
    """The rerankers module must not call any LLM or text generation."""
    src = inspect.getsource(__import__("medrack.retrieval.rerankers", fromlist=["*"]))
    assert "LLMClient" not in src
    assert "complete(" not in src
