"""Tests for medrack.ingest.embed + index."""
import os
import tempfile
from pathlib import Path

import pytest

from medrack.config import CHROMA_PATH, EMBEDDING_MODEL
from medrack.ingest.chunk import Chunk
from medrack.ingest.embed import get_model, embed_chunks
from medrack.ingest.index import get_or_create_collection, index_chunks, query


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    yield tmp_path


def test_model_loads_with_correct_dim(temp_home):
    model = get_model()
    assert model.get_sentence_embedding_dimension() == 384


def test_embed_chunks_adds_embedding_field(temp_home):
    chunks = [
        Chunk(chunk_id="c1", text="Hello world.", subject="psm", book_id="b1",
              chapter_title="T", page_start=1, page_end=1, token_count=2),
        Chunk(chunk_id="c2", text="Goodbye world.", subject="psm", book_id="b1",
              chapter_title="T", page_start=1, page_end=1, token_count=2),
    ]
    result = embed_chunks(chunks)
    assert len(result) == 2
    assert all(c.embedding is not None for c in result)
    assert all(len(c.embedding) == 384 for c in result)


def test_index_chunks_and_query(temp_home):
    chunks = [
        Chunk(chunk_id="c1", text="Hypertension is high blood pressure.",
             subject="medicine", book_id="b1", chapter_title="Cardio",
             page_start=1, page_end=1, token_count=5),
        Chunk(chunk_id="c2", text="Diabetes is high blood sugar.",
             subject="medicine", book_id="b1", chapter_title="Endo",
             page_start=2, page_end=2, token_count=5),
        Chunk(chunk_id="c3", text="Pneumonia is a lung infection.",
             subject="medicine", book_id="b1", chapter_title="Pulmo",
             page_start=3, page_end=3, token_count=5),
    ]
    embed_chunks(chunks)
    n = index_chunks(chunks, subject="medicine")
    assert n == 3

    # Query with the embedding of the first chunk (or a similar text)
    model = get_model()
    q = model.encode(["blood pressure"]).tolist()
    results = query("medicine", q, top_k=2)
    assert len(results) == 2
    # Top result should be the hypertension chunk
    assert "Hypertension" in results[0]["text"]


def test_query_filters_by_subject(temp_home):
    """CRITICAL: query MUST only return chunks from the requested subject."""
    med_chunk = Chunk(chunk_id="med1", text="Cardiology is the study of the heart.",
                     subject="medicine", book_id="b1", chapter_title="Intro",
                     page_start=1, page_end=1, token_count=8)
    surg_chunk = Chunk(chunk_id="surg1", text="Surgery is the study of operations.",
                      subject="surgery", book_id="b2", chapter_title="Intro",
                      page_start=1, page_end=1, token_count=8)
    embed_chunks([med_chunk, surg_chunk])
    index_chunks([med_chunk], subject="medicine")
    index_chunks([surg_chunk], subject="surgery")

    model = get_model()
    q = model.encode(["heart study"]).tolist()
    results = query("medicine", q, top_k=10)
    for r in results:
        assert r["metadata"]["subject"] == "medicine", \
            f"Subject filter failed: got {r['metadata']['subject']}"
