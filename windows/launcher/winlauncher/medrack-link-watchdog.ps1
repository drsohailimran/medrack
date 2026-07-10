# MedRack link watchdog — keep OCR agent (+ tunnel) alive on Windows.
# Invoked by scheduled task every 5 minutes and at logon.
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'medrack-config.ps1')
$cfg = $MedrackConfig
$log = Join-Path $cfg.OcrAgentDir 'link-watchdog.log'

function Write-Log([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    try { Add-Content -Path $log -Value $line -Encoding UTF8 } catch {}
}

function Test-LocalPort([int]$port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', $port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(800)
        if ($ok) { try { $c.EndConnect($iar) } catch { $ok = $false } }
        $c.Close()
        return $ok
    } catch { return $false }
}

function Test-Http([string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
    } catch { return $false }
}

# Clear stop flags so watchdog can bring agent back
if ($cfg.OcrAgentStopFlag -and (Test-Path $cfg.OcrAgentStopFlag)) {
    # Only clear if agent is down — Stop MedRack may have just set it.
    # If agent is supposed to be permanent, we clear stop flag after 2 minutes of downtime.
    try { Remove-Item $cfg.OcrAgentStopFlag -Force -ErrorAction SilentlyContinue } catch {}
}

# --- OCR agent ---
$agentUp = (Test-LocalPort $cfg.OcrAgentPort) -and (Test-Http "http://127.0.0.1:$($cfg.OcrAgentPort)/v1/health")
if (-not $agentUp) {
    Write-Log 'OCR agent DOWN — starting task MedRack OCR Agent'
    try {
        Start-ScheduledTask -TaskName 'MedRack OCR Agent' -ErrorAction Stop
    } catch {
        # Fallback: start cmd directly
        $startCmd = Join-Path $cfg.OcrAgentDir 'START-OCR-AGENT.cmd'
        if (Test-Path $startCmd) {
            Start-Process 'cmd.exe' -ArgumentList '/c', "start `"MedRack OCR Agent`" /MIN `"$startCmd`"" -WindowStyle Hidden
            Write-Log 'Started OCR agent via START-OCR-AGENT.cmd fallback'
        } else {
            Write-Log ("Failed to start OCR agent: {0}" -f $_)
        }
    }
} else {
    Write-Log 'OCR agent OK'
}

# --- Reverse tunnel (backup path for Ubuntu) ---
$tunAlive = $false
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -like "*$($cfg.OcrTunnelRemotePort):127.0.0.1:$($cfg.OcrAgentPort)*" -or
            $_.CommandLine -like "*-R $($cfg.OcrTunnelRemotePort):*"
        )
    } | ForEach-Object { $tunAlive = $true }

if (-not $tunAlive) {
    Write-Log 'OCR tunnel DOWN — starting task MedRack OCR Tunnel'
    try {
        Start-ScheduledTask -TaskName 'MedRack OCR Tunnel' -ErrorAction Stop
    } catch {
        $tunCmd = Join-Path $PSScriptRoot 'start-ocr-tunnel.cmd'
        if (Test-Path $tunCmd) {
            Start-Process 'cmd.exe' -ArgumentList '/c', "start `"MedRack OCR Tunnel`" /MIN `"$tunCmd`"" -WindowStyle Hidden
            Write-Log 'Started tunnel via start-ocr-tunnel.cmd fallback'
        } else {
            Write-Log ("Failed to start tunnel: {0}" -f $_)
        }
    }
} else {
    Write-Log 'OCR tunnel process OK'
}

# Optional: probe Ubuntu can see us (best-effort, non-fatal)
if ($cfg.SshKey -and (Test-Path $cfg.SshKey)) {
    try {
        $probe = & ssh.exe -i $cfg.SshKey -o BatchMode=yes -o ConnectTimeout=6 `
            "$($cfg.LinuxUser)@$($cfg.LinuxHost)" `
            "curl -sS --max-time 4 http://$($cfg.WindowsLanHost):$($cfg.OcrAgentPort)/v1/health 2>/dev/null | head -c 80; echo; curl -sS --max-time 3 http://127.0.0.1:$($cfg.OcrTunnelRemotePort)/v1/health 2>/dev/null | head -c 80" 2>$null
        Write-Log ("Ubuntu probe: {0}" -f (($probe -join ' ') -replace '\s+', ' ').Trim())
    } catch {
        Write-Log 'Ubuntu probe skipped/failed'
    }
}
