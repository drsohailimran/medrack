@echo off
REM ============================================================
REM   Authorize this PC's SSH key on the MedRack server.
REM   Double-click this once. Type the server password when asked.
REM   The window stays open so you can read the result.
REM ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0authorize-server.ps1"
echo.
pause
