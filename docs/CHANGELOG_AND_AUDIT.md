# MedRack — Change log and audit

**Live version:** **1.3.3** · GitHub tag `v1.3.3`  
**Date:** 2026-07-20  
**Windows:** `C:\Medrack` · **Ubuntu:** `/home/sohail/medrack` · **Data:** `/home/sohail/medrack-data`

Primary deep freeze doc: **`FREEZE_v1.3.2.md`** (use for LLM troubleshooting / feature work).  
Ops short form: **`HANDOVER.md`**.

---

## v1.3.3 (2026-07-20) — FMT ingest fix + vector-store dedup

### Book ingest
- **Auto-skip hybrid OCR on text-layer PDFs.** `run_hybrid_ingest_book` now
  detects a native text layer via `_pdf_native_text_stats()` and ingests the
  text directly instead of force-OCRing, mirroring the question-bank auto-skip.
  Fixes *Essentials of Forensic Medicine* (KS Narayan Reddy) failing every
  hybrid ingest with `OCR quality failed: nonempty=53% (need >=85%)` — the book
  is a clean digital PDF that never needed OCR.
- **`replace` no longer orphans/duplicates vectors.** `run_ingest_book`'s
  replace path now purges the old book's Chroma chunks (`delete_book_chunks`)
  and archives **every** active manifest record for the sha via `list_books`
  (not `get_book`, whose first match could be an archived record ordered ahead
  of the live one). Prevents `kb_<subject>` accumulating duplicate chunks on
  re-ingest and the spurious `Book with sha256 ... already indexed` failure.

### Verification
- FMT re-ingested clean: **717/717 pages** covered, **1059 chunks**, **0
  duplicate texts**; retrieval hits correct chapters/pages. KB source is
  byte-identical to the supplied PDF (SHA-256 match).

### Notes
- Ingest-path only — `PIPELINE_VERSIONS` unchanged (no answer-cache impact).

---

## v1.3.2 (2026-07-10) — Quality freeze

### Reliability (from 1.3.1)

- SQLite job store; GPU exclusive lock; disk/subject preflight; system preflight API  
- Book + bank post-job verification; gibberish scoring  
- P2 skip-on-fail runner + sleep prevent  

### OCR / model control

- **Elevated Qwopus stop:** stop flag + `schtasks /End` before OCR (fixes Access denied)  
- Hard-fail hybrid if model not free; wait RAM/GPU free  
- OCR agent + tunnel run **hidden** (no desktop clutter)  
- Qwopus console restored with **live white text** (no stdout-only redirect)  
- Hybrid OCR: better Marker page distribute; OCR gibberish gate  

### Question banks

- **Auto-skip hybrid OCR** when PDF has native text layer (fixes 0-question extract)  
- Fallback to original PDF if hybrid yields 0 questions  
- Section marks from headers (10 Marks / 5 marks)  

### Answer quality (prompt 7 / validator 7)

- Multi-part 10-mark prompt (balanced sections, depth floor)  
- Length bands: 5-mark ~240–457; 10-mark ~525–840  
- `_clean_answer_text`: strip incomplete last bullets (token cut-off)  
- Higher 5-mark token headroom so last bullet can finish  
- ReferenceConsistency: **only explicit chunk cites** (no false FAIL on “pregnancy”)  
- Grounding allowlist: NDD, NAHP, ICTC, RKSK family  
- Retrieval query boost for adolescent / ANC / PNC / EOC stems  

### Docs

- **`FREEZE_v1.3.2.md`** thorough LLM-oriented freeze  
- HANDOVER / TROUBLESHOOTING updated  

---

## v1.3.0 – v1.3.1 (summary)

- Auto Marker page detect; hybrid for banks; clear-all books; permanent LAN link  
- Post-ingest verification; P2 kit; HANDOVER  
- Reliability suite 1.3.1 (jobs.sqlite, GPU lock, preflight)  

---

## Failure points (ranked residual)

See FREEZE §13. Highest remaining risks: sleep during overnight, API kill mid-OCR, DHCP IP change, medical OCR “readable garbage”.

---

## API additions worth knowing

| Path | Purpose |
|------|---------|
| GET `/system/preflight` | disk + OCR + LLM + GPU |
| GET `/jobs` | recent jobs SQLite |
| GET `/library/books/{id}/verify` | book verify |
| GET `/library/question-banks/{name}/verify` | bank verify |
| POST `/library/books/clear-all` | wipe library |

---

*Mirror to Ubuntu `docs/` on release.*
