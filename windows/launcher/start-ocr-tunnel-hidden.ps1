# MedRack OCR reverse tunnel - NO console window (stays alive reconnecting).
# ASCII-only script (encoding-safe for Windows PowerShell 5).
$ErrorActionPreference = 'Continue'
$LogDir = 'C:\Medrack\ocr'
if (-not (Test-Path $LogDir)) { $LogDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$OutLog = Join-Path $LogDir 'tunnel.out.log'
$Key = Join-Path $env:USERPROFILE '.ssh\medrack_ed25519'
$Remote = 'sohail@192.168.29.82'
$RPort = 18090
$LPort = 8090

function Write-TLog([string]$msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    try { Add-Content -Path $OutLog -Value $line -Encoding UTF8 } catch {}
}

if (-not (Test-Path -LiteralPath $Key)) {
    Write-TLog "SSH key missing: $Key"
    exit 1
}

# Already have a tunnel?
$existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq 'ssh.exe' -and $_.CommandLine -and ($_.CommandLine -match "-R\s+$RPort`:")
}
if ($existing) {
    $pid0 = ($existing | Select-Object -First 1).ProcessId
    Write-TLog "Tunnel already running pid=$pid0 - exiting duplicate"
    exit 0
}

Write-TLog 'Tunnel supervisor starting (hidden)'

while ($true) {
    $agentOk = $false
    for ($i = 0; $i -lt 24; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$LPort/v1/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $agentOk = $true; break }
        } catch {}
        Start-Sleep -Seconds 5
    }
    if (-not $agentOk) {
        Write-TLog 'OCR agent not up yet - retrying in 15s'
        Start-Sleep -Seconds 15
        continue
    }

    try {
        Start-Process -FilePath 'ssh.exe' -ArgumentList @(
            '-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
            '-o', 'StrictHostKeyChecking=accept-new', $Remote,
            "fuser -k $RPort/tcp 2>/dev/null; true"
        ) -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue | Out-Null
    } catch {}

    Write-TLog "Connecting reverse tunnel $RPort -> 127.0.0.1:$LPort"
    $sshArgs = @(
        '-i', $Key, '-N',
        '-o', 'BatchMode=yes',
        '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=20',
        '-o', 'ServerAliveCountMax=3',
        '-o', 'StrictHostKeyChecking=accept-new',
        '-R', "${RPort}:127.0.0.1:${LPort}",
        $Remote
    )
    $p = Start-Process -FilePath 'ssh.exe' -ArgumentList $sshArgs -WindowStyle Hidden -PassThru -Wait
    $code = if ($null -ne $p) { $p.ExitCode } else { -1 }
    Write-TLog "Tunnel dropped (exit $code). Retry in 8s..."
    Start-Sleep -Seconds 8
}
