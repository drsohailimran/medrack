# ============================================================
#  MedRack launcher - ONE-TIME SETUP
#  Run this ONCE. Double-click it, click "Yes" on the Windows
#  security prompt, and enter the server password when asked
#  (this is the only time you'll ever type it).
#
#  It will:
#    1. Register an elevated Scheduled Task for the model
#       (so daily start needs no admin popup)
#    2. Create a passwordless SSH key and authorize it on the box
#    3. Create "Start MedRack" and "Stop MedRack" desktop shortcuts
# ============================================================

# ---- Self-elevate (needed to register the highest-privilege task) ----
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
function OK([string]$t)      { Write-Host "  [OK] $t"   -ForegroundColor Green }
function Warn([string]$t)    { Write-Host "  [!!] $t"   -ForegroundColor Yellow }

Write-Host '============================================' -ForegroundColor Cyan
Write-Host '   MedRack launcher - one-time setup'          -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan

# ===== 1. Scheduled task for the model (elevated, on-demand) =====
Section 'Registering the model task (no more admin popups)'
if (-not (Test-Path $cfg.ModelBat)) {
    throw "Model batch file not found: $($cfg.ModelBat)"
}
$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument ('/c "' + $cfg.ModelBat + '"')
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $cfg.ModelTaskName -Action $action `
    -Principal $principal -Settings $settings -Force | Out-Null
OK "Task '$($cfg.ModelTaskName)' registered."

# ===== 2. SSH key =====
Section 'Setting up passwordless SSH'
$sshDir = Split-Path $cfg.SshKey -Parent
if (-not (Test-Path $sshDir)) { New-Item -ItemType Directory -Path $sshDir -Force | Out-Null }

if (Test-Path $cfg.SshKey) {
    OK 'SSH key already exists, reusing it.'
} else {
    # cmd /c avoids PowerShell 5.1 mangling the empty-passphrase argument.
    cmd /c "ssh-keygen -t ed25519 -f `"$($cfg.SshKey)`" -N `"`" -C medrack-launcher" | Out-Null
    if (-not (Test-Path $cfg.SshKey)) { throw 'ssh-keygen failed to create the key.' }
    OK 'Created a new SSH key.'
}

$pub = (Get-Content "$($cfg.SshKey).pub" -Raw).Trim()
$target = "$($cfg.LinuxUser)@$($cfg.LinuxHost)"

# Check whether the key already works (setup may be re-run safely).
$test = & ssh -i $cfg.SshKey -o BatchMode=yes -o StrictHostKeyChecking=accept-new `
    -o ConnectTimeout=8 $target 'echo medrack-key-ok' 2>$null
if ($test -eq 'medrack-key-ok') {
    OK 'Passwordless login already works.'
} else {
    # The password step is done by AUTHORIZE-SERVER.cmd, NOT here. Typing a
    # password inside this elevated window is fragile (invisible input, easy to
    # close by mistake), so we keep it as a separate, clearly-labelled step.
    Warn 'Passwordless login is NOT set up yet.'
    Write-Host ''
    Write-Host '   >> After this window closes, double-click AUTHORIZE-SERVER.cmd' -ForegroundColor Yellow
    Write-Host '      in C:\Medrack\launcher and type the server password once.' -ForegroundColor Yellow
    Write-Host ''
}

# ===== 3. Desktop shortcuts =====
Section 'Creating desktop shortcuts'
$desktop = [Environment]::GetFolderPath('Desktop')
$ws = New-Object -ComObject WScript.Shell

function New-Shortcut([string]$name, [string]$script, [string]$icon) {
    $lnk = $ws.CreateShortcut((Join-Path $desktop $name))
    $lnk.TargetPath = 'powershell.exe'
    $lnk.Arguments  = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation = $icon
    $lnk.WindowStyle  = 7   # minimized
    $lnk.Description   = 'MedRack'
    $lnk.Save()
    OK "Created '$name' on the Desktop."
}
New-Shortcut 'Start MedRack.lnk' (Join-Path $PSScriptRoot 'medrack-launcher.ps1') "$env:SystemRoot\System32\shell32.dll,137"
New-Shortcut 'Stop MedRack.lnk'  (Join-Path $PSScriptRoot 'medrack-stop.ps1')     "$env:SystemRoot\System32\shell32.dll,27"

Write-Host ''
Write-Host '============================================' -ForegroundColor Green
Write-Host '   Setup complete!' -ForegroundColor Green
Write-Host '   Double-click "Start MedRack" on the Desktop.' -ForegroundColor Green
Write-Host '============================================' -ForegroundColor Green
Write-Host ''
Read-Host 'Press Enter to close'
