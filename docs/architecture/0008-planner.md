# ADR 0008 — Planner (Deterministic Answer Blueprinting)

- Status: Accepted
- Date: 2026-06-29
- Phase: 8 (Planner)
- Depends on: ADR 0005 (benchmark framework), ADR 0006 (structured medical metadata), ADR 0007 (adaptive retrieval)

## Context

The answer pipeline (Phase 2) takes a question and produces a free-form
MBBS theory answer. The current pipeline is **structure-blind**: the
prompt template asks the LLM to "discuss the management" but does not
say *what* the answer should look like (which sections, in what
order, how many words per section). The writer's only structural cue
is the word count target (5-mark = 475w, 10-mark = 775w), which is
honored unevenly across LLM runs.

The Phase 8 directive asks us to add a **Planner** between the
question and the writer. The Planner is a deterministic component
that converts a question into a structured answer blueprint. The
blueprint tells the writer which sections to include, in what order,
and how many words each section gets.

The Planner is **not** an autonomous agent. It does not retrieve
documents, does not generate prose, and does not perform validation.

## Decision

### Module structure

```
medrack/planner/
├── __init__.py     (public API)
├── blueprint.py    (Blueprint, Section, SectionCategory, JSON)
├── rules.py        (deterministic rules engine)
└── planner.py      (Planner ABC + DeterministicPlanner v1)
```

### Blueprint

A :class:`Blueprint` is a JSON-serializable, machine-readable contract
between the Planner and the downstream consumers (retrieval, writer).
Schema version 1. Fields:

- ``subject`` — the subject (``"psm"``, ``"fmt"``)
- ``marks`` — 5 or 10 (None for MCQ)
- ``question_type`` — ``"theory"`` or ``"mcq"``
- ``target_word_count`` — overall target
- ``sections`` — ordered list of :class:`Section` objects
- ``required_metadata_categories`` — set of ChunkMetadata section
  names the downstream retrieval should target

A :class:`Section` has:

- ``name`` — human-readable name (``"management"``, ``"introduction"``)
- ``category`` — :class:`SectionCategory` (STRUCTURE / MEDICAL / FRAMING)
- ``target_word_count`` — the writer's target
- ``required`` — must be present
- ``metadata_section`` — the ChunkMetadata flag (e.g. ``"section_management"``)
  or ``None`` for framing sections

### Rules engine (v1, deterministic)

The :class:`RulesEngine` is a pure deterministic function:
``(PlannerInput) -> Blueprint``. No I/O, no LLM, no randomness.

Rules in v1:

1. **Section detection** — same vocabulary as Phase 6/7's metadata
   extractor (13 medical + 7 structural patterns). Priority-ordered,
   deduplicated.
2. **Canonical ordering** — medical sections follow standard answer
   order (definition → epidemiology → etiology → pathogenesis → risk
   factors → classification → clinical features → diagnosis →
   differential → investigations → **management** → prevention →
   national programme → medicolegal → statistics). Structural
   sections are appended in their own canonical order.
3. **Section capping** — 5-mark caps at 3 detected sections, 10-mark
   at 7, unknown marks default to 7.
4. **Word allocation** — introduction = 15% of target, conclusion =
   10% of target, remainder split equally among detected sections.
   With no detected sections, the body budget folds into the
   introduction so the writer still produces a sensible-length intro.
5. **Target word counts** — ``("theory", 5) = 475``,
   ``("theory", 10) = 775``. MCQ target is 0 (MCQ blueprints are
   minimal — just the answer).

### Planner (v1)

The :class:`Planner` ABC defines the contract. The
:class:`DeterministicPlanner` v1 implementation wraps the rules
engine with input validation:

- ``question_text`` must be non-empty
- ``subject`` must be non-empty
- ``question_type`` must be ``"theory"`` or ``"mcq"``
- ``marks`` must be 5, 10, or None

Validation failures raise :class:`ValueError`; the caller is
responsible for catching and reporting.

A module-level :func:`plan_for_question` helper is the v1 entry point
(it builds the input and calls the planner).

## Architecture guarantee

The Planner sits at the head of the pipeline:

```
Planner -> Blueprint -> Retrieval -> Writer -> Validator
```

The Planner's contract is the :class:`Blueprint` — a typed
JSON-serializable object. Downstream stages consume the blueprint
without needing to know how it was produced. Future phases can:

- **Phase 9 (Blueprint Retrieval)**: use
  ``Blueprint.required_metadata_categories`` to bias retrieval.
- **Phase 10 (Writer)**: use ``Blueprint.sections`` and
  ``Blueprint.target_word_counts`` to organize the answer.
- **Phase 11 (Validation)**: use ``Blueprint`` to validate that the
  answer covers all required sections.

## Isolation

``medrack.planner`` imports nothing from:

- ``medrack.answer.*`` (writer)
- ``medrack.retrieval.*`` (retrieval implementation)
- ``medrack.ingest.*`` (vector index, metadata extractor)
- ``medrack.bot.*`` (Telegram bot)
- ``medrack.dashboard.*`` (Web UI)
- ``medrack.benchmarks.*`` (benchmark framework)

It does import the standard library and :mod:`re` (for section
detection). Enforced by an AST test that scans all four planner
modules.

The Planner is *intentionally* decoupled from the retrieval analyzer
even though they share vocabulary. The retrieval analyzer's job is
"what does retrieval need"; the planner's job is "what should the
answer look like". Different responsibilities, different modules.

## Compatibility

- **No changes to the answer pipeline.** Phase 8 lands the Planner
  module; future phases (Phase 9+) will wire it into the answer
  pipeline. The current ``generate.py`` still works exactly as it
  did in Phase 7.
- **No changes to the retrieval layer.** Phase 7's adaptive
  retrieval is untouched.
- **No changes to the benchmark framework.** Phase 5's framework
  still produces the same numbers.
- **No cached answers are invalidated.** The planner is a new
  layer; existing cached answers are still valid.

## Benchmark comparison (mock, vs Phase 5 baseline)

| Metric | Phase 5 | Phase 6 | Phase 7 | Phase 8 | Delta (P5→P8) |
|---|---|---|---|---|---|
| n_questions | 20 | 20 | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.170s | 0.169s | 0.168s | -0.005s |
| avg_pdf_generation | 0.005s | 0.005s | 0.005s | 0.005s | 0 |

**No regression in the mock benchmark.** Phase 8 is a pure-additive
layer that the answer pipeline does not yet consume; the benchmark
runs the v0-v7 pipeline and gets the same numbers as every other
phase.

## Out of scope for Phase 8

- **Wiring the Planner into the answer pipeline.** That belongs to
  Phase 9 (Blueprint Retrieval) and Phase 10 (Writer with
  blueprint). Phase 8 just lands the planner module; the planner is
  *available* but not yet *consumed*.
- **LLM-based planner.** v1 is regex-only. A future phase can
  subclass :class:`Planner` and call out to a model.
- **Composite sections** (e.g. "etiology + risk factors as one
  paragraph"). v1 emits one section per detected pattern. A future
  phase can add a "merging" step.
- **Per-corpus section availability.** The v1 planner assumes all
  sections are available in the corpus. A future phase can consume
  the ``metadata_summary`` input to skip unavailable sections.
- **Authoring the answer.** The Planner outputs the blueprint; the
  writer is a future phase.

## Future direction

The Planner is the foundation for **structured answer generation**:
the writer (Phase 10) will receive the blueprint and produce a
section-by-section answer with per-section word targets, ordering,
and metadata guidance. The retrieval layer (Phase 9) will use
``required_metadata_categories`` to bias which chunks are returned.
The validator (Phase 11) will check that all required sections are
present and the per-section word counts are within tolerance.
