@echo off
title MedRack OCR Worker (legacy pull-only)
cd /d C:\Medrack\ocr
set PYTHONPATH=C:\Medrack\ocr
set MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
set MEDRACK_OCR_TOKEN=medrack-ocr
"C:\Medrack\ocr\venv\Scripts\python.exe" "C:\Medrack\ocr\ocr_pull_worker.py"
if errorlevel 1 pause
