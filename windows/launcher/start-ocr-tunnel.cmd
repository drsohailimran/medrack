@echo off
title MedRack OCR Tunnel (permanent)
setlocal EnableExtensions

set KEY=%USERPROFILE%\.ssh\medrack_ed25519
set REMOTE=sohail@192.168.29.82
set RPORT=18090
set LPORT=8090
set LOCK=%TEMP%\medrack-ocr-tunnel.lock

rem --- Single instance: if another tunnel script holds the lock, exit ---
if exist "%LOCK%" (
  for /f "usebackq delims=" %%p in ("%LOCK%") do set OLD=%%p
  if defined OLD (
    tasklist /FI "PID eq %OLD%" 2>nul | findstr /I "%OLD%" >nul
    if not errorlevel 1 (
      echo [%date% %time%] Another tunnel already running PID %OLD%. Exiting.
      exit /b 0
    )
  )
)
echo %~nx0 > "%LOCK%" 2>nul
rem store our PID via powershell (cmd has no reliable $$)
for /f %%i in ('powershell -NoProfile -Command "$p=(Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.ProcessId -eq $PID -or $_.ParentProcessId -eq $PID } | Select-Object -First 1).ProcessId; if (-not $p) { $p=$PID }; $p"') do set MYPID=%%i
if not defined MYPID set MYPID=%RANDOM%
echo %MYPID%> "%LOCK%"

:loop
rem If OCR agent is down, wait (no point tunneling to a dead port)
curl.exe -sS --max-time 2 http://127.0.0.1:%LPORT%/v1/health >nul 2>&1
if errorlevel 1 (
  echo [%date% %time%] OCR agent not on :%LPORT% yet. Waiting 10s...
  timeout /t 10 /nobreak >nul
  goto loop
)

rem Free stale remote listener so -R can bind (harmless if free)
ssh.exe -i "%KEY%" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new %REMOTE% "fuser -k %RPORT%/tcp 2>/dev/null; pkill -u sohail -f 'sshd-session: sohail@notty' 2>/dev/null; true" >nul 2>&1
timeout /t 1 /nobreak >nul

echo [%date% %time%] Connecting reverse tunnel %RPORT% -^> 127.0.0.1:%LPORT% ...
ssh.exe -i "%KEY%" -N ^
  -o BatchMode=yes ^
  -o ExitOnForwardFailure=yes ^
  -o ServerAliveInterval=20 ^
  -o ServerAliveCountMax=3 ^
  -o StrictHostKeyChecking=accept-new ^
  -R %RPORT%:127.0.0.1:%LPORT% ^
  %REMOTE%

set EC=%ERRORLEVEL%
echo [%date% %time%] Tunnel dropped (exit %EC%). Cleaning remote port, retry in 8s...

rem On failure "port already used", free remote port before retry
ssh.exe -i "%KEY%" -o BatchMode=yes -o ConnectTimeout=8 %REMOTE% "fuser -k %RPORT%/tcp 2>/dev/null; pkill -u sohail -f 'sshd-session: sohail@notty' 2>/dev/null; true" >nul 2>&1

timeout /t 8 /nobreak >nul
goto loop
