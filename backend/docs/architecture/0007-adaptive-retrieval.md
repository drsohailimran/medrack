# ADR 0007 — Adaptive Retrieval (Pluggable Pipeline)

- Status: Accepted
- Date: 2026-06-29
- Phase: 7 (adaptive retrieval)
- Depends on: ADR 0005 (benchmark framework), ADR 0006 (structured medical metadata)

## Context

The Phase 5 baseline showed the real LLM uses ~7,200 prompt tokens per
10-mark theory answer. The Phase 6 metadata layer put structured
section flags on every chunk but the answer pipeline did not consume
them. Retrieval was still pure vector similarity with top_k=8 and no
section-awareness — questions about management, classification,
epidemiology, and national programmes all returned the same generic
top-8 by cosine distance.

The Phase 7 directive asks us to use the metadata to **influence
retrieval ranking** (not replace semantic search). Hybrid retrieval:
vector similarity remains the primary mechanism, metadata is an
additional signal. 5-mark questions should retrieve fewer chunks than
10-mark questions. Questions about management should retrieve more
management chunks. Answer quality has priority over token reduction.

## Decision

### Pluggable pipeline

The retrieval layer is a three-step pipeline. Each step is a separate
ABC and is independently swappable:

  1. **QuestionAnalyzer** (medrack.retrieval.analyzer) — extracts
     ``(marks, target_sections)`` from a question dict. v1 is
     deterministic regex; future LLM-based analyzers can subclass.
  2. **RetrievalStrategy** (medrack.retrieval.strategy) — produces a
     ``RetrievalPlan(top_k, metadata_filter)`` from the analysis. v1
     ships:
       - ``IdentityStrategy`` (top_k=8, no filter) — v0-compatible,
         for A/B testing.
       - ``AdaptiveStrategy`` (5-mark=5, 10-mark=8; filter for
         single-section questions only) — the v1 default.
  3. **Reranker** (medrack.retrieval.reranker) — reorders the
     retrieved chunks. v1 ships ``MetadataBoostReranker``, which
     multiplies the vector-similarity distance by a per-section boost
     factor (default 0.67, ~1.5x per match).

The three components are composed by ``RetrievalEngine``
(medrack.retrieval.engine), which is the only thing the answer
pipeline needs to import. The engine exposes a single function,
``retrieve_for_question``, that returns a ``RetrievalResult`` (chunks
+ diagnostic info).

### Hybrid retrieval

The reranker is **multiplicative on distance**, not additive. A
non-matching chunk's relative position among other non-matching chunks
is preserved — the reranker only reshuffles matching chunks to the
top. This is the literal "metadata is an additional signal" semantic
the directive asked for.

### No over-constraining

The AdaptiveStrategy's filter logic caps at 2 sections
(``MAX_SECTIONS_FOR_FILTER``). A question matching 3+ sections drops
the filter and lets the reranker handle the boost. Rationale: a
broad filter would exclude potentially-relevant chunks; the
directive says "do not remove useful evidence merely to reduce
tokens".

The QuestionAnalyzer caps at 4 sections (``MAX_SECTIONS``). A
question that mentions 5+ medical topics is too broad to filter on.

## Scope (v1)

### AdaptiveStrategy decisions
- **5-mark → top_k=5** (3 fewer than the v0 8)
- **10-mark → top_k=8** (unchanged)
- **unknown marks → top_k=8** (default)
- **target_sections = []** → no filter
- **1-2 target_sections** → metadata filter (split into structure +
  medical groups)
- **3+ target_sections** → no filter (let reranker boost)

### MetadataBoostReranker
- **boost_factor = 0.67** (~1.5x per match)
- **multi-match compound** — a chunk matching 2 sections gets
  distance * 0.67^2 ≈ 0.45
- **preserves input** — does not mutate the caller's list
- **handles None distance** — matching chunks still rank first

### QuestionAnalyzer
- 13 medical-section regex patterns (case-insensitive)
- 7 structural-section regex patterns
- Priority-ordered, deduplicated
- Caps at 4 sections

## Architectural guarantees

1. **Pluggable** — every component is an ABC. Future cross-encoder
   rerankers, LLM-based analyzers, blueprint-aware strategies slot
   in without changing callers.
2. **Isolated** — ``medrack.retrieval`` imports nothing from
   ``answer/``, ``bot/``, ``dashboard/``, ``benchmarks/``. The
   dependency is one-way: ``answer`` calls into ``retrieval``, not
   vice versa. Enforced by a test that AST-scans the module source.
3. **Hybrid, not filter-only** — the reranker is multiplicative, not
   a hard filter. Non-matching chunks are still returned in their
   original relative order; only matching chunks are boosted.
4. **Backward compatible at the engine boundary** —
   ``IdentityStrategy`` reproduces the v0 behavior exactly
   (top_k=8, no filter, no rerank boost). Use it for A/B tests.
5. **Diagnostic** — ``RetrievalResult`` exposes retrieval_latency,
   rerank_latency, top_k, metadata_filter_active, and the
   ``QuestionAnalysis``. Future phases can log these for
   per-question quality tracking.

## Compatibility

- The answer pipeline (``medrack.answer.generate``) replaces its
  direct ``medrack.ingest.index.query()`` call with
  ``medrack.retrieval.retrieve_for_question(...)``. The return
  shape is the same (list of chunk dicts with ``id``, ``text``,
  ``metadata``, ``distance``), so the downstream code is
  unchanged.
- The ``RETRIEVAL_TOP_K = 8`` constant in
  ``medrack.answer.generate`` is preserved for backward compat but
  is no longer the source of truth — the strategy decides.
- Existing chunks indexed with ``metadata=None`` (Phase 5 and
  earlier) are still queryable but won't match any metadata
  filter. They rank based on vector similarity alone. New chunks
  indexed with Phase 6 metadata can match the new filters.
- The Phase 5 mock benchmark baseline still produces identical
  numbers: 20/20 questions, 40/40 records, 100% success,
  cache_hit_rate=0.5, avg_total_latency=0.17s, total_tokens=12,000.
  Phase 7 made no changes to the answer pipeline, prompt
  templates, embedder, or benchmark engine.

## Benchmark comparison (mock, vs Phase 5 baseline)

| Metric | Phase 5 | Phase 6 | Phase 7 | Delta (P5→P7) |
|---|---|---|---|---|
| n_questions | 20 | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.170s | 0.169s | -0.004s |
| avg_pdf_generation | 0.005s | 0.005s | 0.005s | 0 |

**No regression in the mock benchmark.** Phase 7's adaptive
retrieval is exercised on every question (the analyzer + strategy +
reranker run for each) but the mock LLM returns canned responses
that don't depend on chunk selection, so the aggregate metrics are
unchanged.

## Out of scope for Phase 7

- **Real LLM benchmark** — would measure the actual prompt-token
  reduction and answer quality change. Blocked on the Phase 5
  real-LLM API hang issue. The operator can re-run
  ``medrack.benchmarks.run --llm real`` in a quiet session.
- **Planner** — the directive explicitly defers this.
- **Blueprint retrieval** — the directive explicitly defers this.
- **Cross-encoder reranker** — the directive explicitly defers this.
  The v1 reranker is metadata-only; a future cross-encoder can
  subclass ``Reranker`` and compose with the v1 boost.
- **LLM-based question analysis** — v1 is regex. A future LLM
  analyzer can subclass ``QuestionAnalyzer``.
- **Composite filters (AND/NOT)** — the v1 strategy uses OR within
  the structure/medical groups and AND across groups. More
  expressive filters belong to a future phase.
- **Evaluation of metadata quality on real LLM** — same blocker as
  the real benchmark above.
- **Integration with validation** — the directive explicitly says
  validation is a separate concern; the retrieval layer does not
  know about validation.
