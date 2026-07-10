# MedRack Freeze Document — v1.3.2

**Audience:** Humans and local LLMs with **zero prior session context**.  
**Purpose:** Operate, troubleshoot, and extend MedRack without guessing.  
**Freeze date:** 2026-07-10  
**Package version:** **1.3.2**  
**GitHub:** https://github.com/drsohailimran/medrack · tag **`v1.3.2`**  
**Owner:** Sohail Imran  

If you are an LLM: treat this file as the **single source of operational truth**. Prefer it over older docs when they conflict. Read `HANDOVER.md` for short ops; this file for deep work.

---

## 0. One-paragraph product definition

MedRack is a **local-first RAG system** that turns **MBBS exam question banks** into **exam-ready answer PDFs**, grounded in **ingested medical textbooks** (e.g. Park’s PSM). Day-to-day answering uses a **local Qwopus MoE model** (llama.cpp) on a Windows GPU PC. **API, Chroma vector store, and web UI** run on Ubuntu on the LAN. Scanned textbooks use a **Windows hybrid OCR agent** (RapidOCR + optional auto Marker) before indexing.

**Priority order:** answer quality > overnight stability > speed.

**Not in scope for day-to-day:** paid cloud APIs for answering; multi-user auth; public internet exposure of API/OCR ports.

---

## 1. Topology (machines, IPs, ports)

| Role | Host | Typical IP | Ports / services |
|------|------|------------|------------------|
| Ubuntu app | `hermes` | `192.168.29.82` | **8010** FastAPI, **3010** UI, **7860** Gradio (optional), **18090** SSH reverse tunnel endpoint (local) |
| Windows GPU | Sohail desktop | `192.168.29.89` | **8080** Qwopus llama-server, **8090** OCR agent |
| SSH | user `sohail` on Ubuntu | key: `%USERPROFILE%\.ssh\medrack_ed25519` | passwordless from Windows |

### Network paths (OCR)

| Path | URL | Role |
|------|-----|------|
| Primary | `http://192.168.29.89:8090` | Ubuntu → Windows OCR agent (LAN) |
| Backup | `http://127.0.0.1:18090` on Ubuntu | Windows `ssh -R 18090:127.0.0.1:8090` |
| Model | `http://192.168.29.89:8080` | Ubuntu → Qwopus |

Ubuntu env (canonical):

```bash
MEDRACK_HOME=/home/sohail/medrack-data
MEDRACK_LLM_MODE=real
MEDRACK_LLM_PROVIDER=llamacpp
MEDRACK_LLM_BASE_URL=http://192.168.29.89:8080
MEDRACK_LLM_MODEL=qwopus
API_PORT=8010
FRONTEND_PORT=3010
MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
MEDRACK_OCR_AGENT_URL=http://192.168.29.89:8090
MEDRACK_OCR_AGENT_URLS=http://192.168.29.89:8090,http://127.0.0.1:18090
MEDRACK_OCR_AGENT_TOKEN=medrack-ocr   # must match Windows agent
```

API probes OCR URLs in order; first healthy wins.

---

## 2. Canonical paths (do not invent new roots)

### Windows — only `C:\Medrack\`

| Path | Purpose |
|------|---------|
| `C:\Medrack\` | Root Windows workspace |
| `C:\Medrack\launcher\` | Start/Stop, config, tunnel, permanent link install |
| `C:\Medrack\ocr\` | OCR agent, venv, hybrid pipeline |
| `C:\Medrack\ocr\pipeline\hybrid_ocr.py` | RapidOCR + auto Marker + page distribute + gibberish gate |
| `C:\Medrack\ocr\pipeline\model_control.py` | Stop/start Qwopus with RAM/GPU free check |
| `C:\Medrack\ocr\ocr_agent_server.py` | FastAPI agent :8090 (push + pull) |
| `C:\Medrack\ocr\start-ocr-agent-hidden.ps1` | **Hidden** agent launcher (no console window) |
| `C:\Medrack\launcher\start-ocr-tunnel-hidden.ps1` | **Hidden** reverse tunnel launcher |
| `C:\Medrack\docs\` | This freeze + HANDOVER + audit |
| `C:\Medrack\p2-inbox\` | Overnight P2 PDFs + `ORDER.md` + runner |
| `C:\Medrack\archive\` | Dead copies — **DO NOT RUN** |
| `C:\ai models\` | Qwopus GGUF + `run-qwopus-medrack.bat` + `qwopus.stop` |
| `C:\llama-cpp-turboquant\build\bin\Release\llama-server.exe` | llama-server binary |

**Legacy:** `C:\medrack-ocr\` may exist; **ignore**. Canonical agent is `C:\Medrack\ocr\`.

### Ubuntu

| Path | Purpose |
|------|---------|
| `/home/sohail/medrack/` | App code: `backend/`, `frontend/`, `docs/`, `start_stack.sh` |
| `/home/sohail/medrack-data/` | **Data** (`MEDRACK_HOME`): books, index, modules, answers, output, logs, `jobs.sqlite` |
| `/home/sohail/medrack/.env` | Runtime env |
| `/home/sohail/medrack/.venv/` | Python venv (editable install of `backend/medrack`) |
| `/home/sohail/medrack-ARCHIVE-*` | Old archives — **DO_NOT_USE** |

### Data layout under `MEDRACK_HOME`

```
medrack-data/
  books/                 # textbook PDFs (incl. *_hybrid_ocr.pdf)
  inbox/                 # book upload staging
  modules/               # question-bank PDFs (not books)
  index/chroma/          # Chroma collections kb_<subject>
  tests/regression_datasets/*.json   # question banks
  answers/<module>/.../*.json        # cached generated answers
  output/*_solved.pdf
  jobs.sqlite            # async job registry (survives API restart for history)
  logs/api.log
  docs/                  # mirrored docs optional
```

---

## 3. Version freeze (locked)

| Component | Version | Notes |
|-----------|---------|--------|
| Package | **1.3.2** | `medrack.__version__` |
| Prompt | **7** | Multi-part depth, aligned length bands, finish cleanly |
| Validator | **7** | Explicit chunk cites only; wider 5-mark band; NDD/NAHP/ICTC allowlist |
| Schema | **3** | needs_review + kb_revision on answers |
| Retrieval | **1** | top_k≈8, MiniLM-L6-v2 |
| Planner | **0** | not used in day-to-day bank solve path |
| Renderer | **1** | exam-prep PDF |
| OCR agent | **1.3.1** | stop-before-OCR, exclusive pipeline lock |

Bump `PIPELINE_VERSIONS` in `medrack/config.py` when changing prompt/validator/retrieval so answer **cache keys** invalidate.

---

## 4. How to start / stop (operator)

### Daily start (Windows)

1. Double-click **`C:\Medrack\Start MedRack.lnk`**  
   - Starts Qwopus scheduled task (console window OK — white text on black)  
   - Ensures OCR agent + tunnel (hidden)  
   - Starts Ubuntu stack via SSH (`start_stack.sh`)  
   - Opens UI `http://192.168.29.82:3010`

2. Wait until top bar shows LLM online (model load can take several minutes; ~21GB mlock).

### Daily stop

- **`Stop MedRack.lnk`** — stops model + stack; **keeps OCR agent + tunnel** (permanent link) by default.

### Permanent link tasks (Windows Task Scheduler)

| Task | Purpose | Window |
|------|---------|--------|
| MedRack OCR Agent | :8090 agent | **Hidden** |
| MedRack OCR Tunnel | reverse SSH 18090 | **Hidden** |
| MedRack Link Watchdog | restart agent/tunnel if down | Hidden |
| MedRack Qwopus Server | llama-server + watchdog bat | **Visible console** |

Re-register hidden OCR tasks:  
`powershell -File C:\Medrack\launcher\register-hidden-ocr-tasks.ps1`

Install permanent link (admin once):  
`C:\Medrack\launcher\INSTALL-PERMANENT-LINK.cmd`

### Health checks

```bash
# From Windows or Ubuntu
curl -s http://192.168.29.82:8010/api/v1/version
curl -s http://192.168.29.82:8010/api/v1/system/preflight
curl -s http://192.168.29.89:8090/v1/health
curl -s http://192.168.29.89:8080/health
```

Preflight returns: disk, ocr_agent, llm, gpu_lock, `ready_for_p2`.

---

## 5. Core flows (end-to-end)

### 5.1 Hybrid textbook ingest (Books UI)

1. User uploads PDF + subject + **hybrid_ocr=true** (typical for scans).  
2. API `POST /library/books/upload` → job `hybrid_ingest_book`.  
3. Ubuntu: pre-call `POST {ocr}/v1/model/stop` until `llama_running=false`.  
4. Push PDF to Windows agent `POST /v1/jobs`.  
5. Agent: **GPU exclusive** — stop Qwopus (stop flag + `schtasks /End` + wait RAM/GPU free) → RapidOCR → auto Marker ranges → validate pages (incl. gibberish) → text PDF → start Qwopus.  
6. Ubuntu indexes clean PDF into Chroma `kb_<subject>`.  
7. **verify_book** hard-fails empty Chroma / missing manifest; soft warnings for density/OCR suspects.  
8. Job result includes `verification`.

**Critical:** Qwopus runs **elevated** (`RunLevel Highest`). Plain `taskkill` gets Access denied. Stop uses **`schtasks /End /TN "MedRack Qwopus Server"`** + stop flag first.

### 5.2 Question bank upload

1. `POST /library/question-banks/upload` with `hybrid_ocr`, `use_marker`.  
2. **Auto-skip hybrid** if PDF already has native text layer (avg chars ≥ ~80). Hybrid on text PDFs **destroys** extractable questions (bug fixed in 1.3.2 era).  
3. Regex MCQ/theory extract + LLM extract → merge → save JSON bank.  
4. **verify_question_bank** requires ≥1 question, stem quality.  
5. Fallback to original PDF if hybrid path yields 0 questions.

### 5.3 Solve bank → PDF

1. Workspace: select bank, marks filters, solve.  
2. Job `solve_bank`: per question generate (retrieve → prompt → LLM → clean → validate → cache).  
3. Render multi-page exam-prep PDF to `output/`.  
4. `needs_review=true` if any validation **FAIL** rule.

### 5.4 GPU exclusive lock

Kinds that cannot overlap: `hybrid_ingest_book`, `extract_bank`, `solve_bank`.  
Registry in `dashboard/jobs.py` — second job waits or cancels while waiting.

---

## 6. Answer generation pipeline (code map)

| Step | Module | Function / notes |
|------|--------|------------------|
| Cache lookup | `answer/cache.py` | Key includes pipeline versions, subject, target words |
| Embed query | `ingest/embed.py` | MiniLM; retrieval query may be **boosted** (adolescent→RKSK etc.) |
| Retrieve | `retrieval/` | `retrieve_for_question` |
| Prompt | `answer/prompt.py` | Theory prompt v7: length band, multi-part block, grounding |
| LLM | `answer/llm.py` | OpenAI-compatible → Qwopus :8080 |
| Token budget | `answer/generate.py` | 5-mark ~1.3×target+200 tokens (finish last bullet); 10-mark larger |
| Clean text | `answer/generate.py` `_clean_answer_text` | Strip incomplete last bullets / orphan headings |
| Validate | `validation/pipeline.py` + `rules.py` | FAIL → needs_review |
| Save | `answer/cache.py` | answers/<module>/... |

### Length bands (ScopeLengthRule, with target 375/750)

| Marks | Approx min–max words |
|------:|----------------------|
| 5 | ~240–457 |
| 10 | ~525–840 |

### Validation rules that matter for exam banks

| Rule | FAIL when |
|------|-----------|
| ScopeLengthRule | Outside mark band |
| GroundingRule | Foreign schemes or acronyms not in source **and** not allowlisted |
| TruncationRule | Incomplete last line / empty bullet / cut mid-phrase |
| ReferenceConsistencyRule | Only **explicit** `chunk_…` / `[id]` duplicates — **not** normal English words |

**Do not** treat repeated words like `pregnancy` as chunk IDs (fixed in validator 7).

### Multi-part detection

`prompt._is_multipart_question`: ≥2 `?`, a/b/c parts, or multiple imperatives (Mention/Outline/…).  
Injects MULTI-PART STEM block requiring separate headings and depth per part.

---

## 7. API cheat sheet (`/api/v1`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/version` | package + pipeline versions |
| GET | `/system/preflight` | disk, OCR, LLM, GPU lock, ready_for_p2 |
| GET | `/llm/status` | live model indicator |
| GET | `/jobs` | recent jobs (SQLite) |
| GET | `/jobs/{id}` | job status |
| POST | `/jobs/{id}/cancel` | cooperative cancel |
| GET | `/library/books` | list books |
| POST | `/library/books/upload` | hybrid_ocr, use_marker, replace, subject, title |
| POST | `/library/books/clear-all` | wipe books + purge kb_* |
| GET | `/library/books/{id}/verify` | post-ingest verify |
| DELETE | `/library/books/{id}` | delete one |
| GET | `/library/question-banks` | list banks |
| POST | `/library/question-banks/upload` | hybrid_ocr, use_marker |
| GET | `/library/question-banks/{name}/verify` | bank verify |
| GET | `/library/question-banks/{name}/questions` | full questions |
| POST | `/questions/generate` | single answer |
| POST | solve bank (see frontend) | batch → PDF |

Errors: `{ "error_code": "…", "detail": "…" }` e.g. `INVALID_SUBJECT`.

Known subjects: `psm, fmt, medicine, surgery, obgyn, pediatrics, ortho, ent, ophthalmology, anesthesia`.

---

## 8. Windows scheduled-task / model stop contract

### Stop Qwopus (for OCR)

Order **must** be:

1. Write `C:\ai models\qwopus.stop`  
2. `schtasks /End /TN "MedRack Qwopus Server"`  
3. Best-effort taskkill (may Access denied — OK if End worked)  
4. Wait until process gone + free RAM/GPU healthy  
5. Only then load RapidOCR / Marker  

Implemented in `model_control.stop_model()`. Hybrid pipeline **hard-fails** if stop not OK.

### Start Qwopus

1. Delete stop flag  
2. `schtasks /Run /TN "MedRack Qwopus Server"`  
3. Console shows live llama-server lines (`color 0F` white on black) — **do not** redirect stdout solely to a file (that caused black empty console).

Bat: `C:\ai models\run-qwopus-medrack.bat`  
Stable settings: `--n-cpu-moe 40`, `--mlock`, unified memory spill, watchdog loop.

---

## 9. P2 overnight campaign

**P2 is not a new engine** — ordered hybrid book ingest + verify + skip-on-fail.

| Item | Path |
|------|------|
| Drop zone | `C:\Medrack\p2-inbox\` |
| Order file | `ORDER.md` lines: `order|subject|title|filename.pdf` |
| Runner | `run-p2-overnight.ps1` |
| Policy | skip on fail; report in `p2-report.md` / `.json` |
| Start only when owner says | **P2 ready** + PDFs + ORDER |

Runner: powercfg AC sleep off, preflight each book, hybrid+marker defaults on.

---

## 10. Troubleshooting playbook (for LLMs)

### Symptom → check → fix

| Symptom | Check | Fix |
|---------|-------|-----|
| Hybrid OCR crashes PC | Qwopus + OCR concurrent | Ensure agent v1.3+; stop uses schtasks /End; never OCR while model holds mlock |
| Qwopus not stopping | Access denied on taskkill | Stop flag + `schtasks /End`; elevated task |
| Black empty Qwopus console | stdout redirected to log only | run bat without `> log 2>&1` alone; live console |
| OCR console windows clutter | old START-OCR-AGENT.cmd | use hidden PS1 launchers + Hidden scheduled tasks |
| Bank upload 0 questions | hybrid on text PDF | auto-skip hybrid if native text layer; fallback original |
| 5/6 needs_review (length) | ScopeLengthRule | bands widened; multi-part prompt; re-solve |
| All needs_review “duplicate chunk refs” | ReferenceConsistency false positive | only explicit chunk_ cites; validator 7 |
| Last line mid-sentence `• HBNC is` | max_output_tokens hit | raise 5-mark token headroom; `_clean_answer_text` strip incomplete bullet |
| Grounding NAHP/NDD/ICTC | allowlist | add real Indian acronyms to `_GROUNDING_ALLOWLIST` |
| Tunnel port 18090 busy | multiple ssh -R | FIX-OCR-TUNNEL.cmd; kill dupes |
| Jobs disappear after API restart | old in-memory only | jobs.sqlite; interrupted jobs marked error |
| Wrong subject collection | typo subject | validate_subject at upload |
| Frontend wrong host | baked Vite base | rebuild frontend with `VITE_MEDRACK_API_BASE` |

### Useful log files

| Log | Location |
|-----|----------|
| API | `/home/sohail/medrack-data/logs/api.log` |
| OCR agent | `C:\Medrack\ocr\agent.out.log`, `agent.err.log` |
| Tunnel | `C:\Medrack\ocr\tunnel.out.log` |
| Link watchdog | `C:\Medrack\ocr\link-watchdog.log` |
| Qwopus watchdog | `C:\ai models\qwopus-watchdog.log` |
| Qwopus server (notes) | `C:\ai models\qwopus-server.log` |

### Restart API only (Ubuntu)

```bash
# kill uvicorn on 8010, then:
cd /home/sohail/medrack
set -a; source .env; set +a
export MEDRACK_HOME=/home/sohail/medrack-data
nohup .venv/bin/python -m uvicorn medrack.dashboard.api.v1:app --host 0.0.0.0 --port 8010 \
  > $MEDRACK_HOME/logs/api.log 2>&1 &
```

Or `bash start_stack.sh` / `stop_stack.sh`.

### Editable package

Code lives in `/home/sohail/medrack/backend/medrack/`. Venv uses editable install — **edit files then restart API** (no reinstall needed for pure Python).

---

## 11. How to add features (conventions)

1. **API:** add route in `dashboard/api/v1.py`; business logic in `dashboard/services/`.  
2. **Long jobs:** use `jobs.registry.run(kind, body)`; call `progress(pct, msg)`; respect cancel and GPU exclusive kinds if using GPU/OCR.  
3. **Prompt changes:** edit `answer/prompt.py`; **bump** `PIPELINE_VERSIONS["prompt"]` so caches stale.  
4. **Validation:** edit `validation/rules.py`; **bump** `validator` version; keep FAIL vs WARN intentional.  
5. **OCR:** Windows only under `C:\Medrack\ocr\pipeline\`; agent must remain stop→OCR→start.  
6. **Frontend:** `frontend/src/routes/*.tsx`; rebuild production output if shipping UI.  
7. **Subjects:** add to `KNOWN_SUBJECTS` / `preflight.py` and `config.Subject` / `SUBJECT_CONTEXTS`.  
8. **Tests:** `backend/medrack/tests/` — run with package venv.  
9. **Never** commit secrets; token is LAN-only weak shared secret.  
10. **Docs:** update this FREEZE or CHANGELOG when behaviour changes.

---

## 12. File map (critical paths)

### Backend (Ubuntu)

```
backend/medrack/
  __init__.py              # __version__
  config.py                # PIPELINE_VERSIONS, targets, SUBJECT_CONTEXTS
  answer/
    generate.py            # orchestrate generate + clean + validate
    prompt.py              # MCQ/Theory templates
    llm.py                 # clients
    cache.py
    render_full.py         # bank PDF
  validation/
    rules.py               # ScopeLength, Grounding, Truncation, ReferenceConsistency, …
    pipeline.py
  dashboard/
    jobs.py                # SQLite jobs + GPU lock
    api/v1.py
    services/
      tasks.py             # ingest, hybrid OCR, extract_bank, solve_bank
      library.py           # verify_book, verify_question_bank, clear-all
      preflight.py         # disk, subject, gibberish
  ingest/                  # extract, chunk, embed, index, ocr fallback
  retrieval/               # adaptive retrieve
  module/                  # bank extract (mcq regex + llm_extract)
```

### Windows OCR

```
C:\Medrack\ocr\
  ocr_agent_server.py
  pipeline/hybrid_ocr.py
  pipeline/model_control.py
  start-ocr-agent-hidden.ps1
```

### Windows launcher

```
C:\Medrack\launcher\
  medrack-config.ps1
  medrack-launcher.ps1
  medrack-stop.ps1
  start-ocr-tunnel-hidden.ps1
  register-hidden-ocr-tasks.ps1
  install-permanent-link.ps1
```

---

## 13. Known residuals (accepted at freeze)

1. **No full mid-OCR job resume** after API kill — re-run ORDER line; RapidOCR cache helps.  
2. **Single-question generate** not in GPU exclusive set (only hybrid/extract/solve).  
3. **Marker multi-page** is proportional/paragraph split, not perfect per-page Marker.  
4. **Gibberish gate** is heuristic, not medical correctness.  
5. **DHCP IP change** of Windows can break OCR/LLM URLs — pin reservation if possible.  
6. **~7GB Ubuntu archives** still on disk (hygiene).  
7. **Frontend API base** baked at build time.

---

## 14. Regression notes (testpsm 2026-07-10)

Bank: `C:\test psm.pdf` → 6 theory questions (EOC, adolescent, ANC×3, PNC).  
KB: Park hybrid ingest into `kb_psm`.

| Solve | Outcome |
|-------|---------|
| First | 5/6 needs_review (length, NPHCE, truncation) |
| After P0.5 bands/prompt | better content; false ReferenceConsistency fails |
| After ReferenceConsistency fix + NDD/NAHP/ICTC | **6/6 pass** |
| Token cut on Q6 | fixed by higher 5-mark max_out + clean incomplete bullets |
| solved-2 PDF | complete endings; multi-part depth; good exam-prep quality |

---

## 15. Release checklist (v1.3.2)

- [x] Code freeze on Ubuntu backend + Windows OCR  
- [x] `__version__ = "1.3.2"`  
- [x] PIPELINE_VERSIONS prompt 7 / validator 7  
- [x] FREEZE + CHANGELOG + HANDOVER updated  
- [x] API `GET /version` reports 1.3.2  
- [x] GitHub tag `v1.3.2` pushed  

### After freeze, operators should

1. `Start MedRack`  
2. Confirm preflight `ok=true`  
3. Prefer re-solve only when intentionally testing prompt/validator bumps  

---

## 16. Glossary

| Term | Meaning |
|------|---------|
| Hybrid OCR | Windows RapidOCR (+ auto Marker) → clean text PDF → Ubuntu index |
| EOC / EmOC | Essential / Emergency Obstetric Care |
| needs_review | Validation had ≥1 FAIL rule |
| GPU exclusive | Jobs that must not overlap (OCR stops model) |
| P2 | Overnight ordered book ingest campaign |
| kb_psm | Chroma collection for subject psm |

---

*End of FREEZE v1.3.2. Update this file on every behaviour-changing release.*
