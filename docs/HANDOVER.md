# MedRack — Handover (v1.3.2)

**Audience:** Engineer or AI with no prior context.  
**Deep freeze / LLM encyclopedia:** **`FREEZE_v1.3.2.md`** (read that for troubleshooting and feature work).  
**Date:** 2026-07-10 · **Owner:** Sohail Imran  

---

## What it is

Local RAG for **MBBS exam answers** from **ingested textbooks** + **question banks**.  
Generation: **Qwopus** on Windows `:8080`. API/UI/Chroma: **Ubuntu** `:8010` / `:3010`.  
Scans: **Windows hybrid OCR** `:8090` (RapidOCR + auto Marker).

---

## Machines

| Role | IP | Ports |
|------|-----|-------|
| Ubuntu | 192.168.29.82 | 8010 API, 3010 UI, 18090 OCR tunnel |
| Windows | 192.168.29.89 | 8080 model, 8090 OCR |

Paths: Windows **`C:\Medrack\`** only · Ubuntu **`/home/sohail/medrack`** + data **`/home/sohail/medrack-data`**.

---

## Start / stop

- **Start:** `C:\Medrack\Start MedRack.lnk`  
- **Stop:** `C:\Medrack\Stop MedRack.lnk` (OCR link stays up)  
- Health: `GET http://192.168.29.82:8010/api/v1/system/preflight`  
- Version: `GET …/version` → **1.3.2**, prompt **7**, validator **7**

---

## Reliability suite (1.3.1+)

- Jobs → `$MEDRACK_HOME/jobs.sqlite`  
- GPU lock: hybrid OCR / extract_bank / solve_bank exclusive  
- Disk + subject preflight; bank + book verify  
- Stop Qwopus before OCR (elevated `schtasks /End` + stop flag + RAM free)  
- OCR agent/tunnel **hidden**; Qwopus console **visible** (white text)

---

## Common pitfalls

| Issue | Fix |
|-------|-----|
| OCR + model together crash PC | Agent must stop model first (1.3.1+) |
| Bank upload 0 questions | Hybrid auto-skipped on text PDFs (1.3.2) |
| All answers “duplicate chunk refs” | Validator 7 — fixed false positive |
| Incomplete last bullet | Token budget + clean_answer_text (1.3.2) |
| Tunnel spam port busy | `FIX-OCR-TUNNEL.cmd` |

---

## P2 overnight

`C:\Medrack\p2-inbox\` + `ORDER.md` + `run-p2-overnight.ps1`.  
**Do not start** until owner says **P2 ready**. Skip-on-fail.

---

## GitHub

https://github.com/drsohailimran/medrack · tag **`v1.3.2`**

For full architecture, API list, code map, and how to extend: open **`FREEZE_v1.3.2.md`**.
