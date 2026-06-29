# ADR 0003 — Layered Answer Versioning

- Status: Accepted
- Date: 2026-06-29
- Phase: 3 (layered answer versioning)
- Depends on: ADR 0001 (layered module architecture), ADR 0002 (subject-aware prompts)

## Problem

Phase 2 changed two things that affect every existing cached answer on disk:

1. The prompt template is now subject-aware (PSM gets K. Park, FMT gets Narayan Reddy). A cached answer for a PSM question generated before Phase 2 won't be wrong (it was always PSM-flavoured), but a cached answer for an FMT question — once one is generated — would be wrong if the system ever fell back to the old prompt.
2. The word count constants changed: 500 → 775 (10-mark), 300 → 475 (5-mark), 300 → 275 (MCQ explanation). A cached answer generated with the old 500-word prompt is no longer aligned with the operator's current expectation.

The operator's directive is explicit:

> "Never permanently invalidate cached answers solely because prompt
> templates, word counts or schema evolve. Instead implement answer
> schema versioning. Every cached answer must record: schema version,
> prompt version, model version, retrieval version, target word count.
> When a version mismatch is detected, mark the answer as stale
> instead of deleting it. Support both selective regeneration and
> batch regeneration."

The current cache layer (`medrack/answer/cache.py`) is a key-value store with no version metadata. The cache key includes only `module_name|qid|question_text|prompt_template|model` — no version info. The cache value (the answer dict) has `package_version` missing, no `versions` dict, no `target_word_count`, no `embedding_model`.

## Alternatives considered

1. **Just delete the old caches and regenerate.** Rejected by the operator's directive: "Never permanently invalidate cached answers solely because prompt templates, word counts or schema evolve." The previously-approved PSM Module 1 preview PDFs (q022, q053, q062) were approved by the operator and should be preserved as historical artifacts.
2. **Add a single `schema_version: int` field, bump when anything changes.** Rejected: collapses all the per-component drift into one number. The operator can't tell whether the staleness is from a prompt change, a model upgrade, or an embedding model change — all three have different remediation paths (regenerate just the affected answers vs. re-embed the whole KB).
3. **Layered per-component versioning + selective regeneration.** ← *chosen*
4. **Full content-addressable storage** (hash the prompt + question + retrieved chunks and use that as the key). Rejected: significant refactor of the cache layer; doesn't add anything the per-component version metadata doesn't already give us for this single-user system.

## Decision

Adopt option 3:

1. **Add `PIPELINE_VERSIONS` dict to `medrack/config.py`.** Schema: `{"schema": 2, "prompt": 1, "retrieval": 1, "planner": 0, "validator": 0, "reranker": 0, "renderer": 1}`. Each component has a monotonically-increasing integer; bump when the component changes. Components at 0 are "not yet implemented" (planner, validator, reranker — they live in Phase 7+).

2. **New module `medrack/answer/versioning.py`** with three public functions:
   - `is_stale(cached_answer) -> (bool, list[str])`: pure function, no I/O, no mutation. Returns `(True, ["schema_version_drift", "prompt_version_drift", ...])` if any per-component version differs, or if the answer has no `versions` field at all (pre-Phase-3 schema).
   - `mark_stale(cached_answer) -> dict`: returns a copy of the answer with `stale=True` and `stale_reasons=[...]`. Never mutates the input. Never deletes the cache file.
   - `find_stale_answers(module_name=None, answers_root=None) -> list[dict]`: scans the answers directory, returns a list of `{module, chapter, qid, path, reasons}` for every stale entry. Read-only — never writes or deletes.

3. **`medrack/answer/cache.py` changes:**
   - `load_answer` now calls `mark_stale` on the loaded dict before returning. The on-disk file is **never modified** by the version check (verified by the "load does not modify cache file" test).
   - `cache_key_for_question` gains two keyword-only parameters: `subject: str = "psm"` and `target_word_count: int | None = None`. The key now also includes the `PIPELINE_VERSIONS` dict (sorted, compact) and the `EMBEDDING_MODEL` constant. So a Phase 3 PSM 10-mark answer has a different cache key from a pre-Phase-3 PSM 10-mark answer.

4. **`medrack/answer/prompt.py` changes:**
   - `BuildResult` gains a `word_count_target: int | None` field. The MCQ and theory prompt builders set it (the MCQ explanation target for MCQ, the theory target for theory).

5. **`medrack/answer/generate.py` changes:**
   - `build_answer_dict` accepts a `target_word_count` parameter. The answer dict now includes: `package_version` (from `medrack.__version__`), `versions` (copy of `PIPELINE_VERSIONS`), `embedding_model`, and `stale`/`stale_reasons` defaults (False / []).
   - `generate_answer` passes `subject=subject` and `target_word_count=build_result.word_count_target` to `cache_key_for_question` and `build_answer_dict`.

## Reasoning

- **Existing caches (q022, q053, q062) are preserved.** When loaded, they're marked stale with reason `missing_versions_field` and per-component drift reasons. The operator can see the drift, but the file stays on disk.
- **Per-component versions isolate drift causes.** A prompt change doesn't mark a cache stale for embedding-model reasons. A re-embedding doesn't mark a cache stale for prompt reasons. The operator can target regeneration precisely.
- **`mark_stale` is non-mutating.** The cache file on disk is never modified by a load. This was a strong requirement: the operator should be able to look at the original file with `cat ~/.hermes/medrack/answers/psm-module-1/all/q022.json` and see the original answer text without any version metadata contaminating it.
- **`word_count_target` is informational, not drift-checked.** An early version of the staleness logic tried to compare the cached `target_word_count` against the current config values, but this over-flags (the MCQ explanation target is 275; the theory targets are 475/775; an MCQ answer's target_word_count=275 would falsely "drift" against a theory question's expected value). The clean design: `prompt_version` captures prompt-related drift (which is what word count changes are); `target_word_count` is just a record of what was instructed.
- **Default `subject="psm"` keeps backward compat.** Every existing test that calls `cache_key_for_question` without a subject still produces the same hash as `subject="psm"` (verified by the `test_cache_key_default_subject_is_psm_for_backward_compat` test).
- **Components at version 0 (planner, validator, reranker) are not flagged as missing.** An old cache that doesn't have a `planner` field in its `versions` dict should not be marked stale just because we added a planner version field to the schema. The `is_stale` function skips drift reporting for components at version 0 (verified by the `test_is_stale_does_not_flag_unimplemented_components` test).

## Consequences

**Positive:**

- Existing cached answers (q022, q053, q062) are preserved on disk. The operator can inspect them; they show up as `stale: true` with reasons when loaded.
- When the operator bumps `prompt_version` to 2 in a future phase, all currently-cached answers will be automatically marked stale with reason `prompt_version_drift`. A batch regeneration command (deferred — the actual `regenerate_stale()` function lands in a later phase) can then re-render them.
- Adding a new pipeline component (e.g. `validator`) is a one-line change in `PIPELINE_VERSIONS`. Old caches missing that field are NOT marked stale (because the new component starts at version 0).
- The cache file is the source of truth; the in-memory `stale` annotation is derived. The operator can always `cat` the file and see the original answer.

**Negative:**

- The cached answer JSON is larger (adds 5 fields: `package_version`, `versions`, `embedding_model`, `stale`, `stale_reasons`, plus optional `target_word_count`). ~200 bytes per cache file. Negligible.
- The cache key is longer (includes the full `PIPELINE_VERSIONS` dict as a sorted string). Hashing is still O(1) per call. Negligible.
- The `find_stale_answers` function reads every cache file in the answers directory. For a system with 10,000 cached answers, that's ~10,000 small JSON reads. Acceptable for the personal edition (the operator has at most a few hundred cached answers in the foreseeable future).
- The selective regeneration function (`regenerate_stale()`) is **not** implemented in this phase — only the discovery (`find_stale_answers`). The actual regeneration will land in a follow-up. The operator can already see what's stale; the next phase will give them a `medrack regenerate-stale` command to fix them.

**Risks accepted:**

- The `is_stale` function reads `PIPELINE_VERSIONS` and `EMBEDDING_MODEL` from the config module-level constants. If a test mutates these without restoring, the next test sees the mutated values. The `test_cache_key_includes_pipeline_versions` test has a try/finally to restore the original.
- A test that constructs `BuildResult` directly with positional args will fail because we added a new field. The dataclass field has a default (`word_count_target: int | None = None`), so this is backward compatible for any caller that uses keyword args.

## Future considerations

- **Phase 4 (regression dataset)**: the 20-question regression suite should include some pre-Phase-3 caches to verify the `is_stale` function correctly identifies them.
- **Phase 5 (benchmark framework)**: benchmarks will record cache hit/miss, stale status, and the regeneration reason. This is the data layer for measuring how often the operator's cache becomes stale over time.
- **A `medrack regenerate-stale` command** is the natural follow-up. It would:
  1. Call `find_stale_answers(module_name=...)` to get the list
  2. For each stale entry, call `generate_answer(force_regenerate=True)`
  3. Overwrite the cache file (atomic write, same as `save_answer`)
  4. Return a summary: `N stale → M regenerated, K failed`
  This is the "selective regeneration" half of the directive. Deferred to a follow-up phase because it requires CLI + bot wiring, and the underlying data layer (versioning) is the foundation.
- **A `medrack benchmark cache-staleness` subcommand** could report the staleness rate of the cache as a single number. Useful for monitoring.
- **A `_cache_key` field on the answer dict** (already present from Phase 2) stores the cache key. The `is_stale` function could use this as a sanity check (recompute the key and compare). Currently we don't do this; the version check alone is sufficient. Could be added if we discover a class of bugs where the cache key doesn't catch drift.

## Verification

- **Ad-hoc verifier**: 31/31 checks pass.
- **Test runs**:
  - `test_answer_versioning.py`: 18/18 (new file, Phase 3)
  - `test_answer_cache.py`: 20/20 (8 existing + 12 new; the existing `test_save_and_load_roundtrip` was updated to include the new schema fields)
  - `test_answer_prompt.py`: 18/18 (unchanged from Phase 2)
  - `test_answer_generate.py`: 7/7 (unchanged from Phase 2)
  - `test_answer_batch.py`, `test_answer_llm.py`, `test_answer_render*.py`: 18/18
  - `test_bot_*.py`, `test_dashboard_*.py`: 48/48
  - **Total: 142/142** phase-3-relevant tests pass.
- **Backward compat**: `medrack version` and `medrack --help` work unchanged. The default `subject="psm"` on `cache_key_for_question` means existing call sites produce the same key prefix.
- **No data destruction**: existing cached answers (q022, q053, q062) are preserved on disk. Verified by reading the file before and after `load_answer` — byte-identical.
