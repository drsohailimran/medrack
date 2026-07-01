# ADR 0010 — Reranker (Generic Interface + HeuristicReranker v1)

- Status: Accepted
- Date: 2026-06-29
- Phase: 10 (Cross-Encoder Reranker — generic interface)
- Depends on: ADR 0005 (benchmark framework), ADR 0007 (adaptive retrieval), ADR 0009 (Blueprint Retrieval)

## Context

The Phase 7 retrieval layer returns chunks ranked by vector
similarity. The metadata-boost reranker (`MetadataBoostReranker`,
Phase 7) re-orders them using the question's detected sections. But
the metadata-boost reranker is additive only (multiplicative on
distance); it doesn't *replace* the vector similarity with a
semantic relevance score.

The Phase 10 directive asks for a **cross-encoder reranker**: a
component that re-orders retrieved evidence according to *semantic*
relevance. The operator's architectural refinement generalizes this:
the reranker should be a **generic interface** that accepts a
family of implementations (Identity, Heuristic, CrossEncoder, BGE,
etc.), not just one.

## Decision

### Module structure

```
medrack/retrieval/rerankers.py   # Reranker ABC + HeuristicReranker v1 + IdentityReranker
medrack/tests/test_rerankers.py  # 33 new tests
medrack/retrieval/engine.py      # wire in (additive)
```

### Generic Reranker interface

A :class:`Reranker` ABC defines the contract:

```python
class Reranker(ABC):
    @abstractmethod
    def rerank(
        self,
        *,
        question: str,
        chunks: List[Dict[str, Any]],
        blueprint_spec: Optional[Any] = None,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        ...
```

The interface is *deliberately* small. A real cross-encoder
(future phase), a BGE reranker (future phase), or any other
semantic reranker can subclass and call out to a model API. The
v1 implementation is a deterministic heuristic.

### v1: HeuristicReranker

The :class:`HeuristicReranker` is the v1 implementation. It
combines three signals (per the operator's architectural
refinement):

  1. **Embedding similarity** (primary signal) — the existing
     distance from the vector index. The reranker does NOT replace
     the embedding similarity; it only re-orders the chunks the
     retrieval engine returned.
  2. **Blueprint section relevance** — a chunk whose metadata
     flags include any of the blueprint's
     ``required_metadata_categories`` gets a positive boost
     (1.0).
  3. **Lightweight keyword overlap** — a chunk that shares more
     non-stopword tokens with the question gets a positive boost
     (0.5 per matching keyword).

The v1 is **conservative**: when both heuristic signals are
neutral (no section match, no keyword overlap), the input order
is preserved. This means the system "still functions correctly
if reranking is disabled" (per the directive).

The v1 deliberately does **NOT implement BM25, tf-idf, or any
other term-frequency normalization** (per the directive). The
heuristic is a section-boost + keyword-count signal, not an IR
algorithm.

### IdentityReranker

A :class:`IdentityReranker` is the no-op pass-through. It returns
the input chunks in their input order, optionally truncated to
``top_n``. Useful for:
- A/B testing against a real reranker.
- Disabling reranking entirely (per the directive: "the system
  must still function correctly if reranking is disabled").
- Fallback when a real cross-encoder model fails to load.

It is the **default** for the engine. The operator can opt in to
`HeuristicReranker` (or a future cross-encoder) by passing it in.

### Future implementations

The interface is designed to accept future rerankers without
changing callers:

- **`CrossEncoderReranker`** (future phase): a real cross-encoder
  model loaded as a separate ML dependency.
- **`BGEReranker`** (future phase): BGE cross-encoder reranker.
- Other semantic rerankers: subclass :class:`Reranker` and call
  out to a model API.

All of these will accept the same ``(question, chunks,
blueprint_spec, top_n) -> reranked_chunks`` interface.

### What the Reranker does NOT do

Per the directive:

- It does not generate text (the writer's job).
- It does not summarize evidence (the writer's job).
- It does not perform planning (the planner's job).
- It does not modify the blueprint (the blueprint is frozen).
- It does not perform validation (the validator's job).
- It does not change metadata (chunks' metadata is preserved as-is).
- It does not perform retrieval (the engine's job).
- It does not implement BM25 or any other IR algorithm — it only
  *re-orders* the chunks the retrieval engine returns.

The Reranker **preserves traceability**: every output chunk carries
its original ``id`` and ``metadata``, so the writer can cite it.

## Architecture guarantee

The Reranker is the fourth stage of the pipeline:

```
Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator
```

The engine composes two reranking stages:

1. **Metadata-boost reranker** (Phase 7, `MetadataBoostReranker`):
   the existing v1 reranker, multiplicative on vector distance.
2. **Semantic reranker** (Phase 10, generic `Reranker` interface):
   the new pluggable stage. Default is `IdentityReranker` (no-op);
   operators can swap in `HeuristicReranker` or a future
   cross-encoder.

The two stages are independent: either can be replaced without
affecting the other.

## Isolation

`medrack.retrieval.rerankers` imports only from:

- `medrack.ingest.metadata` (for the `flatten_for_chroma` helper
  and the `StructureMetadata` / `MedicalMetadata` field catalogs)
- The standard library

It does **not** import from:

- `medrack.answer.*` (writer)
- `medrack.bot.*` (Telegram bot)
- `medrack.dashboard.*` (Web UI)
- `medrack.benchmarks.*` (benchmark framework)
- `medrack.planner.*` (planner; the reranker is duck-typed to
  accept any object with a `required_metadata_categories` list)
- `medrack.retrieval.reranker` (the Phase 7 metadata-boost
  reranker is a peer, not a dependency)
- `medrack.ingest.index` (the engine handles retrieval; the
  reranker only re-orders)

The isolation is enforced by AST tests in `test_rerankers.py`.

## Compatibility

- **No changes to the answer pipeline.** The answer pipeline does
  not yet consume the reranker. The Phase 10 land is a pure
  retrieval-side addition.
- **No changes to the Planner or Blueprint.** The reranker accepts
  the Blueprint as a duck-typed input (`required_metadata_categories`).
- **No changes to the existing retrieval layer.** The
  `MetadataBoostReranker` (Phase 7) is untouched. The Phase 10
  semantic reranker is a *new* stage in the engine, applied
  *after* the metadata-boost reranker.
- **No changes to the benchmark framework.** Phase 5's framework
  still produces the same numbers.
- **No cached answers are invalidated.** The new reranker is a
  retrieval-side component; cached answers are unchanged.
- **Backward compat**: the engine's default semantic_reranker is
  `IdentityReranker` (no-op), so existing callers see no change.

## Benchmark comparison (mock, vs Phase 5 baseline)

| Metric | Phase 5 | Phase 9 | Phase 10 | Delta (P5→P10) |
|---|---|---|---|---|
| n_questions | 20 | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.173s | 0.169s | -0.004s |
| avg_pdf_generation | 0.005s | 0.005s | 0.005s | 0 |

**No regression in the mock benchmark.** Phase 10 is a pure
retrieval-side addition; the default engine uses `IdentityReranker`
(no-op), so the benchmark runs the v0-v9 pipeline and gets the
same numbers as every other phase.

## Out of scope for Phase 10

- **Wiring the reranker into the answer pipeline.** The reranker
  is consumed by the engine; the answer pipeline does not yet
  consume the reranked chunks directly. Future phases (11+)
  can wire the writer to consume the reranker output.
- **A real cross-encoder model.** The v1 is a heuristic. A
  future phase can load a real cross-encoder model and subclass
  `Reranker` to call it.
- **BGE reranker.** A future phase can add a BGE-based
  implementation.
- **Per-corpus section availability.** The v1 reranker assumes
  all sections are available. A future phase can consume the
  Planner's `metadata_summary` to skip unavailable sections.
- **Real LLM benchmark.** Same blocker as Phase 5/6/7/8/9
  (real-LLM API hang); the operator can re-run
  `medrack.benchmarks.run --llm real` in a quiet session.

## Future direction

The `Reranker` ABC is the foundation for **semantic re-ranking**.
The v1 is a heuristic; future phases can swap in real models
without changing the engine or the answer pipeline. The engine's
`semantic_reranker` parameter is the single integration point.

Future phases can:
- Add a `CrossEncoderReranker` (loads a model from
  `sentence-transformers` or similar).
- Add a `BGEReranker` (uses the BGE cross-encoder family).
- Add an `LLMReranker` (uses a small LLM to score chunks).
- All of these are drop-in replacements for the v1
  `HeuristicReranker` or the default `IdentityReranker`.
