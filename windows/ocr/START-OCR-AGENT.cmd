@echo off
title MedRack OCR Agent (auto with Start MedRack)
cd /d C:\medrack-ocr
set PYTHONPATH=C:\medrack-ocr
set MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
set MEDRACK_OCR_TOKEN=medrack-ocr
set MEDRACK_OCR_PULL=1
echo MedRack OCR Agent — port 8090 + Ubuntu pull loop
echo Keep this minimized window open while using Hybrid OCR ingest.
"C:\medrack-ocr\venv\Scripts\python.exe" "C:\medrack-ocr\ocr_agent_server.py"
if errorlevel 1 pause
