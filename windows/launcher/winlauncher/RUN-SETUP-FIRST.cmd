@echo off
REM ============================================================
REM   MedRack launcher - ONE-TIME SETUP
REM   Just double-click this file.
REM   - Click "Yes" on the Windows security prompt.
REM   - Type the server password ONCE when asked.
REM   You only ever need to do this one time.
REM ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-medrack-launcher.ps1"
