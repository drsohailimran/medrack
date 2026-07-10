@echo off
title MedRack — Install Permanent Ubuntu Link
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-permanent-link.ps1"
