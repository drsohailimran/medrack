# MedRack â€” Complete Handover Document (v1.3.1)

**Audience:** Any engineer or AI with **no prior context**.  
**Goal:** After reading this file alone, you can operate, troubleshoot, and extend MedRack.  
**Date:** 2026-07-10 Â· **Owner:** Sohail Imran  

---

## 0. What MedRack is (one paragraph)

MedRack is a **local-first RAG system** that turns MBBS exam question banks into **exam-ready answer PDFs**, grounded in **ingested medical textbooks**. It does **not** call paid cloud APIs for day-to-day answering: generation uses a **local Qwopus MoE model** (llama.cpp) on a Windows GPU PC; the **API, Chroma vector store, and web UI** run on an **Ubuntu** machine on the LAN. Scanned textbooks are cleaned via a **Windows hybrid OCR agent** (RapidOCR + optional auto Marker) before indexing.

**Product priority:** answer quality > overnight stability > speed.

---

## Reliability suite (v1.3.1)

- Jobs persist to $MEDRACK_HOME/jobs.sqlite (restart marks interrupted jobs as error).
- GPU exclusive lock: hybrid OCR / bank extract / solve cannot run concurrently.
- GET /api/v1/system/preflight — disk, OCR agent, LLM, GPU lock, 
eady_for_p2.
- GET /api/v1/jobs — recent job history.
- Book + bank post-job verification (including gibberish text quality).
- Subject validated at upload (400 INVALID_SUBJECT).
- P2 runner: powercfg sleep prevent + preflight + skip-on-fail.



## 1. Machines and network

| Role | Machine | Typical IP | Key ports |
|------|---------|------------|-----------|
| **Ubuntu app server** | Linux host `hermes` | `192.168.29.82` | API **8010**, UI **3010**, Gradio **7860**, OCR tunnel local **18090** |
| **Windows GPU PC** | Sohailâ€™s desktop | `192.168.29.89` | Qwopus **8080**, OCR agent **8090** |
| SSH user (Ubuntu) | `sohail` | | Key-based login from Windows |

**Permanent LAN link (v1.2+):** Ubuntu â†” Windows is kept up by Windows scheduled tasks + dual-path OCR discovery.

| Path | URL | Role |
|------|-----|------|
| **Primary (direct LAN)** | `http://192.168.29.89:8090` | Ubuntu â†’ Windows OCR agent |
| **Backup (SSH reverse tunnel)** | `http://127.0.0.1:18090` on Ubuntu | Windows `ssh -R 18090:127.0.0.1:8090` |
| **Model** | `http://192.168.29.89:8080` | Ubuntu â†’ Qwopus |

Install once (if not already): double-click `C:\Medrack\launcher\INSTALL-PERMANENT-LINK.cmd` (admin) **or** user tasks already registered as `MedRack OCR Agent`, `MedRack OCR Tunnel`, `MedRack Link Watchdog`.

Ubuntu env:
```
MEDRACK_OCR_AGENT_URL=http://192.168.29.89:8090
MEDRACK_OCR_AGENT_URLS=http://192.168.29.89:8090,http://127.0.0.1:18090
MEDRACK_LLM_BASE_URL=http://192.168.29.89:8080
```
API probes URLs in order and uses the first healthy agent.

---

## 2. Canonical paths (single source of truth)

### Windows â€” **only** `C:\Medrack\`

| Path | Contents |
|------|----------|
| `C:\Medrack\` | **Root** Windows workspace |
| `C:\Medrack\launcher\` | Start/Stop MedRack, config, OCR tunnel helper |
| `C:\Medrack\ocr\` | Hybrid OCR agent + venv + pipeline |
| `C:\Medrack\docs\` | This handover, PHASES, troubleshooting |
| `C:\Medrack\archive\` | Dead copies â€” do not run |
| `C:\Medrack\Start MedRack.lnk` | Daily start |
| `C:\Medrack\Stop MedRack.lnk` | Daily stop |
| `C:\ai models\` | Qwopus GGUF + `run-qwopus-medrack.bat` + `qwopus.stop` |
| `C:\llama-cpp-turboquant\` | llama-server binary (used by bat) |

**Legacy:** `C:\medrack-ocr\` may still exist as a duplicate; **canonical agent is `C:\Medrack\ocr\`**. Prefer deleting/ignoring the old folder after confidence.

### Ubuntu

| Path | Contents |
|------|----------|
| `/home/sohail/medrack/` | App code: `backend/`, `frontend/`, `docs/`, `start_stack.sh` |
| `/home/sohail/medrack-data/` | **Data root** (`MEDRACK_HOME`): books, Chroma index, answers, modules, output, logs |
| `/home/sohail/medrack-ARCHIVE-*` | Old multi-copy archives â€” **DO_NOT_USE** |
| `/home/sohail/medrack/.env` | Runtime env (LLM, ports, OCR URL/token) |
| `/home/sohail/medrack/.venv/` | Python venv |

### GitHub

- Repo: https://github.com/drsohailimran/medrack  
- Branch: `main`  
- Tags: `v1.0.0` (early), `v1.1.0` (P0â€“P4 freeze), **`v1.3.1`** (auto Marker + handover + Windows consolidation)  
- License: **proprietary**

---

## 3. Runtime processes

### Start everything (human / wife-friendly)

**Windows:** double-click **Start MedRack** â†’ runs `launcher\medrack-launcher.ps1`:

1. Start **Qwopus** scheduled task (or bat) â†’ wait for `:8080`  
2. Start **OCR agent** `C:\Medrack\ocr\` â†’ wait for `:8090`  
3. Start **SSH reverse tunnel** `18090â†’8090` (durable `start-ocr-tunnel.cmd` preferred)  
4. SSH â†’ `bash /home/sohail/medrack/start_stack.sh`  
5. Wait for UI `:3010` â†’ open browser  

**Stop MedRack** â†’ stop model (stop flag + kill), stop OCR agent, stop Ubuntu stack.

### Ubuntu `start_stack.sh`

Starts if not already listening:

- `uvicorn medrack.dashboard.api.v1:app` on **8010**  
- `node frontend/.output/server/index.mjs` on **3010**  
- Optional Gradio dashboard on **7860**  

Env is loaded from `/home/sohail/medrack/.env`.

### Critical `.env` keys (Ubuntu)

```
MEDRACK_HOME=/home/sohail/medrack-data
MEDRACK_LLM_MODE=real
MEDRACK_LLM_PROVIDER=llamacpp
MEDRACK_LLM_BASE_URL=http://192.168.29.89:8080
MEDRACK_LLM_MODEL=qwopus
API_PORT=8010
FRONTEND_PORT=3010
MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
MEDRACK_OCR_AGENT_URL=http://127.0.0.1:18090
MEDRACK_OCR_AGENT_TOKEN=medrack-ocr
```

Frontend bakes API base at **build time** (`VITE_MEDRACK_API_BASE`). After changing API URL, rebuild frontend:

```bash
cd /home/sohail/medrack/frontend
export VITE_MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
npm run build   # nitro preset node-server (see vite.config.ts)
# restart node .output/server/index.mjs on :3010
```

---

## 4. Architecture (data flow)

```
[Textbooks PDF]
      â”‚
      â”œâ”€ clean digital â”€â”€â–º ingest (chunk â†’ embed MiniLM â†’ Chroma kb_<subject>)
      â”‚
      â””â”€ scanned â”€â”€â–º UI Hybrid OCR â”€â”€â–º Windows agent
                          â”‚  stop Qwopus
                          â”‚  RapidOCR all pages
                          â”‚  auto-score table pages â†’ Marker ranges (optional)
                          â”‚  validate quality
                          â”‚  build full text PDF
                          â”‚  start Qwopus
                          â””â”€â–º Ubuntu indexes clean PDF

[Question bank PDF] â”€â”€â–º extract (LLM/module pipeline) â”€â”€â–º modules/ or regression_datasets JSON

[Solve bank]
  for each question:
    retrieve chunks (subject-scoped) â†’ prompt (scope/grounding/length) â†’ Qwopus
    validate (scope length, grounding, truncation) â†’ cache under answers/
  render multi-question PDF â†’ medrack-data/output/
```

### Packages (Ubuntu backend)

Live package root: `/home/sohail/medrack/backend/medrack/`

| Module | Role |
|--------|------|
| `answer/` | prompt, generate, batch, cache, versioning, kb_revision, render PDF |
| `retrieval/` | analyzer, engine, rerankers |
| `ingest/` | extract, chunk, embed, index |
| `validation/` | ScopeLengthRule, GroundingRule, TruncationRule |
| `dashboard/api/v1.py` | FastAPI routes |
| `dashboard/jobs.py` | In-memory async jobs + **cooperative cancel** |
| `dashboard/services/tasks.py` | ingest book, hybrid ingest, extract bank, solve bank |
| `dashboard/services/ocr_bridge.py` | Pull-queue fallback for OCR jobs |
| `config.py` | paths, subjects, LLM providers, PIPELINE_VERSIONS |

### Frontend

TanStack Start + React at `/home/sohail/medrack/frontend/src/`

| Route | Purpose |
|-------|---------|
| `/` | **Workspace** â€” preview + solve module, stop gen, keep/delete review |
| `/books` | Upload/ingest books, hybrid OCR + auto Marker toggles |
| `/question-banks` | Upload/extract banks |
| `/answers` | Cached answers, delete |
| `/pipeline` | Read-only pipeline inspect |
| Top bar | Package version + **live LLM status** |

API client: `src/lib/api/client.ts` Â· jobs: `src/lib/use-job.ts`.

### Windows OCR agent

`C:\Medrack\ocr\`

| File | Role |
|------|------|
| `ocr_agent_server.py` | FastAPI push API :8090 + optional pull loop |
| `pipeline/hybrid_ocr.py` | RapidOCR, **auto Marker page detect**, validate, text PDF |
| `pipeline/build_text_pdf.py` | Full text layer PDF (no 50Ã—80 truncation) |
| `pipeline/model_control.py` | Stop/start Qwopus via stop-flag / scheduled task |
| `START-OCR-AGENT.cmd` | Manual agent start |

**Auto Marker algorithm** (any textbook):

1. RapidOCR every page (cached under `jobs/<id>/work/rapidocr_cache/`)  
2. Score each page for table-like text (short lines, multi-space columns, digit grids, pipes)  
3. Select pages with score â‰¥ **0.48**, cap ~**18%** of book or **180** pages  
4. Merge into ranges (max span **28** pages)  
5. Run Marker on those ranges only; on failure keep RapidOCR  
6. Optional legacy Parkâ€™s ranges only if env `MEDRACK_MARKER_LEGACY_PARKS=1` and auto finds nothing  

**No Qwopus** is used for page selection (would take hours). Heuristics are seconds after OCR.

---

## 5. Answer quality pipeline (P0 â€” locked)

Versions live in `PIPELINE_VERSIONS` / answer `versions` dict:

| Key | Meaning (v1.3.1 live) |
|-----|------------------------|
| schema | 3 |
| prompt | **6** |
| validator | **5** |
| retrieval / planner / reranker / renderer | see config |

**Prompt:** SCOPE CONTROL + HARD GROUNDING + LENGTH BAND (marks-aware).  
**Validator:** fails over/under length, invented scheme names (with allowlist), truncation.  
**Behavior:** bad answers are still **saved** with `needs_review=true` (overnight stability).  
**Stale cache:** on pipeline version drift or KB reindex (`kb_revision`), answers auto-regenerate.

Do **not** casually regress prompt/validator without re-running `tests/test_p0_quality.py` and a live `test` bank PDF check.

---

## 6. Jobs and cancel (P3)

- Jobs are **in-memory** on the API process (lost on API restart).  
- Create: e.g. `POST /banks/solve`, `POST /library/books/upload` â†’ `{ job_id }`  
- Poll: `GET /jobs/{id}` â†’ status `pending|running|done|error|cancelled`  
- Cancel: `POST /jobs/{id}/cancel` â€” **cooperative**: current LLM/OCR unit finishes, then stop.  
- Solve cancel returns partial answers + optional partial PDF; UI offers **keep/delete** review.  
- PDF: `GET /jobs/{id}/pdf` when `done` or `cancelled` with `pdf_path`.

---

## 7. Main HTTP API (prefix `/api/v1`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/version` | package + pipeline versions |
| GET | `/llm/status` | provider, model, base_url, online probe |
| GET/POST/DELETE | `/library/booksâ€¦` | list, upload, delete, reindex |
| POST | `/library/books/upload` | multipart; `hybrid_ocr`, `use_marker` |
| GET/POST/DELETE | `/library/question-banksâ€¦` | banks |
| POST | `/banks/solve` | async solve whole bank |
| POST | `/questions/generate` | single answer |
| GET/POST | `/jobs/{id}`, `/jobs/{id}/cancel`, `/jobs/{id}/pdf` | job control |
| GET/DELETE | `/cache/entriesâ€¦` | answer cache |
| GET | `/pipeline/inspect` | stage trace |
| OCR agent bridge | `/ocr/agent/*` | claim/progress/result (pull mode) |

Error shape: JSON `{ error_code, detail }` with HTTP status.

---


### Question bank hybrid OCR (v1.3+)

Question Banks upload supports the **same Windows hybrid OCR** as textbooks:

1. Optional Hybrid OCR (default on) + Auto Marker
2. Windows: stop Qwopus → RapidOCR → Marker on table pages → clean PDF → start Qwopus
3. Ubuntu: extract questions (regex + LLM) from clean text
4. Bank appears in Workspace

API: `POST /library/question-banks/upload` with `hybrid_ocr=true` & `use_marker=true`.

### Clear library for re-ingest

- UI Books → **Delete all books** (or single Delete)
- API: `POST /api/v1/library/books/clear-all` (purges `kb_*` Chroma collections)
- Fixed: filesystem-only ("not indexed") PDFs can now be deleted

### Post-ingest verification (automatic + API)

Every successful book ingest (`run_ingest_book` / hybrid) runs a **verification gate** before the job is marked done:

| Check | Hard fail if |
|--------|----------------|
| Active manifest entry | Missing |
| Pages / chunks in manifest | pages ≤ 0 or chunks &lt; 1 |
| Chroma vectors for `book_id` | count &lt; 1 |
| Sample retrieval on subject KB | Probe errors (soft) / empty collection (hard when no hits at all) |
| Source PDF on disk | Missing → warning |
| Chunk density / OCR suspects | Warning only if low/high |

- Job **errors** if hard checks fail (overnight P2 will not treat it as success).
- Result JSON includes `verification: { ok, checks, errors, warnings, chunks_chroma, ... }`.
- Manual recheck: `GET /api/v1/library/books/{book_id}/verify`

### P2 overnight

Owner drops PDFs + `ORDER.md` in `C:\Medrack\p2-inbox\`. AI ingests in order with hybrid OCR; **each book must pass verification** before the next starts (or failures are logged and skipped per policy).

## 8. Day-to-day operator workflows

### A. Solve a question module â†’ PDF

1. Start MedRack  
2. UI â†’ Workspace  
3. Select bank + textbook subject context  
4. Set length boxes (defaults ~750/375/125 words for 10/5/3)  
5. Generate preview â†’ Approve & Solve  
6. Optional: **Stop generation** mid-run â†’ review keep/delete  
7. Download PDF  

### B. Ingest a scanned textbook (hybrid)

1. Start MedRack (agent + tunnel required)  
2. Books â†’ Hybrid OCR **on**, Auto Marker **on** (default)  
3. Upload PDF â†’ one job: stop model â†’ OCR â†’ auto Marker â†’ validate â†’ restart model â†’ index  
4. Confirm book appears **indexed** with chunk_count > 0  

### C. Clear bad answers

- Cached Answers page, or delete under `MEDRACK_HOME/answers/<module>/`  
- Re-solve bank  

---

## 9. Verification commands (always evidence-based)

```bash
# Ubuntu
curl -sS http://127.0.0.1:8010/api/v1/version
curl -sS http://127.0.0.1:8010/api/v1/llm/status
curl -sS http://127.0.0.1:18090/v1/health   # needs tunnel
ss -tln | grep -E '8010|3010|18090'
cd /home/sohail/medrack/backend
../.venv/bin/python -m pytest medrack/tests/test_p0_quality.py medrack/tests/test_p3_cancel.py -q
```

```powershell
# Windows
curl.exe -sS http://127.0.0.1:8090/v1/health
curl.exe -sS http://127.0.0.1:8080/health
curl.exe -sS http://192.168.29.82:8010/api/v1/version
cd C:\Medrack\ocr
.\venv\Scripts\python.exe -m pipeline.test_auto_marker
```

**E2E (2026-07-10) verified:** hybrid ingest with auto Marker selected page 2 of smoke PDF; job `done`; `marker.mode=auto`; single-question generate OK (~22s); API **1.2.0**.

---

## 10. Troubleshooting (high-signal)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| UI loads but API fails | Wrong baked `VITE_MEDRACK_API_BASE` | Rebuild frontend with correct LAN URL |
| Hybrid stuck / agent down | OCR agent not running | Start task `MedRack OCR Agent` or Start MedRack; check `http://192.168.29.89:8090/v1/health` |
| Agent up, Ubuntu canâ€™t reach | Firewall / wrong IP | Confirm Windows LAN IP in config; allow TCP 8090; fallback tunnel `18090` |
| Tunnel only path fails | Tunnel task stopped | `Start-ScheduledTask 'MedRack OCR Tunnel'`; watchdog restarts every 5 min |
| Empty reply on tunnel | Agent crashed mid-request | Restart agent; ensure only one agent on 8090 |
| Model offline in top bar | Qwopus not on 8080 | Start MedRack / scheduled task; check `C:\ai models` bat |
| Answers invent schemes | Dirty KB or old cache | Hybrid re-ingest; delete answers cache; check validator |
| Cancel does nothing immediately | Cooperative cancel | Waits for current question; then status `cancelled` |
| Jobs disappear | API restart | Jobs are in-memory only |
| Frontend 200 but old UI | Old `.output` | Rebuild + restart node server |
| Wrong Windows OCR folder | Using `C:\medrack-ocr` | Use **`C:\Medrack\ocr`** |

More detail: `docs/TROUBLESHOOTING.md`.

---

## 11. How to change the system safely

### Rule: phase gate

1. Implement one concern  
2. Verify with commands/PDF evidence  
3. Document  
4. Do not ship silent regressions to prompt/validator without tests  

### Add a feature (checklist)

1. Prefer editing **Ubuntu** `backend/medrack/` and `frontend/src/`  
2. For OCR: edit **`C:\Medrack\ocr/pipeline/`**, run `test_auto_marker`  
3. Unit tests under `backend/medrack/tests/`  
4. Restart API: kill :8010 + `start_stack.sh`  
5. Rebuild frontend if UI changed  
6. Update this HANDOVER + PHASES if behavior changes  
7. Commit/push GitHub; bump version if release  

### Sync Windows OCR into git

Repo path: `windows/ocr/` (source only; **no** `venv/`, no `jobs/`).  
Copy from `C:\Medrack\ocr\` excluding venv/jobs.

### Bump version

- `backend/medrack/__init__.py` â†’ `__version__`  
- OCR agent FastAPI version string  
- Tag `vX.Y.Z` on GitHub  
- Restart API to serve new package_version  

---

## 12. Phase history (summary)

| Phase | Status | What |
|-------|--------|------|
| P0 | **Approved** | Bulletproof answers: prompt/validator/stale/regression |
| P1 | **Approved** | Hybrid OCR one-UI, agent + tunnel |
| P2 | **Deferred** | Mass multi-subject book content (owner runs later) |
| P3 | **Approved** | Stop mid-batch + keep/delete; live LLM indicator |
| P4 | **Approved** | GitHub sync, housekeeping |
| Post-1.1 | **v1.3.1** | Auto Marker page detect; Windows single-folder; this handover |

---

## 13. Security & privacy

- Proprietary code â€” do not publish private keys, `.env`, or patient data.  
- SSH keys: Windows `%USERPROFILE%\.ssh\medrack_ed25519`; Ubuntu GitHub `~/.ssh/github_hermes`.  
- OCR token default `medrack-ocr` is LAN-trust only â€” not internet-facing.  
- Never commit `.env`, answer caches, or textbook PDFs to public remotes.

---

## 14. File map for the next AI (quick open list)

| Need | Open |
|------|------|
| Operate system | this file Â§1â€“3, Â§8â€“10 |
| Answer quality | `backend/medrack/answer/prompt.py`, `validation/rules.py`, `config.py` PIPELINE_VERSIONS |
| Solve job | `dashboard/services/tasks.py` `run_solve_bank`, `answer/batch.py`, `dashboard/jobs.py` |
| Hybrid OCR | `C:\Medrack\ocr\pipeline\hybrid_ocr.py`, `dashboard/services/tasks.py` `run_hybrid_ingest_book` |
| UI solve | `frontend/src/routes/index.tsx` |
| UI books | `frontend/src/routes/books.tsx` |
| API surface | `dashboard/api/v1.py` |
| Launcher | `C:\Medrack\launcher\medrack-config.ps1`, `medrack-launcher.ps1` |
| Phase status | `docs/PHASES.md` |

---

## 15. Known residuals (accepted)

1. Multi-page Marker ranges still **char-split** markdown across pages (imperfect alignment).  
2. Auto Marker is **heuristic**, not perfect; caps prevent whole-book Marker.  
3. Parkâ€™s chunk density (fewer chunks than ancient ingest) â€” optional re-chunk if retrieval thin (content work, not code freeze).  
4. Mild answer length edge cases under P0 residual.  
5. Jobs not persisted across API restarts.  
6. `C:\medrack-ocr` may remain as legacy duplicate until owner deletes.  

---

## 16. Definition of â€œhealthy systemâ€

- `GET /version` â†’ `package_version` **1.2.0** (or newer)  
- `GET /llm/status` â†’ `online: true` for qwopus  
- UI `:3010` returns 200  
- OCR agent `:8090` health OK on Windows  
- Ubuntu `curl 127.0.0.1:18090/v1/health` OK (tunnel)  
- Can solve `test` bank and download PDF  
- Can hybrid-ingest a small PDF end-to-end  

If all of the above pass, MedRack is operational.

---

*End of handover. Keep this file updated when behavior or paths change.*

