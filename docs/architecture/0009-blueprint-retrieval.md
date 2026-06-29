# ADR 0009 — Blueprint Retrieval (Retrieval-Aware Enrichment of the Planner Blueprint)

- Status: Accepted
- Date: 2026-06-29
- Phase: 9 (Blueprint Retrieval)
- Depends on: ADR 0005 (benchmark framework), ADR 0007 (adaptive retrieval), ADR 0008 (Planner)

## Context

The Phase 8 Planner produces a :class:`Blueprint` that lists which
sections the answer should have, in what order, with what word
targets. The retrieval layer (Phase 7) is metadata-aware: it can
filter chunks by their section flags (e.g. "give me only
management chunks") and boost matching chunks in the reranker.

What was missing was a bridge between the two: a way to say "for the
management section, retrieve management chunks; for the
epidemiology section, retrieve epidemiology chunks; for the
introduction, no specific filter needed".

The Phase 9 directive asks us to add that bridge. The Blueprint
Retrieval spec consumes the Planner's Blueprint and produces a
:class:`BlueprintRetrieval` — a typed, JSON-serializable, deterministic
spec that says *what evidence to retrieve for each section, in what
priority, with what constraints*.

## Decision

### Module structure

```
medrack/retrieval/blueprint_retrieval.py   # BlueprintRetrieval + SectionRetrievalSpec
medrack/tests/test_blueprint_retrieval.py   # 19 new tests
```

### Data model

A :class:`BlueprintRetrieval` contains:

- Top-level fields echoed from the Planner blueprint: ``subject``,
  ``marks``, ``question_type``, ``target_word_count``.
- ``section_specs``: ordered list of :class:`SectionRetrievalSpec`,
  one per Planner section, in the same order as the Planner blueprint.
- ``aggregate_metadata_filter``: union of all per-section
  :class:`MetadataFilter`s. Useful for retrieval strategies that want
  a single filter to apply.
- ``evidence_categories``: distinct list of ``metadata_section`` values
  across all sections (the union, deduplicated).

A :class:`SectionRetrievalSpec` contains:

- ``section_name``: the Planner section's name.
- ``metadata_filter``: per-section :class:`MetadataFilter`. Empty for
  framing sections (introduction, conclusion) that have no chunk-
  metadata equivalent.
- ``priority``: 0 for required, 2 for optional. (1 is reserved for
  future use.)
- ``min_chunks``, ``max_chunks``: per-section chunk budget. The v1
  default is ``min_chunks=1, max_chunks=3``.
- ``evidence_category``: the Planner section's ``metadata_section`` or
  ``None`` for framing sections.

### v1 rules (deterministic, pure)

For each Planner section:

1. If the section has a ``metadata_section`` (e.g.
   ``section_management``), build a single-section
   :class:`MetadataFilter` for that section. Otherwise the filter
   is empty.
2. ``priority`` = 0 if the section is ``required``, else 2.
3. ``min_chunks`` = 1 (every section needs at least one chunk to be
   grounded).
4. ``max_chunks`` = 3 (the v1 budget per section).
5. ``evidence_category`` = the section's ``metadata_section`` or
   ``None``.

The aggregate filter is the deduplicated union of all per-section
filters. The evidence categories list is the deduplicated union of
all per-section ``metadata_section`` values.

### JSON contract

Schema version 1. Same pattern as Phase 8: ``to_json`` / ``from_json``
/ ``to_dict`` / ``from_dict`` helpers, deterministic (sorted keys),
rejects unknown schema versions.

### What the Blueprint Retrieval spec is NOT

Per the directive:

- It does **not** perform retrieval. No ChromaDB calls, no
  ``medrack.ingest.index.query`` calls.
- It does **not** generate prose. The writer is a future phase.
- It does **not** modify the Planner's section list. The
  ``section_specs`` list is in the same order as the Planner's
  ``sections`` list; sections are never added or removed.
- It does **not** perform validation. The validator is a future
  phase.

The spec is a *pure data layer* between the Planner's structural
decisions and the future retrieval strategies that will consume
them.

## Architecture guarantee

The Blueprint Retrieval sits between the Planner and the future
retrieval strategies:

```
Planner -> Blueprint -> [Blueprint Retrieval] -> Retrieval -> Writer -> Validator
```

It is the bridge that translates the Planner's structural decisions
(what sections to write) into retrieval-ready specs (what evidence
to fetch). Future retrieval strategies can consume the
:class:`BlueprintRetrieval` to:

- Allocate per-section chunk budgets (so the management section
  gets more management chunks than the introduction).
- Apply per-section metadata filters (so the management section
  only sees management chunks).
- Prioritize sections (so high-priority sections get their
  evidence first).
- Skip low-priority sections when chunk budget is tight.

None of this is wired into the answer pipeline yet — that's a
future phase (Phase 10: Writer with blueprint, or earlier: the
retrieval engine could start consuming ``BlueprintRetrieval`` if
the operator wants).

## Isolation

``medrack.retrieval.blueprint_retrieval`` imports only from:

- :mod:`medrack.ingest.metadata` (for the ``MetadataFilter`` type and
  the ``StructureMetadata`` / ``MedicalMetadata`` field catalogs)
- The standard library

It does **not** import from:

- ``medrack.answer.*`` (writer)
- ``medrack.bot.*`` (Telegram bot)
- ``medrack.dashboard.*`` (Web UI)
- ``medrack.benchmarks.*`` (benchmark framework)
- ``medrack.planner.*`` (planner is the *upstream* producer; the
  spec is duck-typed to accept any object with the right shape)
- ``medrack.retrieval.*`` (other retrieval modules — the spec is
  the data; the engine and analyzer are consumers, not peers)

The duck-typed contract is enforced by a test that builds a
``FakeBlueprint`` and confirms the spec is constructed from it
without type errors.

## Compatibility

- **No changes to the Planner.** Phase 9 consumes the Planner's
  Blueprint as a duck-typed input. The Planner's interface is
  unchanged.
- **No changes to the existing retrieval layer.** Phase 7's
  ``RetrievalEngine`` is untouched. Future phases may wire the
  ``BlueprintRetrieval`` into the engine, but Phase 9 just lands
  the data layer.
- **No changes to the answer pipeline.** The answer pipeline does
  not yet consume the Planner or the Blueprint Retrieval spec.
- **No cached answers are invalidated.** The new spec is a
  retrieval-side data structure; cached answers are unchanged.
- **No benchmark framework changes.** The Phase 5 framework still
  produces the same numbers.

## Benchmark comparison (mock, vs Phase 5 baseline)

| Metric | Phase 5 | Phase 6 | Phase 7 | Phase 8 | Phase 9 | Delta (P5→P9) |
|---|---|---|---|---|---|---|
| n_questions | 20 | 20 | 20 | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 40/40 | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 12,000 | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.170s | 0.169s | 0.168s | 0.173s | 0 |
| avg_pdf_generation | 0.005s | 0.005s | 0.005s | 0.005s | 0.005s | 0 |

**No regression in the mock benchmark.** Phase 9 is a pure data
layer; the answer pipeline does not yet consume it; the benchmark
runs the v0-v7 pipeline and gets the same numbers as every other
phase.

## Out of scope for Phase 9

- **Wiring the Blueprint Retrieval into the answer pipeline.** That
  belongs to Phase 10 (Writer with blueprint) and possibly the
  retrieval engine (Phase 7+). Phase 9 just lands the data layer.
- **Retrieval strategies that consume the spec.** A future
  ``BlueprintRetrievalStrategy`` can subclass
  :class:`medrack.retrieval.strategy.RetrievalStrategy` and consume
  the spec. Phase 9 does not do this.
- **Cross-encoder reranker integration.** Explicitly deferred per
  the Phase 7 directive; the v1 reranker is metadata-only.
- **Per-corpus section availability.** The v1 spec assumes all
  sections are available. A future phase can consume the Planner's
  ``metadata_summary`` to skip unavailable sections.
- **Composite filters (AND/NOT across groups).** Same constraint as
  Phase 7; future phase can extend.

## Future direction

The Blueprint Retrieval spec is the *contract* between the Planner
and the future retrieval strategies. Once wired, the answer
pipeline will:

1. Call the Planner → get a ``Blueprint``
2. Call ``build_blueprint_retrieval(blueprint)`` → get a
   ``BlueprintRetrieval`` (this phase)
3. Pass the spec to a retrieval strategy → get section-specific
   chunks
4. Pass the chunks + the Planner's word targets to the writer
5. The validator checks that all required sections got their
   evidence

The spec is the typed, JSON-serializable, deterministic link in
this chain. Future phases (10+) can consume it without re-deriving
the per-section metadata filters or priority logic.
