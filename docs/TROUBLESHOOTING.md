# MedRack Troubleshooting (v1.3.2)

Full narrative and architecture: **`FREEZE_v1.3.2.md`**.

## Quick health

```text
curl http://192.168.29.82:8010/api/v1/version
curl http://192.168.29.82:8010/api/v1/system/preflight
curl http://192.168.29.89:8090/v1/health
curl http://192.168.29.89:8080/health
```

## Symptom table

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| System crash on hybrid ingest | Model + OCR concurrent | Update agent; stop uses `schtasks /End` + stop flag; wait RAM free |
| Qwopus keeps running during OCR | Access denied taskkill | Elevated End task; check `qwopus.stop` |
| Black empty Qwopus window | stdout fully redirected | `run-qwopus-medrack.bat` must print live to console |
| OCR cmd windows on desktop | Old launchers | `register-hidden-ocr-tasks.ps1`; hidden PS1 scripts |
| Bank verify question_count 0 | Hybrid OCR on text PDF | Auto-skip hybrid when text layer present; re-upload |
| needs_review: length | Strict ScopeLength | Bands v7; multi-part prompt; re-solve |
| needs_review: duplicate chunk refs | False positive rule | Validator 7 explicit cites only |
| Last answer ends mid-sentence | max_tokens cut | Higher 5-mark max_out + `_clean_answer_text` |
| Grounding fail real acronym (NDD, ICTC) | Not in allowlist | Add to `_GROUNDING_ALLOWLIST` in `validation/rules.py` |
| remote port forwarding failed | Dup tunnel | FIX-OCR-TUNNEL; kill extra ssh |
| Jobs lost after restart | Pre-SQLite | jobs.sqlite persists history; mid-job marked interrupted |
| LLM red in UI | Model loading/down | Wait load; Start MedRack; check :8080/health |
| Upload invalid subject | Typo | Use known subject list (psm, medicine, …) |

## Logs

- Ubuntu API: `/home/sohail/medrack-data/logs/api.log`  
- OCR: `C:\Medrack\ocr\agent.out.log`  
- Tunnel: `C:\Medrack\ocr\tunnel.out.log`  
- Model: `C:\ai models\qwopus-watchdog.log`  

## Restart pieces

- **API:** restart uvicorn on Ubuntu (see FREEZE §10)  
- **OCR agent:** `Start-ScheduledTask 'MedRack OCR Agent'`  
- **Model:** `Start-ScheduledTask 'MedRack Qwopus Server'` or Start MedRack  
