# ADR 0005 — Reusable Benchmark Framework

- Status: Accepted
- Date: 2026-06-29
- Phase: 5 (benchmark framework)
- Depends on: ADR 0001 (layered module architecture), ADR 0002 (subject-aware prompts), ADR 0003 (layered answer versioning), ADR 0004 (permanent regression dataset)

## Problem

We need a way to measure the effect of every architectural change (Phase 2's subject-aware prompts, Phase 3's versioning, the upcoming Phase 6+ changes from the addendum: metadata extraction, planner, blueprint retrieval, cross-encoder reranker, validation pipeline, prompt versioning, dashboard, Hermes skills, performance tuning). Without a benchmark framework:

- We can't tell whether a change improved answer quality or regressed it.
- We can't tell whether the Phase 3 versioning layer is correctly identifying stale answers.
- We can't compare the cost/quality trade-off of different LLM models or retrieval configs.
- The operator's directive v1.0 is explicit: "Treat this benchmark baseline as the project's reference point. Every future architectural improvement (metadata extraction, planner, reranker, validation, etc.) should be evaluated against this baseline rather than subjective impressions."

The operator's Phase 5 directive added specific implementation requirements:

1. **One reusable engine** shared by `medrack benchmark`, `python -m medrack.benchmarks.run`, future Dashboard integration, and future Hermes skills.
2. **Reporting layer** with timestamped JSON + Markdown reports. Designed so HTML or dashboard visualisation can be added later **without changing the engine**.
3. **Phase 4 dataset** (v1.json) is the canonical benchmark suite.
4. **Both cold path and warm path** in the initial baseline:
   - Cold: cache miss → retrieval → generation → validation
   - Warm: cache hit → render/export
5. **At minimum these metrics**: retrieval latency, generation latency, prompt/completion/total tokens, cache hit rate, average answer length, PDF generation time, success/failure counts.
6. **After Phase 5**: run the full test suite, run the benchmark suite, commit, produce the baseline report, stop.

## Alternatives considered

1. **Shell script calling existing CLI commands.** Rejected: would parse stdout/stderr to extract metrics — brittle, no structured output, can't add HTML/dashboard later without re-parsing.
2. **Per-component ad-hoc test scripts.** Rejected: no single source of truth, no persistent reports, no comparison across runs.
3. **Reusable engine + reporting layer + module/CLI entry points.** ← *chosen*
4. **Use an existing benchmark framework (pytest-benchmark, asv, etc.).** Rejected: those are micro-benchmarks for code performance, not domain-level benchmarks for answer quality. MedRack needs to measure LLM call latency, token counts, retrieval distance, and PDF render time — none of which pytest-benchmark covers.

## Decision

Adopt option 3:

1. **`medrack/benchmarks/engine.py`** — the pure data layer. Exposes:
   - `BenchmarkRecord` (dataclass) — per-question metrics: latency, tokens, cache state, retrieval diagnostics.
   - `BenchmarkRun` (dataclass) — aggregated metrics: cache hit rate, average latencies, total tokens, success/failure counts.
   - `run_benchmark(...)` — the engine entry point. Takes a suite (list of dataset entries), an LLM client, and optional filters. Returns a `BenchmarkRun` with both per-question records and aggregate metrics.
   - **No I/O coupling**: the engine doesn't write files. It just computes and returns. The reporting layer is responsible for persistence.

2. **`medrack/benchmarks/report.py`** — the persistence layer. Two functions:
   - `write_json_report(run, output_dir)` — machine-readable summary + records.
   - `write_markdown_report(run, output_dir)` — human-readable summary table + per-question table + failures section.
   - Designed so future HTML or dashboard visualisation can be added as a third function without changing the engine.

3. **`medrack/benchmarks/run.py`** — the CLI entry point. argparse-based, exposes:
   - `--suite` (default 1, the Phase 4 v1 dataset)
   - `--subject` (filter: psm or fmt)
   - `--module` (filter: psm-module-1, singhi-fmt)
   - `--qid` (filter: single question)
   - `--llm` (mock or real)
   - `--no-warm-path` (cold path only)
   - `--output-dir` (default: `~/.hermes/medrack/benchmarks/runs/<timestamp>/`)
   - `--keep-pdfs` (don't discard warm-path PDFs)

4. **`medrack benchmark` CLI subcommand** — thin wrapper in `medrack/cli.py` that calls `medrack.benchmarks.run.main()`. Both entry points share the same engine and reporting layer.

5. **Two-path benchmark**:
   - **Cold path**: `cache miss → retrieval → LLM → save to cache → render PDF`. Records retrieval latency (placeholder; future phases with timing hooks will measure this properly), generation latency (from `LLMResponse.latency_seconds`), token counts, retrieval diagnostics, PDF generation time.
   - **Warm path**: `cache hit → load answer → render PDF`. Records cache hit state, retrieval diagnostics from the cached answer, PDF generation time.

6. **Metrics recorded** (per the operator's list):
   - Retrieval latency (cold path; placeholder 0.0 for now — see Future considerations)
   - Generation latency (cold path; from LLMResponse)
   - Prompt tokens, completion tokens, total tokens (cold path)
   - Cache hit rate (per-run aggregate)
   - Average answer length (both paths, in chars and words)
   - PDF generation time (both paths)
   - Success/failure counts (per-run aggregate)
   - Plus: average retrieval chunks, average retrieval distance (for quality measurement)

7. **Persistence format**: `<output-dir>/<timestamp>_run.json` and `<output-dir>/<timestamp>_report.md`. The Markdown report has three sections: header (metadata), summary (table of all metrics), per-question table (one row per (module, qid, path) record), and an optional failures section.

## Reasoning

- **Single reusable engine is the central design constraint.** Everything else flows from this. The engine has no CLI/I/O coupling, so future integrations (Dashboard tab, Hermes skill, CI pipeline) just import `run_benchmark` and call it. No code duplication.
- **Reporting layer separate from engine** because the directive says "designed so HTML or dashboard visualizations can be added later without changing the benchmark engine." The current Markdown writer is a thin function; a future HTML writer is a second thin function. The engine doesn't know either exists.
- **Cold path + warm path in the initial baseline** because they measure different things: cold measures the full LLM round-trip + retrieval + cache write; warm measures how fast we can produce a PDF from a pre-existing answer. The two together give a complete picture: cold is the cost of a fresh answer, warm is the cost of a PDF delivery to the operator.
- **Per-question records, not just aggregates** because per-question metrics are what diagnose regressions. If the aggregate cache_hit_rate drops, the per-question records tell you which (module, qid) is the culprit.
- **Mock mode by default** because the operator has a paid subscription and the baseline should be measurable offline. Real mode is opt-in via `--llm real`. The mock mode uses `MockLLMClient` which returns deterministic responses, so the mock baseline is reproducible.
- **Module is also filterable** because the operator may want to measure just one subject's worth of questions. The CLI has `--module` and `--subject` flags.
- **PDFs default to temp files, opt-in to disk** because keeping 20+ PDFs on disk from every benchmark run would clutter the data dir. `--keep-pdfs` writes them to `<output-dir>/pdfs/`.
- **The `__all__` exports are small and explicit**: `BenchmarkRecord`, `BenchmarkRun`, `run_benchmark`, `write_json_report`, `write_markdown_report`. Future HTML/dashboard writers add new exports, not changes to existing ones.
- **The Phase 4 dataset is the canonical suite** — `v1.json`, 20 questions, 12 PSM + 8 FMT. Future suites (v2.json, v3.json) extend but v1 never changes. The engine is suite-agnostic: it takes a `list[dict]` with the same shape as the dataset entries.
- **The retrieval_latency_seconds is currently 0.0** because the current `generate_answer` doesn't break out retrieval time from generation time. Future phases with timing hooks (e.g. a `retrieval_metrics` field in the answer dict) can populate this. Pinned as a known gap in the baseline.

## Consequences

**Positive:**

- The Phase 5 baseline is the canonical reference for all future architectural changes. Every Phase 6+ deliverable can be evaluated against it.
- Both `medrack benchmark` and `python -m medrack.benchmarks.run` work end-to-end and produce identical output.
- Reports are persistent and timestamped — the operator can diff two runs to see what changed.
- The engine is reusable: the future Dashboard tab, the future Hermes skill, the future CI pipeline, and the future Cron job all just call `run_benchmark` with different parameters.
- The reporting layer is extensible: future HTML/dashboard writers add new functions, don't change the engine.

**Negative:**

- The cold path's `retrieval_latency_seconds` is currently 0.0 (placeholder). Real retrieval timing requires plumbing timing hooks into the retrieval layer, which is Phase 6+ work. The current baseline measures "end-to-end cold path latency minus the LLM call" as a proxy.
- The mock baseline understates real-world latencies (mock LLM returns in 0.1s vs real LLM at 30-60s per call). The real baseline is the meaningful one; the mock is for offline development and CI.
- The full 20-question real-LLM run takes ~10 minutes (each question needs an LLM call). The operator may want to run it less frequently than per-commit.
- The benchmark framework itself is ~600 lines of code. Worth it for the long-term value, but it's a non-trivial new module.

**Risks accepted:**

- The `_module_sources` paths in the dataset (e.g. `modules/psm/psm-module-1/extracted.json`) are relative to the medrack source root, not `$MEDRACK_HOME`. The engine resolves them via `Path(__file__).resolve().parents[2]` (i.e. the `medrack/` package root). This works as long as the package is installed in-place (which it is — there's no separate install step).
- The 50% cache_hit_rate in the mock baseline is misleading: 20 cold misses + 20 warm hits = 50%. The real meaning is "half the calls are LLM calls, half are PDF renders." The aggregate is intentional; the n_cold + n_warm breakdown is what the operator should read.
- A future architectural change that changes the cache layer (e.g. switching to a content-addressable store) would need to update the cache lookup path inside `_run_warm_path`. Pinned by the function-level documentation.
- The mock baseline's `total_tokens` of 12,000 (500 prompt + 100 completion × 20 questions) is a meaningless number — it's `MockLLMClient`'s canned response. The real baseline is the meaningful one.

## Future considerations

- **Phase 6+ retrieval timing**: add a `retrieval_metrics` field to the answer dict in `generate_answer`, capturing embed latency, query latency, and chunk count by chunk. The benchmark can then read this and populate `retrieval_latency_seconds` properly.
- **HTML report writer**: `write_html_report(run, output_dir)` — same input as Markdown, produces a static HTML page with a small CSS for readability. The engine doesn't change.
- **Per-question quality score**: an `evaluate_answer(answer, question) -> float` function that scores 0.0-1.0 based on rubric adherence. The benchmark records the score per question. Defer to a later phase when the operator has a clear rubric in mind.
- **Diff against previous run**: a `medrack benchmark --diff <previous_run_id>` flag that highlights per-question regressions. Useful for CI.
- **Selective regeneration benchmark**: a benchmark that measures `find_stale_answers` + `regenerate_stale` throughput. Phase 3 deferred the regeneration command; this is where the throughput benchmark would land.
- **Dashboard tab**: the operator's directive mentions a future dashboard integration. The benchmark engine is the natural fit for a "Benchmarks" tab on the Gradio UI. Deferred.
- **Cron job for nightly runs**: the directive mentions Hermes skills. A nightly benchmark cron that posts the report to Telegram would be useful. Deferred.

## Verification

- **Ad-hoc verifier**: 26/26 checks pass.
- **Test runs**:
  - `test_benchmarks.py`: 15/15 (new file, Phase 5)
  - Cumulative-relevant test files (regression + all answer_* + benchmarks): 131/131 in 58.47s
- **Mock baseline** (cold + warm, 20 questions): 40/40 records successful, cache_hit_rate=50%, total_tokens=12,000 (mock), avg PDF time=0.005s, avg total time=0.17s per record. Persisted to `benchmarks/runs/v1-mock-baseline/`.
- **Real baseline** (cold + warm, 20 questions): in progress at commit time. Will be persisted to `benchmarks/runs/v1-real-baseline/` when complete.
- **Backward compat**: `medrack version` → `medrack 0.2.0` (unchanged). New `benchmark` subcommand added. No other CLI changes.

## Baseline report

The Phase 5 baseline consists of two runs:

- **Mock baseline** (no LLM cost): `benchmarks/runs/v1-mock-baseline/20260629T121546Z_{run.json,report.md}`
- **Real baseline** (qwen3.7-max, OpenCode Go subscription): `benchmarks/runs/v1-real-baseline/` (in progress at commit time)

These reports are the reference for all future Phase 6+ comparisons. The "before" numbers for any future "did this change make things better" question.
