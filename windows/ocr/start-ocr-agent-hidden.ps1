# MedRack OCR agent — NO console window.
# Scheduled Task / launcher run this with: powershell -WindowStyle Hidden -File ...
# This process STAYS ALIVE (waits on python) so Task Scheduler tracks it correctly.
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'venv\Scripts\python.exe'
$Script = Join-Path $Root 'ocr_agent_server.py'
$OutLog = Join-Path $Root 'agent.out.log'
$ErrLog = Join-Path $Root 'agent.err.log'

if (-not (Test-Path -LiteralPath $Python) -or -not (Test-Path -LiteralPath $Script)) {
    Add-Content -Path $ErrLog -Value ("[{0}] missing python or script under {1}" -f (Get-Date -Format o), $Root)
    exit 1
}

# If already healthy on 8090, exit (avoid duplicate)
try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/v1/health' -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { exit 0 }
} catch {}

# Kill stale listeners on 8090 (orphaned previous runs)
try {
    Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
} catch {}
Start-Sleep -Milliseconds 400

$env:PYTHONPATH = $Root
if (-not $env:MEDRACK_API_BASE) { $env:MEDRACK_API_BASE = 'http://192.168.29.82:8010/api/v1' }
if (-not $env:MEDRACK_OCR_TOKEN) { $env:MEDRACK_OCR_TOKEN = 'medrack-ocr' }
if (-not $env:MEDRACK_OCR_PULL) { $env:MEDRACK_OCR_PULL = '1' }

foreach ($log in @($OutLog, $ErrLog)) {
    if ((Test-Path $log) -and ((Get-Item $log).Length -gt 8MB)) {
        Move-Item -LiteralPath $log -Destination ($log + '.old') -Force -ErrorAction SilentlyContinue
    }
}

Add-Content -Path $OutLog -Value ("`n[{0}] agent starting (hidden)" -f (Get-Date -Format o)) -Encoding UTF8

# -WindowStyle Hidden + no shell window; -Wait keeps this task alive
$p = Start-Process -FilePath $Python `
    -ArgumentList "`"$Script`"" `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru `
    -Wait

exit $(if ($p) { $p.ExitCode } else { 1 })
