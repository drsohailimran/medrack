# ============================================================
#  MedRack â€” permanent Ubuntu â†” Windows LAN link (ONE-TIME ADMIN)
#
#  Makes connectivity survive reboots and logons:
#    1. Firewall: allow Ubuntu â†’ this PC :8080 (model) and :8090 (OCR)
#    2. Scheduled Task: OCR agent always on (auto-restart)
#    3. Scheduled Task: SSH reverse tunnel backup (auto-reconnect loop)
#    4. Scheduled Task: link watchdog (every 5 min; starts agent if dead)
#
#  Double-click INSTALL-PERMANENT-LINK.cmd (UAC Yes).
# ============================================================

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host 'Requesting administrator rights...'
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
    )
    exit
}

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'medrack-config.ps1')
$cfg = $MedrackConfig

function Section([string]$t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function OK([string]$t)      { Write-Host "  [OK] $t" -ForegroundColor Green }
function Warn([string]$t)    { Write-Host "  [!!] $t" -ForegroundColor Yellow }

$ubuntu = $cfg.LinuxHost
$user = "$env:USERDOMAIN\$env:USERNAME"

Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  MedRack permanent LAN link setup' -ForegroundColor Cyan
Write-Host "  Ubuntu: $ubuntu  Windows: this PC" -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan

# ---------- Firewall ----------
Section 'Windows Firewall (Ubuntu can always reach model + OCR)'

# Remove old rules cleanly then recreate (idempotent)
@(
    'MedRack HTTP',
    'MedRack OCR Agent 8090',
    'MedRack Qwopus 8080',
    'MedRack LAN Model 8080',
    'MedRack LAN OCR 8090'
) | ForEach-Object {
    Get-NetFirewallRule -DisplayName $_ -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
}

# Allow from Ubuntu host specifically + general private LAN
New-NetFirewallRule -DisplayName 'MedRack LAN Model 8080' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080 `
    -RemoteAddress $ubuntu -Profile Any -Description 'MedRack: Ubuntu â†’ Qwopus llama-server' | Out-Null
New-NetFirewallRule -DisplayName 'MedRack LAN OCR 8090' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8090 `
    -RemoteAddress $ubuntu -Profile Any -Description 'MedRack: Ubuntu â†’ OCR agent' | Out-Null
# Also allow any Private profile (laptops / DHCP IP change of Ubuntu)
New-NetFirewallRule -DisplayName 'MedRack LAN Model 8080 (Private)' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080 `
    -Profile Private -Description 'MedRack Qwopus on private LAN' | Out-Null
New-NetFirewallRule -DisplayName 'MedRack LAN OCR 8090 (Private)' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8090 `
    -Profile Private -Description 'MedRack OCR on private LAN' | Out-Null
OK "Firewall allows TCP 8080 + 8090 from $ubuntu and Private networks"

# ---------- Helper: register long-running task ----------
function Register-MedrackTask {
    param(
        [string]$Name,
        [string]$Execute,
        [string]$Argument,
        [string]$WorkDir,
        [switch]$AtLogOn,
        [switch]$AtStartup,
        [int]$RestartMinutes = 1
    )
    $action = New-ScheduledTaskAction -Execute $Execute -Argument $Argument -WorkingDirectory $WorkDir
    $triggers = @()
    if ($AtLogOn)   { $triggers += (New-ScheduledTaskTrigger -AtLogOn -User $user) }
    if ($AtStartup) { $triggers += (New-ScheduledTaskTrigger -AtStartup) }
    if (-not $triggers) { $triggers = @(New-ScheduledTaskTrigger -AtLogOn -User $user) }

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes $RestartMinutes) `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -DontStopOnIdleEnd `
        -Hidden

    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest

    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $triggers `
        -Principal $principal -Settings $settings -Force | Out-Null
    OK "Task '$Name' registered (hidden / no console)"
}

# ---------- OCR agent task (hidden PowerShell — no desktop console) ----------
Section 'Scheduled Task: MedRack OCR Agent (always on, hidden)'
if (-not (Test-Path $cfg.OcrAgentPython) -or -not (Test-Path $cfg.OcrAgentScript)) {
    throw "OCR agent missing under $($cfg.OcrAgentDir)"
}
$ocrHidden = Join-Path $cfg.OcrAgentDir 'start-ocr-agent-hidden.ps1'
if (-not (Test-Path $ocrHidden)) { throw "Missing $ocrHidden" }

Register-MedrackTask -Name 'MedRack OCR Agent' `
    -Execute 'powershell.exe' `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ocrHidden`"") `
    -WorkDir $cfg.OcrAgentDir `
    -AtLogOn -AtStartup `
    -RestartMinutes 1

# ---------- Tunnel backup task (hidden PowerShell — no desktop console) ----------
Section 'Scheduled Task: MedRack OCR Tunnel (backup reverse SSH, hidden)'
$tunHidden = Join-Path $PSScriptRoot 'start-ocr-tunnel-hidden.ps1'
if (-not (Test-Path $tunHidden)) { throw "Missing $tunHidden" }

Register-MedrackTask -Name 'MedRack OCR Tunnel' `
    -Execute 'powershell.exe' `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$tunHidden`"") `
    -WorkDir $PSScriptRoot `
    -AtLogOn -AtStartup `
    -RestartMinutes 1

# ---------- Watchdog (every 5 minutes) ----------
Section 'Scheduled Task: MedRack Link Watchdog'
$watch = Join-Path $PSScriptRoot 'medrack-link-watchdog.ps1'
Register-MedrackTask -Name 'MedRack Link Watchdog' `
    -Execute 'powershell.exe' `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watch`"") `
    -WorkDir $PSScriptRoot `
    -AtLogOn `
    -RestartMinutes 5

# Also a repeating trigger every 5 minutes
$wd = Get-ScheduledTask -TaskName 'MedRack Link Watchdog'
$rep = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ((New-TimeSpan -Days 3650))
$logon = New-ScheduledTaskTrigger -AtLogOn -User $user
Set-ScheduledTask -TaskName 'MedRack Link Watchdog' -Trigger @($logon, $rep) | Out-Null
OK 'Watchdog runs at logon and every 5 minutes'

# ---------- Start services now ----------
Section 'Starting link services now'
try { Start-ScheduledTask -TaskName 'MedRack OCR Agent' } catch { Warn $_ }
Start-Sleep -Seconds 4
try { Start-ScheduledTask -TaskName 'MedRack OCR Tunnel' } catch { Warn $_ }
Start-Sleep -Seconds 3
try { Start-ScheduledTask -TaskName 'MedRack Link Watchdog' } catch { Warn $_ }

# Local health
$okAgent = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$($cfg.OcrAgentPort)/v1/health" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { $okAgent = $true; OK "OCR agent health OK on :$($cfg.OcrAgentPort)" }
} catch { Warn "OCR agent not healthy yet: $_" }

$okModel = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$($cfg.ModelPort)/health" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { $okModel = $true; OK "Model health OK on :$($cfg.ModelPort)" }
} catch { Warn "Model not running (Start MedRack will start it when needed)" }

Write-Host ''
Write-Host '============================================' -ForegroundColor Green
Write-Host '  Permanent link installed' -ForegroundColor Green
Write-Host '  Tasks: MedRack OCR Agent | OCR Tunnel | Link Watchdog' -ForegroundColor Green
Write-Host '  Ubuntu direct: http://192.168.29.89:8090' -ForegroundColor Green
Write-Host '  Tunnel backup: Ubuntu 127.0.0.1:18090' -ForegroundColor Green
Write-Host '============================================' -ForegroundColor Green
Write-Host ''
if ($env:MEDRACK_LINK_SILENT -ne '1') {
    try { Read-Host 'Press Enter to close' } catch {}
}
# Write status marker for non-interactive verification
try {
    Set-Content -Path (Join-Path $PSScriptRoot 'permanent-link.installed') -Value (Get-Date -Format o) -Encoding UTF8
} catch {}

