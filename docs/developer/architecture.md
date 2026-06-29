# MedRack Architecture

This document describes the MedRack backend architecture. It is
intended for engineers who need to understand the system at a
deep level, not just integrate with the API.

## High-level architecture

MedRack is a local medical AI system that generates publication-
quality MBBS university answers from trusted medical textbooks.
The user provides a question; the system produces a structured
answer with section headings, evidence references, and a PDF
output.

The backend is a pipeline of six layers:

```
Planner  →  Blueprint  →  Retrieval  →  Reranker  →  Writer  →  Validator
                                                        ↓
                                                    Cache (canonical)
```

Each layer has exactly one responsibility. The layers are
independent: any layer can be replaced without changing the
others (subject to the data contracts).

## Pipeline layers

### 1. Planner (`medrack.planner`)

The Planner is a **deterministic** component that converts a
question into a structured answer blueprint. It does NOT retrieve
documents, write answers, or perform validation.

**Input:** question text, subject, marks, question type
**Output:** `Blueprint` (a list of `Section` records with target
word counts and required flags)

**Determinism:** same input → same blueprint. No LLM calls.

### 2. Blueprint (`medrack.retrieval.blueprint_retrieval`)

The Blueprint Retrieval spec is the **retrieval-aware enrichment**
of the Planner's output. The Planner decides *which sections*;
the Blueprint decides *what evidence to retrieve for each
section*.

**Input:** `Blueprint` (from the Planner)
**Output:** `BlueprintRetrieval` (per-section metadata filters,
priorities, evidence categories)

**Determinism:** same input → same spec. No I/O.

### 3. Retrieval (`medrack.retrieval`)

The Retrieval layer fetches evidence from the vector index
(ChromaDB). It uses a **pluggable strategy** that decides top_k
based on the question's marks, and a **metadata filter** based
on the Blueprint's required sections.

**Input:** question embedding, subject, Blueprint Retrieval spec
**Output:** ranked list of chunks (with metadata)

**Components:**
- `medrack.retrieval.engine` — the orchestrator
- `medrack.retrieval.strategy` — pluggable retrieval strategies
  (`AdaptiveStrategy` is the v1 implementation)
- `medrack.retrieval.analyzer` — question analyzer (marks +
  topic detection)
- `medrack.retrieval.reranker` — Phase 7 metadata-boost reranker

### 4. Reranker (`medrack.retrieval.rerankers`)

The Reranker is a **pluggable** component that re-orders the
retrieved chunks by semantic relevance. The v1 is a deterministic
heuristic; future cross-encoder / BGE / LLM-based rerankers are
drop-in subclasses of the `Reranker` ABC.

**Input:** question, chunks, Blueprint Retrieval spec, top_n
**Output:** reranked chunks (same shape, possibly different order)

**Components:**
- `Reranker` — generic ABC
- `HeuristicReranker` — v1 deterministic implementation
- `IdentityReranker` — no-op pass-through (default; system
  functions correctly if reranking is disabled)

### 5. Writer (`medrack.answer`)

The Writer generates the answer prose from the blueprint and
retrieved evidence. It uses the LLM (or mock) to synthesize the
answer.

**Input:** Blueprint, retrieved chunks, subject, marks
**Output:** answer text (with section headings), PDF

**Components:**
- `medrack.answer.prompt` — subject-aware prompt templates
- `medrack.answer.generate` — the orchestrator
- `medrack.answer.render` — PDF rendering
- `medrack.answer.cache` — answer cache
- `medrack.answer.llm` — LLM client

### 6. Validator (`medrack.validation`)

The Validator is a **quality gate** with 9 independent rules. It
inspects the generated answer and returns a structured
`ValidationReport`. It NEVER mutates the answer.

**Input:** answer text, optional Blueprint
**Output:** `ValidationReport` (pass/fail, score, per-rule
verdicts)

**Rules (v1):**
1. `FormattingRule` — basic formatting checks
2. `HeadingStructureRule` — proper section headings
3. `DuplicateSectionRule` — no duplicate section titles
4. `EmptySectionRule` — no empty sections
5. `WordCountRule` — per-section word count within ±10% of
   blueprint target
6. `RequiredSectionsRule` — all required sections present
7. `BlueprintComplianceRule` — answer matches blueprint sections
8. `EvidenceCoverageRule` — each section references ≥1 chunk
9. `ReferenceConsistencyRule` — chunk references are unique

## Module layout

```
medrack/
├── __init__.py
├── config.py                # global config (PIPELINE_VERSIONS, word counts)
├── state.py                 # state machine
├── orchestrate.py           # CLI orchestration
├── cli.py                   # CLI entry point
│
├── answer/                  # Writer
│   ├── prompt.py
│   ├── generate.py
│   ├── render.py
│   ├── cache.py
│   ├── llm.py
│   ├── versioning.py
│   └── ...
│
├── ingest/                  # Ingestion
│   ├── format_detect.py
│   ├── clean.py
│   ├── chapter.py
│   ├── chunk.py
│   ├── embed.py
│   ├── index.py
│   ├── metadata.py          # structured metadata (Phase 6)
│   └── extractors/          # pluggable extractors
│
├── retrieval/               # Retrieval + Reranker
│   ├── engine.py            # orchestrator
│   ├── strategy.py          # pluggable strategies
│   ├── analyzer.py          # question analyzer
│   ├── reranker.py          # Phase 7 metadata-boost reranker
│   ├── rerankers.py         # Phase 10 generic Reranker ABC
│   └── blueprint_retrieval.py  # Phase 9 Blueprint Retrieval spec
│
├── planner/                 # Planner (Phase 8)
│   ├── blueprint.py
│   ├── rules.py
│   └── planner.py
│
├── validation/              # Validator (Phase 11)
│   ├── result.py
│   ├── rules.py
│   └── pipeline.py
│
├── benchmarks/              # Benchmark framework (Phase 5)
│   ├── engine.py
│   ├── report.py
│   └── run.py
│
├── bot/                     # Telegram bot
│   └── app.py
│
├── dashboard/               # Operator Console + API (Phase 12)
│   ├── app.py               # existing Gradio dashboard
│   ├── services/            # stable service interfaces
│   │   ├── library.py
│   │   ├── questions.py
│   │   ├── pipeline.py
│   │   ├── validation.py
│   │   ├── benchmarks.py
│   │   ├── cache.py
│   │   ├── version.py
│   │   └── logs.py
│   └── api/                 # v1 HTTP API (FastAPI)
│       └── v1.py
│
└── tests/                   # pytest test suite
```

## Data flow

A complete answer generation request flows through the pipeline
as follows:

1. **CLI / API / Bot** receives a question
2. **Question is analyzed** (`analyzer.py`): marks, target_sections
3. **Strategy decides** (`strategy.py`): top_k, metadata filter
4. **Vector index query** (`ingest/index.py`): raw chunks
5. **Metadata-boost rerank** (`retrieval/reranker.py`): chunks
   reordered by metadata match
6. **Semantic rerank** (`retrieval/rerankers.py`): chunks
   reordered by heuristic
7. **Planner runs** (`planner/rules.py`): Blueprint
8. **Blueprint Retrieval spec** (`retrieval/blueprint_retrieval.py`):
   retrieval-aware spec
9. **Writer runs** (`answer/generate.py`): prompt, LLM call, render
10. **Validator runs** (`validation/pipeline.py`): 9 rules
11. **Cache stores** the validated answer (`answer/cache.py`)
12. **PDF is generated** (`answer/render.py`)

## Authoritative decisions

The 12 ADRs in `docs/architecture/` are the authoritative source
for architectural decisions. Each ADR records:
- Context
- Decision
- Architecture guarantee
- Compatibility
- Out of scope (future work)

The ADRs are the contract between the backend and any future
frontend.

## Stability

The backend is **frozen** as of the Backend Freeze v1.0. No new
AI pipeline stages will be introduced. Future work focuses on
bug fixes, performance, compatibility, and frontend integration.
