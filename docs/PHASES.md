# MedRack — Phase checklist (single source of progress)

**Rule:** One phase at a time. **Verify → document completion → document next → wait for owner approval.**  
Do **not** start Pn+1 until the owner explicitly approves Pn.

**Full context:** `HANDOVER.md` (primary) · `MEDRACK_FULL_SYSTEM_HANDOFF.md`  
**Priority:** answer quality > overnight stability > speed  
**Canonical app:** `/home/sohail/medrack` (**v1.3.0 FREEZE**) · **Data:** `/home/sohail/medrack-data`  
**Windows:** `C:\Medrack\` only  

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
| P1 | Hybrid OCR ingest (books) | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |
| P2 | Multi-subject content (book ingest) | **DEFERRED** — owner-driven | No |
| P3 | UX: stop-gen + LLM indicator | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |
| P4 | Housekeeping | **COMPLETE — APPROVED** | **Yes (2026-07-10)** |
| — | **v1.3.0 product freeze** | **FROZEN** | **Yes (2026-07-10)** |

---

## Freeze record — v1.3.0 (2026-07-10)

**Owner request:** finalise and freeze the build; docs current; push GitHub.

### Included in freeze

| Area | Status |
|------|--------|
| Answer pipeline P0 (`prompt:6`, `validator:5`) | Frozen |
| Hybrid OCR textbooks + **question banks** | Frozen |
| Auto Marker page detect (any book/bank) | Frozen |
| Stop generation + keep/delete review | Frozen |
| Live LLM indicator | Frozen |
| Book delete (filesystem + manifest) + **Delete all** / purge Chroma | Frozen |
| Permanent Ubuntu↔Windows LAN link (direct + tunnel + watchdog) | Frozen |
| Windows single folder `C:\Medrack` | Frozen |
| HANDOVER.md for zero-context AIs | Frozen |

### Residual / deferred (not blockers)

- P2 mass multi-subject textbook campaigns (owner runs hybrid when ready)
- True per-page Marker char-split residual on multi-page ranges
- Optional denser Park’s re-chunk
- Mild 5-mark length edge cases (accepted at P0)

### Verification at freeze

- API `package_version` **1.3.0**
- Hybrid book OCR E2E + auto Marker
- Library clear-all empties books list
- Permanent tasks: OCR Agent, OCR Tunnel, Link Watchdog
- GitHub tag **v1.3.0**

---

## Decision log (summary)

| Date | Decision |
|------|----------|
| 2026-07-09 | Single workspace; phase gate |
| 2026-07-09 | P0 COMPLETE — APPROVED |
| 2026-07-10 | P1 COMPLETE — APPROVED; P2 deferred |
| 2026-07-10 | P3 COMPLETE — APPROVED |
| 2026-07-10 | P4 COMPLETE — APPROVED; v1.1.0 / v1.2.0 releases |
| 2026-07-10 | Hybrid OCR for question banks; book delete fix; permanent LAN link |
| 2026-07-10 | **v1.3.0 FREEZE** — finalise, document, push |

---

*Mirror: Ubuntu `/home/sohail/medrack/docs/PHASES.md` and `/home/sohail/medrack-data/PHASES.md`.*
