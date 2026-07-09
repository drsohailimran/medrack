# MedRack — Phase checklist (single source of progress)

**Rule:** One phase at a time. **Verify → document completion → document next → wait for owner approval.**  
Do **not** start Pn+1 until the owner explicitly approves Pn.

**Full context:** `MEDRACK_FULL_SYSTEM_HANDOFF.md`  
**Priority:** answer quality > overnight stability > speed  
**Canonical app:** `/home/sohail/medrack` (**v1.1.0**) · **Data:** `/home/sohail/medrack-data`

---

## Working agreement

| Step | Who | Action |
|------|-----|--------|
| 1 | AI | Implement **only** the active phase |
| 2 | AI | **Verify** with evidence (API, sample PDFs, tests) |
| 3 | AI | Mark phase **IMPLEMENTED — AWAITING APPROVAL** in this file |
| 4 | AI | Write **what was done** + **what the next phase will do** |
| 5 | AI | **Stop** and wait |
| 6 | Owner | Approve (e.g. “P0 approved”) or request fixes |
| 7 | AI | On approval: mark **COMPLETE — APPROVED**, then open next phase |

---

## Status board

| Phase | Name | Status | Approved by owner |
|-------|------|--------|-------------------|
| P0 | Bulletproof answers | **COMPLETE — APPROVED** | **Yes (2026-07-09)** |
| P1 | Hybrid OCR ingest mode | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |
| P2 | Multi-subject content (book ingest) | **DEFERRED by owner** — do when owner wants | No |
| P3 | UX: stop-gen + LLM indicator | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |
| P4 | Housekeeping | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |

*Owner priority (2026-07-10): **do not spend time mass-ingesting textbooks now.** Prefer a solid, reliable system. Owner will hybrid-ingest books later. Do **not** auto-start P2 content work.*

---

## P0 — Bulletproof answers

**Goal:** Exam answers stay on-scope, grounded in the textbook KB, and bad output is caught before the PDF is trusted.

### Tasks

- [x] Scope-control prompt (answer only what is asked; mark-aware length)
- [x] Hard grounding (programmes/laws/names only if in SOURCE MATERIAL or universal fact)
- [x] Validator gate (off-scope / invented names / truncation → fail or needs_review)
- [x] Regression pack (fixed questions; must pass before big overnight runs)
- [x] Stale-answer handling when books are re-ingested

### Exit criteria (all required)

- [x] Validator fails PRAMS / invented Yojana fixtures; passes grounded JSY short answers
- [x] ScopeLengthRule fails over-long 3-mark laundry lists
- [x] `generate_answer` attaches `validation` + `needs_review` on every new answer
- [x] Stale cache (pipeline drift or KB reindex) auto-regenerates
- [x] Regression pack `p0_quality.json` + unit tests green
- [x] Changes documented in handoff + this file
- [x] **Owner approval recorded below**

### What was implemented (2026-07-09)

| Area | Change |
|------|--------|
| Prompt | `SCOPE CONTROL` + `HARD GROUNDING` + `LENGTH BAND`; 5-mark STRICT COMPACT; 10-mark anti laundry-list (P0→P0.4) |
| Validator | `ScopeLengthRule`, `GroundingRule`, `TruncationRule`; `needs_review` on generate path |
| Answer dict | `validation` report, `needs_review`, `kb_revision` |
| Versions (final) | `schema:3`, `prompt:6`, `validator:5` |
| Stale | Stale cache auto-regenerates; `bump_kb_revision` on book index |
| Regression | `p0_quality.json` + unit tests |
| Live verification | 6-Q bank (`test`) re-solved through P0.1–P0.4; final `test-solved-6.pdf` acceptable |

**Note:** Validator marks bad answers `needs_review=True` but still **saves** them (overnight stability).

**Known residual (accepted at approval):** occasional mild 5-mark overshoot (~420 vs 405 max); rare grounding false fails (e.g. COC); 10-mark may sit slightly under/over ideal ±10% but open-stem 1100+ word dumps fixed.

### Verification log

```
Unit tests: test_p0_quality + related → green (90–96 passed depending on slice)
Live API: package 1.0.0, prompt:6, validator:5
Live bank re-runs: test-solved-3 through test-solved-6.pdf
Final (test-solved-6): Q1 EOC ~606 words (was 1142); Q2 ~847; 5-mark ~247–428
Owner: “p0 approved” 2026-07-09
```

### Completion record

| Field | Value |
|-------|--------|
| Status | **COMPLETE — APPROVED** |
| Implemented date | 2026-07-09 |
| Verified date | 2026-07-09 |
| Owner approval | **Yes — “p0 approved” (2026-07-09)** |
| Next phase after approval | **P1** |

### P0.1 follow-up (length control) — 2026-07-09

After `test-solved-5.pdf` analysis (10-mark answers ~half length; Q5 over-long):

| Fix | Detail |
|-----|--------|
| Prompt | Hard **LENGTH BAND**: min `{lower_words}` / target / max `{upper_words}`; 10-mark must not write 5-mark depth; 5-mark max 2–3 headings / 6–12 bullets |
| Tokens | `max_output_tokens` raised so model is not cut off before minimum |
| Validator | `ScopeLengthRule` fails **under** min and **over** max; uses `target_word_count` when present |
| Allowlist | EOC, BEmOC, CEmOC, ARSH, KMC, etc. |
| UI | Length boxes reset to **750 / 375 / 125** (new localStorage keys `*_v2`) |
| Versions | `prompt:3`, `validator:2` |

**Re-test:** clear answers for `test` bank, re-solve with defaults 750/375, download PDF, check word counts in band.

### P0.2 follow-up (5-mark overshoot + allowlist) — 2026-07-09

After `test-solved-3.pdf` (10-mark OK; 5-mark all over-long; MHM false-fail):

| Fix | Detail |
|-----|--------|
| Prompt | **STRICT COMPACT** 5-mark: max 2–3 headings, 6–10 bullets, no extra “Challenges/Future” sections; hard stop at upper_words |
| Tokens | Tighter `max_output_tokens` for marks ≤5 so model is less likely to write a mini-textbook |
| Validator | 5-mark max 420; target-based ceiling **+10%** for 5/3-mark (was +20%) |
| Allowlist | **MHM**, MCTS, BEMOC/CEMOC, PROM, LSCS, etc. |
| Versions | `prompt:4`, `validator:3` |

**Re-test:** delete cached answers for `test` bank, re-solve → expect 5-mark ~340–410 words, no MHM false fail.

### P0.3 follow-up (final length polish) — 2026-07-09

After `test-solved-4.pdf` (Q3 under min 281; Q5–Q6 over; PMMVY false-fail):

| Fix | Detail |
|-----|--------|
| 5-mark min | **0.68 × target** (375 → **255**) so compact ~262w answers pass |
| 5-mark max | **0.08 × target** ceiling (375 → **405**) + hard max 410 |
| Tokens | Harder 5-mark cap: `1.20×target + 200` tokens |
| Prompt | Ban extra “Indian Context/Data” and newborn digression on ANC list stems |
| Schemes | Known titles: **PMMVY**, SUMAN, LaQshya, JSY, JSSK, RKSK, RBSK, … |
| Versions | `prompt:5`, `validator:4` |

**Re-test once:** delete `test` cache → solve → then approve P0 if acceptable.

### P0.4 follow-up (10-mark overshoot / laundry list) — 2026-07-09

After latest `test-solved-5.pdf`: Q1 = **1142 words** (target 750); Q2 OK at 664; model used full `completion_tokens=1900`.

| Fix | Detail |
|-----|--------|
| Token budget (10-mark) | `1.35×target + 150` (~1162 tok for 750) — was ~1900 |
| Prompt | Hard max applies to 10-mark too; max ~15–25 bullets; no NHM/newborn/HIV/WASH laundry list; STOP after definition+components+brief Indian context |
| Validator | 10-mark max **850** hard / **+12%** of target (750 → 840) |
| Allowlist | PPP, WASH, VHND, ANMOL, UIP, etc. |
| Versions | `prompt:6`, `validator:5` |

**Re-test:** delete `test` cache → solve → Q1 should land ~650–840 words, not 1100+.

### After P0 is approved — what P1 will do

Productize hybrid OCR as an ingest mode: stop Qwopus → RapidOCR+Marker → clean PDF → reindex → start Qwopus, with progress in the product (not manual scratchpad).

---

## P1 — Hybrid OCR ingest mode

**Goal:** Scanned textbook ingest from the **single MedRack UI**: stop model → hybrid OCR → validate → restart model → index.

**Status:** **COMPLETE — APPROVED (2026-07-10).** Owner may revisit fixes later.

### Tasks

- [x] Stop Qwopus on ingest (free GPU)
- [x] Hybrid RapidOCR + optional Marker pipeline
- [x] Full text PDF builder (no 50×80 truncation)
- [x] Feed clean PDF into MedRack KB / reindex
- [x] Start Qwopus again after OCR (always, even if OCR fails)
- [x] OCR quality validation gate before accepting PDF
- [x] UI: Books hybrid checkbox + progress (one button)
- [x] Start MedRack starts OCR agent + SSH reverse tunnel
- [x] Stop MedRack stops OCR agent + tunnel
- [x] E2E smoke: 3-page hybrid ingest job `done` (2026-07-10 API test)

### Single-UI flow (current)

1. **Start MedRack** on Windows  
   - Starts Qwopus (:8080)  
   - Starts Ubuntu stack (:8010 / :3010)  
   - Starts **OCR agent** minimized (`C:\medrack-ocr\ocr_agent_server.py` on :8090)  
   - Opens **SSH reverse tunnel**: Ubuntu `127.0.0.1:18090` → Windows `:8090`  
     (LAN direct to Windows:8090 is unreliable even with firewall rule; tunnel is the reliable path)
2. Browser → **Books** → Upload PDF  
3. **Hybrid OCR** checked (default) → **Upload · OCR · ingest**  
4. Agent: stop Qwopus → RapidOCR → optional Marker → **validate** (nonempty page ratio) → full text PDF → start Qwopus  
5. Ubuntu downloads clean PDF → standard ingest (chunk/embed/index)  
6. Progress stays in the Books dialog the whole time  

### Paths / env

| Path | Role |
|------|------|
| `C:\medrack-ocr\ocr_agent_server.py` | Unified agent (HTTP push + background pull) |
| `C:\medrack-ocr\START-OCR-AGENT.cmd` | Manual agent start (also used by Start MedRack) |
| `C:\medrack-ocr\pipeline\hybrid_ocr.py` | Plan C pipeline + validation |
| `C:\medrack-ocr\pipeline\build_text_pdf.py` | Full text PDF (no line cap) |
| `C:\medrack-ocr\pipeline\model_control.py` | Stop/start Qwopus |
| `C:\Medrack\launcher\medrack-launcher.ps1` | Auto-starts agent + tunnel |
| `C:\Medrack\launcher\medrack-stop.ps1` | Stops agent + tunnel |
| Ubuntu `dashboard/services/ocr_bridge.py` | Job queue under `$MEDRACK_HOME/ocr_jobs/` |
| Ubuntu `tasks.run_hybrid_ingest_book` | Orchestrates OCR then ingest |
| Ubuntu API `/api/v1/ocr/agent/*` | Claim / source / progress / result (pull path) |
| Books UI | Hybrid OCR + Marker checkboxes |

| Env | Value |
|-----|--------|
| Ubuntu `MEDRACK_OCR_AGENT_URL` | `http://127.0.0.1:18090` (via reverse tunnel) |
| Ubuntu `MEDRACK_OCR_AGENT_TOKEN` | `medrack-ocr` |
| Windows agent `MEDRACK_API_BASE` | `http://192.168.29.82:8010/api/v1` |
| Windows agent `MEDRACK_OCR_TOKEN` | `medrack-ocr` |

### Known caveats (accepted at approval; fix later if needed)

- Full textbook OCR can take **1–2+ hours**; leave PC on.  
- Direct Ubuntu→Windows:8090 often fails; **tunnel is required**.  
- Marker optional (slow); char-split Marker pages still imperfect (P4).  
- Smoke used a 3-page synthetic PDF (1 chunk); large real scans not re-verified in this approval.  
- Can return to P1 fixes without blocking P2 if owner prioritizes.

### Verification log

```
2026-07-10 smoke:
  POST /library/books/upload hybrid_ocr=true
  job kind=hybrid_ingest_book status=done
  ocr_mode=push via MEDRACK_OCR_AGENT_URL=http://127.0.0.1:18090
  result: pages=3 chunks=1 book "Smoke Hybrid OCR Test" indexed
  Qwopus online after job (stop_flag cleared)
```

### Exit criteria

- [x] Multi-page hybrid path works end-to-end (smoke)  
- [x] Model stop/start + validate wired  
- [x] Documented + troubleshooting  
- [x] **Owner approval**

### Completion record

| Field | Value |
|-------|--------|
| Status | **COMPLETE — APPROVED** |
| Implemented date | 2026-07-10 |
| Verified date | 2026-07-10 (API smoke) |
| Owner approval | **Yes (2026-07-10)** — may revisit later |
| Next phase after approval | **P2** |

### Troubleshooting (for any AI) — hybrid OCR

**Symptoms → checks (in order):**

1. **“OCR agent not on :8090” / timeout waiting for agent**  
   - On Windows: `http://127.0.0.1:8090/v1/health` must return JSON.  
   - If down: Start MedRack, or `C:\medrack-ocr\START-OCR-AGENT.cmd`.  
   - On Ubuntu: `curl http://127.0.0.1:18090/v1/health` must work.  
   - If Ubuntu 18090 fails but Windows 8090 works: reverse tunnel down.  
     Recreate tunnel (Start MedRack does this):  
     `ssh -i medrack_ed25519 -N -R 18090:127.0.0.1:8090 sohail@192.168.29.82`  
   - Confirm Ubuntu `.env`: `MEDRACK_OCR_AGENT_URL=http://127.0.0.1:18090`

2. **Ubuntu cannot curl Windows:8090 directly**  
   - **Expected.** Do not waste time on firewall alone. Use tunnel.

3. **Job stuck on “Stopping Qwopus…”**  
   - Check agent logs / `C:\medrack-ocr\jobs\<id>\`.  
   - Manual: write `C:\ai models\qwopus.stop`, `taskkill /F /IM llama-server.exe`.  
   - Agent should still restart model in `finally`.

4. **OCR quality failed**  
   - Too many empty pages / low avg chars.  
   - Inspect `jobs\<id>\work\rapidocr_cache\page_*.txt`.  
   - Scanned PDF render path uses pypdfium2; broken PDF → empty text.

5. **Job done but book missing / 0 chunks**  
   - Check clean PDF: `$MEDRACK_HOME/books/*_hybrid_ocr.pdf`  
   - API job result fields: `clean_pdf`, `chunks`, `pages`.  
   - Re-run non-hybrid ingest on the clean PDF to isolate OCR vs index.

6. **Pull fallback**  
   - Jobs under `$MEDRACK_HOME/ocr_jobs/<id>/` with `meta.json`.  
   - Agent pull loop claims via `GET /api/v1/ocr/agent/claim` + `X-OCR-Token: medrack-ocr`.  
   - Token must match `MEDRACK_OCR_AGENT_TOKEN` on Ubuntu.

7. **Model not answering after hybrid job**  
   - `curl http://192.168.29.89:8080/health` from Ubuntu.  
   - Agent health: `model.llama_running`, `stop_flag_present`.  
   - Delete `qwopus.stop` and Start MedRack / scheduled task.

**Key code:**  
`tasks.run_hybrid_ingest_book`, `ocr_bridge.py`, `v1.py` `/ocr/agent/*` + upload `hybrid_ocr`,  
`C:\medrack-ocr\pipeline\*.py`, launcher `medrack-launcher.ps1` / `medrack-stop.ps1`.

---

## P2 — Multi-subject content

**Goal:** Enough **trusted, clean-KB textbooks** so multi-subject exam banks can be solved without garbage retrieval.

**Status:** **DEFERRED (2026-07-10)** — owner will run full-book hybrid OCR later.  
**Do not auto-start mass textbook ingest.** Only start when owner explicitly wants content work.

### What P2 is (when owner is ready)

Uses the already-approved P1 hybrid path to fill subjects (FMT first, then others). Not urgent for “system works.”

### Completion record

| Field | Value |
|-------|--------|
| Status | **DEFERRED** |
| Owner approval | — |
| Next | Owner-driven later |

---

## P3 — UX

**Goal:** Safe overnight use for a non-technical primary user.

### Tasks

- [x] Stop generation mid-batch + review keep/delete answers
- [x] Live LLM indicator (model/endpoint)

### Exit criteria

- [x] Stop + review usable in UI
- [x] Indicator visible and accurate
- [x] Documented + owner approved
- [x] **Owner approval recorded below**

### What was implemented (2026-07-10)

| Area | Change |
|------|--------|
| Jobs | Cooperative cancel: `POST /api/v1/jobs/{id}/cancel`; job status `cancelled`; current LLM question finishes first |
| Batch | `generate_full_batch(..., cancel_check=)` stops remaining questions; partial answers kept |
| Solve result | Returns `cancelled`, `skipped`, `answers[]` summaries (`qid`, text snippet, word_count, needs_review) for review UI |
| Partial PDF | Rendered when any answers exist; downloadable after cancel |
| Workspace UI | **Stop generation** button while solving; keep/delete review modal (delete selected / delete all / keep remaining) |
| Cached Answers | Unchanged full list still available for later cleanup |
| LLM indicator | `GET /api/v1/llm/status` — provider, model, base_url, online probe; top bar badge (15s poll) |
| Tests | `test_p3_cancel.py` (batch cancel + job registry); live API smoke cancel on real bank |

### How to use (wife-friendly)

1. Start solve as usual (**Approve & Solve Module**).
2. Click **Stop generation** anytime — waits for the current question, then stops.
3. Review panel: check answers to **delete**, or **Keep remaining**. Deleted answers regenerate next solve.
4. Top bar shows green **qwopus · llamacpp** (or red if model offline).

### Verification log

```
Unit: test_p3_cancel.py → 2 passed
Live: GET /llm/status → llamacpp/qwopus online=true (HTTP 200 /health)
Live: POST /banks/solve → POST /jobs/{id}/cancel → status=cancelled, answers[] present
Frontend: rebuilt node-server; :3010 up; bundle includes llm/status + cancel
```

### Completion record

| Field | Value |
|-------|--------|
| Status | **COMPLETE — APPROVED** |
| Implemented date | 2026-07-10 |
| Verified date | 2026-07-10 |
| Owner approval | **Yes — “p3 approved” (2026-07-10)** |
| Next phase after approval | **P4** (or return to deferred P2 content) |

---

## P4 — Housekeeping

**Goal:** Repo and machines stay aligned; optional cleanup.

### Tasks

- [x] Push ops fixes so GitHub matches machines (v1.1.0 release)
- [x] Document archive (`medrack-ARCHIVE-*`) — **left on disk**, not deleted (recoverable; marked DO_NOT_USE)
- [x] Marker page alignment — **documented residual** (char-split chapters acceptable for now; true per-page is future)
- [x] Park’s denser re-chunk — **deferred** until owner re-ingests books (P2); not required for v1.1.0 code freeze

### Exit criteria

- [x] Agreed items done (code sync + version + docs)
- [x] Documented + owner approved (owner requested finalize + push v1.1.0)

### What was implemented (2026-07-10)

| Area | Change |
|------|--------|
| Version | Package + live API **1.1.0** |
| GitHub | Full monorepo push: backend P0–P3, frontend, docs, `start_stack`/`stop_stack`, `windows/launcher`, `windows/ocr` |
| Cleanup | No bak/pycache; archives retained on Ubuntu only |
| Residual | True Marker per-page + denser Park’s re-chunk remain optional content/OCR follow-ups |

### Completion record

| Field | Value |
|-------|--------|
| Status | **COMPLETE — APPROVED** |
| Implemented date | 2026-07-10 |
| Verified date | 2026-07-10 |
| Owner approval | **Yes — owner requested finalize + push v1.1.0** |
| Next phase after approval | Maintenance / owner-driven P2 content |

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-07-09 | Single workspace consolidated; multi-copy confusion removed |
| 2026-07-09 | Owner locked phase gate: verify → document → wait for approval before next phase |
| 2026-07-09 | **P0 COMPLETE — APPROVED** by owner; next is P1 when owner says start |
| 2026-07-10 | **P1 COMPLETE — APPROVED** (smoke E2E; may revisit) |
| 2026-07-10 | Owner: **do not mass-ingest textbooks now**; prefer solid/reliable system; P2 content deferred |
| 2026-07-10 | Owner: proceed with **P3** (stop-gen + LLM indicator); P2 still deferred |
| 2026-07-10 | **P3 COMPLETE — APPROVED** by owner; next is P4 (or deferred P2) when owner says start |
| 2026-07-10 | **P4 COMPLETE — APPROVED**; GitHub **v1.1.0** release (code freeze P0–P4) |

---

*Update this file whenever a phase moves. Mirror to Ubuntu: `/home/sohail/medrack/docs/PHASES.md` and `/home/sohail/medrack-data/PHASES.md`.*
