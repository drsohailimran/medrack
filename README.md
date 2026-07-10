# MedRack

**Release: v1.3.0 FREEZE** (2026-07-10)

Local-first MBBS exam answer RAG for Sohail & family.  
Ubuntu API/UI + Windows Qwopus + hybrid OCR agent on LAN.

### Freeze includes
- P0 bulletproof answers (`prompt:6`, `validator:5`)
- Hybrid OCR for **textbooks and question banks** (scanned PDFs)
- Auto Marker page detection
- Stop generation + keep/delete review; live LLM indicator
- Book delete / **clear-all** + Chroma purge
- Permanent Ubuntu↔Windows link (LAN primary + SSH tunnel backup + watchdog)
- Windows single root: `C:\Medrack`
- Full operator doc: [`docs/HANDOVER.md`](docs/HANDOVER.md)

### Deferred
- P2 mass multi-subject book campaigns (owner-driven)
- True per-page Marker alignment residual

### Quick layout
```
backend/          FastAPI + RAG
frontend/         TanStack UI
docs/             HANDOVER, PHASES, troubleshooting
windows/launcher  Start/Stop + permanent link
windows/ocr       Hybrid OCR agent sources
```

### Production
- UI: `http://<ubuntu>:3010`
- API: `http://<ubuntu>:8010/api/v1`
- Qwopus: Windows `:8080`
- OCR agent: Windows `:8090` (Ubuntu also has tunnel `:18090`)

---

