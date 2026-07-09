# MedRack — Complete System Handoff Document

**Purpose:** Single source of truth for any AI or human continuing this project.  
**Last updated:** 2026-07-09 (post single-workspace cleanup)  
**Owner:** Sohail Imran (wife is primary end-user for exam prep)  
**Priority order:** **answer quality > overnight stability > speed**

If you are an AI picking this up: read this document fully before changing anything. Do not invent alternate install paths. There is **one** app tree and **one** data tree on Ubuntu.  
**Ignore** anything under `medrack-ARCHIVE-*`, `C:\Medrack\archive\`, or `~/.hermes/medrack` (stub only).

---

## 0. What MedRack is (one paragraph)

MedRack is a **local-first RAG system** that turns MBBS textbooks + exam question banks into **exam-style answer PDFs** (point form, tables, optional flowcharts). It is built for **NEET PG / university theory + MCQ** prep. Primary user: the owner’s wife (non-technical). Workflow: ingest textbook → ingest question bank → preview one answer → solve bank → download PDF.

It is **not** a cloud product. The LLM can be local (llama.cpp / Qwopus on a Windows GPU PC) or other providers (Gemini, Ollama, OpenCode) via config.

---

## 1. Canonical layout (AFTER 2026-07-09 consolidation)

### 1.1 Rule

| Role | **Only** path | Notes |
|------|----------------|-------|
| Ubuntu **application code** | `/home/sohail/medrack` | Was `medrack-app`; version **1.0.0** |
| Ubuntu **data** (KB, answers, modules) | `/home/sohail/medrack-data` | Live data migrated from `~/.hermes/medrack` |
| Ubuntu start | `bash /home/sohail/medrack/start_stack.sh` | |
| Ubuntu stop | `bash /home/sohail/medrack/stop_stack.sh` | |
| Windows workspace | `C:\Medrack` | Launcher + docs + archive |
| Windows OCR tools | `C:\medrack-ocr` | venv + merge script (not a second app) |
| Windows LLM | `C:\ai models\` + llama-cpp-turboquant | |

### 1.2 What was removed / archived (do not revive as “main”)

**Ubuntu** → `/home/sohail/medrack-ARCHIVE-20260709/`:

| Archived path (old) | What it was |
|---------------------|-------------|
| `medrack-app-parallel` | Old parallel code (~0.4.0) |
| `medrack-samples` | Early sample PDFs/chunks experiments |
| `medrack-app.tar.gz` | Deploy tarball snapshot |
| `hermes-medrack-old` | Former live tree under `~/.hermes/medrack` (code + data before migrate) |

**Stub left so AIs do not reuse Hermes:**

- `/home/sohail/.hermes/medrack/MOVED_README.md` → points to canonical paths

**Windows** → `C:\Medrack\archive\`:

| Item | What it was |
|------|-------------|
| `medrack-backend-old-20260630` | Old git checkout of backend-only tree |
| `medrack.rar` | RAR backup |
| `claude-session-transcript.txt` | Pasted Claude Code chat transcript |

**Not MedRack (leave alone):** `C:\claude code\pdf-qa-system` is a separate earlier Streamlit PDF-QA experiment.

### 1.3 Pointer files (duplicated on purpose so any scan finds the map)

| File | Purpose |
|------|---------|
| `/home/sohail/MEDRACK_CANONICAL.md` | One-screen Ubuntu map (home root) |
| `/home/sohail/medrack/MEDRACK_CANONICAL.md` | Same, app root |
| `/home/sohail/medrack-data/MEDRACK_CANONICAL.md` | Same, data root |
| `C:\Medrack\CANONICAL.md` | One-screen Windows map |
| `C:\Medrack\README.md` | Windows entry README |
| **This document (3 copies):** | |
| `C:\Medrack\docs\MEDRACK_FULL_SYSTEM_HANDOFF.md` | Windows |
| `/home/sohail/medrack/docs/MEDRACK_FULL_SYSTEM_HANDOFF.md` | Ubuntu app |
| `/home/sohail/medrack-data/MEDRACK_FULL_SYSTEM_HANDOFF.md` | Ubuntu data |
| `/home/sohail/medrack-ARCHIVE-20260709/DO_NOT_USE_README.md` | Archive ban banner |
| `C:\Medrack\archive\DO_NOT_USE_README.md` | Windows archive ban banner |

### 1.4 Cleanup completed 2026-07-09 (second pass)

Live Ubuntu home now shows only: `medrack/`, `medrack-data/`, `medrack-ARCHIVE-20260709/`, `MEDRACK_CANONICAL.md`.

Moved out of the live tree into the archive:

- `medrack-data/_premerge_backup` (~479 MB old snapshot)
- empty `medrack-data/medrack/`
- accidental `/home/sohail/C:` path
- home-root `FMTSinghi-fixed.pdf` → `medrack-data/inbox/`
- app-root `diag.py` / `diag2.py` / `diag3.py`

Fixed stale `medrack-data/.env` that still pointed at `~/.hermes/medrack` (canonical env is `/home/sohail/medrack/.env` only).

**Verified live:** `package_version` **1.0.0** on `:8010`, frontend **200** on `:3010`.

---

## 2. Deployment topology (two machines)

```
┌─────────────────────────────────────┐         LAN          ┌──────────────────────────────────────┐
│  Windows PC                         │◄───────────────────►│  Ubuntu Linux                        │
│  Hostname: (user PC)                │   192.168.29.89      │  Host: hermes / 192.168.29.82        │
│  User: Sohail Imran (path has SPACE)│   Windows IP used    │  User: sohail                        │
│                                     │   by Linux for LLM   │                                      │
│  • Qwopus llama-server :8080        │                      │  • MedRack API :8010                 │
│  • One-click launcher               │                      │  • Frontend UI :3010                 │
│  • Hybrid OCR (GPU/CPU) when needed │                      │  • Gradio dashboard :7860 (optional) │
│  • Browser opens UI on .82:3010     │                      │  • Data: Chroma, answers, modules    │
└─────────────────────────────────────┘                      └──────────────────────────────────────┘
```

**Important IP note:**  
- Ubuntu reaches Windows LLM at `http://192.168.29.89:8080` (from `.env`).  
- Windows reaches Ubuntu UI at `http://192.168.29.82:3010`.  
- SSH from Windows → Ubuntu: `sohail@192.168.29.82` with key `medrack_ed25519`.

### 2.1 Ports (canonical)

| Service | Host | Port | How started |
|---------|------|------|-------------|
| MedRack API (FastAPI) | Ubuntu | **8010** | `start_stack.sh` → uvicorn |
| Frontend (Nitro/Node) | Ubuntu | **3010** | `start_stack.sh` → `node frontend/.output/server/index.mjs` |
| Gradio dashboard | Ubuntu | **7860** | `start_stack.sh` → `medrack dashboard` |
| Qwopus llama-server | Windows | **8080** | Scheduled task / `run-qwopus-medrack.bat` |

Legacy note: older stacks used API **8000**. After consolidation, prefer **8010** only.

### 2.2 Auth / SSH

| Direction | Method |
|-----------|--------|
| Windows → Ubuntu | `ssh -i ~/.ssh/medrack_ed25519 sohail@192.168.29.82` |
| Config | `C:\Users\Sohail Imran\.ssh\config` Host `ubuntu-sohail` / `192.168.29.82` |
| Ubuntu → Windows (optional) | Key `~/.ssh/windows_pc` to `sohail@192.168.29.89` (space in Windows username is a known pain) |

**Windows username space gotcha:** paths like `C:\Users\Sohail Imran\...` must always be quoted in PowerShell/`Start-Process` SSH args. Launcher was fixed for this.

---

## 3. How the system works (pipeline)

### 3.1 High-level flow

```
Textbook PDF ──► (optional hybrid OCR) ──► clean text PDF
        ──► chunk + embed (MiniLM) ──► ChromaDB collection kb_<subject>

Question-bank PDF ──► extract questions (marks 10/5/3, chapters)
        ──► stored under modules/

For each question:
  analyze → retrieve top-k (subject filter) → prompt + SOURCE MATERIAL
  → LLM (Qwopus/etc) → cache answer JSON → render PDF (ReportLab)
```

### 3.2 Backend package structure

Root: `/home/sohail/medrack/backend/medrack/`

| Module | Role |
|--------|------|
| `config.py` | Paths, subjects, LLM providers, chunk/retrieval/pipeline versions |
| `cli.py` | `medrack init/status/version/ingest-book/ingest-module/preview/...` |
| `ingest/` | format detect, text extract, OCR (Tesseract), clean, chapter, chunk, embed, index, manifest |
| `module/` | question bank extraction (LLM + regex), MCQ, storage |
| `retrieval/` | engine, strategy, analyzer, rerankers, blueprint_retrieval |
| `planner/` | answer blueprint (deterministic) |
| `answer/` | prompt, llm client, generate, cache, versioning, render, batch |
| `validation/` | quality rules (present; not fully blocking by default on all paths) |
| `dashboard/api/v1.py` | FastAPI `/api/v1/*` |
| `dashboard/services/` | library, questions, pipeline, cache, version, logs, benchmarks |
| `bot/` | Telegram operator bot |
| `benchmarks/` | regression / quality runs |
| `tests/` | ~50 pytest modules |

### 3.3 Subjects (locked enum)

`psm`, `fmt`, `medicine`, `surgery`, `ortho`, `obgyn`, `anesthesia`, `pediatrics`, `ent`, `ophthalmology`

`SUBJECT_FILTER_MANDATORY = true` — never retrieve across subjects.

### 3.4 LLM providers (`config.py` / `.env`)

| Provider | Use |
|----------|-----|
| `llamacpp` | **Production** — Windows Qwopus OpenAI-compatible `/v1/chat/completions` |
| `gemini` | Google free tier option |
| `ollama` | Local Ollama |
| `opencode` | OpenCode Zen (historical; not required for local) |

**Critical:** MedRack often sends **no temperature/top_p** in the request body. Server CLI defaults on llama-server control sampling. Production bat sets factual sampling:

```
--temp 0.3 --top-p 0.8 --top-k 20 --min-p 0
```

Also: `chat_template_kwargs: { enable_thinking: false }` so no `<think>` pollution.

**Fallback:** `llamacpp` has empty `fallback_chain` — if Windows LLM is down, jobs **stall**, they do **not** silently bill cloud APIs.

### 3.5 Embeddings & retrieval

- Model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim), CPU default on Ubuntu  
- Default retrieval top_k: 8  
- Prompt context (current config on app): `PROMPT_CONTEXT_MAX_CHUNKS=8`, `PROMPT_CONTEXT_MAX_CHARS_PER_CHUNK=2500`  
- Cache is **qid-based** and does **not** track temperature; changing model sampling requires cache clear/re-answer to regenerate.

### 3.6 Data directory layout (`MEDRACK_HOME=/home/sohail/medrack-data`)

```
medrack-data/
  books/          # textbook PDFs (incl. parks_clean_text_layer.pdf)
  modules/        # question banks
  index/          # ChromaDB + manifest.json
  answers/        # cached answers by module
  output/         # solved PDFs
  inbox/          # uploads pending
  trash/          # removed books
  logs/           # api.log, frontend.log, ingest logs
  state/          # internal state
  tests/          # regression datasets
  references/     # reference chunks (if used)
  claude-handoff.md   # older partial handoff (superseded by THIS file)
```

### 3.7 Canonical Ubuntu `.env` (`/home/sohail/medrack/.env`)

```
MEDRACK_HOME=/home/sohail/medrack-data
MEDRACK_LLM_MODE=real
MEDRACK_LLM_PROVIDER=llamacpp
MEDRACK_LLM_BASE_URL=http://192.168.29.89:8080
MEDRACK_LLM_MODEL=qwopus
API_PORT=8010
FRONTEND_PORT=3010
MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
```

### 3.8 Frontend

- Path: `/home/sohail/medrack/frontend`  
- Stack: React 19, TanStack Start, Vite, Tailwind, shadcn/Radix  
- Built output: `frontend/.output/server/index.mjs`  
- Routes include: books, question-banks, workspace/pipeline, answers, benchmarks, history, logs, settings  
- API base is **baked at build time** via `MEDRACK_API_BASE` / `VITE_MEDRACK_API_BASE`  

### 3.9 Main API endpoints (prefix `/api/v1`)

- Library: books list/add/upload/delete/reindex; question-banks list/upload/delete/questions  
- Questions: generate, batch, revise, stale, render-pdf  
- Banks: `POST /banks/solve` (async job)  
- Jobs: `GET /jobs/{id}`, `POST /jobs/{id}/cancel` (P3 cooperative stop), `GET /jobs/{id}/pdf` (also after cancel if partial PDF exists)  
- LLM: `GET /llm/status` (P3 live indicator: provider/model/endpoint/online)  
- Pipeline inspect, validation, benchmarks, cache CRUD, version, logs

---

## 4. Windows components (detail)

### 4.1 One-click launcher — `C:\Medrack\launcher\`

| File | Role |
|------|------|
| `RUN-SETUP-FIRST.cmd` | One-time: schtask + SSH key + shortcuts |
| `AUTHORIZE-SERVER.cmd` | One-time password → authorize key |
| `medrack-launcher.ps1` | Daily start: model → SSH start stack → wait :3010 → browser |
| `medrack-stop.ps1` | Stop model (stop-flag first) + SSH stop stack |
| `medrack-config.ps1` | Host/ports/paths |
| `README.md` | Human runbook |

**Config (post-consolidation):**

- `RemoteStart = bash /home/sohail/medrack/start_stack.sh`  
- `RemoteStop = bash /home/sohail/medrack/stop_stack.sh`  
- `SshKey = ...\medrack_ed25519`  
- `ModelTaskName = MedRack Qwopus Server`  
- `ModelStopFlag = C:\ai models\qwopus.stop`  

### 4.2 Qwopus model — `C:\ai models\run-qwopus-medrack.bat`

- Model: `Qwopus3.6-35B-A3B-v1-Q4_K_M.gguf` (~19.7 GB, MoE 40 layers / 256 experts)  
- Server: `C:\llama-cpp-turboquant\build\bin\Release\llama-server.exe`  
- GPU: RTX 3060 Ti **8 GB**  
- **Stability:** `--n-cpu-moe 40` (all experts CPU), `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`, auto-restart watchdog  
- **Stop:** write `qwopus.stop` **before** killing process (else watchdog restarts)  
- Logs: `qwopus-watchdog.log`, `qwopus-server.log`  
- Context: 16K (sufficient for MedRack single-request pattern)  
- Do **not** copy friend configs with `n-cpu-moe 32` + huge context on this card (VRAM danger)

Benchmarks (owner machine): n-cpu-moe 40 ≈ 35–38 tok/s with ~4–5 GB free VRAM; safer and preferred for overnight.

### 4.3 Hybrid OCR tools — `C:\medrack-ocr\`

| Item | Path |
|------|------|
| Python venv | `C:\medrack-ocr\venv` (torch+cu, marker-pdf, surya, rapidocr stack) |
| Merge/wrap script | `C:\medrack-ocr\merge_and_wrap.py` |
| Session scratchpad (Park’s outputs) | `C:\Users\Sohail Imran\AppData\Local\Temp\claude\C--Medrack\0d804f8c-d675-41fe-889a-3f0e94826bf2\scratchpad\` |

Scratchpad contents (Park’s 27th hybrid OCR):

| Dir/File | Status |
|----------|--------|
| `parks_ocr_cache/page_0000.txt` … `page_1051.txt` | RapidOCR full book (1052 pages) |
| `marker_out/marker_*.md` | 7 table-heavy chapter ranges |
| `parks_merged/` | Hybrid page texts |
| `parks_clean_text_layer.pdf` | ~265 MB text-layer PDF |

**Marker ranges used:**

| Chapter | Pages |
|---------|-------|
| NCD Epidemiology | 419–440 |
| Health Programmes | 503–528 |
| RCH / Prev Med | 595–618 |
| Community Care | 713–727 |
| Hospital Waste | 913–929 |
| Biostatistics | 974–987 |
| Health Planning | 999–1011 |

**Claude’s formal plan file:**  
`C:\Users\Sohail Imran\.claude\projects\C--Medrack\memory\ocr-reingest-plan.md`  
(Plan C = hybrid RapidOCR whole book + Marker tables only.)

**Known limitations of current clean PDF builder:**

1. Marker chapter MD split across pages by **character chunking**, not true per-page Marker alignment.  
2. Invisible text overlay originally limited (~50 lines × 80 chars) — ingest still got **1027/1052 pages as text**, 25 OCR fallback.  
3. Hybrid OCR is **not** yet wired into MedRack ingest UI/API as automatic “ingest mode.”

### 4.4 Source scanned PDF

`C:\Users\Sohail Imran\Downloads\parks-textbook-of-preventive-and-social-medicine-27nbsped-9382219196-9789382219194_compress.pdf`  
1052 pages, scanned, originally no text layer.

---

## 5. Current live inventory (as of handoff)

### 5.1 Running stack (after consolidation)

- **package_version:** `1.0.0` (verified via `/api/v1/version`)  
- **API:** `0.0.0.0:8010`  
- **Frontend:** `*:3010`  
- **Dashboard:** may be on `:7860` when start_stack launches it  

### 5.2 Indexed books (live library)

| Title | Subject | Chunks | Notes |
|-------|---------|--------|-------|
| **Parks PSM 27th Ed Clean OCR** | psm | **821** | Hybrid OCR product; **use this for PSM** |
| Essentials of Forensic Medicine (Narayan Reddy) | fmt | 1059 | **Still old ingest path** (not hybrid re-OCR) |
| MCH-v1 | unknown | 0 | Not indexed |

**Removed intentionally (garbled OCR pollution):**

- “PSM Park” 27th compressed scan (old Tesseract KB)  
- “Park's PSM 23rd Ed (47MB scan)” (also pulled garbage like `Bt00 s Orage raci'ty` in retrieval)

### 5.3 Prompt quality work (already on disk)

- File: `/home/sohail/medrack/backend/medrack/answer/prompt.py`  
- Backup: `prompt.py.bak-accuracy`  
- Anti-fabrication rules: do not invent scheme names/stats; rely on SOURCE MATERIAL  
- Still **weak on scope control** (e.g. “ANC objectives” becomes full RMNCH laundry list)

### 5.4 Recent answer quality sample

`C:\Users\Sohail Imran\Downloads\test-solved-4.pdf` (2026-07-09, 6 PSM questions):

- **Good:** No cartoon schemes (Ashwini / Jeevan Rekha gone); real JSY, RKSK, FRU, IMNCI  
- **Bad:** Q3 massively off-scope; Q4 may invent “Pregnancy Risk Assessment Monitoring System” (US PRAMS, not Indian NHM)  
- Conclusion: clean KB helps grounding; **prompt+validator still required for bulletproof answers**

### 5.5 GitHub

- Repo: https://github.com/drsohailimran/medrack  
- Tag **v1.0.0** ≈ early baseline (2026-07-03)  
- Tag **v1.1.0** = P0–P4 freeze (2026-07-10): bulletproof answers, hybrid OCR, stop-gen/LLM UI, ops sync  
- License: proprietary  


---

## 6. Why answers were wrong (root cause chain)

1. Scanned Park’s → Tesseract OCR → **garbage text in Chroma**  
2. Retrieval found right *topic* but unreadable *text*  
3. Prompt encouraged Indian programmes/stats → model **invented** names  
4. Temperature A/B (0.8 vs 0.3) **barely fixed accuracy**; prompt + source text mattered more  
5. Fix path: hybrid re-OCR → clean PDF → re-ingest → remove old books → (still needed) stricter prompts + validation for all subjects  

---

## 7. What has been DONE (checklist)

### Product / app
- [x] Full backend RAG + FastAPI + Gradio + bot code (1.0.0)  
- [x] React frontend with workspace, books, banks, solve jobs  
- [x] Subjects, marks 10/5/3, chapter filters, FMT answer structure  
- [x] Question extraction cleaning for scanned banks (e.g. FMT Singhi)  
- [x] Answer cache + versioning fields  
- [x] GitHub public repo tagged v1.1.0  

### Ops / UX
- [x] One-click Start/Stop MedRack on Windows  
- [x] Passwordless SSH key `medrack_ed25519`  
- [x] Scheduled Task for elevated model start  
- [x] Space-in-path SSH quoting fix  

### Model stability
- [x] Diagnose CUDA OOM on 8 GB card  
- [x] n-cpu-moe 40 + unified memory + watchdog + stop flag  
- [x] Factual sampling defaults on server  

### Quality
- [x] Anti-fabrication prompt patch + backup  
- [x] Retrieval diagnostic proving OCR garbage was ceiling  
- [x] Hybrid OCR Plan C documented and mostly executed for Park’s  
- [x] Clean Park’s PDF produced and copied to Linux  
- [x] Clean Park’s **re-ingested** (821 chunks)  
- [x] Old garbled PSM books removed from library  

### Workspace hygiene (2026-07-09)
- [x] Single Ubuntu app path `/home/sohail/medrack`  
- [x] Single data path `/home/sohail/medrack-data` (live data migrated from Hermes)  
- [x] Old parallel/samples/tar/hermes tree archived with `DO_NOT_USE_README.md`  
- [x] Windows `C:\Medrack` cleaned; old clone/rar/transcript archived  
- [x] Stack runs **package_version 1.0.0** on port 8010  
- [x] Removed/relocated leftover confusion (`_premerge_backup`, accidental `C:`, home PDFs, diag scripts)  
- [x] Stale data `.env` Hermes path fixed  
- [x] Full handoff placed on Windows + Ubuntu app + Ubuntu data  
- [x] Launcher remotes point at `start_stack.sh` / `stop_stack.sh` under `/home/sohail/medrack`  

---

## 8. Phase hierarchy & working agreement (MANDATORY for all AIs)

### 8.0 How we work from now on

1. Work **one phase at a time** in order: **P0 → P1 → P2 → P3 → P4**.  
2. Do **not** start the next phase until the owner **explicitly approves** the current phase.  
3. When a phase’s implementation is done, the AI must:
   - **Verify** (commands, sample answers, API checks — evidence, not claims)  
   - **Document** that the phase is complete (update this file + `docs/PHASES.md`)  
   - **Document** what the **next** phase will do  
   - **Stop and wait** for owner approval  
4. Owner replies with approval (e.g. “P0 approved”) → only then open the next phase.  
5. If verification fails, fix within the **same** phase; do not “half-pass” and move on.  
6. Priority remains: **answer quality > overnight stability > speed**.

**Living checklist file:** `C:\Medrack\docs\PHASES.md` (mirrored on Ubuntu under `medrack/docs/` and `medrack-data/`).

### 8.1 Phase status board

| Phase | Name | Status | Owner approved? |
|-------|------|--------|-----------------|
| **P0** | Bulletproof answers | **COMPLETE — APPROVED (2026-07-09)** | **Yes** |
| **P1** | Hybrid OCR ingest mode | **COMPLETE — APPROVED (2026-07-10)** | **Yes** |
| **P2** | Multi-subject content (book ingest) | **DEFERRED** — owner will ingest later | No |
| **P3** | UX (stop-gen + LLM indicator) | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |
| **P4** | Housekeeping | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |

*(Status values: NOT STARTED | IN PROGRESS | IMPLEMENTED — AWAITING APPROVAL | COMPLETE — APPROVED)*

### 8.2 P0 — Bulletproof answers (all future banks/subjects)

1. **Scope-control prompt** — answer only what is asked; mark-aware max bullets/words ✅  
2. **Hard grounding** — name programmes/laws only if in SOURCE MATERIAL (or universal textbook fact) ✅  
3. **Validator gate** — fail/needs_review on off-scope, invented names, truncation ✅  
4. **Regression pack** — `p0_quality.json` fixtures + unit tests ✅  
5. **Stale answers** when books re-ingested — `kb_revision` bump + auto-regenerate ✅  

**Status:** **COMPLETE — APPROVED** by owner (2026-07-09). Final live stack: `prompt:6`, `validator:5`. Residual mild length edge cases accepted. See `docs/PHASES.md` for full log (P0–P0.4) and final `test-solved-6.pdf` results.

**Code touchpoints:** `answer/prompt.py`, `answer/generate.py`, `answer/kb_revision.py`, `answer/versioning.py`, `validation/rules.py`, `validation/pipeline.py`, `config.PIPELINE_VERSIONS`, `orchestrate.py` (post-index bump).

### 8.3 P1 — Hybrid OCR as productized “ingest mode”

**Status: COMPLETE — APPROVED (2026-07-10).** Owner may revisit. Full troubleshooting in `docs/PHASES.md` §P1.

**Single UI:** Books → Hybrid OCR → stop Qwopus → RapidOCR (+ optional Marker) → validate → text PDF → start Qwopus → index.

**Architecture:**

- Windows `C:\medrack-ocr\ocr_agent_server.py` (auto-started by **Start MedRack**)  
- SSH reverse tunnel: Ubuntu `127.0.0.1:18090` → Windows `:8090` (**required**; LAN 8090 often blocked)  
- Ubuntu `run_hybrid_ingest_book` + Books UI  
- Env: `MEDRACK_OCR_AGENT_URL=http://127.0.0.1:18090`, `MEDRACK_OCR_AGENT_TOKEN=medrack-ocr`  

**Smoke:** 2026-07-10 hybrid_ingest_book `done`, 3 pages, 1 chunk, Qwopus restarted.

### 8.4 P2 — Multi-subject content

**Status: DEFERRED (2026-07-10).** Owner does not want time spent mass-ingesting full textbooks right now. Hybrid path (P1) is ready when they are. Prefer reliability of the existing system over content population until asked.

### 8.5 P3 — UX (stop-gen + LLM indicator)

**Status: COMPLETE — APPROVED (2026-07-10).** Owner: “p3 approved”.

| Feature | Detail |
|---------|--------|
| Stop mid-batch | Workspace **Stop generation** → `POST /jobs/{id}/cancel`; finishes current question, skips rest |
| Keep/delete review | Modal lists answers from this run; delete selected/all or keep; uses existing cache delete APIs |
| Partial PDF | If any answers exist after stop, PDF still rendered/downloadable |
| LLM indicator | Top bar badge from `GET /llm/status` (model · provider, green/red online) |

### 8.6 P4 — Housekeeping

**Status: COMPLETE — APPROVED (2026-07-10).** Released as **v1.1.0** on GitHub.

- [x] GitHub matches machines (backend/frontend/docs/windows launcher+OCR)
- [x] Archives retained on Ubuntu (`medrack-ARCHIVE-20260709`) — DO_NOT_USE, not deleted
- [x] **Auto Marker page detect** (post-v1.1.0): RapidOCR → score pages → Marker only on table-like pages (capped); any textbook  
- [x] Denser Park’s re-chunk still optional residual if retrieval feels thin


---

## 9. Day-to-day operations

### Start everything (wife-friendly)

1. Double-click **Start MedRack** (Desktop or `C:\Medrack\`)  
   - Starts Qwopus, Ubuntu stack, **OCR agent**, and **OCR reverse tunnel**  
2. Wait for model + UI  
3. Hybrid book ingest: **Books** → Hybrid OCR on → upload PDF (one button)
3. Browser → `http://192.168.29.82:3010`  

### Start from Ubuntu SSH

```bash
bash /home/sohail/medrack/start_stack.sh
```

### Stop

```bash
bash /home/sohail/medrack/stop_stack.sh
# and/or Windows: Stop MedRack shortcut
```

### Ingest a book (current CLI — still uses built-in Tesseract path unless PDF already has text)

```bash
export MEDRACK_HOME=/home/sohail/medrack-data
cd /home/sohail/medrack
./.venv/bin/medrack ingest-book --subject psm --book "Title" /path/to.pdf
# optional: --replace
```

### Clear answer cache for a module (required after model/prompt/book changes)

```bash
curl -X DELETE http://127.0.0.1:8010/api/v1/cache/module/MODULE_NAME
# or use UI Cached Answers
```

### Version check

```bash
curl -s http://192.168.29.82:8010/api/v1/version
# expect package_version 1.0.0
```

---

## 10. Claude / AI memory files (Windows)

`C:\Users\Sohail Imran\.claude\projects\C--Medrack\memory\`

| File | Topic |
|------|--------|
| `MEMORY.md` | Index of memories |
| `ocr-reingest-plan.md` | Hybrid OCR Plan C |
| `qwopus-model-stability.md` | CUDA OOM / n-cpu-moe 40 |
| `medrack-llm-pipeline.md` | How LLM is called + quality fixes |
| `one-click-launcher.md` | Launcher design |
| `deployment-topology.md` | Two-machine map |

Session ID for OCR work: `0d804f8c-d675-41fe-889a-3f0e94826bf2`

---

## 11. Design decisions already made (do not re-litigate without evidence)

1. **Quality > stability > speed**  
2. Hybrid OCR Plan C (Rapid full + Marker tables only) for scanned books  
3. Kill/pause local model during heavy OCR (user preference)  
4. Factual llama-server sampling (temp 0.3) because client omits sampling  
5. Do not use classic speculative decoding on this MoE+CPU-offload setup  
6. Mark answers stale / clear cache rather than silent wrong reuse  
7. Single workspace after 2026-07-09 — **no** parallel app trees as “main”  

---

## 12. Risks / landmines

| Risk | Mitigation |
|------|------------|
| Windows path with space | Always quote; launcher already fixed |
| Two data homes (historical) | Use **only** `/home/sohail/medrack-data` now |
| venv shebang breaks if app dir renamed | Rebuild venv with uv python 3.11 if moved again |
| System python is 3.14 without venv | Use `/home/sohail/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3.11` |
| Jobs cancel is cooperative only | Current LLM call still finishes; then remaining questions skip |
| Cache ignores sampling/book upgrades | Always re-answer after changes |
| Old books pollute retrieval | Keep only clean books per subject |
| Secrets | Never commit `.env` with keys; Hermes `.env` had OpenCode key historically |

---

## 13. Suggested next session agenda (for the next AI)

1. Read **this document** + `ocr-reingest-plan.md`.  
2. Verify `curl http://192.168.29.82:8010/api/v1/version` → `1.0.0`.  
3. Implement **P0 prompt scope + validator gate** (fastest path to better PDFs).  
4. Or implement **P1 ingest-mode hybrid OCR + model stop/start** (product requirement).  
5. Hybrid-ingest FMT book (P2).  
6. Do **not** resurrect archived trees as main without explicit user request.

---

## 14. Quick “is the system healthy?” checklist

```bash
# From Windows PowerShell
ssh -i $env:USERPROFILE\.ssh\medrack_ed25519 sohail@192.168.29.82 "curl -s localhost:8010/api/v1/version; curl -s localhost:8010/api/v1/library/books"
# Expect package_version 1.0.0 and Parks PSM 27th Ed Clean OCR

# Model
# Check Windows port 8080 / Start MedRack

# UI
# http://192.168.29.82:3010
```

---

## 15. Document control

| Field | Value |
|-------|--------|
| Title | MedRack Full System Handoff |
| Location (Windows) | `C:\Medrack\docs\MEDRACK_FULL_SYSTEM_HANDOFF.md` |
| Location (Ubuntu) | Also copy to `/home/sohail/medrack-data/` and `/home/sohail/medrack/docs/` if present |
| Supersedes | `/home/sohail/medrack-data/claude-handoff.md` (partial, older) |
| Author of consolidation + this doc | Grok session 2026-07-09 |

**End of handoff.** Any AI continuing work should treat Section 1 paths as law and Section 8 as the backlog.
