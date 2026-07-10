# MedRack — Change log, verification layer, and project audit

**Date:** 2026-07-10  
**Live version:** **1.3.1** (API) · GitHub tag `v1.3.1`  
**Windows root:** `C:\Medrack`  
**Ubuntu app:** `/home/sohail/medrack` · **Data:** `/home/sohail/medrack-data`  

This document captures:

1. **Everything implemented** in the recent arc (including reliability suite)  
2. **What can be improved**  
3. **Potential failure points** (for overnight P2 and day-to-day ops)  

Primary operator doc remains **`HANDOVER.md`**. This file is the deep audit trail.

---

## 1. Changes delivered (chronological summary)

### 1.1 Product phases (approved)

| Phase | What shipped |
|-------|----------------|
| **P0** | Scope/grounding/length prompt; validators; stale cache / `kb_revision`; regression pack; live answer quality iteration |
| **P1** | Hybrid OCR for textbooks: Windows agent (RapidOCR + optional Marker), reverse tunnel, one-click Books UI |
| **P2** | Content campaign (owner-driven). **Scheduled for tonight** — not a new engine; uses hybrid ingest in order |
| **P3** | Mid-batch stop (`POST /jobs/{id}/cancel`); keep/delete review; live LLM indicator (`GET /llm/status`) |
| **P4** | Single workspace, GitHub sync, housekeeping, freeze discipline |

### 1.2 Post-freeze / freeze-adjacent work (v1.2 → v1.3.0)

| Change | Why |
|--------|-----|
| **Auto Marker page detect** | Any textbook/bank: score RapidOCR pages → Marker only on table-like ranges (capped) |
| **Hybrid OCR for question banks** | Scanned question papers get same Windows OCR then extract |
| **Book delete fix** | Filesystem-only rows (“not indexed”) could not be deleted before |
| **Delete all books** | `POST /library/books/clear-all` + UI button; purges `kb_*` Chroma |
| **Permanent Ubuntu↔Windows link** | LAN `:8090` primary; SSH tunnel `:18090` backup; scheduled tasks + watchdog |
| **Windows single folder** | Canonical `C:\Medrack\` (launcher, ocr, docs, p2-inbox) |
| **Post-ingest verification gate** | Hard-fail job if index/manifest/Chroma/retrieval checks fail |
| **P2 overnight kit** | `C:\Medrack\p2-inbox\`, ORDER format, skip-on-fail runner, policy docs |
| **HANDOVER.md** | Zero-context ops document for other AIs |

### 1.3 Reliability suite (v1.3.1) — audit improvements + failure fixes

| Change | Failure fixed | Detail |
|--------|---------------|--------|
| **SQLite job store** | C3 API restart loses jobs | Jobs under `$MEDRACK_HOME/jobs.sqlite`; restart marks pending/running as `interrupted_by_api_restart` |
| **GPU exclusive lock** | H2 OCR stops Qwopus mid-solve | `hybrid_ingest_book` / `extract_bank` / `solve_bank` cannot overlap |
| **Disk preflight** | C4 disk full mid-night | ≥5 GB free before book ingest; ≥3 GB before bank extract; P2 rechecks each book |
| **Subject validation** | H5 wrong `kb_*` | Upload returns `400 INVALID_SUBJECT` before job starts |
| **Text gibberish scoring** | C7 garbage OCR passes | Book verify + bank verify sample text quality; OCR agent validates mean gibberish |
| **Bank extract verify** | Silent empty/broken banks | `verify_question_bank` after extract; hard-fail empty/weak stems |
| **System preflight API** | Ops guesswork | `GET /system/preflight` → disk + OCR + LLM + GPU lock + `ready_for_p2` |
| **Jobs list API** | Overnight blind | `GET /jobs` recent history from SQLite |
| **P2 sleep prevent** | C5 Windows sleep | `powercfg` AC standby/hibernate = 0 for run |
| **P2 skip-on-fail** | One book kills night | Already policy; runner hardened with preflight + report |
| **Marker page distribution** | M1 char-split tables | Paragraph-aware proportional split weighted by RapidOCR page lengths; form-feed aware |

### 1.4 Answer / pipeline versions (locked)

| Component | Version |
|-----------|---------|
| Package | **1.3.1** |
| Prompt | **6** |
| Validator | **5** |
| Schema | **3** |

---

## 2. Post-ingest verification layer (detail)

### 2.1 When it runs

- Automatically at the end of **`run_ingest_book`** (also used by hybrid book ingest).  
- If verification hard-fails → job status **`error`** (not “done”).  
- Manual: `GET /api/v1/library/books/{book_id}/verify`  
- Banks: auto after extract; manual `GET /api/v1/library/question-banks/{name}/verify`

### 2.2 What it checks (books)

| Check | Hard fail? | Notes |
|-------|------------|--------|
| Active **manifest** entry for `book_id` | **Yes** | Must not be archived-only |
| **Subject** consistent | **Yes** if expected subject passed |
| **Pages** > 0 | **Yes** | |
| **Chunks** (manifest) ≥ 1 | **Yes** | |
| **Chroma** chunk count for `book_id` ≥ 1 | **Yes** | Vectors actually stored |
| Chroma vs manifest / expected count | Soft | Large mismatch → warning |
| **Chunk density** (chunks/page) for long books | Soft | Very low → bad OCR/chunking |
| **Source PDF** still on disk | Soft | |
| **Sample retrieval** on subject collection | Soft / hard | Empty collection is bad |
| OCR suspect page ratio | Soft | High % → warning |
| **Text quality / gibberish** | Hard if mean ≥ 0.85 | Samples Chroma documents |

### 2.3 Bank verification

| Check | Hard fail? |
|-------|------------|
| Bank exists | Yes |
| `question_count` ≥ min | Yes |
| Empty stems | Hard if majority empty |
| Avg stem length | Hard if avg < 10 |
| Stem gibberish | Soft warning |

### 2.4 P2 overnight policy (owner-confirmed)

- **If one book fails → skip → next book**  
- Failures logged in `p2-report.md` / `p2-report.json`  
- Successful PDFs → `p2-inbox/done/`  
- Failed copies → `p2-inbox/failed/`  
- Do **not** start until owner says **P2 ready** with PDFs + `ORDER.md`

### 2.5 What verification does *not* guarantee

- Medical correctness of textbook OCR (only structural + gibberish heuristics)  
- Perfect Marker table fidelity (improved, not perfect)  
- Answer quality for every exam question  
- Automatic resume of interrupted mid-book OCR (job marked error; re-run that line)  
- That Qwopus is free during OCR (lock serializes; answers wait)

---

## 3. Architecture map (quick)

```
Windows PC (192.168.29.89)
  Qwopus :8080
  OCR agent :8090  (RapidOCR + auto Marker + gibberish gate)
  Permanent tasks: OCR Agent, OCR Tunnel, Link Watchdog
  Reverse tunnel → Ubuntu 127.0.0.1:18090

Ubuntu (192.168.29.82)
  FastAPI :8010  (medrack package 1.3.1)
  UI :3010
  Chroma under medrack-data/index/chroma
  jobs.sqlite under medrack-data/
  Dual OCR URLs: LAN 8090 then tunnel 18090
```

---

## 4. Potential points of failure (ranked) — after v1.3.1

### 4.1 Critical

| # | Failure | Mitigation now | Residual |
|---|---------|----------------|----------|
| C1 | OCR agent down | Scheduled task + watchdog; preflight fails | Needs logon/session |
| C2 | Qwopus down | Start MedRack; preflight fails | Long load / VRAM |
| C3 | Ubuntu API restart | SQLite job history; interrupted jobs marked error | **No auto-resume** of mid-OCR work — re-run failed ORDER line |
| C4 | Disk full | Preflight + per-book recheck | Very large books near limit |
| C5 | Windows sleep | P2 runner sets powercfg AC timeouts to 0 | User may re-enable sleep later |
| C6 | LAN IP change | Config + dual OCR URLs | DHCP reassignment |
| C7 | Bad / empty OCR | Verify + gibberish hard-fail | Edge medical text can still be “readable noise” |

### 4.2 High

| # | Failure | Mitigation now | Residual |
|---|---------|----------------|----------|
| H1 | Tunnel 18090 busy | FIX-OCR-TUNNEL; LAN primary | Multi-instance spam |
| H2 | Hybrid stops Qwopus mid-solve | **GPU exclusive lock** | Single-question generate during OCR still possible (sync path) |
| H3 | Concurrent ingest | Sequential P2 + GPU lock | Manual parallel UI uploads queue on lock |
| H4 | LLM extract weak on banks | Hybrid OCR first + bank verify | Prompt limits |
| H5 | Subject mis-tagged | **Validate at upload** | User can still pick wrong valid subject |
| H6 | Firewall | Permanent link install | Rare profile flips |

### 4.3 Medium / low

| # | Issue | Status |
|---|--------|--------|
| M1 | Marker multi-page char-split | **Improved** proportional + paragraph cuts |
| M2 | 5-mark length edges | P0 residual accepted |
| M3 | Frontend API base at build | Rebuild if IP changes |
| L1–L4 | Legacy paths, archives | Prefer `C:\Medrack` only |

---

## 5. Remaining optional improvements (not blocking P2)

1. True per-page Marker runs for every table page (slower, highest fidelity)  
2. Full job resume (continue OCR cache mid-book after API death) — RapidOCR cache already helps on re-run  
3. P2 progress dashboard in UI  
4. Subject auto-detect from title/filename  
5. Email/Telegram notify on P2 complete  
6. Pin Windows LAN IP via DHCP reservation  

---

## 6. Pre-flight checklist (before P2 tonight)

- [ ] `Start MedRack` left running; PC **not** sleeping  
- [ ] `GET http://192.168.29.82:8010/api/v1/system/preflight` → `ok=true`, `ready_for_p2=true`  
- [ ] `GET .../version` → **1.3.1**  
- [ ] Books list empty or intentional state  
- [ ] PDFs + `ORDER.md` in `C:\Medrack\p2-inbox\`  
- [ ] Policy: **skip on fail** confirmed  
- [ ] Owner message: **P2 ready**  

---

## 7. API cheat sheet (reliability)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/library/books/upload` | `hybrid_ocr`, `use_marker`, `replace`; subject validated |
| POST | `/library/books/clear-all` | Wipe books + purge Chroma |
| GET | `/library/books/{id}/verify` | Manual ingest verification |
| GET | `/library/question-banks/{name}/verify` | Bank verification |
| POST | `/library/question-banks/upload` | `hybrid_ocr`, `use_marker` |
| GET | `/jobs` | Recent jobs (SQLite) |
| GET | `/jobs/{id}` | Job status (memory + SQLite) |
| POST | `/jobs/{id}/cancel` | Cooperative cancel |
| GET | `/system/preflight` | Disk + OCR + LLM + GPU lock |
| GET | `/llm/status` | Live model indicator |

---

## 8. File map

| Piece | Path |
|-------|------|
| Job store + GPU lock | `backend/medrack/dashboard/jobs.py` |
| Preflight / gibberish | `backend/medrack/dashboard/services/preflight.py` |
| Verify book/bank | `backend/medrack/dashboard/services/library.py` |
| Ingest + bank verify | `backend/medrack/dashboard/services/tasks.py` |
| API endpoints | `backend/medrack/dashboard/api/v1.py` |
| Hybrid OCR + Marker split | `C:\Medrack\ocr\pipeline\hybrid_ocr.py` |
| P2 runner | `C:\Medrack\p2-inbox\run-p2-overnight.ps1` |

---

## 9. Bottom line

| Question | Answer |
|----------|--------|
| Are audit reliability fixes shipped? | **Yes — v1.3.1** |
| Is verification real? | **Yes** — structural + gibberish gates |
| Can one bad book kill P2 night? | **No** (skip and continue) |
| Can API restart mid-job recover? | Status **persists** as error; **re-run** that ORDER line |
| #1 overnight risk remaining | Sleep / agent dead / disk / bad PDF content |

---

*Update this file when verification rules or P2 policy change. Mirror to Ubuntu `docs/` when releasing.*
