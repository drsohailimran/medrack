@echo off
title MedRack OCR Pull Worker
cd /d C:\medrack-ocr
set PYTHONPATH=C:\medrack-ocr
set MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
set MEDRACK_OCR_TOKEN=medrack-ocr
echo.
echo  MedRack OCR Pull Worker
echo  Polls Ubuntu for hybrid-OCR jobs (no firewall hole needed).
echo  Keep this window open while using Hybrid OCR ingest in the UI.
echo.
"C:\medrack-ocr\venv\Scripts\python.exe" "C:\medrack-ocr\ocr_pull_worker.py"
pause
