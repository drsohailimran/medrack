"""ChromaDB indexer + query stage of the KB ingest pipeline (Stage 2.2, T7).

Persists embedded chunks to a per-subject ChromaDB collection and exposes
a query function used by Stage 2.4 (RAG retrieval).

Public interface:
    get_or_create_collection(subject: str) -> chromadb.api.models.Collection
    index_chunks(chunks: list[Chunk], subject: str) -> int
    query(subject: str, query_embedding: list[float], top_k: int = 8) -> list[dict]

CRITICAL SAFETY INVARIANT — SUBJECT FILTER MANDATORY
---------------------------------------------------
The MedRack plan locks cross-subject retrieval as forbidden: an MBBS
theory question on, say, "heart failure management" must never pull a
paragraph from a surgery textbook. We enforce this *structurally* by
giving every subject its own ChromaDB collection (``kb_<subject>``) and
making ``query()`` only ever call ``get_or_create_collection(subject)``
with the caller's subject. There is no API path that lets a caller
query across subjects — the safety property is enforced by the
collection layout itself, not by a runtime check on metadata.

The ``test_query_filters_by_subject`` test in
``medrack/tests/test_ingest_index.py`` is the regression guard for
this invariant. Do not change the per-subject collection naming
convention.

Design notes:
- We use ``chromadb.PersistentClient`` (the new API; ``chromadb.Client``
  is deprecated). The persistence path is re-evaluated per call via
  ``medrack.config.get_medrack_home()`` so the ``$MEDRACK_HOME``
  override used by the ``temp_home`` test fixture actually works. The
  module-level ``CHROMA_PATH`` constant in ``medrack.config`` is frozen
  at first import, which would defeat test isolation.
- ChromaDB defaults to L2-squared distance; for sentence-transformer
  embeddings (which are cosine-distributed on the unit sphere) this
  is monotonic with cosine distance, so closest-still-wins ranking is
  correct in practice. We do not change the distance function.
- Metadata values are coerced to JSON-compatible scalars: ``page_start``
  / ``page_end`` / ``token_count`` stay as ints, the rest stay as
  strings. ChromaDB rejects nested dicts / lists in metadata.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import chromadb

from medrack import config
from medrack.ingest.chunk import Chunk


def _chroma_path() -> Path:
    """Re-evaluate the ChromaDB persistence path on every call.

    This is the same pattern used by ``medrack.ingest.manifest`` — the
    module-level ``config.CHROMA_PATH`` is frozen at first config import
    and would not honour ``$MEDRACK_HOME`` overrides applied later
    (e.g. by the ``temp_home`` pytest fixture).
    """
    return config.get_medrack_home() / "index" / "chroma"


def get_or_create_collection(subject: str):
    """Return the ChromaDB collection for ``subject`` (one per subject).

    The collection name is ``kb_<subject>`` (e.g. ``kb_medicine``,
    ``kb_surgery``). Calling this twice for the same subject returns
    the same collection object; calling for a new subject creates a
    new collection on disk.
    """
    client = chromadb.PersistentClient(path=str(_chroma_path()))
    return client.get_or_create_collection(name=f"kb_{subject}")


def index_chunks(chunks: List[Chunk], subject: str) -> int:
    """Add chunks to the subject's ChromaDB collection.

    Each chunk is stored with:

    - ``ids``         : ``chunk.chunk_id`` (deterministic UUID from T6)
    - ``embeddings``  : ``chunk.embedding`` (384-dim list of floats)
    - ``documents``   : ``chunk.text`` (the raw chunk text)
    - ``metadatas``   : provenance dict (see below)

    Metadata dict per chunk contains:
        subject, book_id, chapter_title, page_start, page_end,
        token_count, embedding_model

    Returns the number of chunks added. ChromaDB enforces a unique-id
    constraint — re-indexing a chunk with the same ``chunk_id`` raises;
    the orchestrator (T10) is responsible for handling updates by
    deleting the old record first.
    """
    collection = get_or_create_collection(subject)
    collection.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=[c.embedding for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[{
            "subject": c.subject,
            "book_id": c.book_id,
            "chapter_title": c.chapter_title,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "token_count": c.token_count,
            "embedding_model": config.EMBEDDING_MODEL,
        } for c in chunks],
    )
    return len(chunks)


def query(
    subject: str,
    query_embedding: List[float],
    top_k: int = 8,
) -> List[dict]:
    """Return the top-``top_k`` chunks for ``subject`` by vector similarity.

    The subject filter is enforced structurally: this function only
    ever calls ``get_or_create_collection(subject)``, so a query for
    ``"medicine"`` is physically incapable of returning surgery chunks
    — they live in a different collection.

    Parameters
    ----------
    subject:
        The subject to query (e.g. ``"medicine"``). The collection
        ``kb_<subject>`` is opened.
    query_embedding:
        The query vector, as produced by
        ``medrack.ingest.embed.get_model().encode([text]).tolist()``
        (a 2D ``list[list[float]]`` with one row). A 1D
        ``list[float]`` is also accepted for convenience and will be
        wrapped automatically.
    top_k:
        Maximum number of results to return. Defaults to 8, matching
        ``medrack.config.RETRIEVAL_TOP_K``.

    Returns
    -------
    list of dict, each with keys ``id``, ``text``, ``metadata``, ``distance``.
    Ordered by ascending distance (closest match first). The
    ``distance`` field may be ``None`` if ChromaDB was built without
    a distance function — in practice it is always present.
    """
    collection = get_or_create_collection(subject)
    # Be lenient on input shape: accept either a 1D vector
    # (list[float], the brief's nominal interface) or a 2D batch
    # (list[list[float]], the natural output of
    # ``model.encode([text]).tolist()``).
    if not query_embedding or not isinstance(query_embedding[0], (list, tuple)):
        query_embeddings = [query_embedding]
    else:
        query_embeddings = query_embedding
    results = collection.query(
        query_embeddings=query_embeddings,
        n_results=top_k,
    )

    # Flatten ChromaDB's nested result structure (always length-1 lists
    # at the outer level when query_embeddings is a single vector).
    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results.get("distances", [None])[0] if "distances" in results else None

    out: List[dict] = []
    for i, doc_id in enumerate(ids):
        out.append({
            "id": doc_id,
            "text": documents[i],
            "metadata": metadatas[i],
            "distance": distances[i] if distances is not None else None,
        })
    return out


__all__ = ["get_or_create_collection", "index_chunks", "query"]
