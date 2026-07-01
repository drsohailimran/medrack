# ADR 0011 — Validation Pipeline (Quality Gate)

- Status: Accepted
- Date: 2026-06-29
- Phase: 11 (Validation Pipeline)
- Depends on: ADR 0001-0010 (the established MedRack architecture)

## Context

The Phase 1-10 architecture produces a free-form MBBS theory answer
through the pipeline: Planner → Blueprint → Retrieval → Reranker →
Writer. The Writer outputs prose with section headings, per-section
word targets, and evidence references.

What was missing was a **quality gate**: a component that determines
whether the generated answer satisfies MedRack's quality
requirements before it is accepted as a canonical cached answer.

The Phase 11 directive asks for a **Validation Pipeline** that:

  - Is the final stage of the pipeline (after Writer).
  - Is a collection of **independent rules**, not a monolithic
    validator.
  - Returns a **structured report** (pass/fail, score, per-rule
    results).
  - **NEVER** mutates the answer, the planner, the blueprint, the
    metadata, the reranking, or anything else.
  - Is **pluggable**: each rule is independently testable,
    independently enableable/disableable.
  - Stores validation results alongside cached answers for
    auditing and benchmarking (but never as part of the answer).

## Decision

### Module structure

```
medrack/validation/
├── __init__.py     (public API)
├── result.py       (Severity, ValidationResult, ValidationReport)
├── rules.py        (9 v1 rule classes)
└── pipeline.py     (ValidationPipeline orchestrator)
```

### Data model

- :class:`Severity` — enum of `PASS` / `WARN` / `FAIL`.
- :class:`ValidationResult` — a single rule's verdict (rule_name,
  severity, message, details).
- :class:`ValidationReport` — the aggregate report (pass_, score,
  results, failed_rules, warnings, informational_messages). JSON-
  serializable with schema_version=1.

### 9 v1 rules

Per the directive's example list (and the per-section word count
contract from Phase 2):

1. :class:`FormattingRule` — no empty answer, no excessive blank
   lines, no trailing whitespace, no absurdly long text.
2. :class:`HeadingStructureRule` — answer has proper section
   headings (e.g. "Definition:", "Management:").
3. :class:`DuplicateSectionRule` — no section title appears twice
   (case-insensitive).
4. :class:`EmptySectionRule` — no section is empty (zero or only
   whitespace).
5. :class:`WordCountRule` — per-section word count is within
   ±10% of the blueprint's target. Requires a blueprint.
6. :class:`RequiredSectionsRule` — all required sections from
   the blueprint are present. Requires a blueprint.
7. :class:`BlueprintComplianceRule` — the answer's section titles
   match the blueprint's expected titles. Requires a blueprint.
8. :class:`EvidenceCoverageRule` — each section references at
   least one retrieval chunk. Requires a blueprint.
9. :class:`ReferenceConsistencyRule` — chunk references within
   a section are unique.

### Blueprint independence

Per the directive, the validator must be independent of the
planner. Rules that require a blueprint are **duck-typed**: they
accept any object with ``.sections`` and ``.target_word_count``.
When no blueprint is provided, they emit `WARN` (not `FAIL`).

### Per-rule enable/disable

Each rule has an `enabled` flag. The pipeline skips disabled rules.
Custom rules can be added by subclassing :class:`Rule` and passing
the new rule to the pipeline constructor.

### Score formula

```
score = (PASS_count + 0.5 * WARN_count) / total_enabled_rules
```

A score of 1.0 means all enabled rules passed. A score of 0.0
means all enabled rules failed. WARN contributes half a PASS.

### No-mutation guarantee

The pipeline NEVER mutates:
- The answer (read-only inspection)
- The blueprint (read-only inspection)
- The planner's output
- The retrieval's chunks
- The metadata
- The reranking

If validation fails, the pipeline returns a structured report. The
cache-write logic uses the report to decide whether to store the
answer. Failed answers remain available for inspection; they never
silently overwrite a valid cached answer.

## Architecture guarantee

```
Planner -> Blueprint -> Retrieval -> Reranker -> Writer -> Validator
```

The Validator is the final stage. It is **independent of all
upstream layers** (no imports from answer/bot/dashboard/
benchmarks/ingest/retrieval/planner). The validator is a
**consumer** of the blueprint (duck-typed) but not a peer.

## Isolation

`medrack.validation` imports only from:

- The standard library
- `medrack.validation.result` (internal)
- `medrack.validation.rules` (internal)
- `medrack.validation.pipeline` (internal)

It does NOT import from:

- `medrack.answer.*` (writer)
- `medrack.bot.*` (Telegram bot)
- `medrack.dashboard.*` (Web UI)
- `medrack.benchmarks.*` (benchmark framework)
- `medrack.ingest.*` (vector index, metadata extractor)
- `medrack.retrieval.*` (retrieval layer)
- `medrack.planner.*` (planner; validator is duck-typed)

The isolation is enforced by AST tests in `test_validation.py`.

## Compatibility

- **No changes to existing layers.** Phase 11 lands the validation
  module; the answer pipeline does not yet consume it. Future
  phases (12+) can wire the validator into the answer pipeline.
- **No changes to the benchmark framework.** Phase 5's framework
  still produces the same numbers.
- **No changes to cached answers.** The validator is a new
  consumer; cached answers are unchanged.
- **Backward compat**: existing tests pass unchanged.

## Benchmark comparison (mock, vs Phase 5 baseline)

| Metric | Phase 5 | Phase 10 | Phase 11 | Delta (P5→P11) |
|---|---|---|---|---|
| n_questions | 20 | 20 | 20 | 0 |
| n_success | 40/40 | 40/40 | 40/40 | 0 |
| n_failure | 0 | 0 | 0 | 0 |
| cache_hit_rate | 0.500 | 0.500 | 0.500 | 0 |
| total_tokens | 12,000 | 12,000 | 12,000 | 0 |
| avg_total_latency | 0.173s | 0.169s | 0.168s | -0.005s |
| avg_pdf_generation | 0.005s | 0.005s | 0.005s | 0 |

**No regression in the mock benchmark.** Phase 11 is a pure
addition; the answer pipeline does not yet consume it; the
benchmark runs the v0-v10 pipeline and gets the same numbers.

## Out of scope for Phase 11

- **Wiring the validator into the answer pipeline.** That
  belongs to a future phase (12+). Phase 11 lands the module; the
  validator is *available* but not yet *consumed*.
- **Validation-based cache-write gating.** The cache layer can
  consume :class:`ValidationReport` to decide whether to store
  the answer. Phase 11 does not do this.
- **LLM-based validation.** v1 is deterministic. A future phase
  can add an LLM-based rule (subclass :class:`Rule` and call out
  to a model).
- **Per-chunk reference validation.** The v1
  :class:`EvidenceCoverageRule` and :class:`ReferenceConsistencyRule`
  use a simple regex-based heuristic. A future phase can validate
  against the actual retrieved chunk list.
- **Real LLM benchmark.** Same blocker as Phase 5/6/7/8/9/10
  (real-LLM API hang); the operator can re-run
  `medrack.benchmarks.run --llm real` in a quiet session.
- **Per-section custom rules.** v1 ships 9 rules; users can add
  custom rules by subclassing :class:`Rule`.

## Future direction

The Validation Pipeline is the foundation for **quality-gated
generation**. Future phases can:

  - Wire the validator into the answer pipeline (Phase 12+).
  - Add LLM-based validation rules (subclass :class:`Rule`).
  - Use :class:`ValidationReport` to gate the cache write
    (only PASS reports are eligible for canonical cache).
  - Use :class:`ValidationReport` for observability (dashboard
    shows pass/fail trends over time).
  - Use :class:`ValidationReport` to drive the writer (e.g. retry
    if a required section is missing — but the validator itself
    never mutates the answer).
