# ADR 0004 — Permanent Regression Dataset

- Status: Accepted
- Date: 2026-06-29
- Phase: 4 (regression dataset)
- Depends on: ADR 0001 (layered module architecture), ADR 0002 (subject-aware prompts), ADR 0003 (layered answer versioning)

## Problem

We need a way to measure the effect of every architectural change (Phase 2's subject-aware prompts, Phase 3's versioning, and all the future phases from the addendum). Without a fixed benchmark:

- We can't tell whether a change to the prompt template improved answer quality or regressed it.
- We can't tell whether the Phase 3 versioning layer is correctly identifying stale answers.
- We can't compare the cost/quality trade-off of different LLM models or retrieval configs.

The operator's directive v1.0 is explicit:

> "Create a permanent regression dataset. Approximately twenty
> representative MBBS questions. Include: PSM, FMT. Long questions.
> Short questions. Easy. Moderate. Difficult. This dataset becomes the
> permanent benchmark suite. Never modify it. Only extend with
> additional benchmark suites."

## Alternatives considered

1. **Random sampling of questions each time.** Rejected: the same question produces slightly different LLM output on each call, so random sampling is high-variance and unreliable for measuring small quality differences. We need fixed inputs.
2. **Use the existing cached answers (q022, q053, q062).** Rejected: those are pre-Phase-3 caches; they're stale per the versioning layer. Also, only 3 questions is not a representative sample.
3. **Hand-pick 20 questions and freeze them as a versioned JSON file.** ← *chosen*
4. **Generate a synthetic dataset from the LLM.** Rejected: we want to measure the LLM's output, not its self-evaluation. Also, the operator explicitly said "never modify" — synthetic data is a moving target.

## Decision

Adopt option 3:

1. **Dataset file at `medrack/tests/regression_datasets/v1.json`**. Schema:
   - `_doc`: human-readable note about the dataset, including the "NEVER MODIFY" warning
   - `_version`: integer, currently 1
   - `_created`: ISO date
   - `_module_sources`: dict mapping module slug → relative path to `extracted.json` (so the test can validate the source data is still there)
   - `questions`: list of 20 entries, each with: `module`, `qid`, `subject`, `marks`, `section`, `difficulty`, `topic`, `notes`

2. **Hand-picked 20 questions** with this composition:
   - 12 PSM, 8 FMT (the operator's primary use case is PSM, but FMT needs representation since it's the only other currently-ingested subject)
   - 14 10-mark, 6 5-mark (long answers are the harder benchmark and they're the operator's primary use case)
   - 5 easy, 10 moderate, 5 difficult (balanced)
   - Spread across PSM sections A/C/D and FMT section I (the actual sections in the source modules)
   - Topics: epidemiology, nutrition, health indicators, surveillance, immunization, causation, communicable disease, occupational health, health promotion, natural history, FMT identity, FMT pathology, FMT ballistics, FMT toxicology, FMT jurisprudence

3. **Loader in `medrack/tests/regression_datasets/__init__.py`**:
   - `load_regression_dataset(version) -> dict`: returns the parsed JSON
   - `get_regression_questions(version) -> list[dict]`: returns the questions list
   - `list_available_versions() -> list[int]`: discovers available versions by glob
   - `ACTIVE_VERSION`: integer constant, currently 1

4. **Test file at `medrack/tests/test_regression_dataset.py`** with 22 tests covering:
   - Structure (v1 loads, 20 questions, metadata fields, "NEVER MODIFY" in `_doc`)
   - Coverage (PSM+FMT, 5+10 mark, easy+moderate+difficult, ≥8 10-mark, ≥8 per subject)
   - Integrity (no duplicate (module, qid) tuples, all qids exist in source modules, marks match source)
   - Schema (all required fields present, subject is a known Subject enum value, module is on disk)
   - Loader behaviour (missing version raises FileNotFoundError, returns fresh dict)

## Reasoning

- **The directive's "never modify" rule is enforced by the test suite.** The `test_dataset_module_sources_point_to_real_files` and `test_all_qids_exist_in_source_modules` tests would fail if someone deleted a source module or changed a qid. Even if the data were hand-edited, the validation tests would catch it.
- **The (module, qid) tuple is the unique key, not just qid.** This is the lesson from a real bug: PSM and FMT both have `q173` (their qid sequences are independent). A test that uses only `qid` as the key would silently misbehave.
- **The dataset file is small (6.9KB) and human-editable.** Operators can add questions to v2 by copying an entry and editing fields. The schema is documented in the `_doc` field and the test enforces it.
- **Tests live in `medrack/tests/`, not in `medrack/benchmarks/`.** The dataset is a test fixture, validated by the test suite. The benchmark framework (Phase 5) will use the same dataset, but it's owned and validated by the test infrastructure first. This means a broken dataset blocks CI immediately.
- **The `_module_sources` dict provides a strong integrity guarantee.** If someone moves a module's `extracted.json` to a new path, the test fails — the operator can't accidentally orphan a question.
- **The "difficulty" field is operator-assigned** (easy / moderate / difficult) based on the question's complexity, not computed. This is intentional: difficulty is a property of the question's *exam relevance*, not just its word count. A short 5-mark question about disease control vs eradication is "easy"; a long 10-mark question about natural history of disease is "difficult" because it requires reasoning across multiple PSM frameworks.

## Consequences

**Positive:**

- Future phases (5 through 7+) can use this dataset as a fixed-input benchmark to measure architectural changes. Before/after metrics are directly comparable.
- The test suite validates the dataset's integrity — operators can edit the JSON without worrying about breaking the contract.
- The 20-question size is small enough to run on every architectural change (we expect < 5 minutes per full run with the LLM, < 30 seconds with `MEDRACK_LLM_MODE=mock`).
- The mix of subjects, marks, and difficulty gives a balanced sample. If we add Medicine or Surgery in a future phase, the dataset gets a v2 with 20 more questions from those subjects.

**Negative:**

- The dataset is biased toward PSM (12/20) because that's the operator's primary use case. FMT has 8 questions. A future Medicine/Surgery ingestion should add more subjects.
- Some FMT questions (q605, q518) include year/letter codes from the original answer bank (e.g. "127, 156 D10", "105 ang J13, D14, J05(0S)"). These are noisy but the question text itself is clean. Future v2 datasets should use cleaner FMT questions.
- The 5-mark count is low (6/20) because the operator's primary workflow is 10-mark theory. A future v2 with more 5-mark questions is straightforward — just add more entries to the JSON.
- **The dataset is currently unused.** The benchmark framework (Phase 5) is what will actually run it. Until then, the dataset exists as a contract and an integrity check, not as a measurement.

**Risks accepted:**

- The operator may want to add or remove questions later. The directive says "never modify" but adds "only extend with additional benchmark suites" — so a v2.json is allowed. v1 is frozen.
- A future change to the extracted.json (e.g. re-ingesting a module with a different OCR result) could change the qid numbering. The test would catch it. Mitigation: keep the source modules frozen; re-ingest is rare and operator-initiated.
- The `_doc` field is a free-text string. Future operators might not notice the "NEVER MODIFY" rule. Mitigation: the test `test_dataset_metadata_doc_mentions_never_modify` checks for the literal string.

## Future considerations

- **Phase 5 (benchmark framework)** will use this dataset. The framework will:
  1. Load v1.json
  2. For each (module, qid) entry, load the source question from extracted.json
  3. Call `generate_answer` (with the configured LLM client)
  4. Record per-question metrics: prompt tokens, completion tokens, total tokens, latency, retrieval distance, answer quality score (operator-assigned or auto), word count
  5. Aggregate per-subject and per-marks breakdowns
  6. Persist the run as a JSON + Markdown report
  7. Compare against the previous run to detect regressions
- **Adding a v2.json** would be a deliberate operator action: copy v1.json, add 20 more questions, bump the `ACTIVE_VERSION` constant. The v1.json stays frozen.
- **A v2 from Medicine or Surgery** is the natural next step when those subjects are ingested. Same 20-question composition (mix of long/short, easy/moderate/difficult), but with the new subjects.
- **The `_module_sources` field is the only mutable metadata** — operators can re-point it if they move the source files. The questions list is immutable per the directive.

## Verification

- **Ad-hoc verifier**: 17/17 checks pass.
- **Test runs**:
  - `test_regression_dataset.py`: 22/22 (new file, Phase 4)
  - `test_answer_versioning.py`: 18/18 (unchanged)
  - `test_answer_cache.py`: 20/20 (unchanged)
  - `test_answer_prompt.py`: 18/18 (unchanged)
  - `test_answer_generate.py`: 7/7 (unchanged)
  - **Total: 85/85** for the regression + answer modules.
- **Dataset integrity**:
  - 20 questions, all with unique (module, qid) tuples
  - 12 PSM + 8 FMT (covers both subjects)
  - 14 10-mark + 6 5-mark (covers both marks)
  - 5 easy + 10 moderate + 5 difficult (all three difficulty levels)
  - All qids exist in their source modules
  - All required fields present
- **Backward compat**: `medrack version` → `medrack 0.2.0` (unchanged). No new CLI commands.
- **No data changes**: the dataset file is new; no existing files were modified.
