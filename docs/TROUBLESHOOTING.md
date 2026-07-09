# MedRack troubleshooting (for humans and AIs)

**Canonical app:** `/home/sohail/medrack` · **Data:** `/home/sohail/medrack-data`  
**Do not use:** `medrack-ARCHIVE-*`, `C:\Medrack\archive\`, `~/.hermes/medrack`  
**Phases:** `docs/PHASES.md` · **Full system:** `docs/MEDRACK_FULL_SYSTEM_HANDOFF.md`

---

## Quick health checks

| Check | Command / action |
|-------|------------------|
| Ubuntu API | `curl http://192.168.29.82:8010/api/v1/version` |
| Ubuntu UI | browser `http://192.168.29.82:3010` → “Backend online” |
| Windows model | `curl http://127.0.0.1:8080/health` (or from Ubuntu `192.168.29.89:8080`) |
| OCR agent (Windows) | `curl http://127.0.0.1:8090/v1/health` |
| OCR via tunnel (Ubuntu) | `curl http://127.0.0.1:18090/v1/health` |
| SSH Windows→Ubuntu | `ssh -i ~/.ssh/medrack_ed25519 sohail@192.168.29.82` |

If UI says **Backend offline**: frontend was built with wrong API base. Rebuild with  
`VITE_MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1` and `NITRO_PRESET=node-server`.

---

## Start / Stop

| Action | How |
|--------|-----|
| Full stack start | Desktop **Start MedRack** |
| Full stack stop | Desktop **Stop MedRack** |
| Ubuntu only | `bash /home/sohail/medrack/start_stack.sh` / `stop_stack.sh` |
| OCR agent only | `C:\medrack-ocr\START-OCR-AGENT.cmd` |
| OCR tunnel only | `ssh -i medrack_ed25519 -N -R 18090:127.0.0.1:8090 sohail@192.168.29.82` |

Start MedRack is supposed to start: model + Ubuntu + OCR agent + reverse tunnel.

---

## Hybrid OCR ingest

### Happy path

Books → Hybrid OCR on → upload PDF → progress shows stop model → OCR → validate → start model → index → book listed.

### Agent / tunnel down

1. Windows: is `:8090` up?  
2. Ubuntu: is `:18090` up?  
3. If only (1) works: restart tunnel / Start MedRack.  
4. Ubuntu `.env` must have `MEDRACK_OCR_AGENT_URL=http://127.0.0.1:18090`  
5. **Do not rely on** `http://192.168.29.89:8090` from Ubuntu (often times out).

### Job errors

| Message | Likely cause | Fix |
|---------|--------------|-----|
| OCR agent unreachable / timeout | Agent or tunnel down | Start MedRack |
| Hybrid OCR failed: OCR quality failed | Too many empty pages | Check scan quality; inspect agent `jobs\<id>\work\rapidocr_cache` |
| Timed out waiting for OCR worker | Pull mode, agent not running | Start agent; check `ocr_jobs/*/meta.json` |
| 0 chunks after ingest | Empty clean PDF | Re-OCR; verify text in `*_hybrid_ocr.pdf` |
| Model not answering after job | Qwopus failed to restart | Delete `C:\ai models\qwopus.stop`; Start MedRack |

### Logs / artifacts

| Location | Contents |
|----------|----------|
| `$MEDRACK_HOME/logs/api.log` | Ubuntu API |
| `$MEDRACK_HOME/ocr_jobs/<id>/` | Queued OCR jobs (source, meta, clean) |
| `$MEDRACK_HOME/books/*_hybrid_ocr.pdf` | Clean text PDFs |
| `C:\medrack-ocr\jobs\<id>\` | Windows-side job workdirs |
| `C:\ai models\qwopus-*.log` | Model server / watchdog |

### Tokens / secrets

- OCR agent token: `medrack-ocr` (Ubuntu `MEDRACK_OCR_AGENT_TOKEN` = Windows `MEDRACK_OCR_TOKEN`)  
- SSH key: `medrack_ed25519` (Windows user path has a **space**)

---

## Answer quality (P0)

| Issue | Notes |
|-------|--------|
| Invented schemes | Clean KB + grounding rules; re-ingest if garbage OCR |
| Length off | Targets 750/375/125; versions `prompt:6` `validator:5` |
| `needs_review` | Validation failed but answer still saved |
| Stale answers | Re-ingest bumps `kb_revision`; generate regenerates stale |

Live version: `GET /api/v1/version` → `pipeline_versions`.

---

## Phase gate (mandatory)

1. One phase at a time: P0 → P1 → P2 → P3 → P4  
2. Verify → document → wait for owner approval  
3. Do **not** start Pn+1 until owner approves Pn  

Current: **P0 and P1 approved.** Next: **P2** only after owner says start.
