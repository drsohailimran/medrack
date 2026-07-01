# ADR 0001 — Layered Module Architecture for MedRack

- Status: Accepted
- Date: 2026-06-29
- Phase: 1 (CLI / state / orchestrate refactor)
- Commit: `3c8c052`

## Problem

The original `medrack/cli.py` had grown to 1,220+ lines containing:

- Argparse wiring (the *only* thing the file should do)
- Preview state machine (load/save/clear/atomic-write of `preview_state.json`)
- Revisions log (load/append of `revisions.json`)
- LLM client factory (`$MEDRACK_LLM_MODE=mock` toggle)
- All six pipeline orchestrators (`cmd_ingest_book`, `cmd_ingest_module`, `cmd_preview`, `cmd_approve`, `cmd_revise`, `cmd_cancel`)

The bot (`medrack/bot/app.py`) and the dashboard (`medrack/dashboard/app.py`) both reached *into* the CLI for orchestration logic and state, importing `medrack.cli as cli` and `from medrack.cli import _load_preview_state`. These were private functions of the CLI, but the bot and dashboard had no other choice — the public surface didn't exist.

This was:
- A tight coupling: the bot and dashboard would break if the CLI internals changed
- A test smell: tests had to patch `medrack.bot.app.cli.cmd_*` (a back-reference)
- A readability cost: 1,220 lines is too long to navigate

## Alternatives considered

1. **Keep the monolith, document the private API.**
   - Cheapest short-term fix. But: still doesn't give the bot/dashboard a public surface; still 1,220 lines; still no test isolation.
2. **Move everything to a single `medrack/core.py`.**
   - The same code, but renamed. Doesn't fix the layering — there's still no public/private distinction.
3. **Three-module split (state, orchestrate, cli).** ← *chosen*
   - `medrack.state` — pure state-machine functions, no argparse, no I/O outside the state files. Public via `__all__`.
   - `medrack.orchestrate` — pipeline orchestrators, take `argparse.Namespace`, return `int`. Public via module attributes (each `cmd_*` is a top-level def).
   - `medrack.cli` — thin argparse shell, imports the orchestrators and state, defines trivial wrappers inline.
4. **Full hexagonal / ports-and-adapters rewrite.**
   - Significant scope increase. The directive v1.0 says: "Do not rewrite working modules without measurable benefit. Extend existing modules rather than replacing them whenever practical." This was rejected as over-engineering for a single-user system.

## Decision

Adopt option 3: the three-module split. `cli.py` becomes a 242-line argparse shell (down from 1,220+). The bot and dashboard now import from `medrack.orchestrate` and `medrack.state` — public APIs, not private CLI internals.

The five trivial cmd_* functions (`cmd_init`, `cmd_status`, `cmd_version`, `cmd_dashboard`, `cmd_bot`) stay inline in `cli.py` because they're 5-15 lines each and extracting them would add a layer of indirection without benefit.

## Reasoning

- **The bot and dashboard already wanted the public surface.** Their old `import medrack.cli as cli; cli.cmd_preview(ns)` calls proved it. We were already paying the cost of the indirection; we just hadn't formalized it.
- **`__all__` makes the public API discoverable.** Anyone reading `medrack/state.py` sees immediately what's exported.
- **The three responsibilities are genuinely separate.** State doesn't need to know about orchestrators; orchestrators don't need to know about argparse. The split is along the natural seam.
- **Test patches get cleaner.** `patch("medrack.bot.app.orchestrate.cmd_preview", ...)` reads better than `patch("medrack.bot.app.cli.cmd_preview", ...)`.
- **Future phases need this split.** Phase 3 (answer versioning) and Phase 5 (benchmark framework) both need to read cached answer JSONs; they should import from `medrack.cache`, not reach into `orchestrate.cmd_preview` to find the file path. Setting up the layering now makes those phases cleaner.

## Consequences

**Positive:**
- Bot and dashboard are no longer coupled to CLI internals. They can be tested in isolation.
- New commands can be added by writing a `cmd_*` function in `orchestrate.py` and adding an argparse subparser in `cli.py`. Two locations, no shared private state.
- The pipeline orchestrators become individually testable without going through argparse.

**Negative:**
- Three files instead of one. Slight increase in cognitive overhead for newcomers ("where does the actual code live?"). Mitigated by clear module docstrings.
- The bot's old `import medrack.cli as cli` is now `import medrack.orchestrate as orchestrate`. Any external script that did the same import is broken. (Mitigated: there are no other callers; the bot and dashboard are the only consumers.)

**Risks accepted:**
- The cli.py and orchestrate.py import cycle is broken by design: cli imports from orchestrate, orchestrate does not import from cli. Verified by the ad-hoc verifier (23/23 checks pass).
- The `get_llm_client()` function lives in `state.py` even though it has nothing to do with preview state. This is a pragmatic call — both `cli.py` and `orchestrate.py` need it, and the alternative was either a fourth tiny module or duplicating the 10 lines. Kept in `state.py` with a clear docstring. Future: if it grows, extract to `medrack/llm_factory.py`.

## Future considerations

- Phase 3 (answer schema versioning) will add `medrack/cache.py` for cache I/O. The orchestrators will move from direct `json.dumps` to `medrack.cache.write_answer(answer, metadata)`.
- Phase 5 (benchmark framework) will add `medrack/benchmarks/`. It will import from `medrack.orchestrate` (not from `medrack.cli`) to keep the public-API discipline.
- If the `medrack.state.get_llm_client()` function gets more complex (e.g. needs to support per-subject model selection), it will move to its own module.

## Verification

- Ad-hoc verifier: 23/23 checks pass (module sizes, public API, import discipline, smoke test, fresh-interpreter import).
- Per-file test runs: all green.
- Full pytest run: 236/237 pass; 1 pre-existing failure (`test_extracts_from_real_psm_module` — environment-level, not introduced by this refactor; see Phase 1 stop report).
- Backward compat: `medrack version`, `medrack --help` work as before; the cached answers and `extracted.json` files are unchanged on disk.
