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
from typing import List, Optional

import chromadb

from medrack import config
from medrack.ingest.chunk import Chunk
from medrack.ingest.metadata import MetadataFilter, flatten_for_chroma, filter_to_chroma_where


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
    - ``metadatas``   : provenance dict + structured metadata (see below)

    The base metadata dict per chunk contains:
        subject, book_id, chapter_title, page_start, page_end,
        token_count, embedding_model

    If the chunk has a :class:`ChunkMetadata` (Phase 6), the grouped
    metadata is flattened via :func:`flatten_for_chroma` and merged
    into the metadata dict. Chunks without metadata (backward compat)
    still get the base dict only.

    Returns the number of chunks added. ChromaDB enforces a unique-id
    constraint — re-indexing a chunk with the same ``chunk_id`` raises;
    the orchestrator (T10) is responsible for handling updates by
    deleting the old record first.
    """
    collection = get_or_create_collection(subject)

    base_keys = (
        "subject", "book_id", "chapter_title", "page_start", "page_end",
        "token_count", "embedding_model",
    )

    metadatas = []
    for c in chunks:
        meta: dict = {
            "subject": c.subject,
            "book_id": c.book_id,
            "chapter_title": c.chapter_title,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "token_count": c.token_count,
            "embedding_model": config.EMBEDDING_MODEL,
        }
        if c.metadata is not None:
            # Flatten the grouped metadata into Chroma-safe scalars.
            # The flattening helper is the only place that knows about
            # Chroma's scalar-only constraint.
            flat = flatten_for_chroma(c.metadata)
            for k, v in flat.items():
                if k in base_keys:
                    # Provenance keys take precedence over any name
                    # collision with a metadata field. None today, but
                    # pinned to prevent future regressions.
                    continue
                meta[k] = v
        metadatas.append(meta)

    collection.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=[c.embedding for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=metadatas,
    )
    return len(chunks)


def delete_book_chunks(subject: str, book_id: str) -> None:
    """Delete all indexed chunks for one book from its subject collection.

    Chunks store their ``book_id`` in metadata (see ``index_chunks``), so
    a single ``collection.delete(where=...)`` removes every chunk that came
    from this book. Used when a book is removed from the library.
    """
    collection = get_or_create_collection(subject)
    collection.delete(where={"book_id": book_id})


def query(
    subject: str,
    query_embedding: List[float],
    top_k: int = 8,
    metadata_filter: Optional[MetadataFilter] = None,
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
    metadata_filter:
        Optional :class:`MetadataFilter` (Phase 6). When provided and
        non-empty, results are restricted to chunks whose structured
        metadata matches the filter. Translation to Chroma's ``where``
        clause is done via :func:`filter_to_chroma_where`; the rest of
        the application does not need to know Chroma's filter syntax.

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

    # Phase 6: optional metadata filter translation.
    where = filter_to_chroma_where(metadata_filter) if metadata_filter is not None else None

    query_kwargs: dict = dict(
        query_embeddings=query_embeddings,
        n_results=top_k,
    )
    if where is not None:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)

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
