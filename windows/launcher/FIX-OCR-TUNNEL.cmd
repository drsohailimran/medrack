@echo off
title Fix MedRack OCR tunnel (port 18090)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix-ocr-tunnel.ps1"
