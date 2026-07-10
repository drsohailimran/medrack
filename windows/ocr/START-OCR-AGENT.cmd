@echo off
REM Thin launcher — always starts the agent HIDDEN (no desktop console).
REM Scheduled Task / Start MedRack / watchdog all use this entry point.
cd /d C:\Medrack\ocr
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Medrack\ocr\start-ocr-agent-hidden.ps1"
exit /b %ERRORLEVEL%
