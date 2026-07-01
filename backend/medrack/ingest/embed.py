"""Embedding stage of the KB ingest pipeline (Stage 2.2, T7).

Wraps ``sentence-transformers`` so the rest of the pipeline can embed chunks
with a single function call. The model is loaded lazily on first use and
cached as a module-level singleton — loading the MiniLM-L6-v2 model costs
~80MB and ~1s, so we only want to pay that cost once per process.

Public interface:
    get_model() -> SentenceTransformer
    embed_chunks(chunks, batch_size=32) -> list[Chunk]

Design notes:
- ``get_model`` is a lazy singleton. We re-evaluate ``EMBEDDING_MODEL`` from
  ``medrack.config`` on first call so ``$MEDRACK_HOME`` overrides and test
  config swaps are honoured, but the model itself is loaded only once and
  cached on the module-level ``_model`` global.
- ``embed_chunks`` mutates each chunk in place by setting the ``embedding``
  attribute, then returns the same list. The Chunk dataclass does not
  declare ``embedding`` as a field (T6 left it commented out for T7 to
  fill in), so we just attach the attribute dynamically — this matches the
  brief's interface and keeps Chunk backwards-compatible with T6 tests.
- We use ``show_progress_bar=False`` because progress bars break pytest
  output capture and are noise in batch ingest runs (the CLI orchestrator
  will log progress separately).
"""
from __future__ import annotations

import os
from typing import List

from sentence_transformers import SentenceTransformer

from medrack.config import EMBEDDING_MODEL
from medrack.ingest.chunk import Chunk

# Module-level singleton — loaded on first call to get_model().
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazy-loaded, cached singleton SentenceTransformer.

    First call resolves ``medrack.config.EMBEDDING_MODEL`` (default
    ``sentence-transformers/all-MiniLM-L6-v2``, 384-dim) and constructs
    the model. Subsequent calls return the cached instance.

    Device handling
    ---------------
    We pin the model to CPU by default. The MedRack dev box has a
    GeForce GTX 750 (sm_50) which is below the compute capability
    floor of recent PyTorch CUDA wheels (sm_75+), so the GPU path
    raises ``torch.AcceleratorError: no kernel image is available``.
    MiniLM-L6-v2 at batch_size=32 runs in well under a second on a
    modern CPU, so the CPU default is the right baseline.

    Set the environment variable ``MEDRACK_EMBED_DEVICE=cuda`` to
    opt into GPU (e.g. on a beefier machine, or a CI runner with a
    supported GPU). Unknown values fall back to CPU with a warning.
    """
    global _model
    if _model is None:
        device = os.environ.get("MEDRACK_EMBED_DEVICE", "cpu").strip().lower()
        if device not in {"cpu", "cuda"}:
            import warnings
            warnings.warn(
                f"MEDRACK_EMBED_DEVICE={device!r} not recognised; falling back to CPU"
            )
            device = "cpu"
        _model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    return _model


def embed_chunks(chunks: List[Chunk], batch_size: int = 32) -> List[Chunk]:
    """Add the ``embedding`` field (list of floats) to each chunk in-place.

    Returns the same list (mutated). The encoder is run once over all
    chunk texts with the requested ``batch_size``; progress bars are
    suppressed so this is safe to call inside pytest.

    Parameters
    ----------
    chunks:
        List of ``medrack.ingest.chunk.Chunk`` objects. Each chunk's
        ``text`` is encoded; each chunk's ``embedding`` attribute is set
        to a Python list of 384 floats (the MiniLM-L6-v2 dimensionality).
    batch_size:
        Number of texts to encode in a single forward pass. Defaults
        to 32 (sensible for CPU; bump up for GPU).
    """
    model = get_model()
    texts = [c.text for c in chunks]
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    for c, e in zip(chunks, embeddings):
        c.embedding = e.tolist()
    return chunks


__all__ = ["get_model", "embed_chunks"]
