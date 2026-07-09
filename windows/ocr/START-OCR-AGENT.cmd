@echo off
title MedRack OCR Agent
cd /d C:\Medrack\ocr
set PYTHONPATH=C:\Medrack\ocr
set MEDRACK_API_BASE=http://192.168.29.82:8010/api/v1
set MEDRACK_OCR_TOKEN=medrack-ocr
set MEDRACK_OCR_PULL=1
echo MedRack OCR Agent ? port 8090
"C:\Medrack\ocr\venv\Scripts\python.exe" "C:\Medrack\ocr\ocr_agent_server.py"
if errorlevel 1 pause
