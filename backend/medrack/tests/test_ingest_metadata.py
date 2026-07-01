"""Tests for Phase 6: structured medical metadata + pluggable extractor.

Coverage:
  - metadata.py: dataclasses, flatten_for_chroma, filter_to_chroma_where
  - regex_extractor: deterministic extraction on representative text
  - chunk.py: extractor wiring (additive; metadata=None when no extractor)
  - index.py: metadata persistence (flattened) and filter translation

The tests are organised in one file per concern to match the existing
test layout (one test file per module). This file is
``test_ingest_metadata`` rather than separate files because the
extractor is tightly coupled to the schema (a separate file per piece
would be over-decomposed for the v1 surface area).
"""
from __future__ import annotations

from medrack.ingest.chapter import Chapter
from medrack.ingest.chunk import Chunk, chunk_pages
from medrack.ingest.extractors import RegexMetadataExtractor
from medrack.ingest.index import index_chunks, query
from medrack.ingest.metadata import (
    ChunkMetadata,
    ExamMetadata,
    MedicalMetadata,
    MetadataExtractor,
    MetadataFilter,
    StructureMetadata,
    filter_to_chroma_where,
    flatten_for_chroma,
)


def _attach_dummy_embedding(chunks, dim: int = 8) -> None:
    """Attach a zero-vector embedding to each chunk for Chroma persistence.

    The Chunk dataclass doesn't formally declare an ``embedding`` field
    (it's added by the embedder pipeline at index time), but the
    ``index_chunks`` function reads it. For tests we set it as a plain
    instance attribute, which is the same pattern the real embedder
    uses.
    """
    for c in chunks:
        c.embedding = [0.0] * dim


# ----------------------------------------------------------------------
# metadata.py: grouped dataclasses
# ----------------------------------------------------------------------

def test_default_metadata_is_all_empty():
    m = ChunkMetadata()
    assert isinstance(m.structure, StructureMetadata)
    assert isinstance(m.medical, MedicalMetadata)
    assert isinstance(m.exam, ExamMetadata)
    assert m.structure.section_definition is False
    assert m.medical.section_management is False
    assert m.exam.important_years == []
    assert m.exam.keywords == []


def test_to_dict_flattens_all_groups():
    m = ChunkMetadata(
        structure=StructureMetadata(section_table=True),
        medical=MedicalMetadata(section_management=True),
        exam=ExamMetadata(important_years=[2020], keywords=["x"]),
    )
    d = m.to_dict()
    assert d["section_table"] is True
    assert d["section_management"] is True
    assert d["important_years"] == [2020]
    assert d["keywords"] == ["x"]


# ----------------------------------------------------------------------
# metadata.py: flatten_for_chroma (ChromaDB boundary)
# ----------------------------------------------------------------------

def test_flatten_for_chroma_booleans_pass_through():
    m = ChunkMetadata(
        structure=StructureMetadata(section_table=True),
        medical=MedicalMetadata(section_management=True),
    )
    flat = flatten_for_chroma(m)
    assert flat["section_table"] is True
    assert flat["section_management"] is True
    assert flat["section_definition"] is False


def test_flatten_for_chroma_lists_become_csv_strings():
    m = ChunkMetadata(
        exam=ExamMetadata(
            important_years=[2020, 2021, 2099],
            important_numbers=["1000", "50000"],
            keywords=["diabetes", "epidemiology"],
        ),
    )
    flat = flatten_for_chroma(m)
    assert flat["important_years"] == "2020,2021,2099"
    assert flat["important_numbers"] == "1000,50000"
    assert flat["keywords"] == "diabetes,epidemiology"


def test_flatten_for_chroma_empty_lists_become_empty_string():
    flat = flatten_for_chroma(ChunkMetadata())
    assert flat["important_years"] == ""
    assert flat["important_numbers"] == ""
    assert flat["keywords"] == ""


# ----------------------------------------------------------------------
# metadata.py: filter_to_chroma_where (typed filter -> Chroma where)
# ----------------------------------------------------------------------

def test_empty_filter_returns_none():
    assert filter_to_chroma_where(MetadataFilter()) is None


def test_single_section_filter_returns_plain_dict():
    where = filter_to_chroma_where(MetadataFilter(medical=["section_management"]))
    assert where == {"section_management": True}


def test_multi_section_filter_uses_or():
    where = filter_to_chroma_where(
        MetadataFilter(medical=["section_management", "section_treatment"])
    )
    assert where == {"$or": [{"section_management": True}, {"section_treatment": True}]}


def test_structure_and_medical_filter_combined():
    where = filter_to_chroma_where(
        MetadataFilter(
            structure=["section_table"],
            medical=["section_management"],
        )
    )
    # Both groups collapse into a single $or
    assert where == {
        "$or": [
            {"section_table": True},
            {"section_management": True},
        ]
    }


def test_metadata_filter_is_empty():
    assert MetadataFilter().is_empty() is True
    assert MetadataFilter(medical=["section_management"]).is_empty() is False
    assert MetadataFilter(structure=["section_table"]).is_empty() is False


# ----------------------------------------------------------------------
# metadata.py: pluggable extractor interface
# ----------------------------------------------------------------------

class _RecordingExtractor(MetadataExtractor):
    """Test extractor that records all inputs and returns a fixed metadata."""

    def __init__(self, fixed: ChunkMetadata) -> None:
        self.fixed = fixed
        self.calls: list = []

    def extract(self, text, *, subject, book_id, chapter_title, page_start, page_end):
        self.calls.append(
            {
                "text": text,
                "subject": subject,
                "book_id": book_id,
                "chapter_title": chapter_title,
                "page_start": page_start,
                "page_end": page_end,
            }
        )
        return self.fixed


def test_pluggable_extractor_interface_is_swappable():
    """A custom extractor can be swapped in without changing the pipeline."""
    fixed = ChunkMetadata(
        structure=StructureMetadata(section_definition=True),
        medical=MedicalMetadata(section_diagnosis=True),
    )
    ext = _RecordingExtractor(fixed)
    pages = [
        {"page_num": 1, "method": "text", "text": "Diabetes is a chronic condition.", "char_count": 38}
    ]
    chapters = [Chapter("Diabetes", 1, 1, 0.5)]
    chunks = chunk_pages(pages, chapters, "psm", "b1", extractor=ext)
    assert len(chunks) == 1
    assert chunks[0].metadata is fixed
    assert ext.calls[0]["subject"] == "psm"
    assert ext.calls[0]["chapter_title"] == "Diabetes"


def test_no_extractor_yields_none_metadata():
    """Backward compat: no extractor -> metadata=None."""
    pages = [{"page_num": 1, "method": "text", "text": "X" * 5000, "char_count": 5000}]
    chapters = [Chapter("C", 1, 1, 0.5)]
    chunks = chunk_pages(pages, chapters, "psm", "b1")
    assert all(c.metadata is None for c in chunks)


# ----------------------------------------------------------------------
# regex_extractor: deterministic extraction
# ----------------------------------------------------------------------

def test_regex_extractor_detects_medical_sections():
    ext = RegexMetadataExtractor()
    text = (
        "Etiology: Diabetes is caused by insulin deficiency. "
        "Management: Treatment includes metformin. "
        "Epidemiology: Prevalence is 10%."
    )
    m = ext.extract(text, subject="psm", book_id="b", chapter_title="DM", page_start=1, page_end=1)
    assert m.medical.section_etiology is True
    assert m.medical.section_management is True
    assert m.medical.section_epidemiology is True
    # Sections NOT mentioned should remain False
    assert m.medical.section_pathogenesis is False
    assert m.medical.section_national_programme is False


def test_regex_extractor_detects_structural_elements():
    ext = RegexMetadataExtractor()
    text = (
        "Figure 1 shows the anatomy. "
        "See Table 2 for the classification. "
        "The formula is: BMI = weight/height^2. "
        "In summary, the condition is benign."
    )
    m = ext.extract(text, subject="anatomy", book_id="b", chapter_title="C", page_start=1, page_end=1)
    assert m.structure.section_diagram is True
    assert m.structure.section_table is True
    assert m.structure.section_formula is True
    assert m.structure.section_conclusion is True


def test_regex_extractor_detects_important_years():
    ext = RegexMetadataExtractor()
    m = ext.extract(
        "The National Health Policy was announced in 2017 and revised in 2024.",
        subject="psm", book_id="b", chapter_title="NHP", page_start=1, page_end=1,
    )
    assert 2017 in m.exam.important_years
    assert 2024 in m.exam.important_years


def test_regex_extractor_excludes_years_from_important_numbers():
    """important_numbers should not double-count years and should preserve raw form."""
    ext = RegexMetadataExtractor()
    m = ext.extract(
        "The programme was launched in 2017. It covers 1,200,000 beneficiaries.",
        subject="psm", book_id="b", chapter_title="P", page_start=1, page_end=1,
    )
    assert 2017 in m.exam.important_years
    # The raw form (with commas) is preserved in the output
    assert "1,200,000" in m.exam.important_numbers
    # 2017 must not appear in important_numbers
    assert "2017" not in m.exam.important_numbers


def test_regex_extractor_extracts_keywords_stopword_filtered():
    ext = RegexMetadataExtractor()
    m = ext.extract(
        "The patient presents with diabetes mellitus. Diabetes management "
        "includes lifestyle modification. Diabetes complications are serious.",
        subject="medicine", book_id="b", chapter_title="DM", page_start=1, page_end=1,
    )
    # Stopwords ("the", "with", "includes", "are") must not appear
    assert "the" not in m.exam.keywords
    assert "with" not in m.exam.keywords
    # Content words should be present
    assert "diabetes" in m.exam.keywords
    # "diabetes" is the most frequent, should be at the top
    assert m.exam.keywords[0] == "diabetes"


def test_regex_extractor_is_deterministic():
    """Same input must produce same output. Critical for cache stability."""
    ext = RegexMetadataExtractor()
    text = "Management: treatment of diabetes. Definition: a chronic condition."
    kwargs = dict(subject="psm", book_id="b", chapter_title="DM", page_start=1, page_end=1)
    m1 = ext.extract(text, **kwargs)
    m2 = ext.extract(text, **kwargs)
    assert m1.to_dict() == m2.to_dict()


def test_regex_extractor_handles_empty_text():
    ext = RegexMetadataExtractor()
    m = ext.extract("", subject="psm", book_id="b", chapter_title="C", page_start=1, page_end=1)
    assert m.to_dict() == ChunkMetadata().to_dict()


def test_regex_extractor_does_not_modify_input_text():
    """The extractor must be additive: it must not mutate its input."""
    ext = RegexMetadataExtractor()
    text = "Management: Diabetes is treated with metformin."
    snapshot = text
    ext.extract(text, subject="psm", book_id="b", chapter_title="C", page_start=1, page_end=1)
    assert text == snapshot


# ----------------------------------------------------------------------
# chunk.py: extractor wiring
# ----------------------------------------------------------------------

def test_chunk_pages_with_extractor_populates_metadata():
    ext = RegexMetadataExtractor()
    text = (
        "Etiology: Diabetes is caused by insulin deficiency. "
        "Management: Treatment includes metformin. "
        + ("padding " * 200)  # enough text to potentially split into multiple chunks
    )
    pages = [{"page_num": 1, "method": "text", "text": text, "char_count": len(text)}]
    chapters = [Chapter("Diabetes", 1, 1, 0.5)]
    chunks = chunk_pages(pages, chapters, "psm", "b1", extractor=ext)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.metadata is not None
        assert isinstance(c.metadata, ChunkMetadata)
        # The chapter's medical keywords appear at least in the first chunk
        # (subsequent chunks may have moved past the keyword). Don't assert
        # exact content; assert the metadata object is populated.
        assert c.metadata.to_dict() is not None


def test_chunk_pages_preserves_chunk_id_with_extractor():
    """chunk_id must be identical with or without extractor (same hash input)."""
    text = ("some text " * 200)
    pages = [{"page_num": 1, "method": "text", "text": text, "char_count": len(text)}]
    chapters = [Chapter("C", 1, 1, 0.5)]

    c_no_ext = chunk_pages(pages, chapters, "psm", "b1")
    c_with_ext = chunk_pages(pages, chapters, "psm", "b1", extractor=RegexMetadataExtractor())

    assert len(c_no_ext) == len(c_with_ext)
    for a, b in zip(c_no_ext, c_with_ext):
        assert a.chunk_id == b.chunk_id
        assert a.text == b.text


# ----------------------------------------------------------------------
# index.py: persistence and retrieval filtering
# ----------------------------------------------------------------------

def test_index_persists_flattened_metadata(tmp_path, monkeypatch):
    """Indexed chunks should have flattened metadata stored in Chroma."""
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    # Reload the medrack home-resolver and chroma-path
    from medrack import config
    config.get_medrack_home()  # ensure module re-evaluated

    ext = RegexMetadataExtractor()
    text = "Management: Diabetes treatment includes metformin. Figure 1 shows the pathway."
    chunks = chunk_pages(
        [{"page_num": 1, "method": "text", "text": text, "char_count": len(text)}],
        [Chapter("DM", 1, 1, 0.5)],
        "psm",
        "b1",
        extractor=ext,
    )
    # Add a dummy embedding (Chroma requires it for index)
    _attach_dummy_embedding(chunks)

    n = index_chunks(chunks, "psm")
    assert n == len(chunks)

    # Re-query without filter; metadata should be present in the result
    # (use a real embedding for the query — we'll re-embed the same text
    # but since we stored 0s, we need to match that). Skip distance check.
    results = query("psm", [0.0] * 8, top_k=1)
    assert len(results) >= 1
    meta = results[0]["metadata"]
    # Flattened bools should be present
    assert "section_management" in meta
    assert meta["section_management"] is True
    # Flattened lists -> CSV strings
    assert "important_years" in meta
    assert isinstance(meta["important_years"], str)


def test_index_chunks_without_metadata_backward_compat(tmp_path, monkeypatch):
    """Chunks with metadata=None must still be indexable (no crash)."""
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))

    text = "Just some text " * 200
    chunks = chunk_pages(
        [{"page_num": 1, "method": "text", "text": text, "char_count": len(text)}],
        [Chapter("C", 1, 1, 0.5)],
        "psm",
        "b1",
        # No extractor -> metadata=None
    )
    _attach_dummy_embedding(chunks)
    index_chunks(chunks, "psm")

    results = query("psm", [0.0] * 8, top_k=1)
    assert len(results) >= 1
    # Base metadata still present
    meta = results[0]["metadata"]
    assert meta["subject"] == "psm"
    assert meta["book_id"] == "b1"


def test_query_with_metadata_filter_passes_where_to_chroma(tmp_path, monkeypatch):
    """metadata_filter is translated to Chroma's where clause."""
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))

    # Index a chunk with management metadata
    ext = RegexMetadataExtractor()
    mgmt_text = "Management: Diabetes treatment includes metformin. Figure 1 shows the pathway."
    mgmt_chunks = chunk_pages(
        [{"page_num": 1, "method": "text", "text": mgmt_text, "char_count": len(mgmt_text)}],
        [Chapter("DM", 1, 1, 0.5)],
        "psm",
        "b1",
        extractor=ext,
    )
    _attach_dummy_embedding(mgmt_chunks, dim=8)

    # And a chunk without management (definition only)
    def_text = "Definition: Diabetes is a chronic condition of carbohydrate metabolism."
    def_chunks = chunk_pages(
        [{"page_num": 2, "method": "text", "text": def_text, "char_count": len(def_text)}],
        [Chapter("DM", 1, 1, 0.5)],
        "psm",
        "b2",
        extractor=ext,
    )
    _attach_dummy_embedding(def_chunks, dim=8)

    index_chunks(mgmt_chunks + def_chunks, "psm")

    # Query WITH a metadata filter for management only
    filt = MetadataFilter(medical=["section_management"])
    results = query("psm", [0.1] * 8, top_k=10, metadata_filter=filt)
    # All returned chunks must have section_management=True
    for r in results:
        assert r["metadata"]["section_management"] is True

    # Query WITHOUT filter returns everything
    results_all = query("psm", [0.1] * 8, top_k=10)
    assert len(results_all) >= len(results)


def test_query_with_empty_filter_is_same_as_no_filter(tmp_path, monkeypatch):
    """An empty MetadataFilter should behave identically to no filter."""
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))

    text = "Management: Diabetes is treated with metformin."
    chunks = chunk_pages(
        [{"page_num": 1, "method": "text", "text": text, "char_count": len(text)}],
        [Chapter("DM", 1, 1, 0.5)],
        "psm",
        "b1",
        extractor=RegexMetadataExtractor(),
    )
    _attach_dummy_embedding(chunks, dim=8)
    index_chunks(chunks, "psm")

    r_no = query("psm", [0.1] * 8, top_k=5)
    r_empty = query("psm", [0.1] * 8, top_k=5, metadata_filter=MetadataFilter())
    assert len(r_no) == len(r_empty)
    assert [r["id"] for r in r_no] == [r["id"] for r in r_empty]
