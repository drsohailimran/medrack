@echo off
REM Thin launcher — reverse tunnel runs HIDDEN (no desktop console).
cd /d C:\Medrack\launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Medrack\launcher\start-ocr-tunnel-hidden.ps1"
exit /b %ERRORLEVEL%
