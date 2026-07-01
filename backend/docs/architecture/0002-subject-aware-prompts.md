# ADR 0002 — Subject-Aware Prompt Architecture

- Status: Accepted
- Date: 2026-06-29
- Phase: 2 (subject-aware prompts + word count revision)
- Depends on: ADR 0001 (layered module architecture)

## Problem

The prompt templates in `medrack/answer/prompt.py` were hardcoded to PSM:

- `"You are an MBBS (PSM/Community Medicine) ... writer ..."`
- `'Reference: K. Park\'s "Preventive & Social Medicine" 27th edition.'`
- PSM-specific style guidance: "Mention primary/secondary/tertiary prevention (Park's framework) where relevant."
- PSM-specific data suggestions: "NHM, NVBDCP, RNTCP, Ayushman Bharat, NFHS, SRS, IMR, MMR, U5MR, TFR."

The system already supports 10 subjects (`psm`, `fmt`, `medicine`, `surgery`, `ortho`, `obgyn`, `anesthesia`, `pediatrics`, `ent`, `ophthalmology`) and one of them — FMT — is already indexed as a KB textbook. But the prompt builder ignored the subject and produced PSM-flavoured answers for every question, regardless of which subject's KB was being retrieved.

This is wrong for two reasons:

1. **Quality**: FMT answers that reference "K. Park" and "NHM" are nonsensical to an examiner. An FMT answer should reference Narayan Reddy and the IPC/CrPC/IEA.
2. **Scalability**: Adding a new subject required editing `prompt.py` directly. There was no data-driven way to add a new medical subject.

Additionally, the word count targets (`THEORY_LONG=500`, `THEORY_SHORT=300`) were tightened in the operator's directive v1.0 to a new range (700-850 / 450-500), reflecting a more substantial exam-style answer.

## Alternatives considered

1. **String substitution at call time.** Each caller (the bot, the dashboard, the CLI) builds the prompt by formatting a subject-specific string. Rejected: spreads the prompt-construction logic across three modules; doesn't centralize the subject-context data.
2. **A single template with an `if subject == "psm"` ladder inside `build_theory_prompt`.** Rejected: makes `prompt.py` carry per-subject knowledge; adding a new subject still requires editing this file.
3. **Data-driven `SUBJECT_CONTEXTS` dict + placeholder substitution in a single template.** ← *chosen*
4. **Jinja2 templates per subject.** Rejected: adds a dependency, increases surface area, and the operator-set prompt style is small enough that f-strings are sufficient.

## Decision

Adopt option 3:

1. **Add `SUBJECT_CONTEXTS` dict to `medrack/config.py`** — per-subject metadata. Schema: `display`, `reference_text`, `indian_context`, `key_sources`, `framework`, optional `fallback` flag. PSM and FMT fully populated; a `generic` entry serves as the default for unknown subjects.

2. **Refactor `build_mcq_prompt` and `build_theory_prompt`** to read the subject's context dict at build time and substitute into a single template. The template uses `{display}`, `{reference_text}`, `{indian_context}`, `{key_sources}`, `{framework}` placeholders. Both functions gain a `subject: str = "psm"` parameter (default preserves backward compatibility for existing call sites).

3. **Add a resolver `_get_subject_context(subject)`** that looks up the dict and falls back to the `generic` entry for unknown subjects. A debug-level log is emitted so the operator can see when this happens.

4. **Thread `subject` through `_build_prompt` in `medrack/answer/generate.py`** to the prompt builders. `generate_answer()` already accepted `subject` for retrieval scoping; we just forward it to the prompt builder.

5. **Update word count constants** to the operator-set directive v1.0 values:
   - `THEORY_LONG_TARGET_WORDS = 775` (10-mark, target 700-850)
   - `THEORY_SHORT_TARGET_WORDS = 475` (5-mark, target 450-500)
   - `MCQ_EXPLANATION_TARGET_WORDS = 275` (was 300; tightened to ±10% per directive v1.0)

6. **Add `subject` field to `BuildResult`** so downstream consumers (the answer cache, the renderer) can log and audit which subject context was used.

## Reasoning

- **Adding a new subject becomes a one-line config change** (add a row to `SUBJECT_CONTEXTS`). The directive v1.0 explicitly says "Future subjects must be easy to add without modifying existing prompt logic" — this satisfies that requirement.
- **No code review needed for adding a subject.** Per-subject context is data, not logic. Future subjects (Medicine, Surgery, etc.) are just new dict entries.
- **Backward compat is preserved** by defaulting `subject="psm"` on the prompt builders and falling back to `generic` for unknown subjects. Existing tests and call sites that don't pass a subject still get the PSM context (the prior behavior).
- **The "fallback to generic, not PSM" decision** is the right one: if a new subject is ingested without adding an entry, the operator gets a clear debug log and a sensible generic prompt — not PSM-specific noise that would silently mis-train the LLM.
- **Word count revision goes here, not in a separate phase** because both the prompt template and the cached answer word count are part of the same "what we ask the LLM for" surface. Splitting them across phases would mean two commits that change the same surface area.
- **Cache is NOT invalidated** per the operator's earlier directive ("never permanently invalidate cached answers solely because prompt templates, word counts or schema evolve"). The cached answers still pass the cache key check; they just won't match the new word count target until regenerated. Phase 3 (answer schema versioning) is the right place to add the version check + selective regeneration.

## Consequences

**Positive:**

- FMT answers now use Narayan Reddy as the reference and IPC/CrPC/IEA in the Indian context. (Confirmed by the ad-hoc verifier: PSM prompt has K. Park, FMT prompt does not, FMT prompt has IPC.)
- Adding Medicine, Surgery, or any other subject is one dict entry in `config.py` — no `prompt.py` edit, no test changes.
- The BuildResult.subject field means downstream consumers (the renderer, the dashboard, the answer cache) can report which subject context was used, which is useful for QA and audit.

**Negative:**

- Word count bump from 500→775 for 10-mark answers is a 55% increase in target answer length. This will increase per-answer completion token cost by a similar factor. The OpenCode Go API is a paid subscription, so this is a real cost increase. (Will be measured in Phase 5 once the benchmark framework lands; we can revisit if cost is a problem.)
- The prompt template is slightly more verbose (added lines for `{key_sources}` and `{framework}`). Adds ~50-80 prompt tokens per question. Minor; acceptable.
- The new `SUBJECT_CONTEXTS["generic"]` entry is used as a fallback. If a real subject is missing from the dict, the operator will get generic answers, not PSM answers. This is the safer failure mode (the operator sees a debug log entry and adds a proper entry), but it does mean the failure is silent at the user level. **Future improvement**: emit a warning-level log (not just debug) when a fallback is used, so the operator notices in production logs.

**Risks accepted:**

- Existing cached answers (q022, q053, q062, etc.) were generated with the old prompts (300/500 words, PSM-specific). When the operator regenerates them with `--reanswer`, they'll come back at 475/775 words with the correct subject context. Until then, the cache serves the old answers unchanged. Per the operator's directive, this is the right behavior — we don't delete valid answers.
- The CLI tests (`test_cli_*.py`) call `medrack ingest-book` and `medrack ingest-module` as subprocesses on real PDFs. They take 30-60s each. The Phase 2 changes don't affect them, but they do slow down every CI run. (Not a Phase 2 regression; pre-existing performance issue.)

## Future considerations

- **Phase 3 (answer schema versioning)**: when this lands, the answer cache will start writing `schema_version`, `prompt_version`, and `word_count_target_version` to every cache entry. The Phase 2 word count change is the first place where that versioning layer will actually be useful — old caches (schema 1) will be marked stale; new ones (schema 2) will not. This is exactly the operator's stated requirement.
- **Phase 4 (regression dataset)**: the 20-question regression suite will include ~10 PSM and ~5 FMT questions. The Phase 2 subject-awareness will be exercised by the FMT portion of the suite.
- **Phase 5 (benchmark framework)**: benchmarks will record `subject`, `word_count_target`, and `actual_word_count` for every answer. This will make the word count cost-vs-quality tradeoff visible and measurable.
- **Adding more subjects**: when the operator ingests a new subject's KB textbook, they add a row to `SUBJECT_CONTEXTS` in `medrack/config.py` with the appropriate `display`, `reference_text`, `indian_context`, `key_sources`, and `framework` strings. No other code changes needed.

## Verification

- **Ad-hoc verifier**: 33/33 substantive checks pass (the 34th was a false negative in the verifier's `-k` filter; the underlying tests all pass).
- **Test runs**:
  - `test_answer_prompt.py`: 18/18 (10 existing + 8 new subject-aware)
  - `test_answer_generate.py`: 7/7 (1 test updated to use config-driven word count)
  - `test_answer_cache.py`, `test_answer_llm.py`, `test_answer_batch.py`, `test_answer_render.py`, `test_answer_render_full.py`: 39/39
  - `test_bot_*.py`, `test_dashboard_*.py`: 48/48
  - `test_cli_bot.py`, `test_cli_dashboard.py`: 5/5
  - `test_cli_ingest.py`, `test_cli_module.py`, `test_cli_preview.py`: 13/13
  - Total: **133/133** phase-2-relevant tests pass.
- **Backward compat**: `medrack version` and `medrack --help` work unchanged. The default `subject="psm"` on the prompt builders means existing call sites that don't pass a subject still work.
- **No data changes**: cached answers, `extracted.json`, ChromaDB index — all untouched on disk.
- **Cache invalidation**: NOT performed. Per operator's directive, the cache stays; Phase 3 will add selective regeneration.
