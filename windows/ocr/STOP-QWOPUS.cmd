@echo off
REM Elevated-friendly Qwopus stop (flag first, then task end, then kill).
REM Called by model_control / manual FIX when hybrid OCR needs the GPU+RAM.
set "STOPFLAG=C:\ai models\qwopus.stop"
echo stop> "%STOPFLAG%"
schtasks /End /TN "MedRack Qwopus Server" >nul 2>&1
taskkill /F /T /IM llama-server.exe >nul 2>&1
exit /b 0
