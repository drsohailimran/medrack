# MedRack — single workspace map

**Last verified:** 2026-07-10

## Read first (in order)

1. `C:\Medrack\docs\PHASES.md` — status + what to do next  
2. `C:\Medrack\docs\TROUBLESHOOTING.md` — when something breaks  
3. `C:\Medrack\docs\MEDRACK_FULL_SYSTEM_HANDOFF.md` — full system context  
4. `C:\medrack-ocr\README.md` — hybrid OCR agent  

Ubuntu mirrors: `/home/sohail/medrack/docs/`, `/home/sohail/medrack-data/`.

## Phase status

| Phase | Status |
|-------|--------|
| **P0** Bulletproof answers | **COMPLETE — APPROVED** (2026-07-09) |
| **P1** Hybrid OCR ingest | **COMPLETE — APPROVED** (2026-07-10; may revisit) |
| **P2** Multi-subject book ingest | **DEFERRED** — owner will ingest later |
| P3 UX (stop-gen + LLM indicator) | **COMPLETE — APPROVED** (2026-07-10) |
| P4 Housekeeping | **COMPLETE — APPROVED** (v1.1.0, 2026-07-10) |

## Canonical paths

| Role | Path |
|------|------|
| Windows workspace | `C:\Medrack` |
| Launcher | `C:\Medrack\launcher\` |
| OCR agent | `C:\medrack-ocr\` |
| Ubuntu app | `/home/sohail/medrack` (v1.0.0) |
| Ubuntu data | `/home/sohail/medrack-data` |
| UI | http://192.168.29.82:3010 |
| API | http://192.168.29.82:8010/api/v1 |
| Model (Windows) | :8080 |
| OCR agent (Windows) | :8090 |
| OCR tunnel (on Ubuntu) | `http://127.0.0.1:18090` |

## Daily use

1. **Start MedRack** (model + Ubuntu + OCR agent + tunnel)  
2. Browser → UI  
3. Hybrid book: **Books** → Hybrid OCR → upload  
4. **Stop MedRack** when done  

## Archives (not the app)

- `C:\Medrack\archive\`  
- `/home/sohail/medrack-ARCHIVE-20260709/`  
- `/home/sohail/.hermes/medrack/` (stub only)  
