@echo off
title MedRack OCR Tunnel
set KEY=%USERPROFILE%\.ssh\medrack_ed25519
:loop
ssh.exe -i "%KEY%" -N -o BatchMode=yes -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -R 18090:127.0.0.1:8090 sohail@192.168.29.82
echo Tunnel dropped, retrying in 3s...
timeout /t 3 /nobreak >nul
goto loop
