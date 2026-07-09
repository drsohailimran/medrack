# MedRack Windows OCR agent (P1 — APPROVED 2026-07-10)

Hybrid OCR for scanned textbooks, integrated with the **single MedRack UI**.  
Troubleshooting: `C:\Medrack\docs\TROUBLESHOOTING.md` and `docs/PHASES.md` §P1.

## Day-to-day (recommended)

1. Double-click **Start MedRack**  
   - Starts Qwopus, Ubuntu stack, **this OCR agent** (minimized), and an **SSH reverse tunnel** so Ubuntu can reach the agent.  
2. In the browser: **Books** → Hybrid OCR (on) → upload PDF → **Upload · OCR · ingest**  
3. One click does: **stop Qwopus → RapidOCR → validate → text PDF → start Qwopus → index**  

**Stop MedRack** stops the model, OCR agent, and tunnel.

You should **not** need a separate OCR window if Start MedRack is used.

## Manual agent start (if needed)

```
C:\medrack-ocr\START-OCR-AGENT.cmd
```

Keep that window open. Start MedRack still provides the reverse tunnel.

## Connectivity note

Ubuntu often **cannot** open Windows LAN port `8090` even with a firewall allow rule.  
Reliable path: reverse tunnel created by Start MedRack:

- Windows agent listens on `0.0.0.0:8090`  
- Ubuntu uses `MEDRACK_OCR_AGENT_URL=http://127.0.0.1:18090`  

Optional one-time admin firewall (may still not fix LAN access):

```
C:\medrack-ocr\OPEN-FIREWALL-ONCE.cmd
```

## Pipeline

1. Stop Qwopus (`qwopus.stop` + kill llama-server)  
2. RapidOCR full book (resumable page cache under `jobs/<id>/work/rapidocr_cache`)  
3. Optional Marker on table ranges  
4. **Validate** (nonempty page ratio / avg chars)  
5. Build full text PDF (`pipeline/build_text_pdf.py` — no 50×80 truncation)  
6. Start Qwopus (scheduled task / bat)  

## Layout

```
C:\medrack-ocr\
  START-OCR-AGENT.cmd      # agent (push + pull)
  START-OCR-WORKER.cmd     # legacy pull-only worker (optional)
  OPEN-FIREWALL-ONCE.cmd   # optional admin firewall
  ocr_agent_server.py
  ocr_pull_worker.py
  pipeline\
    hybrid_ocr.py
    build_text_pdf.py
    model_control.py
  venv\
  README.md
```

## Env

| Side | Variable | Value |
|------|----------|--------|
| Ubuntu `.env` | `MEDRACK_OCR_AGENT_URL` | `http://127.0.0.1:18090` |
| Ubuntu `.env` | `MEDRACK_OCR_AGENT_TOKEN` | `medrack-ocr` |
| Windows agent | `MEDRACK_API_BASE` | `http://192.168.29.82:8010/api/v1` |
| Windows agent | `MEDRACK_OCR_TOKEN` | `medrack-ocr` |

Full phase notes: `C:\Medrack\docs\PHASES.md` §P1.
