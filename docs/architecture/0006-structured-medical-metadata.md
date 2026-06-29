# ADR 0006 — Structured Medical Metadata (Pluggable Extractor Architecture)

- Status: Accepted
- Date: 2026-06-29
- Phase: 6 (structured medical metadata)
- Depends on: ADR 0001 (layered module architecture), ADR 0005 (benchmark framework — establishes the baseline this phase is measured against)

## Context

The Phase 5 benchmark baseline showed that the real LLM (qwen3.7-max) uses
~9,200 tokens per 10-mark theory answer, of which ~7,200 are prompt tokens
(prompt cost is the largest contributor to per-answer cost). The retrieval
layer currently returns 8 chunks of ~1000 tokens each, with no
section-awareness — the LLM receives a mix of definitions, classifications,
tables, flowcharts, and management paragraphs regardless of the question.

The Phase 6 directive asked us to **improve retrieval quality while
reducing prompt size** by enriching every chunk with structured metadata
at ingestion time. Future retrieval should be able to target specific
section types (definitions, tables, flowcharts, management) independently.

## Decision

### 1. Pluggable extractor interface

Metadata extraction is hidden behind an abstract base class
(`medrack.ingest.metadata.MetadataExtractor`). The v1 implementation
(`medrack.ingest.extractors.regex_extractor.RegexMetadataExtractor`) is
deterministic and uses only regex + heuristics. Future LLM-based or
hybrid extractors can be added as new modules in
`medrack.ingest.extractors` without changing the ingestion pipeline.

The extractor receives the chunk text plus provenance context and
returns a `ChunkMetadata` object. It **never modifies the chunk text**
— metadata is additive.

### 2. Grouped metadata dataclasses

Metadata is internally organized as three grouped dataclasses
(`StructureMetadata`, `MedicalMetadata`, `ExamMetadata`) aggregated
into a `ChunkMetadata`. The application never depends on ChromaDB's
scalar-only metadata constraint. The flat dict is computed only at
the persistence boundary (`flatten_for_chroma` in
`medrack.ingest.metadata`).

### 3. Typed retrieval filter

Retrieval uses a `MetadataFilter` dataclass (lists of section names to
include) which is translated to ChromaDB's `where` clause by
`filter_to_chroma_where`. The rest of the application does not need to
know Chroma's filter syntax.

### 4. Section-based naming

Field names describe the section represented (`section_management`,
`section_epidemiology`), not implementation-specific boolean properties
(`has_management`). This is the language retrieval will use.

### 5. Excluded from Phase 6

Per the directive, `previous_university_question` and
`frequently_asked` are **excluded**. They belong to the question-bank
layer, not textbook ingestion. They will be addressed in a later phase
when the question-bank layer is designed.

## Scope (v1)

### StructureMetadata (7 fields)
- `section_definition` — "defined as", "definition:", "is a (disease|disorder|condition|...)"
- `section_classification` — "classification", "stage I-IV", "type 1-4"
- `section_flowchart` — arrow chains (→, ->, ⇒), "flowchart", "algorithm"
- `section_table` — "table N", "see table"
- `section_diagram` — "figure N", "see figure", "illustration"
- `section_formula` — math symbols (Σ, ∫, ±), "formula", "equation"
- `section_conclusion` — "conclusion", "summary:", "take-home point"

### MedicalMetadata (13 fields)
- `section_epidemiology`, `section_etiology`, `section_pathogenesis`,
  `section_risk_factors`, `section_clinical_features`,
  `section_diagnosis`, `section_differential_diagnosis`,
  `section_investigations`, `section_management`, `section_prevention`,
  `section_national_programme`, `section_medicolegal`,
  `section_statistics`

### ExamMetadata (3 fields)
- `important_years: list[int]` — 4-digit numbers in 1900-2100
- `important_numbers: list[str]` — integers >= 1000 (raw form, with commas)
- `keywords: list[str]` — top unigrams by frequency, stopword-filtered

### Excluded
- `previous_university_question` — question-bank layer (later phase)
- `frequently_asked` — question-bank layer (later phase)

## Architectural guarantees

1. **Additive** — chunk text is never modified. The extractor reads it
   and returns metadata alongside.
2. **Pluggable** — the extractor is an ABC. v1 ships a regex
   implementation; future LLM or hybrid extractors subclass the ABC
   and are swapped in via the `extractor=` parameter to `chunk_pages`.
3. **Isolated** — `medrack.ingest.metadata` and
   `medrack.ingest.extractors` have no imports from
   `medrack.answer.*`, `medrack.bot.*`, `medrack.dashboard.*`, or
   `medrack.benchmarks.*`. Coupling is one-way: the pipeline calls
   into metadata, not vice versa.
4. **Backward compatible** — `Chunk.metadata` is `Optional[ChunkMetadata]`
   with a default of `None`. `chunk_pages(extractor=None)` works exactly
   as before. `index_chunks` handles both cases. `query()` defaults to
   no filter.
5. **Chroma boundary is local** — `flatten_for_chroma` and
   `filter_to_chroma_where` are the only two functions that know
   about Chroma's scalar-only constraint. Everything else in the
   application uses the typed grouped form.

## Consequences

### Positive
- Future LLM extractors can be added as new modules without touching
  the ingestion pipeline.
- Retrieval can now answer "give me only the management chunks" or
  "give me only the definitions" — reducing prompt size and improving
  answer quality.
- The grouped dataclasses give a clean typed API to the rest of the
  application; Chroma quirks are hidden behind two functions.
- Deterministic v1 extractor means re-ingesting the same PDF produces
  the same metadata, which means cache keys remain stable.

### Negative / risks
- v1 regex extractor is conservative: it will miss some valid
  section flags (false negatives are acceptable; false positives
  would waste prompt tokens).
- Keyword extraction is unigram-frequency-based for v1 — no
  lemmatization, no stopword-aware phrase detection. Future phases
  can add NLP here.
- Important-numbers extraction only handles integers >= 1000 with
  comma-separated thousands. Fractions, percentages, ratios are not
  captured.
- Section filtering is per-section-flags only. Future phases may need
  composite filters (e.g. "management AND has epidemiology") or
  negation (e.g. "NOT table").

## Compatibility

- Existing v0 chunks (with `metadata=None`) are still indexable and
  queryable. They simply don't participate in section-targeted
  retrieval.
- Existing Chroma collections are forward-compatible: re-indexing
  adds the new metadata fields without breaking the old ones.
- Existing tests (`test_ingest_chunk.py`, `test_ingest_index.py`)
  pass unchanged — verified after Phase 6 implementation.
- The Phase 5 mock benchmark baseline still produces identical
  numbers (20/20 questions, 40/40 records, 100% success,
  cache_hit_rate=0.5, avg_total_latency=0.17s) — Phase 6 made no
  changes to the benchmark engine or the answer pipeline.

## Benchmark comparison

| Metric | Phase 5 mock baseline | Phase 6 mock regression | Delta |
|---|---|---|---|
| n_questions | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.170s | -0.003s |
| avg_pdf_generation | 0.005s | 0.005s | 0 |

**No regression.** Phase 6 is purely additive — it does not touch
the answer pipeline, the prompt templates, the embedder, or the
retrieval defaults. Existing answers continue to work; new chunks
carry metadata for future-targeted retrieval.

## Out of scope for Phase 6

- Using the metadata at answer-generation time (i.e. filtering
  chunks before sending to the LLM). This is a future phase — the
  metadata is now available, the answer pipeline does not yet
  consume it.
- Cross-chunk aggregation (e.g. "give me the top 3 management
  chunks AND the top 1 definition chunk"). The current `query()`
  returns a single ranked list.
- LLM-based extractors. v1 is regex-only.
- Reranker integration. Retrieval is still pure vector-similarity.
- Evaluation of metadata quality on the real LLM (would require
  re-running the real baseline benchmark, which was not feasible
  in Phase 5 due to real-LLM API hangs).
