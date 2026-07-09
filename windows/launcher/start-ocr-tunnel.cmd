@echo off
title MedRack OCR Tunnel (permanent)
set KEY=%USERPROFILE%\.ssh\medrack_ed25519
set REMOTE=sohail@192.168.29.82
set RPORT=18090
set LPORT=8090
:loop
echo [%date% %time%] Connecting reverse tunnel %RPORT% -> 127.0.0.1:%LPORT% ...
ssh.exe -i "%KEY%" -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new -R %RPORT%:127.0.0.1:%LPORT% %REMOTE%
echo [%date% %time%] Tunnel dropped (exit %ERRORLEVEL%). Reconnecting in 5s...
timeout /t 5 /nobreak >nul
goto loop
