# ============================================================
#  MedRack - one-click STOP
#  Frees this PC's RAM/GPU by stopping the Qwopus model, and
#  best-effort stops MedRack on the Linux box.
# ============================================================

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'medrack-config.ps1')
$cfg = $MedrackConfig

Add-Type -AssemblyName System.Windows.Forms

# ---- 1. Stop the model on this PC (the expensive part) ----
# The model runs under an auto-restart watchdog, so we must FIRST drop a
# stop-flag (which the watchdog checks) and only THEN kill llama-server -
# otherwise the watchdog would just relaunch it.
$stopped = @()
if ($cfg.ModelStopFlag) {
    try { New-Item -ItemType File -Path $cfg.ModelStopFlag -Force | Out-Null } catch {}
}
$proc = Get-Process llama-server -ErrorAction SilentlyContinue
if ($proc) {
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    $stopped += 'AI model (this PC)'
}
# Give the watchdog a moment to see the flag and exit its loop.
Start-Sleep -Milliseconds 800

# ---- 1b. Stop OCR agent + reverse tunnel ----
if ($cfg.OcrAgentStopFlag) {
    try { New-Item -ItemType File -Path $cfg.OcrAgentStopFlag -Force | Out-Null } catch {}
}
try {
    $conns = Get-NetTCPConnection -LocalPort $cfg.OcrAgentPort -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        if ($c.OwningProcess) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            $stopped += 'OCR agent (this PC)'
        }
    }
} catch {}
# Kill OCR SSH reverse tunnels
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -like "*$($cfg.OcrTunnelRemotePort):127.0.0.1:$($cfg.OcrAgentPort)*" -or
            $_.CommandLine -like "*-R $($cfg.OcrTunnelRemotePort):*"
        )
    } |
    ForEach-Object {
        try {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            $stopped += 'OCR tunnel'
        } catch {}
    }

# ---- 2. Best-effort stop MedRack on the Linux box ----
# Leaving MedRack running is harmless (it's lightweight), so this is
# best-effort only and never blocks.
if (Test-Path $cfg.SshKey) {
    # Quote the key path explicitly (it may contain spaces).
    $sshCmd = '-i "{0}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 {1}@{2} {3}' -f `
        $cfg.SshKey, $cfg.LinuxUser, $cfg.LinuxHost, $cfg.RemoteStop
    try {
        $p = Start-Process 'ssh' -ArgumentList $sshCmd -WindowStyle Hidden -PassThru
        if (-not $p.WaitForExit(15000)) { try { $p.Kill() } catch {} }
        else { $stopped += 'MedRack (server)' }
    } catch {}
}

$msg = if ($stopped.Count) { "Stopped:`n  - " + ($stopped -join "`n  - ") }
       else { 'Nothing was running.' }
[System.Windows.Forms.MessageBox]::Show($msg, 'MedRack - Stop', 'OK', 'Information') | Out-Null
